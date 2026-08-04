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

"Actually painted on" is meant literally, and the counter is why. It carries a
backdrop of its own -- the page background with the same grey wash the field
uses -- added so the number stays legible where it overlaps the story text. So
its two colours sit on rgba(128,128,128,.08) over --bg, while .agit-notice
sits on bare --bg, and scoring both against --bg reports the counter about half
a point more headroom than a reader gets. Measured: #6e6e6e clears the light
page background at 4.885:1 and fails the counter's real surface at 4.484:1,
which is a colour the old reading would have passed. The surfaces are read out
of the page's own CSS per selector, not restated here.

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
from typing import NamedTuple

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

RULE = re.compile(r"(?P<selector>[^{}]+)\{(?P<decls>[^{}]*)\}")
STATE_CLASS = re.compile(r"(?:\.is-[\w-]+)+$")
BG_COLOUR_DECL = re.compile(r"(?<![-\w])background-color\s*:\s*([^;}]+)")
OVERLAY_DECL = re.compile(
    r"linear-gradient\(\s*rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)"
)

Rgb = tuple[float, float, float]


def _linear(channel: float) -> float:
    """One sRGB channel, gamma-expanded to linear light (WCAG 2.1 relative luminance)."""
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def rgb(hex_colour: str) -> Rgb:
    h = hex_colour.lstrip("#")
    return tuple(float(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def luminance(colour: str | Rgb) -> float:
    r, g, b = rgb(colour) if isinstance(colour, str) else colour
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast(fg: str | Rgb, bg: str | Rgb) -> float:
    a, b = luminance(fg), luminance(bg)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def composite(overlay: Rgb, alpha: float, base: Rgb) -> Rgb:
    """A translucent wash over an opaque surface, in sRGB, unquantised.

    Left as floats rather than rounded back to bytes. Rounding first is a
    second model of what the compositor does on top of the one this file
    already makes, and it moves the answer (5.736 vs 5.748 for the light
    'short' red) without moving the verdict. The unrounded value is the one the
    maths actually produces.
    """
    return tuple(overlay[i] * alpha + base[i] * (1 - alpha) for i in range(3))


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


class Painted(NamedTuple):
    """One text colour, and the surface it is actually painted on."""
    selector: str
    colour: str
    backdrop: Rgb
    surface: str          # human-readable, for the failure message


def _rules(css: str) -> list[tuple[str, str]]:
    return [(" ".join(m["selector"].split()), m["decls"]) for m in RULE.finditer(css)]


def _base_selector(selector: str) -> str:
    """`.agit-count.is-short` -> `.agit-count`: the component under its state.

    A state class changes what the component says, not what it sits on. The
    surface is declared once on the base rule, so that is where a state's
    backdrop has to be looked up.
    """
    return STATE_CLASS.sub("", selector).strip()


def _surface_for(selector: str, whole_css: str, theme_bg: str) -> tuple[Rgb, str]:
    """The real backdrop under `selector`, read off the page's own CSS.

    Searched across the WHOLE page style rather than the current theme half:
    the counter declares its backdrop once, outside the dark media query, and
    both themes' state colours sit on it.
    """
    base = _base_selector(selector)
    backdrop, surface = rgb(theme_bg), theme_bg

    for rule_selector, decls in _rules(whole_css):
        if rule_selector != base:
            continue

        declared = BG_COLOUR_DECL.search(decls)
        if declared:
            value = declared.group(1).strip()
            if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                backdrop, surface = rgb(value), value
            else:
                assert value == "var(--bg)", (
                    f"{base} sets background-color: {value!r}, which this gate "
                    f"cannot resolve to a surface. It scores text against what it "
                    f"is painted on, so an unresolvable background means it cannot "
                    f"state what it is measuring."
                )

        wash = OVERLAY_DECL.search(decls)
        if wash:
            r, g, b, alpha = wash.groups()
            over = (float(r), float(g), float(b))
            backdrop = composite(over, float(alpha), backdrop)
            surface = f"rgba({r},{g},{b},{alpha}) over {surface}"

    return backdrop, surface


def _painted(half_css: str, whole_css: str, theme_bg: str) -> list[Painted]:
    out = []
    for selector, decls in _rules(half_css):
        for colour in COLOUR_DECL.findall(decls):
            backdrop, surface = _surface_for(selector, whole_css, theme_bg)
            out.append(Painted(selector, colour, backdrop, surface))
    return out


PAGE_CSS = _page_style()
LIGHT_CSS, DARK_CSS = _split_on_dark_query(PAGE_CSS)
LIGHT_BG, DARK_BG = _backgrounds()

LIGHT_PAINTED = _painted(LIGHT_CSS, PAGE_CSS, LIGHT_BG)
DARK_PAINTED = _painted(DARK_CSS, PAGE_CSS, DARK_BG)

LIGHT_COLOURS = [p.colour for p in LIGHT_PAINTED]
DARK_COLOURS = [p.colour for p in DARK_PAINTED]


def test_backgrounds_are_the_two_theme_values():
    """The gate scores against the real tokens, so a retheme re-opens it."""
    assert LIGHT_BG.lower() != DARK_BG.lower()
    assert luminance(LIGHT_BG) > luminance(DARK_BG), "light --bg must be the lighter one"


def _ids(painted: list[Painted]) -> list[str]:
    return [f"{p.selector} {p.colour}" for p in painted]


@pytest.mark.parametrize(
    "painted",
    LIGHT_PAINTED or [pytest.param(None, marks=pytest.mark.skip)],
    ids=_ids(LIGHT_PAINTED) or None,
)
def test_light_theme_colour_clears_wcag_aa(painted):
    ratio = contrast(painted.colour, painted.backdrop)
    assert ratio >= WCAG_AA, (
        f"{painted.colour} on {painted.surface} measures {ratio:.2f}:1, "
        f"below the {WCAG_AA}:1 WCAG AA floor ({painted.selector})"
    )


@pytest.mark.parametrize(
    "painted",
    DARK_PAINTED or [pytest.param(None, marks=pytest.mark.skip)],
    ids=_ids(DARK_PAINTED) or None,
)
def test_dark_theme_colour_clears_wcag_aa(painted):
    ratio = contrast(painted.colour, painted.backdrop)
    assert ratio >= WCAG_AA, (
        f"{painted.colour} on {painted.surface} measures {ratio:.2f}:1, "
        f"below the {WCAG_AA}:1 WCAG AA floor ({painted.selector})"
    )


PADDING_BOTTOM = re.compile(r"(?<![-\w])padding-bottom\s*:\s*([\d.]+)rem")
SHORTHAND_PADDING = re.compile(r"(?<![-\w])padding\s*:\s*([\d.]+)rem\s+([\d.]+)rem")
FONT_SIZE = re.compile(r"(?<![-\w])font-size\s*:\s*([\d.]+)em")
LINE_HEIGHT = re.compile(r"(?<![-\w])line-height\s*:\s*([\d.]+)")


def _decls_for(selector: str) -> str:
    return "\n".join(d for s, d in _rules(PAGE_CSS) if s == selector)


def test_the_story_field_reserves_a_gutter_for_the_counter():
    """The counter is opaque, so it needs somewhere of its own to sit.

    Without a gutter it lands on the last line of the story at exactly the
    moment a member is looking at it: at the end of what they have written,
    watching the number climb. Measured in Chromium before the gutter went in,
    80 pixels of a 1240-character story were behind the chip.

    This is the CI half, and it is deliberately a weak claim: that the gutter is
    declared and is at least as tall as the counter it has to hold. Whether the
    padding, the box-sizing, the line-height and the chip's offset actually add
    up to a clear strip is a rendered property, and scripts/check_agit_form_counter.py
    is what asserts that, in a real browser, in the pre-publish lane. What this
    catches is the gutter being deleted or shrunk in a lane with no Chromium,
    which is every lane a change normally passes through.
    """
    story_field = _decls_for('.agit-form-wrap textarea[name="feature"]')
    assert story_field, (
        "no rule for the story textarea in the page's inline <style>. The "
        "counter sits inside that field and needs a gutter reserved for it."
    )

    gutter = PADDING_BOTTOM.search(story_field)
    assert gutter, (
        "the story field declares no padding-bottom, so nothing is reserving "
        "space for the counter and it paints straight onto the last line."
    )
    gutter_rem = float(gutter.group(1))

    counter = _decls_for(".agit-form-wrap .agit-count")
    assert counter, "no .agit-count rule to size the gutter against"
    size = FONT_SIZE.search(counter)
    leading = LINE_HEIGHT.search(counter)
    padding = SHORTHAND_PADDING.search(counter)
    assert size and leading and padding, (
        "the counter's own font-size, line-height and padding are what decide "
        "how tall the gutter has to be; one of them is no longer declared here, "
        "so this gate cannot state what it is checking."
    )
    # The field sets `font: inherit`, so the counter's em resolves against the
    # same 1rem base as the gutter it has to fit inside.
    chip_rem = float(size.group(1)) * float(leading.group(1)) + 2 * float(padding.group(1))

    assert gutter_rem >= chip_rem, (
        f"the story field reserves {gutter_rem}rem but the counter is "
        f"{chip_rem:.2f}rem tall, so the chip cannot fit in its own gutter and "
        f"overlaps the story text at the end of it."
    )


def test_the_counter_is_scored_on_its_own_backdrop_not_the_page():
    """The counter sits on a wash of its own, so the page colour is the wrong one.

    Without this, dropping the overlay resolution above leaves every ratio
    passing -- they are all comfortably clear either way today -- while the
    gate quietly goes back to scoring against a surface the counter is not
    painted on. The headroom it reports would then be about half a point more
    than the counter actually has, and a future darkening would be waved
    through against the wrong background. That silence is the whole defect;
    this is what breaks it.
    """
    for painted, theme_bg in ((LIGHT_PAINTED, LIGHT_BG), (DARK_PAINTED, DARK_BG)):
        counter = [p for p in painted if ".agit-count" in p.selector]
        assert counter, "no .agit-count colour found to check the backdrop of"
        for p in counter:
            assert p.backdrop != rgb(theme_bg), (
                f"{p.selector} is being scored against the bare page background "
                f"{theme_bg}, but the counter declares its own backdrop over that "
                f"background. The ratio reported for {p.colour} is therefore not "
                f"the ratio a reader gets."
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


# --------------------------------------------------------------------------
# The stated minimum and the enforced minimum are the same number
# --------------------------------------------------------------------------
#
# Added after Ralph Tier 3 pointed out the gap. Three surfaces carry the 1200:
# the prose a member reads, the client gate, and the server floor. Two of the
# three pairings were already bound in CI (the server floor to its test mirror,
# and the browser gate's own constant to STORY_MIN). The member-facing PROSE was
# bound only in the pre-publish Chromium lane, so CI would have gone green on a
# form that promised one number and enforced another. That is this issue's own
# defect class -- the whole point of the change is that the form STATES the
# minimum -- so it is closed here rather than deferred.

STATED_MINIMUM = re.compile(r"minimum (\d+) characters")
STORY_MIN_DECL = re.compile(r"var STORY_MIN = (\d+);")
FLOOR_DECL = re.compile(r"FIELD_FLOORS\s*=\s*\{[^}]*feature:\s*(\d+)")

AGIT_FORM_JS = REPO / "static" / "js" / "agit-form.js"
CONTRIBUTE_JS = REPO / "functions" / "api" / "contribute.js"


def _one(pattern, path, what):
    matches = pattern.findall(path.read_text(encoding="utf-8"))
    assert matches, f"{what} not found in {path.name}"
    assert len(set(matches)) == 1, (
        f"{what} appears in {path.name} with conflicting values {sorted(set(matches))}"
    )
    return int(matches[0])


def test_the_stated_minimum_equals_the_client_gate():
    """The number the member reads is the number the counter turns green on."""
    stated = _one(STATED_MINIMUM, PAGE, "the stated minimum")
    enforced = _one(STORY_MIN_DECL, AGIT_FORM_JS, "STORY_MIN")
    assert stated == enforced, (
        f"the form promises {stated} characters but the counter turns green at "
        f"{enforced}. A member who writes exactly what was asked for would be "
        f"told to keep going, or told they are done too early."
    )


def test_the_stated_minimum_equals_the_server_floor():
    """And the number the server actually enforces on the submitted story."""
    stated = _one(STATED_MINIMUM, PAGE, "the stated minimum")
    floor = _one(FLOOR_DECL, CONTRIBUTE_JS, "FIELD_FLOORS.feature")
    assert stated == floor, (
        f"the form promises {stated} characters but the server rejects below "
        f"{floor}. Whichever is higher, somebody writes to the stated number and "
        f"is refused."
    )


# ---------------------------------------------------------------------------
# The form's other promises, bound the same way (Stage 5, hoiboy-uk#57).
#
# The two tests above bind the STATED minimum to the two places that enforce
# it. Stage 5 found the same binding missing in two neighbouring places, both
# of which can break the same promise in the same way, so they are bound here
# rather than tracked for later: this file is already the one that holds the
# AGIT form's stated contract against its enforced one.
# ---------------------------------------------------------------------------

HEADERS = REPO / "static" / "_headers"

FIELD_TAG = re.compile(
    r'<(?:input|textarea)\b[^>]*\bname="(?P<name>[a-z_]+)"[^>]*\bmaxlength="(?P<cap>\d+)"',
)
CAPS_DECL = re.compile(r"FIELD_CAPS\s*=\s*\{(?P<body>[^}]*)\}")
CAP_ENTRY = re.compile(r"(?P<key>[a-z_]+)\s*:\s*(?P<value>\d+)")
SOCIALS_TOTAL_DECL = re.compile(r"SOCIALS_MAX_TOTAL\s*=\s*(\d+)")


def _server_caps() -> dict[str, int]:
    """Every server-side length ceiling, keyed by the form field it governs.

    `socials` is deliberately NOT in FIELD_CAPS -- it is routed through
    cleanLines() with its own SOCIALS_MAX_TOTAL rather than through clean()
    -- so a gate built only from FIELD_CAPS would leave that one pair
    unguarded while reporting full coverage.
    """
    source = CONTRIBUTE_JS.read_text(encoding="utf-8")
    body = CAPS_DECL.search(source)
    assert body, "FIELD_CAPS not found in contribute.js"
    caps = {m["key"]: int(m["value"]) for m in CAP_ENTRY.finditer(body["body"])}
    socials = SOCIALS_TOTAL_DECL.search(source)
    assert socials, "SOCIALS_MAX_TOTAL not found in contribute.js"
    caps["socials"] = int(socials.group(1))
    return caps


def test_every_stated_maximum_equals_the_server_cap():
    """No field may advertise a ceiling the server does not actually hold.

    `maxlength` stops typing at N; the server truncates or rejects at its own
    constant. If they disagree the member either loses the tail of what they
    wrote with no warning, or is stopped short of what the server would have
    accepted. Same defect shape as a stated minimum that does not match the
    enforced one, on the other end of the range.
    """
    markup = PAGE.read_text(encoding="utf-8")
    stated = {m["name"]: int(m["cap"]) for m in FIELD_TAG.finditer(markup)}
    assert stated, "no maxlength-bearing fields found - the markup regex is wrong"

    caps = _server_caps()
    mismatched = {
        name: (cap, caps[name])
        for name, cap in stated.items()
        if name in caps and cap != caps[name]
    }
    assert not mismatched, (
        "the form advertises a maximum the server does not enforce: "
        + "; ".join(
            f"{name} maxlength={stated_cap} but server cap {server_cap}"
            for name, (stated_cap, server_cap) in sorted(mismatched.items())
        )
    )

    ungoverned = sorted(set(stated) - set(caps))
    assert not ungoverned, (
        f"{ungoverned} advertise a maxlength with no server-side ceiling behind "
        "it, so the browser is the only thing holding the limit"
    )


BARE_SCRIPT_TAG = re.compile(r'<script\b[^>]*\bsrc="/js/[^"]*"')
VERSIONED_SHORTCODE = re.compile(
    r'\{\{<\s*versioned-script\s+"(?P<path>js/[^"]+)"\s*>\}\}')


def test_the_form_script_is_not_served_stale_against_its_own_markup():
    """The JS enforcing the minimum cannot outlive the HTML promising it.

    Site JS is served unfingerprinted, so its filename never moves when the
    file does. The page revalidates every load; the script gets Cloudflare
    Pages' asset default of max-age=14400. For that window a member gets fresh
    markup promising "minimum 1200 characters" against a cached script carrying
    neither the counter nor the submit guard, and collects a server 400 the
    page never warned them about.

    This originally asserted a Cache-Control rule in static/_headers, and that
    was a gate on the wrong thing. The rule was deployed and MEASURED live:
    the response came back `public, max-age=14400, must-revalidate`, because
    Cloudflare Pages joins same-name headers and the asset default's max-age
    won. The gate was green the whole time, because it asserted what the source
    file SAID rather than what the edge DID. It now asserts the mechanism that
    was measured to work: the version lives in the URL, where no header merge
    can reach it.

    The hash itself is checked against the built page by
    scripts/check_agit_form_counter.py. What this holds is the half a source
    tree can hold: that the page goes through the shortcode at all.
    """
    markup = PAGE.read_text(encoding="utf-8")

    versioned = VERSIONED_SHORTCODE.findall(markup)
    assert "js/agit-form.js" in versioned, (
        "the page does not load js/agit-form.js through the versioned-script "
        "shortcode, so the URL carries no content hash and the script can be "
        "served up to four hours staler than the markup that promises the "
        "minimum. static/_headers cannot fix this: a Cache-Control rule there "
        "is joined with the asset default rather than replacing it, measured "
        "live on this exact file."
    )

    bare = BARE_SCRIPT_TAG.findall(markup)
    assert not bare, (
        f"the page hard-codes {bare}, bypassing the shortcode that puts the "
        f"script's content hash in its URL. A hard-coded /js/ src never changes "
        f"when the file does, which is the whole staleness window."
    )
