#!/usr/bin/env python3
"""The discovery-call CTA is styled as a button and WINS the cascade.

blog-priv#63.

The defect this exists to stop, in two halves.

HALF ONE, the original: `layouts/_shortcodes/consulting-cta.html` emitted
`class="btn"` from the day it shipped and nothing in `assets/css/main.css` ever
defined `.btn`. The site's only commercial call to action rendered as ordinary
underlined body copy. Nothing errored, nothing looked broken, and no test could
see it, because a class with no rule is not a syntax error anywhere.

HALF TWO, the trap the first fix falls into: writing the obvious bare `.btn`
rule does NOT fix it. `assets/css/main.css` carries

    .main a { color: var(--accent); text-decoration: underline; ... }

at specificity 0-1-1. A bare `.btn` is 0-1-0, so it loses BOTH the colour and
the underline while appearing, in the source, to have set them. This was
reproduced live during colour testing: the label rendered red and underlined,
and on the accent colour the white-on-accent text vanished into its own fill.
The rule therefore has to be scoped (`.main a.btn`, 0-2-1) and has to state
`text-decoration: none` explicitly, because it is overriding an inherited
underline rather than declining to add one.

So the assertions here are specificity-aware rather than string matches. A
future tidy-up that "simplifies" the selector back to `.btn`, or drops the
`text-decoration` line as redundant, reintroduces exactly the bug the rule was
written for, and both mutations fail this file.

Contrast is asserted rather than assumed: white on the configured fill must
clear WCAG AA (4.5:1). It is computed from the two colours actually in the
source, not restated as the number that was true on the day, so changing either
colour to something that fails re-opens the assertion instead of sailing past a
stale comment.

The cascade itself cannot be proven here. What a browser computes after the
cascade is the only real answer, and that needs a browser, which is
`scripts/check_cta_rendered.py`. This file also asserts that gate is WIRED,
because an unwired gate in this repo has a track record of running never.

Run:  python3 -m pytest scripts/test_cta_button.py -q
"""

from __future__ import annotations

import functools
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "assets" / "css" / "main.css"
PARAMS = ROOT / "config" / "_default" / "params.toml"
SHORTCODE = ROOT / "layouts" / "_shortcodes" / "consulting-cta.html"
PRE_PUBLISH = ROOT / "scripts" / "pre-publish.sh"
RENDERED_GATE = "scripts/check_cta_rendered.py"

# The rule the button has to outrank. Kept as a selector string, not as a
# hardcoded (0,1,1), so the comparison re-derives if that rule is ever rewritten.
COMPETING_SELECTOR = ".main a"

# `.btn` as a whole class name. Does NOT match `.menu-toggle-btn`, the mobile
# nav hamburger, which is an unrelated class that merely ends in the same three
# letters; and does not match a hypothetical `.btn-secondary`, which would be a
# different class and would need its own rule.
BTN_CLASS = re.compile(r"\.btn(?![\w-])")

COMMENTS = re.compile(r"/\*.*?\*/", re.S)
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)

# A CSS string literal. Not re.S, and the body excludes a raw newline, because
# per CSS syntax a string ends at the newline rather than running on to pair
# with some later quote.
STRING_LITERAL = re.compile(r"""(['"])(?:\\.|(?!\1)[^\\\n])*\1""")


def blank_string_contents(css: str) -> str:
    """Blank the CONTENTS of string literals, preserving quotes and length.

    A brace inside a string is data, not structure, and `RULE` above cannot tell
    the difference. `content: "}"` is ordinary valid CSS - this stylesheet
    already uses `content` for list markers - and inside the button's own rule
    it ended the declaration capture early, so `declaration()` returned an
    EARLIER `color` while the browser painted a LATER one. Because
    `test_label_contrast_clears_wcag_aa` is the only WCAG gate in this repo and
    scores whatever `declaration()` returns, that reported 4.82:1 for a button
    actually rendering at 1.56:1, with every gate green.

    Deliberately an INDEPENDENT implementation of the same idea as
    `check_cta_rendered.py`'s `_blank_strings`, not an import of it. The two
    gates are a source model and a real browser, and sharing a parser would let
    them agree on the same wrong answer (rationale recorded in e9a927f). Fixing
    one defect in BOTH files is AP #9; merging the files is not.
    """
    return STRING_LITERAL.sub(
        lambda m: m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[0], css)


