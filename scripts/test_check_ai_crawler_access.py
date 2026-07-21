"""Exit-contract tests for check-ai-crawler-access.sh.

Run: python3 -m pytest scripts/test_check_ai_crawler_access.py -q

The script's whole value is its tri-state exit code, and nothing exercised it:
the only evidence it worked was a live run against the production edge, which
cannot be re-run in CI, cannot produce a PASS case while Cloudflare blocks the
citation class, and cannot produce the inconclusive case at all. blog-priv#55
shipped it that way and the Stage 5 audit flagged it.

These stand up a real HTTP server that answers by user-agent, so all three
exits are produced hermetically and offline. No network.

Contract under test:
  0 = every citation-class crawler reachable
  1 = at least one citation-class crawler blocked (401/403/451)
  2 = operational error, or a status the script cannot classify
"""
from __future__ import annotations

import http.server
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "check-ai-crawler-access.sh"

# Kept in step with CITATION_BOTS in the script. A crawler added there and not
# here means that crawler is unexercised, so this list is asserted against the
# script's own array below rather than trusted.
CITATION_TOKENS = [
    "OAI-SearchBot",
    "ChatGPT-User",
    "Claude-SearchBot",
    "Claude-User",
    "PerplexityBot",
    "Perplexity-User",
]


def _make_server(decide, robots=None):
    """Serve HEAD/GET with a status chosen by `decide(user_agent) -> int`.

    `robots`, when given, is served as the body of /robots.txt. Left as None the
    path 404s, which is the "robots.txt unavailable" branch. The status for
    /robots.txt deliberately does NOT go through `decide`: the script fetches it
    with a browser user-agent, and routing it through the crawler decision would
    make the fixture unable to express "crawler blocked, robots.txt readable".
    """
    class Handler(http.server.BaseHTTPRequestHandler):
        def _respond(self):
            if self.path == "/robots.txt":
                if robots is None:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                body = robots.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if self.command == "GET":
                    self.wfile.write(body)
                return
            ua = self.headers.get("User-Agent", "")
            self.send_response(decide(ua))
            self.send_header("Content-Length", "0")
            self.end_headers()

        do_GET = do_HEAD = _respond

        def log_message(self, *_args):
            pass  # keep pytest output readable

    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f"http://127.0.0.1:{srv.server_port}/"


def _run(decide, robots=None):
    srv, url = _make_server(decide, robots)
    try:
        p = subprocess.run(
            ["bash", str(SCRIPT), url],
            capture_output=True, text=True, timeout=120,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin", "CRAWLER_TIMEOUT": "5"},
        )
        return p
    finally:
        srv.shutdown()
        srv.server_close()


def _training_row(stdout: str, name: str) -> str:
    """The TRAINING-section line for one crawler, or "" if absent.

    Scoped to the TRAINING block so a same-named row in another section cannot
    satisfy an assertion about training policy.
    """
    section = stdout.split("TRAINING class")[-1].split("CONTROLS")[0]
    for line in section.splitlines():
        if re.match(rf"\s+{re.escape(name)}\s", line):
            return line
    return ""


def _is_citation(ua: str) -> bool:
    return any(tok in ua for tok in CITATION_TOKENS)


def test_token_list_matches_the_scripts_own_array():
    # If the script gains a crawler and this list does not, the new one is
    # never exercised and the suite quietly under-tests the contract.
    src = SCRIPT.read_text(encoding="utf-8")
    block = re.search(r"CITATION_BOTS=\((.*?)\n\)", src, re.S).group(1)
    names = re.findall(r'"\s*([A-Za-z0-9-]+)\|', block)
    assert sorted(names) == sorted(CITATION_TOKENS)


@pytest.mark.parametrize("everything_ok", [200])
def test_all_reachable_exits_zero(everything_ok):
    p = _run(lambda ua: everything_ok)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "PASS" in p.stdout


@pytest.mark.parametrize("denial", [401, 403, 451])
def test_any_citation_crawler_denied_exits_one(denial):
    # One blocked crawler is enough. 401/403/451 are the policy denials the
    # script defines as "blocked"; a 403 on one bot must not be diluted by five
    # 200s, because a denial guarantees zero citation from that engine.
    def decide(ua):
        return denial if "PerplexityBot" in ua else 200
    p = _run(decide)
    assert p.returncode == 1, p.stdout + p.stderr


