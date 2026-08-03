#!/usr/bin/env python3
"""Assert the footer subscribe form renders on exactly the right pages.

Reads the BUILT tree, not the template source. The suppression predicate lives in
``layouts/_partials/footer.html`` and reaches every page kind through the single
shared shell at ``layouts/baseof.html``, so a wrong predicate ships site-wide and
source-level greps cannot prove placement. Only a rendered tree can.

Three assertions, in increasing strength:

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
import sys
from pathlib import Path

# Pinned once in AC 2.2 and quoted by every other surface: the outer element in
# layouts/_partials/subscribe-form.html, the CSS selector in assets/css/main.css,
# and this grep. Changing it here alone silently disarms the gate.
MARKER = "subscribe-form"

# baseof.html emits this on every page it renders. Its absence means the file is an
# alias stub or a standalone bundle asset, not a page with a footer to guard.
BASEOF_MARKER = "<footer"

# The five suppressed classes, as BUILT paths.
#   /legal/*   operator instruction
#   /private/* the per-path CSP at static/_headers:10 is narrower than the root
#              policy and would break the Turnstile widget, so the form is removed
#              rather than worked around
#   404        a form posting from a URL that does not exist
#   the AGIT signup and thanks pages, which already carry an email-capture form
SUPPRESSED_PREFIXES = (
    "legal/",
    "private/",
    "community/asians-gingers-in-tech/",
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


def is_suppressed(rel: str) -> bool:
    return rel in SUPPRESSED_EXACT or rel.startswith(SUPPRESSED_PREFIXES)


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
