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


def _make_server(decide):
    """Serve HEAD/GET with a status chosen by `decide(user_agent) -> int`."""
    class Handler(http.server.BaseHTTPRequestHandler):
        def _respond(self):
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


def _run(decide):
    srv, url = _make_server(decide)
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
