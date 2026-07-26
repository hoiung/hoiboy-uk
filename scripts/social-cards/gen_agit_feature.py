#!/usr/bin/env python3
"""Generate the branded image pair for AGIT community features (Issue #47).

Each feature gets two images, dropped into its page bundle under
content/community/agit-featured/<slug>/:

  1. hero.jpg       portrait 4:5 (1080x1350) display photo + AGIT logo watermark,
                    EXIF-stripped. This is the on-page hero, the index-card image,
                    and what the featured person posts straight to socials.
  2. share-card.png branded landscape 1200x630 link-preview card: the submitted
                    photo inset on the left, a blue->cream gradient panel on the
                    right with the page's trail eyebrow + the person's name + role,
                    and the AGIT logo watermark bottom-right. head.html prefers
                    share-card.* over the hero for og:image, so a portrait submission
                    no longer gets its head/legs sliced off in the link preview.

The EYEBROW is the page's parent trail, uppercased and joined with " > ", read from
the per-page trail.json sidecar Hugo emits (blog-priv#62) - the same rule that renders
the on-page breadcrumb, so the two cannot drift. It replaced a pair of hardcoded brand
strings. The site must therefore be BUILT before this script runs; use
scripts/gen-social-cards.sh, which pins that order.

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

There is also a brand-only SECTION card for the /community/agit-featured/ index
(no person photo): the AGIT logo + the section's own trail eyebrow/headline/tagline
on the same blue->cream gradient, written to content/community/agit-featured/share-card.png
so head.html can resolve it as the section og:image. See build_section_card().

Usage:
  python3 scripts/social-cards/gen_agit_feature.py            # regenerate every feature + the section card
  python3 scripts/social-cards/gen_agit_feature.py <slug>     # regenerate one feature
  python3 scripts/social-cards/gen_agit_feature.py --section  # regenerate just the section index card
Deps: rsvg-convert (librsvg), Pillow.
"""
import subprocess, sys, os, html, base64, io, pathlib, re
from PIL import Image, ImageOps, ImageDraw, ImageFont
from card_common import TrailIndex, font_face, load_trails, bundle_key, eyebrow_for

# --- brand tokens (canonical: docs/research/07_DESIGN_TOKENS.md + AGIT marketing) ---
NAVY   = "#0c1c2d"   # AGIT dark navy (logo border / title)
ORANGE = "#da611c"   # AGIT orange (eyebrow, rule, divider)
GREY   = "#4f5b64"   # role text
NUMGREY = "#98a2ab"  # light grey for the small feature-number kicker (#N above the name)
GRAD   = ("#b5dae7", "#f9ebdf")   # panel gradient: powder-blue (top) -> cream (bottom)

# --- share-card geometry ---
CW, CH   = 1200, 630
PHOTO_W  = 748       # left photo panel width
PAD      = 48        # right-panel inner inset (equal left/right margins)
EB_FS    = 18        # eyebrow size CEILING (justified across the panel via letter-spacing)
EB_LINES = 2         # a deep trail wraps rather than shrinking to an illegible size
EB_FLOOR = 12        # smallest eyebrow size _fit_lines may drop to
NAME_MAX = 80        # name font ceiling (shrinks to fit; floor is _fit_lines' default 12)
NAME_FLOOR = 48      # smallest name size _fit_stack may drop to before failing loud
ROLE_MAX = 28        # role font ceiling
ROLE_FLOOR = 18      # smallest role size _fit_stack may drop to before failing loud
BODY_CLEAR = 18      # the name/role block keeps this much clear of the watermark, both
                     # above (below the eyebrow) and below (above the logo). blog-priv#62
                     # made the eyebrow a wrapping parent trail instead of a fixed
                     # one-line brand string, which pushes the block down, so this is
                     # now enforced by _fit_stack rather than assumed.
LOGO_CARD = 92       # watermark size on the card

# --- hero geometry ---
HERO_W, HERO_H = 1080, 1350          # portrait 4:5
HERO_LOGO_FRAC = 0.20                 # watermark width as a fraction of the hero width
HERO_LOGO_MARGIN_FRAC = 0.035

