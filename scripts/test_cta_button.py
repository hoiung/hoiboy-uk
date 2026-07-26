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


def stylesheet() -> str:
    """main.css with comments stripped.

    Stripping is not cosmetic. The comment above the button rule discusses
    `.btn` and `.main a` at length, precisely because the selector needs
    explaining. Parsed naively, that prose reads as several extra rules and the
    specificity assertions below start scoring English.
    """
    return COMMENTS.sub("", CSS.read_text(encoding="utf-8"))


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
    m = re.search(rf"(?:^|;)\s*{re.escape(prop)}\s*:\s*([^;]+)", decls)
    return m.group(1).strip() if m else None


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    h = value.strip().lstrip("#")
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


def cta_color() -> str:
    """`ctaColor` as declared in params.toml.

    Read from the config rather than from the CSS: the config is where the
    value lives (No Hardcoded Settings), and the CSS only consumes it.
    """
    if sys.version_info >= (3, 11):
        import tomllib
        return tomllib.loads(PARAMS.read_text(encoding="utf-8"))["ctaColor"]
    m = re.search(r'^ctaColor\s*=\s*"([^"]+)"', PARAMS.read_text(encoding="utf-8"), re.M)
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

# WCAG 2.1 contrast minimums. 4.5:1 for normal-size text, 3:1 for large text
# (>=18.66px bold or >=24px regular) and for UI component boundaries.
AA_NORMAL = 4.5
AA_LARGE = 3.0


def test_label_contrast_clears_the_large_text_floor():
    """Computed from the two colours in source, so a colour change re-tests it.

    The floor is 3:1, not 4.5:1, and that is a recorded decision rather than a
    slackened gate. The fill is the LOGO green (#228b22, exactly CSS
    `forestgreen`), which the operator requires verbatim: "I want the logo
    green. that's the theme colour, not some made up green." An earlier revision
    shipped #188418, a green darkened until it cleared 4.5:1, and that was
    rejected precisely because inventing a colour to satisfy a test is backwards.

    #228b22 is a mid-tone, so at normal text size NEITHER label clears AA:
    white is 4.39:1 and near-black is 3.95:1. There is no label colour that
    rescues it. Keeping the brand colour therefore means accepting the 3:1
    floor, which white clears at 4.39:1.

    The assertion stays discriminating: a genuinely unreadable fill still fails
    (the #9be89b mutation is 2.0:1). What it no longer does is force the brand
    colour to move.
    """
    _, decls = base_rule()
    label = declaration(decls, "color")
    assert label, "the button rule sets no label colour."
    ratio = contrast_ratio(hex_to_rgb(label), hex_to_rgb(cta_color()))
    assert ratio >= AA_LARGE, (
        f"label {label} on fill {cta_color()} is {ratio:.2f}:1, below even the "
        f"WCAG large-text/UI minimum of {AA_LARGE}:1. The fill is unreadable, "
        f"not merely imperfect."
    )


def test_the_aa_normal_shortfall_is_recorded_not_forgotten():
    """If the fill ever clears 4.5:1, say so, so the concession can be dropped.

    A known shortfall that nobody re-checks becomes permanent by accident. This
    fails when the situation IMPROVES, which is the point: it forces the docs
    and the 3:1 concession above to be revisited rather than left as folklore.
    """
    _, decls = base_rule()
    ratio = contrast_ratio(hex_to_rgb(declaration(decls, "color")), hex_to_rgb(cta_color()))
    assert ratio < AA_NORMAL, (
        f"the label now clears {AA_NORMAL}:1 at {ratio:.2f}:1. Good news, and it "
        f"means the large-text concession is no longer needed: restore the "
        f"{AA_NORMAL} floor in the test above and update the notes in "
        f"params.toml and main.css that describe the shortfall."
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

def test_the_shortcode_emits_no_class_the_stylesheet_does_not_define():
    """`btn-secondary` shipped for months naming a variant that never existed.

    Dropped in blog-priv#63 rather than invented. This asserts the general rule
    instead of that one name: every class the CTA anchor carries has a rule.
    """
    html = SHORTCODE.read_text(encoding="utf-8")
    emitted = {
        cls
        for attr in re.findall(r'class="([^"]*)"', html)
        for cls in attr.split()
    }
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
    """
    code = "\n".join(
        line for line in PRE_PUBLISH.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("#")
    )
    assert RENDERED_GATE in code, (
        f"{RENDERED_GATE} is not invoked by scripts/pre-publish.sh. Specificity "
        f"is scored from source here, which is a model of the cascade and not "
        f"the cascade itself; the browser check is what proves it. Unwired, it "
        f"runs never."
    )
