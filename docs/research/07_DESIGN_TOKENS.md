# Design Tokens

**Date**: 2026-04-07

## Decision

| Token | Value | Rationale |
|---|---|---|
| Accent colour | `#c0533a` (terracotta) | Warm, earthy, food/adventure friendly. WCAG AA on white (4.78:1) and on `#fafafa` (4.65:1). |
| Body text | `#1a1a1a` on `#fafafa` (light), `#e8e8e8` on `#141414` (dark) | AAA contrast in both modes |
| Body font | Inter (Google Fonts) | Humanist sans, warm, reads at small sizes, voice-fit (not academic) |
| Mono font | JetBrains Mono → SF Mono → Menlo system fallback | Tech posts |
| Max content width | 64rem (1024px) outer, 42rem (672px) prose | ~70ch line length on prose body |
| Sidebar width | 14rem | Constant size, never grows |
| Body size | 1rem / 1.6 line-height | Comfortable reading |
| Dark mode | `prefers-color-scheme` auto-switch | No JS toggle. System decides. |

## Single source of truth

`config/_default/params.toml > accentColor` is the canonical accent colour. Read by `assets/css/main.css` via Hugo template processing (`resources.ExecuteAsTemplate`). Changing the hex in `params.toml` automatically updates the rendered CSS.

## Notes

- Greyscale base for body text and chrome. Accent applied ONLY to links and active-nav indicator. No other colour anywhere.
- Inter loaded from Google Fonts (`?family=Inter:wght@400;600;700`). System fonts as fallback so first paint never blocks on font load.
- No custom dark-mode toggle in Phase 0. System preference rules. Revisit in a later phase if user demand exists.
- Accent contrast checked manually via WebAIM Contrast Checker. Re-check if accent is changed.

---

## Inline SVG Illustration Tokens (brand template)

Hand-drawn schematic SVGs (data-flow diagrams, pipelines, layer diagrams) are the house style for blog and consulting illustrations: code-drawn, not AI-generated (an AI image is "mood not meaning" for a schematic). This section is the **single source of truth** for their colours so every diagram looks like part of the same family. In use: `posts/3-types-of-tests-for-production-systems/pipeline.svg`, `posts/observability-and-logging-for-production-systems/observability.svg`, `consulting/claude-code-harness-architect/harness-layers.svg`.

### Palette

| Role | Class | Light | Dark | Notes |
|---|---|---|---|---|
| Accent (terracotta) | `.accent` / `.accentstroke` | `#c0533a` | `#c0533a` | same in both modes; the ONLY warm colour. Endpoints, arrows, failure/verdict emphasis |
| Background | `.bg` | `#fafafa` | `#141414` | the SVG paints its OWN background rect so text contrast holds on any host page |
| Card / box fill | `.card` | `#ffffff` | `#1f1f1f` | boxes sit on the bg |
| Label text | `.label` | `#1a1a1a` | `#f0f0f0` | primary box/diagram text, `font-weight:600` |
| Muted text | `.muted` | `#6a6a6a` | `#a6a6a6` | captions, secondary labels, neutral lines |
| Box / trail stroke | `.boxstroke` / `.trailstroke` | `#9aa0a6` | `#6a6a6a` | neutral borders + connector/trail lines |
| OK / positive green | `.ok` | `#7aa869` | `#7aa869` | "logged / healthy / passing / automation" markers; same in both modes |
| Brand watermark (sky blue) | `.watermark` | `#87ceeb` | `#87ceeb` | the `hoiboy.uk` signature, top-right corner; the logo's blue; same in both modes |

Fonts: `font-family="Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"` on the root `<svg>` (matches the site body font). Boxes use `rx="10"` rounded corners; accent arrowheads via a shared `<marker>`.

### Canonical class block (copy-paste into a new diagram's `<defs>`)

```xml
<style>
  .bg { fill: #fafafa; }
  .card { fill: #ffffff; }
  .label { fill: #1a1a1a; font-weight: 600; }
  .muted { fill: #6a6a6a; }
  .boxstroke { stroke: #9aa0a6; }
  .trailstroke { stroke: #9aa0a6; }
  .accent { fill: #c0533a; }
  .accentstroke { stroke: #c0533a; }
  .ok { fill: #7aa869; }
  .watermark { fill: #87ceeb; }
  @media (prefers-color-scheme: dark) {
    .bg { fill: #141414; }
    .card { fill: #1f1f1f; }
    .label { fill: #f0f0f0; }
    .muted { fill: #a6a6a6; }
    .boxstroke { stroke: #6a6a6a; }
    .trailstroke { stroke: #6a6a6a; }
  }
</style>
```

