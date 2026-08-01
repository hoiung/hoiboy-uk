#!/usr/bin/env python3
"""The Read Next box is ranked by shared tags, and stays that way (blog-priv#66).

Before this file the only test touching the box asserted that a `read-next`
element existed and held at least one link, against one hard-coded post
(`test_section_keyed_regression.py:79-83`). A ranking that returned the five
oldest food posts on every page would have passed it. That is the gap this
closes: without an assertion on WHICH posts appear, a silent revert to
category-and-recency would never be noticed.

Everything here asserts the RULE, not a frozen list of slugs, so publishing a
new post cannot redden CI (AC 2.2). The named posts below are edge-case
ANCHORS - each is checked for the property that made it interesting, and the
property is re-derived from the corpus rather than assumed, so a corpus that
moves on reports honestly instead of failing for the wrong reason.

  AC 1.2  every box is exactly 5 links, and where fewer than 5 siblings share a
          tag the remainder are category-then-recency top-ups with zero shared
          tags.
  AC 1.4  the oldest post renders a full box (the includeNewer=false failure
          mode does not occur on the hand-rolled route).
  AC 1.5  the named edge cases still render: two categories, newest, oldest,
          and the one post with no tag matches at all.
  AC 1.6  no single post appears in more than HUB_CAP of the boxes.
  AC 2.3  monotonic ordering: the shared-tag count of link i is >= link i+1.
          This is the one that isolates a sort-key inversion - a presence check
          cannot see it, and the hub cap is a distribution statistic that can
          redden for unrelated reasons.

Parsing is delegated to scripts/readnext_parse.py, the SAME parser the Phase 0
baseline used, so the before/after comparison is like-for-like and the test and
the template cannot disagree about what a shared tag is.

Usage:  python3 scripts/test_related_ranking.py [--built public]
Exit 0 = the ranking holds. Exit 1 = a named failure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from readnext_parse import PostMeta, inbound_counts, post_meta, read_next_map  # noqa: E402

# The box is capped at 5 in the template. Expressed as a cap rather than a
# literal so a corpus smaller than 6 posts does not fail for the wrong reason.
BOX_SIZE = 5

# AC 1.6. The Stage-1 simulation predicted a maximum of 24 of 80; the ceiling is
# 30 to leave room for an implementation that differs slightly from it. The
# pre-fix maximum was 77 of 80, so this discriminates.
HUB_CAP = 30


# The posts AC 1.5 names. They are PREFERENCES, not requirements: the anchor
# falls back to whatever else in the corpus carries the same property, so a post
# that gains a tag match or loses a category moves the example rather than
# reddening CI for a reason that has nothing to do with the ranking.
NAMED_MULTI_CATEGORY = "entrepreneurship-in-a-nutshell"
NAMED_NO_TAG_MATCH = "reverse-engineering-moju-ginger-shots"


def _prefer(named: str, group: list[str]) -> str:
    """The issue's named example when it still has the property, else the first
    post that does."""
    return named if named in group else group[0]


def _shared(meta: dict[str, PostMeta], a: str, b: str) -> int:
    return len(meta[a].tags & meta[b].tags)


def _tag_matching_siblings(meta: dict[str, PostMeta], slug: str) -> int:
    return sum(1 for other in meta if other != slug and _shared(meta, slug, other))


def check_links_resolve(meta, rn_map, failures: list[str]) -> None:
    """Every href in a box resolves to a post this test knows about.

    Two posts override their URL with a front-matter `slug:` key, so a link
    joins back on the URL slug and not the bundle directory name. If that ever
    breaks, every downstream count silently loses those posts instead of
    failing, which is why this runs first.
    """
    for slug, links in sorted(rn_map.items()):
        unknown = [link for link in links if link not in meta]
        if unknown:
            failures.append(
                f"AC 2.2: /blogs/{slug}/ Read Next links to {unknown}, which resolve to "
                f"no post bundle. A link that cannot be joined back to its front matter "
                f"cannot be checked for shared tags, so the ranking would be unverifiable."
            )


def check_box_size(meta, rn_map, failures: list[str]) -> None:
    """AC 1.2 / Expected Behavior: reading (A) fills every box to exactly 5."""
    expected = min(BOX_SIZE, len(meta) - 1)
    for slug, links in sorted(rn_map.items()):
        if len(links) != expected:
            failures.append(
                f"AC 1.2: /blogs/{slug}/ Read Next has {len(links)} links, expected "
                f"{expected}. Reading (A) tops up with category then recency so every "
                f"box is full; a short box means a top-up stage stopped firing."
            )


def check_monotonic(meta, rn_map, failures: list[str]) -> None:
    """AC 2.3: shared-tag count never increases down the list.

    The assertion that fires when the template reverts to category-and-recency,
    and the only one here that isolates a sort-key inversion.
    """
    for slug, links in sorted(rn_map.items()):
        known = [link for link in links if link in meta]
        for i in range(len(known) - 1):
            hi, lo = _shared(meta, slug, known[i]), _shared(meta, slug, known[i + 1])
            if hi < lo:
                failures.append(
                    f"AC 2.3: /blogs/{slug}/ Read Next is not ordered by shared-tag "
                    f"count.\n        Link {i + 1} ({known[i]}) shares {hi} tags but sits "
                    f"above link {i + 2} ({known[i + 1]})\n        which shares {lo}. The "
                    f"sort key in related-posts.html is not the\n        tag intersection."
                )
                break


def check_topup(meta, rn_map, failures: list[str]) -> None:
    """AC 1.2: below 5 tag matches, the tail is category-then-recency filler.

    Checked on every post that actually exercises the top-up rather than on one
    named example, so the check cannot go vacuous when the named post gains a
    tag match. `entrepreneurship-in-a-nutshell` is the worked example in the
    issue and is covered by this sweep like any other.
    """
    for slug, links in sorted(rn_map.items()):
        matches = _tag_matching_siblings(meta, slug)
        if matches >= BOX_SIZE:
            continue
        known = [link for link in links if link in meta]
        tail = known[matches:]
        impure = [link for link in tail if _shared(meta, slug, link)]
        if impure:
            failures.append(
                f"AC 1.2: /blogs/{slug}/ has {matches} tag-matching sibling(s), so links "
                f"{matches + 1}+ must be top-ups with zero shared tags, but {impure} "
                f"share one. Either the tag ranking missed a match or the top-up ran "
                f"before the ranking finished."
            )
            continue
        if not tail:
            continue
        picked = set(known[:matches])
        cat_candidates = {
            other for other in meta
            if other != slug and other not in picked and meta[slug].categories & meta[other].categories
        }
        if cat_candidates and not meta[slug].categories & meta[tail[0]].categories:
            failures.append(
                f"AC 1.2: /blogs/{slug}/ fell straight to recency at link {matches + 1} "
                f"({tail[0]}) while {len(cat_candidates)} unpicked sibling(s) still shared "
                f"a category. The category top-up must be exhausted before the recency "
                f"top-up runs."
            )


def check_hub_cap(meta, rn_map, failures: list[str]) -> tuple[str, int]:
    """AC 1.6: no post monopolises the boxes. Returns the measured hub."""
    counts = inbound_counts(rn_map, sorted(meta))
    hub = max(counts, key=lambda s: (counts[s], s))
    if counts[hub] > HUB_CAP:
        failures.append(
            f"AC 1.6: {hub} appears in {counts[hub]} of {len(meta)} Read Next boxes, over "
            f"the cap of {HUB_CAP}. One post dominating the boxes is the concentration "
            f"this ranking exists to break up (it was 77 of 80 before the change)."
        )
    return hub, counts[hub]


def check_edge_cases(meta, rn_map, failures: list[str]) -> list[str]:
    """AC 1.4 + AC 1.5: the named edge cases still render a full box.

    Each anchor is re-derived from the corpus rather than hard-coded, so the
    check follows the corpus instead of failing when it moves. The covered set
    is returned and printed, so a case that stops existing is visible rather
    than silently dropped.
    """
    expected = min(BOX_SIZE, len(meta) - 1)
    dated = [s for s in meta if meta[s].date]
    anchors: dict[str, str] = {}
    if dated:
        anchors["oldest post (AC 1.4, no chronological previous)"] = min(dated, key=lambda s: meta[s].date)
        anchors["newest post (no chronological next)"] = max(dated, key=lambda s: meta[s].date)
    multi_cat = sorted(s for s in meta if len(meta[s].categories) > 1)
    if multi_cat:
        anchors["post with two categories"] = _prefer(NAMED_MULTI_CATEGORY, multi_cat)
    no_match = sorted(s for s in meta if not _tag_matching_siblings(meta, s))
    if no_match:
        anchors["post with zero tag matches"] = _prefer(NAMED_NO_TAG_MATCH, no_match)

    covered: list[str] = []
    for label, slug in anchors.items():
        covered.append(f"{label} = {slug}")
        links = rn_map.get(slug)
        if links is None:
            failures.append(f"AC 1.5: the {label} ({slug}) renders no Read Next box at all")
        elif len(links) != expected:
            failures.append(
                f"AC 1.5: the {label} ({slug}) renders {len(links)} links, expected "
                f"{expected}. This edge case is named in the issue precisely because it "
                f"is where a ranking is most likely to return a short box."
            )
    for label, group in (("posts with two categories", multi_cat),
                         ("posts with zero tag matches", no_match)):
        if len(group) > 1:
            covered.append(f"{label}: {len(group)} in corpus, all checked by the sweeps above")
    return covered


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

    if not built.is_dir():
        print(f"FAIL: built site not found at {built} (run `hugo` first)", file=sys.stderr)
        return 1

    meta = post_meta()
    if len(meta) < 2:
        print(f"FAIL: walked {len(meta)} posts; every check below would pass vacuously",
              file=sys.stderr)
        return 1

    try:
        rn_map = read_next_map(built, sorted(meta))
    except (ValueError, FileNotFoundError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    failures: list[str] = []
    check_links_resolve(meta, rn_map, failures)
    check_box_size(meta, rn_map, failures)
    check_monotonic(meta, rn_map, failures)
    check_topup(meta, rn_map, failures)
    hub, hub_count = check_hub_cap(meta, rn_map, failures)
    covered = check_edge_cases(meta, rn_map, failures)

    if failures:
        print(f"FAIL: {len(failures)} Read Next ranking violation(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"OK: all {len(rn_map)} Read Next boxes are ordered by shared-tag count, "
          f"descending; every box is {min(BOX_SIZE, len(meta) - 1)} links with "
          f"zero-shared-tag top-ups only in the tail; the largest hub is {hub} at "
          f"{hub_count} of {len(meta)} (cap {HUB_CAP}).")
    for line in covered:
        print(f"    edge case covered: {line}")
    return 0


def test_related_ranking() -> None:
    """pytest entry point (CI runs pytest through explicit file lists)."""
    assert main([]) == 0


if __name__ == "__main__":
    sys.exit(main())
