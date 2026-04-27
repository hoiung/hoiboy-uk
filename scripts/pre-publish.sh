#!/bin/bash
# Pre-publish gate aggregator for hoiboy.uk new blog posts.
#
# Runs seven sequential checks fail-fast on first non-zero exit:
#   1. Em-dash grep      (any U+2014 = fail)
#   2. Voice tells       (check-ai-writing-tells.py --check-only-new)
#   3. Frontmatter       (validate_frontmatter.py — whole-tree)
#   4. Word count        (check_wordcount.py >3000 = fail)
#   5. Private leaks     (check-public-repo-secrets.py)
#   6. Hugo build        (hugo --buildDrafts so cross-link resolution + permalinks
#                         match production exactly; rendered HTML lands in public/)
#   7. Rendered links    (lychee on `public/posts/<slug>/index.html` NOT raw .md
#                         — catches broken cross-section links + missing assets
#                         that markdown-only lychee cannot see)
#
# Checks 6+7 added per dotfiles Issue #447 Phase 7 (AP #18 per-shape recipe
# for the Static-blog shape). Lighthouse-CI deliberately OUT OF SCOPE — no
# perf-budget need yet, would add puppeteer/headless-Chrome overhead.
#
# Bash (not strict POSIX sh) for `set -o pipefail`.
#
# Usage:
#   bash scripts/pre-publish.sh content/posts/<slug>/             # page bundle dir
#   bash scripts/pre-publish.sh content/posts/<slug>/index.md     # single file
#
# Tracker: private bake-off teaser issue (Phase 1 infra).
# Exit codes: 0 = all checks pass; non-zero = first failing check's exit code.

set -euo pipefail

if [ "$#" -ne 1 ]; then
    printf >&2 'usage: %s <post-path-or-bundle-dir>\n' "$0"
    exit 2
fi

TARGET="$1"
if [ ! -e "$TARGET" ]; then
    printf >&2 'ERR: target does not exist: %s\n' "$TARGET"
    exit 2
fi

# Resolve POST_FILE for word-count (which expects a file, not a dir).
if [ -d "$TARGET" ]; then
    POST_FILE="$TARGET/index.md"
    if [ ! -f "$POST_FILE" ]; then
        printf >&2 'ERR: page bundle missing index.md: %s\n' "$POST_FILE"
        exit 2
    fi
else
    POST_FILE="$TARGET"
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

declare -a results=()

run_check() {
    local label="$1"
    shift
    printf '[RUN ] %s\n' "$label"
    if "$@"; then
        printf '[PASS] %s\n' "$label"
        results+=("PASS  $label")
    else
        local rc=$?
        printf >&2 '[FAIL] %s (exit %d)\n' "$label" "$rc"
        results+=("FAIL  $label (exit $rc)")
        print_summary
        exit "$rc"
    fi
}

print_summary() {
    printf '\n----- pre-publish summary -----\n'
    for line in "${results[@]}"; do
        printf '  %s\n' "$line"
    done
    printf '%s\n' '-------------------------------'
}

# 1. Em-dash grep (recurses into directory; fails if any U+2014 found).
EM_DASH=$'\xe2\x80\x94'
em_dash_check() {
    if grep -rn "$EM_DASH" "$TARGET" >/dev/null 2>&1; then
        printf >&2 '  Em dashes found in %s:\n' "$TARGET"
        grep -rn "$EM_DASH" "$TARGET" >&2 || true
        return 1
    fi
    return 0
}
run_check "em-dash-zero" em_dash_check

# 2. Voice tells (marker-driven; default skip; exit 0 = clean).
run_check "voice-tells" python3 scripts/check-ai-writing-tells.py --check-only-new "$TARGET"

# 3. Frontmatter validator (walks content/posts/ unconditionally).
run_check "frontmatter" python3 scripts/validate_frontmatter.py

# 4. Word count ceiling (>3000 fails; legacy + grandfathered skipped).
run_check "wordcount" python3 scripts/check_wordcount.py "$POST_FILE"

# 5. Private blocklist + secrets (PLATFORM_TOKEN + PRIVATE_PATH + BLOCKLIST).
run_check "secrets" python3 scripts/check-public-repo-secrets.py "$TARGET"

# 6. Hugo build with --buildDrafts so the rendered HTML in public/ matches
#    what production will serve (excluding the auto-deploy gate). Builds ALL
#    drafts so cross-links to in-progress posts resolve.
hugo_build() {
    rm -rf public
    hugo --buildDrafts --minify --quiet
    [[ -d public ]] || { printf >&2 'ERR: hugo build did not produce public/\n'; return 1; }
}
run_check "hugo-build" hugo_build

# 7. Lychee on rendered HTML — catches broken cross-section links + missing
#    assets that markdown-only lychee misses (e.g. a `[link](../other-section/)`
#    that resolves under Hugo's permalink scheme but not under raw-md walk).
rendered_link_check() {
    local slug rendered
    if [ -d "$TARGET" ]; then
        slug=$(basename "$TARGET")
    else
        slug=$(basename "$(dirname "$TARGET")")
    fi
    rendered="public/posts/$slug/index.html"
    if [[ ! -f "$rendered" ]]; then
        printf >&2 'WARN: rendered HTML not at %s — looking for any matching slug\n' "$rendered"
        rendered=$(find public -path "*/$slug/index.html" -type f 2>/dev/null | head -n1)
        [[ -z "$rendered" ]] && { printf >&2 'ERR: cannot locate rendered HTML for slug %s\n' "$slug"; return 1; }
    fi
    if ! command -v lychee >/dev/null 2>&1; then
        printf >&2 'ERR: lychee not installed; install via cargo or apt\n'
        return 127
    fi
    lychee --config lychee.toml --no-progress "$rendered"
}
run_check "rendered-link-liveness" rendered_link_check

print_summary
printf '[OK] all 7 pre-publish checks passed for %s\n' "$TARGET"