Rules:
- **Declare root `width` AND `height` on the `<svg>` (match the viewBox), e.g. `viewBox="0 0 880 360" width="880" height="360"`.** Not optional. Without intrinsic dimensions, the `zoom-image` lightbox (glightbox) has no natural size to scale from and renders the SVG TINY when clicked (caught 2026-06-04 on pipeline.svg / observability.svg / fix-test-observe-loop.svg; harness-layers.svg always worked because it carried width/height). Inline display stays responsive via CSS (`.zoom-image img { width:100% }`); the attributes only fix the lightbox. Enforced by `scripts/check_svg_dimensions.py` (wired into `pre-publish.sh`).
- Always paint an explicit `.bg` rect covering the whole viewBox (never rely on the page background; a transparent SVG shows dark text on a dark host and vice-versa).
- Card fills carry the readable text. The dark-mode card (`#1f1f1f`) keeps `.label` text legible; do NOT leave cards white in dark mode (white card + dark host chrome around it looks broken, and was the readability complaint on the first pass of observability.svg).
- Use `.ok` green ONLY for positive/healthy/logged/automation; use `.accent` for endpoints, the active data path, and failure/verdict emphasis. No other colours.
- Embed via the `zoom-image` shortcode, never a bare markdown image: `{{</* zoom-image src="diagram.svg" alt="..." title="..." */>}}`. The shortcode trips the `.HasShortcode` guard in `single.html` so the theme does NOT also dump the SVG into the auto-gallery (double-render bug).

### Brand watermark (every illustration)

Every illustration carries a subtle `hoiboy.uk` signature in the **top-right corner**, in the logo's sky blue (`#87ceeb`). It is identical on every diagram so the brand mark reads consistently across the site. `#87ceeb` is the same in both colour schemes (no dark-mode override needed).

- Element (dual-mode SVG with a `<style>` block): `<text x="..." y="..." text-anchor="end" class="watermark" font-size="..." font-weight="400" letter-spacing="...">hoiboy.uk</text>`, placed right after the background `<rect>` so it sits under nothing. For a fixed-dark SVG with no `<style>` (e.g. `harness-layers.svg`), use inline `fill="#87ceeb"` instead of the class.
- **Scale it to the viewBox width** so it appears the same size on every illustration (these SVGs display responsively, so a fixed `font-size` would look bigger on a narrow viewBox and smaller on a wide one). Reference: a **900-unit-wide** viewBox uses `font-size="11"`, baseline `y="24"`, `x = W − 15` (anchored `end`), `letter-spacing="0.5"`. For a diagram of width `W`, multiply each by `W / 900`:
  - `font-size = 11 × W/900`  ·  `x = W − 15×W/900`  ·  `y = 24 × W/900`  ·  `letter-spacing = 0.5 × W/900`
  - Worked: W=880 → size 10.8, x 865, y 23.5 · W=620 → size 7.6, x 610, y 16.5 · W=1600 → size 19.6, x 1573, y 43
- This yields an equal (reference ~16px) inset from the top and right edges. Always render the diagram and eyeball the corner so the watermark does not overlap a title, label, or any content.

### Exporting to PNG (social cards, fixed-dark diagrams)

The `prefers-color-scheme` media query does **not** apply when a rasteriser flattens an SVG to PNG: there is no "system" to query, so it renders the **default (light) branch** and any media-query overrides are dropped. So an exported PNG is ALWAYS a single fixed appearance. Pick the mode deliberately and bake an **opaque** background (never a transparent PNG: transparent + a dark client = invisible text).

- **Light export (default, for hoiboy.uk `og:image` social cards and light contexts):** render the light branch on an opaque `#fafafa` canvas. Text `#1a1a1a`, cards `#ffffff`, accent `#c0533a`, green `#7aa869`. The `.bg` rect already supplies `#fafafa`, so a normal rasterise of the inline SVG gives the correct light card.
- **Fixed-dark export (standalone dark diagrams, e.g. `harness-layers.svg`):** these are authored WITHOUT the media query, with a baked `#1a1a1a` background and `#e8e8e8` text (the dark-token text colour). Use this only when the diagram is meant to be dark everywhere (a poster/standalone asset), not an inline dual-mode illustration.

