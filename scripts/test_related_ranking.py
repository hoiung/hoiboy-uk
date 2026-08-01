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
          tag the remainder are category-then-last-resort top-ups with zero
          shared tags. Both top-ups iterate least-reachable-first, not
          newest-first (the operator-authorised tie-break change; see the
          `## Scope update` comment on blog-priv#66). The ORDER within a top-up
          is not what this check asserts - it asserts the category top-up is
          exhausted before the last resort runs.
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


def _reach(meta: dict[str, PostMeta]) -> dict[str, int]:
    """slug -> how many OTHER posts share at least one tag with it.

    An INDEPENDENT re-derivation of what `layouts/_partials/readnext-reach.html`
    computes in Go. That independence is the whole point: reach had exactly one
    producer and no verifier, so the template could be deleted outright and every
    check here still passed. Deriving it a second time, from the front matter
    rather than from the rendered HTML, is what lets `check_tie_break` below
    discriminate.

    Keep this definition and the template's in step. If they ever disagree,
    `check_tie_break` starts failing for a reason that has nothing to do with the
    ranking - which is the same contract `_norm_terms` carries against the
    template's tag lowering.
    """
    return {
        slug: sum(1 for other in meta if other != slug and _shared(meta, slug, other))
        for slug in meta
    }


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
        # EVERY tail slot, not just the first. Checking only tail[0] leaves the
        # gate blind to a top-up that starts correctly and then falls to recency
        # partway down while category candidates remain - link 4 category, link 5
        # recency-with-candidates-left would have passed. (Ralph Tier 3.)
        picked = set(known[:matches])
        remaining = {
            other for other in meta
            if other != slug and other not in picked and meta[slug].categories & meta[other].categories
        }
        for offset, link in enumerate(tail):
            if not meta[slug].categories & meta[link].categories and remaining:
                failures.append(
                    f"AC 1.2: /blogs/{slug}/ fell to the last-resort top-up at link "
                    f"{matches + offset + 1} ({link}) while {len(remaining)} unpicked "
                    f"sibling(s) still shared a category. The category top-up must be "
                    f"exhausted before the last-resort top-up runs."
                )
                break
            remaining.discard(link)


def check_tie_break(meta, rn_map, failures: list[str]) -> int:
    """Ties on shared-tag count go to the LEAST-REACHABLE post, not the newest.

    This is the operator-authorised tie-break (blog-priv#66 `## Scope update`) and
    it is the mechanism the whole change now rests on: it took the site from 6
    zero-inbound posts back to 2 and halved the hub again, at no relevance cost.

    Ralph round 3 Tier 2 proved it had NO gate. Reverting the sort key from
    `reach * 1000 + date-rank` to plain `date-rank` - deleting the mechanism
    outright - left every other check green, because `check_hub_cap`'s ceiling of
    30 cannot tell the reach hub (12) from the recency hub (24), and
    `check_monotonic` / `check_topup` only constrain shared-tag count and top-up
    SEQUENCING, never which candidate wins a tie. A gate that passes in both the
    fixed and the broken state is not a gate.

    THE PROPERTY, and it holds for ALL THREE selection passes, not just the first.
    The template walks `$ordered` (reach ascending, then date descending) three
    times: once per shared-tag bucket, once for the category top-up, once for the
    last resort. Each pass draws from its own eligibility pool. So for every pool:
    every candidate PICKED from it must sort at or before every candidate LEFT in
    it, under the key `(reach, date-rank)`.

    Covering only the tag pass is not enough, and this is the second time that lesson
    landed on this function. The first version bucketed on `if n:` - shared-tag count
    of at least one - which silently discarded every candidate the two top-ups draw
    from, because those pools are zero-shared-tag BY CONSTRUCTION. Ralph round 4
    Tier 2 reverted both top-ups from `$ordered` to `$byDate`, undoing half the
    operator-authorised change, and the suite still passed with exit 0 and the same
    61 buckets. Enumerating the pools instead of the one pass that prompted the fix
    is what closes the ORDERING half of the class.

    WHAT THIS FUNCTION DOES NOT COVER, stated plainly so the next reader does not
    over-trust it. It asserts reach-ordering WITHIN whatever each pool contributed.
    It does NOT assert that the passes ran in the right ORDER - that the category
    top-up is exhausted before the last resort. `check_topup` owns that half, and the
    two are complements, not substitutes. Ralph round 5 Tier 2 proved the distinction
    by disabling the category filter so the last resort drew from both pools at once:
    `check_topup` produced 13 failures, and this function reported zero, because a
    reach-ascending prefix of a merged pool leaves each SUBSET internally
    reach-sorted, so the taken-vs-left comparison is still satisfied. The suite
    catches that mutation; this function alone does not. Do not delete `check_topup`
    on the theory that this supersedes it.

    Only a pool the 5-link cap cut through can discriminate; a pool consumed whole,
    or one that contributed nothing, leaves nothing behind to compare against and is
    skipped rather than counted as a pass. The return value is how many pools
    actually got compared, so a corpus that stops producing them reports that plainly
    instead of passing vacuously.
    """
    reach = _reach(meta)
    by_date = sorted(meta, key=lambda s: meta[s].date, reverse=True)
    date_rank = {slug: i for i, slug in enumerate(by_date)}
    key = lambda s: (reach[s], date_rank[s])  # noqa: E731 - the template's sort key

    discriminating = 0
    for slug, links in sorted(rn_map.items()):
        picked = set(links)
        others = [o for o in meta if o != slug]

        # One pool per selection pass, in the order the template runs them.
        pools: list[tuple[str, list[str]]] = []

        buckets: dict[int, list[str]] = {}
        for other in others:
            n = _shared(meta, slug, other)
            if n:
                buckets.setdefault(n, []).append(other)
        for n, members in sorted(buckets.items(), reverse=True):
            pools.append((f"at {n} shared tag(s)", members))

        # The two top-ups draw only from zero-shared-tag candidates. The last resort
        # scans every unpicked candidate, but each top-up loop walks its whole list
        # and only no-ops once the box holds 5 - it never breaks early - so by the
        # time the last resort can take anything, the category pool is either
        # exhausted or the box is full. That is what makes these two pools a correct
        # partition OF THE OUTCOME the template produces. It is not an independent
        # check that the passes ran in that order; see the docstring.
        zero = [o for o in others if not _shared(meta, slug, o)]
        shares_cat = [o for o in zero if meta[slug].categories & meta[o].categories]
        no_cat = [o for o in zero if not (meta[slug].categories & meta[o].categories)]
        if shares_cat:
            pools.append(("in the category top-up", shares_cat))
        if no_cat:
            pools.append(("in the last-resort top-up", no_cat))

        for label, members in pools:
            taken = [m for m in members if m in picked]
            left = [m for m in members if m not in picked]
            if not taken or not left:
                continue  # consumed whole, or contributed nothing: nothing to compare
            discriminating += 1
            worst_taken = max(taken, key=key)
            best_left = min(left, key=key)
            if key(worst_taken) > key(best_left):
                failures.append(
                    f"AC 1.6/tie-break: /blogs/{slug}/ took {worst_taken} "
                    f"(reach {reach[worst_taken]}) over {best_left} "
                    f"(reach {reach[best_left]}) {label}. Ties must go to the "
                    f"least-reachable post, so a post with fewer other ways in gets "
                    f"the slot. This is what fails if any of the three passes in "
                    f"related-posts.html stops iterating $ordered."
                )
                break

    if not discriminating:
        failures.append(
            "AC 1.6/tie-break: no bucket in the whole corpus had both a picked and "
            "an unpicked member, so this check compared nothing. It would pass with "
            "the reach mechanism deleted. Treat as a failure, not a pass."
        )
    return discriminating


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
    tie_buckets = check_tie_break(meta, rn_map, failures)
    hub, hub_count = check_hub_cap(meta, rn_map, failures)
    covered = check_edge_cases(meta, rn_map, failures)

    if failures:
        print(f"FAIL: {len(failures)} Read Next ranking violation(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"OK: all {len(rn_map)} Read Next boxes are ordered by shared-tag count, "
          f"descending; every box is {min(BOX_SIZE, len(meta) - 1)} links with "
          f"zero-shared-tag top-ups only in the tail; ties went to the "
          f"least-reachable post in all {tie_buckets} boundary bucket(s); the "
          f"largest hub is {hub} at {hub_count} of {len(meta)} (cap {HUB_CAP}).")
    for line in covered:
        print(f"    edge case covered: {line}")
    return 0


def test_related_ranking() -> None:
    """pytest entry point (CI runs pytest through explicit file lists)."""
    assert main([]) == 0


if __name__ == "__main__":
    sys.exit(main())
