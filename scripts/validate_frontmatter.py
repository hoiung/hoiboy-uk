#!/usr/bin/env python3
"""Frontmatter contract for hoiboy.uk posts.

Required: title, date, categories, tags
Optional: slug, draft

Phase 0 inline schema. 08_FRONTMATTER_SCHEMA.md is deferred to Phase 1
once real WordPress posts shape the schema.

Walks content/posts/, validates required fields. Fails loudly.
"""
from __future__ import annotations
import sys
from pathlib import Path

REQUIRED = {"title", "date", "categories", "tags"}
ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "content" / "posts"


def parse_frontmatter(text: str) -> dict[str, str] | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    body = text[3:end].strip()
    out: dict[str, str] = {}
    for line in body.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


def main() -> int:
    if not POSTS.exists():
        return 0
    failures: list[str] = []
    for md in POSTS.rglob("index.md"):
        text = md.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm is None:
            failures.append(f"{md.relative_to(ROOT)}: no frontmatter")
            continue
        missing = REQUIRED - set(fm.keys())
        if missing:
            failures.append(f"{md.relative_to(ROOT)}: missing {sorted(missing)}")
    if failures:
        print("FRONTMATTER VALIDATION FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"Frontmatter OK ({len(list(POSTS.rglob('index.md')))} posts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
