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
# no vendor offers a cite-for-training contract.
#
# BOTH classes gate the exit code. This block used to say the CITATION class
# alone did, on the grounds that training's "correct value is an operator policy
# choice, not a defect". That held only while the policy was undecided. It was
# decided on 2026-07-20 (block training on every domain), so an unprotected
# training token is now a defect like any other, and a standing watch that
# cannot fail on it is not a watch.
#
# The two gates read different instruments, deliberately:
#   CITATION -> HTTP STATUS. A 401/403/451 is the denial itself.
#   TRAINING -> the robots.txt DIRECTIVE, never status. Google-Extended and
#     Applebot-Extended are control tokens with no user-agent of their own, so
#     no edge rule can match them and they return 200 while fully opted out.
#     Gating training on status would fail this site forever for a condition
#     that is neither fixable nor wrong.
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
#   0 = every citation-class crawler reachable (HTTP 200), and no training-class
#       token PROVEN to lack an opt-out. Stated that way on purpose, because two
#       states exit 0 without every token being proven opted out:
#         - a CONFLICT token (contradictory records) is reported, excluded from
#           the opt-out count, and deliberately not failed
#         - if robots.txt cannot be fetched the training gate is SKIPPED
#           entirely; no data is neither a pass nor a fail
#       An earlier version of this table said "AND every training-class token
#       carrying a full opt-out", which was false in both of those states. The
#       PASS line itself reports the actual count, so read it rather than
#       inferring nine-of-nine from a zero exit.
#   1 = a POLICY FAILURE, which is EITHER of two conditions needing OPPOSITE
#       fixes, so read the output before acting:
#         (a) at least one citation-class crawler blocked. "Blocked" means a
#             policy denial: 401, 403 or 451.
#         (b) at least one training-class token with no full opt-out in the
#             served robots.txt.
#       A CONFLICT verdict is NOT (b): contradictory records whose resolution
#       varies by parser are reported, counted out of the opt-out total, and
#       deliberately not failed, because the measured live outcome is blocked.
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
    # The three below were MISSING while this list covered six of the nine
    # tokens the managed block names. That was tolerable while the training
    # class was reported for information only. It stopped being tolerable the
    # moment the training class started gating the exit code: a gate that never
    # asks about a token cannot fail on it, so a regression on any of these
    # three was structurally invisible to the standing watch that exists to
    # catch exactly that. Enumerated from the LIVE managed block
    # (`curl -s https://hoiboy.uk/robots.txt`), not from memory.
    #
    # Applebot-Extended is a robots.txt CONTROL TOKEN with no user-agent of its
    # own, exactly like Google-Extended above, so it is expected to return 200
    # at the edge while being fully opted out. That is why this gate keys on the
    # robots.txt directive and never on HTTP status.
    "Amazonbot|Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15 (Amazonbot/0.1; +https://developer.amazon.com/support/amazonbot)"
    "Applebot-Extended|Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15 (Applebot-Extended/0.1; +http://www.apple.com/go/applebot)"
    "CloudflareBrowserRenderingCrawler|CloudflareBrowserRenderingCrawler/1.0"
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
# them. So a token can carry BOTH a `Disallow: /` and an empty `Disallow:`,
# and an empty `Disallow:` is an ALLOW (the traditional allow-everything special
# case, which is why the parser below scores it that way). That is not
# hypothetical: Cloudflare's managed robots.txt PREPENDS its own groups ahead of
# the origin's file, and the two can disagree. cuarchitects.co.uk serves exactly
# that for GPTBot, ClaudeBot, Google-Extended and CCBot.
#
# Do NOT infer an outcome from a CONFLICT in either direction. Measured on the
# live file, every parser tried returns blocked, but they do not agree on why:
# a strict RFC reading resolves it on §2.2.2 specificity, while urllib is
# first-matching-group-wins and would return allowed if the origin's group came
# first. Reported as CONFLICT precisely because the answer depends on the
# implementation and on serving order, which is a state to fix rather than to
# reason about. Detail: docs/research/17_AI_CRAWLER_FRAMEWORK.md.
robots_verdict() {
    [ "$ROBOTS_STATE" = "ok" ] || { printf 'robots.txt unavailable'; return; }
    awk -v want="$1" '
        BEGIN { want = tolower(want) }

        # Render one group_s accumulated flags into a verdict. Used for the
        # token_s own group and, failing that, for the `*` group.
        function verdict(seen, deny, empty_dis, allow_rule, partial, partial_allow,   pfx) {
            if (!seen) return ""
            # RFC 9309 2.2.2: "If an allow rule and a disallow rule are
            # equivalent, then the allow rule SHOULD be used." `Allow: /`
            # against `Disallow: /` is therefore DETERMINATE, not a conflict.
            # Reporting it as CONFLICT (as this function used to) invented an
            # ambiguity the spec resolves, and a test locked that error in.
            if (deny && allow_rule)   return "allowed (Allow:/ beats Disallow:/ per RFC 9309 2.2.2)"
            # An EMPTY `Disallow:` is a different animal from an `Allow:` rule
            # and must not share its flag. Real parsers treat it as allow-all
            # (CPython: "an empty value means allow all"); RFC 9309 has no such
            # special case and its ABNF puts `empty-pattern = *WS` under
            # disallow, making it a zero-octet DISALLOW that loses to `/` on
            # 2.2.2 specificity. The two readings disagree, so this pairing is
            # a genuine CONFLICT where `Allow: /` above is not.
            if (deny && empty_dis)    return "CONFLICT: Disallow:/ with an empty Disallow: (parsers disagree)"
            if (deny && partial_allow) return "CONFLICT: Disallow:/ with a scoped Allow carving paths back out"
            if (deny)                 return "Disallow: / (training opted out)"
            if (partial || partial_allow) return "scoped rules only (NOT a full opt-out)"
            return "allowed (training NOT opted out)"
        }
        {
            line = $0
            sub(/#.*/, "", line)
            gsub(/\r/, "", line)
        }
        # A run of consecutive User-agent lines opens ONE group covering all of
        # them. Only a non-User-agent directive ends the run, so group membership
        # must accumulate across the run rather than reset per line.
        tolower(line) ~ /^[[:space:]]*user-agent[[:space:]]*:/ {
            if (!in_ua_run) { member = 0; wmember = 0 }
            in_ua_run = 1
            v = line
            sub(/^[^:]*:[[:space:]]*/, "", v)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", v)
            if (tolower(v) == want) member = 1
            # RFC 9309 2.2.1: "If no matching group exists, crawlers MUST obey
            # the group with a user-agent line with the \"*\" value, if
            # present." The wildcard group is therefore tracked in parallel, not
            # ignored. Without this a site-wide `User-agent: * / Disallow: /`
            # (the most common way to write a blanket opt-out) was reported as
            # "no group", i.e. as though nothing governed the token at all.
            if (v == "*") wmember = 1
            next
        }
        tolower(line) ~ /^[[:space:]]*disallow[[:space:]]*:/ {
            in_ua_run = 0
            v = line
            sub(/^[^:]*:[[:space:]]*/, "", v)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", v)
            # A scoped rule (Disallow: /admin) is neither a full opt-out nor an
            # absence of one. Reporting it as "allowed" would assert no
            # restriction exists when one is on record.
            if (member) {
                seen = 1
                if (v == "/") deny = 1
                else if (v == "") empty_dis = 1
                else partial = 1
            }
            if (wmember) {
                w_seen = 1
                if (v == "/") w_deny = 1
                else if (v == "") w_empty_dis = 1
                else w_partial = 1
            }
            next
        }
        # An actual Allow: rule, which is NOT the same as an empty Disallow:.
        # RFC 9309 2.2.2 gives allow the tie-break over an equivalent disallow,
        # so `Allow: /` against `Disallow: /` is a genuine contradiction. Without
        # this branch the value was discarded and the pair reported as a clean
        # opt-out, silently picking the side the function claims it refuses to.
        tolower(line) ~ /^[[:space:]]*allow[[:space:]]*:/ {
            in_ua_run = 0
            v = line
            sub(/^[^:]*:[[:space:]]*/, "", v)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", v)
            # A scoped Allow (Allow: /public) against Disallow: / carves paths
            # back out. Under RFC 9309 longest-match those paths are explicitly
            # permitted, with no tie-break needed, so this is a MORE certain
            # permission than the exact `Allow: /` case, not a lesser one.
            # Discarding it reported a clean opt-out for a file that grants
            # access.
            if (member) {
                seen = 1
                if (v == "/") allow_rule = 1
                else if (v != "") partial_allow = 1
            }
            if (wmember) {
                w_seen = 1
                if (v == "/") w_allow_rule = 1
                else if (v != "") w_partial_allow = 1
            }
            next
        }
        # Any other record (Sitemap:, Content-Signal:, prose) is IGNORED and
        # must NOT touch group state. RFC 9309 2.2.4: "Parsing of other records
        # MUST NOT interfere with the parsing of explicitly defined records in
        # Section 2. For example, a \"Sitemaps\" record MUST NOT terminate a
        # group." This branch used to close the user-agent run on any non-blank
        # line, so
        #
        #     User-agent: GPTBot
        #     Sitemap: https://example/sitemap.xml
        #     User-agent: ClaudeBot
        #     Disallow: /
        #
        # silently dropped GPTBot from the group it belongs to and reported it
        # as ungoverned. The user-agent run is closed by the first RULE
        # (allow/disallow), which the two branches above already do; nothing
        # else may close it.
        #
        # A BLANK line is likewise exempt, and that is not an oversight.
        # RFC 9309: `group = startgroupline *(startgroupline / emptyline)
        # *(rule / emptyline)`. Empty lines are explicitly permitted BETWEEN
        # consecutive user-agent lines, so
        #
        #     User-agent: GPTBot
        #     <blank>
        #     User-agent: ClaudeBot
        #     Disallow: /
        #
        # is ONE group covering both tokens, and both are correctly reported as
        # opted out. Closing the run on a blank line would split it and silently
        # drop the rule for every token but the last. A review flagged this
        # behaviour as a leak; it is the specified behaviour, and the earlier
        # version of this comment (which listed "blank" among the closers)
        # contradicted the code. The code was right.
        { }
        END {
            own = verdict(seen, deny, empty_dis, allow_rule, partial, partial_allow)
            if (own != "") { print own; exit }
            # No group named this token, so the `*` group governs it (2.2.1).
            wild = verdict(w_seen, w_deny, w_empty_dis, w_allow_rule, w_partial, w_partial_allow)
            if (wild != "") { print "via * group: " wild; exit }
            print "no rules for this token (no group, no * group, or a group with no rules)"
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
# `Disallow: /` is the normal, correct state for a token no edge rule can match.
#
# The TRAINING class NOW GATES THE EXIT CODE, and that is a deliberate change.
# It previously did not, on the stated grounds that "its correct value is an
# operator policy choice, not a defect". That rationale held only while the
# policy was undecided. It was decided on 2026-07-20 ("i dont want to give bots
# free training if i am not cited. i want to block that"), so a training block
# that silently collapses is now a defect, and a standing watch that cannot
# fail on it is not a watch. Stage 5 proved the old behaviour: a robots.txt
# serving zero training groups still printed PASS and exited 0.
#
# The gate keys on the robots.txt DIRECTIVE, never on HTTP status. Status would
# be the wrong signal: Google-Extended and Applebot-Extended send no user-agent
# of their own, so no edge rule can ever match them and they correctly return
# 200 while being fully opted out in robots.txt. Gating on status would fail
# this site forever for a condition that is not fixable and not wrong.
printf '\nTRAINING class (directive gates the exit code; HTTP status is reported only)\n'
train_open=0
train_open_names=""
train_conflict=0
for entry in "${TRAINING_BOTS[@]}"; do
    name="${entry%%|*}"
    ua="${entry#*|}"
    code=$(probe "$ua")
    directive=$(robots_verdict "$name")
    printf '  %-20s %-4s %s\n' "$name" "$code" "$directive"
    case "$directive" in
        *"training opted out"*)
            : ;;
        *CONFLICT*)
            # Ambiguous rather than open: contradictory records whose resolution
            # varies by parser. Reported, and deliberately NOT failed, because
            # the measured live outcome on the affected zone is still blocked.
            train_conflict=$((train_conflict + 1)) ;;
        *"robots.txt unavailable"*)
            : ;;
        *)
            train_open=$((train_open + 1))
            train_open_names="${train_open_names:+$train_open_names, }$name" ;;
    esac
