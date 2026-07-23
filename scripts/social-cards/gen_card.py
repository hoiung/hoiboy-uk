#!/usr/bin/env python3
"""Generate 1200x630 social-share cards (retro type) for the text-card pages.

Covers three card sets, all sharing one template:
  - consulting  -> content/hire-hoi/ai-consultancy/<slug>/share-card.png   (cards.tsv)
  - legal       -> content/legal/<slug>/share-card.png        (legal-cards.tsv)
  - default     -> content/default-card.png                   (site-wide og:image
                   fallback for the home page + taxonomy / section index pages)

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

Usage:  python3 scripts/social-cards/gen_card.py [consulting] [legal] [default]
        (no args = all three sets)
Reads:  scripts/social-cards/cards.tsv, legal-cards.tsv (slug <TAB> title <TAB>
        tagline [<TAB> style]); style is hoiboy (default) or agit.
Deps:   rsvg-convert (librsvg), Pillow.  Re-run after editing a *.tsv.
"""
import subprocess, sys, html, textwrap, pathlib, base64, io
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
FONTS = REPO / "scripts" / "social-cards" / "fonts"
LOGO  = REPO / "assets" / "images" / "logo.png"

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
    targets = sys.argv[1:] or ["consulting", "legal", "default"]
    for p in (LOGO, VT323_TTF, PLEX_R, PLEX_B):
        if not p.exists():
            sys.exit(f"missing required input: {p}")
    logo_uri = logo_data_uri()
    n = 0
    if "consulting" in targets:
        n += gen_section("hire-hoi/ai-consultancy", CONSULTING_TSV, logo_uri)
    if "legal" in targets:
        n += gen_section("legal", LEGAL_TSV, logo_uri)
    if "default" in targets:
        n += gen_default(logo_uri)
    print(f"generated {n} cards")


if __name__ == "__main__":
    main()
