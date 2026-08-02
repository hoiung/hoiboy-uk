#!/bin/bash
# Pre-publish gate aggregator for hoiboy.uk new blog posts.
#
# Runs 17 sequential gates fail-fast on first non-zero exit:
#   1. Consulting YAML   (data/consulting.yaml MUST NOT contain OPERATOR_TODO
#                         substring — global gate, blocks publish whenever a
#                         placeholder URL is unreplaced. consulting-ops#2 AC 0.2.)
#   2. Em-dash grep      (any U+2014 = fail)
#   3. Voice tells       (check-ai-writing-tells.py --check-only-new)
#   4. Frontmatter       (validate_frontmatter.py --scope posts)
#   4a.Project pages     (validate_frontmatter.py --scope consulting)
#                         4 and 4a are DISJOINT on purpose, and their union is
#                         exactly the whole tree. They used to be nested (4 ran
#                         the whole tree, 4a re-ran a subset of it), which made
#                         4a unable to fail independently AND unreachable in
#                         the one case it existed for: run_check exits on the
#                         first failure, so a project-page fault failed at gate
#                         4 and gate 4a never printed. Disjoint scopes give the
#                         attribution the nested pair only claimed to give.
#                         `description` is REQUIRED on both trees since
#                         blog-priv#55 Phase 2.
#   4b.Social cards      (check_social_cards.py, source: every singular indexable
#                         page owns its og:image card)
#   4c.Future date       (check_future_date.py — fail if date is future in the
#                         site timeZone vs now-UTC; Hugo would silently drop a
#                         future-dated post from the production build)
#   5. Word count        (check_wordcount.py >3000 = fail. POSTS ONLY: this gate
#                         SKIPs for consulting/legal/skills/private targets, so a
#                         non-post run reports 16 PASS + 1 SKIP, not 17 PASS.)
#   6. Private leaks     (check-public-repo-secrets.py)
#   6b.SVG dimensions    (check_svg_dimensions.py)
#   6c.Social cards      (gen-social-cards.sh — the AC 3.0 two-pass card build:
#                         build, regenerate every card from its page's trail,
#                         rebuild, then check_social_cards.py --strict)
#   7. Hugo build        (hugo --buildDrafts so cross-link resolution + permalinks
#                         match production exactly; rendered HTML lands in public/)
#   7a.Social cards      (check_social_cards.py --built public: rendered backstop
#                         for a head.html/hero-pick template regression)
#   7b.404 gate          (test_404.py --built public: root 404.html emitted, its
#                         content block rendered, it went through the baseof
#                         shell, its own escape links resolve, and static/_headers
#                         keeps /404* out of the index. blog-priv#64.)
#   7c.CTA rendered      (check_cta_rendered.py --built public: the browser's
#                         COMPUTED fill, label colour and text-decoration for the
#                         discovery-call button, in both colour schemes. This is
#                         the only lane with Chromium, which is why the gate lives
#                         here and not in CI. blog-priv#63.)
#   8. Rendered links    (lychee on rendered HTML NOT raw .md — catches broken
#                         cross-section links + missing assets that markdown-only
#                         lychee cannot see. This is the ONLY tier that checks a
#                         post's links: "content/posts" stays in lychee.toml
#                         exclude_path, so CI's markdown-level lychee reports
#                         0 Total for a post by design. "public/blogs" was in
#                         exclude_path too until #55, which meant this gate ALSO
#                         checked zero links and still reported PASS for every
#                         post: exclude_path voids even the explicit path passed
#                         below. It now carries a zero-item floor: 0 links is a
#                         FAILURE, not a pass, because a gate that examines
#                         nothing must never report success.)
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
    # Fail loud on absence (#55 Stage 5). This used to `return 0`, and the identical
    # shape is mirrored in .pre-commit-config.yaml and .github/workflows/ci.yml -- so
    # renaming or moving this file turned all THREE tiers green simultaneously and an
    # OPERATOR_TODO placeholder could ship. The file is tracked, so its absence is a
    # defect, never a normal state: a "guard" that passes when its subject is missing
    # is the vacuous-pass class this Issue exists to close.
    if [ ! -f "$yaml" ]; then
        printf >&2 '  %s is missing. It is tracked, so this is a rename/deletion, not a normal state -- and this guard, its pre-commit twin and its ci.yml twin would all pass silently on it. Restore the file or update all three call sites together.\n' "$yaml"
        return 1
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