# --- section (brand-only) card: the /community/agit-featured/ index og:image ---
# No person photo. The eyebrow is the page's parent trail like every other card's
# (blog-priv#62); the headline and tagline present the SECTION, and the AGIT logo
# already carries the group wordmark, so neither repeats it.
SEC_HEADLINE = "Featured"
SEC_TAGLINE  = "The quiet, heads-down people doing brilliant work in tech, and the stories behind them."
SEC_LOGO     = 430       # big logo on the left (prominent, not a watermark)
SEC_LOGO_X   = 76
SEC_TX       = 596       # text-column left edge
SEC_PAD_R    = 64        # text-column right margin
SEC_EB_FS    = 18        # eyebrow size (justified across the text column)
SEC_HEAD_MAX = 120       # headline font ceiling (VT323)
SEC_TAG_MAX  = 26        # tagline font ceiling (IBM Plex Mono)

REPO   = pathlib.Path(__file__).resolve().parents[2]
CONTENT = REPO / "content"
# Where Hugo wrote the per-page trail.json sidecars that supply the eyebrow.
# Overridable so the tests can point at a sandbox build instead of the working tree's.
PUBLIC = pathlib.Path(os.environ.get("HOIBOY_PUBLIC_DIR") or (REPO / "public"))
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
    """Rendered line width: max of the advance (getlength) and the ink extent (getbbox).
    Neither alone is a safe upper bound for rsvg's render — Plex's advance exceeds its
    ink, while VT323's pixel glyphs overhang their advance box — so take the larger."""
    f = ImageFont.truetype(str(ttf), fs)
    return max(f.getlength(s), f.getbbox(s)[2])

def _hard_break(word, ttf, fs, maxw):
    """Split a single word too wide for maxw into character chunks that each fit,
    so a line can never overflow the panel width (unbreakable/hyphen-joined tokens)."""
    if _measure(word, ttf, fs) <= maxw:
        return [word]
    chunks, cur = [], ""
    for ch in word:
        if not cur or _measure(cur + ch, ttf, fs) <= maxw:
            cur += ch
        else:
            chunks.append(cur); cur = ch
    if cur:
        chunks.append(cur)
    return chunks

def _wrap(s, ttf, fs, maxw):
    words = []
    for w in s.split():
        words.extend(_hard_break(w, ttf, fs, maxw))
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if _measure(t, ttf, fs) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines

def _limit(maxw, fs):
    """Usable line width at font size `fs`. rsvg renders VT323/Plex a few px wider than
    Pillow measures, and the gap grows with size, so reserve a size-proportional margin
    (empirically ~0.4*fs covers VT323's worst overhang) so a fitted line never overflows."""
    return maxw - max(6, int(round(fs * 0.4)))

def _fit_lines(s, ttf, maxw, mx, max_lines, floor=12):
    """Largest size in [floor, mx] whose wrap is <= max_lines lines, each within the
    size-adjusted panel width. Because `_wrap` hard-breaks over-long tokens, each line
    always fits the width; the size search caps the line count, which keeps the block
    clear of the bottom-right watermark. If even `floor` needs more than max_lines lines
    (absurdly long text), keep the first max_lines and end with an ellipsis. Realistic
    names/roles never reach the truncation branch."""
    for fs in range(mx, floor - 1, -1):
        lines = _wrap(s, ttf, fs, _limit(maxw, fs))
        if len(lines) <= max_lines:
            return fs, lines
    fl = _limit(maxw, floor)
    lines = _wrap(s, ttf, floor, fl)[:max_lines]
    last = lines[-1]
    while last and _measure(last + "...", ttf, floor) > fl:
        last = last[:-1]
    lines[-1] = last.rstrip() + "..."
    return floor, lines

def _eyebrow_spacing(s, fs, target_w):
    """letter-spacing that stretches the eyebrow to span target_w (rsvg honours
    letter-spacing; it ignores SVG textLength/lengthAdjust)."""
    return max(0.0, (target_w - _measure(s, PLEX_B, fs)) / max(len(s) - 1, 1))


