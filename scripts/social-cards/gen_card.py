#!/usr/bin/env python3
"""Generate 1200x630 social-share cards (retro type) for the text-card pages.

Covers six card sets, all sharing one brand system:
  - consulting  -> content/hire-hoi/ai-consultancy/<slug>/share-card.png   (cards.tsv)
  - legal       -> content/legal/<slug>/share-card.png        (legal-cards.tsv)
  - hire-hoi    -> content/hire-hoi/<slug>/share-card.png      (hire-hoi-cards.tsv;
                   the top-level Hire Hoi leaf pages, e.g. permanent-roles)
  - landings    -> content/<path>/share-card.png               (landing-cards.tsv; the
                   section-landing _index.md pages, incl. section ROOTS. Title + tagline
                   read from each landing's own frontmatter - title-only when no
                   description. blog-priv#61)
  - home        -> content/share-card.png                      (photo composite from
                   content/hoi-mug.jpg + the hoiboy.uk wordmark. blog-priv#61)
  - default     -> content/default-card.png                   (site-wide og:image
                   fallback for taxonomy / term pages that have no content bundle)

Brand colours are the canonical ones from docs/research/07_DESIGN_TOKENS.md. Two
palettes: the HOIBOY house style (terracotta #c0533a accent, dark #141414) and
the AGIT community style (orange #da611c on navy #0c1c2d) for the AGIT story
guidelines page. Both use the sky-blue #87ceeb hoiboy.uk signature. Type is the
retro stack: VT323 for the title, IBM Plex Mono for the eyebrow / tagline /
signature. The fonts are vendored under fonts/ (OFL, licenses alongside) and
embedded as base64 @font-face so rsvg-convert renders them identically anywhere.

The EYEBROW (the card's top line) is the page's parent trail, uppercased and joined
with " > " - HIRE HOI > AI CONSULTANCY, BLOGS > TECH & AI - read from the per-page
trail.json sidecar Hugo emits (blog-priv#62). It used to be a brand string hardcoded
per card set, which said nothing the logo did not already say and drifted from the
on-page breadcrumb. Both now derive from layouts/_partials/breadcrumb-trail.html, so
they cannot disagree. A page whose parent trail is empty - home, and the top-level
landings - renders no eyebrow line at all.

Because the eyebrow comes from a RENDERED page, the site must be built before the
cards are generated, and rebuilt afterwards so the new PNGs reach public/. That
two-pass order is what scripts/gen-social-cards.sh exists to pin; run that rather
than this script directly.

layouts/_partials/head.html picks up share-card.png as the page's og:image, and
default-card.png as the site-wide fallback (both resized to 1200 wide, aspect
preserved, so the 1200x630 source emits a correct 1.91:1 card).

Usage:  python3 scripts/social-cards/gen_card.py [consulting] [legal] [hire-hoi] [landings] [home] [default]
        (no args = all six sets)
Reads:  scripts/social-cards/cards.tsv, legal-cards.tsv, hire-hoi-cards.tsv (slug <TAB> title <TAB>
        tagline [<TAB> style]); style is hoiboy (default) or agit.
        scripts/social-cards/landing-cards.tsv (one content-relative landing path per line;
        title + tagline come from that landing's _index.md frontmatter).
        public/<url>/trail.json for every page above (HOIBOY_PUBLIC_DIR overrides public/).
Deps:   rsvg-convert (librsvg), Pillow.  Re-run after editing a *.tsv.
"""
import subprocess, sys, os, html, textwrap, pathlib, base64, io, re
import yaml  # already declared: requirements-dev.txt
from card_common import TrailIndex, font_face, load_trails, bundle_key, eyebrow_for

# --- Palettes (canonical: docs/research/07_DESIGN_TOKENS.md) ------------------
# A style selects a PALETTE only. The eyebrow is deliberately not part of it: it is
# the page's own parent trail read from its trail.json sidecar (blog-priv#62), so
# two pages sharing a style still get different eyebrows.
HOIBOY_PAL = {"bg": "#141414", "accent": "#c0533a", "title": "#f0f0f0",
              "tag": "#a6a6a6", "sig": "#87ceeb"}
