#!/usr/bin/env python3
"""The 6 section-keyed sites still work after the URL move (blog-priv#62 AC 5.13).

Six places in the templates key off `.Section` or a section NAME rather than a
URL. The config-only route was believed to break none of them, and "believed" is
not verified. `.Section` stays `posts`/`tech-ai` while [permalinks] rewrites only
the served URL, so the expectation is that all six are untouched: this test is
what turns that expectation into an assertion.

  1. layouts/_default/list.html:8,10   every category landing still lists its posts
  2. layouts/_partials/related-posts.html  a post still renders its Read Next block
  3. layouts/_partials/head.html:40        a post still emits its hero og:image
  4. layouts/_partials/head.html:80        a post still emits JSON-LD Article
  5. config/_default/params.toml           textFirstSections still fires per section
  6. the retired paths are NOT also built  (no duplicate serving the old URL)

Thresholds are floors taken from the pre-move build, not exact counts, so adding a
post does not fail the suite. A floor of zero would be vacuous, which is why each
one is a real number.

Usage:  python3 scripts/test_section_keyed_regression.py [--built public]
Exit 0 = no regression. Exit 1 = a named failure.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARAMS = ROOT / "config" / "_default" / "params.toml"

# Floors measured on the pre-move build (2026-07-25): tech-ai 41 posts,
# entrepreneurship 8. Set below the real figures so the gate survives normal
# publishing but still catches a landing that empties out.
LISTING_FLOORS = {"tech-ai": 30, "entrepreneurship": 5}
ALL_CATEGORIES = ("tech-ai", "entrepreneurship", "trading", "food-booze",
                  "adventure", "dance", "life")
SAMPLE_POST = "why-scope-beats-code"
RETIRED_PATHS = (*ALL_CATEGORIES, "categories")


def _post_links(html: str) -> set[str]:
    """Post permalinks inside the main region (not the sidebar's category links)."""
    m = re.search(r'<main class="main">(.*?)</main>', html, re.S)
    region = m.group(1) if m else html
    cats = {f"/blogs/{c}/" for c in ALL_CATEGORIES}
    return {h for h in re.findall(r'href="(/blogs/[^"/]+/)"', region)
            if h not in cats and h != "/blogs/"}


def check_listings(built: Path, failures: list[str]) -> None:
    for cat in ALL_CATEGORIES:
        page = built / "blogs" / cat / "index.html"
        if not page.is_file():
            failures.append(f"AC 5.13: no category landing at {page}")
            continue
        html = page.read_text(encoding="utf-8")
        if "No posts yet" in html:
            failures.append(f"AC 5.13: /blogs/{cat}/ renders the empty state, so the "
                            f"`Params.categories intersect .Section` cross-filter in "
                            f"list.html no longer matches after the move")
        n = len(_post_links(html))
        floor = LISTING_FLOORS.get(cat, 1)
        if n < floor:
            failures.append(f"AC 5.13: /blogs/{cat}/ lists {n} posts, expected >= {floor}")


def check_post_furniture(built: Path, failures: list[str]) -> None:
    page = built / "blogs" / SAMPLE_POST / "index.html"
    if not page.is_file():
        failures.append(f"AC 5.13: no rendered post at {page}")
        return
    html = page.read_text(encoding="utf-8")

    if 'class="read-next"' not in html:
        failures.append("AC 5.13: the post renders no Read Next block "
                        "(related-posts.html keys on Section + Params.categories)")
    elif not re.search(r'<ul class="read-next-list">.*?<a href=', html, re.S):
        failures.append("AC 5.13: the Read Next block is present but empty")

    og = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    if not og:
        failures.append("AC 5.13: the post emits no og:image (head.html hero-pick)")
    elif any(marker in og.group(1) for marker in ("default-card", "hoi-mug")):
        failures.append(f"AC 5.13: the post's og:image fell back to the site default "
                        f"({og.group(1)}), so hero-pick stopped resolving its hero")

    if '"@type":"Article"' not in html and '"@type": "Article"' not in html:
        failures.append("AC 5.13: the post emits no JSON-LD Article (head.html)")


def check_text_first(built: Path, failures: list[str]) -> None:
    """params.toml textFirstSections selects a different listing partial per section,
    so each configured section must still render the text-first list, not cards."""
    cfg = tomllib.loads(PARAMS.read_text(encoding="utf-8"))
    sections = cfg.get("textFirstSections") or cfg.get("params", {}).get("textFirstSections")
    if not sections:
        failures.append("AC 5.13: params.toml declares no textFirstSections, so this "
                        "check would pass vacuously")
        return
    for section in sections:
        page = built / "blogs" / section / "index.html"
        if not page.is_file():
            failures.append(f"AC 5.13: textFirstSections names '{section}' but there is "
                            f"no landing at {page}")
            continue
        html = page.read_text(encoding="utf-8")
        if "post-list" not in html:
            failures.append(f"AC 5.13: /blogs/{section}/ is in textFirstSections but "
                            f"does not render the text-first list partial, so the "
                            f"per-section layout switch stopped firing")


def check_retired_not_built(built: Path, failures: list[str]) -> None:
    for path in RETIRED_PATHS:
        if (built / path).exists():
            failures.append(f"AC 5.13: public/{path}/ is still built. A retired URL must "
                            f"be served by its 301 only, or two pages answer the same "
                            f"content and the canonical is ambiguous.")


def main(argv: list[str] | None = None) -> int:
    """`argv=None` reads sys.argv, which under pytest is the pytest command line
    (file paths + flags), so argparse exits 2 before a single assertion runs. CI
    invokes these through pytest, so the entry point below passes an explicit []
    and this signature is what makes that possible."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--built", default="public", help="built site root (default: public)")
    args = ap.parse_args(argv)
    built = Path(args.built)
    if not built.is_absolute():
        built = ROOT / built

    failures: list[str] = []
    if not built.is_dir():
        print(f"FAIL: built site not found at {built} (run `hugo` first)", file=sys.stderr)
        return 1

    check_listings(built, failures)
    check_post_furniture(built, failures)
    check_text_first(built, failures)
    check_retired_not_built(built, failures)

    if failures:
        print(f"FAIL: {len(failures)} section-keyed regression(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("OK: all 7 landings still list their posts, a post still renders Read Next + "
          "hero og:image + JSON-LD Article, textFirstSections still fires, and no "
          "retired path is built alongside its 301")
    return 0


def test_section_keyed_regression() -> None:
    """pytest entry point (CI runs pytest through explicit file lists)."""
    assert main([]) == 0


if __name__ == "__main__":
    sys.exit(main())