def test_all_citation_crawlers_denied_exits_one():
    p = _run(lambda ua: 403 if _is_citation(ua) else 200)
    assert p.returncode == 1, p.stdout + p.stderr


def test_server_error_is_inconclusive_not_a_block():
    # 5xx means the probe could not tell. Reporting that as a confirmed block
    # would send the operator to the Cloudflare dashboard to fix a system that
    # is not broken, which is the failure the tri-state exists to prevent.
    p = _run(lambda ua: 500)
    assert p.returncode == 2, p.stdout + p.stderr


def test_rate_limit_is_inconclusive_not_a_block():
    # 429 is transient rate limiting, not a policy decision.
    p = _run(lambda ua: 429 if _is_citation(ua) else 200)
    assert p.returncode == 2, p.stdout + p.stderr


def test_unreachable_target_is_inconclusive():
    # Nothing listening: an operational failure must not read as "reachable".
    p = subprocess.run(
        ["bash", str(SCRIPT), "http://127.0.0.1:1/"],
        capture_output=True, text=True, timeout=120,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "CRAWLER_TIMEOUT": "3"},
    )
    assert p.returncode == 2, p.stdout + p.stderr


def test_a_denial_outranks_an_inconclusive_elsewhere():
    # Mixed signal: one bot genuinely denied, another inconclusive. A confirmed
    # denial is real information and must not be downgraded to "could not tell"
    # by unrelated noise.
    def decide(ua):
        if "PerplexityBot" in ua:
            return 403
        if "Claude-User" in ua:
            return 500
        return 200
    p = _run(decide)
    assert p.returncode == 1, p.stdout + p.stderr


def test_controls_do_not_gate_the_exit_code():
    # Googlebot and the browser UA are reported as controls only. A blocked
    # control with the citation class reachable must still exit 0, or the gate
    # starts failing for a reason it explicitly says it does not judge.
    def decide(ua):
        if _is_citation(ua):
            return 200
        return 403
    p = _run(decide)
    assert p.returncode == 0, p.stdout + p.stderr


# --- TRAINING class: robots.txt directives, not HTTP status ------------------
#
# The TRAINING rows used to report only an HTTP status, which is the wrong
# instrument: training access is governed by robots.txt, and a training crawler
# that honours `Disallow: /` still returns 200 to this probe. These pin the
# directive reporting that replaced it.

# The NINE tokens Cloudflare's managed block names, enumerated from the LIVE
# file (`curl -s https://hoiboy.uk/robots.txt`), not from memory.
#
# This list held SIX for the life of the script, omitting Amazonbot,
# Applebot-Extended and CloudflareBrowserRenderingCrawler. That was tolerable
# while the training class was reported for information only. It stopped being
# tolerable the moment the training class started gating the exit code: a gate
# that never asks about a token cannot fail on it, so a regression on any of
# those three was structurally invisible to the standing watch built to catch
# exactly that. Ralph Tier 2 found it by diffing this list against the live
# managed block.
#
# Two of the nine (Google-Extended, Applebot-Extended) are robots.txt CONTROL
# TOKENS with no user-agent of their own, so they return 200 at the edge while
# being fully opted out. That is why the gate keys on the robots.txt directive
# and never on HTTP status.
TRAINING_TOKENS = [
    "GPTBot",
    "ClaudeBot",
    "CCBot",
    "Google-Extended",
    "meta-externalagent",
    "Bytespider",
    "Amazonbot",
    "Applebot-Extended",
    "CloudflareBrowserRenderingCrawler",
]

# The shape Cloudflare actually produces: the managed block is PREPENDED, then
# the origin's own file follows. When the two disagree the file carries two
# groups for one token. cuarchitects.co.uk served exactly this for GPTBot.
CONFLICTING_ROBOTS = """\
User-agent: *
Content-Signal: search=yes,ai-train=no,use=reference
Allow: /

User-agent: GPTBot
Disallow: /

User-agent: GPTBot
Disallow:
"""


def test_training_token_list_matches_the_scripts_own_array():
    # Mirrors the citation-class pin. A training crawler added to the script but
    # not here would never be exercised by any assertion below.
    src = SCRIPT.read_text(encoding="utf-8")
    block = re.search(r"TRAINING_BOTS=\((.*?)\n\)", src, re.S).group(1)
    names = re.findall(r'"\s*([A-Za-z0-9-]+)\|', block)
    assert sorted(names) == sorted(TRAINING_TOKENS)