AGIT_PAL   = {"bg": "#0c1c2d", "accent": "#da611c", "title": "#f9ebdf",
              "tag": "#b5dae7", "sig": "#87ceeb"}
STYLE_MAP  = {"hoiboy": HOIBOY_PAL, "agit": AGIT_PAL}

# Signature (bottom-right): square logo + "hoiboy.uk", inset by an EQUAL margin
# from the right and bottom edges (symmetric corner placement, identical on every
# card whether the title is 1 or 2 lines). Mirrors the brand bar in dotfiles
# SST3/scripts/sst3_brand.py; logo provenance = assets/images/logo.png.
SIG_TEXT   = "hoiboy.uk"
SIG_FS     = 30         # signature font-size
EB_FS      = 26         # eyebrow font-size CEILING (shrinks to fit a deep trail)
EB_MIN_FS  = 16         # smallest eyebrow font-size before failing loud
EB_TRACK   = 3          # eyebrow letter-spacing (px); part of the per-char advance
EB_USABLE  = 980        # 1200px card minus the x=110 inset, mirrored on the right
TITLE_USABLE    = EB_USABLE   # the title starts at the same x=110 inset, so same budget
TITLE_FS_1L     = 98    # leaf-card title font-size on one line
TITLE_FS_2L     = 86    # ... and on two (VT323 is condensed, so larger than sans would be)
TITLE_MAX_LINES = 2     # make_svg's geometry defines ONE and TWO line cases only: at three
                        # lines tag_y runs past SIG_CLEAR_Y and the tagline collides with the
                        # signature. make_landing_svg solves the same collision by dropping
                        # the tagline; a leaf card carries real copy there, so it shrinks the
                        # title to fit instead of discarding the line.
TITLE_ADV       = 0.40  # VT323 advance in em, MEASURED (20 'M' at fs=86 = 688px = 34.40px
                        # each = 0.400*fs). Monospace, so a character count IS an exact
                        # width fit, same reasoning as fit_eyebrow.
TITLE_MIN_FS    = 60    # smallest leaf-card title size before failing loud
TAG_FS     = 26         # tagline font-size (IBM Plex Mono is wide; 26 keeps the
                        # longest strapline on one line within the card width)
TAG_LINE_GAP = 10       # extra px per landing-card tagline line (line height = fs + this)
TAG_MIN_FS   = 15       # smallest tagline font-size before truncating
SIG_CLEAR_Y  = 486      # landing-card tagline block must stay ABOVE this y so it never
                        # collides with the bottom-right signature (logo top ~= 502)
LOGO_PX    = 64
LOGO_GAP   = 16
SIG_MARGIN = 64         # equal inset from BOTH the right and bottom edges

REPO          = pathlib.Path(__file__).resolve().parents[2]      # repo root
CONTENT        = REPO / "content"
# Where Hugo wrote the per-page trail.json sidecars. Overridable so the tests can
# point at a sandbox build instead of the working tree's public/.
PUBLIC         = pathlib.Path(os.environ.get("HOIBOY_PUBLIC_DIR") or (REPO / "public"))
CONSULTING_TSV = REPO / "scripts" / "social-cards" / "cards.tsv"
LEGAL_TSV      = REPO / "scripts" / "social-cards" / "legal-cards.tsv"
HIRE_HOI_TSV   = REPO / "scripts" / "social-cards" / "hire-hoi-cards.tsv"
LANDING_TSV    = REPO / "scripts" / "social-cards" / "landing-cards.tsv"   # section-landing _index.md pages
HOME_MUG       = REPO / "content" / "hoi-mug.jpg"       # home photo-composite source
HOME_CARD      = REPO / "content" / "share-card.png"    # home og:image (home bundle = content/)
FONTS = REPO / "scripts" / "social-cards" / "fonts"
LOGO  = REPO / "assets" / "images" / "logo.png"

# Landing text cards use the house palette. Their eyebrow is the page's parent trail
# like every other card's, so a TOP-LEVEL landing (Hire Hoi, Legal, Skills, Community,
# the Blogs hub) has an empty trail and renders with no eyebrow line at all.
# Home photo card: brand lockup over the mug photo. Its trail is empty by construction,
# so it carries no eyebrow either. The strapline is the site's own description
# (config/_default/params.toml) - existing copy, not invented.
HOME_WORDMARK = "hoiboy.uk"
HOME_TAGLINE  = "Food, booze, adventure, dance, tech and AI."

