#!/usr/bin/env python3
"""Frontmatter contract for hoiboy.uk posts and project pages.

Posts (content/posts/)            required: title, date, categories, tags, description
Project pages (content/consulting/) required: title, description

Phase 0 inline schema. 08_FRONTMATTER_SCHEMA.md is deferred to Phase 1
once real WordPress posts shape the schema.

Walks content/posts/ and content/consulting/, parses YAML frontmatter,
validates required fields. Fails loudly. Uses a tiny YAML parser (no
third-party deps in CI).

`description` became REQUIRED on 2026-07-20 (blog-priv#55 Phase 2). Before
that it sat in OPTIONAL, so 33 posts (32 legacy plus one dated on the
2026-04-07 cutoff) rendered with the site-default
meta description, so they shipped as near-duplicates of each other. Phase 1
backfilled all 33; this gate stops the field regressing. This is SEO hygiene,
not a GEO lever: nothing supports a claim that unique descriptions increase
AI citations (see the /blog skill's SEO/GEO authoring rules).

Project pages carry a SEPARATE, smaller required set: they have no
categories/tags taxonomy, and several legitimately carry no date (the
service pages set `hideDate: true`). Applying the post contract to them
would hard-fail a compliant tree.
"""
from __future__ import annotations
import argparse
import sys
import re
from pathlib import Path

REQUIRED = {"title", "date", "categories", "tags", "description"}
# Project/service pages under content/consulting/ (including portfolio/<client>/).
# Intentionally NOT the post contract - see module docstring.
CONSULTING_REQUIRED = {"title", "description"}
# Optional fields (informational schema, not enforced for backward compat).
# `series` + `order` added 2026-04-26 (Issue #3) for the bake-off teaser series
# taxonomy. Posts lacking these fields continue to validate as PASS.
OPTIONAL = {"slug", "draft", "series", "order", "lastmod", "hideDate", "type"}
# Allowed category values. Sourced from config/_default/menus.toml at runtime.
# A typo like categories: [foood] would create an orphan term page no
# sidebar link reaches. Hard fail.
ALLOWED_CATEGORIES = {"food-booze", "adventure", "dance", "tech-ai", "life", "entrepreneurship", "trading"}
# Content formats Hugo renders natively. Kept identical to CONTENT_EXTS in
# scripts/check_social_cards.py: a walk narrower than this silently skips real
# pages, and a skipped page passes the contract by omission rather than by
# compliance. Matching only `index.md` would miss a flat `content/consulting/x.md`
# single page entirely.
CONTENT_EXTS = (".md", ".markdown", ".html")
ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "content" / "posts"
CONSULTING = ROOT / "content" / "consulting"


def strip_trailing_comment(value: str) -> str:
    """Drop an unquoted trailing YAML comment from a scalar value.

    In YAML a `#` starts a comment when it follows whitespace, so
    `description: ~ # TODO` is the null `~`, not the string "~ # TODO".
    The sentinel test below compares by exact match, so without this a null
    sentinel with any trailing comment sailed through as a present value while
    Hugo served the site default (Ralph round 21, blocker; proven end to end on
    a real build). Five shapes were affected: `null`, `Null`, `NULL`, `~` and a
    quoted empty string, each with a trailing comment.

    A `#` inside a quoted scalar is literal, so a value that opens with a quote
    is cut only after its closing quote. That keeps `description: "hello #
    world"` intact, which is the false-failure this would otherwise introduce.
    """
    if value[:1] in ('"', "'"):
        quote = value[0]
        close = value.find(quote, 1)
        if close == -1:
            return value  # unterminated; leave it alone, not ours to repair
        head, tail = value[: close + 1], value[close + 1:]
        return head if re.match(r"^\s+#", tail) or tail.strip() == "" else value
    cut = re.split(r"(?:^|\s)#", value, maxsplit=1)[0]
    return cut.strip()


