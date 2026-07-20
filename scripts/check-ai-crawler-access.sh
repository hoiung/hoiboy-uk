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
# The two classes are also governed by DIFFERENT mechanisms, which is why they are
# reported differently. Citation access is an edge decision, so an HTTP status
# answers it. Training access is governed by robots.txt, which no HTTP status can
# reveal: a training crawler that obeys `Disallow: /` still gets 200 on this probe
# because the probe is not that crawler. Reporting status alone for the TRAINING
# class was therefore actively misleading, so each training row also reports the
# directive the served robots.txt gives that user-agent.
#
# Known limits (stated so a PASS is not read as more than it is):
#   - Classifies on HTTP status only. A managed challenge or block page served
#     with a 200 body reads as "ok". A clean exit means "not status-blocked",
#     not "served real content".
#   - robots.txt is honour-system. A reported `Disallow: /` is a request, not an
#     enforcement. Bytespider in particular has been reported ignoring it. Only an
#     edge rule (WAF / bot management) actually enforces.
#   - Status-probes the homepage only, not /sitemap.xml, so a path-scoped rule
#     would go unseen. robots.txt IS fetched, but only to read training directives.
#   - The user-agent list is a snapshot. A vendor renaming or adding a crawler is
#     invisible until this list is updated.
#
# Usage:
#   bash scripts/check-ai-crawler-access.sh [URL]
#   CRAWLER_TARGET_URL=https://example.com bash scripts/check-ai-crawler-access.sh
#
# Exit codes (tri-state, mirroring scripts/check_social_cards.py):
#   0 = every citation-class crawler reachable (HTTP 200)
#   1 = at least one citation-class crawler blocked (the defect this gate
#       catches). "Blocked" means a policy denial: 401, 403 or 451.
#   2 = operational error, or a status this script cannot interpret as either
#       reachable or denied (curl missing, DNS/network failure, target
#       unreachable, 5xx, redirects that end somewhere unexpected, and 429,
#       which is transient rate limiting rather than a policy decision)

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
# 429 is deliberately NOT in the blocked set. It is transient rate limiting, not
# a policy denial: it does not guarantee zero citation, and none of the four
# Cloudflare remediation steps this script prints would address it. Calling it
# blocked would make the failure message ("an access denial guarantees zero
# citation") false for that case and send the operator to a dashboard setting
# that is not the cause. It withholds the verdict instead, like any other code
# this script does not positively understand.
classify() {
    case "$1" in
        200)         printf 'ok' ;;
        401|403|451) printf 'blocked' ;;
        *)           printf 'error' ;;
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

# --- served robots.txt, fetched once for the TRAINING class ------------------
#
# Fetched with a browser user-agent, not a crawler one, so a zone that varies
# robots.txt by user-agent cannot hand us a different file than a human sees.
ROBOTS_FILE=$(mktemp 2>/dev/null) || ROBOTS_FILE=""
[ -n "$ROBOTS_FILE" ] && trap 'rm -f "$ROBOTS_FILE"' EXIT
ROBOTS_STATE="unavailable"
if [ -n "$ROBOTS_FILE" ]; then
    robots_code=$(curl -sL -o "$ROBOTS_FILE" -w '%{http_code}' \
        --max-time "$TIMEOUT" -A "$BROWSER_UA" "${TARGET%/}/robots.txt" 2>/dev/null)
    [ "$robots_code" = "200" ] && ROBOTS_STATE="ok"
fi

# Report how the served robots.txt governs one user-agent token.
#
# RFC 9309 permits more than one group for the same token, and a crawler merges
# them. So a token can carry BOTH a `Disallow: /` and an empty `Disallow:`.
# That is not hypothetical: Cloudflare's managed robots.txt PREPENDS its own
# groups ahead of the origin's file, and the two can disagree. cuarchitects.co.uk
# was serving exactly that for GPTBot, ClaudeBot, Google-Extended and CCBot.
# Permissive parsers resolve the tie toward allow, so the safe reading is that
# training is permitted. Reported as CONFLICT rather than silently picking a
# side, because that state is a defect in the policy, not a valid configuration.
robots_verdict() {
    [ "$ROBOTS_STATE" = "ok" ] || { printf 'robots.txt unavailable'; return; }
    awk -v want="$1" '
        BEGIN { want = tolower(want) }
        {
            line = $0
            sub(/#.*/, "", line)
            gsub(/\r/, "", line)
        }
        # A run of consecutive User-agent lines opens ONE group covering all of
        # them. Only a non-User-agent directive ends the run, so group membership
        # must accumulate across the run rather than reset per line.
        tolower(line) ~ /^[[:space:]]*user-agent[[:space:]]*:/ {
            if (!in_ua_run) { member = 0 }
            in_ua_run = 1
            v = line
            sub(/^[^:]*:[[:space:]]*/, "", v)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", v)
            if (tolower(v) == want) member = 1
            next
        }
        tolower(line) ~ /^[[:space:]]*disallow[[:space:]]*:/ {
            in_ua_run = 0
            if (!member) next
            v = line
            sub(/^[^:]*:[[:space:]]*/, "", v)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", v)
            seen = 1
            if (v == "/") deny = 1
            else if (v == "") allow = 1
            # A scoped rule (Disallow: /admin) is neither a full opt-out nor an
            # absence of one. Reporting it as "allowed" would assert no
            # restriction exists when one is on record.
            else partial = 1
            next
        }
        # An actual Allow: rule, which is NOT the same as an empty Disallow:.
        # RFC 9309 2.2.2 gives allow the tie-break over an equivalent disallow,
        # so `Allow: /` against `Disallow: /` is a genuine contradiction. Without
        # this branch the value was discarded and the pair reported as a clean
        # opt-out, silently picking the side the function claims it refuses to.
        tolower(line) ~ /^[[:space:]]*allow[[:space:]]*:/ {
            in_ua_run = 0
            if (!member) next
            v = line
            sub(/^[^:]*:[[:space:]]*/, "", v)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", v)
            seen = 1
            if (v == "/") allow = 1
            next
        }
        # Any other directive (Allow:, Sitemap:, Content-Signal:, blank) closes
        # the user-agent run without closing the group.
        { if (line !~ /^[[:space:]]*$/) in_ua_run = 0 }
        END {
            if (!seen)          { print "no group (falls under *)"; exit }
            if (deny && allow)  { print "CONFLICT: allow and Disallow:/ both present"; exit }
            if (deny)           { print "Disallow: / (training opted out)"; exit }
            if (partial)        { print "scoped rules only (NOT a full opt-out)"; exit }
            print "allowed (training NOT opted out)"
        }' "$ROBOTS_FILE"
}

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

# Status and directive are BOTH reported because they answer different questions.
# The status says whether the edge served us; the directive says whether a
# well-behaved training crawler is permitted to use the content. A 200 next to
# `Disallow: /` is the normal, correct state for this site's policy.
printf '\nTRAINING class (reported only; governed by robots.txt, not by HTTP status)\n'
for entry in "${TRAINING_BOTS[@]}"; do
    name="${entry%%|*}"
    ua="${entry#*|}"
    code=$(probe "$ua")
    printf '  %-20s %-4s %s\n' "$name" "$code" "$(robots_verdict "$name")"
done
if [ "$ROBOTS_STATE" != "ok" ]; then
    printf '  NOTE: robots.txt could not be fetched, so training directives are unknown.\n'
    printf '        This does not affect the exit code, which the CITATION class alone gates.\n'
fi

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