# 3. Voice tells (marker-driven; default skip; exit 0 = clean).
run_check "voice-tells" python3 scripts/check-ai-writing-tells.py --check-only-new "$TARGET"

# 4. Frontmatter validator, POSTS scope. Disjoint from 4a below; see the header.
run_check "frontmatter" python3 scripts/validate_frontmatter.py --scope posts

# 4a. Same validator, project-page scope. Disjoint from gate 4, so a failure
#     here names the consulting/portfolio tree directly rather than being
#     buried in a whole-tree result. This pair is NOT the same shape as the
#     social-card guard at 4b/7a: that one deliberately checks the SAME set
#     twice at two different layers (source, then rendered), which is real
#     defence in depth. Two nested checks of the same set at the SAME layer
#     would be redundancy, not depth, which is what 4/4a used to be.
#     `description` is REQUIRED here: without it a project page inherits the
#     site-default meta description and ships as a near-duplicate
#     (blog-priv#55 AC 2.3/2.6). SEO hygiene, not a GEO lever.
run_check "frontmatter-project-pages" python3 scripts/validate_frontmatter.py --scope consulting

# 4b. Social-card guard (whole-tree): every singular indexable page must be a
#     leaf bundle that owns its share-card / hero, else it silently falls back to
#     the default card in link previews. See scripts/check_social_cards.py (#52).
run_check "social-cards" python3 scripts/check_social_cards.py

# 4c. Future-date guard. Hugo drops future-dated posts from the production
#     build (buildFuture off) and Cloudflare builds in UTC, so a post-dated
#     entry silently vanishes from the live site + all listings. Fail if this
#     post's date (read in the site timeZone from hugo.toml) is still in the
#     future relative to now (UTC). See docs/AUTHORING.md section 2.
run_check "no-future-date" python3 scripts/check_future_date.py "$TARGET"

# 5. Word count ceiling (>3000 fails; legacy + grandfathered skipped).
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

# 6. Private blocklist + secrets (PLATFORM_TOKEN + PRIVATE_PATH + BLOCKLIST).
run_check "secrets" python3 scripts/check-public-repo-secrets.py "$TARGET"

# 6b. SVG dimensions: every page-bundle SVG needs root width/height or it renders
#     tiny in the glightbox lightbox (zoom-image shortcode). See check_svg_dimensions.py.
run_check "svg-dimensions" python3 scripts/check_svg_dimensions.py "$TARGET"

# 6c. Regenerate every social card from the page trails (blog-priv#62 AC 3.0). A
#     card's eyebrow is its page's parent trail, so a breadcrumb, section title or
#     permalink change stales every card below it — and nothing else in the repo
#     ever invokes a generator, so without this the cards drift silently. Runs
#     BEFORE the build check below so that build sees the regenerated PNGs.
run_check "social-cards-generate" bash scripts/gen-social-cards.sh

# 7. Hugo build with --buildDrafts so the rendered HTML in public/ matches
#    what production will serve (excluding the auto-deploy gate). Builds ALL
#    drafts so cross-links to in-progress posts resolve.
hugo_build() {
    rm -rf public
    hugo --buildDrafts --minify --quiet
    [[ -d public ]] || { printf >&2 'ERR: hugo build did not produce public/\n'; return 1; }
}
run_check "hugo-build" hugo_build

# 7a. Rendered social-card backstop: assert each singular indexable page's RENDERED
#     og:image is its own card, not the site default. Catches a head.html/hero-pick
#     template regression the source-only guard (check #4b) cannot see (#52 Stage 5).
run_check "social-cards-rendered" python3 scripts/check_social_cards.py --built public