def _fit_eyebrow(eyebrow, maxw, max_fs):
    """(font-size, letter-spacing, lines) for a trail eyebrow in a `maxw`-wide column.

    The trail can be deep - JOIN COMMUNITY > ASIANS & GINGERS IN TECH > AGIT FEATURED is
    57 characters against the feature card's 356px panel - so it WRAPS to EB_LINES rather
    than shrinking to fit one line, which at that width would land near 10px and be
    unreadable. Tracking is derived from the widest line so every line shares one value;
    with a single line that is exactly the previous justify-across-the-panel behaviour.

    An empty eyebrow (a page with no parent trail) returns no lines, and the caller emits
    no eyebrow text node."""
    if not eyebrow:
        return max_fs, 0.0, []
    fs, lines = _fit_lines(eyebrow, PLEX_B, maxw, max_fs, EB_LINES, floor=EB_FLOOR)
    widest = max(lines, key=lambda l: _measure(l, PLEX_B, fs))
    return fs, _eyebrow_spacing(widest, fs, maxw), lines


def _eyebrow_tspans(lines, tx, first_y, line_h):
    """Eyebrow text nodes, one per wrapped line, and the LAST baseline used (so the
    caller can stack the block below it)."""
    out, y = "", first_y
    for i, line in enumerate(lines):
        y = first_y + i * line_h
        out += f'<text x="{tx}" y="{y:.0f}" class="eyebrow">{html.escape(line)}</text>'
    return out, y


RULE_GT, RULE_H, RULE_GB = 30, 6, 44   # gap above the rule, its height, gap below it
RULE_GB_FLOOR = 28                     # the rule-to-role gap gives way before any type does


def _stack_height(name_fs, name_lines, role_fs, role_lines, have_role, have_num,
                  rule_gb=RULE_GB):
    """Total height of the #N / name / rule / role block.

    Defined ONCE and used by both the fitter and the emitter below, so the measured
    height and the drawn height cannot drift apart."""
    num_fs = round(name_fs * 2 / 3) if have_num else 0
    num_gap = 10 if have_num else 0
    return ((num_fs + num_gap)
            + len(name_lines) * (name_fs + 2)
            + RULE_GT + RULE_H
            + (rule_gb + len(role_lines) * (role_fs + 8) if have_role else 0))


def _fit_stack(name, role, inner, avail, have_role, have_num):
    """Largest (name_fs, name_lines, role_fs, role_lines, rule_gb) whose assembled block
    fits `avail` px of vertical room between the eyebrow and the watermark.

    Elasticity order, most elastic first: the rule-to-role GAP gives way before any type
    does, then the role, then the name. Whitespace is the cheapest thing to spend, and
    the name is the dominant element by design (see _feature_number), so it gives last.

    Why this exists: `_fit_lines` caps the LINE COUNT of one text run, which bounds that
    run's width but says nothing about the height of the assembled block. Before
    blog-priv#62 the eyebrow was a fixed one-line brand string, so `region_top` was a
    constant 88 and the block always fitted; the eyebrow then became the page's own
    parent trail, which wraps to EB_LINES and pushes `region_top` down by ~24px. The old
    code centred with `max(0, (avail - stack) / 2)`, so an over-tall block silently
    started at `region_top` and ran PAST the logo with no error. Measured on the one real
    feature: stack 379 against 366 available, 13px into the watermark's clearance. That
    13px now comes out of the 44px gap instead of the type. This fails loud instead."""
    for name_mx in range(NAME_MAX, NAME_FLOOR - 1, -1):
        name_fs, name_lines = _fit_lines(name, VT323, inner, name_mx, 2)
        for role_mx in range(ROLE_MAX, ROLE_FLOOR - 1, -1):
            if have_role:
                role_fs, role_lines = _fit_lines(role, PLEX_R, inner, role_mx, 2)
            else:
                role_fs, role_lines = role_mx, []
            for rule_gb in range(RULE_GB, RULE_GB_FLOOR - 1, -1):
                if _stack_height(name_fs, name_lines, role_fs, role_lines,
                                 have_role, have_num, rule_gb) <= avail:
                    return name_fs, name_lines, role_fs, role_lines, rule_gb
                if not have_role:
                    break    # no role block, so the gap below the rule is not drawn
            if not have_role:
                break        # no role to shrink; only the name can give
    sys.exit(f"share-card body does not fit above the watermark: name={name!r} "
             f"role={role!r} still needs more than {avail}px at name={NAME_FLOOR}px / "
             f"role={ROLE_FLOOR}px / gap={RULE_GB_FLOOR}px. Shorten the name or the role.")