@functools.lru_cache(maxsize=None)
def stylesheet() -> str:
    """main.css with comments stripped and string contents blanked.

    Stripping is not cosmetic. The comment above the button rule discusses
    `.btn` and `.main a` at length, precisely because the selector needs
    explaining. Parsed naively, that prose reads as several extra rules and the
    specificity assertions below start scoring English.
    """
    return blank_string_contents(COMMENTS.sub("", CSS.read_text(encoding="utf-8")))


def specificity(selector: str) -> tuple[int, int, int]:
    """CSS specificity as (ids, classes, elements), per the cascade spec.

    Classes, attribute selectors and pseudo-classes all score in the middle
    column; elements and pseudo-elements in the last. Enough of the grammar for
    the selectors this stylesheet actually uses, which are all simple compound
    selectors with no :not()/:is() re-entry.
    """
    sel = selector.strip()
    ids = len(re.findall(r"#[\w-]+", sel))
    classes = (
        len(re.findall(r"\.[\w-]+", sel))
        + len(re.findall(r"\[[^\]]+\]", sel))
        + len(re.findall(r"(?<!:):(?!:)[\w-]+", sel))
    )
    elements = (
        len(re.findall(r"(?:^|[\s>+~])([a-zA-Z][\w-]*)", sel))
        + len(re.findall(r"::[\w-]+", sel))
    )
    return (ids, classes, elements)


def btn_rules() -> list[tuple[str, str]]:
    """Every (selector, declarations) pair in main.css that styles `.btn`.

    Selector lists are split, so `a.btn, button.btn { ... }` is scored as two
    selectors rather than one long string, which would inflate its score.
    """
    out: list[tuple[str, str]] = []
    for sel_group, decls in RULE.findall(stylesheet()):
        for sel in sel_group.split(","):
            if BTN_CLASS.search(sel):
                out.append((sel.strip(), decls))
    return out


def base_rule() -> tuple[str, str]:
    """The `.btn` rule that paints the button: no pseudo-class on it.

    :hover and :focus-visible are state layers on top and are checked as such.
    """
    plain = [(s, d) for s, d in btn_rules() if ":" not in s]
    assert len(plain) == 1, (
        f"expected exactly one stateless .btn rule in main.css, found "
        f"{len(plain)}: {[s for s, _ in plain]!r}. More than one means the "
        f"button's appearance is split across rules whose order now matters."
    )
    return plain[0]


def declaration(decls: str, prop: str) -> str | None:
    # LAST wins, as the cascade does within a rule. Taking the FIRST made the
    # WCAG assertion below score a colour the browser never paints: a duplicate
    # `color: #fff; color: #6b6b6b;` reported 4.82:1 while the button rendered
    # at 1.10:1, green in CI (blog-priv#63, post-Ralph deep dive).
    found = re.findall(rf"(?:^|;)\s*{re.escape(prop)}\s*:\s*([^;]+)", decls)
    return found[-1].strip() if found else None


HEX_COLOUR = re.compile(r"#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\Z")


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    # Guarded for the same reason as the sibling gate's hex_to_rgb_string: every
    # other colour in main.css is a var() token, so `color: var(--cta-label)` is
    # the likeliest edit here, and unguarded it surfaced as `int("va", 16)`.
    h = value.strip()
    assert HEX_COLOUR.match(h), (
        f"the button's colour is declared as `{h}`, which is not a hex literal. "
        f"This test resolves the cascade by reading the stylesheet, so it can only "
        f"handle hex values - a var()/named/rgb() colour must be resolved by the "
        f"browser instead."
    )
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