done
if [ "$ROBOTS_STATE" != "ok" ]; then
    printf '  NOTE: robots.txt could not be fetched, so training directives are unknown.\n'
    printf '        The training gate is skipped; it cannot pass or fail on no data.\n'
fi

# Controls. These rule out the two alternative explanations for a wall of 403s:
# the site being down, and a blanket block that is not user-agent-specific. If
# the browser and empty user-agents return 200 while the crawler user-agents do
# not, the blocking is user-agent-based at the edge. Googlebot is the
# verified-bot control: a 200 here alongside crawler 403s shows the edge is
# allow-listing some bots and denying others, rather than denying all bots.
# Reported only. These do NOT touch the exit code (which the CITATION and
# TRAINING classes gate). Documented in docs/research/16_AI_BOT_AND_SEO_POLICY.md, and
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
    printf >&2 '  1. ai_bots_protection / "Block AI bots" set to DISABLED. This is the\n'
    printf >&2 '     coarse legacy switch and was the measured cause on hoiboy.uk; it takes\n'
    printf >&2 '     the citation class down together with training.\n'
    printf >&2 '  2. AI Crawl Control set to Allow for the citation class\n'
    printf >&2 '     (ai_search and ai_user DISABLED; ai_training may stay block)\n'
    printf >&2 '  3. Bot Fight Mode off, or configured to skip verified bots\n'
    printf >&2 '\n'
    printf >&2 'Do NOT turn managed robots.txt off to fix this. It cannot cause a 403,\n'
    printf >&2 'so it is never the cause here, and it is the mechanism that carries the\n'
    printf >&2 'training block. Disabling it would silently drop the training opt-out\n'
    printf >&2 'while doing nothing for the citation failure being reported.\n'
    printf >&2 'Detail: docs/research/17_AI_CRAWLER_FRAMEWORK.md\n'
    exit 1
