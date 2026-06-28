#!/usr/bin/env python3
"""Generate 1200x630 social-share cards for the consulting pages (retro type).

Brand colours are the canonical ones from docs/research/07_DESIGN_TOKENS.md
(terracotta #c0533a accent, sky-blue #87ceeb signature, dark #141414). Type is
the consulting-ops retro stack: VT323 for the title, IBM Plex Mono for the
eyebrow / tagline / hoiboy.uk signature. The fonts are vendored under fonts/
(OFL, licenses alongside) and embedded as base64 @font-face so rsvg-convert
renders them identically anywhere — no system-font dependency.

Each card is written to content/consulting/<slug>/share-card.png, which
layouts/_partials/head.html picks up as the page's og:image (resized to 1200
wide, aspect preserved — so the 1200x630 source emits a correct 1.91:1 card).

Usage:  python3 scripts/social-cards/gen_card.py
Reads:  scripts/social-cards/cards.tsv  (slug <TAB> title <TAB> tagline)
Deps:   rsvg-convert (librsvg), Pillow.  Re-run after editing cards.tsv.
"""
import subprocess, sys, html, textwrap, pathlib, base64, io

ACCENT = "#c0533a"   # terracotta — the only warm colour
SKY    = "#87ceeb"   # hoiboy.uk signature blue
BG     = "#141414"   # dark background
TITLE  = "#f0f0f0"
TAG    = "#a6a6a6"

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

REPO  = pathlib.Path(__file__).resolve().parents[2]      # repo root
TSV   = REPO / "scripts" / "social-cards" / "cards.tsv"
FONTS = REPO / "scripts" / "social-cards" / "fonts"
LOGO  = REPO / "assets" / "images" / "logo.png"

VT323_TTF = FONTS / "VT323-Regular.ttf"
PLEX_R    = FONTS / "IBMPlexMono-Regular.ttf"
PLEX_B    = FONTS / "IBMPlexMono-Bold.ttf"


def _b64(p):
    return base64.b64encode(pathlib.Path(p).read_bytes()).decode()


def font_face(family, ttf, weight):
    return (f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"src:url(data:font/ttf;base64,{_b64(ttf)}) format('truetype');}}")


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


def make_svg(title, tagline, logo_uri):
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
    .title {{ fill: {TITLE}; font-family: 'VT323', monospace; font-size: {fs}px; }}
    .eyebrow {{ fill: {ACCENT}; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: 26px; letter-spacing: 3px; }}
    .tag {{ fill: {TAG}; font-family: 'IBM Plex Mono', monospace; font-weight: 400; font-size: {TAG_FS}px; }}
    .sig {{ fill: {SKY}; font-family: 'IBM Plex Mono', monospace; font-weight: 700; font-size: {SIG_FS}px; }}
  </style>
  <rect width="1200" height="630" fill="{BG}"/>
  <rect x="0" y="0" width="16" height="630" fill="{ACCENT}"/>
  <text x="110" y="150" class="eyebrow">HOIBOY AI LTD</text>
  {title_tspans}
  <rect x="112" y="{rule_y:.0f}" width="90" height="7" fill="{ACCENT}"/>
  <text x="110" y="{tag_y:.0f}" class="tag">{html.escape(tagline)}</text>
  <image href="{logo_uri}" x="{logo_x:.0f}" y="{logo_y:.0f}" width="{LOGO_PX}" height="{LOGO_PX}" clip-path="url(#logoclip)"/>
  <text x="{sig_right:.0f}" y="{sig_y:.0f}" text-anchor="end" class="sig">{SIG_TEXT}</text>
</svg>'''


def main():
    for p in (TSV, LOGO, VT323_TTF, PLEX_R, PLEX_B):
        if not p.exists():
            sys.exit(f"missing required input: {p}")
    logo_uri = logo_data_uri()
    n = 0
    for raw in TSV.read_text().splitlines():
        raw = raw.rstrip("\n")
        if not raw or raw.startswith("#"):
            continue
        slug, title, tagline = raw.split("\t")
        bundle = REPO / "content" / "consulting" / slug
        if not bundle.is_dir():
            sys.exit(f"page bundle not found: {bundle}")
        svg_path = bundle / "share-card.svg"
        png_path = bundle / "share-card.png"
        svg_path.write_text(make_svg(title, tagline, logo_uri))
        subprocess.run(["rsvg-convert", "-w", "1200", "-h", "630",
                        str(svg_path), "-o", str(png_path)], check=True)
        svg_path.unlink()
        print(f"  {slug}: {png_path.relative_to(REPO)}")
        n += 1
    print(f"generated {n} cards")


if __name__ == "__main__":
    main()