@functools.lru_cache(maxsize=None)
def cta_color() -> str:
    """`ctaColor` as declared in params.toml.

    Read from the config rather than from the CSS: the config is where the
    value lives (No Hardcoded Settings), and the CSS only consumes it.
    """
    # utf-8-sig on both paths: TOML disallows a leading BOM, so a BOM-prefixed
    # save raised an unhandled TOMLDecodeError here, and the regex fallback's
    # `^` cannot match before the BOM byte either. The sibling reader in
    # check_cta_rendered.py had the identical defect (Ralph round 7).
    if sys.version_info >= (3, 11):
        import tomllib
        return tomllib.loads(PARAMS.read_text(encoding="utf-8-sig"))["ctaColor"]
    m = re.search(r'^ctaColor\s*=\s*"([^"]+)"', PARAMS.read_text(encoding="utf-8-sig"), re.M)
    assert m, "ctaColor is not declared in config/_default/params.toml"
    return m.group(1)


# --------------------------------------------------------------------------
# The colour is configured, not hardcoded
# --------------------------------------------------------------------------

def test_cta_colour_is_a_config_param_not_a_literal_in_the_stylesheet():
    """Mirrors the existing accentColor pattern, per No Hardcoded Settings."""
    colour = cta_color()
    assert re.fullmatch(r"#[0-9a-fA-F]{3,6}", colour), (
        f"ctaColor is {colour!r}, which is not a hex colour."
    )
    assert re.search(r"--cta:\s*\{\{\s*site\.Params\.ctaColor", CSS.read_text(encoding="utf-8")), (
        "assets/css/main.css does not define --cta from site.Params.ctaColor. "
        "The token has to consume the config key, otherwise params.toml holds a "
        "value nothing reads and check_config_traceability.py fails by design."
    )
    _, decls = base_rule()
    background = declaration(decls, "background") or ""
    assert "var(--cta)" in background, (
        f"the button's background is {background!r}, not var(--cta). A literal "
        f"colour here means changing ctaColor in params.toml silently does "
        f"nothing, and the config key becomes decoration."
    )


# --------------------------------------------------------------------------
# The cascade defect (this is the one that matters)
# --------------------------------------------------------------------------

def test_every_btn_rule_outranks_the_generic_link_rule():
    """A bare `.btn` loses to `.main a` and the button reverts to a text link.

    Scored rather than string-matched, so this passes for any selector that is
    genuinely specific enough and fails for any that is not, instead of pinning
    one exact spelling that a legitimate refactor would trip over.
    """
    rules = btn_rules()
    assert rules, (
        "no rule in assets/css/main.css styles .btn at all. That is the "
        "original blog-priv#63 defect: the shortcode emits the class and the "
        "stylesheet never defined it, so the CTA renders as body copy."
    )
    beaten = specificity(COMPETING_SELECTOR)
    for sel, _ in rules:
        assert specificity(sel) > beaten, (
            f"selector {sel!r} scores {specificity(sel)}, which does not beat "
            f"{COMPETING_SELECTOR!r} at {beaten}. `.main a` sets both colour and "
            f"an underline, so this rule loses both and the button renders as an "
            f"underlined accent-coloured link. Scope it (`.main a.btn`)."
        )


def test_the_button_kills_the_inherited_underline_explicitly():
    """`text-decoration: none` is overriding, not omitting.

    Dropping it as redundant is the second way back into the bug: the underline
    is inherited from `.main a`, so saying nothing means keeping it.
    """
    sel, decls = base_rule()
    value = declaration(decls, "text-decoration")
    assert value == "none", (
        f"{sel!r} declares text-decoration: {value!r}. It must be 'none'. "
        f"`.main a` sets an underline, so a button that stays silent about "
        f"text-decoration inherits one."
    )