def build_share_card(photo, name, role, out_png, eyebrow, number=None):
    tx = PHOTO_W + PAD
    inner = CW - PHOTO_W - 2 * PAD
    top = 52
    logo_px = LOGO_CARD
    logo_x = CW - 42 - logo_px
    logo_y = CH - 42 - logo_px
    body_bottom = logo_y - BODY_CLEAR             # keep text clear of the watermark

    eb_fs, eb_ls, eb_lines = _fit_eyebrow(eyebrow, inner, EB_FS)
    eb_y = top + eb_fs
    eb_ts, eb_last_y = _eyebrow_tspans(eb_lines, tx, eb_y, eb_fs + 6)
    if not eb_lines:
        eb_last_y = eb_y
    region_top = eb_last_y + BODY_CLEAR   # symmetric with body_bottom so the block centres between the eyebrow bottom and the logo top

    num = str(number).strip() if number not in (None, "") else ""
    role = (role or "").strip()
    if role.lower() in ("(not given)", "not given"):   # the skill's missing-field sentinel
        role = ""
    have_role = bool(role)

    name_fs, name_lines, role_fs, role_lines, rule_gb = _fit_stack(
        name, role, inner, body_bottom - region_top, have_role, bool(num))
    name_lh = name_fs + 2
    role_lh = role_fs + 8
    num_fs = round(name_fs * 2 / 3) if num else 0     # kicker is 2/3 of the fitted name size
    num_gap = 10 if num else 0                          # gap between the #N kicker and the name

    rule_gt, rule_h = RULE_GT, RULE_H
    stack = _stack_height(name_fs, name_lines, role_fs, role_lines, have_role, bool(num),
                          rule_gb)
    start = region_top + ((body_bottom - region_top) - stack) / 2
    assert start + stack <= body_bottom, (            # _fit_stack's postcondition
        f"share-card body overflows the watermark clearance: end={start + stack:.0f} "
        f"> body_bottom={body_bottom}")

    y = start
    num_ts = ""
    if num:
        y += num_fs
        num_ts = f'<text x="{tx}" y="{y:.0f}" class="fnum">#{html.escape(num)}</text>'
        y += num_gap
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
    .eyebrow{{fill:{ORANGE};font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:{eb_fs}px;letter-spacing:{eb_ls:.2f}px;}}
    .name{{fill:{NAVY};font-family:'VT323',monospace;font-size:{name_fs}px;}}
    .fnum{{fill:{NUMGREY};font-family:'VT323',monospace;font-size:{num_fs}px;}}
    .role{{fill:{GREY};font-family:'IBM Plex Mono',monospace;font-size:{role_fs}px;}}
  </style>
  <rect width="{CW}" height="{CH}" fill="url(#bg)"/>
  <image href="{photo_uri}" x="0" y="0" width="{PHOTO_W}" height="{CH}" preserveAspectRatio="xMidYMid slice" clip-path="url(#ph)"/>
  <rect x="{PHOTO_W}" y="0" width="6" height="{CH}" fill="{ORANGE}"/>
  {eb_ts}
  {num_ts}
  {name_ts}
  <rect x="{tx + 2}" y="{rule_y:.0f}" width="72" height="{rule_h}" fill="{ORANGE}"/>
  {role_ts}
  <image href="{logo_uri}" x="{logo_x}" y="{logo_y}" width="{logo_px}" height="{logo_px}"/>
