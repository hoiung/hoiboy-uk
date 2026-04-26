#!/bin/bash
# Pre-publish gate aggregator for hoiboy.uk new blog posts.
#
# Runs five sequential checks fail-fast on first non-zero exit:
#   1. Em-dash grep   (any U+2014 = fail)
#   2. Voice tells    (check-ai-writing-tells.py --check-only-new)
#   3. Frontmatter    (validate_frontmatter.py — whole-tree)
#   4. Word count     (check_wordcount.py >3000 = fail)
#   5. Private leaks  (check-public-repo-secrets.py)
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

print_summary
printf '[OK] all 5 pre-publish checks passed for %s\n' "$TARGET"
