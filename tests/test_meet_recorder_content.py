"""Source-validation regression guard for content/private/tools/meet-recorder/index.md.

Full-site Hugo build takes >4 min on this corpus (Cloudflare Pages is the
production rendering path; AC 1.20 is the operator-gated end-to-end deploy
check). This test pins the load-bearing markdown invariants so a
regression in the verbatim consent script, attestation checkboxes,
engagement gate, or JS-script tag would fail loud before a re-deploy.

Validates:
  * YAML frontmatter parses + has the noindex/sitemap-disable safety flags
  * Verbatim consent script literal is intact (HOIBOY AI LTD + hoiboy.uk +
    UK GDPR Article 17 references all present)
  * 13 named <section> elements covering the 10 pre-meeting checklist +
    engagement gate + Article 9 attestations + recording fields
  * meet-recorder.js is referenced exactly once at the page bottom
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


PAGE = (
    Path(__file__).resolve().parent.parent
    / "content"
    / "private"
    / "tools"
    / "meet-recorder"
    / "index.md"
)


@pytest.fixture(scope="module")
def page_text() -> str:
    return PAGE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def frontmatter_and_body(page_text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", page_text, re.DOTALL)
    assert m, "page is missing --- frontmatter delimiters"
    try:
        import yaml
    except ImportError:
        pytest.skip("pyyaml not installed; install via pip install pyyaml")
    return yaml.safe_load(m.group(1)), m.group(2)


def test_frontmatter_safety_flags(frontmatter_and_body):
    fm, _body = frontmatter_and_body
    assert fm.get("noindex") is True, "noindex must be true for operator-only tool"
    assert fm.get("sitemap", {}).get("disable") is True, "sitemap must be disabled"
    assert fm.get("hideDate") is True, "hideDate true (no public timestamp)"


def test_verbatim_consent_script_intact(frontmatter_and_body):
    _fm, body = frontmatter_and_body
    required_substrings = [
        "data-verbal-consent-script",
        "starting the recording",
        "transcribed with the help of AI tools",
        "HOIBOY AI LTD as data controller",
        "hello@hoiboy.uk",
        "UK GDPR Article 17",
        "Is everyone here happy for me to continue recording",
    ]
    for needle in required_substrings:
        assert needle in body, f"verbatim consent script missing required substring: {needle!r}"


def test_section_count_and_engagement_gate(frontmatter_and_body):
    _fm, body = frontmatter_and_body
    sections = re.findall(r'<section\s+id="([^"]+)"', body)
    assert len(sections) >= 11, (
        f"expected >=11 named sections covering checklist + gates, got {len(sections)}: {sections}"
    )
    assert "section-engagement" in sections, "engagement-letter gate section missing"

    # Article 9 stack-config attestations live in the meet-recorder UI
    # (consulting-ops#8 AC 1.13).
    assert "attestation-claude-art9" in body, "Anthropic-training-opt-out attestation missing"
    assert "attestation-meet-art9" in body, "Meet face-recognition-disabled attestation missing"


def test_meet_recorder_js_referenced_exactly_once(frontmatter_and_body):
    _fm, body = frontmatter_and_body
    matches = re.findall(r'<script\s+src="[^"]*meet-recorder\.js"', body)
    assert len(matches) == 1, (
        f"meet-recorder.js script tag must appear exactly once; got {len(matches)}: {matches}"
    )
