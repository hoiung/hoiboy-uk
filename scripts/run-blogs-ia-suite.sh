#!/usr/bin/env bash
# Run the Blogs IA suite as a pre-push gate (#55 AC 2.1-2.3).
#
# Until #55 this suite ran ONLY in ci.yml's "Blogs IA tests" step, so a broken
# URL contract, a missing redirect, or a hub-listing regression was found by red
# CI on main -- after the push, on the shared branch. The same tests run here
# before the push can land, which is the whole point: the author learns from
# their own terminal instead of from a broken main.
#
# The test list is NOT hardcoded here. It is passed in as arguments by the
# `blogs-ia-suite` hook in .pre-commit-config.yaml, so the hook entry names every
# file (AC 2.1 half (b)) and there is exactly one place per caller to edit.
# scripts/test_run_blogs_ia_suite.py asserts that list stays identical to the one
# in ci.yml -- two callers naming two different suites is the drift this gate
# would otherwise invite.
#
# Exit codes:
#   0 = every test passed
#   1 = a test failed, or the ./public precondition is unmet
#   2 = usage error (no test files passed)

set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT" || exit 2

if [[ $# -eq 0 ]]; then
    printf >&2 'ERR: no test files passed. Usage: %s <test_file.py> [...]\n' "$0"
    exit 2
fi

BUILD_CMD='hugo --gc --minify -e production'

# Measured 2026-08-02 by parking ./public and running each file: these 8 FAIL
# without a built tree; scripts/test_redirects_order.py and
# scripts/test_emdash_hub_coverage.py pass without one (they read content/ and
# config/ only). Stated explicitly because AC 2.3 requires the gate to say WHICH
# tests need the tree, rather than emitting a stack trace and leaving the author
# to work it out from a traceback.
NEEDS_PUBLIC=(
    scripts/test_permalink_contract.py
    scripts/test_redirects_coverage.py
    scripts/test_hub_listing.py
    scripts/test_page_url_permalinks.py
    scripts/test_section_keyed_regression.py
    scripts/test_taxonomy_cleanup.py
    scripts/readnext_parse.py
    scripts/test_related_ranking.py
    tests/test_taxonomy_terms_match_build.py
)

explain_public() {
    # $1 = the headline problem
    printf >&2 '\n%s\n\n' "$1"
    printf >&2 'These %d of the Blogs IA tests read the BUILT site, not the sources:\n' "${#NEEDS_PUBLIC[@]}"
    printf >&2 '  %s\n' "${NEEDS_PUBLIC[@]}"
    printf >&2 '\nRun this, then push again:\n\n    %s\n\n' "$BUILD_CMD"
}

if [[ ! -d public ]]; then
    explain_public "ERR: the Blogs IA suite needs a built ./public tree and there isn't one."
    exit 1
fi

if [[ ! -f public/index.html ]]; then
    explain_public "ERR: ./public exists but holds no index.html, so it is not a completed Hugo build."
    exit 1
fi

# Staleness. A tree built before the most recent source edit makes every one of
# the tests above assert against output that no longer corresponds to the
# sources being pushed -- they pass, and prove nothing about this push.
#
# share-card.* is excluded deliberately. scripts/pre-publish.sh REGENERATES those
# PNGs on every run (and `git checkout --` to revert them bumps the mtime again),
# so an author who follows docs/AUTHORING.md and runs pre-publish.sh before
# pushing would trip a STALE failure caused entirely by a generated artifact.
# A gate that fires on the workflow it is documented alongside gets bypassed with
# SKIP=, which is worse than not having it. Excluding them costs nothing here:
# these 8 tests assert URL structure, redirects, hub listing and taxonomy from
# rendered HTML, none of which depends on card image bytes. Card freshness is
# gate 6c's job (scripts/check_social_cards.py --built), not this suite's.
#
# SOURCE ROOTS (#55 Stage 5): Hugo reads SIX roots, and this scan originally named
# four. `data/` is live -- layouts/_shortcodes/consulting-cta.html reads
# `hugo.Data.consulting` -- and `static/` holds _redirects, which
# scripts/test_redirects_coverage.py asserts against the BUILT tree. Editing
# either and pushing without a rebuild passed the scan and tested a stale build.
#
# CONTENT STAMP (#55 Stage 5): mtime alone is not a proxy for "edited". Running
# this hook through pre-commit rewrites unrelated working-tree files, bumping their
# mtimes with byte-identical content, so a PASS invalidated its own precondition
# and the very next run reported STALE on an unchanged tree -- measured three times.
# Since pre-publish.sh always leaves an unstaged regenerated share-card.png, the
# documented author workflow reliably produced it, and the fix for that is the same
# SKIP= bypass the comment above calls worse than no gate at all.
# So: mtime stays the cheap first signal, but a mtime hit is only STALE if the
# source CONTENT also differs from what was verified against this build. The stamp
# is written only after a genuine pass, so `hash == stamp` means "public/ was
# already confirmed current for exactly these bytes". 698 files, ~0.17s.
SRC_ROOTS=(content layouts config assets data static)
STAMP=public/.blogs-ia-srchash

src_hash() {
    find "${SRC_ROOTS[@]}" -type f ! -name 'share-card.*' -print0 2>/dev/null \
        | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1
}

current_hash=$(src_hash)
newest_src=$(find "${SRC_ROOTS[@]}" -type f \
    ! -name 'share-card.*' -newer public/index.html -print -quit 2>/dev/null)
if [[ -n "$newest_src" ]]; then
    if [[ -f $STAMP ]] && [[ "$(cat "$STAMP")" == "$current_hash" ]]; then
        printf 'Blogs IA suite: %s is newer than the build, but source content is byte-identical to the last verified build (stamp match) -- not stale.\n' \
            "$newest_src"
    else
        explain_public "ERR: ./public is STALE -- $newest_src is newer than public/index.html."
        exit 1
    fi
fi
printf '%s\n' "$current_hash" > "$STAMP"

printf 'Blogs IA suite: %d test files, ./public built and current.\n' "$#"
python3 -m pytest "$@" -q
rc=$?

if (( rc != 0 )); then
    printf >&2 '\nBlogs IA suite FAILED (pytest exit %d). This gate runs pre-push so the\n' "$rc"
    printf >&2 'failure lands in your terminal rather than as red CI on main. Fix it, or\n'
    printf >&2 'bypass deliberately with: SKIP=blogs-ia-suite git push\n'
fi
exit $rc