def test_disallow_all_reports_opted_out():
    robots = "User-agent: GPTBot\nDisallow: /\n"
    p = _run(lambda ua: 200, robots=robots)
    assert "training opted out" in _training_row(p.stdout, "GPTBot"), p.stdout


def test_status_200_with_disallow_still_reports_opted_out():
    # The whole point of the change: a 200 next to Disallow:/ is the correct,
    # expected state, not a failure of the block.
    robots = "User-agent: GPTBot\nDisallow: /\n"
    p = _run(lambda ua: 200, robots=robots)
    row = _training_row(p.stdout, "GPTBot")
    assert "200" in row and "training opted out" in row, p.stdout


def test_contradictory_groups_report_conflict():
    p = _run(lambda ua: 200, robots=CONFLICTING_ROBOTS)
    assert "CONFLICT" in _training_row(p.stdout, "GPTBot"), p.stdout


def test_conflict_is_scoped_to_the_contradicted_token():
    # A conflict on one token must not smear across the others, or the report
    # cannot be used to find which entry to fix.
    #
    # Asserts BOTH directions on one fixture on purpose. The negative half alone
    # is vacuous: delete the whole feature and "CONFLICT" appears nowhere, so it
    # would still pass. Pairing it with the positive makes the test about
    # scoping rather than about absence.
    p = _run(lambda ua: 200, robots=CONFLICTING_ROBOTS)
    assert "CONFLICT" in _training_row(p.stdout, "GPTBot"), p.stdout
    assert "CONFLICT" not in _training_row(p.stdout, "ClaudeBot"), p.stdout


def test_real_allow_rule_against_disallow_all_resolves_to_allow():
    # RFC 9309 2.2.2: "If an allow rule and a disallow rule are equivalent, then
    # the allow rule SHOULD be used." `Allow: /` against `Disallow: /` is
    # therefore DETERMINATE, not a contradiction.
    #
    # This test previously asserted CONFLICT and so locked in the opposite of
    # the spec, which is why the defect survived six Ralph rounds: the suite was
    # defending it. The tie-break exists precisely to stop this pair being
    # ambiguous. Contrast test_conflicting_records_are_reported_as_conflict,
    # where the allow side is an EMPTY `Disallow:` and implementations really do
    # disagree.
    robots = "User-agent: GPTBot\nDisallow: /\nAllow: /\n"
    p = _run(lambda ua: 200, robots=robots)
    row = _training_row(p.stdout, "GPTBot")
    assert "2.2.2" in row, p.stdout
    assert "CONFLICT" not in row, p.stdout


def test_allow_rule_order_does_not_change_the_verdict():
    # Same pair, reversed. RFC 9309 rule precedence is order-independent, so the
    # verdict must not depend on which record was written first.
    robots = "User-agent: GPTBot\nAllow: /\nDisallow: /\n"
    p = _run(lambda ua: 200, robots=robots)
    row = _training_row(p.stdout, "GPTBot")
    assert "2.2.2" in row, p.stdout
    assert "CONFLICT" not in row, p.stdout


def test_scoped_disallow_is_not_reported_as_allowed():
    # `Disallow: /admin` is neither a full opt-out nor an absence of one.
    # Reporting it as "allowed (training NOT opted out)" asserts no restriction
    # exists while one is on record.
    robots = "User-agent: GPTBot\nDisallow: /admin\n"
    p = _run(lambda ua: 200, robots=robots)
    row = _training_row(p.stdout, "GPTBot")
    assert "scoped rules only" in row, p.stdout
    assert "NOT a full opt-out" in row, p.stdout


def test_a_later_groups_rules_do_not_leak_into_an_earlier_token():
    # The Allow: branch must close the User-agent run, or `member` survives into
    # the NEXT bot's group and that bot's Disallow:/ is attributed to this one.
    # Deleting `in_ua_run = 0` from the Allow: branch passed all 29 tests before
    # this existed, while producing a false CONFLICT on exactly this shape.
    robots = "User-agent: GPTBot\nAllow: /\nUser-agent: Bytespider\nDisallow: /\n"
    p = _run(lambda ua: 200, robots=robots)
    gpt = _training_row(p.stdout, "GPTBot")
    assert "CONFLICT" not in gpt, p.stdout
    assert "NOT opted out" in gpt, p.stdout
    assert "training opted out" in _training_row(p.stdout, "Bytespider"), p.stdout