def test_hover_state_does_not_hand_the_underline_back():
    """Hover re-enters the same trap: `.main a:hover` territory, same cascade."""
    hovers = [(s, d) for s, d in btn_rules() if ":hover" in s]
    assert hovers, "the button has no hover state, so it gives no click affordance."
    for sel, decls in hovers:
        assert declaration(decls, "text-decoration") == "none", (
            f"{sel!r} does not hold text-decoration: none, so the underline "
            f"returns the moment a reader points at the button."
        )


# --------------------------------------------------------------------------
# Accessibility
# --------------------------------------------------------------------------

# WCAG 2.1 contrast minimum for normal-size text. The button label is ~16px at
# weight 600, which is NOT "large text" (that needs >=18.66px bold or >=24px),
# so 4.5:1 is the applicable threshold and the 3:1 large-text allowance does not
# apply here.
AA_NORMAL = 4.5


def test_label_contrast_clears_wcag_aa():
    """Computed from the two colours in source, so a colour change re-tests it.

    The floor is the full 4.5:1 for normal-size text, and the fill is chosen to
    meet it rather than the threshold being lowered to accept the fill. Both
    directions of that trade were tried live and the history is worth keeping,
    because the wrong lesson is easy to draw from it:

      #188418   4.82:1   shipped. The logo green darkened by rgb(10, 7, 10).
      #228b22   4.39:1   the exact logo green, against white. Against this
                         theme's --fg #1a1a1a it is 3.97:1. Both fail, so no
                         label colour the theme actually uses clears 4.5:1 on
                         it. (It is not a universal failure: pure black clears
                         it at 4.78:1. The theme just never uses pure black.)

    The earlier failure here was never the hex. It was describing #188418 as
    "taken from the logo" when it is a derivative, so nobody could see a trade
    had been made. The colour is now the same value with that trade written
    down, in params.toml and in main.css, as an operator decision taken with
    both versions deployed and compared for readability.

    So: do not relax this threshold to fit a future colour. If a brand colour
    cannot clear 4.5:1, that is a finding to surface, not a number to edit.
    """
    _, decls = base_rule()
    label = declaration(decls, "color")
    assert label, "the button rule sets no label colour."
    ratio = contrast_ratio(hex_to_rgb(label), hex_to_rgb(cta_color()))
    assert ratio >= AA_NORMAL, (
        f"label {label} on fill {cta_color()} is {ratio:.2f}:1, below the WCAG "
        f"AA minimum of {AA_NORMAL}:1 for body-size text. Note that the exact "
        f"logo green (#228b22) sits here at 4.39:1: if that is what has just "
        f"been set, the fix is a darker derivative, not a lower threshold."
    )


def test_the_button_is_reachable_by_keyboard():
    """A focus ring, because the button is the one thing on the page to action."""
    assert any(":focus-visible" in s for s, _ in btn_rules()), (
        "the button has no :focus-visible rule, so a keyboard user tabbing to "
        "the site's only call to action cannot see where they are."
    )


# --------------------------------------------------------------------------
# The class the shortcode emits, and the gate that checks the real cascade
# --------------------------------------------------------------------------

# Hugo and HTML comments in the shortcode, stripped before any class is scraped.
#
# This is load-bearing, not hygiene. The shortcode's own comment block contains
# the sentence: Emits class="btn" only. A scrape over the raw file therefore
# found `btn` in the PROSE, so deleting class="btn" from both real anchors -
# which drops the site's only commercial CTA back to unstyled underlined body
# copy on all six CTA-bearing pages - left the whole CI lane green, 8/8. The file's
# two sibling helpers already strip comments for exactly this reason
# (`stylesheet()` strips CSS comments, the wiring test strips shell comments);
# this one did not, and it was the only automatic gate standing between the
# defect and production.
HUGO_COMMENT = re.compile(r"\{\{-?\s*/\*.*?\*/\s*-?\}\}", re.S)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
ANCHOR_TAG = re.compile(r"<a\b[^>]*>", re.I)


