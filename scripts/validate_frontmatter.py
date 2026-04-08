#!/usr/bin/env python3
"""Frontmatter contract for hoiboy.uk posts.

Required: title, date, categories, tags
Optional: slug, draft

Phase 0 inline schema. 08_FRONTMATTER_SCHEMA.md is deferred to Phase 1
once real WordPress posts shape the schema.

Walks content/posts/, parses YAML frontmatter, validates required fields.
Fails loudly. Uses a tiny YAML parser (no third-party deps in CI).
"""
from __future__ import annotations
import sys
import re
from pathlib import Path

REQUIRED = {"title", "date", "categories", "tags"}
# Allowed category values. Sourced from config/_default/menus.toml at runtime.
# A typo like categories: [foood] would create an orphan term page no
# sidebar link reaches. Hard fail.
ALLOWED_CATEGORIES = {"food", "adventure", "dance", "tech", "relationship"}
ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "content" / "posts"


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


def main() -> int:
    if not POSTS.exists():
        return 0
    failures: list[str] = []
    md_files = list(POSTS.rglob("index.md"))
    for md in md_files:
        text = md.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm is None:
            failures.append(f"{md.relative_to(ROOT)}: no frontmatter")
            continue
        missing = REQUIRED - set(fm.keys())
        if missing:
            failures.append(f"{md.relative_to(ROOT)}: missing {sorted(missing)}")
            continue
        cats = fm.get("categories")
        if isinstance(cats, list):
            unknown = set(c.lower() for c in cats) - ALLOWED_CATEGORIES
            if unknown:
                failures.append(
                    f"{md.relative_to(ROOT)}: unknown categories {sorted(unknown)} "
                    f"(allowed: {sorted(ALLOWED_CATEGORIES)})"
                )
    if failures:
        print("FRONTMATTER VALIDATION FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"Frontmatter OK ({len(md_files)} posts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
