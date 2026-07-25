#!/usr/bin/env python3
"""The /blogs/ hub is a real page listing the 7 categories (blog-priv#62 Phase 4).

Before this issue the section index rendered `<h1>Posts</h1>` and
`No posts yet.` with zero post links: `layouts/_default/list.html` cross-filters
`site.RegularPages` on `Params.categories intersect (slice .Section)`, and no post
declares `categories: [posts]`, so the hub matched nothing by construction.

  AC 4.1 - the SOURCE exists with the approved title and description.
  AC 4.2 - the BUILT page lists exactly the 7 categories, in the operator's
           stated order, each with descriptive text rather than a bare link.
  AC 4.3 - its <h1> and its own breadcrumb crumb read `Blogs`, not `Posts`.
  AC 4.4 - it owns a social card instead of falling back to the site default.

**Every assertion is scoped to the `<main class="main">` region.** Once the
category menu points at /blogs/<cat>/, the SIDEBAR emits all 7 of those links on
EVERY page of the site, so a document-wide link count passes on a hub still
rendering "No posts yet". Scoping is what makes this test discriminate.

Usage:  python3 scripts/test_hub_listing.py [--built public]
Exit 0 = the hub is real. Exit 1 = a named failure.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "content" / "posts" / "_index.md"

# The operator's stated order and display titles (A15, 2026-07-25), which are also
# the existing menus.toml order and the existing content/<cat>/_index.md titles.
CATEGORIES = [
    ("tech-ai", "Tech & AI"),
    ("entrepreneurship", "Entrepreneurship"),
    ("trading", "Trading"),
    ("food-booze", "Food & Booze"),
    ("adventure", "Adventure"),
    ("dance", "Dance"),
    ("life", "Life"),
]
MIN_BLURB_CHARS = 40

_MAIN_RE = re.compile(r'<main class="main">(.*?)</main>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    """Visible text of an HTML fragment, entities resolved."""
    return html.unescape(_TAG_RE.sub("", fragment)).strip()


def main_region(page: Path) -> str:
    doc = page.read_text(encoding="utf-8")     # not `html`: that shadows the module
    m = _MAIN_RE.search(doc)
    if not m:
        sys.exit(f"AC 4.2: no <main class=\"main\"> region in {page}; the assertions "
                 f"below would silently widen to the whole document (sidebar included)")
    return m.group(1)


def check_source(failures: list[str]) -> None:
    """AC 4.1 - the hand-written landing, not a Hugo-generated section index."""
    if not SOURCE.is_file():
        failures.append(f"AC 4.1: {SOURCE.relative_to(ROOT)} does not exist")
        return
    text = SOURCE.read_text(encoding="utf-8")
    if not re.search(r'^title:\s*"?Blogs"?\s*$', text, re.M):
        failures.append("AC 4.1: content/posts/_index.md has no `title: Blogs`")
    desc = re.search(r"^description:\s*(.+?)\s*$", text, re.M)
    if not desc:
        failures.append("AC 4.1: content/posts/_index.md has no `description:`, so the "
                        "hub inherits the site-default meta description and its landing "
                        "card is title-only")
    elif len(desc.group(1).strip().strip("\"'")) < MIN_BLURB_CHARS:
        failures.append(f"AC 4.1: the hub description is under {MIN_BLURB_CHARS} chars")
    headings = re.findall(r"^## (.+)$", text, re.M)
    if len(headings) != len(CATEGORIES):
        failures.append(f"AC 4.1: content/posts/_index.md has {len(headings)} `## ` "
                        f"headings, expected {len(CATEGORIES)} (one per category)")


def check_listing(region: str, failures: list[str]) -> None:
    """AC 4.2 - 7 categories, in order, each a heading + prose + link."""
    if "No posts yet" in region:
        failures.append("AC 4.2: the hub still renders the `No posts yet.` empty state")

    positions: list[int] = []
    for slug, title in CATEGORIES:
        href = f'<a href="/blogs/{slug}/">'
        link_at = region.find(href)
        if link_at < 0:
            failures.append(f"AC 4.2: no link to /blogs/{slug}/ inside <main>")
            continue
        head_m = None
        for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", region, re.S):
            if m.start() < link_at and _text(m.group(1)) == title:
                head_m = m
        if head_m is None:
            titles = [_text(m)
                      for m in re.findall(r"<h2[^>]*>(.*?)</h2>", region, re.S)]
            failures.append(f"AC 4.2: no <h2> reading {title!r} before the /blogs/{slug}/ "
                            f"link; headings found: {titles}")
            continue
        positions.append(head_m.start())
        # Descriptive text between the heading and its link, not a bare list.
        between = region[head_m.end():link_at]
        prose = max((_text(p) for p in re.findall(r"<p>(.*?)</p>", between, re.S)),
                    key=len, default="")
        if len(prose) < MIN_BLURB_CHARS:
            failures.append(
                f"AC 4.2: {title} has {len(prose)} chars of description before its link "
                f"(need >= {MIN_BLURB_CHARS}). A bare link list is not what the hub is for."
            )

    if len(positions) == len(CATEGORIES) and positions != sorted(positions):
        order = [t for _, t in CATEGORIES]
        failures.append(f"AC 4.2: the categories are not in the operator's stated "
                        f"order {order}")

    # No individual post is listed here: the hub lists CATEGORIES (A15).
    cat_hrefs = {f"/blogs/{s}/" for s, _ in CATEGORIES}
    posts = sorted({h for h in re.findall(r'<a href="(/blogs/[^"/]+/)"', region)
                    if h not in cat_hrefs and h != "/blogs/"})
    if posts:
        failures.append(f"AC 4.2: {len(posts)} post permalink(s) listed on the hub, which "
                        f"lists the 7 categories, not the 79 posts: {posts[:3]}")


def check_headings_and_card(page: Path, region: str, failures: list[str]) -> None:
    """AC 4.3 (h1 + crumb) and AC 4.4 (own card)."""
    if "<h1>Posts</h1>" in region:
        failures.append("AC 4.3: the hub still renders <h1>Posts</h1>")
    if "<h1>Blogs</h1>" not in region:
        failures.append("AC 4.3: the hub does not render <h1>Blogs</h1>")
    nav = re.search(r'<nav class="breadcrumbs".*?</nav>', region, re.S)
    if not nav:
        failures.append("AC 4.3: the hub renders no breadcrumb nav")
    elif "Posts" in _text(nav.group(0)):
        failures.append("AC 4.3: the hub's own breadcrumb crumb still reads `Posts`")

    og = re.search(r'<meta property="og:image" content="([^"]+)"',
                   page.read_text(encoding="utf-8"))
    if not og:
        failures.append("AC 4.4: the hub emits no og:image at all")
    elif any(marker in og.group(1) for marker in ("default-card", "hoi-mug")):
        failures.append(
            f"AC 4.4: the hub falls back to the site default card ({og.group(1)}). "
            f"Add `posts` to scripts/social-cards/landing-cards.tsv and run "
            f"scripts/gen-social-cards.sh."
        )


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
    check_source(failures)
    page = built / "blogs" / "index.html"
    if not page.is_file():
        failures.append(f"AC 4.2: no rendered hub at {page} (run `hugo` first)")
    else:
        region = main_region(page)
        check_listing(region, failures)
        check_headings_and_card(page, region, failures)

    if failures:
        print(f"FAIL: {len(failures)} hub violation(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("OK: /blogs/ lists the 7 categories in the stated order inside <main>, each "
          "with a heading, prose and a link; titled Blogs; and owns its social card")
    return 0


def test_hub_listing() -> None:
    """pytest entry point (CI runs pytest through explicit file lists)."""
    assert main([]) == 0


if __name__ == "__main__":
    sys.exit(main())
