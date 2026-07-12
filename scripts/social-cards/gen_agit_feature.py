#!/usr/bin/env python3
"""Generate the branded image pair for AGIT community features (Issue #47).

Each feature gets two images, dropped into its page bundle under
content/community/agit-featured/<slug>/:

  1. hero.jpg       portrait 4:5 (1080x1350) display photo + AGIT logo watermark,
                    EXIF-stripped. This is the on-page hero, the index-card image,
                    and what the featured person posts straight to socials.
  2. share-card.png branded landscape 1200x630 link-preview card: the submitted
                    photo inset on the left, a blue->cream gradient panel on the
                    right with the AGIT eyebrow + the person's name + role, and the
                    AGIT logo watermark bottom-right. head.html prefers share-card.*
                    over the hero for og:image, so a portrait submission no longer
                    gets its head/legs sliced off in the link preview.

Why a separate script from gen_card.py: the consulting cards are text-only (no
photo) and TSV/tagline-driven; AGIT features are photo-driven and need a portrait
hero as well as the landscape card. Both share the same brand system: the vendored
VT323 + IBM Plex Mono faces under fonts/, base64 @font-face embedding so rsvg-convert
renders identically anywhere, and a circular logo watermark.

Brand: AGIT navy #0c1c2d + orange #da611c on a powder-blue->cream gradient sampled
from AGIT_banner_global_01.png. The AGIT logo is vendored at assets/images/agit-logo.png
(a copy of the Drive master; masked to a circle at render time).

Inputs (so the whole set can be regenerated after a design change, like cards.tsv):
  scripts/social-cards/agit-features.tsv   slug <TAB> name <TAB> role   (role may be "")
  scripts/social-cards/agit-sources/<slug>.<ext>   the EXIF-clean source photo

Usage:
  python3 scripts/social-cards/gen_agit_feature.py            # regenerate every feature
  python3 scripts/social-cards/gen_agit_feature.py <slug>     # regenerate one feature
Deps: rsvg-convert (librsvg), Pillow.
"""
import subprocess, sys, html, base64, io, pathlib
from PIL import Image, ImageOps, ImageDraw, ImageFont
from card_common import b64, font_face

# --- brand tokens (canonical: docs/research/07_DESIGN_TOKENS.md + AGIT marketing) ---
NAVY   = "#0c1c2d"   # AGIT dark navy (logo border / title)
ORANGE = "#da611c"   # AGIT orange (eyebrow, rule, divider)
GREY   = "#4f5b64"   # role text
GRAD   = ("#b5dae7", "#f9ebdf")   # panel gradient: powder-blue (top) -> cream (bottom)

EYEBROW = "ASIANS & GINGERS IN TECH"

# --- share-card geometry ---
CW, CH   = 1200, 630
PHOTO_W  = 748       # left photo panel width
PAD      = 48        # right-panel inner inset (equal left/right margins)
EB_FS    = 18        # eyebrow size (justified across the panel via letter-spacing)
NAME_MAX, NAME_MIN = 80, 44
ROLE_MAX, ROLE_MIN = 28, 20
LOGO_CARD = 92       # watermark size on the card

# --- hero geometry ---
HERO_W, HERO_H = 1080, 1350          # portrait 4:5
HERO_LOGO_FRAC = 0.20                 # watermark width as a fraction of the hero width
HERO_LOGO_MARGIN_FRAC = 0.035

REPO   = pathlib.Path(__file__).resolve().parents[2]
SDIR   = REPO / "scripts" / "social-cards"
FONTS  = SDIR / "fonts"
TSV    = SDIR / "agit-features.tsv"
SOURCES = SDIR / "agit-sources"
LOGO   = REPO / "assets" / "images" / "agit-logo.png"
OUTDIR = REPO / "content" / "community" / "agit-featured"

VT323  = FONTS / "VT323-Regular.ttf"
PLEX_R = FONTS / "IBMPlexMono-Regular.ttf"
PLEX_B = FONTS / "IBMPlexMono-Bold.ttf"


def _im_datauri(im, fmt="PNG"):
    buf = io.BytesIO(); im.save(buf, fmt, quality=90)
    mt = "png" if fmt == "PNG" else "jpeg"
    return f"data:image/{mt};base64," + base64.b64encode(buf.getvalue()).decode()

