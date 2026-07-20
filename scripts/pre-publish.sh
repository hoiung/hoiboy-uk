#!/bin/bash
# Pre-publish gate aggregator for hoiboy.uk new blog posts.
#
# Runs 14 sequential gates fail-fast on first non-zero exit:
#   1. Consulting YAML   (data/consulting.yaml MUST NOT contain OPERATOR_TODO
#                         substring — global gate, blocks publish whenever a
#                         placeholder URL is unreplaced. consulting-ops#2 AC 0.2.)
#   2. Em-dash grep      (any U+2014 = fail)
#   3. Voice tells       (check-ai-writing-tells.py --check-only-new)
#   4. Frontmatter       (validate_frontmatter.py, whole-tree: content/posts/
#                         plus content/consulting/)
#   4a.Project pages     (validate_frontmatter.py --scope consulting, reported
#                         as its own named gate so a project-page failure is
#                         attributable without reading the whole-tree output.
#                         `description` is REQUIRED on both trees since
#                         blog-priv#55 Phase 2.)
#   4b.Future date       (check_future_date.py — fail if date is future in the
#                         site timeZone vs now-UTC; Hugo would silently drop a
#                         future-dated post from the production build)
#   4c.Social cards      (check_social_cards.py, source: every singular indexable
#                         page owns its og:image card)
#   5. Word count        (check_wordcount.py >3000 = fail. POSTS ONLY: this gate
#                         SKIPs for consulting/legal/skills/private targets, so a
#                         non-post run reports 13 PASS + 1 SKIP, not 14 PASS.)
#   6. Private leaks     (check-public-repo-secrets.py)
#   6b.SVG dimensions    (check_svg_dimensions.py)
#   7. Hugo build        (hugo --buildDrafts so cross-link resolution + permalinks
#                         match production exactly; rendered HTML lands in public/)
#   7a.Social cards      (check_social_cards.py --built public: rendered backstop
#                         for a head.html/hero-pick template regression)
#   8. Rendered links    (lychee on rendered HTML NOT raw .md — catches broken
#                         cross-section links + missing assets that markdown-only
#                         lychee cannot see; covers public/posts/<slug>/ AND
#                         public/consulting/<slug>/ per AC 0.4.)
#   8a.Consulting links  (consulting_link_check: live external-URL liveness)
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

# 1. Consulting YAML guard — blocks publish if any OPERATOR_TODO_REPLACE_BEFORE_LAUNCH
#    placeholder is still in data/consulting.yaml. Defence-in-depth alongside the
#    pre-commit hook + Hugo shortcode mailto fallback. consulting-ops#2 AC 0.2.
consulting_yaml_check() {
    local yaml="data/consulting.yaml"
    if [ ! -f "$yaml" ]; then
        return 0
    fi
    if grep -F 'OPERATOR_TODO' "$yaml" >/dev/null 2>&1; then
        printf >&2 '  consulting.yaml contains OPERATOR_TODO placeholder; refusing to publish\n'
        grep -nF 'OPERATOR_TODO' "$yaml" >&2 || true
        return 1
    fi
    return 0
}
run_check "consulting-yaml-no-operator-todo" consulting_yaml_check

# 2. Em-dash grep (recurses into directory; fails if any U+2014 found).
# -I skips binary files: this is a PROSE check, and a binary image can contain
# the U+2014 byte sequence (0xE2 0x80 0x94) by chance (e.g. a DSLR JPEG), which
# is a false positive. Text files (.md, .svg) are still scanned.
EM_DASH=$'\xe2\x80\x94'
em_dash_check() {
    if grep -rnI "$EM_DASH" "$TARGET" >/dev/null 2>&1; then
        printf >&2 '  Em dashes found in %s:\n' "$TARGET"
        grep -rnI "$EM_DASH" "$TARGET" >&2 || true
        return 1
    fi
    return 0
}
run_check "em-dash-zero" em_dash_check

# 2. Voice tells (marker-driven; default skip; exit 0 = clean).
run_check "voice-tells" python3 scripts/check-ai-writing-tells.py --check-only-new "$TARGET"

# 3. Frontmatter validator (walks content/posts/ AND content/consulting/).
run_check "frontmatter" python3 scripts/validate_frontmatter.py

# 3-project. Same validator, project-page scope, reported as its own named gate
#     so a failure on a consulting/portfolio page is attributable at a glance
#     instead of being buried in the whole-tree result. Mirrors how the
#     social-card guard is wired twice (source at 3a, rendered at 7a).
#     `description` is REQUIRED here: without it a project page inherits the
#     site-default meta description and becomes a near-duplicate that answer
#     engines cannot tell apart (blog-priv#55 AC 2.3/2.6).
run_check "frontmatter-project-pages" python3 scripts/validate_frontmatter.py --scope consulting

# 3a. Social-card guard (whole-tree): every singular indexable page must be a
#     leaf bundle that owns its share-card / hero, else it silently falls back to
#     the default card in link previews. See scripts/check_social_cards.py (#52).
run_check "social-cards" python3 scripts/check_social_cards.py

# 3b. Future-date guard. Hugo drops future-dated posts from the production
#     build (buildFuture off) and Cloudflare builds in UTC, so a post-dated
#     entry silently vanishes from the live site + all listings. Fail if this
#     post's date (read in the site timeZone from hugo.toml) is still in the
#     future relative to now (UTC). See docs/AUTHORING.md section 2.
run_check "no-future-date" python3 scripts/check_future_date.py "$TARGET"

