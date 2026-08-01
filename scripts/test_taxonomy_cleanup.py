#!/usr/bin/env python3
"""The `categories` taxonomy is off and nothing else moved (blog-priv#62 Phase 6).

  AC 6.1 - `category = "categories"` is gone from hugo.toml.
  AC 6.2 - zero /categories/ URLs remain in the built sitemap.
  AC 6.4 - /tags/ and /series/ are untouched, at the SAME counts as before.
  AC 6.5 - the `categories:` FRONT-MATTER KEY survives on all 79 posts.

AC 6.5 is the one that makes this test worth having. "Switch the taxonomy off"
reads like it could mean stripping the key from every post, and it does not:
four templates read `.Params.categories` (breadcrumb-trail.html,
related-posts.html, _default/list.html, _default/single.html), so removing the key
would empty all 7 category landings and break the post breadcrumb. Removing the
MAPPING drops exactly the 8 /categories/ URLs and changes nothing else.

Usage:  python3 scripts/test_taxonomy_cleanup.py [--built public]
Exit 0 = clean. Exit 1 = a named failure.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUGO_TOML = ROOT / "config" / "_default" / "hugo.toml"
POSTS = ROOT / "content" / "posts"

# Measured before the change (2026-07-25): the sitemap carried 217 tag URLs and
# 2 series URLs, and Phase 6 must not touch either (A11).
#
# blog-priv#66 Phase 4 moved the tag floor 217 -> 211 DELIBERATELY. Six /tags/
# terms were retired by merging mechanically-duplicate tags (casing, plural and
# whitespace spellings of a term that already existed); each retired URL has a
# 301 in static/_redirects and a line in the coverage baseline, so it is a
# migration rather than a loss. The number is derived, not fitted: 216 term
# pages plus the /tags/ landing is 217 sitemap paths today, minus the 6 that
# stop generating. Eight merges were applied but only six retire a URL -
# `brazilian-zouk` survives via what-is-zouk-aam and `AI` already slugged to
# `ai`. If this number ever needs to move again, move it for a reason you can
# write down here; loosening it to make a red test go quiet is how the taxonomy
# loses pages unnoticed, which is the whole point of a floor.
EXPECT_TAGS = 211
EXPECT_SERIES = 2

_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")


def sitemap_paths(built: Path) -> list[str]:
    sitemap = built / "sitemap.xml"
    if not sitemap.is_file():
        sys.exit(f"AC 6.2: no sitemap at {sitemap} (run `hugo` first)")
    return [re.sub(r"^https?://[^/]+", "", loc)
            for loc in _LOC_RE.findall(sitemap.read_text(encoding="utf-8"))]


def check_config(failures: list[str]) -> None:
    cfg = HUGO_TOML.read_text(encoding="utf-8")
    if re.search(r'^\s*category\s*=\s*"categories"', cfg, re.M):
        failures.append('AC 6.1: hugo.toml still maps category = "categories"')
    for keep in ('tag = "tags"', 'series = "series"'):
        if keep not in cfg:
            failures.append(f"AC 6.4: hugo.toml no longer declares {keep}; only the "
                            f"`category` taxonomy was in scope")


def check_sitemap(built: Path, failures: list[str]) -> None:
    paths = sitemap_paths(built)
    cats = [p for p in paths if p.startswith("/categories/")]
    if cats:
        failures.append(f"AC 6.2: {len(cats)} /categories/ URL(s) still in the sitemap: "
                        f"{cats[:3]}")
    # A FLOOR, not an equality. The property AC 6.4 protects is that switching the
    # `category` taxonomy off did not take `tags` or `series` down with it - i.e. that
    # none DISAPPEARED. An exact `!=` also reddens CI the first time a new post carries
    # a tag nobody has used before, which on a blog that publishes regularly is a
    # near-term certainty and has nothing to do with Phase 6. That turns a correct
    # publish into a build failure and teaches the next author to edit the number until
    # the suite goes quiet - which is how a real regression eventually gets waved
    # through. A floor catches every loss and stays silent on legitimate growth.
    # (Ralph round 6 Tier 3.)
    for label, prefix, expect in (("tags", "/tags/", EXPECT_TAGS),
                                  ("series", "/series/", EXPECT_SERIES)):
        n = len([p for p in paths if p.startswith(prefix)])
        if n < expect:
            failures.append(f"AC 6.4: {n} {label} URLs in the sitemap, down from the "
                            f"{expect} measured before Phase 6. {label.title()} is out of "
                            f"scope for this change, so a DROP means the taxonomy was "
                            f"collateral damage. Growth is fine and is not checked.")


def check_frontmatter_key(failures: list[str]) -> None:
    """AC 6.5 - the key stays on every post."""
    bundles = sorted(POSTS.glob("*/index.md"))
    if not bundles:
        failures.append(f"AC 6.5: walked 0 posts under {POSTS} (vacuous pass)")
        return
    missing = [b.parent.name for b in bundles
               if not re.search(r"^categories:", b.read_text(encoding="utf-8"), re.M)]
    if missing:
        failures.append(
            f"AC 6.5: {len(missing)} of {len(bundles)} posts lost their `categories:` "
            f"front-matter key: {missing[:5]}. Switching the taxonomy off means removing "
            f"the MAPPING only; four templates read .Params.categories, so without the "
            f"key every category landing empties and the post breadcrumb breaks."
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
    check_config(failures)
    check_frontmatter_key(failures)
    if not built.is_dir():
        failures.append(f"AC 6.2: built site not found at {built} (run `hugo` first)")
    else:
        check_sitemap(built, failures)

    if failures:
        print(f"FAIL: {len(failures)} taxonomy-cleanup violation(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    n = len(sorted(POSTS.glob("*/index.md")))
    print(f"OK: the `categories` taxonomy is off (0 /categories/ URLs), tags and series "
          f"have not dropped below their pre-Phase-6 {EXPECT_TAGS}/{EXPECT_SERIES}, and "
          f"all {n} posts keep their `categories:` front-matter key")
    return 0


def test_taxonomy_cleanup() -> None:
    """pytest entry point (CI runs pytest through explicit file lists)."""
    assert main([]) == 0


if __name__ == "__main__":
    sys.exit(main())