def parse_frontmatter(text: str) -> dict[str, object] | None:
    """Minimal YAML frontmatter parser. Handles strings, bracketed lists,
    block lists, folded/literal block scalars, and quoted values with colons
    inside. Sufficient for blog frontmatter.

    KNOWN DIVERGENCES FROM REAL YAML (Ralph rounds 16-18, all measured against
    PyYAML and a real Hugo build). These shapes resolve to an empty value in
    YAML, so Hugo serves the site-default description, but they parse to a
    non-empty string here and so pass the presence gate:

        description: !!str              (empty explicit type tag)
        description: *anchor            (alias to an anchored empty string)

    And this one passes here but hard-fails the Hugo build later:

        description: >
        <TAB>text                       (tab-indented continuation)

    None appear in any current post, and the real Hugo build in pre-publish
    gate 7 and CI catches the tab case before anything ships. Fixing the class
    properly means replacing this function with PyYAML, which is a scoped
    change of its own (operator decision, 2026-07-20: patch-and-ship #55, track
    the swap separately) rather than another sentinel bolted on here. If you
    are about to add a fourth special case to the branch below, do the swap
    instead. Every shape listed above has to keep being caught after it.
    """
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    body = text[3:end].strip()
    out: dict[str, object] = {}
    current_key: str | None = None
    # Open block scalar (`description: >` / `|`), if any. Tracked as state so
    # the single pass below can fold the indented continuation lines into the
    # value. Without this a block scalar parsed to the literal indicator ">",
    # which is non-empty, so an EMPTY one counted as a present description
    # while Hugo resolved it to "" and served the site default (Ralph round 17).
    # Treating a bare ">" as empty without also reading the continuation would
    # just trade that for a false failure on a block scalar that DOES have text.
    block_key: str | None = None
    block_lines: list[str] = []
    block_indent: int | None = None

    def close_block() -> None:
        # current_key is cleared too, so a stray dash-list line with no
        # governing key cannot be misattributed to the block key just closed
        # and overwrite its resolved string with a list (Ralph round 18).
        nonlocal block_key, block_lines, block_indent, current_key
        if block_key is not None:
            out[block_key] = " ".join(x for x in block_lines if x).strip()
            current_key = None
        block_key, block_lines, block_indent = None, [], None

    for raw in body.splitlines():
        line = raw.rstrip()
        if block_key is not None:
            if not line.strip():
                continue
            indent = len(raw) - len(raw.lstrip())
            if block_indent is None and indent > 0:
                block_indent = indent
            if block_indent is not None and indent >= block_indent:
                block_lines.append(line.strip())
                continue
            close_block()  # dedented: the block ended, parse this line normally
        if not line or line.startswith("#"):
            continue
        # Block-list item belonging to the key above:
        #     categories:
        #       - entrepreneurship
        # Without this the key parses to an empty string, which made the
        # category allowlist check silently skip the page (the isinstance
        # list-guard below never fired) and, once blank values counted as
        # missing, produced a false "missing categories" on a correctly
        # categorised post. 1 of 78 posts uses this form; a typo'd category
        # in it would never have been caught.
        item = re.match(r"^\s*-\s+(.*)$", raw)
        if item and current_key is not None:
            value = item.group(1).strip().strip('"').strip("'")
            existing = out.get(current_key)
            if isinstance(existing, list):
                existing.append(value)
            else:
                out[current_key] = [value]
            continue
        # Key: value pattern. Match the FIRST colon that follows an
        # unquoted key (no quotes/brackets in the key portion).
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            key = m.group(1)
            value = strip_trailing_comment(m.group(2).strip())
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                items = [s.strip().strip('"').strip("'") for s in inner.split(",") if s.strip()]
                out[key] = items
            elif value.startswith('"') and value.endswith('"'):
                out[key] = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                out[key] = value[1:-1]
            else:
                # YAML null sentinels, and a value that is nothing but a
                # comment, all mean "no value" to Hugo. Normalising them to ""
                # here is what makes the blank-counts-as-missing rule below
                # actually bite. Ralph round 16 proved the gap end to end:
                # `description: null` passed the gate ("Frontmatter OK (79
                # posts)", exit 0) while the built page served
                # site.Params.description verbatim - the exact near-duplicate
                # this gate exists to prevent. `~` and `# TODO write this`
                # behave identically. Deliberately confined to the UNQUOTED
                # branch: a quoted `description: "# hashtags"` is a real value
                # and must keep passing.
                # This comment used to claim a trailing comment was "a cosmetic
                # divergence, not a bypass - the value is non-empty either way".
                # That was TRUE for `description: Text # note` and FALSE for a
                # sentinel: `description: ~ # TODO` is null in YAML but was kept
                # whole here, so it counted as present and the page shipped the
                # site default. Ralph round 21 blocker. Trailing comments are
                # now stripped in strip_trailing_comment() above, before this
                # test runs, so the sentinel list below sees the real value.
                if value in ("null", "Null", "NULL", "~") or value.startswith("#"):
                    out[key] = ""
                # A block header is the indicator, then an optional indentation
                # digit (1-9) and an optional chomping sign, in EITHER order.
                # The first version of this regex only allowed sign-then-digit,
                # so `|2-` fell through and was stored as the literal "|2-",
                # which is non-empty: an empty block scalar written that way
                # passed the gate while Hugo served the site default
                # (Ralph round 18).
                elif re.fullmatch(r"[>|](?:[1-9][-+]?|[-+]?[1-9]?)", value):
                    # Block scalar. Provisionally empty; the continuation lines
                    # collected above replace this when the block closes.
                    out[key] = ""
                    block_key, block_lines, block_indent = key, [], None
                    current_key = key
                    continue
                else:
                    out[key] = value
            current_key = key
    close_block()
    return out


