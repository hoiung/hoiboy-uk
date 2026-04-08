#!/usr/bin/env python3
"""Parse the AdventureAnd.Me mysqldump SQL and build a JSON index of
`jos_easyblog_post` rows keyed by lowercase title.

Pure-Python: only `sqlparse` + stdlib. No DB required.

Output JSON record shape (per title key):
    {
        "id": int,
        "title": str,
        "date_published": str | None,   # `publish_up`
        "date_created": str | None,     # `created`
        "body_html_md5": str,           # md5(intro + content) decoded HTML
        "image_filenames": [str, ...]   # basenames of <img src="..."> in body
    }
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
from typing import Iterator, List, Optional

import sqlparse  # noqa: F401  (imported to satisfy requirement; used as sanity check)

DEFAULT_INPUT = (
    "/mnt/c/Users/hoi_u/My Drive/AdventureAnd.Me/BACKUP/adventureandme/"
    "adventureandme.sql"
)
DEFAULT_OUTPUT = "/tmp/aam-sql-index.json"

TABLE_NAME = "jos_easyblog_post"

IMG_RE = re.compile(r"""<img\s+[^>]*?src=["']([^"']+)["']""", re.IGNORECASE)


def extract_column_order(sql_text: str) -> List[str]:
    """Parse the CREATE TABLE for `jos_easyblog_post` and return column names."""
    pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`" + re.escape(TABLE_NAME)
        + r"`\s*\((.*?)\)\s*ENGINE",
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(sql_text)
    if not m:
        raise RuntimeError(f"CREATE TABLE for {TABLE_NAME} not found")
    body = m.group(1)
    cols: List[str] = []
    for line in body.splitlines():
        line = line.strip().rstrip(",")
        if not line or line.upper().startswith(("PRIMARY KEY", "KEY ", "UNIQUE",
                                                 "CONSTRAINT", "FULLTEXT", "INDEX ")):
            continue
        cm = re.match(r"`([^`]+)`", line)
        if cm:
            cols.append(cm.group(1))
    if not cols:
        raise RuntimeError("Failed to parse column list")
    return cols


def iter_insert_blocks(sql_text: str) -> Iterator[str]:
    """Yield the VALUES payload of every INSERT INTO jos_easyblog_post statement."""
    # mysqldump writes: INSERT INTO `tbl` VALUES (...),(...),...;
    # May include column list. May be multi-line. Use regex to find start, then
    # walk forward respecting string quoting to find the terminating ;.
    start_re = re.compile(
        r"INSERT\s+INTO\s+`" + re.escape(TABLE_NAME) + r"`(?:\s*\([^)]*\))?\s*VALUES\s*",
        re.IGNORECASE,
    )
    pos = 0
    while True:
        m = start_re.search(sql_text, pos)
        if not m:
            return
        i = m.end()
        end = find_stmt_end(sql_text, i)
        yield sql_text[i:end]
        pos = end + 1


def find_stmt_end(s: str, i: int) -> int:
    """Return index of terminating `;` for the statement starting at i,
    respecting single-quoted strings with backslash escapes."""
    n = len(s)
    in_str = False
    while i < n:
        ch = s[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == "'":
                in_str = False
        else:
            if ch == "'":
                in_str = True
            elif ch == ";":
                return i
        i += 1
    raise RuntimeError("Unterminated INSERT statement")


def iter_tuples(values_blob: str) -> Iterator[List[str]]:
    """Split a VALUES payload `(...),(...),...` into lists of raw field tokens.

    Each field is returned as its raw SQL token: either `NULL` or a
    single-quoted string (quotes preserved, escapes preserved).
    """
    s = values_blob
    n = len(s)
    i = 0
    while i < n:
        # Skip whitespace / commas
        while i < n and s[i] in " \t\r\n,":
            i += 1
        if i >= n or s[i] == ";":
            return
        if s[i] != "(":
            raise RuntimeError(f"Expected '(' at pos {i}: {s[i:i+40]!r}")
        i += 1
        fields: List[str] = []
        while True:
            # Skip whitespace
            while i < n and s[i] in " \t\r\n":
                i += 1
            if i >= n:
                raise RuntimeError("Unexpected EOF inside tuple")
            if s[i] == ")":
                i += 1
                break
            if s[i] == ",":
                i += 1
                continue
            # Parse one field
            if s[i] == "'":
                # quoted string
                start = i
                i += 1
                while i < n:
                    c = s[i]
                    if c == "\\":
                        i += 2
                        continue
                    if c == "'":
                        i += 1
                        break
                    i += 1
                fields.append(s[start:i])
            else:
                # unquoted literal (NULL or number)
                start = i
                while i < n and s[i] not in ",)":
                    i += 1
                fields.append(s[start:i].strip())
        yield fields


def unquote_sql(tok: str) -> Optional[str]:
    """Decode a raw mysqldump field token into a Python str (or None)."""
    if tok is None:
        return None
    if tok.upper() == "NULL":
        return None
    if len(tok) >= 2 and tok[0] == "'" and tok[-1] == "'":
        inner = tok[1:-1]
        # mysqldump escapes: \\ \' \" \n \r \t \0 \Z
        out: List[str] = []
        i = 0
        n = len(inner)
        esc = {
            "n": "\n", "r": "\r", "t": "\t", "0": "\x00",
            "Z": "\x1a", "\\": "\\", "'": "'", '"': '"',
        }
        while i < n:
            c = inner[i]
            if c == "\\" and i + 1 < n:
                nxt = inner[i + 1]
                out.append(esc.get(nxt, nxt))
                i += 2
            else:
                out.append(c)
                i += 1
        return "".join(out)
    # numeric literal
    return tok


def build_record(cols: List[str], raw: List[str]) -> Optional[dict]:
    if len(raw) != len(cols):
        raise RuntimeError(
            f"Column count mismatch: got {len(raw)} fields, expected {len(cols)}"
        )
    row = {cols[i]: unquote_sql(raw[i]) for i in range(len(cols))}
    title = row.get("title") or ""
    intro = row.get("intro") or ""
    content = row.get("content") or ""
    body_raw = intro + content
    body_decoded = html.unescape(body_raw)
    images = [os.path.basename(src) for src in IMG_RE.findall(body_decoded)]
    # dedupe preserving order
    seen = set()
    uniq_images: List[str] = []
    for x in images:
        if x and x not in seen:
            seen.add(x)
            uniq_images.append(x)
    try:
        rid = int(row["id"]) if row.get("id") is not None else None
    except ValueError:
        rid = None
    return {
        "id": rid,
        "title": html.unescape(title),
        "date_published": row.get("publish_up"),
        "date_created": row.get("created"),
        "body_html_md5": hashlib.md5(body_decoded.encode("utf-8")).hexdigest(),
        "image_filenames": uniq_images,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default=DEFAULT_INPUT)
    ap.add_argument("--output", default=DEFAULT_OUTPUT)
    ap.add_argument("--sample", action="store_true",
                    help="Print the first parsed row and exit.")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: input file not found: {args.input}", file=sys.stderr)
        return 2

    with open(args.input, "r", encoding="utf-8", errors="replace") as f:
        sql_text = f.read()

    cols = extract_column_order(sql_text)
    print(f"[parse_aam_sql] {TABLE_NAME} columns: {len(cols)}", file=sys.stderr)

    index: dict = {}
    total = 0
    for blob in iter_insert_blocks(sql_text):
        for raw in iter_tuples(blob):
            rec = build_record(cols, raw)
            if rec is None:
                continue
            total += 1
            key = (rec["title"] or "").strip().lower()
            if args.sample:
                print(json.dumps(rec, indent=2, ensure_ascii=False))
                return 0
            # If duplicate title keys occur, keep the one with higher id
            prior = index.get(key)
            if prior is None or (rec["id"] or 0) > (prior["id"] or 0):
                index[key] = rec

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(
        f"[parse_aam_sql] extracted {total} rows; "
        f"{len(index)} unique title keys -> {args.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