VT323_TTF = FONTS / "VT323-Regular.ttf"
PLEX_R    = FONTS / "IBMPlexMono-Regular.ttf"
PLEX_B    = FONTS / "IBMPlexMono-Bold.ttf"


def logo_data_uri():
    from PIL import Image
    im = Image.open(LOGO).convert("RGBA").resize((96, 96), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def text_width(s, fs):
    """Measure the signature text width (IBM Plex Mono Bold) so the logo sits left of it."""
    from PIL import ImageFont
    try:
        return ImageFont.truetype(str(PLEX_B), fs).getbbox(s)[2]
    except Exception:
        return int(len(s) * fs * 0.6)   # mono fallback


def wrap_title(title, max_chars=22):
    return textwrap.wrap(title, width=max_chars) or [title]


def fit_title(title):
    """(font-size, lines) for a LEAF card title, capped at TITLE_MAX_LINES.

    The default 22-char wrap is conservative rather than geometric: at TITLE_FS_2L the
    card actually affords 28 characters (980px / (86*0.40)). A title long enough to need
    a third line under the 22-char wrap can therefore still fit two lines once the wrap
    uses the width the card really has, so try that before shrinking anything.

    Only then shrink. Below TITLE_MIN_FS, fail loud rather than render a card whose
    tagline sits on top of the signature - the failure this exists to prevent is silent,
    because a 3-line title still renders, it just renders broken.

    Titles that already fit in <=2 lines at width 22 return byte-identical output to
    before this function existed, which is what keeps every other card unchanged.
    """
    lines = wrap_title(title)
    if len(lines) <= TITLE_MAX_LINES:
        return (TITLE_FS_1L if len(lines) == 1 else TITLE_FS_2L), lines
    for fs in range(TITLE_FS_2L, TITLE_MIN_FS - 1, -1):
        wrapped = wrap_title(title, max_chars=int(TITLE_USABLE // (fs * TITLE_ADV)))
        if len(wrapped) <= TITLE_MAX_LINES:
            return fs, wrapped
    sys.exit(f"title does not fit the card: {title!r} still needs more than "
             f"{TITLE_MAX_LINES} lines at {TITLE_MIN_FS}px. Shorten the page title.")


def fit_eyebrow(eyebrow, usable_px=EB_USABLE, max_fs=EB_FS, min_fs=EB_MIN_FS, tracking=EB_TRACK):
    """Largest font-size in [min_fs, max_fs] at which `eyebrow` fits on ONE line inside
    usable_px. IBM Plex Mono is monospace (advance 0.6em) and the card adds a fixed
    letter-spacing, so a run of n characters is exactly n*(fs*0.6 + tracking) wide - a
    character count IS an exact width fit here, no font metrics needed.

    At the 26px ceiling that is 52 characters. The longest trail on the site today is
    'HIRE HOI > AI CONSULTANCY > PORTFOLIO' at 37, so nothing shrinks yet; a deeper
    future trail shrinks instead of overflowing, and one that will not fit even at
    min_fs (78 characters; 77 still fit at fs=16) fails loud rather than running off
    the edge of the card.
    """
    for fs in range(max_fs, min_fs - 1, -1):
        if len(eyebrow) * (fs * 0.6 + tracking) <= usable_px:
            return fs
    sys.exit(f"eyebrow does not fit the card: {eyebrow!r} is {len(eyebrow)} characters, which "
             f"overruns {usable_px}px even at {min_fs}px. Shorten the page's trail.")


def eyebrow_svg(eyebrow, y=150):
    """(font-size, markup) for the eyebrow line. An empty eyebrow - a top-level landing
    or home, whose parent trail is empty - emits NO text node at all, rather than an
    empty one, so the card carries no stray element. The returned font-size still feeds
    the .eyebrow CSS rule so the class is always defined."""
    if not eyebrow:
        return EB_FS, ""
    fs = fit_eyebrow(eyebrow)
    return fs, f'<text x="110" y="{y}" class="eyebrow">{html.escape(eyebrow)}</text>'


def make_svg(eyebrow, title, tagline, logo_uri, pal):
    fs, lines = fit_title(title)
    line_h = fs + 4
    start_y = 300 - (len(lines) - 1) * line_h / 2
    title_tspans = "".join(
        f'<text x="110" y="{start_y + i*line_h:.0f}" class="title">{html.escape(l)}</text>'
        for i, l in enumerate(lines)
    )
    rule_y = start_y + (len(lines) - 1) * line_h + 40
    tag_y = start_y + (len(lines) - 1) * line_h + 112
    eb_fs, eb_markup = eyebrow_svg(eyebrow)

    # Signature group: equal SIG_MARGIN inset from right + bottom edges.
    tw = text_width(SIG_TEXT, SIG_FS)
    sig_right = 1200 - SIG_MARGIN
    logo_bottom = 630 - SIG_MARGIN
    logo_y = logo_bottom - LOGO_PX
    logo_x = sig_right - tw - LOGO_GAP - LOGO_PX
    sig_y = logo_y + LOGO_PX / 2 + SIG_FS * 0.34
    rx = round(LOGO_PX * 0.2)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <clipPath id="logoclip"><rect x="{logo_x:.0f}" y="{logo_y:.0f}" width="{LOGO_PX}" height="{LOGO_PX}" rx="{rx}"/></clipPath>
  </defs>
  <style>
    {font_face("VT323", VT323_TTF, 400)}
    {font_face("IBM Plex Mono", PLEX_R, 400)}
    {font_face("IBM Plex Mono", PLEX_B, 700)}
    .title {{ fill: {pal['title']}; font-family: 'VT323', monospace; font-size: {fs}px; }}
    .eyebrow {{ fill: {pal['accent']}; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: {eb_fs}px; letter-spacing: {EB_TRACK}px; }}
    .tag {{ fill: {pal['tag']}; font-family: 'IBM Plex Mono', monospace; font-weight: 400; font-size: {TAG_FS}px; }}
    .sig {{ fill: {pal['sig']}; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: {SIG_FS}px; }}
  </style>
  <rect width="1200" height="630" fill="{pal['bg']}"/>
  <rect x="0" y="0" width="16" height="630" fill="{pal['accent']}"/>
  {eb_markup}
  {title_tspans}
  <rect x="112" y="{rule_y:.0f}" width="90" height="7" fill="{pal['accent']}"/>
  <text x="110" y="{tag_y:.0f}" class="tag">{html.escape(tagline)}</text>
  <image href="{logo_uri}" x="{logo_x:.0f}" y="{logo_y:.0f}" width="{LOGO_PX}" height="{LOGO_PX}" clip-path="url(#logoclip)"/>
  <text x="{sig_right:.0f}" y="{sig_y:.0f}" text-anchor="end" class="sig">{SIG_TEXT}</text>
</svg>'''


def render_card(png_path, eyebrow, title, tagline, logo_uri, pal):
    """Render one card SVG through rsvg-convert to png_path (svg is a temp sibling)."""
    svg_path = png_path.with_suffix(".svg")
    svg_path.write_text(make_svg(eyebrow, title, tagline, logo_uri, pal))
    subprocess.run(["rsvg-convert", "-w", "1200", "-h", "630",
                    str(svg_path), "-o", str(png_path)], check=True)
    svg_path.unlink()
    return png_path


# --- Section-landing (_index.md) + home cards (blog-priv#61) ------------------
# make_svg above stays byte-for-byte for the consulting/legal/hire-hoi leaf cards
# (so those shipped PNGs never regenerate). The landing + home cards below share one
# NEW signature helper; make_svg deliberately keeps its own inline copy rather than
# adopt the helper, to avoid touching the shipped-card render path at all.

def _signature_svg(logo_uri, text=True):
    """The bottom-right brand mark, inset an equal SIG_MARGIN from the right + bottom
    edges. text=True -> square logo + 'hoiboy.uk' wordmark (landing cards, matching the
    consulting cards). text=False -> logo only, flush right (the home card already
    carries a big 'hoiboy.uk' wordmark, so the corner mark drops the duplicate text).
    Returns (clipPath_def, markup); the caller supplies the .sig CSS class."""
    rx = round(LOGO_PX * 0.2)
    logo_y = 630 - SIG_MARGIN - LOGO_PX
    if text:
        tw = text_width(SIG_TEXT, SIG_FS)
        sig_right = 1200 - SIG_MARGIN
        logo_x = sig_right - tw - LOGO_GAP - LOGO_PX
        sig_y = logo_y + LOGO_PX / 2 + SIG_FS * 0.34
        text_markup = (f'\n  <text x="{sig_right:.0f}" y="{sig_y:.0f}" text-anchor="end" '
                       f'class="sig">{SIG_TEXT}</text>')
    else:
        logo_x = 1200 - SIG_MARGIN - LOGO_PX
        text_markup = ""
    clip = (f'<clipPath id="logoclip"><rect x="{logo_x:.0f}" y="{logo_y:.0f}" '
            f'width="{LOGO_PX}" height="{LOGO_PX}" rx="{rx}"/></clipPath>')
    markup = (f'<image href="{logo_uri}" x="{logo_x:.0f}" y="{logo_y:.0f}" '
              f'width="{LOGO_PX}" height="{LOGO_PX}" clip-path="url(#logoclip)"/>' + text_markup)
    return clip, markup


def read_landing_meta(index_md):
    """(title, description|None) from a landing _index.md frontmatter.

    A landing card's title and tagline are the page's OWN frontmatter - single
    source of truth, no invented copy. A landing with no `description:` gets a
    title-only card.

    Parsed with yaml.safe_load, exactly as the sibling reader
    scripts/validate_frontmatter.py:96 already does, rather than with a
    line-anchored regex. The regex captured only the FIRST line of a value, so a
    block scalar

        description: >
          a perfectly ordinary folded description

    collapsed to the single character ">" and rendered that straight into the
    committed 1200x630 share-card.png served as og:image. Nothing caught it:
    scripts/check_social_cards.py asserts a card EXISTS, never what it says.
    """
    text = index_md.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    try:
        fm = yaml.safe_load(m.group(1)) if m else None
    except yaml.YAMLError as exc:
        sys.exit(f"unparseable frontmatter in {index_md}: {exc}")
    if fm is None:
        fm = {}
    if not isinstance(fm, dict):
        sys.exit(f"frontmatter is not a mapping in {index_md}: {type(fm).__name__}")

    def field(name):
        value = fm.get(name)
        if value is None:
            return None
        # Die rather than render a Python repr into a PNG: a date-like or
        # numeric `description` parses as a non-str and would ship as e.g.
        # "datetime.date(2026, 7, 27)" on a card nobody re-reads before publish.
        # bool BEFORE the numeric check: bool subclasses int in Python, so an
        # unquoted YAML 1.1 boolean-like scalar (no / yes / on / off / true /
        # false) passed straight through and rendered "False" onto the card.
        # A landing described as "no" is not fanciful - it is one word.
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            sys.exit(
                f"{name} in {index_md} parsed as {type(value).__name__}, not text. "
                f"Quote it, so the card renders the words you meant."
            )
        return str(value).strip() or None

    title = field("title")
    if not title:
        sys.exit(f"no title in frontmatter: {index_md}")
    return title, field("description")


TAG_MAX_LINES = 4       # design cap on landing-card tagline lines (a card, not an essay)


def _tag_max_lines(avail_px, fs):
    """How many tagline lines of font-size `fs` fit in `avail_px` of vertical space,
    capped at the design maximum. n baselines span (n-1) line heights, so n fits when
    (n-1)*(fs+TAG_LINE_GAP) <= avail_px, i.e. n <= avail_px//line_h + 1. At least 1.
    For a 1-line title (avail_px ~128) this is TAG_MAX_LINES at every fs in [15,26], so
    the card output matches the original fixed-4 fitter; a 2-line title shrinks avail_px
    and this returns fewer, keeping the block clear of the signature."""
    line_h = fs + TAG_LINE_GAP
    return max(1, min(TAG_MAX_LINES, int(avail_px // line_h) + 1))


def fit_tagline(tagline, usable_px=980, avail_px=128, max_fs=TAG_FS, min_fs=TAG_MIN_FS):
    """Largest IBM Plex Mono size in [min_fs, max_fs] whose word-wrap of `tagline` fits
    BOTH usable_px wide AND avail_px tall (so the block can never run into the space below
    it - the bottom-right signature - regardless of how far a wrapped title pushed it
    down). Plex Mono is monospace (advance ~0.6*fs) so a character-count wrap is an exact
    width fit; the vertical fit is line-count * (fs + TAG_LINE_GAP). Returns (fs, [lines]).
    Shows the FULL description for realistic copy (no truncation - every current landing
    fits); text too long to fit even at min_fs is truncated with an ellipsis so the block
    stays within its box."""
    for fs in range(max_fs, min_fs - 1, -1):
        cpl = max(8, int(usable_px / (fs * 0.6)))
        lines = textwrap.wrap(tagline, width=cpl)
        if len(lines) <= _tag_max_lines(avail_px, fs):
            return fs, lines
    cpl = max(8, int(usable_px / (min_fs * 0.6)))
    max_lines = _tag_max_lines(avail_px, min_fs)
    lines = textwrap.wrap(tagline, width=cpl)
    if len(lines) > max_lines:                       # too long even at min_fs: bound + ellipsis
        lines = lines[:max_lines]
        last = lines[-1]
        if len(last) + 3 > cpl:
            last = last[:max(0, cpl - 3)].rstrip()
        lines[-1] = last + "..."
    return min_fs, lines


def make_landing_svg(title, tagline, logo_uri, pal=HOIBOY_PAL, eyebrow=""):
    """Text card for a section-landing _index.md page. Same brand grammar as the
    consulting make_svg (accent bar, eyebrow, VT323 title, accent rule, hoiboy.uk
    signature); the tagline is the page's frontmatter description, shrunk to fit in
    full when present, or omitted (title-only) when the landing has no description.
    The eyebrow defaults to empty because the top-level landings are the cards that
    carry none; a nested landing is passed its parent trail by gen_landings()."""
    lines = wrap_title(title)
    fs = 98 if len(lines) == 1 else 86
    line_h = fs + 4
    title_y = 260
    title_tspans = "".join(
        f'<text x="110" y="{title_y + i*line_h:.0f}" class="title">{html.escape(l)}</text>'
        for i, l in enumerate(lines)
    )
    rule_y = title_y + (len(lines) - 1) * line_h + 40

    tag_fs = TAG_FS
    tag_markup = ""
    tag_top = rule_y + 58                             # first tagline baseline
    avail_px = SIG_CLEAR_Y - tag_top                  # room between the rule and the signature
    # Render the tagline only if at least one line fits above the signature. A title that
    # wraps to 2 lines shrinks the tagline; a title long enough to wrap to 3+ lines leaves
    # no room, so the tagline is dropped (title-only) rather than overlapping the mark.
    # Landing titles are short section labels, so this only guards pathological future copy.
    if tagline and avail_px >= TAG_MIN_FS + TAG_LINE_GAP:
        tag_fs, tag_lines = fit_tagline(tagline, avail_px=avail_px)
        tag_lh = tag_fs + TAG_LINE_GAP
        ty = tag_top
        for l in tag_lines:
            tag_markup += f'<text x="110" y="{ty:.0f}" class="tag">{html.escape(l)}</text>'
            ty += tag_lh

    clip, sig_markup = _signature_svg(logo_uri, text=True)
    eb_fs, eb_markup = eyebrow_svg(eyebrow)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    {clip}
  </defs>
  <style>
    {font_face("VT323", VT323_TTF, 400)}
    {font_face("IBM Plex Mono", PLEX_R, 400)}
    {font_face("IBM Plex Mono", PLEX_B, 700)}
    .title {{ fill: {pal['title']}; font-family: 'VT323', monospace; font-size: {fs}px; }}
    .eyebrow {{ fill: {pal['accent']}; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: {eb_fs}px; letter-spacing: {EB_TRACK}px; }}
    .tag {{ fill: {pal['tag']}; font-family: 'IBM Plex Mono', monospace; font-weight: 400; font-size: {tag_fs}px; }}
    .sig {{ fill: {pal['sig']}; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: {SIG_FS}px; }}
  </style>
  <rect width="1200" height="630" fill="{pal['bg']}"/>
  <rect x="0" y="0" width="16" height="630" fill="{pal['accent']}"/>
  {eb_markup}
  {title_tspans}
  <rect x="112" y="{rule_y:.0f}" width="90" height="7" fill="{pal['accent']}"/>
  {tag_markup}
  {sig_markup}
</svg>'''


def _mug_data_uri():
    """The mug photo, EXIF-honoured then re-decoded (drops EXIF), cropped to fill the
    1200x630 card (centred slightly high so Hoi + the mug both stay in frame)."""
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(HOME_MUG)).convert("RGB")
    im = ImageOps.fit(im, (1200, 630), Image.LANCZOS, centering=(0.5, 0.42))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=86, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def make_home_svg(photo_uri, logo_uri, pal=HOIBOY_PAL, eyebrow=""):
    """The home og:image: the mug photo full-bleed, a bottom scrim for text legibility,
    and the brand lockup (big hoiboy.uk wordmark + site strapline) bottom-left, with the
    logo mark bottom-right. Operator: the home card should 'integrate with me and the
    mug image'. Home is the root of the trail, so its parent trail is empty by
    construction and the eyebrow line is omitted; the parameter exists so the eyebrow
    rule is uniform across all three builders rather than special-cased here."""
    clip, sig_markup = _signature_svg(logo_uri, text=False)
    eb_fs, eb_markup = eyebrow_svg(eyebrow, y=498)
    wm_fs = 82
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    {clip}
    <linearGradient id="scrim" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0.42" stop-color="{pal['bg']}" stop-opacity="0"/>
      <stop offset="1" stop-color="{pal['bg']}" stop-opacity="0.88"/>
    </linearGradient>
  </defs>
  <style>
    {font_face("VT323", VT323_TTF, 400)}
    {font_face("IBM Plex Mono", PLEX_R, 400)}
    {font_face("IBM Plex Mono", PLEX_B, 700)}
    .eyebrow {{ fill: {pal['accent']}; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: {eb_fs}px; letter-spacing: {EB_TRACK}px; }}
    .wordmark {{ fill: {pal['title']}; font-family: 'VT323', monospace; font-size: {wm_fs}px; }}
    .tag {{ fill: {pal['tag']}; font-family: 'IBM Plex Mono', monospace; font-weight: 400; font-size: 24px; }}
    .sig {{ fill: {pal['sig']}; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: {SIG_FS}px; }}
  </style>
  <image href="{photo_uri}" x="0" y="0" width="1200" height="630" preserveAspectRatio="xMidYMid slice"/>
  <rect width="1200" height="630" fill="url(#scrim)"/>
  <rect x="0" y="0" width="16" height="630" fill="{pal['accent']}"/>
  {eb_markup}
  <text x="108" y="564" class="wordmark">{html.escape(HOME_WORDMARK)}</text>
  <text x="110" y="600" class="tag">{html.escape(HOME_TAGLINE)}</text>
  {sig_markup}
</svg>'''


def gen_landings(tsv: pathlib.Path, logo_uri: str, trails: TrailIndex | None) -> int:
    """Generate share-card.png for each section-landing path in landing-cards.tsv. Each
    row is a bundle path under content/ whose _index.md supplies the title + (optional)
    tagline. Writes into that landing's own bundle so head.html resolves it as og:image."""
    if not tsv.exists():
        sys.exit(f"missing required input: {tsv}")
    n = 0
    for raw in tsv.read_text().splitlines():
        raw = raw.rstrip("\n")
        if not raw or raw.startswith("#"):
            continue
        path = raw.split("\t")[0].strip()
        bundle = REPO / "content" / path
        index_md = bundle / "_index.md"
        if not index_md.exists():
            sys.exit(f"landing _index.md not found: {index_md}")
        title, tagline = read_landing_meta(index_md)
        eyebrow = eyebrow_for(trails, bundle_key(bundle, CONTENT))
        png = bundle / "share-card.png"
        svg_path = png.with_suffix(".svg")
        try:
            svg_path.write_text(make_landing_svg(title, tagline, logo_uri, eyebrow=eyebrow))
            subprocess.run(["rsvg-convert", "-w", "1200", "-h", "630",
                            str(svg_path), "-o", str(png)], check=True)
        finally:
            svg_path.unlink(missing_ok=True)
        kind = "title+tagline" if tagline else "title-only"
        print(f"  landing/{path} [{kind}] eyebrow={eyebrow or '(none)'}: {png.relative_to(REPO)}")
        n += 1
    return n


def gen_home(logo_uri: str, trails: TrailIndex | None) -> int:
    """Generate the home page's photo-composite share card from the mug photo."""
    if not HOME_MUG.exists():
        sys.exit(f"missing required input: {HOME_MUG}")
    eyebrow = eyebrow_for(trails, bundle_key(CONTENT, CONTENT))
    svg_path = HOME_CARD.with_suffix(".svg")
    try:
        svg_path.write_text(make_home_svg(_mug_data_uri(), logo_uri, eyebrow=eyebrow))
        subprocess.run(["rsvg-convert", "-w", "1200", "-h", "630",
                        str(svg_path), "-o", str(HOME_CARD)], check=True)
    finally:
        svg_path.unlink(missing_ok=True)
    print(f"  home: {HOME_CARD.relative_to(REPO)}")
    return 1


def gen_section(section: str, tsv: pathlib.Path, logo_uri: str,
                trails: TrailIndex | None) -> int:
    """Generate share-card.png for each row of a section TSV (slug/title/tagline[/style])."""
    if not tsv.exists():
        sys.exit(f"missing required input: {tsv}")
    n = 0
    for raw in tsv.read_text().splitlines():
        raw = raw.rstrip("\n")
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split("\t")
        slug, title, tagline = parts[0], parts[1], parts[2]
        style = parts[3] if len(parts) > 3 and parts[3] else "hoiboy"
        if style not in STYLE_MAP:
            sys.exit(f"unknown style '{style}' for {section}/{slug} (expected: {', '.join(STYLE_MAP)})")
        pal = STYLE_MAP[style]
        bundle = REPO / "content" / section / slug
        if not bundle.is_dir():
            sys.exit(f"page bundle not found: {bundle}")
        eyebrow = eyebrow_for(trails, bundle_key(bundle, CONTENT))
        png = render_card(bundle / "share-card.png", eyebrow, title, tagline, logo_uri, pal)
        print(f"  {section}/{slug} [{style}] eyebrow={eyebrow or '(none)'}: {png.relative_to(REPO)}")
        n += 1
    return n


def gen_default(logo_uri):
    """Generate the site-wide default card: the og:image fallback for taxonomy / term
    pages, which have no content bundle. It stands for no single page, so it has no
    parent trail and therefore no eyebrow - the same rule every other card follows,
    not a special case."""
    png = render_card(REPO / "content" / "default-card.png",
                      "", "hoiboy.uk",
                      "Food, booze, adventure, dance, tech and AI.",
                      logo_uri, HOIBOY_PAL)
    print(f"  default: {png.relative_to(REPO)}")
    return 1


def main():
    targets = sys.argv[1:] or ["consulting", "legal", "hire-hoi", "landings", "home", "default"]
    for p in (LOGO, VT323_TTF, PLEX_R, PLEX_B):
        if not p.exists():
            sys.exit(f"missing required input: {p}")
    logo_uri = logo_data_uri()
    # Every set except `default` derives its eyebrow from a rendered page, so the trail
    # index is loaded only when one of those is in play - `gen_card.py default` still
    # works on a tree that has never been built.
    trails = load_trails(PUBLIC) if [t for t in targets if t != "default"] else None
    n = 0
    if "consulting" in targets:
        n += gen_section("hire-hoi/ai-consultancy", CONSULTING_TSV, logo_uri, trails)
    if "legal" in targets:
        n += gen_section("legal", LEGAL_TSV, logo_uri, trails)
    if "hire-hoi" in targets:
        n += gen_section("hire-hoi", HIRE_HOI_TSV, logo_uri, trails)
    if "landings" in targets:
        n += gen_landings(LANDING_TSV, logo_uri, trails)
    if "home" in targets:
        n += gen_home(logo_uri, trails)
    if "default" in targets:
        n += gen_default(logo_uri)
    print(f"generated {n} cards")


if __name__ == "__main__":
    main()
