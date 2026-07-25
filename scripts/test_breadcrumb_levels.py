#!/usr/bin/env python3
"""The Blogs breadcrumb level (blog-priv#62 AC 1.1 + AC 1.2).

AC 1.1  A `Blogs` crumb links to the Blogs hub on every post and on every one of
        the category landings, AND ON NO OTHER PAGE. Both halves are asserted:
        the expected set is computed, then the whole built tree is swept and the
        two sets must be equal, so a crumb leaking onto an unrelated page fails
        here rather than at operator review.

AC 1.2  That crumb reads exactly `Blogs`. Title case, not `BLOGS`. The operator
        typed the target in caps once and then corrected it ("breadcrumb isn't
        FULL CAPS"), so this is pinned case-sensitively and an all-caps crumb is
        reported as its own failure rather than as a generic miss.

SCOPING IS LOAD-BEARING. Every assertion here reads the `<nav class="breadcrumbs">`
region only. layouts/_partials/sidebar.html renders `>Blogs</a>` into the sidebar
of EVERY page, so a document-wide grep returns a hit on the negative controls too
and inverts the test.

Page sets come from the built tree and from config, never from a hardcoded URL
list, so this survives the Phase-5 permalink move unchanged:
  - posts            = every trail.json whose content path is under posts/;
  - category landings = the `categories` menu in config/_default/menus.toml;
  - hub              = the trail.json for posts/_index.md.

Usage:  python3 scripts/test_breadcrumb_levels.py [--built public]
Run it against a FULL build of the FINAL tree: the crumb text is the hub page's
own title, so it reads `Posts` until Phase 4 lands content/posts/_index.md, and
the built paths do not exist under public/blogs/ until Phase 5.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
MENUS = ROOT / "config" / "_default" / "menus.toml"

CRUMB_TEXT = "Blogs"
HUB_CONTENT_PATH = "posts/_index.md"

# AC 1.1 names these three as the pages that must NOT carry the crumb. They are
# checked by name as well as by the whole-tree sweep so a failure is legible.
NAMED_CONTROLS = ("/hire-hoi/ai-consultancy/", "/legal/", "/")

_spec = importlib.util.spec_from_file_location("test_trail_manifest", SCRIPTS / "test_trail_manifest.py")
_tm = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _tm
_spec.loader.exec_module(_tm)


def category_landing_urls() -> list[str]:
    """Served URLs of the blog category landings, from the `categories` menu.

    menus.toml is the single enumeration of that set; the breadcrumb partial
    reads the same menu. Phase 5 rewrites these URLs to /blogs/<cat>/ and the
    section permalinks with them, so the two stay in step by construction.
    """
    menus = tomllib.loads(MENUS.read_text(encoding="utf-8"))
    urls = [entry["url"] for entry in menus.get("categories", [])]
    if not urls:
        sys.exit(f"FAIL: no [[categories]] entries in {MENUS}")
    return urls


def crumb_pages(built: Path) -> dict[str, list[str]]:
    """Every built page -> its breadcrumb trail crumbs (Home and own title dropped)."""
    out: dict[str, list[str]] = {}
    for f in built.rglob("index.html"):
        url = "/" + f.relative_to(built).parent.as_posix().strip(".").lstrip("/")
        url = "/" if url in ("/", "//") else url.rstrip("/") + "/"
        crumbs = _tm.nav_crumbs(f)
        if crumbs is not None:
            out[url] = crumbs
    return out


def main(argv: list[str] | None = None) -> int:
    """`argv=None` reads sys.argv, which under pytest is the pytest command line
    (file paths + flags), so argparse exits 2 before a single assertion runs. CI
    invokes these through pytest, so the entry point below passes an explicit []
    and this signature is what makes that possible."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--built", default="public", help="built site root (default: public)")
    args = ap.parse_args(argv)

    built = (ROOT / args.built) if not Path(args.built).is_absolute() else Path(args.built)
    if not built.is_dir():
        print(f"FAIL: built site not found at {built} (run `hugo` first)", file=sys.stderr)
        return 1

    trails = _tm.load_trails(built)
    failures: list[str] = []

    # --- where the hub actually lives (never hardcoded) ----------------------
    hub = trails.get(HUB_CONTENT_PATH)
    if hub is None:
        print(
            f"FAIL: no trail.json for {HUB_CONTENT_PATH}. The Blogs hub landing does not "
            "exist in this build, so the crumb cannot resolve. Land Phase 4 "
            "(content/posts/_index.md) before running this against the final tree.",
            file=sys.stderr,
        )
        return 1
    hub_url = hub["url"]
    if not (built / hub_url.strip("/") / "index.html").exists():
        failures.append(f"hub URL {hub_url} has no built page")

    # --- the expected set ----------------------------------------------------
    expected = {rec["url"] for path, rec in trails.items() if path.startswith("posts/") and path != HUB_CONTENT_PATH}
    n_posts = len(expected)
    cat_urls = category_landing_urls()
    expected |= set(cat_urls)

    pages = crumb_pages(built)
    for url in sorted(expected):
        if url not in pages:
            failures.append(f"expected blog page {url} has no rendered breadcrumb nav")

    # --- AC 1.1: exactly these pages carry the crumb -------------------------
    actual = {url for url, crumbs in pages.items() if CRUMB_TEXT in crumbs}
    for url in sorted(expected - actual):
        got = pages.get(url)
        failures.append(f"{url} is missing the {CRUMB_TEXT!r} crumb (its trail reads {got!r})")
    for url in sorted(actual - expected):
        failures.append(f"{url} carries a {CRUMB_TEXT!r} crumb but is not a post or a category landing")

    # --- AC 1.2: title case, never all-caps ----------------------------------
    for url, crumbs in sorted(pages.items()):
        for c in crumbs:
            if c != CRUMB_TEXT and c.casefold() == CRUMB_TEXT.casefold():
                failures.append(f"{url} renders the crumb as {c!r}; AC 1.2 pins it to {CRUMB_TEXT!r}")

    # --- the crumb points at the hub -----------------------------------------
    for url in sorted(expected & actual):
        page = built / url.strip("/") / "index.html"
        if f'href="{hub_url}">{CRUMB_TEXT}<' not in _tm.NAV_RE.search(page.read_text(encoding="utf-8", errors="replace")).group(0):
            failures.append(f"{url}: the {CRUMB_TEXT!r} crumb does not link to the hub at {hub_url}")

    # --- named negative controls (AC 1.1) ------------------------------------
    for url in NAMED_CONTROLS:
        if url == "/":
            if url in pages:
                failures.append("home renders a breadcrumb nav; it is meant to have none")
            continue
        if url not in pages:
            failures.append(f"negative control {url} has no rendered breadcrumb nav")
        elif CRUMB_TEXT in pages[url]:
            failures.append(f"negative control {url} carries the {CRUMB_TEXT!r} crumb")

    if failures:
        print(f"FAIL: {len(failures)} breadcrumb-level violation(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"OK: {CRUMB_TEXT!r} crumb -> {hub_url} on {n_posts} posts + {len(cat_urls)} category landings, and on no other page ({len(pages)} navs swept)")
    return 0


def test_breadcrumb_levels() -> None:
    """pytest entry point (CI runs pytest through explicit file lists)."""
    assert main([]) == 0


if __name__ == "__main__":
    sys.exit(main())
