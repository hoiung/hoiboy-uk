#!/bin/bash
# Probe the LIVE site as each AI crawler and fail if a citation-class bot is blocked.
#
# Why this exists (blog-priv#55 Phase 10): layouts/robots.txt serves allow-all,
# but that is only the repo's intent. Cloudflare can override it at the edge, and
# on 2026-07-20 it was doing exactly that: every citation-class crawler probed
# returned 403. Nothing in the repo can reveal this, which is why the block sat
# unnoticed from 2026-05-31 to 2026-07-20.
#
# Do NOT quote a bot-by-bot tally here. Two probes hours apart on 2026-07-20
# disagreed, so any fixed count in a comment goes stale and then contradicts the
# record. The authoritative, dated state lives in
# docs/research/16_AI_BOT_AND_SEO_POLICY.md; this script measures, it does not
# remember.
#
# This converts the one-time manual dashboard checklist in
# docs/research/16_AI_BOT_AND_SEO_POLICY.md into a standing gate.
#
# The two classes are NOT interchangeable. Training crawls never emit citations;
# no vendor offers a cite-for-training contract. Only the CITATION class gates the
# exit code. The TRAINING class is probed and reported for visibility only, because
# its correct value is an operator policy choice, not a defect.
#
# Known limits (stated so a PASS is not read as more than it is):
#   - Classifies on HTTP status only. A managed challenge or block page served
#     with a 200 body reads as "ok". A clean exit means "not status-blocked",
#     not "served real content".
#   - Probes the homepage only, not /robots.txt or /sitemap.xml, so a path-scoped
#     rule would go unseen.
#   - The user-agent list is a snapshot. A vendor renaming or adding a crawler is
#     invisible until this list is updated.
#
# Usage:
#   bash scripts/check-ai-crawler-access.sh [URL]
#   CRAWLER_TARGET_URL=https://example.com bash scripts/check-ai-crawler-access.sh
#
# Exit codes (tri-state, mirroring scripts/check_social_cards.py):
#   0 = every citation-class crawler reachable
#   1 = at least one citation-class crawler blocked (the defect this gate catches)
#   2 = operational error (curl missing, DNS/network failure, target unreachable)

set -uo pipefail

TARGET="${1:-${CRAWLER_TARGET_URL:-https://hoiboy.uk/}}"
TIMEOUT="${CRAWLER_TIMEOUT:-20}"

if ! command -v curl >/dev/null 2>&1; then
    printf >&2 'ERR: curl not installed; cannot probe. This is an operational error, not a pass.\n'
    exit 2
fi

# name|user-agent
CITATION_BOTS=(
    "OAI-SearchBot|OAI-SearchBot/1.0; +https://openai.com/searchbot"
    "ChatGPT-User|Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot"
    "Claude-SearchBot|Mozilla/5.0 (compatible; Claude-SearchBot/1.0; +https://www.anthropic.com/claude-searchbot)"
    "Claude-User|Mozilla/5.0 (compatible; Claude-User/1.0; +Claude-User@anthropic.com)"
    "PerplexityBot|Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)"
    "Perplexity-User|Mozilla/5.0 (compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)"
)

TRAINING_BOTS=(
    "GPTBot|Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.1; +https://openai.com/gptbot"
    "ClaudeBot|Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)"
    "CCBot|CCBot/2.0 (https://commoncrawl.org/faq/)"
    "Google-Extended|Mozilla/5.0 (compatible; Google-Extended/1.0; +http://www.google.com/bot.html)"
    "meta-externalagent|meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)"
    "Bytespider|Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 (compatible; Bytespider; spider-feedback@bytedance.com)"
)

# Echoes the FINAL HTTP status (redirects followed), or "ERR" when the request
# could not be made at all. -L matters: without it a 301/302 reads as a non-200
# and would be misreported as a block.
probe() {
    local ua="$1" code
    code=$(curl -sL -o /dev/null -w '%{http_code}' \
        --max-time "$TIMEOUT" -A "$ua" "$TARGET" 2>/dev/null)
    if [ -z "$code" ] || [ "$code" = "000" ]; then
        printf 'ERR'
    else
        printf '%s' "$code"
    fi
}

# Classify a status into ok | blocked | error.
#
# Only the access-denied family counts as BLOCKED. A 5xx is the origin failing,
# and any other unexpected code is something this script does not understand:
# reporting either as "blocked at the edge" would send an operator to the
# Cloudflare dashboard chasing a cause that is not there. Those withhold the
# verdict (exit 2) instead of asserting a defect that was never observed.
classify() {
    case "$1" in
        200)             printf 'ok' ;;
        401|403|429|451) printf 'blocked' ;;
        *)               printf 'error' ;;
    esac
}

printf 'AI crawler access probe: %s\n\n' "$TARGET"