def shortcode_anchor_classes() -> set[str]:
    """Class tokens carried by real <a> tags in the shortcode, comments removed.

    Scoped to anchor tags rather than the whole file so a class named in prose,
    or on some other element, cannot stand in for the button actually having it.
    """
    html = SHORTCODE.read_text(encoding="utf-8")
    html = HTML_COMMENT.sub(" ", HUGO_COMMENT.sub(" ", html))
    return {
        cls
        for tag in ANCHOR_TAG.findall(html)
        for attr in re.findall(r'class="([^"]*)"', tag)
        for cls in attr.split()
    }


def test_the_shortcode_anchor_actually_carries_the_button_class():
    """The positive half: the CTA anchor really is a button.

    Every other test here checks that IF an element carries `btn` THEN it is
    styled correctly. None of them noticed when the class was removed from the
    anchors altogether, because the rule, the token and the contrast all stayed
    perfectly valid for an element that no longer existed. A gate that only
    validates the styling of an absent thing is not a regression gate.
    """
    classes = shortcode_anchor_classes()
    assert "btn" in classes, (
        f"no <a> tag in {SHORTCODE.name} carries the `btn` class (found "
        f"{sorted(classes) or 'no classes at all'}). The discovery-call CTA is "
        f"then an ordinary link: it inherits `.main a`, so it renders as "
        f"underlined terracotta body copy, which is the exact defect "
        f"blog-priv#63 was opened to fix."
    )


def test_the_shortcode_emits_no_class_the_stylesheet_does_not_define():
    """`btn-secondary` shipped for months naming a variant that never existed.

    Dropped in blog-priv#63 rather than invented. This asserts the general rule
    instead of that one name: every class the CTA anchor carries has a rule.
    """
    emitted = shortcode_anchor_classes()
    assert emitted, "the consulting-cta shortcode emits no class at all."
    css = stylesheet()
    undefined = sorted(c for c in emitted if not re.search(rf"\.{re.escape(c)}(?![\w-])", css))
    assert not undefined, (
        f"the shortcode emits {undefined}, which main.css never defines. A class "
        f"with no rule does nothing but imply a style that is not there; that is "
        f"how `btn` itself went unstyled from launch, and how `btn-secondary` "
        f"named a variant nobody had built."
    )


def test_the_rendered_cascade_gate_is_wired():
    """Source scoring is a proxy. The browser is the authority, so it must run.

    This repo has been bitten twice by a check that existed and was invoked
    nowhere (tests/test_gate_wiring.py, scripts/test_gen_card.py). Comment lines
    are stripped: pre-publish.sh documents its own gates at length, and a gate
    named only in prose is not wired.

    This asserts the INVOCATION SHAPE, not that the filename appears somewhere.
    An earlier version was a bare `RENDERED_GATE in code` substring test, which
    a Stage 5 mutation defeated in one line: rewriting the call as
    `echo "scripts/check_cta_rendered.py"`, or as a disabled variable
    assignment, kept the test green while the gate no longer ran. A substring is
    evidence that a string is present, never that a program is executed.

    Scope note, so nobody reads more coverage into this than exists:
    scripts/pre-publish.sh is the MANUAL pre-publish lane. It is not invoked by
    CI or by pre-commit, deliberately, because it is the only lane with Chromium
    and installing a browser on every push is not free. So this test proves the
    browser gate runs when a human runs pre-publish, which is the documented
    publish step, and NOT that it runs on every commit. The automatic half of
    this file's coverage is the specificity scoring above, which needs no
    browser and does run in CI.
    """
    code = "\n".join(
        line for line in PRE_PUBLISH.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("#")
    )
    invocation = re.compile(
        rf"^\s*run_check\s+\S+\s+python3\s+{re.escape(RENDERED_GATE)}(?![\w./-])",
        re.M,
    )
    assert invocation.search(code), (
        f"{RENDERED_GATE} is not INVOKED by scripts/pre-publish.sh in the "
        f"`run_check <name> python3 {RENDERED_GATE} ...` shape every other gate "
        f"in that file uses. Specificity is scored from source here, which is a "
        f"model of the cascade and not the cascade itself; the browser check is "
        f"what proves it. Naming the file without calling it means it runs never."
    )