def test_disallow_branch_also_closes_the_user_agent_run():
    # Sibling of the Allow: case above. Mutating the Disallow: branch's own
    # `in_ua_run = 0` survived all 32 tests while producing a false CONFLICT:
    # a LATER group's Allow: leaked back onto this token.
    robots = "User-agent: GPTBot\nDisallow: /\nUser-agent: Bytespider\nAllow: /\n"
    p = _run(lambda ua: 200, robots=robots)
    gpt = _training_row(p.stdout, "GPTBot")
    assert "CONFLICT" not in gpt, p.stdout
    assert "training opted out" in gpt, p.stdout


def test_blank_line_between_user_agent_lines_keeps_one_group():
    # RFC 9309: group = startgroupline *(startgroupline / emptyline)
    #                   *(rule / emptyline)
    # Empty lines are permitted BETWEEN consecutive user-agent lines, so both
    # tokens below share the one Disallow. Closing the run on a blank line would
    # split them and drop the rule for every token but the last.
    #
    # Pinned because a review read this as a rule leak and proposed "fixing" it;
    # the behaviour is specified, and without this test the mutation that breaks
    # it passes the whole suite.
    robots = "User-agent: GPTBot\n\nUser-agent: ClaudeBot\nDisallow: /\n"
    p = _run(lambda ua: 200, robots=robots)
    assert "training opted out" in _training_row(p.stdout, "GPTBot"), p.stdout
    assert "training opted out" in _training_row(p.stdout, "ClaudeBot"), p.stdout


def test_a_non_rule_directive_does_not_terminate_a_group():
    # RFC 9309 2.2.4: "Parsing of other records MUST NOT interfere with the
    # parsing of explicitly defined records in Section 2. For example, a
    # \"Sitemaps\" record MUST NOT terminate a group."
    #
    # Cloudflare's managed block really does ship `Content-Signal:` lines
    # between groups, so this is the live shape, not a contrived one. This test
    # previously asserted that the directive DOES close the run, locking in a
    # MUST NOT violation: GPTBot was dropped from the group it belongs to and
    # reported as ungoverned while it is in fact disallowed.
    robots = (
        "User-agent: GPTBot\n"
        "Content-Signal: search=yes,ai-train=no\n"
        "User-agent: Bytespider\n"
        "Disallow: /\n"
    )
    p = _run(lambda ua: 200, robots=robots)
    assert "training opted out" in _training_row(p.stdout, "GPTBot"), p.stdout
    assert "training opted out" in _training_row(p.stdout, "Bytespider"), p.stdout


def test_sitemap_record_does_not_terminate_a_group():
    # The exact example the RFC names, kept separate from Content-Signal so a
    # regression in either record type fails on its own name.
    robots = (
        "User-agent: GPTBot\n"
        "Sitemap: https://example.test/sitemap.xml\n"
        "User-agent: CCBot\n"
        "Disallow: /\n"
    )
    p = _run(lambda ua: 200, robots=robots)
    assert "training opted out" in _training_row(p.stdout, "GPTBot"), p.stdout
    assert "training opted out" in _training_row(p.stdout, "CCBot"), p.stdout


def test_scoped_allow_against_disallow_all_is_a_conflict():
    # `Allow: /public` under `Disallow: /` explicitly permits /public by RFC 9309
    # longest-match, with no tie-break needed. Reporting a clean opt-out here
    # asserts a total block over a file that grants access to a subtree.
    robots = "User-agent: GPTBot\nDisallow: /\nAllow: /public\n"
    p = _run(lambda ua: 200, robots=robots)
    row = _training_row(p.stdout, "GPTBot")
    assert "CONFLICT" in row, p.stdout
    assert "scoped Allow" in row, p.stdout


def test_scoped_allow_alone_is_not_a_full_opt_out():
    robots = "User-agent: GPTBot\nAllow: /public\n"
    p = _run(lambda ua: 200, robots=robots)
    assert "scoped rules only" in _training_row(p.stdout, "GPTBot"), p.stdout