# Reachability pre-flight. Without this, a dead network would report every bot as
# blocked and read as the exact defect we are looking for, which is a false alarm
# an operator would act on.
BROWSER_UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
baseline=$(probe "$BROWSER_UA")
if [ "$baseline" = "ERR" ]; then
    printf >&2 'ERR: target unreachable with an ordinary user-agent (%s).\n' "$TARGET"
    printf >&2 '     Network or DNS failure, not a crawler-policy result. Not reporting a verdict.\n'
    exit 2
fi

blocked=0
errored=0
blocked_codes=""

printf 'CITATION class (gates the exit code)\n'
for entry in "${CITATION_BOTS[@]}"; do
    name="${entry%%|*}"
    ua="${entry#*|}"
    code=$(probe "$ua")
    if [ "$code" = "ERR" ]; then
        printf '  %-20s %s request failed\n' "$name" "$code"
        errored=$((errored + 1))
        continue
    fi
    case "$(classify "$code")" in
        ok)
            printf '  %-20s %s ok\n' "$name" "$code"
            ;;
        blocked)
            printf '  %-20s %s BLOCKED\n' "$name" "$code"
            blocked=$((blocked + 1))
            case "$blocked_codes" in
                *"$code"*) : ;;
                *) blocked_codes="${blocked_codes:+$blocked_codes/}$code" ;;
            esac
            ;;
        *)
            printf '  %-20s %s UNEXPECTED (not an access denial; verdict withheld)\n' "$name" "$code"
            errored=$((errored + 1))
            ;;
    esac
done

printf '\nTRAINING class (reported only; operator policy, not a defect)\n'
for entry in "${TRAINING_BOTS[@]}"; do
    name="${entry%%|*}"
    ua="${entry#*|}"
    code=$(probe "$ua")
    printf '  %-20s %s\n' "$name" "$code"
done

# Controls. These rule out the two alternative explanations for a wall of 403s:
# the site being down, and a blanket block that is not user-agent-specific. If
# the browser and empty user-agents return 200 while the crawler user-agents do
# not, the blocking is user-agent-based at the edge. Googlebot is the
# verified-bot control: a 200 here alongside crawler 403s shows the edge is
# allow-listing some bots and denying others, rather than denying all bots.
# Reported only. These do NOT touch the exit code, which the CITATION class
# alone gates. Documented in docs/research/16_AI_BOT_AND_SEO_POLICY.md, and
# implemented here so the standing gate reproduces its own evidence instead of
# citing a measurement no one can re-run.
printf '\nCONTROLS (reported only; rule out outage and blanket blocking)\n'
printf '  %-20s %s\n' "browser-UA" "$(probe "$BROWSER_UA")"
printf '  %-20s %s\n' "empty-UA" "$(probe "")"
printf '  %-20s %s\n' "Googlebot" "$(probe "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")"

printf '\n'

# A CONFIRMED block outranks noise elsewhere. If any probe returned a genuine
# access denial, report it, even when another probe separately failed. Checking
# `errored` first would let one unrelated 5xx suppress the whole verdict and hide
# a real block from the operator, which is a worse failure than an incomplete run.
if [ "$blocked" -eq 0 ] && [ "$errored" -gt 0 ]; then
    printf >&2 'ERR: %d citation-class probe(s) returned no usable answer, and no\n' "$errored"
    printf >&2 '     confirmed access denial was observed among the rest.\n'
    printf >&2 '     Request failure, origin error or an unrecognised status: NOT an\n'
    printf >&2 '     observed block. Verdict withheld rather than reported as one.\n'
    exit 2
fi

if [ "$blocked" -gt 0 ]; then
    if [ "$errored" -gt 0 ]; then
        printf >&2 'NOTE: %d further probe(s) returned no usable answer. Coverage is\n' "$errored"
        printf >&2 '      incomplete, so the true block count may be HIGHER than reported.\n'
    fi
    printf >&2 'FAIL: %d of %d citation-class crawlers are BLOCKED at the edge (HTTP %s).\n' \
        "$blocked" "${#CITATION_BOTS[@]}" "$blocked_codes"
    printf >&2 'An access denial guarantees zero citation from that engine.\n'
    printf >&2 'Fix in the Cloudflare dashboard for this zone (repo changes cannot):\n'
    printf >&2 '  1. "Block AI bots" managed toggle OFF\n'
    printf >&2 '  2. AI Crawl Control set to Allow for the citation class\n'
    printf >&2 '  3. managed-robots.txt OFF, so it cannot inject rules over the repo-served file\n'
    printf >&2 '  4. Bot Fight Mode off, or configured to skip verified bots\n'
    printf >&2 'Detail: docs/research/16_AI_BOT_AND_SEO_POLICY.md\n'
    exit 1
fi

printf 'PASS: all %d citation-class crawlers reachable.\n' "${#CITATION_BOTS[@]}"
printf 'Note: this means they are not blocked. It does NOT mean the site is cited;\n'
printf 'no reliable method for measuring AI citation currently exists.\n'
exit 0
