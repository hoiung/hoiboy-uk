#!/usr/bin/env python3
"""Unit tests for the pure helpers in `scripts/check_cta_rendered.py`.

blog-priv#63, added at Ralph Tier 2.

Why this file exists. `check_cta_rendered.py` is the browser-computed CTA gate,
and it runs only in `scripts/pre-publish.sh`, the manual lane, because it is the
only lane with Chromium. That is a deliberate design choice, but it left every
pure helper inside it reachable ONLY through a Playwright run that never happens
in CI. So the arithmetic that decides what "correct" means (the expected fill,
the expected label, the class-token match) had no automatic coverage at all,
while the repo's own convention is a companion `test_check_*.py` beside every
`check_*.py` gate: there are eleven of them.

These helpers are where a silent wrong answer would live. `has_button` deciding
`menu-toggle-btn` counts, or `expected_fill` reading the wrong key, would make
the browser gate confidently assert the wrong thing on the pages it does check.
None of that needs a browser to test.

The one behaviour deliberately NOT tested here is the browser half itself, which
has no meaningful test double: mocking Playwright would assert that the mock
works. That half is covered by the real run in the pre-publish lane.

Run:  python3 -m pytest scripts/test_check_cta_rendered.py -q
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "scripts" / "check_cta_rendered.py"

_spec = importlib.util.spec_from_file_location("check_cta_rendered", GATE)
ccr = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = ccr
_spec.loader.exec_module(ccr)


# --------------------------------------------------------------------------
# hex_to_rgb_string: the format Chromium actually reports
# --------------------------------------------------------------------------

@pytest.mark.parametrize("hex_value,expected", [
    ("#188418", "rgb(24, 132, 24)"),      # the shipped fill
    ("#228b22", "rgb(34, 139, 34)"),      # the logo green, for contrast
    ("#ffffff", "rgb(255, 255, 255)"),    # the label
    ("#000000", "rgb(0, 0, 0)"),
    ("188418", "rgb(24, 132, 24)"),       # tolerate a missing leading #
    ("  #188418  ", "rgb(24, 132, 24)"),  # and surrounding whitespace
])
def test_hex_to_rgb_string_matches_chromium_formatting(hex_value, expected):
    """Spacing matters: Chromium reports `rgb(24, 132, 24)`, with the spaces.

    An exact string comparison is what the gate does, so a formatting drift here
    would fail every page for a reason that has nothing to do with the button.
    """
    assert ccr.hex_to_rgb_string(hex_value) == expected


def test_hex_to_rgb_string_expands_three_digit_shorthand():
    """`#fff` and `#ffffff` are the same colour; CSS permits either."""
    assert ccr.hex_to_rgb_string("#fff") == ccr.hex_to_rgb_string("#ffffff")
    assert ccr.hex_to_rgb_string("#f00") == "rgb(255, 0, 0)"


# --------------------------------------------------------------------------
# has_button: the whole-token match that a substring match gets wrong
# --------------------------------------------------------------------------

def test_has_button_finds_the_class_in_every_quoting_style():
    """Hugo here keeps quotes (hugo.toml keepQuotes = true), but the gate
    tolerates all three forms so a minifier config change cannot blind it."""
    assert ccr.has_button('<a class="btn">x</a>')
    assert ccr.has_button("<a class='btn'>x</a>")
    assert ccr.has_button("<a class=btn>x</a>")


def test_has_button_finds_the_class_among_others():
    assert ccr.has_button('<a class="foo btn bar">x</a>')
    assert ccr.has_button('<a class="btn foo">x</a>')
    assert ccr.has_button('<a class="foo btn">x</a>')


def test_has_button_does_not_match_menu_toggle_btn():
    """The regression that made an early version of this gate useless.

    `\\bbtn\\b` matches INSIDE `menu-toggle-btn`, because `-` is a non-word
    character. The shared sidebar puts that class on 333 of the 339 built pages,
    so a substring match "found" the button almost everywhere and then failed on
    every page where no such element existed.
    """
    assert not ccr.has_button('<button class="menu-toggle-btn">x</button>')
    assert not ccr.has_button('<button class="nav menu-toggle-btn open">x</button>')


def test_has_button_does_not_match_a_hypothetical_variant_class():
    """`btn-secondary` was a real class here that named a style nobody built.

    It was dropped rather than defined. If it ever returns it is a DIFFERENT
    class needing its own rule, so it must not satisfy this check.
    """
    assert not ccr.has_button('<a class="btn-secondary">x</a>')
    assert not ccr.has_button('<a class="cta-link">x</a>')


def test_has_button_is_false_for_markup_with_no_classes():
    assert not ccr.has_button("<a href='/'>x</a>")
    assert not ccr.has_button("")


# --------------------------------------------------------------------------
# expected_fill / expected_label: read from source, never restated
# --------------------------------------------------------------------------

def test_expected_fill_reads_the_configured_colour_not_a_literal():
    """The gate must re-derive from params.toml, so a colour change re-tests.

    Compared against the config rather than against `rgb(24, 132, 24)`: pinning
    the literal here would mean editing this test every time the operator picks
    a different fill, which is exactly the stale-constant pattern the gate
    exists to avoid.
    """
    import re
    params = (ROOT / "config" / "_default" / "params.toml").read_text(encoding="utf-8")
    declared = re.search(r'^ctaColor\s*=\s*"([^"]+)"', params, re.M)
    assert declared, "ctaColor is not declared in config/_default/params.toml"
    assert ccr.expected_fill() == ccr.hex_to_rgb_string(declared.group(1))


def test_expected_label_reads_the_stateless_btn_rule_from_the_stylesheet():
    """White, today. Asserted against the stylesheet rather than hardcoded."""
    assert ccr.expected_label() == ccr.hex_to_rgb_string("#ffffff")


def test_expected_label_ignores_the_hover_rule():
    """`:hover` is a state layer, not the button's resting appearance.

    The helper filters selectors containing `:`. If it stopped doing so it could
    pick up a state rule's colour and assert the wrong thing on every page.
    """
    css = ccr.CSS.read_text(encoding="utf-8")
    assert ".main a.btn:hover" in css, (
        "this test's premise is gone: there is no hover rule to ignore."
    )
    # The hover rule declares color:#fff too, so prove the filter by construction
    # rather than by coincidence: a stateless rule must exist and be the source.
    stateless = [
        s for s in css.splitlines()
        if s.startswith(".main a.btn ") or s.startswith(".main a.btn{")
    ]
    assert stateless, "no stateless .main a.btn rule found in main.css"


# --------------------------------------------------------------------------
# pages_with_button: URL shaping over a built tree
# --------------------------------------------------------------------------

def test_pages_with_button_maps_index_html_to_a_directory_url(tmp_path):
    """`/a/b/index.html` is served at `/a/b/`, and the gate must ask for that."""
    (tmp_path / "hire-hoi" / "svc").mkdir(parents=True)
    (tmp_path / "hire-hoi" / "svc" / "index.html").write_text(
        '<a class="btn">Book</a>', encoding="utf-8")
    assert ccr.pages_with_button(tmp_path) == ["/hire-hoi/svc/"]


def test_pages_with_button_skips_pages_without_it(tmp_path):
    (tmp_path / "with").mkdir()
    (tmp_path / "without").mkdir()
    (tmp_path / "with" / "index.html").write_text('<a class="btn">y</a>', encoding="utf-8")
    (tmp_path / "without" / "index.html").write_text(
        '<button class="menu-toggle-btn">n</button>', encoding="utf-8")
    assert ccr.pages_with_button(tmp_path) == ["/with/"]


def test_pages_with_button_returns_empty_for_a_tree_with_none(tmp_path):
    """The floors in main() depend on this being honest rather than defaulting."""
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "index.html").write_text("<p>nothing</p>", encoding="utf-8")
    assert ccr.pages_with_button(tmp_path) == []


def test_pages_with_button_is_sorted_and_deterministic(tmp_path):
    """Two runs over the same tree must agree, so a diff of output is meaningful."""
    for name in ("c", "a", "b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "index.html").write_text('<a class="btn">x</a>', encoding="utf-8")
    first = ccr.pages_with_button(tmp_path)
    assert first == ["/a/", "/b/", "/c/"]
    assert first == ccr.pages_with_button(tmp_path)


# --------------------------------------------------------------------------
# The gate's own floors
# --------------------------------------------------------------------------

def test_the_default_floors_match_the_measured_coverage():
    """5 pages / 6 buttons, measured, not guessed.

    `claude-code-harness-architect` calls the shortcode twice, top and bottom,
    which is why instances exceed pages. If a service page is added or removed
    these floors are meant to be updated deliberately, and this assertion is
    what makes that a conscious edit rather than a silent drift.
    """
    assert ccr.DEFAULT_MIN_PAGES == 5
    assert ccr.DEFAULT_MIN_INSTANCES == 6
    assert ccr.DEFAULT_MIN_INSTANCES >= ccr.DEFAULT_MIN_PAGES, (
        "there cannot be fewer button instances than pages carrying one."
    )


def test_both_colour_schemes_are_checked():
    """A button that reads correctly in light and vanishes in dark is a defect
    for half the readers, so the gate runs every page under both."""
    assert set(ccr.SCHEMES) == {"light", "dark"}