fi

# The training gate. Runs only when robots.txt was actually readable, so a fetch
# failure withholds the verdict (exit 2 above already covers an unusable run)
# rather than manufacturing a pass or a fail from no data.
if [ "$ROBOTS_STATE" = "ok" ] && [ "$train_open" -gt 0 ]; then
    printf >&2 'FAIL: %d of %d training-class crawlers are NOT opted out in robots.txt: %s\n' \
        "$train_open" "${#TRAINING_BOTS[@]}" "$train_open_names"
    printf >&2 'The standing policy is citation ALLOWED, training BLOCKED. A token with no\n'
    printf >&2 'full opt-out is free to train on this content.\n'
    printf >&2 'Check, in this order:\n'
    printf >&2 '  1. Cloudflare managed robots.txt (is_robots_txt_managed) still TRUE for the\n'
    printf >&2 '     zone. It is the mechanism that carries the training block.\n'
    printf >&2 '  2. The WAF custom rule still present in the http_request_firewall_custom\n'
    printf >&2 '     phase. It hard-enforces seven of the nine tokens at the edge.\n'
    printf >&2 '  3. The origin robots.txt has not grown a group that re-permits a token the\n'
    printf >&2 '     managed block disallows.\n'
    printf >&2 'Detail: docs/research/17_AI_CRAWLER_FRAMEWORK.md\n'
    exit 1
