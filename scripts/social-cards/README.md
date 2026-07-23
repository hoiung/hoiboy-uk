# Text social-share cards (consulting + legal + site default)

Per-page 1200×630 Open Graph / Twitter share cards for the consulting pages,
client case-study (portfolio) pages, and the **legal** pages, plus the site-wide
branded default card — so each page gets a distinct, correctly-sized social card
instead of falling back to a personal face photo.

## How it works

`gen_card.py` renders three card sets, all from one template:

- **consulting** — each row of `cards.tsv` (`slug <TAB> title <TAB> tagline
  [<TAB> style]`) to `content/hire-hoi/ai-consultancy/<slug>/share-card.png`.
- **legal** — each row of `legal-cards.tsv` to `content/legal/<slug>/share-card.png`.
  `privacy` + `sub-processors` use the `hoiboy` style; `agit-story-guidelines`
  uses the `agit` style (navy `#0c1c2d` / orange `#da611c`, "ASIANS & GINGERS IN
  TECH" eyebrow).
- **default** — `content/default-card.png`, the site-wide `og:image` fallback for
  the home page + taxonomy/section index pages (replaced the old `hoi-mug.jpg`).

Run `python3 scripts/social-cards/gen_card.py [consulting] [legal] [default]`
(no args = all three). `layouts/_partials/head.html` picks up a page's own
`share-card.*` as its `og:image` (resized to 1200 wide, aspect preserved), and
`default-card.png` as the fallback.

**Guard:** `scripts/check_social_cards.py` (pre-commit + pre-publish + CI, with a
rendered-HTML backstop) fails the build if a singular indexable page is a flat
`.md`/`.markdown`/`.html` (cannot hold a card) or would fall back to the default
card — so a page can never silently ship the generic default.

The `slug` is the page bundle path under `content/hire-hoi/ai-consultancy/`, so **nested
slugs work as-is** — a client case study at
`content/hire-hoi/ai-consultancy/portfolio/cu-architects/` is just the row
`portfolio/cu-architects <TAB> CU Architects <TAB> <tagline>`. Client
case-study cards use the **same template** (HOIBOY AI LTD eyebrow, page title,
tagline, `hoiboy.uk` signature) — no client logo, for visual consistency with
the service cards. To add a card for a new portfolio/client page, add one row
and re-run; nothing else changes.

Brand colours are the canonical ones from `docs/research/07_DESIGN_TOKENS.md`:
terracotta `#c0533a` accent, sky-blue `#87ceeb` `hoiboy.uk` signature, dark
`#141414` background. Type is the consulting-ops retro stack — **VT323** for the
title, **IBM Plex Mono** for the eyebrow / tagline / signature — vendored under
`fonts/` (OFL; licenses alongside) and embedded as base64 `@font-face` so they
render identically anywhere. No photos — title + tagline + logo wordmark.

## Where the card renders (placement standard)

`share-card.*` is a **social-share-only** image. Its visible placement depends on the page type — this is enforced in `layouts/_partials/hero-pick.html` + `layouts/_default/single.html`:

- **Service pages** (`/hire-hoi/ai-consultancy/work-with-hoi`, `/automation-services`, `/ai-adoption-training`, `/claude-code-harness-architect`, `/pricing-billing`, and the portfolio index): the card is **hidden** (the page's `og:image` only). It must NOT appear as a hero or in the bottom photo-gallery.
- **Individual portfolio project pages** (`/hire-hoi/ai-consultancy/portfolio/<client>/`): the card is the **hero** image at the top of the page (unless the bundle has an explicit `hero.*`). Real project **screenshots** in the same bundle still render as the gallery below.

So: drop `share-card.png` into any bundle for the og:image; on a portfolio project page it doubles as the hero, everywhere else it stays out of the visible page.

## Regenerate

```bash
python3 scripts/social-cards/gen_card.py   # needs rsvg-convert (librsvg)
```

Edit `cards.tsv` to change a title/tagline, then re-run and rebuild the site.

## AGIT community feature images (`gen_agit_feature.py`)

A sibling generator for the **Asians & Gingers in Tech** community features
(`content/community/agit-featured/<slug>/`). Unlike the text-only consulting
cards, each AGIT feature is **photo-driven** and gets a **pair** of images:

- `hero.jpg` — portrait **4:5** (1080×1350) display photo + AGIT logo watermark,
  EXIF-stripped. The on-page hero, the index-card image, and the person's
  direct-to-social image.
- `share-card.png` — branded landscape **1200×630** link-preview: the submitted
  photo inset on the left, a powder-blue→cream gradient panel on the right with
  the `ASIANS & GINGERS IN TECH` eyebrow, the person's name (VT323) and role
  (IBM Plex Mono), and the AGIT logo watermark bottom-right. `head.html` prefers
  `share-card.*` over the hero for `og:image`, so a portrait submission no longer
  gets its head/legs sliced off in the link preview.

Brand: AGIT navy `#0c1c2d` + orange `#da611c` on the gradient sampled from the
AGIT banner art. The AGIT logo is vendored at `assets/images/agit-logo.png` (a
downscaled, EXIF-clean copy of the Drive master; masked to a circle at render
time). Same VT323 + IBM Plex Mono faces as the consulting cards.

Design tokens (the full frozen spec, with the logo-size reasoning, lives in
`docs/research/07_DESIGN_TOKENS.md` under "AGIT feature-image tokens"):

| Token | Value |
|---|---|
| Navy (name / logo border) | `#0c1c2d` |
| Orange (eyebrow / rule / divider) | `#da611c` |
| Grey (role text) | `#4f5b64` |
| Panel gradient (top to bottom) | `#b5dae7` to `#f9ebdf` |
| Name font | VT323, up to 80px (auto-shrinks, floor 12px, max 2 lines) |
| Role font | IBM Plex Mono, up to 28px |
| Eyebrow font | IBM Plex Mono Bold, 18px, letter-spaced across the panel |
| Logo watermark | circular, bottom-right: 92px on the share-card, 20% of width on the hero |
| Share-card layout | 748px photo panel, 48px right-panel inset, 6px orange divider |

Inputs (so the whole set can be regenerated after a design change, like `cards.tsv`):

- `agit-features.tsv` — `slug <TAB> name <TAB> role` (role may be empty).
- `agit-sources/<slug>.<ext>` — the EXIF-clean **source** photo. These live here,
  outside `content/`, so they are never published and never appear in the page's
  photo-gallery (`single.html` galleries every bundle image except the hero and
  `share-card.*`).

```bash
python3 scripts/social-cards/gen_agit_feature.py           # regenerate every feature
python3 scripts/social-cards/gen_agit_feature.py <slug>    # regenerate one feature
```

The `/agit-featured` skill calls this at publish time. Re-run with no slug after a
design tweak to rebuild every feature's pair, then rebuild the site.
