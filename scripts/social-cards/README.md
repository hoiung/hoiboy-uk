# Consulting social-share cards

Per-page 1200×630 Open Graph / Twitter share cards for the consulting pages
**and client case-study (portfolio) pages**, so each page gets a distinct,
correctly-sized social card instead of falling back to the shared `hoi-mug.jpg`
default (or, for the harness page, the old 1200×900 card which emitted a
non-standard aspect ratio in feeds).

## How it works

`gen_card.py` renders each row of `cards.tsv` (`slug <TAB> title <TAB> tagline`)
to `content/consulting/<slug>/share-card.png`. `layouts/_partials/head.html`
picks up `share-card.*` as the page's `og:image` (resized to 1200 wide, aspect
preserved), so a 1200×630 source emits a correct 1.91:1 card.

The `slug` is the page bundle path under `content/consulting/`, so **nested
slugs work as-is** — a client case study at
`content/consulting/portfolio/cu-architects/` is just the row
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

- **Service pages** (`/consulting/work-with-hoi`, `/automation-services`, `/ai-adoption-training`, `/claude-code-harness-architect`, `/pricing-billing`, and the portfolio index): the card is **hidden** (the page's `og:image` only). It must NOT appear as a hero or in the bottom photo-gallery.
- **Individual portfolio project pages** (`/consulting/portfolio/<client>/`): the card is the **hero** image at the top of the page (unless the bundle has an explicit `hero.*`). Real project **screenshots** in the same bundle still render as the gallery below.

So: drop `share-card.png` into any bundle for the og:image; on a portfolio project page it doubles as the hero, everywhere else it stays out of the visible page.

## Regenerate

```bash
python3 scripts/social-cards/gen_card.py   # needs rsvg-convert (librsvg)
```

Edit `cards.tsv` to change a title/tagline, then re-run and rebuild the site.
