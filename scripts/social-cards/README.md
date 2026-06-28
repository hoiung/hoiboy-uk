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

## Regenerate

```bash
python3 scripts/social-cards/gen_card.py   # needs rsvg-convert (librsvg)
```

Edit `cards.tsv` to change a title/tagline, then re-run and rebuild the site.