def check_tree(root: Path, required: set[str], check_categories: bool,
               include_section_pages: bool = False) -> tuple[list[str], int]:
    """Validate every page bundle under `root` against `required`.

    Returns (failures, files_checked). A missing root is not an error - the
    tree is simply empty, which is how a fresh clone or a partial checkout
    behaves.

    Walks EVERY natively-rendered content file (CONTENT_EXTS), not just
    `index.md`. A filename-specific walk skips flat single pages such as
    `content/consulting/thing.md`, and a skipped page passes by omission
    rather than by compliance, which is a false PASS.

    `include_section_pages` controls whether `_index.*` branch bundles are
    validated. Consulting section pages are real indexable URLs, so they are
    gated; the posts section index is Hugo-generated with no source
    frontmatter to validate.
    """
    failures: list[str] = []
    if not root.exists():
        return failures, 0

    md_files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in CONTENT_EXTS
        and (include_section_pages or not p.name.startswith("_index."))
    )

    for md in md_files:
        text = md.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm is None:
            failures.append(f"{md.relative_to(ROOT)}: no frontmatter")
            continue
        # A key present with a BLANK value is treated as missing. Hugo's
        # `.Description | default site.Params.description` sees "" as falsy and
        # serves the site default, so `description:` with nothing after it
        # produces exactly the near-duplicate this gate exists to prevent while
        # satisfying a naive key-presence check. Same reasoning for an empty
        # title or an empty categories list.
        present = {k for k, v in fm.items() if str(v).strip() and v != []}
        missing = required - present
        if missing:
            failures.append(f"{md.relative_to(ROOT)}: missing {sorted(missing)}")
            continue
        if check_categories:
            cats = fm.get("categories")
            if isinstance(cats, list):
                unknown = set(c.lower() for c in cats) - ALLOWED_CATEGORIES
                if unknown:
                    failures.append(
                        f"{md.relative_to(ROOT)}: unknown categories {sorted(unknown)} "
                        f"(allowed: {sorted(ALLOWED_CATEGORIES)})"
                    )
    return failures, len(md_files)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--scope",
        choices=("all", "posts", "consulting"),
        default="all",
        help="which tree to validate (default: all)",
    )
    args = ap.parse_args(argv)

    failures: list[str] = []
    counts: list[str] = []

    # A walk that finds NOTHING is a broken walk, not a clean tree. Both of
    # these trees are non-empty in any real checkout, so a zero count means the
    # root was renamed, mistyped, or CONTENT_EXTS stopped matching - and every
    # page it should have gated then passes by omission. Ralph round 16 proved
    # this was undefended: pointing POSTS at a nonexistent path printed
    # "Frontmatter OK (0 posts)" and exited 0, sailing through pre-commit,
    # pre-publish gates 4/4a, both ci.yml steps and all four wiring tests.
    # check_tree itself stays tolerant of a missing root (it is used as a
    # library and a partial checkout is legitimately empty); the "must not be
    # empty" judgement belongs here, where the specific trees are known.
    if args.scope in ("all", "posts"):
        f, n = check_tree(POSTS, REQUIRED, check_categories=True)
        failures += f
        counts.append(f"{n} posts")
        if n == 0:
            failures.append(
                f"walked 0 files under {POSTS} - the posts tree is never empty, "
                "so the root or the extension filter is broken (vacuous pass)"
            )

    if args.scope in ("all", "consulting"):
        f, n = check_tree(CONSULTING, CONSULTING_REQUIRED, check_categories=False,
                          include_section_pages=True)
        failures += f
        counts.append(f"{n} project pages")
        if n == 0:
            failures.append(
                f"walked 0 files under {CONSULTING} - the consulting tree is never "
                "empty, so the root or the extension filter is broken (vacuous pass)"
            )

    if failures:
        print("FRONTMATTER VALIDATION FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"Frontmatter OK ({', '.join(counts)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