# 4. Word count ceiling (>3000 fails; legacy + grandfathered skipped).
#    POSTS ONLY. Consulting / legal / skills / private landing pages are
#    long-form by design and are NOT gated. This matches the pre-commit hook
#    (files: ^content/posts/.*/index\.md$) and CI (git ls-files content/posts/*),
#    both already posts-scoped; pre-publish was the only caller that leaked.
case "$POST_FILE" in
    content/posts/*/index.md|*/content/posts/*/index.md)
        run_check "wordcount" python3 scripts/check_wordcount.py "$POST_FILE"
        ;;
    *)
        printf '[SKIP] wordcount (not a blog post: %s)\n' "$POST_FILE"
        results+=("SKIP  wordcount (non-post)")
        ;;
esac

# 5. Private blocklist + secrets (PLATFORM_TOKEN + PRIVATE_PATH + BLOCKLIST).
run_check "secrets" python3 scripts/check-public-repo-secrets.py "$TARGET"

# 5b. SVG dimensions: every page-bundle SVG needs root width/height or it renders
#     tiny in the glightbox lightbox (zoom-image shortcode). See check_svg_dimensions.py.
run_check "svg-dimensions" python3 scripts/check_svg_dimensions.py "$TARGET"

# 6. Hugo build with --buildDrafts so the rendered HTML in public/ matches
#    what production will serve (excluding the auto-deploy gate). Builds ALL
#    drafts so cross-links to in-progress posts resolve.
hugo_build() {
    rm -rf public
    hugo --buildDrafts --minify --quiet
    [[ -d public ]] || { printf >&2 'ERR: hugo build did not produce public/\n'; return 1; }
}
run_check "hugo-build" hugo_build

# 6a. Rendered social-card backstop: assert each singular indexable page's RENDERED
#     og:image is its own card, not the site default. Catches a head.html/hero-pick
#     template regression the source-only guard (check #3a) cannot see (#52 Stage 5).
run_check "social-cards-rendered" python3 scripts/check_social_cards.py --built public

# 7. Lychee on rendered HTML — catches broken cross-section links + missing
#    assets that markdown-only lychee misses (e.g. a `[link](../other-section/)`
#    that resolves under Hugo's permalink scheme but not under raw-md walk).
rendered_link_check() {
    local slug rendered fm_slug
    if [ -d "$TARGET" ]; then
        slug=$(basename "$TARGET")
    else
        slug=$(basename "$(dirname "$TARGET")")
    fi
    # A frontmatter `slug:` overrides the directory name in Hugo's permalink,
    # so the rendered path is public/posts/<frontmatter-slug>/, NOT the bundle
    # dir. Without this, every post carrying an override fails the gate: as of
    # 2026-07-20 that is 2 of 78 (2026-04-07-foundation -> foundation,
    # ai-jargon-for-noobs -> ai-jargon-for-newbies). Read from the closing ---
    # onward only, so a `slug:` mentioned in body prose cannot hijack it.
    fm_slug=$(awk 'NR==1 && /^---/ {f=1; next} f && /^---/ {exit} f' "$POST_FILE" \
        | sed -n 's/^slug:[[:space:]]*//p' | head -n1 | tr -d '"'"'" | tr -d '[:space:]')
    [[ -n "$fm_slug" ]] && slug="$fm_slug"
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
    lychee --config lychee.toml --root-dir "$REPO_ROOT/public" --no-progress "$rendered"
}
run_check "rendered-link-liveness" rendered_link_check

# 8b. Lychee on rendered consulting pages — when public/consulting/*/index.html
#     exists post-Hugo-build, every external URL in those rendered pages is
#     verified live. This is what catches a stale cal.com/OPERATOR_TODO/...
#     URL slipping through (the OPERATOR_TODO yaml gate at check #1 is the
#     primary defence; this is defence-in-depth at the rendered-HTML layer).
#     consulting-ops#2 AC 0.4.
consulting_link_check() {
    if [ ! -d "public/consulting" ]; then
        printf '  no public/consulting/ directory in build output; skipping consulting-link-liveness\n'
        return 0
    fi
    local rendered
    rendered=$(find public/consulting -path '*/index.html' -type f 2>/dev/null)
    if [ -z "$rendered" ]; then
        printf '  no rendered consulting pages found; skipping\n'
        return 0
    fi
    if ! command -v lychee >/dev/null 2>&1; then
        printf >&2 'ERR: lychee not installed; install via cargo or apt\n'
        return 127
    fi
    # shellcheck disable=SC2086
    lychee --config lychee.toml --root-dir "$REPO_ROOT/public" --no-progress $rendered
}
run_check "consulting-link-liveness" consulting_link_check

print_summary
# Report PASS and SKIP separately. Counting the array length folded a skipped
# gate into "passed", so a consulting target read as "all 14 passed" when the
# posts-only wordcount gate had in fact been skipped.
pass_n=$(printf '%s\n' "${results[@]}" | grep -c '^PASS' || true)
skip_n=$(printf '%s\n' "${results[@]}" | grep -c '^SKIP' || true)
if [ "$skip_n" -gt 0 ]; then
    printf '[OK] %d pre-publish gates passed, %d skipped (not applicable) for %s\n' \
        "$pass_n" "$skip_n" "$TARGET"
else
    printf '[OK] all %d pre-publish gates passed for %s\n' "$pass_n" "$TARGET"
fi
