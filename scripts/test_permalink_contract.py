#!/usr/bin/env python3
"""Every retired URL maps 1:1 onto a live one (blog-priv#62 AC 5.2, AC 5.15c).

39 files across four other repos link to the pre-move URLs, including a submitted
funding application and material already sent to recruiters. None of them can be
retroactively edited, so "every old URL still resolves" is the load-bearing
property of this change, not housekeeping. This test is what proves it, against
the checked-in baseline of URLs that actually existed before the move.

The mapping is TWO rules, not one prefix swap:

  A. /posts/X/     -> /blogs/X/        prefix REPLACEMENT   (80 URLs)
  B. /<category>/  -> /blogs/<category>/  prefix INSERTION   (7 URLs)

Coding to "just swap the prefix" lands 80 of 87 and leaves the 7 category
landings dead, which is why both rules are asserted separately, along with their
disjointness (no URL may be claimed by both) and totality (no URL unmapped).

AC 5.15c is asserted here too: the regenerated sitemap must contain no retired
first-segment. The pattern is anchored to the FIRST path segment on purpose. An
unanchored `<loc>[^<]*/(posts|tech-ai|...)/` matches the CORRECT new
/blogs/<category>/ canonicals and the deliberately-untouched /tags/<category>/
term pages, so it returns >=11 on a perfectly correct tree and can never reach 0.

Usage:  python3 scripts/test_permalink_contract.py [--built public]
Exit 0 = the contract holds. Exit 1 = a named failure.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "scripts" / "tests" / "fixtures" / "blogs_ia" / "retired_urls.txt"
# Live /blogs/ URLs for pages authored AFTER the migration, which by definition have
# no retired URL mapping onto them. See that file's header for why they are not added
# to the baseline instead.
ADDED_SINCE = ROOT / "scripts" / "tests" / "fixtures" / "blogs_ia" / "added_since_migration.txt"

CATEGORIES = (
    "tech-ai", "entrepreneurship", "trading", "food-booze", "adventure", "dance", "life",
)
# First path segments that must no longer appear in the sitemap. `posts` and the 7
# categories moved; `categories` was switched off in Phase 6.
RETIRED_SEGMENTS = ("posts", *CATEGORIES, "categories")

_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")

# An exact phrase from the two docs/AUTHORING.md lines that legitimately SHOW a retired
# shape because they teach authors not to use it. Deliberately not the bare word
# "retired" -- see check_authoring_doc's docstring for the mutants that escaped that.
_RETIRED_LABEL_RE = re.compile(
    r"do not author these|still resolve for visitors through the 301s", re.I)
_EXPECTED_LABELLED_LINES = 2

# A rendered link or asset ref whose FIRST path segment is retired.
_RETIRED_REF_RE = re.compile(
    r'(?:href|src)="/(' + "|".join(RETIRED_SEGMENTS) + r')/')


def read_baseline() -> list[str]:
    """The retired PAGE URLs (feeds and taxonomy URLs are the coverage test's job).

    BOTH taxonomies are filtered out, for the one reason in the docstring above.
    `/categories/` was excluded when Phase 6 switched that taxonomy off; blog-priv#66
    Phase 4 retired 6 `/tags/` terms by merging mechanically-duplicate tags, and they
    are the same shape of thing. A taxonomy URL has no 1:1 live counterpart under
    /blogs/ to map onto, so leaving it in here fails `check_mapping` twice over -
    once as "matches neither rule", once as "the mapping is not 1:1" - for a URL this
    test never claimed to own. scripts/test_redirects_coverage.py is what proves those
    six resolve, and it reads the same baseline file precisely so the two cannot
    disagree about which URLs were retired.
    """
    if not BASELINE.exists():
        sys.exit(f"AC 5.2: baseline not found at {BASELINE}; without it this test "
                 f"would compare the new sitemap against itself and pass vacuously")
    urls = [ln.strip() for ln in BASELINE.read_text(encoding="utf-8").splitlines()]
    return [u for u in urls if u.startswith("/") and not u.endswith(".xml")
            and not u.startswith("/categories/") and not u.startswith("/tags/")]


def read_added_since() -> set[str]:
    """Live /blogs/ URLs for pages authored after the migration.

    Absent file is fine and means "nothing published since the move" -- unlike the
    baseline, whose absence would make the test vacuous, this one only ever widens
    what AC 5.2 tolerates, and an empty set widens it by nothing.
    """
    if not ADDED_SINCE.exists():
        return set()
    return {ln.strip() for ln in ADDED_SINCE.read_text(encoding="utf-8").splitlines()
            if ln.strip().startswith("/")}


def sitemap_paths(built: Path) -> set[str]:
    sitemap = built / "sitemap.xml"
    if not sitemap.is_file():
        sys.exit(f"AC 5.2: no sitemap at {sitemap} (run `hugo` first)")
    paths = set()
    for loc in _LOC_RE.findall(sitemap.read_text(encoding="utf-8")):
        paths.add(re.sub(r"^https?://[^/]+", "", loc))
    return paths


def check_mapping(retired: list[str], live: set[str], failures: list[str]) -> None:
    rule_a = [u for u in retired if u.startswith("/posts/")]
    rule_b = [u for u in retired if u in {f"/{c}/" for c in CATEGORIES}]
    unclaimed = [u for u in retired if u not in rule_a and u not in rule_b]

    if unclaimed:
        failures.append(f"AC 5.2: {len(unclaimed)} retired URL(s) match neither rule: "
                        f"{unclaimed[:5]}")
    both = set(rule_a) & set(rule_b)
    if both:
        failures.append(f"AC 5.2: rules A and B are not disjoint, {sorted(both)[:5]} "
                        f"claimed by both, so the mapping is ambiguous")

    for label, group, fn in (
        ("A", rule_a, lambda u: u.replace("/posts/", "/blogs/", 1)),
        ("B", rule_b, lambda u: "/blogs" + u),
    ):
        dead = [(u, fn(u)) for u in group if fn(u) not in live]
        if dead:
            failures.append(
                f"AC 5.2: rule {label} maps {len(dead)} of {len(group)} retired URL(s) "
                f"to a target the new sitemap does NOT serve: {dead[:5]}"
            )

    mapped = {fn(u) for group, fn in (
        (rule_a, lambda u: u.replace("/posts/", "/blogs/", 1)),
        (rule_b, lambda u: "/blogs" + u),
    ) for u in group}
    blogs_live = {u for u in live if u == "/blogs/" or u.startswith("/blogs/")}
    if len(retired) != len(mapped):
        failures.append(f"AC 5.2: {len(retired)} retired URLs collapsed onto "
                        f"{len(mapped)} targets, so the mapping is not 1:1")
    added_since = read_added_since()
    extra = blogs_live - mapped - added_since
    if extra:
        failures.append(f"AC 5.2: the new tree serves {len(extra)} /blogs/ URL(s) that "
                        f"no retired URL maps onto: {sorted(extra)[:5]}. Either the "
                        f"baseline is stale, or a page was added after the migration "
                        f"and needs listing in {ADDED_SINCE.name}.")

    # The acknowledgement list cannot rot: a URL named there that the site no longer
    # serves is a dead line, and dead lines are how an allowlist quietly stops meaning
    # anything. Fail on it rather than let it accumulate.
    dead_ack = added_since - blogs_live
    if dead_ack:
        failures.append(f"AC 5.2: {ADDED_SINCE.name} lists {len(dead_ack)} URL(s) the "
                        f"sitemap does not serve: {sorted(dead_ack)[:5]}. Remove the "
                        f"stale line(s) or restore the page.")


def check_sitemap_clean(live: set[str], failures: list[str]) -> None:
    """AC 5.15c - no retired FIRST segment survives in the sitemap."""
    for seg in RETIRED_SEGMENTS:
        hits = sorted(u for u in live if u.split("/")[1:2] == [seg])
        if hits:
            failures.append(
                f"AC 5.15c: sitemap still carries {len(hits)} canonical(s) under the "
                f"retired first segment /{seg}/: {hits[:3]}"
            )


def check_no_retired_links(built: Path, failures: list[str]) -> None:
    """No RENDERED page links to a retired URL (blog-priv#62, Ralph Tier 3 round 2).

    Every other check in this file asserts what the build SERVES. This one asserts what
    the build LINKS TO, and nothing else covered it: `validate_internal_links.py` walks
    `content/**/*.md` only and never sees rendered output; `lychee.toml` puts
    `public/blogs` in `exclude_path`; and the CI URL-contract block asserts that retired
    paths are not BUILT, never that nothing points at one.

    That gap shipped a real defect. `layouts/_default/single.html` hand-built its
    category chip as `/{{ $c | urlize }}/`, which was correct until the landings moved
    under /blogs/. The file has zero diff lines on this branch -- it was simply left
    behind -- and the result was 113 retired hrefs across all 79 post pages, each page
    self-inconsistent because its own breadcrumb and sidebar already pointed at the live
    path. Every one still "worked", via a 301, which is exactly why no gate noticed.

    A redirect is a safety net for INBOUND links from places we do not control. An
    in-repo link taking a redirect hop is a defect, and it is the rule this repo already
    states in `validate_internal_links.py` and `docs/AUTHORING.md`.
    """
    pages = sorted(built.rglob("*.html"))
    if not pages:
        failures.append(f"AC 5.2: no rendered HTML under {built} to check for retired links")
        return
    offenders: dict[str, list[str]] = {}
    for page in pages:
        hits = set(_RETIRED_REF_RE.findall(page.read_text(encoding="utf-8", errors="replace")))
        for seg in hits:
            offenders.setdefault(seg, []).append(str(page.relative_to(built)))
    if offenders:
        detail = "; ".join(
            f"/{seg}/ on {len(paths)} page(s) e.g. {sorted(paths)[0]}"
            for seg, paths in sorted(offenders.items())
        )
        failures.append(
            f"AC 5.2: the rendered site links to retired URLs that only survive via a "
            f"301 -- {detail}. An in-repo link must point at the live path; resolve the "
            f"target page and use its .RelPermalink rather than hand-building the URL."
        )


def check_permalink_token(failures: list[str]) -> None:
    """AC 5.1 - the token itself. `:slug` builds clean and silently rewrites 51 of
    82 post URLs to title-derived strings, so asserting on the built output alone
    would not catch a regression that swapped the token back."""
    cfg = (ROOT / "config" / "_default" / "hugo.toml").read_text(encoding="utf-8")
    if 'posts = "/blogs/:slugorcontentbasename/"' not in cfg:
        failures.append('AC 5.1: hugo.toml has no [permalinks.page] posts = '
                        '"/blogs/:slugorcontentbasename/"')
    if 'posts = "/blogs/:slug/"' in cfg:
        failures.append('AC 5.1: hugo.toml uses the :slug token, which resolves 51 of '
                        '82 post URLs to a title-derived string instead of the '
                        'published slug')


def check_authoring_doc(failures: list[str]) -> None:
    """AC 5.12 - docs/AUTHORING.md teaches the LIVE served-URL contract.

    It is the in-tree canonical that validate_internal_links.py's own error hint and
    the /blog skill both point authors at, so a stale contract here has every future
    post authored against the retired scheme.

    The AC's own verify (`grep -c '/posts/' docs/AUTHORING.md` returns 0) cannot be
    satisfied and should not be: `content/posts/` is a CONTENT path and content
    directories did not move, and the doc deliberately shows the retired shapes in a
    "do not author these" row. Both are correct content that a bare substring count
    cannot tell apart from a stale URL. So the check is narrowed to what the AC was
    a proxy for: a `/posts/...` that appears as a SERVED URL, in link or src or
    inline-code position, on a line that does not explicitly LABEL it retired.

    "Explicitly label" is an exact-phrase match plus a pinned count, not the bare word
    "retired". Ralph Tier 3 (round 2) mutation-proved that a bare-substring skip lets a
    genuinely stale URL escape whenever it merely shares a line with that word -- e.g.
    a live link inside a sentence about "the retired scheme", or one sitting next to a
    filename like RETIRED_NOTES.md. Both mutants escaped a `"retired" in line.lower()`
    skip while an identical link on an ordinary line was caught. Pinning the count
    means a NEW exempt line cannot appear without failing this test first.
    """
    doc = ROOT / "docs" / "AUTHORING.md"
    if not doc.is_file():
        failures.append("AC 5.12: docs/AUTHORING.md does not exist")
        return
    text = doc.read_text(encoding="utf-8")
    if "/blogs/<slug>/" not in text:
        failures.append("AC 5.12: docs/AUTHORING.md never states the live "
                        "/blogs/<slug>/ contract")
    stale, labelled = [], 0
    for n, line in enumerate(text.splitlines(), 1):
        body = line.replace("content/posts/", "")
        if not re.search(r'(\]\(|src="|href="|`)/posts/', body):
            continue
        if _RETIRED_LABEL_RE.search(line):
            labelled += 1                  # a deliberate "do not author this" mention
            continue
        stale.append(f"{n}: {line.strip()[:90]}")
    if stale:
        failures.append(f"AC 5.12: docs/AUTHORING.md still teaches the retired "
                        f"/posts/ served URL on {len(stale)} line(s): {stale[:3]}")
    if labelled != _EXPECTED_LABELLED_LINES:
        failures.append(
            f"AC 5.12: docs/AUTHORING.md has {labelled} line(s) exempted as "
            f"explicitly-labelled retired shapes, expected {_EXPECTED_LABELLED_LINES}. "
            f"Re-read them: an exemption added without thought is how a stale served "
            f"URL gets taught to every future author."
        )


def check_lychee_exclude(failures: list[str]) -> None:
    """AC 5.16 - lychee.toml excludes the BUILT path that moved, not the CONTENT
    path that did not.

    `exclude_path` is stronger than a glob filter: lychee.toml's own header records
    that it voids even an EXPLICIT invocation, and scripts/pre-publish.sh passes the
    rendered path explicitly. So a stale entry here silently flips what the
    rendered-link-liveness gate covers, with nothing asserting it either way.

    Scoped to the exclude_path LINE. The AC's whole-file counts (public/blogs 1,
    content/posts 1) cannot hold in a file whose convention is to explain every
    exclusion in prose above it: any comment naming a path inflates them. The
    `public/posts` half IS asserted file-wide, because there the count is 0 and a
    mention anywhere would be stale documentation.
    """
    lychee = ROOT / "lychee.toml"
    if not lychee.is_file():
        failures.append("AC 5.16: lychee.toml does not exist")
        return
    text = lychee.read_text(encoding="utf-8")
    if "public/posts" in text:
        failures.append("AC 5.16: lychee.toml still mentions the retired built path "
                        "`public/posts` (the rendered output moved to public/blogs)")
    line = next((ln for ln in text.splitlines() if ln.startswith("exclude_path")), None)
    if line is None:
        failures.append("AC 5.16: lychee.toml has no exclude_path line")
        return
    if "public/blogs" not in line:
        failures.append("AC 5.16: exclude_path does not exclude the built output at "
                        "public/blogs, so pre-publish.sh's rendered-link check changes "
                        "scope silently")
    if "content/posts" not in line:
        failures.append("AC 5.16: exclude_path lost `content/posts`. Content directories "
                        "did NOT move; dropping it re-enables raw-markdown link checking "
                        "over the voice-sacred legacy corpus")


_RETIRED_BUILT_PATH = "public/posts"

# Every tracked line outside this file that may mention the retired built path, pinned
# as (path, exact stripped text). A mention not listed here FAILS, whatever it says.
#
# THIS IS A PIN, NOT A HEURISTIC, AND THAT IS THE POINT. Three consecutive Ralph rounds
# broke the heuristic versions of this check, each time with ordinary English rather
# than an adversarial string:
#
#   round 6  no check at all - AC 5.16's second clause was never delivered
#   round 7  marker anywhere on the LINE exempted it:
#            "The sidebar layout was redesigned before. public/posts still hosts ..."
#   round 8  marker anywhere in the CLAUSE exempted it, where "clause" split only on
#            . and ; - so a comma or a coordinating conjunction defeated it:
#            "public/posts was the old build directory but public/posts still serves
#             the rendered blog today."
#            and the bare substring "moved" matched inside "unmoved" / "removed":
#            "public/posts is the unmoved directory that still serves the blog."
#
# Each fix was a narrower guess at what "framed as history" reads like, and each was
# beaten by a sentence one punctuation mark away from the last counterexample. Deciding
# authorial INTENT from prose is not a thing a grep can do, and every further refinement
# is another round of the same game. So it stops being a judgement: the allowed lines
# are enumerated, and anything else is a failure a human re-reads.
#
# Adding a legitimate new historical mention means adding it here. That friction IS the
# control - it forces the one re-read that would have caught the original AC 5.16 miss.
# Matching the `_EXPECTED_LABELLED_LINES` pinned-exemption idiom already used above.
_ALLOWED_RETIRED_MENTIONS = {
    ("docs/AUTHORING.md",
     "**Neither link tier checks a post.** `lychee.toml` `exclude_path` contains "
     "**both** `public/blogs` and `content/posts`, so for a post target the rendered "
     "tier and the CI markdown tier each report `0 Total` and pass without checking "
     "anything. (`public/blogs` is the BUILT path; blog-priv#62 moved the rendered "
     "output there from `public/posts`. `content/posts` is the source path and did not "
     "move.) Measured: a post returns 0 links on both tiers, a consulting page returns "
     "37 on the rendered tier. The exclusions are deliberate and predate blog-priv#55, "
     "so **the links in a new post must be checked by hand** before you publish. Do not "
     "read a green pre-publish run as evidence that a post's links resolve. The same "
     "caveat is restated in the `CAVEAT:` paragraph of the gate-8 entry in "
     "`scripts/pre-publish.sh`'s header block (same substance, different wording, so "
     "check both when either changes)."),
    ("docs/consulting-launch-checklist.md",
     "`scripts/pre-publish.sh` check `consulting-link-liveness` runs `lychee` against "
     "`public/hire-hoi/ai-consultancy/**/index.html` post-Hugo-build. A "
     "`cal.com/OPERATOR_TODO_REPLACE_BEFORE_LAUNCH/20min-discovery` URL would 404 and "
     "fail this gate. The `lychee.toml` `exclude_path` was tightened from `public` to "
     "the blog's built output alone so consulting paths are reachable. That entry is "
     "now `public/blogs` (blog-priv#62 moved the rendered blog there; it read "
     "`public/posts` before)."),
}


# Every sentence that defeated a HEURISTIC version of this guard, kept as fixtures. The
# pin cannot be fooled by phrasing - membership is exact-text equality - so these can
# only start passing if someone reintroduces prose-sniffing or widens the allowlist to
# something generic. That is the regression worth catching: this is what stops a fourth
# heuristic quietly growing back. Each is a real Ralph counterexample, not an invented one.
_REJECTED_MENTION_CASES = (
    ("The sidebar layout was redesigned before. public/posts still hosts the canonical "
     "built blog output today.",
     "round 7: unrelated historical clause, separate current-tense claim"),
    ("public/posts was the old build directory but public/posts still serves the "
     "rendered blog today.",
     "round 8: clauses joined by a conjunction, never split on . or ;"),
    ("public/posts is the unmoved directory that still serves the rendered blog output.",
     "round 8: bare substring 'moved' matching inside 'unmoved'"),
    ("exclude_path contains public/posts and public/blogs.",
     "names both paths as current - defeats a 'must also name public/blogs' rule"),
    ("public/posts is where the rendered blog lives.",
     "the plainest possible stale claim"),
)


def check_pin_rejects_known_escapes(failures: list[str]) -> None:
    """Every sentence that beat a previous version of this guard must still be rejected.

    Membership is exact-text equality, so the only way one of these passes is if the
    allowlist grew to include it - which is what a slide back toward prose-sniffing
    would look like.
    """
    allowed_bodies = {body for _, body in _ALLOWED_RETIRED_MENTIONS}
    for body, why in _REJECTED_MENTION_CASES:
        if body.strip() in allowed_bodies:
            failures.append(
                f"AC 5.16: a known escape is now in _ALLOWED_RETIRED_MENTIONS: {body!r} "
                f"({why}). The pin must never list a sentence stating the retired path "
                f"as current."
            )


def check_no_stale_lychee_claims(failures: list[str]) -> None:
    """AC 5.16 second half - the `/posts/` sweep WIDENED past scripts/ and .github/.

    `check_lychee_exclude` above reads lychee.toml and nothing else, so it proves the
    CONFIG is right while every file that DESCRIBES that config can still be wrong.
    That is exactly what happened: commit 081508f flipped exclude_path to public/blogs
    and left three tracked files telling the reader it contains `public/posts` -
    docs/AUTHORING.md, docs/consulting-launch-checklist.md and this repo's own
    scripts/pre-publish.sh header. All three were false on a tree where the AC was
    ticked, and two of them had a DIFFERENT occurrence updated by the same diff.

    This is the third instance in blog-priv#62 of one class: a file with zero diff
    lines is invalidated by a change elsewhere (layouts/_default/single.html and
    scripts/social-cards/README.md were the first two). A gate that reads only the
    thing that changed cannot see it. So this one reads everything that mentions it.

    The rule is an EXACT-TEXT PIN (`_ALLOWED_RETIRED_MENTIONS`), not a prose heuristic.
    Three rounds of trying to read authorial intent out of a sentence each got beaten by
    ordinary English; the reasoning is recorded at the pin. A mention survives only by
    being enumerated, which keeps the AP #28 reversal record - saying what the value USED
    to be is how a future reader learns the move happened - while making a newly-added
    stale sentence fail regardless of how it is phrased.
    """
    import subprocess
    try:
        out = subprocess.run(["git", "grep", "-n", "public/posts", "--", "."],
                             cwd=ROOT, capture_output=True, text=True, check=False)
    except OSError as exc:                       # git missing - fail loud, never skip
        failures.append(f"AC 5.16: could not run `git grep` to sweep for stale "
                        f"`public/posts` claims: {exc}")
        return
    if out.returncode not in (0, 1):             # 1 = no matches, which is fine
        failures.append(f"AC 5.16: `git grep` failed (rc={out.returncode}): "
                        f"{out.stderr.strip()}")
        return

    self_name = Path(__file__).name
    for hit in out.stdout.splitlines():
        path, _, rest = hit.partition(":")
        lineno, _, body = rest.partition(":")
        if path.startswith("public/") or Path(path).name == self_name:
            continue                             # the build tree, and this guard itself
        if (path, body.strip()) in _ALLOWED_RETIRED_MENTIONS:
            continue                             # pinned, already re-read by a human
        failures.append(
            f"AC 5.16: {path}:{lineno} mentions the retired built path `public/posts` "
            f"and is not pinned. The rendered blog moved to public/blogs, so a "
            f"current-tense claim here is false. Either correct the line, or - if it is "
            f"genuinely a historical note - add it verbatim to "
            f"_ALLOWED_RETIRED_MENTIONS in {Path(__file__).name}. Adding the pin is the "
            f"re-read this guard exists to force; do not widen it to a pattern."
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
    check_permalink_token(failures)
    check_authoring_doc(failures)
    check_lychee_exclude(failures)
    check_pin_rejects_known_escapes(failures)
    check_no_stale_lychee_claims(failures)
    if not built.is_dir():
        failures.append(f"AC 5.2: built site not found at {built} (run `hugo` first)")
    else:
        retired = read_baseline()
        live = sitemap_paths(built)
        check_mapping(retired, live, failures)
        check_sitemap_clean(live, failures)
        check_no_retired_links(built, failures)

    if failures:
        print(f"FAIL: {len(failures)} permalink-contract violation(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("OK: 87 retired URLs map 1:1 onto live /blogs/ URLs under two disjoint "
          "rules (80 replacement + 7 insertion), zero unmapped, no retired first "
          "segment survives in the sitemap, and no rendered page links to one")
    return 0


def test_permalink_contract() -> None:
    """pytest entry point (CI runs pytest through explicit file lists)."""
    assert main([]) == 0


if __name__ == "__main__":
    sys.exit(main())