def test_scoped_disallow_does_not_mask_a_full_opt_out():
    # A scoped rule alongside Disallow:/ must still report the full opt-out.
    robots = "User-agent: GPTBot\nDisallow: /admin\nDisallow: /\n"
    p = _run(lambda ua: 200, robots=robots)
    assert "training opted out" in _training_row(p.stdout, "GPTBot"), p.stdout


def test_wildcard_group_governs_a_token_with_no_group_of_its_own():
    # RFC 9309 2.2.1: "If no matching group exists, crawlers MUST obey the group
    # with a user-agent line with the \"*\" value, if present."
    #
    # The old version of this test used a PERMISSIVE wildcard (`Allow: /`), so
    # "no group" and the true answer coincided and the assertion passed whether
    # or not the wildcard was ever evaluated. It was vacuous by fixture choice.
    # A RESTRICTIVE wildcard is the discriminating case: a site-wide opt-out is
    # the most common way to write a blanket training block, and reporting it as
    # "no group" told the operator nothing governed the token.
    robots = "User-agent: *\nDisallow: /\n"
    p = _run(lambda ua: 200, robots=robots)
    row = _training_row(p.stdout, "GPTBot")
    assert "via * group" in row, p.stdout
    assert "training opted out" in row, p.stdout


def test_wildcard_group_reports_permissive_content_as_not_opted_out():
    # The mirror of the above: a permissive wildcard must be reported as NOT an
    # opt-out, rather than silently reading as one.
    robots = "User-agent: *\nDisallow:\n"
    p = _run(lambda ua: 200, robots=robots)
    row = _training_row(p.stdout, "GPTBot")
    assert "via * group" in row, p.stdout
    assert "NOT opted out" in row, p.stdout


def test_own_group_beats_the_wildcard_group():
    # A token's own group wins over `*` (2.2.1 falls back to `*` only when no
    # matching group exists). Without this, a restrictive wildcard could mask a
    # permissive token-specific group and report a block that is not there.
    robots = "User-agent: *\nDisallow: /\n\nUser-agent: GPTBot\nDisallow:\n"
    p = _run(lambda ua: 200, robots=robots)
    row = _training_row(p.stdout, "GPTBot")
    assert "via * group" not in row, p.stdout
    assert "NOT opted out" in row, p.stdout


def test_no_group_and_no_wildcard_is_reported_as_ungoverned():
    robots = "User-agent: SomeOtherBot\nDisallow: /\n"
    p = _run(lambda ua: 200, robots=robots)
    assert "nothing governs this token" in _training_row(p.stdout, "GPTBot"), p.stdout


def test_empty_disallow_reports_not_opted_out():
    robots = "User-agent: GPTBot\nDisallow:\n"
    p = _run(lambda ua: 200, robots=robots)
    assert "NOT opted out" in _training_row(p.stdout, "GPTBot"), p.stdout


def test_consecutive_user_agent_lines_share_one_group():
    # RFC 9309: a run of User-agent lines opens ONE group. Parsing that as
    # separate groups would drop the rule for every token but the last.
    robots = "User-agent: GPTBot\nUser-agent: ClaudeBot\nDisallow: /\n"
    p = _run(lambda ua: 200, robots=robots)
    assert "training opted out" in _training_row(p.stdout, "GPTBot"), p.stdout
    assert "training opted out" in _training_row(p.stdout, "ClaudeBot"), p.stdout


def test_user_agent_token_matching_is_case_insensitive():
    # RFC 9309 says the product token is matched case-insensitively.
    robots = "User-agent: gptbot\nDisallow: /\n"
    p = _run(lambda ua: 200, robots=robots)
    assert "training opted out" in _training_row(p.stdout, "GPTBot"), p.stdout


def test_commented_out_directive_is_not_honoured():
    robots = "User-agent: GPTBot\n# Disallow: /\nDisallow:\n"
    p = _run(lambda ua: 200, robots=robots)
    row = _training_row(p.stdout, "GPTBot")
    assert "NOT opted out" in row, p.stdout
    assert "CONFLICT" not in row, p.stdout


def test_trailing_comment_is_stripped_from_the_directive_value():
    # This is the case that actually needs the comment strip. A leading "#" is
    # already rejected by the directive pattern, so it cannot detect a parser
    # that never strips. Here the value compares as "/  # blocked per policy"
    # unless comments are removed, and the opt-out silently disappears.
    robots = "User-agent: GPTBot\nDisallow: /  # blocked per policy\n"
    p = _run(lambda ua: 200, robots=robots)
    assert "training opted out" in _training_row(p.stdout, "GPTBot"), p.stdout