</svg>'''
    svg_path = out_png.with_suffix(".svg")
    try:
        svg_path.write_text(svg)
        subprocess.run(["rsvg-convert", "-w", str(CW), "-h", str(CH), str(svg_path), "-o", str(out_png)], check=True)
    finally:
        # Never strand the intermediate .svg inside the tracked content bundle if
        # rsvg-convert is missing or fails (it would otherwise get swept into a
        # later git add or picked up as a Hugo page resource).
        svg_path.unlink(missing_ok=True)


def build_hero(photo, out_jpg):
    im = ImageOps.fit(photo, (HERO_W, HERO_H), Image.LANCZOS, centering=(0.5, 0.4))
    lpx = max(150, int(HERO_W * HERO_LOGO_FRAC))
    m = int(HERO_W * HERO_LOGO_MARGIN_FRAC)
    base = im.convert("RGBA")
    base.alpha_composite(_circle_logo(lpx), (HERO_W - lpx - m, HERO_H - lpx - m))
    base.convert("RGB").save(out_jpg, "JPEG", quality=88)   # re-encode drops any EXIF


def build_section_card(out_png, eyebrow, headline=SEC_HEADLINE, tagline=SEC_TAGLINE):
    """Brand-only landscape 1200x630 card for the agit-featured SECTION index (no
    person photo): full blue->cream gradient, the circular AGIT logo prominent on
    the left, and the section eyebrow + headline + tagline on the right, in the same
    AGIT brand system as the feature cards. head.html resolves it as the og:image
    for /community/agit-featured/. Same brand tokens/fonts/logo/rsvg pipeline as
    build_share_card, minus the photo panel."""
    logo_px = SEC_LOGO
    logo_x  = SEC_LOGO_X
    logo_y  = (CH - logo_px) // 2
    tx      = SEC_TX
    col_w   = CW - tx - SEC_PAD_R
    div_x   = logo_x + logo_px + 30
    div_top, div_bot = logo_y + 8, logo_y + logo_px - 8

    eb_fs, eb_ls, eb_lines = _fit_eyebrow(eyebrow, col_w, SEC_EB_FS)
    eb_lh = eb_fs + 6
    head_fs, head_lines = _fit_lines(headline, VT323, col_w, SEC_HEAD_MAX, 2)
    head_lh = head_fs + 2
    tag_fs, tag_lines = _fit_lines(tagline, PLEX_R, col_w, SEC_TAG_MAX, 4)
    tag_lh = tag_fs + 8

    eb_gap, rule_gt, rule_h, rule_gb = 34, 28, 6, 34
    # An empty eyebrow contributes no height and no gap, so the rest of the block stays
    # vertically centred instead of sitting low against a reserved-but-unused band.
    eb_block = (eb_fs + (len(eb_lines) - 1) * eb_lh + eb_gap) if eb_lines else 0
    stack = (eb_block + len(head_lines) * head_lh
             + rule_gt + rule_h + rule_gb + len(tag_lines) * tag_lh)
    y = (CH - stack) / 2

    eb_ts = ""
    if eb_lines:
        y += eb_fs
        eb_ts, y = _eyebrow_tspans(eb_lines, tx, y, eb_lh)
        y += eb_gap
    head_ts = ""
    for l in head_lines:
        y += head_lh
        head_ts += f'<text x="{tx}" y="{y:.0f}" class="head">{html.escape(l)}</text>'
    rule_y = y + rule_gt
    y = rule_y + rule_h + rule_gb
    tag_ts = ""
    for l in tag_lines:
        y += tag_lh - 8
        tag_ts += f'<text x="{tx}" y="{y:.0f}" class="tag">{html.escape(l)}</text>'
        y += 8

    logo_uri = _im_datauri(_circle_logo(logo_px))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{CW}" height="{CH}" viewBox="0 0 {CW} {CH}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{GRAD[0]}"/><stop offset="1" stop-color="{GRAD[1]}"/></linearGradient>
  </defs>
  <style>
    {font_face("VT323", VT323, 400)}{font_face("IBM Plex Mono", PLEX_R, 400)}{font_face("IBM Plex Mono", PLEX_B, 700)}
    .eyebrow{{fill:{ORANGE};font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:{eb_fs}px;letter-spacing:{eb_ls:.2f}px;}}
    .head{{fill:{NAVY};font-family:'VT323',monospace;font-size:{head_fs}px;}}
    .tag{{fill:{GREY};font-family:'IBM Plex Mono',monospace;font-size:{tag_fs}px;}}
  </style>
  <rect width="{CW}" height="{CH}" fill="url(#bg)"/>
  <image href="{logo_uri}" x="{logo_x}" y="{logo_y}" width="{logo_px}" height="{logo_px}"/>
  <rect x="{div_x}" y="{div_top:.0f}" width="4" height="{div_bot - div_top:.0f}" fill="{ORANGE}"/>
  {eb_ts}
  {head_ts}
  <rect x="{tx + 2}" y="{rule_y:.0f}" width="72" height="{rule_h}" fill="{ORANGE}"/>
  {tag_ts}
</svg>'''
    svg_path = out_png.with_suffix(".svg")
    try:
        svg_path.write_text(svg)
        subprocess.run(["rsvg-convert", "-w", str(CW), "-h", str(CH), str(svg_path), "-o", str(out_png)], check=True)
    finally:
        # Never strand the intermediate .svg inside the tracked content bundle.
        svg_path.unlink(missing_ok=True)


