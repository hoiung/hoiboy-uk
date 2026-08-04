#!/usr/bin/env python3
"""Every text colour on the AGIT form clears WCAG AA against its own theme.

hoiboy-uk#57.

The form gained a story counter that says "keep writing" in red and "long
enough" in green. Colour carrying that much of the message is only honest if it
is actually legible, and the page is served on two backgrounds.

The constraint that shapes this file: NO single hex clears 4.5:1 against both.
AA on the light background (#fafafa) requires relative luminance <= 0.173550;
AA on the dark background (#141414) requires >= 0.206479. The feasible set is
empty, and the best simultaneous ratio any one colour can reach is 4.193:1. So
"pick a red that works everywhere" is not a thing that exists, and every state
needs a light value and a dark value. That is why this gate checks each colour
against the background it is actually painted on rather than against one.

It also caught a live failure on the way in: `.agit-notice` was #e5766a, which
measures 2.82:1 on the light background and was already failing AA before this
issue existed. The new blocked-submit message routes through that same colour,
so the defect was in this issue's own class and was fixed rather than deferred.

Two deliberate choices, both defect-driven:

COMMENTS ARE STRIPPED FIRST. The comment above the rules discusses #fafafa and
#141414 by name, because the empty-feasible-set reasoning is worth recording
next to the values it produced. Parsed naively that prose reads as two more
colours to score, and one of them is a page background that fails against
itself.

THE LUMINANCE MATH IS WRITTEN OUT HERE rather than imported from
`scripts/test_cta_button.py`, which computes the same thing for the CTA button.
That file's own docstring records why (e9a927f): the two gates are meant to be
independent readings, and sharing a parser lets them agree on the same wrong
answer. Fixing one defect in both files is AP #9; merging them is not.

The backgrounds are READ FROM `assets/css/main.css`, not restated as the two
values that were true today. Retheming the site to a background these colours
fail against re-opens this assertion instead of sailing past a stale constant.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PAGE = REPO / "content" / "community" / "asians-gingers-in-tech" / "index.md"
MAIN_CSS = REPO / "assets" / "css" / "main.css"

WCAG_AA = 4.5

CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
STYLE_BLOCK = re.compile(r"<style>(.*?)</style>", re.S)
DARK_QUERY = re.compile(r"@media\s*\(\s*prefers-color-scheme\s*:\s*dark\s*\)\s*\{")
# `color:` only. Background/border greys on this form are rgba() and are not
# text, so scoring them would be noise; a hex on `color` is always painted text.
COLOUR_DECL = re.compile(r"(?<![-\w])color\s*:\s*(#[0-9a-fA-F]{6})\b")
BG_DECL = re.compile(r"--bg\s*:\s*(#[0-9a-fA-F]{6})\b")


def _linear(channel_byte: int) -> float:
    """One sRGB channel, gamma-expanded to linear light (WCAG 2.1 relative luminance)."""
    c = channel_byte / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast(fg: str, bg: str) -> float:
    a, b = luminance(fg), luminance(bg)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def _split_on_dark_query(css: str) -> tuple[str, str]:
    """Return (light_css, dark_css), splitting on the dark media query.

    Brace-matched rather than regex-captured: the query body holds nested rule
    blocks, so a lazy `\\{.*?\\}` would stop at the first inner close and leave
    the rest of the dark rules sitting in the light half, where they would be
    scored against the wrong background and wrongly fail.
    """
    match = DARK_QUERY.search(css)
    if not match:
        return css, ""
    depth, i = 1, match.end()
    while i < len(css) and depth:
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
        i += 1
    assert depth == 0, "unbalanced braces in the dark-theme media query"
    return css[:match.start()] + css[i:], css[match.end():i - 1]


def _page_style() -> str:
    blocks = STYLE_BLOCK.findall(PAGE.read_text(encoding="utf-8"))
    assert blocks, f"no inline <style> block found in {PAGE.name}"
    return CSS_COMMENT.sub("", "\n".join(blocks))


def _backgrounds() -> tuple[str, str]:
    """The two --bg values from main.css: light (:root) then dark (media query)."""
    css = CSS_COMMENT.sub("", MAIN_CSS.read_text(encoding="utf-8"))
    light_css, dark_css = _split_on_dark_query(css)
    light = BG_DECL.search(light_css)
    dark = BG_DECL.search(dark_css)
    assert light, "no light-theme --bg in assets/css/main.css"
    assert dark, "no dark-theme --bg in assets/css/main.css"
    return light.group(1), dark.group(1)


LIGHT_CSS, DARK_CSS = _split_on_dark_query(_page_style())
LIGHT_BG, DARK_BG = _backgrounds()

LIGHT_COLOURS = COLOUR_DECL.findall(LIGHT_CSS)
DARK_COLOURS = COLOUR_DECL.findall(DARK_CSS)


def test_backgrounds_are_the_two_theme_values():
    """The gate scores against the real tokens, so a retheme re-opens it."""
    assert LIGHT_BG.lower() != DARK_BG.lower()
    assert luminance(LIGHT_BG) > luminance(DARK_BG), "light --bg must be the lighter one"


@pytest.mark.parametrize("colour", LIGHT_COLOURS or [pytest.param(None, marks=pytest.mark.skip)])
def test_light_theme_colour_clears_wcag_aa(colour):
    ratio = contrast(colour, LIGHT_BG)
    assert ratio >= WCAG_AA, (
        f"{colour} on the light background {LIGHT_BG} measures {ratio:.2f}:1, "
        f"below the {WCAG_AA}:1 WCAG AA floor"
    )


@pytest.mark.parametrize("colour", DARK_COLOURS or [pytest.param(None, marks=pytest.mark.skip)])
def test_dark_theme_colour_clears_wcag_aa(colour):
    ratio = contrast(colour, DARK_BG)
    assert ratio >= WCAG_AA, (
        f"{colour} on the dark background {DARK_BG} measures {ratio:.2f}:1, "
        f"below the {WCAG_AA}:1 WCAG AA floor"
    )


def test_every_light_colour_has_a_dark_counterpart():
    """Deleting the dark block must FAIL here, not quietly halve the gate.

    Without this, the two parametrised tests above are satisfied by a page that
    declares only light colours: there is simply nothing in the dark list to
    score. The failure mode is a dark-theme reader looking at #166534 green on
    #141414 at 2.30:1 while every test reports green.
    """
    assert LIGHT_COLOURS, "no text colours found in the page's inline <style>"
    assert len(DARK_COLOURS) == len(LIGHT_COLOURS), (
        f"{len(LIGHT_COLOURS)} light colour(s) but {len(DARK_COLOURS)} dark: "
        "every colour the form paints needs a value for both themes"
    )


def test_counter_states_are_visually_distinct():
    """Red and green must differ per theme, or the state signal says nothing."""
    for label, colours in (("light", LIGHT_COLOURS), ("dark", DARK_COLOURS)):
        assert len(set(c.lower() for c in colours)) > 1, (
            f"the {label} theme paints every state the same colour, "
            "so the counter cannot signal met vs short"
        )
