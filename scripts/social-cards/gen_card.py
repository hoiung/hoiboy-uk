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

layouts/_partials/head.html picks up share-card.png as the page's og:image, and
default-card.png as the site-wide fallback (both resized to 1200 wide, aspect
preserved, so the 1200x630 source emits a correct 1.91:1 card).

Usage:  python3 scripts/social-cards/gen_card.py [consulting] [legal] [hire-hoi] [landings] [home] [default]
        (no args = all six sets)
Reads:  scripts/social-cards/cards.tsv, legal-cards.tsv, hire-hoi-cards.tsv (slug <TAB> title <TAB>
        tagline [<TAB> style]); style is hoiboy (default) or agit.
        scripts/social-cards/landing-cards.tsv (one content-relative landing path per line;
        title + tagline come from that landing's _index.md frontmatter).
Deps:   rsvg-convert (librsvg), Pillow.  Re-run after editing a *.tsv.
"""
import subprocess, sys, html, textwrap, pathlib, base64, io, re
from card_common import font_face

# --- Palettes (canonical: docs/research/07_DESIGN_TOKENS.md) ------------------
# Each style is (eyebrow text, palette). The palette keys map onto the template
# below; the consulting cards use "hoiboy" so their output is unchanged.
HOIBOY_PAL = {"bg": "#141414", "accent": "#c0533a", "title": "#f0f0f0",
              "tag": "#a6a6a6", "sig": "#87ceeb"}
AGIT_PAL   = {"bg": "#0c1c2d", "accent": "#da611c", "title": "#f9ebdf",
              "tag": "#b5dae7", "sig": "#87ceeb"}
STYLE_MAP  = {"hoiboy": ("HOIBOY AI LTD", HOIBOY_PAL),
              "agit":   ("ASIANS & GINGERS IN TECH", AGIT_PAL)}

# Signature (bottom-right): square logo + "hoiboy.uk", inset by an EQUAL margin
# from the right and bottom edges (symmetric corner placement, identical on every
# card whether the title is 1 or 2 lines). Mirrors the brand bar in dotfiles
# SST3/scripts/sst3_brand.py; logo provenance = assets/images/logo.png.
SIG_TEXT   = "hoiboy.uk"
SIG_FS     = 30         # signature font-size
TAG_FS     = 26         # tagline font-size (IBM Plex Mono is wide; 26 keeps the
                        # longest strapline on one line within the card width)
LOGO_PX    = 64
LOGO_GAP   = 16
SIG_MARGIN = 64         # equal inset from BOTH the right and bottom edges

REPO          = pathlib.Path(__file__).resolve().parents[2]      # repo root
CONSULTING_TSV = REPO / "scripts" / "social-cards" / "cards.tsv"
LEGAL_TSV      = REPO / "scripts" / "social-cards" / "legal-cards.tsv"
HIRE_HOI_TSV   = REPO / "scripts" / "social-cards" / "hire-hoi-cards.tsv"
LANDING_TSV    = REPO / "scripts" / "social-cards" / "landing-cards.tsv"   # section-landing _index.md pages
HOME_MUG       = REPO / "content" / "hoi-mug.jpg"       # home photo-composite source
HOME_CARD      = REPO / "content" / "share-card.png"    # home og:image (home bundle = content/)
FONTS = REPO / "scripts" / "social-cards" / "fonts"
LOGO  = REPO / "assets" / "images" / "logo.png"

# Landing text cards use the house palette; the eyebrow is the site brand (distinct
# from the "HOIBOY AI LTD" company eyebrow on the consulting service cards).
LANDING_EYEBROW = "HOIBOY.UK"
# Home photo card: brand lockup over the mug photo. The strapline is the site's own
# description (config/_default/params.toml) - existing copy, not invented.
HOME_EYEBROW  = "PERSONAL BLOG"
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


def make_svg(eyebrow, title, tagline, logo_uri, pal):
    lines = wrap_title(title)
    fs = 98 if len(lines) == 1 else 86        # VT323 is condensed: a touch larger than sans
    line_h = fs + 4
    start_y = 300 - (len(lines) - 1) * line_h / 2
    title_tspans = "".join(
        f'<text x="110" y="{start_y + i*line_h:.0f}" class="title">{html.escape(l)}</text>'
        for i, l in enumerate(lines)
    )
    rule_y = start_y + (len(lines) - 1) * line_h + 40
    tag_y = start_y + (len(lines) - 1) * line_h + 112

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
    .eyebrow {{ fill: {pal['accent']}; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: 26px; letter-spacing: 3px; }}
    .tag {{ fill: {pal['tag']}; font-family: 'IBM Plex Mono', monospace; font-weight: 400; font-size: {TAG_FS}px; }}
    .sig {{ fill: {pal['sig']}; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: {SIG_FS}px; }}
  </style>
  <rect width="1200" height="630" fill="{pal['bg']}"/>
  <rect x="0" y="0" width="16" height="630" fill="{pal['accent']}"/>
  <text x="110" y="150" class="eyebrow">{html.escape(eyebrow)}</text>
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
    """(title, description|None) from a landing _index.md frontmatter. Mirrors the
    quote-stripping regex in scripts/check_social_cards.py, so a landing card's title
    and tagline are the page's OWN frontmatter - single source of truth, no invented
    copy. A landing with no `description:` gets a title-only card."""
    text = index_md.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    fm = m.group(1) if m else ""

    def field(name):
        mm = re.search(rf'^{name}:\s*["\']?(.+?)["\']?\s*$', fm, re.M)
        return mm.group(1).strip() if mm else None

    title = field("title")
    if not title:
        sys.exit(f"no title in frontmatter: {index_md}")
    return title, field("description")


def fit_tagline(tagline, usable_px=980, max_fs=TAG_FS, min_fs=15, max_lines=4):
    """Largest IBM Plex Mono size in [min_fs, max_fs] whose word-wrap of `tagline` fits
    within max_lines lines of usable_px. Plex Mono is monospace (advance ~0.6*fs) so a
    character-count wrap is an exact width fit. Returns (fs, [lines]). Shrinks to show
    the FULL description (no ellipsis truncation) so operator copy is never mangled."""
    for fs in range(max_fs, min_fs - 1, -1):
        cpl = max(8, int(usable_px / (fs * 0.6)))
        lines = textwrap.wrap(tagline, width=cpl)
        if len(lines) <= max_lines:
            return fs, lines
    cpl = max(8, int(usable_px / (min_fs * 0.6)))
    return min_fs, textwrap.wrap(tagline, width=cpl)


def make_landing_svg(title, tagline, logo_uri, pal=HOIBOY_PAL, eyebrow=LANDING_EYEBROW):
    """Text card for a section-landing _index.md page. Same brand grammar as the
    consulting make_svg (accent bar, eyebrow, VT323 title, accent rule, hoiboy.uk
    signature); the tagline is the page's frontmatter description, shrunk to fit in
    full when present, or omitted (title-only) when the landing has no description."""
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
    if tagline:
        tag_fs, tag_lines = fit_tagline(tagline)
        tag_lh = tag_fs + 10
        ty = rule_y + 58
        for l in tag_lines:
            tag_markup += f'<text x="110" y="{ty:.0f}" class="tag">{html.escape(l)}</text>'
            ty += tag_lh

    clip, sig_markup = _signature_svg(logo_uri, text=True)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    {clip}
  </defs>
  <style>
    {font_face("VT323", VT323_TTF, 400)}
    {font_face("IBM Plex Mono", PLEX_R, 400)}
    {font_face("IBM Plex Mono", PLEX_B, 700)}
    .title {{ fill: {pal['title']}; font-family: 'VT323', monospace; font-size: {fs}px; }}
    .eyebrow {{ fill: {pal['accent']}; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: 26px; letter-spacing: 3px; }}
    .tag {{ fill: {pal['tag']}; font-family: 'IBM Plex Mono', monospace; font-weight: 400; font-size: {tag_fs}px; }}
    .sig {{ fill: {pal['sig']}; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: {SIG_FS}px; }}
  </style>
  <rect width="1200" height="630" fill="{pal['bg']}"/>
  <rect x="0" y="0" width="16" height="630" fill="{pal['accent']}"/>
  <text x="110" y="150" class="eyebrow">{html.escape(eyebrow)}</text>
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


def make_home_svg(photo_uri, logo_uri, pal=HOIBOY_PAL):
    """The home og:image: the mug photo full-bleed, a bottom scrim for text legibility,
    and the brand lockup (eyebrow + big hoiboy.uk wordmark + site strapline) bottom-left,
    with the logo mark bottom-right. Operator: the home card should 'integrate with me
    and the mug image'."""
    clip, sig_markup = _signature_svg(logo_uri, text=False)
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
    .eyebrow {{ fill: {pal['accent']}; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: 24px; letter-spacing: 3px; }}
    .wordmark {{ fill: {pal['title']}; font-family: 'VT323', monospace; font-size: {wm_fs}px; }}
    .tag {{ fill: {pal['tag']}; font-family: 'IBM Plex Mono', monospace; font-weight: 400; font-size: 24px; }}
    .sig {{ fill: {pal['sig']}; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: {SIG_FS}px; }}
  </style>
  <image href="{photo_uri}" x="0" y="0" width="1200" height="630" preserveAspectRatio="xMidYMid slice"/>
  <rect width="1200" height="630" fill="url(#scrim)"/>
  <rect x="0" y="0" width="16" height="630" fill="{pal['accent']}"/>
  <text x="110" y="498" class="eyebrow">{html.escape(HOME_EYEBROW)}</text>
  <text x="108" y="564" class="wordmark">{html.escape(HOME_WORDMARK)}</text>
  <text x="110" y="600" class="tag">{html.escape(HOME_TAGLINE)}</text>
  {sig_markup}
</svg>'''


def gen_landings(tsv, logo_uri):
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
        png = bundle / "share-card.png"
        svg_path = png.with_suffix(".svg")
        try:
            svg_path.write_text(make_landing_svg(title, tagline, logo_uri))
            subprocess.run(["rsvg-convert", "-w", "1200", "-h", "630",
                            str(svg_path), "-o", str(png)], check=True)
        finally:
            svg_path.unlink(missing_ok=True)
        kind = "title+tagline" if tagline else "title-only"
        print(f"  landing/{path} [{kind}]: {png.relative_to(REPO)}")
        n += 1
    return n


def gen_home(logo_uri):
    """Generate the home page's photo-composite share card from the mug photo."""
    if not HOME_MUG.exists():
        sys.exit(f"missing required input: {HOME_MUG}")
    svg_path = HOME_CARD.with_suffix(".svg")
    try:
        svg_path.write_text(make_home_svg(_mug_data_uri(), logo_uri))
        subprocess.run(["rsvg-convert", "-w", "1200", "-h", "630",
                        str(svg_path), "-o", str(HOME_CARD)], check=True)
    finally:
        svg_path.unlink(missing_ok=True)
    print(f"  home: {HOME_CARD.relative_to(REPO)}")
    return 1


def gen_section(section, tsv, logo_uri):
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
        eyebrow, pal = STYLE_MAP[style]
        bundle = REPO / "content" / section / slug
        if not bundle.is_dir():
            sys.exit(f"page bundle not found: {bundle}")
        png = render_card(bundle / "share-card.png", eyebrow, title, tagline, logo_uri, pal)
        print(f"  {section}/{slug} [{style}]: {png.relative_to(REPO)}")
        n += 1
    return n


def gen_default(logo_uri):
    """Generate the site-wide default card (home + taxonomy / section index fallback)."""
    png = render_card(REPO / "content" / "default-card.png",
                      "PERSONAL BLOG", "hoiboy.uk",
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
    n = 0
    if "consulting" in targets:
        n += gen_section("hire-hoi/ai-consultancy", CONSULTING_TSV, logo_uri)
    if "legal" in targets:
        n += gen_section("legal", LEGAL_TSV, logo_uri)
    if "hire-hoi" in targets:
        n += gen_section("hire-hoi", HIRE_HOI_TSV, logo_uri)
    if "landings" in targets:
        n += gen_landings(LANDING_TSV, logo_uri)
    if "home" in targets:
        n += gen_home(logo_uri)
    if "default" in targets:
        n += gen_default(logo_uri)
    print(f"generated {n} cards")


if __name__ == "__main__":
    main()