def find_source(slug):
    hits = sorted(SOURCES.glob(f"{slug}.*"))
    hits = [h for h in hits if h.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    if not hits:
        sys.exit(f"no source photo for '{slug}' in {SOURCES} (expected {slug}.<jpg|png|...>)")
    return hits[0]


def _feature_number(slug):
    """The feature number parsed from the slug prefix (`1-jane-smith-...` -> "1"),
    or None for an un-numbered slug. Rendered as a small light-grey `#N` kicker
    above the name on the share card, so the card mirrors the page title `#N <Name>`
    while keeping the name the dominant element."""
    m = re.match(r"(\d+)-", slug)
    return m.group(1) if m else None


def generate(slug: str, name: str, role: str, trails: TrailIndex | None) -> None:
    photo = _load_photo(find_source(slug))
    bundle = OUTDIR / slug
    if not bundle.is_dir():
        sys.exit(f"feature bundle not found: {bundle}")
    eyebrow = eyebrow_for(trails, bundle_key(bundle, CONTENT))
    build_hero(photo, bundle / "hero.jpg")
    build_share_card(photo, name, role, bundle / "share-card.png", eyebrow,
                     number=_feature_number(slug))
    print(f"  {slug} eyebrow={eyebrow or '(none)'}: hero.jpg + share-card.png")


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
    for p in (LOGO, VT323, PLEX_R, PLEX_B):   # TSV not needed for --section
        if not p.exists():
            sys.exit(f"missing required input: {p}")
    only = sys.argv[1] if len(sys.argv) > 1 else None
    trails = load_trails(PUBLIC)
    section_eyebrow = eyebrow_for(trails, bundle_key(OUTDIR, CONTENT))
    if only == "--section":                   # regenerate just the section index card
        build_section_card(OUTDIR / "share-card.png", section_eyebrow)
        print(f"  section eyebrow={section_eyebrow or '(none)'}: share-card.png")
        return
    if not TSV.exists():
        sys.exit(f"missing {TSV}")
    n = 0
    for slug, name, role in rows():
        if only and slug != only:
            continue
        generate(slug, name, role, trails)
        n += 1
    if only and n == 0:
        sys.exit(f"slug '{only}' not found in {TSV}")
    if only is None:                          # full regen also refreshes the section card
        build_section_card(OUTDIR / "share-card.png", section_eyebrow)
        print(f"  section eyebrow={section_eyebrow or '(none)'}: share-card.png")
    print(f"generated {n} AGIT feature image pair(s)")


if __name__ == "__main__":
    main()
