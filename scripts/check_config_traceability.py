#!/usr/bin/env python3
"""Config traceability: every key in params.toml is read by layouts/.

Greps layouts/ (NOT vendored themes) for each top-level key in params.toml.
Dead key (declared but never read) = FAIL. Standards Fail Fast.
"""
from __future__ import annotations
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARAMS = ROOT / "config" / "_default" / "params.toml"
LAYOUTS = ROOT / "layouts"
ASSETS = ROOT / "assets"

# Keys declared but not greppable in layouts (none currently). Document each.
EXEMPT: set[str] = set()


def _token(key: str) -> str:
    """Identifier-bounded pattern for one key name."""
    return r"(?<![A-Za-z0-9_-])" + re.escape(key) + r"(?![A-Za-z0-9_-])"


def is_key_referenced(key: str, text: str, parent: str | None = None) -> bool:
    """True if `key` appears in `text` as a standalone identifier token.

    A plain substring test is toothless: a dead key that is a substring of an
    unrelated token reads as referenced (e.g. `accent` inside `--accent-color`
    or `author` inside `authorSameAs`). Require an identifier boundary on both
    sides — treating `-` as part of a token — so `accent` does NOT match
    `accent-color` but `site.Params.accentColor` still matches `accentColor`.

    PARENT-TABLE SCOPING. Identifier boundaries are not table scoping, and the
    two were being conflated: a key nested under `[social]` was searched for by
    its BARE name against the whole concatenated layouts text, so a genuinely
    dead `[social] title` passed as referenced the moment any unrelated template
    mentioned `title`. Boundary matching only rules out substrings of one token;
    it says nothing about which table the token belongs to.

    For a nested key both real Hugo idioms count, and nothing else:
      site.Params.social.title   the dotted path
      with site.Params.social    ... .title   a scoped block
    A bare `title` with no `social` anywhere does not.

    Measured when this landed: params.toml has no nested tables at all, so this
    changes no verdict today. It closes the class before the first nested table
    introduces it, which is the same reason extract_keys moved to tomllib.
    """
    if re.search(_token(key), text) is None:
        return False
    if parent is None:
        return True
    dotted = re.search(_token(parent) + r"\." + re.escape(key)
                       + r"(?![A-Za-z0-9_-])", text)
    if dotted:
        return True
    # A `with`/`range` block names the parent once, then reads `.child`.
    scoped = re.search(_token(parent), text) and re.search(
        r"\." + re.escape(key) + r"(?![A-Za-z0-9_-])", text)
    return bool(scoped)


def extract_keys(toml: str) -> list[tuple[str, str | None]]:
    """Every param key declared in params.toml, nested tables included.

    Parsed with `tomllib` (Python 3.11+ stdlib, no dependency) rather than
    scanned line by line. The scanner read any line containing `=` as a
    declaration, so prose inside a TOML multi-line string - a bio block with
    `something = other` in it - registered as a key that layouts must then
    reference, and a key inside a nested table registered under its bare name
    with no way to tell the two apart.

    Measured on the current params.toml both approaches yield the same 8 keys,
    so this changes no verdict today. It removes the class rather than waiting
    for the first multi-line value to introduce it.
    """
    try:
        data = tomllib.loads(toml)
    except tomllib.TOMLDecodeError as exc:
        print(f"FAIL: {PARAMS} is not valid TOML: {exc}", file=sys.stderr)
        raise SystemExit(1)

    keys: list[tuple[str, str | None]] = []

    def walk(table: dict, parent: str | None = None) -> None:
        for key, value in table.items():
            keys.append((key, parent))
            if isinstance(value, dict):
                walk(value, key)

    walk(data)
    return keys


def main() -> int:
    if not PARAMS.exists():
        print(f"FAIL: {PARAMS} missing", file=sys.stderr)
        return 1
    if not LAYOUTS.exists():
        print(f"FAIL: {LAYOUTS} missing", file=sys.stderr)
        return 1

    # utf-8-sig: tomllib REJECTS a leading BOM outright (blog-priv#63 round 7).
    keys = extract_keys(PARAMS.read_text(encoding="utf-8-sig"))
    layout_text = ""
    for f in LAYOUTS.rglob("*.html"):
        layout_text += f.read_text(encoding="utf-8")
    if ASSETS.exists():
        for f in ASSETS.rglob("*.css"):
            layout_text += f.read_text(encoding="utf-8")

    dead: list[str] = []
    for k, parent in keys:
        if k in EXEMPT:
            continue
        if not is_key_referenced(k, layout_text, parent):
            dead.append(f"{parent}.{k}" if parent else k)

    if dead:
        print("CONFIG TRACEABILITY FAILED:", file=sys.stderr)
        for k in dead:
            print(f"  dead key in params.toml: {k}", file=sys.stderr)
        return 1
    print(f"Config traceability OK ({len(keys)} keys, {len(EXEMPT)} exempt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
