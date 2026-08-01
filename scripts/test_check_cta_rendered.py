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


def test_expected_label_ignores_the_hover_rule(tmp_path, monkeypatch):
    """`:hover` is a state layer, not the button's resting appearance.

    `expected_label` filters selectors containing `:`. Without that filter it
    returns whichever matching rule comes FIRST in file order, which could be a
    state rule, and then the browser gate asserts the wrong resting colour on
    every page it checks.

    Asserted against a SYNTHETIC stylesheet, not the shipped one, and that is
    the whole point of this test. The first version of it read `main.css` and
    asserted substrings of the raw text without ever calling `expected_label` --
    so deleting the filter outright left all 21 tests passing (Ralph round 2,
    proven by mutation). Two properties of the real stylesheet hid the defect:
    the stateless rule is declared BEFORE the hover rule, and both happen to
    declare the same `#fff`. Either one alone makes the filter's removal
    invisible. The synthetic sheet below inverts both -- hover first, and a
    different colour -- so the two branches cannot return the same answer.
    """
    css = tmp_path / "synthetic.css"
    css.write_text(
        ".main a.btn:hover { color: #ff0000; }\n"
        ".main a.btn { color: #ffffff; }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ccr, "CSS", css)
    assert ccr.expected_label() == ccr.hex_to_rgb_string("#ffffff"), (
        "expected_label picked up the :hover rule. Its selector filter "
        '(`":" not in s`) is what skips state layers; without it the first '
        "matching rule in file order wins."
    )


def test_expected_label_ignores_a_rule_that_exists_only_inside_a_comment(tmp_path, monkeypatch):
    """`expected_label` strips CSS comments before scanning, and must keep doing so.

    Its rule scan is `([^{}]+)\\{([^{}]*)\\}` over the whole file, which cannot
    tell a real declaration from one quoted inside `/* ... */`. Nothing tested
    that: removing the `COMMENTS.sub` call entirely left all 22 tests passing,
    because none of the 20 comments in the shipped `main.css` happens to contain
    a brace today. Silently untested, not silently safe.

    Not a hypothetical risk in this file specifically. The block immediately
    above `.main a.btn` is a long WHY-comment full of colour and contrast prose,
    which is exactly where someone eventually pastes an example rule. If that
    example were read as real, the gate would compute the wrong label colour and
    then assert it against every page, in a check whose entire purpose is WCAG
    contrast.

    NOTE THE COMMENT TEXT: it deliberately contains no colon. The first draft of
    this test said "do not copy:" and the mutation slipped past, because the
    state-layer filter (`":" not in s`) rejected the commented rule for an
    unrelated reason, so the test passed without comment-stripping ever running.
    A colon anywhere in the commented selector makes this assertion vacuous.
    """
    css = tmp_path / "synthetic.css"
    css.write_text(
        "/* Example, do not copy - .main a.btn { color: #ff0000; } */\n"
        ".main a.btn { color: #ffffff; }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ccr, "CSS", css)
    assert ccr.expected_label() == ccr.hex_to_rgb_string("#ffffff"), (
        "expected_label read a rule out of a CSS comment. The COMMENTS.sub call "
        "is what stops the brace-scan treating commented examples as real."
    )


def test_the_shipped_stylesheet_still_has_a_hover_rule_worth_ignoring():
    """The premise anchor for the test above, kept honest about what it proves.

    The synthetic-sheet test proves the FILTER works. It cannot notice that the
    hover rule was deleted from `main.css`, at which point the filter guards
    nothing and the test above passes for a condition that no longer exists.
    This one watches the real file, and is deliberately the only assertion here
    that does.
    """
    css = ccr.CSS.read_text(encoding="utf-8")
    assert ".main a.btn:hover" in css, (
        "assets/css/main.css no longer declares a `.main a.btn:hover` rule, so "
        "expected_label's state-layer filter now has nothing to skip. Either "
        "restore the hover state or retire the filter and its test together."
    )


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
    """6 pages / 7 buttons, measured, not guessed.

    `claude-code-harness-architect` calls the shortcode twice, top and bottom,
    which is why instances exceed pages. If a service page is added or removed
    these floors are meant to be updated deliberately, and this assertion is
    what makes that a conscious edit rather than a silent drift.

    hoiboy-uk#54 is the first time that drift-catch actually fired: adding
    ai-adoption-talk as a sixth CTA-bearing page moved the coverage to 6/7, and
    landing the constants without this assertion would have flipped a green,
    CI-wired test to failing.

    "CTA-bearing", not "service": ai-adoption-talk is the FIFTH service. The
    sixth CTA-bearing page is work-with-hoi, which check_landing_sync.py's
    NON_SERVICE_SLUGS classifies as "not an offer". check_cta_rendered.py's own
    comment says the same; this docstring said "sixth service page" until the
    two were reconciled.
    """
    assert ccr.DEFAULT_MIN_PAGES == 6
    assert ccr.DEFAULT_MIN_INSTANCES == 7
    assert ccr.DEFAULT_MIN_INSTANCES >= ccr.DEFAULT_MIN_PAGES, (
        "there cannot be fewer button instances than pages carrying one."
    )


def test_both_colour_schemes_are_checked():
    """A button that reads correctly in light and vanishes in dark is a defect
    for half the readers, so the gate runs every page under both."""
    assert set(ccr.SCHEMES) == {"light", "dark"}


# --------------------------------------------------------------------------
# expected_label anchors to the CTA's own selector
# --------------------------------------------------------------------------

def test_expected_label_ignores_a_btn_rule_that_cannot_match_the_cta(tmp_path, monkeypatch):
    """The CTA is an `<a class="btn">`. A rule not matching an anchor is not it.

    `.btn` is an ordinary class name to reuse. A scroll-to-top or copy-code
    button declared earlier in the sheet used to win purely on file order, and
    the browser gate then asserted that colour against the real CTA on every
    page (Ralph round 6, proven by construction).
    """
    css = tmp_path / "synthetic.css"
    css.write_text(
        ".scroll-top button.btn { color: #ff0000; }\n"
        ".main a.btn { color: #ffffff; }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ccr, "CSS", css)
    assert ccr.expected_label() == ccr.hex_to_rgb_string("#ffffff")


def test_expected_label_dies_when_two_anchor_rules_disagree(tmp_path, monkeypatch):
    """Which rule wins is a cascade question. The gate refuses to guess it."""
    css = tmp_path / "synthetic.css"
    css.write_text(
        ".footer a.btn { color: #ff0000; }\n"
        ".main a.btn { color: #ffffff; }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ccr, "CSS", css)
    with pytest.raises(SystemExit):
        ccr.expected_label()


def test_expected_label_dies_when_no_anchor_rule_exists(tmp_path, monkeypatch):
    css = tmp_path / "synthetic.css"
    css.write_text(".scroll-top button.btn { color: #ff0000; }\n", encoding="utf-8")
    monkeypatch.setattr(ccr, "CSS", css)
    with pytest.raises(SystemExit):
        ccr.expected_label()


def test_agreeing_duplicate_anchor_rules_are_not_an_error(tmp_path, monkeypatch):
    """Only DISAGREEMENT is fatal; restating the same colour is harmless."""
    css = tmp_path / "synthetic.css"
    css.write_text(
        ".main a.btn { color: #ffffff; }\n"
        ".main article a.btn { color: #fff; }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ccr, "CSS", css)
    assert ccr.expected_label() == ccr.hex_to_rgb_string("#ffffff")


def test_a_dark_mode_label_rule_is_rejected_not_silently_returned(tmp_path, monkeypatch):
    """A rule inside `@media` applies sometimes. The gate asserts one value always.

    The flat brace-scan has no concept of nesting, so a conditional rule used to
    be extracted as though it were top-level. Two bad outcomes, and the second
    is the dangerous one (Ralph round 7):

      base + dark   -> looked like an ambiguous duplicate of one selector
      dark ONLY     -> returned SILENTLY as the single expected label, then
                       asserted under the light scheme too, where it is wrong

    This stylesheet already uses `prefers-color-scheme` for other properties, so
    the construct is one edit away, not hypothetical.
    """
    css = tmp_path / "synthetic.css"
    css.write_text(
        "@media (prefers-color-scheme: dark) { .main a.btn { color: #000000; } }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ccr, "CSS", css)
    with pytest.raises(SystemExit):
        ccr.expected_label()


def test_a_base_rule_plus_a_dark_override_is_also_rejected(tmp_path, monkeypatch):
    css = tmp_path / "synthetic.css"
    css.write_text(
        ".main a.btn { color: #ffffff; }\n"
        "@media (prefers-color-scheme: dark) { .main a.btn { color: #000000; } }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ccr, "CSS", css)
    with pytest.raises(SystemExit):
        ccr.expected_label()


def test_an_unrelated_media_block_does_not_disturb_the_answer(tmp_path, monkeypatch):
    """Only a CTA label rule inside a condition is a problem.

    main.css carries several `@media` blocks for other properties, and they must
    keep working. This also pins that the block-removal finds the right closing
    brace: a nested block that swallowed too much would take the real rule with it.
    """
    css = tmp_path / "synthetic.css"
    css.write_text(
        "@media (max-width: 40rem) { .sidebar { display: none; } .main { padding: 0; } }\n"
        ".main a.btn { color: #ffffff; }\n"
        "@media print { .main a.btn { background: none; } }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ccr, "CSS", css)
    assert ccr.expected_label() == ccr.hex_to_rgb_string("#ffffff")


def test_the_literal_a_dot_btn_requirement_is_a_known_tested_boundary(tmp_path, monkeypatch):
    """Selectors that genuinely style the CTA but avoid the literal `a.btn`.

    `.main .btn` and `.main :where(a).btn` are both (0,2,0) and both still beat
    `.main a` at (0,1,1), so the button really is styled in each case. This gate
    matches a substring, not CSS semantics, so it dies. Pinned deliberately: the
    failure is loud and explains itself, and a maintainer meeting it during an
    otherwise-correct refactor should find it documented rather than surprising.
    """
    for selector in (".main .btn", ".main :where(a).btn"):
        css = tmp_path / f"{selector.replace(' ', '_').replace(':', '')}.css"
        css.write_text(f"{selector} {{ color: #ffffff; }}\n", encoding="utf-8")
        monkeypatch.setattr(ccr, "CSS", css)
        with pytest.raises(SystemExit):
            ccr.expected_label()


def test_expected_fill_survives_a_byte_order_mark(tmp_path, monkeypatch):
    """TOML disallows a leading BOM, so plain utf-8 crashed with a traceback.

    Every other failure in this gate is an actionable die(). This one was an
    unhandled TOMLDecodeError, which tells a reader nothing (Ralph round 7).
    """
    params = tmp_path / "params.toml"
    params.write_bytes(b"\xef\xbb\xbf" + b'ctaColor = "#188418"\n')
    monkeypatch.setattr(ccr, "PARAMS", params)
    assert ccr.expected_fill() == ccr.hex_to_rgb_string("#188418")


def test_a_brace_inside_a_string_cannot_smuggle_a_conditional_rule_out(tmp_path, monkeypatch):
    """`content: "}"` is ordinary CSS, and it used to break the block scan.

    The brace-depth counter had no string awareness, so the closing brace inside
    that string ended the `@media` block early and the rest of it leaked into
    the text treated as unconditional. A dark-only `.main a.btn` then came back
    as the single universal label with no die at all, and was asserted under the
    light scheme too (Ralph round 8, reproduced against the real function).

    This stylesheet already uses `content` for list markers, so the construct is
    not exotic.
    """
    css = tmp_path / "synthetic.css"
    css.write_text(
        '@media (prefers-color-scheme: dark) {\n'
        '  .sidebar li::marker { content: "}"; }\n'
        '  .main a.btn { color: #000000; }\n'
        '}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ccr, "CSS", css)
    with pytest.raises(SystemExit):
        ccr.expected_label()


def test_a_brace_in_a_string_does_not_disturb_an_unconditional_answer(tmp_path, monkeypatch):
    """The counterpart: blanking string contents must not lose a real rule."""
    css = tmp_path / "synthetic.css"
    css.write_text(
        '.sidebar li::marker { content: "{"; }\n'
        '.main a.btn { color: #ffffff; }\n'
        '.footer::after { content: \'}\'; }\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ccr, "CSS", css)
    assert ccr.expected_label() == ccr.hex_to_rgb_string("#ffffff")


def test_blank_strings_preserves_offsets_and_quotes():
    """Length and quoting are preserved so nothing downstream shifts."""
    src = '.a { content: "}}"; } .b { content: \'{\'; }'
    out = ccr._blank_strings(src)
    assert len(out) == len(src)
    assert "}" not in out[out.index('"'):out.index('"') + 4]
    assert out.count('"') == 2 and out.count("'") == 2
    # An escaped quote must not end the literal early.
    esc = '.a { content: "a\\"}b"; }'
    assert "}" not in ccr._blank_strings(esc)[15:20]


def test_expected_label_takes_the_last_declaration_not_the_first(tmp_path, monkeypatch):
    """Within one rule the cascade takes the LAST declaration. So must the gate.

    Reading the first made this gate model a colour the browser never paints,
    and because the sibling authority scores its WCAG 4.5:1 assertion from the
    same parse, an unreadable button passed both gates green: 4.82:1 reported,
    1.10:1 rendered. Found by the deep dive Ralph escalated to after nine rounds
    had all landed elsewhere in this file.
    """
    css = tmp_path / "synthetic.css"
    css.write_text(".main a.btn { color: #ffffff; color: #6b6b6b; }\n", encoding="utf-8")
    monkeypatch.setattr(ccr, "CSS", css)
    assert ccr.expected_label() == ccr.hex_to_rgb_string("#6b6b6b")


def test_expected_label_dies_actionably_on_a_non_hex_colour(tmp_path, monkeypatch):
    """`color: var(--cta-label)` is the likeliest edit to this rule.

    Line 138 of main.css is the only hardcoded colour left in the stylesheet;
    every other one is already a var() token. Unguarded this reached
    `int("va", 16)` and surfaced as a raw ValueError traceback pointing at a
    conversion helper, which tells the reader nothing about what to fix.
    """
    css = tmp_path / "synthetic.css"
    css.write_text(".main a.btn { color: var(--cta-label); }\n", encoding="utf-8")
    monkeypatch.setattr(ccr, "CSS", css)
    with pytest.raises(SystemExit) as exc:
        ccr.expected_label()
    assert exc.value.code == 2


def test_expected_label_dies_naming_the_line_on_an_unterminated_quote(
        tmp_path, monkeypatch, capsys):
    """A CSS string cannot span a newline; the blanker used to let it.

    With `re.S` a forgotten closing quote paired with the NEXT quote of the same
    type however far away and blanked every real brace between them. Here the
    button's own rule is swallowed and a DISAGREEING `.footer a.btn` survives
    outside the span, so the function returned red silently with no die at all -
    defeating the ambiguity-is-fatal contract it documents (Ralph round 9).
    """
    css = tmp_path / "synthetic.css"
    css.write_text(
        '.decoy::before { content: "oops-unterminated; }\n'
        ".main a.btn { color: #ffffff; }\n"
        '.tag::after { content: "properly closed"; }\n'
        ".footer a.btn { color: #ff0000; }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ccr, "CSS", css)
    with pytest.raises(SystemExit) as exc:
        ccr.expected_label()
    assert exc.value.code == 2

    # Assert WHICH failure, and WHERE. Exit code 2 alone does not distinguish
    # this from the several other die() paths in the function, and with `re.S`
    # restored the stray quote is located on the WRONG line - so a code-only
    # assertion passed against the defect and reported as coverage. Found by
    # tests/test_gate_mutations.py, which is exactly what that file is for.
    message = capsys.readouterr().err
    assert "unterminated string literal" in message, message
    assert "line 1:" in message, (
        f"the unterminated quote is on line 1; the gate blamed a different line, "
        f"which sends the reader to CSS that is not the problem.\n{message}"
    )


def test_blank_strings_accepts_the_real_stylesheet_unchanged():
    """The unterminated-quote probe must not false-fire on valid CSS.

    Blanking preserves the quotes so offsets do not shift, which means probing
    the BLANKED text re-anchors on a closing quote and reports valid CSS as
    broken. The probe therefore runs on a copy with the literals removed
    outright. This test is the regression pin for that distinction.

    Comments are stripped first because that is exactly what `expected_label`
    does before it blanks. It matters: main.css:111 contains an apostrophe
    inside a comment ("the site's only commercial call to action"), which is a
    lone quote the probe would rightly flag if a comment ever reached it.
    """
    raw = ccr.CSS.read_text(encoding="utf-8-sig")
    assert ccr._blank_strings(ccr.COMMENTS.sub("", raw))


def test_two_unterminated_quotes_do_not_silently_swallow_the_button_rule(
        tmp_path, monkeypatch, capsys):
    """The case that proves dropping `re.S` is load-bearing, not belt-and-braces.

    With ONE stray quote the probe catches it either way, so that input does not
    discriminate - the first version of this pin used it and passed against the
    defect, and even the line number matched, because blanking replaces the
    swallowed newlines with spaces so the count comes out the same by accident.

    With TWO, `re.S` pairs them ACROSS the intervening lines, swallowing the
    button's own rule and consuming BOTH quotes, so the probe finds nothing left
    to complain about and a DISAGREEING `.footer a.btn` is returned silently.
    That is the round-9 defect exactly: a wrong colour, no die.

    Without `re.S` neither quote closes on its own line, no literal matches, and
    the stray quote is reported. Found by tests/test_gate_mutations.py, which is
    the file that exists to catch a pin that does not discriminate.
    """
    css = tmp_path / "synthetic.css"
    css.write_text(
        '.a::before { content: "unterminated one\n'
        ".main a.btn { color: #ffffff; }\n"
        '.b::after { content: "unterminated two\n'
        ".footer a.btn { color: #ff0000; }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ccr, "CSS", css)
    with pytest.raises(SystemExit) as exc:
        ccr.expected_label()
    assert exc.value.code == 2

    # The MESSAGE is what discriminates, not the exit code. With `re.S` restored
    # this input ALSO dies - but as "no stateless a.btn rule found", blaming the
    # button for a quote typo elsewhere and sending the reader to the wrong file
    # entirely. An exit-code-only assertion passed against the defect.
    message = capsys.readouterr().err
    assert "unterminated string literal" in message, (
        f"the gate died, but not for the right reason. It must name the stray "
        f"quote; anything else sends the reader after a rule that is present and "
        f"correct.\n{message}"
    )


# --------------------------------------------------------------------------
# The reported location survives a multi-line comment above the typo
# --------------------------------------------------------------------------

def test_the_reported_line_is_counted_against_the_original_file(
        tmp_path, monkeypatch, capsys):
    """A comment above the stray quote must not shift the line number.

    `expected_label` used to strip comments with `COMMENTS.sub("", ...)`, which
    deletes their newlines too, so every line after a multi-line comment counted
    short by exactly the number of lines that comment spanned. The shipped
    stylesheet opens with a comment block, so in practice EVERY reported line
    number was wrong, and the reader was sent to CSS that is fine.

    The comment here spans four lines and the stray quote sits on line 6. A
    discriminating input: with the old deletion the message says line 2.
    """
    css = tmp_path / "synthetic.css"
    css.write_text(
        "/* a comment block\n"
        "   that spans\n"
        "   several lines\n"
        "   like the real stylesheet's header */\n"
        ".main a.btn { color: #ffffff; }\n"
        '.decoy::before { content: "oops-unterminated; }\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ccr, "CSS", css)
    with pytest.raises(SystemExit) as exc:
        ccr.expected_label()
    assert exc.value.code == 2

    message = capsys.readouterr().err
    assert "unterminated string literal" in message, message
    assert "line 6:" in message, (
        f"the stray quote is on line 6 of the file as written. A different "
        f"number means the count ran against text with the comment removed "
        f"rather than blanked, which sends the reader to the wrong line.\n"
        f"{message}"
    )


def test_blank_comments_preserves_length_and_line_count():
    """Blanking must be offset-neutral, which is the whole point of it.

    If it changed either, every position computed downstream would drift and the
    fix above would be re-broken by a plausible-looking edit.
    """
    raw = ccr.CSS.read_text(encoding="utf-8-sig")
    blanked = ccr._blank_comments(raw)
    assert len(blanked) == len(raw)
    assert blanked.count("\n") == raw.count("\n")
    # The CONTENT still has to stop being readable, or a rule inside a comment
    # would be picked up as a declaration.
    assert "/*" not in blanked


# --------------------------------------------------------------------------
# A non-hex colour names the file it was actually read from
# --------------------------------------------------------------------------

def test_a_non_hex_fill_blames_params_toml_not_the_stylesheet(
        tmp_path, monkeypatch, capsys):
    """Two callers, two source files, one message that named only one of them.

    `hex_to_rgb_string` is reached from `expected_fill` (value from
    `params.toml`) and from `_stateless_anchor_labels` (value from `main.css`),
    and the die() named the stylesheet unconditionally. A `ctaColor` that is not
    a hex literal therefore sent the reader to `main.css` to find a declaration
    that is not in it.
    """
    params = tmp_path / "params.toml"
    params.write_text('ctaColor = "var(--brand)"\n', encoding="utf-8")
    monkeypatch.setattr(ccr, "PARAMS", params)
    with pytest.raises(SystemExit) as exc:
        ccr.expected_fill()
    assert exc.value.code == 2

    message = capsys.readouterr().err
    assert "params.toml" in message, (
        f"the value came from params.toml and the message has to say so.\n{message}"
    )
    assert "main.css" not in message, (
        f"the message named the stylesheet for a value declared in the TOML.\n{message}"
    )


def test_a_non_hex_label_still_blames_the_stylesheet(tmp_path, monkeypatch, capsys):
    """The other direction, so the fix above cannot be a blanket relabel."""
    css = tmp_path / "main.css"
    css.write_text(".main a.btn { color: var(--cta-label); }\n", encoding="utf-8")
    monkeypatch.setattr(ccr, "CSS", css)
    with pytest.raises(SystemExit) as exc:
        ccr.expected_label()
    assert exc.value.code == 2
    assert "main.css" in capsys.readouterr().err