def test_cta_color_survives_a_byte_order_mark(tmp_path, monkeypatch):
    """A BOM-prefixed params.toml must not crash this reader.

    TOML disallows a leading BOM, so `tomllib.loads` raises, and the pre-3.11
    regex fallback's `^` cannot match before the BOM byte either. The fix
    (utf-8-sig on both paths) shipped in 621fe11 alongside a pinning test for
    the sibling reader in check_cta_rendered.py, but none here: reverting this
    file's one line left all 9 tests passing (Ralph round 8).
    """
    params = tmp_path / "params.toml"
    params.write_bytes(b"\xef\xbb\xbf" + b'ctaColor = "#188418"\n')
    monkeypatch.setattr(sys.modules[__name__], "PARAMS", params)
    cta_color.cache_clear()
    try:
        assert cta_color() == "#188418"
    finally:
        cta_color.cache_clear()


def test_declaration_takes_the_last_not_the_first():
    """The WCAG assertion in this file scores whatever `declaration` returns.

    Within one rule the cascade takes the LAST declaration. Taking the first
    made this test score a colour the browser never paints: with a duplicated
    `color`, it reported 4.82:1 while the button actually rendered at 1.10:1,
    and CI stayed green. That is a fail-OPEN in the lane that gates the deploy,
    which is why it is pinned here and not only in the sibling gate.
    """
    decls = " background: var(--cta); color: #fff; color: #6b6b6b; "
    assert declaration(decls, "color") == "#6b6b6b"


def test_declaration_still_finds_a_single_declaration():
    """Control: the ordinary one-declaration case is unchanged."""
    assert declaration(" color: #ffffff; ", "color") == "#ffffff"
    assert declaration(" background: var(--cta); ", "color") is None


def test_hex_to_rgb_rejects_a_non_hex_colour():
    """`color: var(--cta-label)` is the likeliest edit to the button rule.

    Every other colour in main.css is already a var() token. Unguarded, this
    raised `ValueError: invalid literal for int() with base 16: 'va'` - and it
    hit BOTH authorities at once, because the hex-only assumption was copied
    into each rather than being a difference between them. Independence of the
    two gates is about the cascade MODEL, not about value parsing.
    """
    import pytest

    for bad in ("var(--cta-label)", "white", "rgb(255, 255, 255)"):
        with pytest.raises(AssertionError):
            hex_to_rgb(bad)


def test_hex_to_rgb_still_accepts_every_real_hex_form():
    """Control: the forms the stylesheet and params.toml actually use."""
    assert hex_to_rgb("#ffffff") == (255, 255, 255)
    assert hex_to_rgb("#fff") == (255, 255, 255)
    assert hex_to_rgb("188418") == (24, 132, 24)
    assert hex_to_rgb("  #188418  ") == (24, 132, 24)


