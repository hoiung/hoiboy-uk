#!/usr/bin/env python3
"""Assert the footer subscribe form renders on exactly the right pages.

Reads the BUILT tree, not the template source. The suppression predicate lives in
``layouts/_partials/footer.html`` and reaches every page kind through the single
shared shell at ``layouts/baseof.html``, so a wrong predicate ships site-wide and
source-level greps cannot prove placement. Only a rendered tree can.

Four assertions, the first three in increasing strength:

1. SUPPRESSED: the marker is absent from every page in the five suppressed classes.
2. PRESENT: the marker is present on a named sample that deliberately includes the
   two pages a ``.Section``-only predicate gets wrong. ``/community/`` and
   ``/community/agit-featured/`` both report ``.Section == "community"``, the same
   value the two suppressed AGIT pages report, so a section-only predicate either
   kills the form on all four or suppresses none of them. Omitting these two from
   the present set is what would let that defect pass its own gate.
3. WHOLE-TREE: every built page that rendered through ``baseof`` carries the marker
   unless its path is declared suppressed above. This is the assertion that catches
   drift, because it needs no sample list: a page that stops rendering the form, or
   a newly added section that wrongly suppresses it, fails here even though nobody
   remembered to add it to PRESENT_PATHS.
4. LINK TARGETS: every internal link the rendered form emits resolves to a file that
   actually exists under the built tree. Nothing else in this repo checks a link
   emitted from a TEMPLATE: ``validate_internal_links.py`` walks ``content/**/*.md``
   only, and lychee globs ``.md``, so the 29 ``<a href>`` targets across ``layouts/``
   are validated by no gate at all. Two of them are in ``footer.html`` itself, and
   one of those points at ``/legal/privacy/`` -- the same target the consent label
   links to. This script already parses built HTML, so it is the cheapest correct
   home for the assertion (#56 AC 4.6c).

"Rendered through baseof" is detected by the presence of the ``<footer`` element,
which baseof emits unconditionally. Measured on the pinned Hugo 0.160.0, the built
tree's non-baseof HTML is exactly two alias stubs (``<meta http-equiv="refresh">``)
and four standalone page-bundle assets (chart exports, a social-card preview). None
of those is a page a reader navigates to, and none carries a footer, so excluding
them is a structural fact rather than an allowlist that needs maintaining.

Usage: ``python3 scripts/check_subscribe_placement.py --built public``
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Pinned once in AC 2.2 and quoted by every other surface: the outer element in
# layouts/_partials/subscribe-form.html, the CSS selector in assets/css/main.css,
# and this grep. Changing it here alone silently disarms the gate.
MARKER = "subscribe-form"

# baseof.html emits this on every page it renders. Its absence means the file is an
# alias stub or a standalone bundle asset, not a page with a footer to guard.
BASEOF_MARKER = "<footer"

# The six suppressed classes, as BUILT paths.
#   /legal/*   operator instruction
#   /private/* the per-path CSP at static/_headers:10 is narrower than the root
#              policy and would break the Turnstile widget, so the form is removed
#              rather than worked around
#   404        a form posting from a URL that does not exist
#   the AGIT signup and thanks pages, which already carry an email-capture form
#   /newsletter/* the form's own confirmation pages: offering the form to someone
#              just told they are subscribed is the one placement that reads as
#              broken. Added in Phase 3, when those pages first existed.
SUPPRESSED_PREFIXES = (
    "legal/",
    "private/",
    "community/asians-gingers-in-tech/",
    "newsletter/",
)
SUPPRESSED_EXACT = ("404.html",)

# Hugo emits the 404 at public/404.html, NOT public/404/index.html.
PRESENT_PATHS = (
    "index.html",                              # home: .Section is "", same as 404
    "community/index.html",                    # .Section "community", must SHOW
    "community/agit-featured/index.html",      # .Section "community", must SHOW
    "blogs/tech-ai/index.html",                # a /blogs/<category>/ section landing
    "skills/index.html",                       # top-level section named in scope
    "hire-hoi/ai-consultancy/index.html",
    "series/bakeoff/index.html",               # a taxonomy term page
)

# Category landings live alongside posts under /blogs/. The sample post below is
# picked by excluding them. The classification only affects WHICH page is sampled,
# never the verdict: both classes must carry the marker, so a mis-pick still
# asserts the right thing.
CATEGORY_LANDINGS = frozenset(
    (
        "adventure",
        "dance",
        "entrepreneurship",
        "food-booze",
        "foundation",
        "life",
        "tech-ai",
        "trading",
    )
)


# The rendered form runs from its marker to the closing form tag. Bounding the
# scan this way keeps assertion (4) about THIS form: the footer sitting beside it
# carries its own links, and crediting or blaming those here would make the check
# report on markup the form does not own.
FORM_END = "</form>"

HREF_RE = re.compile(r'href="([^"]+)"')


def is_suppressed(rel: str) -> bool:
    return rel in SUPPRESSED_EXACT or rel.startswith(SUPPRESSED_PREFIXES)


def form_block(text: str) -> str | None:
    """The rendered subscribe form, marker to closing tag, or None if absent."""
    start = text.find(MARKER)
    if start == -1:
        return None
    end = text.find(FORM_END, start)
    return None if end == -1 else text[start:end]


def served_file(built: Path, href: str) -> Path:
    """The file Cloudflare Pages serves for an internal href.

    Pretty URLs are directories with an ``index.html`` inside, which is what Hugo
    emits and what the host resolves. A href carrying a real file extension is
    taken at face value; anything else is treated as a pretty URL, because that is
    what every internal link in this repo is.
    """
    rel = href.split("#", 1)[0].split("?", 1)[0].lstrip("/")
    if rel == "" or rel.endswith("/"):
        return built / rel / "index.html"
    candidate = built / rel
    return candidate if candidate.suffix else built / rel / "index.html"


def pick_sample_post(built: Path) -> str | None:
    """First post under /blogs/, deterministically, excluding category landings."""
    for path in sorted(built.glob("blogs/*/index.html")):
        if path.parent.name not in CATEGORY_LANDINGS:
            return str(path.relative_to(built))
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--built",
        default="public",
        help="path to the built Hugo tree (default: public)",
    )
    args = parser.parse_args()

    built = Path(args.built)
    if not built.is_dir():
        print(
            f"ERR: built tree not found at {built}/. "
            "Run 'hugo --gc --minify -e production' first.",
            file=sys.stderr,
        )
        return 2

    pages = sorted(built.rglob("*.html"))
    if not pages:
        print(f"ERR: no HTML files under {built}/ - the build produced nothing.", file=sys.stderr)
        return 2

    failures: list[str] = []

    # (1) SUPPRESSED. Enumerated from the tree rather than hardcoded, so a new legal
    #     page or a new /private/ tool is covered the day it is added.
    suppressed_seen = 0
    for path in pages:
        rel = str(path.relative_to(built))
        if not is_suppressed(rel):
            continue
        suppressed_seen += 1
        if MARKER in path.read_text(encoding="utf-8", errors="replace"):
            failures.append(f"[suppressed-but-present] {rel} carries '{MARKER}' and must not")
    if suppressed_seen == 0:
        failures.append(
            "[no-suppressed-pages-found] the suppressed set matched nothing, so this "
            "gate proved nothing. Check SUPPRESSED_PREFIXES against the built tree."
        )

    # (2) PRESENT, including the sampled post.
    present_paths = list(PRESENT_PATHS)
    sample_post = pick_sample_post(built)
    if sample_post is None:
        failures.append("[no-post-found] no post under blogs/ to sample; cannot prove posts render the form")
    else:
        present_paths.append(sample_post)

    for rel in present_paths:
        path = built / rel
        if not path.is_file():
            failures.append(f"[present-page-missing] {rel} does not exist in {built}/")
            continue
        if MARKER not in path.read_text(encoding="utf-8", errors="replace"):
            failures.append(f"[present-but-absent] {rel} must carry '{MARKER}' and does not")

    # (4) LINK TARGETS. Run over the named PRESENT set rather than the whole tree:
    #     one partial renders on every page, so 340 identical scans would buy
    #     nothing over these.
    links_checked = 0
    for rel in present_paths:
        path = built / rel
        if not path.is_file():
            continue  # already reported by (2)
        block = form_block(path.read_text(encoding="utf-8", errors="replace"))
        if block is None:
            continue  # already reported by (2)
        for href in HREF_RE.findall(block):
            if not href.startswith("/"):
                continue  # external or in-page; lychee owns those
            links_checked += 1
            target = served_file(built, href)
            if not target.exists():
                failures.append(
                    f"[dead-form-link] {rel} renders a form link to {href} but "
                    f"{target.relative_to(built)} does not exist under {built}/"
                )
    # A block that stopped matching, or a form that lost its link, would make the
    # loop above iterate zero times and pass. That is the same silent-pass shape
    # assertion (1) guards against, so say so rather than report a clean run.
    if links_checked == 0:
        failures.append(
            "[no-form-links-checked] the rendered form emitted no internal link, so "
            "this gate proved nothing. Either the consent label lost its Privacy "
            "Notice link, or the form block no longer parses."
        )

    # (3) WHOLE-TREE. The assertion that survives someone forgetting to update (2).
    for path in pages:
        rel = str(path.relative_to(built))
        if is_suppressed(rel):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if BASEOF_MARKER not in text:
            continue  # alias stub or standalone bundle asset, has no footer to guard
        if MARKER not in text:
            failures.append(
                f"[unexpected-suppression] {rel} rendered a footer but no '{MARKER}'. "
                "Either the predicate over-suppresses, or this path belongs in "
                "SUPPRESSED_PREFIXES with a stated reason."
            )

    if failures:
        print(f"[FAIL] subscribe-form placement, {len(failures)} problem(s):", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        return 1

    guarded = sum(
        1
        for p in pages
        if BASEOF_MARKER in p.read_text(encoding="utf-8", errors="replace")
        and not is_suppressed(str(p.relative_to(built)))
    )
    print(
        f"[OK] subscribe-form placement: {suppressed_seen} suppressed page(s) clean, "
        f"{len(present_paths)} named page(s) carry the marker, "
        f"{guarded} footer-bearing page(s) checked tree-wide."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
