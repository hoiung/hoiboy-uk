#!/usr/bin/env python3
"""Unit tests for the pure helpers in `scripts/check_agit_form_counter.py`.

hoiboy-uk#57.

Why this file exists. `check_agit_form_counter.py` is the browser-computed gate
for the story counter, and it runs only in `scripts/pre-publish.sh`, the one lane
with Chromium. That is deliberate, but it leaves every helper inside it reachable
ONLY through a Playwright run that never happens in CI. `ci.yml` records that
exact gap being found on the CTA gate at Ralph Tier 2: the helpers that decide
what "correct" MEANS had no automatic coverage while the browser half was
carefully wired. This issue does not re-create it.

These helpers are where a silent wrong answer would live. `state_for` off by one
would have the gate expect red at 1200 and pass a counter that tells a member to
keep writing when they are already done. `classify_notice` collapsing its
three-way answer would let the Turnstile complaint stand in for the length
complaint, reporting a working gate that never fired. Neither needs a browser.

The browser half itself is deliberately not tested here: mocking Playwright
would assert that the mock works. That half is covered by the real run.

Run:  python3 -m pytest scripts/test_check_agit_form_counter.py -q
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "scripts" / "check_agit_form_counter.py"

_spec = importlib.util.spec_from_file_location("check_agit_form_counter", GATE)
gate = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gate
_spec.loader.exec_module(gate)


# --------------------------------------------------------------------------
# state_for: which colour the counter should be wearing
# --------------------------------------------------------------------------

@pytest.mark.parametrize("count,expected", [
    (0, "short"),
    (1, "short"),
    (1198, "short"),
    (1199, "short"),      # one short is still short
    (1200, "met"),        # AT the minimum is long enough, not one more
    (1201, "met"),
    (8000, "met"),
])
def test_state_for_flips_exactly_at_the_minimum(count, expected):
    assert gate.state_for(count) == expected


def test_state_for_boundary_is_inclusive():
    # Stated separately from the table because this single comparison is the
    # difference between "keep writing" and "you are done" for every member who
    # lands exactly on the number the form told them to hit.
    assert gate.state_for(gate.MINIMUM) == "met"
    assert gate.state_for(gate.MINIMUM - 1) == "short"


def test_state_for_honours_an_explicit_minimum():
    assert gate.state_for(500, minimum=500) == "met"
    assert gate.state_for(499, minimum=500) == "short"


# --------------------------------------------------------------------------
# classify_notice: WHICH complaint the form is making
# --------------------------------------------------------------------------

def test_classify_notice_recognises_the_length_complaint():
    text = ("Your story needs at least 1200 characters so there is enough to work with. "
            "You have written 1199 so far, so keep going.")
    assert gate.classify_notice(text) == "length"


def test_classify_notice_separates_the_turnstile_complaint_from_the_length_one():
    # The long-story case PASSES on 'other'. If this collapsed to a boolean
    # "was something shown", the verification nudge would satisfy the assertion
    # for the short-story case too, and a length gate that never fired would
    # report as working.
    assert gate.classify_notice(
        "Please complete the verification check just above the button, then hit Send.") == "other"
    assert gate.classify_notice(
        "Your two email addresses do not match. Please check them.") == "other"


@pytest.mark.parametrize("text", [None, "", "   ", "\n\t "])
def test_classify_notice_reports_no_notice_at_all(text):
    assert gate.classify_notice(text) == "none"


def test_classify_notice_is_three_way_not_boolean():
    # The three answers must be distinguishable, which is the property the
    # caller depends on when it expects 'other' rather than 'not length'.
    assert len({gate.classify_notice("needs at least 1200 characters"),
                gate.classify_notice("some other problem"),
                gate.classify_notice(None)}) == 3


# --------------------------------------------------------------------------
# hex_to_rgb_string: the format Chromium actually reports
# --------------------------------------------------------------------------

@pytest.mark.parametrize("hex_value,expected", [
    ("#b3261e", "rgb(179, 38, 30)"),      # the shipped short/red, light theme
    ("#166534", "rgb(22, 101, 52)"),      # the shipped met/green, light theme
    ("#f28b82", "rgb(242, 139, 130)"),    # short/red, dark theme
    ("#6fdd8b", "rgb(111, 221, 139)"),    # met/green, dark theme
    ("#000000", "rgb(0, 0, 0)"),
    ("#ffffff", "rgb(255, 255, 255)"),
])
def test_hex_to_rgb_string(hex_value, expected):
    assert gate.hex_to_rgb_string(hex_value) == expected


@pytest.mark.parametrize("bad", ["var(--accent)", "red", "rgb(1,2,3)", "#abc", "#12345", ""])
def test_hex_to_rgb_string_fails_loud_on_anything_it_cannot_resolve(bad):
    # Exit 2 rather than a ValueError traceback: this gate compares against a
    # browser-computed value, so a token it cannot resolve means it cannot state
    # what it would assert, and that is a "cannot run", not a failure.
    with pytest.raises(SystemExit) as exc:
        gate.hex_to_rgb_string(bad)
    assert exc.value.code == 2


# --------------------------------------------------------------------------
# split_on_dark_query + counter_colours: reading expectations off the page
# --------------------------------------------------------------------------

PAGE_CSS = """<style>
/* a comment naming #fafafa and #141414, which are BACKGROUNDS, not counter colours */
.agit-form-wrap .agit-count { font-size: .9em; }
.agit-form-wrap .agit-count.is-short { color: #b3261e; }
.agit-form-wrap .agit-count.is-met { color: #166534; }
@media (prefers-color-scheme: dark) {
  .agit-form-wrap .agit-count.is-short { color: #f28b82; }
  .agit-form-wrap .agit-count.is-met { color: #6fdd8b; }
}
</style>"""


def test_counter_colours_reads_both_schemes_off_the_page():
    got = gate.counter_colours(PAGE_CSS)
    assert got == {
        "light": {"short": "rgb(179, 38, 30)", "met": "rgb(22, 101, 52)"},
        "dark": {"short": "rgb(242, 139, 130)", "met": "rgb(111, 221, 139)"},
    }


def test_counter_colours_ignores_hexes_that_are_only_mentioned_in_a_comment():
    # The rationale comment beside these rules names both page backgrounds. One
    # of them fails contrast against itself, so scoring it would fail a correct
    # page; and #fafafa is not a counter colour in any case.
    got = gate.counter_colours(PAGE_CSS)
    for scheme in got.values():
        assert "rgb(250, 250, 250)" not in scheme.values()
        assert "rgb(20, 20, 20)" not in scheme.values()


def test_split_on_dark_query_brace_matches_rather_than_lazy_regexing():
    # A lazy {.*?} stops at the FIRST nested close brace, which would leave the
    # dark 'met' rule in the light half. The gate would then expect the light
    # colour in dark mode and fail against a correct page.
    light, dark = gate.split_on_dark_query(PAGE_CSS)
    assert "#f28b82" in dark and "#6fdd8b" in dark
    assert "#f28b82" not in light and "#6fdd8b" not in light
    assert "#b3261e" in light and "#166534" in light


def test_split_on_dark_query_with_no_dark_block_returns_everything_as_light():
    css = ".agit-count.is-short { color: #b3261e; }"
    light, dark = gate.split_on_dark_query(css)
    assert light == css
    assert dark == ""


def test_counter_colours_fails_loud_when_a_theme_is_missing_a_state():
    # A page that lost its dark block must be a LOUD failure. Silently returning
    # only the light colours would leave the browser half comparing dark-mode
    # renders against light-mode expectations, or skipping them entirely.
    half = """<style>
.agit-count.is-short { color: #b3261e; }
.agit-count.is-met { color: #166534; }
</style>"""
    with pytest.raises(SystemExit) as exc:
        gate.counter_colours(half)
    assert exc.value.code == 2


def test_counter_colours_fails_loud_with_no_style_block_at_all():
    with pytest.raises(SystemExit) as exc:
        gate.counter_colours("<html><body>no styles here</body></html>")
    assert exc.value.code == 2


def test_the_gate_minimum_matches_the_shipped_client_threshold():
    # The gate carries its own MINIMUM so the pure helpers stay callable without
    # a browser or a build. That copy has to be checked against the source of
    # truth, or the gate can drift into asserting the wrong number confidently.
    shipped = (ROOT / "static" / "js" / "agit-form.js").read_text(encoding="utf-8")
    import re
    match = re.search(r"var STORY_MIN = (\d+);", shipped)
    assert match, "STORY_MIN not found in static/js/agit-form.js"
    assert int(match.group(1)) == gate.MINIMUM