def test_a_brace_inside_a_string_does_not_truncate_the_button_rule(tmp_path, monkeypatch):
    """`content: "}"` is valid CSS and used to fool the ONLY WCAG gate here.

    The rule-scanning regex cannot tell a structural brace from one inside a
    string, so the declaration capture ended early and `declaration()` returned
    an EARLIER `color` than the browser paints. test_label_contrast_clears_wcag_aa
    scores whatever `declaration()` returns, so it reported 4.82:1 for a button
    rendering at 1.56:1 - a fail-OPEN in the lane that gates the deploy.

    The sibling gate got this fix at dee4ffb and this file did not, which is the
    same "hardened one consumer, left the sibling" shape a fourth time.

    Asserted through `base_rule()`, i.e. through `stylesheet()`, NOT by calling
    `blank_string_contents` directly. Calling the helper proves the helper works
    and says nothing about whether anything USES it: the first version of this
    test did exactly that and still passed with the blanking removed from
    `stylesheet()`. A gate that measures something the shared shell supplies is
    vacuous, which is a shape this repo has already been bitten by.
    """
    css = tmp_path / "synthetic.css"
    css.write_text(
        ".main a.btn { background: var(--cta); color: #ffffff; "
        'content: "}"; color: #146214; text-decoration: none; }\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "CSS", css)
    stylesheet.cache_clear()
    try:
        _sel, decls = base_rule()
        assert declaration(decls, "color") == "#146214"
    finally:
        stylesheet.cache_clear()


def test_blank_string_contents_preserves_offsets_and_quotes():
    """Length and quoting are preserved so nothing downstream shifts."""
    src = '.a { content: "}}"; } .b { content: \'{\'; }'
    out = blank_string_contents(src)
    assert len(out) == len(src)
    assert out.count('"') == 2 and out.count("'") == 2
    assert "}" not in out[out.index('"'):out.index('"') + 4]


def test_the_real_stylesheet_still_yields_exactly_one_stateless_btn_rule():
    """Regression pin: blanking must not disturb the real file's parse."""
    assert base_rule()[0] == ".main a.btn"


# ---------------------------------------------------------------------------
# Subscribe-button parity (#56 Stage 5)
# ---------------------------------------------------------------------------
#
# The newsletter submit button is the SAME call to action in a different element.
# Stage 5 reported it as duplication and the obvious remedy -- one shared
# selector list -- was implemented and reverted, because it splits `.main a.btn`
# into two order-dependent rules and `base_rule` above refuses exactly that, for
# the reason recorded there.
#
# The two cannot share by inheritance either: `.main a.btn` is an anchor selector
# and this is a <button>, so nothing cascades between them.
#
# So the duplication stays and the DRIFT is closed instead. That is the part
# worth having: nobody minds two rules saying the same thing, they mind the day
# one is retuned and the site quietly grows two different primary buttons.

SUBSCRIBE_BTN_SELECTOR = '.subscribe-form button[type="submit"]'

# Declarations both rules must agree on. Deliberately not "every declaration":
# min-height, font-family, font-size, cursor and border are genuinely specific to
# the <button>, and display/text-decoration to the <a>.
SHARED_CTA_DECLS = ("background", "color", "padding", "font-weight", "border-radius")


def _declarations(selector: str) -> dict[str, str]:
    """The property -> value map of the stateless rule for `selector`."""
    css = CSS.read_text(encoding="utf-8")
    match = re.search(
        rf"(?m)^\s*{re.escape(selector)}\s*\{{([^}}]*)\}}", css
    )
    assert match, f"no stateless rule found for {selector!r} in main.css"
    out: dict[str, str] = {}
    for decl in match.group(1).split(";"):
        if ":" not in decl:
            continue
        prop, _, value = decl.partition(":")
        out[prop.strip()] = value.strip()
    return out


def test_the_subscribe_button_matches_the_cta_recipe_declaration_by_declaration():
    """Two rules, one appearance. Retune either alone and this fails."""
    anchor = _declarations(".main a.btn")
    button = _declarations(SUBSCRIBE_BTN_SELECTOR)

    for prop in SHARED_CTA_DECLS:
        assert prop in anchor, f".main a.btn no longer declares {prop!r}"
        assert prop in button, (
            f"{SUBSCRIBE_BTN_SELECTOR} no longer declares {prop!r}, so the two "
            f"primary buttons have started to diverge."
        )
        assert anchor[prop] == button[prop], (
            f"the two primary buttons disagree on {prop!r}: "
            f".main a.btn has {anchor[prop]!r}, {SUBSCRIBE_BTN_SELECTOR} has "
            f"{button[prop]!r}. They are the same control in different elements; "
            f"retune both or neither."
        )


def test_the_subscribe_button_hover_tracks_the_same_token():
    """The hover layer is derived from --cta on both, not declared twice."""
    css = CSS.read_text(encoding="utf-8")
    hovers = re.findall(
        r"(?m)^\s*([^\n{]*btn[^\n{]*|[^\n{]*subscribe-form button[^\n{]*):hover\s*\{([^}]*)\}",
        css,
    )
    assert hovers, "no hover rules found; this gate is asserting nothing"
    for selector, body in hovers:
        assert "color-mix(in srgb, var(--cta)" in body, (
            f"{selector.strip()}:hover no longer derives its fill from --cta "
            f"({body.strip()!r}). A second hard-coded hover colour is how the "
            f"token stops being the single source of truth."
        )


# ---------------------------------------------------------------------------
# Subscribe-form heading specificity (#56 Stage 5, second round)
# ---------------------------------------------------------------------------
#
# The same trap this file was created for, one element over. `.subscribe-form-
# title` was written as a bare class at 0-1-0 and lost every declaration to
# `.main h2` at 0-1-1, so the heading silently rendered at .main h2's size with
# .main h2's 2rem top margin. The declared font-size never applied ONCE.
#
# It surfaced only because the operator looked at the rendered page and said the
# gap above was huge and the gap below too tight -- the two numbers that give a
# lost rule away. No test saw it, and the rule read as perfectly correct in
# source. That is what makes this class worth a gate rather than a comment.

SUBSCRIBE_TITLE_CLASS = "subscribe-form-title"
SUBSCRIBE_TITLE_COMPETITOR = ".main h2"


def _stateless_selectors_for(css_class: str) -> list[str]:
    """Every stateless selector in main.css that targets `css_class`."""
    css = CSS.read_text(encoding="utf-8")
    out = []
    for selectors, _body in re.findall(r"(?m)^([^\n@{}]+)\{([^}]*)\}", css):
        for sel in selectors.split(","):
            sel = sel.strip()
            if css_class in sel and ":" not in sel:
                out.append(sel)
    return out


def test_the_subscribe_heading_outranks_the_generic_h2_rule():
    """A bare class here is 0-1-0 and loses to `.main h2` at 0-1-1."""
    selectors = _stateless_selectors_for(SUBSCRIBE_TITLE_CLASS)
    assert selectors, (
        f"no stateless rule targets .{SUBSCRIBE_TITLE_CLASS} in main.css; this "
        f"gate is asserting nothing."
    )
    beaten = specificity(SUBSCRIBE_TITLE_COMPETITOR)
    for sel in selectors:
        assert specificity(sel) > beaten, (
            f"selector {sel!r} scores {specificity(sel)}, which does not beat "
            f"{SUBSCRIBE_TITLE_COMPETITOR} at {beaten}. Every declaration in that "
            f"rule is dead: the heading takes .main h2's font-size and its 2rem "
            f"top margin instead. Scope it with the wrapper "
            f"(.subscribe-form .{SUBSCRIBE_TITLE_CLASS}), do not 'tidy' it to a "
            f"bare class."
        )


def test_the_subscribe_heading_is_larger_than_the_body_it_introduces():
    """The size the rule declares has to be a size that actually wins."""
    decls = _declarations(f".subscribe-form .{SUBSCRIBE_TITLE_CLASS}")
    size = decls.get("font-size", "")
    match = re.fullmatch(r"([\d.]+)rem", size)
    assert match, f"the heading's font-size is {size!r}, not a rem value"
    assert float(match.group(1)) > 1.0, (
        f"the heading is {size}, no larger than body text. It is the line that "
        f"has to earn the reader's attention inside the box."
    )
