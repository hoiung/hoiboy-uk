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
that it sat in OPTIONAL, so 33 legacy posts rendered with the site-default
meta description, making them near-duplicates that answer engines cannot
tell apart. Phase 1 backfilled all 33; this gate stops the field regressing.

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
OPTIONAL = {"slug", "draft", "series", "order", "hideDate", "type"}
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


def parse_frontmatter(text: str) -> dict[str, object] | None:
    """Minimal YAML frontmatter parser. Handles strings, bracketed lists,
    quoted values with colons inside. Sufficient for blog frontmatter.
    Anything more exotic should switch to PyYAML."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    body = text[3:end].strip()
    out: dict[str, object] = {}
    current_key: str | None = None
    for raw in body.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        # Key: value pattern. Match the FIRST colon that follows an
        # unquoted key (no quotes/brackets in the key portion).
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            key = m.group(1)
            value = m.group(2).strip()
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                items = [s.strip().strip('"').strip("'") for s in inner.split(",") if s.strip()]
                out[key] = items
            elif value.startswith('"') and value.endswith('"'):
                out[key] = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                out[key] = value[1:-1]
            else:
                out[key] = value
            current_key = key
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
        if p.is_file() and p.suffix in CONTENT_EXTS
        and (include_section_pages or not p.name.startswith("_index."))
    )

    for md in md_files:
        text = md.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm is None:
            failures.append(f"{md.relative_to(ROOT)}: no frontmatter")
            continue
        missing = required - set(fm.keys())
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

    if args.scope in ("all", "posts"):
        f, n = check_tree(POSTS, REQUIRED, check_categories=True)
        failures += f
        counts.append(f"{n} posts")

    if args.scope in ("all", "consulting"):
        f, n = check_tree(CONSULTING, CONSULTING_REQUIRED, check_categories=False,
                          include_section_pages=True)
        failures += f
        counts.append(f"{n} project pages")

    if failures:
        print("FRONTMATTER VALIDATION FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"Frontmatter OK ({', '.join(counts)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