Rasterise command (resvg / rsvg-convert / Inkscape all honour an explicit background):

```bash
# Light social card (1200x630) on opaque #fafafa
rsvg-convert -w 1200 -h 630 --background-color '#fafafa' diagram.svg -o diagram-card.png
# (resvg)  resvg --background '#fafafa' --width 1200 diagram.svg diagram-card.png
```

Rule of thumb: **inline SVG = dual-mode (media query); exported PNG = one mode + an opaque baked background.** For hoiboy.uk, default to the LIGHT export for any shared/social PNG.

## AGIT feature-image tokens (photo cards)

The Asians & Gingers in Tech community features (`content/community/agit-featured/<slug>/`) use a **photo-driven** card system, distinct from the schematic diagram tokens above. Each feature is generated as a branded pair by `scripts/social-cards/gen_agit_feature.py`, which is the deterministic source of truth (re-running it reproduces the exact approved look for any person). This section is the human-readable design record so a future feature, or a design tweak, does not have to be reverse-engineered from the Python constants. Approved reference example: `content/community/agit-featured/hoi-aka-hoiboy-ai-product-engineer/` (the committed `hero.jpg` + `share-card.png` are the frozen "this is how it should look" artifacts).

### Palette

| Role | Hex | Notes |
|---|---|---|
| Navy (name / logo border) | `#0c1c2d` | the card title colour |
| Orange (eyebrow, rule, divider) | `#da611c` | the single accent: eyebrow text, the short rule under the name, the vertical photo/panel divider |
| Grey (role text) | `#4f5b64` | the role line under the rule |
| Panel gradient | `#b5dae7` to `#f9ebdf` | vertical powder-blue (top) to cream (bottom), sampled from the AGIT banner art |

### Type

- **Name:** VT323 (pixel/retro), up to **80px**, auto-shrinks to fit the panel (floor 12px) and wraps to at most 2 lines. Same face as the consulting card titles.
- **Role:** IBM Plex Mono, up to **28px**, same auto-fit behaviour.
- **Eyebrow** (`ASIANS & GINGERS IN TECH`): IBM Plex Mono Bold, **18px**, letter-spacing stretched to span the panel width.

Both faces are vendored under `scripts/social-cards/fonts/` (OFL) and embedded as base64 `@font-face` so `rsvg-convert` renders them identically anywhere.

### Geometry

| Image | Size | Purpose |
|---|---|---|
| `hero.jpg` | **1080x1350** (portrait 4:5) | on-page hero + index card + the person's direct-to-social image |
| `share-card.png` | **1200x630** (landscape 1.91:1) | OG / Twitter link-preview (photo inset left, gradient panel right) |

Share-card layout: photo panel `748px` wide on the left, `48px` inner inset on the right panel (equal margins), 6px orange divider between them.

### Logo watermark (circular)

The AGIT logo (`assets/images/agit-logo.png`, a downscaled EXIF-clean copy of the Drive master) is masked to a **circle** at render time (drops the white square corners) and placed **bottom-right** on **both** images. Sizes intentionally differ per surface:

| Surface | Logo size | On a 1200-wide canvas |
|---|---|---|
| Consulting card (`gen_card.py`) | `64px` | approx 5.3% width (text-only card, smaller signature) |
| AGIT share-card (`gen_agit_feature.py`) | `92px` | approx 7.7% width (photo card, stronger group brand promo) |
| AGIT hero (`gen_agit_feature.py`) | `20%` of width (approx 216px) + 3.5% margin | portrait, larger so it reads at social thumbnail size |

To change any of these, edit the generator constants (`NAVY`/`ORANGE`/`GREY`/`GRAD`, `NAME_MAX`/`ROLE_MAX`/`EB_FS`, `LOGO_CARD`/`HERO_LOGO_FRAC`, `CW`/`CH`/`HERO_W`/`HERO_H`) and re-run `python3 scripts/social-cards/gen_agit_feature.py` (no slug) to regenerate every feature's pair, then rebuild the site. Do not redesign without operator sign-off.