def test_unavailable_robots_is_reported_not_guessed():
    p = _run(lambda ua: 200)  # robots=None -> 404
    assert "unavailable" in _training_row(p.stdout, "GPTBot"), p.stdout
    assert "robots.txt could not be fetched" in p.stdout, p.stdout


def test_conflict_alone_does_not_gate_the_exit_code():
    # CONFLICT is ambiguous, not open: contradictory records whose resolution
    # varies by parser, where the measured live outcome is still blocked. It is
    # reported and deliberately not failed, so the gate does not cry wolf on
    # drift that is not yet an exposure.
    #
    # The fixture isolates that one variable. CONFLICTING_ROBOTS is NOT usable
    # here: it reproduces the live cuarchitects shape, whose `*` group carries
    # `Allow: /`, so the five tokens without their own group are genuinely not
    # opted out and the training gate fires on them for a real reason. Using it
    # would have tested the wrong thing and hidden which condition turned the
    # gate red. Here every token is opted out; GPTBot additionally carries the
    # contradictory pair.
    robots = "".join(
        f"User-agent: {name}\nDisallow: /\n\n"
        for name in TRAINING_TOKENS if name != "GPTBot"
    ) + "User-agent: GPTBot\nDisallow: /\n\nUser-agent: GPTBot\nDisallow:\n"
    p = _run(lambda ua: 200, robots=robots)
    assert "CONFLICT" in _training_row(p.stdout, "GPTBot"), p.stdout
    assert p.returncode == 0, p.stdout + p.stderr


def test_the_live_cuarchitects_shape_reports_its_unprotected_tokens():
    # The real drift on cuarchitects.co.uk: a `*` group that allows everything,
    # one token with contradictory records, and nothing covering the rest. The
    # gate must name the genuinely-unprotected tokens rather than reporting only
    # the eye-catching CONFLICT, because the tokens with no opt-out at all are
    # the larger exposure and the ones a reader would otherwise miss.
    p = _run(lambda ua: 200, robots=CONFLICTING_ROBOTS)
    assert "CONFLICT" in _training_row(p.stdout, "GPTBot"), p.stdout
    assert p.returncode == 1, p.stdout + p.stderr
    assert "ClaudeBot" in p.stderr, p.stderr


def test_training_collapse_turns_the_gate_red():
    # THE REGRESSION THIS GATE EXISTS FOR. A robots.txt serving zero training
    # groups is a total collapse of the training block. The old contract gated
    # the exit code on the CITATION class alone, so this exact input printed
    # PASS and exited 0, and the weekly workflow stayed green. The standing
    # watch on the operator's actual ask ("i want to block that") could not
    # fail, which is not a watch.
    robots = "User-agent: *\nDisallow:\n"
    p = _run(lambda ua: 200, robots=robots)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "NOT opted out in robots.txt" in p.stderr, p.stderr


def test_training_gate_does_not_fire_on_a_token_that_sends_no_user_agent():
    # Google-Extended and Applebot-Extended are robots.txt CONTROL TOKENS with
    # no user-agent of their own, so they correctly return 200 at the edge while
    # being fully opted out. Gating on HTTP status rather than on the directive
    # would fail this site forever for a condition that is neither fixable nor
    # wrong. All six training tokens are opted out here; every one returns 200.
    robots = "".join(
        f"User-agent: {name}\nDisallow: /\n\n"
        for name in TRAINING_TOKENS
    )
    p = _run(lambda ua: 200, robots=robots)
    assert p.returncode == 0, p.stdout + p.stderr


def test_training_gate_is_skipped_when_robots_is_unavailable():
    # No data is not a pass and not a fail. A fetch failure must not manufacture
    # either verdict for the training class.
    p = _run(lambda ua: 200, robots=None)
    assert "training gate is skipped" in p.stdout, p.stdout


def test_robots_is_readable_even_when_crawlers_are_blocked():
    # The fixture must be able to express "citation blocked, robots readable",
    # which is the state that produced this issue in the first place.
    robots = "User-agent: GPTBot\nDisallow: /\n"
    p = _run(lambda ua: 403 if ua else 200, robots=robots)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "training opted out" in _training_row(p.stdout, "GPTBot"), p.stdout