# 7b. 404 gate: the build must emit a root 404.html, its content block must have
#     actually rendered, and every navigation link ON that page must resolve.
#     Cloudflare Pages returns a 404 status only when that file exists; without
#     it every dead URL soft-404s as HTTP 200 with page HTML, which also makes
#     check #8 below structurally unable to fail on a dead internal link.
#     blog-priv#64.
run_check "404-gate" python3 scripts/test_404.py --built public

# 7c. CTA button, as the BROWSER computes it. Loads every built page carrying
#     a.btn in headless Chromium, in both colour schemes, and asserts the
#     computed fill, label colour and text-decoration. This is the only lane
#     with a browser, so it is the only lane that can prove the cascade rather
#     than model it: `scripts/test_cta_button.py` scores selector specificity
#     from source in CI, which stays green for a stylesheet that is correct and
#     a page that is not. blog-priv#63.
run_check "cta-rendered" python3 scripts/check_cta_rendered.py --built public

# 8. Lychee on rendered HTML — catches broken cross-section links + missing
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
    # so the rendered path is public/blogs/<frontmatter-slug>/, NOT the bundle
    # dir. Without this, every post carrying an override fails the gate: as of
    # 2026-07-20 that is 2 of 78 (2026-04-07-foundation -> foundation,
    # ai-jargon-for-noobs -> ai-jargon-for-newbies). Read from the closing ---
    # onward only, so a `slug:` mentioned in body prose cannot hijack it.
    fm_slug=$(awk 'NR==1 && /^---/ {f=1; next} f && /^---/ {exit} f' "$POST_FILE" \
        | sed -n 's/^slug:[[:space:]]*//p' | head -n1 | tr -d '"'"'" | tr -d '[:space:]')
    [[ -n "$fm_slug" ]] && slug="$fm_slug"
    # A frontmatter `url:` overrides the WHOLE path, not merely the slug. Hugo
    # serves the page at exactly that URL, so neither the section prefix nor the
    # slug describes where it lands, and both derivations below are wrong for it.
    # content/community/agit-thanks/ sets url: /community/asians-gingers-in-tech/
    # thanks/ and renders two levels deeper under a DIFFERENT parent, so
    # slug resolution looks for public/community/agit-thanks/index.html (absent)
    # and the find fallback cannot rescue it either -- the real leaf segment is
    # `thanks`, which never matches the slug `agit-thanks`. The gate therefore
    # could not publish that page at all. Found by Ralph Tier 2 on #55, and it
    # matters because that page is one of the 18 AGIT paths AC 3.2 requires be
    # link-checked. Read from the same frontmatter slice as `slug:` above, so
    # `url:` in body prose cannot hijack it.
    local fm_url
    fm_url=$(awk 'NR==1 && /^---/ {f=1; next} f && /^---/ {exit} f' "$POST_FILE" \
        | sed -n 's/^url:[[:space:]]*//p' | head -n1 | tr -d '"'"'" | tr -d '[:space:]')
    # Which public/ subtree this target's section renders into. Every section
    # renders to public/<section>/ EXCEPT posts, which [permalinks.page] in
    # config/_default/hugo.toml maps to /blogs/. Derived from the target rather
    # than hardcoded so legal/, hire-hoi/, skills/, private/ and community/
    # targets keep resolving -- the fallback below is their DESIGNED path, not an
    # error case, so it must not be narrowed to public/blogs/ only.
    local section expected_prefix
    section=${TARGET#content/}
    section=${section%%/*}
    case "$section" in
        posts) expected_prefix="public/blogs/" ;;
        *)     expected_prefix="public/$section/" ;;
    esac

    # A `url:` override is authoritative: resolve straight to it and do NOT fall
    # through to the slug search, which would look under the wrong parent and, if
    # some unrelated page happened to share the slug, could check the wrong file.
    if [[ -n "$fm_url" ]]; then
        rendered="public/${fm_url#/}"
        rendered="${rendered%/}/index.html"
        if [[ ! -f "$rendered" ]]; then
            printf >&2 'ERR: frontmatter url: %s resolves to %s, which does not exist. Rebuild with: hugo --gc --minify -e production ... or correct the override.\n' \
                "$fm_url" "$rendered"
            return 1
        fi
        printf 'rendered-link-liveness: url: override -> %s\n' "$rendered"
    else
    # /blogs/<slug>/ since blog-priv#62 ([permalinks.page] posts in hugo.toml).
    rendered="$expected_prefix$slug/index.html"
    if [[ ! -f "$rendered" ]]; then
        printf >&2 'WARN: rendered HTML not at %s — looking for any matching slug\n' "$rendered"
        # A bare `find | head -n1` is not safe here: taxonomy pages share the
        # slug namespace and sort first. For the real post slug `foundation`,
        # public/tags/foundation/index.html precedes public/blogs/foundation/
        # index.html, so the gate would check a tag listing page and report PASS
        # having never seen the post. Same collision for adventure, dance,
        # entrepreneurship and trading. Constrain to the target's own section and
        # reject taxonomy output outright.
        local candidate
        rendered=""
        while IFS= read -r candidate; do
            case "$candidate" in
                public/tags/*|public/series/*)
                    printf >&2 'ERR: refusing taxonomy page %s for slug %s (a term page is not the target)\n' \
                        "$candidate" "$slug"
                    continue
                    ;;
            esac
            [[ "$candidate" == "$expected_prefix"* ]] && { rendered="$candidate"; break; }
        done < <(find public -path "*/$slug/index.html" -type f 2>/dev/null | sort)
        if [[ -z "$rendered" ]]; then
            printf >&2 'ERR: cannot locate rendered HTML for slug %s under %s. If this page carries a frontmatter url: override, the override is what decides its path.\n' \
                "$slug" "$expected_prefix"
            return 1
        fi
    fi
    fi
    if ! command -v lychee >/dev/null 2>&1; then
        printf >&2 'ERR: lychee not installed; install via cargo or apt\n'
        return 127
    fi

    # What this floor does and does NOT prove (#55, Ralph Tier 3). It counts
    # `Total`, which is links DISCOVERED, not links VERIFIED. `base_url` above
    # rewrites every root-relative link to https://hoiboy.uk/..., and that domain
    # is allowlisted in `exclude` (the CI-vs-deploy race), so a post's internal
    # links are counted and then suppressed: a typical post reports 41 Total /
    # 4 OK / 37 Excluded. External links are what this tier verifies, and they
    # are the class that rots without anyone touching the repo.
    # Internal links are MOSTLY covered elsewhere, and the gap is worth knowing
    # exactly. scripts/validate_internal_links.py (pre-commit AND ci.yml) resolves
    # /blogs/<slug>/ and the 7 category landings against the content tree. It does
    # NOT resolve /hire-hoi/, /legal/, /community/, /tags/ or /series/ paths: its
    # _ALLOW_TWO_PREFIX set (that file, ~:84) returns True for them unconditionally.
    # So the ~15 root-relative links under those five prefixes are resolved by
    # NEITHER tier -- lychee rewrites them to hoiboy.uk and the allowlist then
    # suppresses them. Stating the gap rather than implying coverage, because a
    # comment claiming a check that does not exist is the defect this whole Issue
    # is about. Closing it is a follow-up (it belongs in validate_internal_links.py,
    # not here); do not read `41 Total` as 41 links verified.
    #
    # Zero-item floor. exclude_path voids even an explicitly-passed input and
    # says so only as "No files found for this input source", which reads like a
    # missing file and still exits 0 -- that is how this gate reported PASS on
    # every post from blog-priv#62 to #55 without examining one link. Exit code
    # alone is therefore not evidence the gate ran; the link COUNT is. Same
    # fail-closed idiom as check_cta_rendered.py's --min-pages/--min-instances.
    local out total
    out=$(lychee --config lychee.toml --root-dir "$REPO_ROOT/public" --no-progress "$rendered" 2>&1)
    local rc=$?
    printf '%s\n' "$out"
    total=$(printf '%s' "$out" | grep -oE '[0-9]+ Total' | head -n1 | cut -d' ' -f1)
    if [[ -z "$total" ]]; then
        printf >&2 'ERR: could not parse a link count from lychee output for %s; refusing to report PASS on an unreadable result\n' \
            "$rendered"
        return 1
    fi
    if (( total == 0 )); then
        printf >&2 'ERR: rendered-link-liveness examined 0 links in %s. A gate that checks nothing must not pass. Most likely an entry in lychee.toml exclude_path matches this path (it voids even an explicitly-passed file); check exclude_path before assuming the page has no links.\n' \
            "$rendered"
        return 1
    fi
    return $rc
}
run_check "rendered-link-liveness" rendered_link_check

# 8a. Lychee on rendered consulting pages — when public/hire-hoi/ai-consultancy/*/index.html
#     exists post-Hugo-build, every external URL in those rendered pages is
#     verified live. This is what catches a stale cal.com/OPERATOR_TODO/...
#     URL slipping through (the OPERATOR_TODO yaml gate at check #1 is the
#     primary defence; this is defence-in-depth at the rendered-HTML layer).
#     consulting-ops#2 AC 0.4.
consulting_link_check() {
    if [ ! -d "public/hire-hoi/ai-consultancy" ]; then
        printf '  no public/hire-hoi/ai-consultancy/ directory in build output; skipping consulting-link-liveness\n'
        return 0
    fi
    local rendered
    rendered=$(find public/hire-hoi/ai-consultancy -path '*/index.html' -type f 2>/dev/null)
    if [ -z "$rendered" ]; then
        printf '  no rendered consulting pages found; skipping\n'
        return 0
    fi
    if ! command -v lychee >/dev/null 2>&1; then
        printf >&2 'ERR: lychee not installed; install via cargo or apt\n'
        return 127
    fi
    # Same DISCOVERED-not-VERIFIED caveat as gate 8's floor above, and this gate
    # is MORE exposed to it: it reports ~468 Total of which ~39 are actually
    # verified (~8%), because the allowlist suppresses the rest. Its stated job is
    # catching a stale cal.com placeholder URL, so if the allowlist ever grows to
    # cover that domain this floor would still pass on a large Total with the one
    # URL that matters unchecked. The floor is a vacuity guard, not a coverage
    # guarantee.
    #
    # Zero-item floor, same class as gate 8's (#55, Ralph Tier 3). Without it
    # this gate reported PASS on whatever lychee said, including a run that
    # examined nothing -- one function below the gate this Issue exists to fix.
    # The Issue declares a UNIFORM item-count contract across all 17 gates out of
    # scope, and that stands; this closes the one instance whose trigger fired,
    # rather than leaving a known live example of the defect being fixed above.
    local out rc total
    # shellcheck disable=SC2086
    out=$(lychee --config lychee.toml --root-dir "$REPO_ROOT/public" --no-progress $rendered 2>&1)
    rc=$?
    printf '%s\n' "$out"
    total=$(printf '%s' "$out" | grep -oE '[0-9]+ Total' | head -n1 | cut -d' ' -f1)
    if [[ -z "$total" ]]; then
        printf >&2 'ERR: consulting-link-liveness could not parse a link count from lychee. Refusing to report PASS on an unreadable result.\n'
        return 1
    fi
    if (( total == 0 )); then
        printf >&2 'ERR: consulting-link-liveness examined 0 links across %s consulting page(s). A gate that checks nothing must not pass. Check lychee.toml exclude_path, which voids even an explicitly-passed file.\n' \
            "$(grep -c . <<< "$rendered")"
        return 1
    fi
    return $rc
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