fi

# The PASS line must not claim more than the run proved. It used to append
# "every training-class token carries a full opt-out" whenever robots.txt was
# merely READABLE, without consulting train_conflict, so on cuarchitects.co.uk
# it asserted a full opt-out for four tokens the same run had just reported as
# CONFLICT. That zone is in the weekly matrix, so the false line would have been
# printed to the job summary every Monday, and the corrective NOTE below does
# not reach the summary or the Verdict step at all. This is the same defect
# class as the deleted doc caveat Ralph caught earlier in this batch: an
# unqualified claim surviving past the point where it stopped being true.
printf 'PASS: all %d citation-class crawlers reachable' "${#CITATION_BOTS[@]}"
if [ "$ROBOTS_STATE" = "ok" ]; then
    if [ "$train_conflict" -gt 0 ]; then
        printf ', and %d of %d training-class tokens carry a full opt-out' \
            "$(( ${#TRAINING_BOTS[@]} - train_conflict ))" "${#TRAINING_BOTS[@]}"
    else
        printf ', and every training-class token carries a full opt-out'
    fi
fi
printf '.\n'
if [ "$train_conflict" -gt 0 ]; then
    printf 'NOTE: %d training token(s) reported CONFLICT (contradictory records whose\n' "$train_conflict"
    printf '      resolution varies by parser). NOT counted as opted out above, and not\n'
    printf '      failed either: the measured live outcome is still blocked. It is drift\n'
    printf '      worth fixing, not an exposure today.\n'
fi
printf 'Note: citation reachability means they are not blocked. It does NOT mean the\n'
printf 'site is cited; no reliable method for measuring AI citation currently exists.\n'
printf 'The training gate reads robots.txt, which is a REQUEST, not enforcement. Only\n'
printf 'the WAF rule hard-blocks, and only for tokens that send a matching user-agent.\n'
exit 0
