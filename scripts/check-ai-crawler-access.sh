#!/bin/bash
# Probe the LIVE site as each AI crawler and fail if a citation-class bot is blocked.
#
# Why this exists (blog-priv#55 Phase 10): layouts/robots.txt serves allow-all,
# but that is only the repo's intent. Cloudflare can override it at the edge, and
# on 2026-07-20 it was doing exactly that: 5 of 6 citation-class crawlers got 403
# while 4 of 5 training-class crawlers got 200. The site was giving away training
# data while blocking the pathway that produces citations. Nothing in the repo can
# reveal that, which is why the defect sat unnoticed from 2026-05-31 to 2026-07-20.
#
# This converts the one-time manual dashboard checklist in
# docs/research/16_AI_BOT_AND_SEO_POLICY.md into a standing gate.
#
# The two classes are NOT interchangeable. Training crawls never emit citations;
# no vendor offers a cite-for-training contract. Only the CITATION class gates the
# exit code. The TRAINING class is probed and reported for visibility only, because
# its correct value is an operator policy choice, not a defect.
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
)

# Echoes the HTTP status, or "ERR" when the request could not be made at all.
probe() {
    local ua="$1" code
    code=$(curl -s -o /dev/null -w '%{http_code}' \
        --max-time "$TIMEOUT" -A "$ua" "$TARGET" 2>/dev/null)
    if [ -z "$code" ] || [ "$code" = "000" ]; then
        printf 'ERR'
    else
        printf '%s' "$code"
    fi
}

printf 'AI crawler access probe: %s\n\n' "$TARGET"

# Reachability pre-flight. Without this, a dead network would report every bot as
# blocked and read as the exact defect we are looking for, which is a false alarm
# an operator would act on.
baseline=$(probe "curl-preflight/1.0")
if [ "$baseline" = "ERR" ]; then
    printf >&2 'ERR: target unreachable with an ordinary user-agent (%s).\n' "$TARGET"
    printf >&2 '     Network or DNS failure, not a crawler-policy result. Not reporting a verdict.\n'
    exit 2
fi

blocked=0
errored=0

printf 'CITATION class (gates the exit code)\n'
for entry in "${CITATION_BOTS[@]}"; do
    name="${entry%%|*}"
    ua="${entry#*|}"
    code=$(probe "$ua")
    if [ "$code" = "200" ]; then
        printf '  %-20s %s ok\n' "$name" "$code"
    elif [ "$code" = "ERR" ]; then
        printf '  %-20s %s request failed\n' "$name" "$code"
        errored=$((errored + 1))
    else
        printf '  %-20s %s BLOCKED\n' "$name" "$code"
        blocked=$((blocked + 1))
    fi
done

printf '\nTRAINING class (reported only; operator policy, not a defect)\n'
for entry in "${TRAINING_BOTS[@]}"; do
    name="${entry%%|*}"
    ua="${entry#*|}"
    code=$(probe "$ua")
    printf '  %-20s %s\n' "$name" "$code"
done

printf '\n'

if [ "$errored" -gt 0 ]; then
    printf >&2 'ERR: %d citation-class probe(s) could not complete. Verdict withheld.\n' "$errored"
    exit 2
fi

if [ "$blocked" -gt 0 ]; then
    printf >&2 'FAIL: %d of %d citation-class crawlers are BLOCKED at the edge.\n' \
        "$blocked" "${#CITATION_BOTS[@]}"
    printf >&2 'A 403 guarantees zero citation from that engine.\n'
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