def _load_photo(path):
    """EXIF-transpose (honour orientation) then drop EXIF by re-decoding to RGB."""
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")

def _circle_logo(px):
    """AGIT logo cropped to a centred circle (drops the white square corners)."""
    im = Image.open(LOGO).convert("RGBA")
    s = min(im.size)
    im = im.crop(((im.width - s) // 2, (im.height - s) // 2,
                  (im.width - s) // 2 + s, (im.height - s) // 2 + s)).resize((px, px), Image.LANCZOS)
    mask = Image.new("L", (px, px), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, px - 1, px - 1), fill=255)
    out = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out

def _measure(s, ttf, fs):
    return ImageFont.truetype(str(ttf), fs).getbbox(s)[2]

def _advance(s, ttf, fs):
    return ImageFont.truetype(str(ttf), fs).getlength(s)

def _wrap(s, ttf, fs, maxw):
    lines, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if _measure(t, ttf, fs) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines

def _fit_lines(s, ttf, maxw, mx, mn, max_lines, floor=12, slack=8):
    """Largest size that wraps to <= max_lines lines, each within maxw.

    Search the preferred band [mn, mx] first; if nothing fits (a very long name or
    a long 2-line title), keep shrinking below mn down to `floor` so the text NEVER
    overflows the panel width and NEVER exceeds max_lines (which is what keeps the
    block clear of the bottom-right watermark). Only a pathological single unbreakable
    token wider than the panel at `floor` hits the last-resort return, which realistic
    names/roles never reach. `slack` reserves a few px against the small gap between
    Pillow's measured ink width and rsvg's rendered width at tiny sizes."""
    limit = maxw - slack
    for fs in range(mx, floor - 1, -1):
        lines = _wrap(s, ttf, fs, limit)
        if len(lines) <= max_lines and all(_measure(l, ttf, fs) <= limit for l in lines):
            return fs, lines
    return floor, _wrap(s, ttf, floor, limit)

def _eyebrow_spacing(s, fs, target_w):
    """letter-spacing that stretches the eyebrow to span target_w (rsvg honours
    letter-spacing; it ignores SVG textLength/lengthAdjust)."""
    return max(0.0, (target_w - _advance(s, PLEX_B, fs)) / max(len(s) - 1, 1))


def build_share_card(photo, name, role, out_png):
    tx = PHOTO_W + PAD
    inner = CW - PHOTO_W - 2 * PAD
    top = 52
    logo_px = LOGO_CARD
    logo_x = CW - 42 - logo_px
    logo_y = CH - 42 - logo_px
    body_bottom = logo_y - 18                    # keep text clear of the watermark

    eb_ls = _eyebrow_spacing(EYEBROW, EB_FS, inner)
    eb_y = top + EB_FS
    region_top = eb_y + 54

    name_fs, name_lines = _fit_lines(name, VT323, inner, NAME_MAX, NAME_MIN, 2)
    name_lh = name_fs + 2
    role = (role or "").strip()
    if role.lower() in ("(not given)", "not given"):   # the skill's missing-field sentinel
        role = ""
    have_role = bool(role)
    if have_role:
        role_fs, role_lines = _fit_lines(role, PLEX_R, inner, ROLE_MAX, ROLE_MIN, 2)
        role_lh = role_fs + 8
    else:
        role_fs, role_lines, role_lh = ROLE_MAX, [], ROLE_MAX + 8

    rule_gt, rule_h, rule_gb = 30, 6, 44
    stack = len(name_lines) * name_lh + rule_gt + rule_h + (rule_gb + len(role_lines) * role_lh if have_role else 0)
    start = region_top + max(0, ((body_bottom - region_top) - stack) / 2)

    y = start
    name_ts = ""
    for l in name_lines:
        y += name_lh
        name_ts += f'<text x="{tx}" y="{y:.0f}" class="name">{html.escape(l)}</text>'
    rule_y = y + rule_gt
    role_ts = ""
    if have_role:
        y = rule_y + rule_h + rule_gb
        for l in role_lines:
            y += role_lh - 8
            role_ts += f'<text x="{tx}" y="{y:.0f}" class="role">{html.escape(l)}</text>'
            y += 8

    logo_uri = _im_datauri(_circle_logo(logo_px))
    photo_uri = _im_datauri(photo, "JPEG")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{CW}" height="{CH}" viewBox="0 0 {CW} {CH}">
  <defs>
    <clipPath id="ph"><rect width="{PHOTO_W}" height="{CH}"/></clipPath>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{GRAD[0]}"/><stop offset="1" stop-color="{GRAD[1]}"/></linearGradient>
  </defs>
  <style>
    {font_face("VT323", VT323, 400)}{font_face("IBM Plex Mono", PLEX_R, 400)}{font_face("IBM Plex Mono", PLEX_B, 700)}
    .eyebrow{{fill:{ORANGE};font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:{EB_FS}px;letter-spacing:{eb_ls:.2f}px;}}
    .name{{fill:{NAVY};font-family:'VT323',monospace;font-size:{name_fs}px;}}
    .role{{fill:{GREY};font-family:'IBM Plex Mono',monospace;font-size:{role_fs}px;}}
  </style>
  <rect width="{CW}" height="{CH}" fill="url(#bg)"/>
  <image href="{photo_uri}" x="0" y="0" width="{PHOTO_W}" height="{CH}" preserveAspectRatio="xMidYMid slice" clip-path="url(#ph)"/>
  <rect x="{PHOTO_W}" y="0" width="6" height="{CH}" fill="{ORANGE}"/>
  <text x="{tx}" y="{eb_y}" class="eyebrow">{html.escape(EYEBROW)}</text>
  {name_ts}
  <rect x="{tx + 2}" y="{rule_y:.0f}" width="72" height="{rule_h}" fill="{ORANGE}"/>
  {role_ts}
  <image href="{logo_uri}" x="{logo_x}" y="{logo_y}" width="{logo_px}" height="{logo_px}"/>
</svg>'''
    svg_path = out_png.with_suffix(".svg")
    svg_path.write_text(svg)
    subprocess.run(["rsvg-convert", "-w", str(CW), "-h", str(CH), str(svg_path), "-o", str(out_png)], check=True)
    svg_path.unlink()


def build_hero(photo, out_jpg):
    im = ImageOps.fit(photo, (HERO_W, HERO_H), Image.LANCZOS, centering=(0.5, 0.4))
    lpx = max(150, int(HERO_W * HERO_LOGO_FRAC))
    m = int(HERO_W * HERO_LOGO_MARGIN_FRAC)
    base = im.convert("RGBA")
    base.alpha_composite(_circle_logo(lpx), (HERO_W - lpx - m, HERO_H - lpx - m))
    base.convert("RGB").save(out_jpg, "JPEG", quality=88)   # re-encode drops any EXIF


def find_source(slug):
    hits = sorted(SOURCES.glob(f"{slug}.*"))
    hits = [h for h in hits if h.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    if not hits:
        sys.exit(f"no source photo for '{slug}' in {SOURCES} (expected {slug}.<jpg|png|...>)")
    return hits[0]


def generate(slug, name, role):
    photo = _load_photo(find_source(slug))
    bundle = OUTDIR / slug
    if not bundle.is_dir():
        sys.exit(f"feature bundle not found: {bundle}")
    build_hero(photo, bundle / "hero.jpg")
    build_share_card(photo, name, role, bundle / "share-card.png")
    print(f"  {slug}: hero.jpg + share-card.png")


def rows():
    if not TSV.exists():
        sys.exit(f"missing {TSV}")
    for raw in TSV.read_text().splitlines():
        raw = raw.rstrip("\n")
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split("\t")
        slug = parts[0]
        name = parts[1] if len(parts) > 1 else slug
        role = parts[2] if len(parts) > 2 else ""
        yield slug, name, role


def main():
    for p in (TSV, LOGO, VT323, PLEX_R, PLEX_B):
        if not p.exists():
            sys.exit(f"missing required input: {p}")
    only = sys.argv[1] if len(sys.argv) > 1 else None
    n = 0
    for slug, name, role in rows():
        if only and slug != only:
            continue
        generate(slug, name, role)
        n += 1
    if only and n == 0:
        sys.exit(f"slug '{only}' not found in {TSV}")
    print(f"generated {n} AGIT feature image pair(s)")


if __name__ == "__main__":
    main()
