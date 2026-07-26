# Text + photo social-share cards (consulting, legal, hire-hoi, landings, home, default)

Per-page 1200x630 Open Graph / Twitter share cards for the consulting pages,
client case-study (portfolio) pages, the **legal** pages, the top-level Hire Hoi
pages, every indexable **section-landing** (`_index.md`) page, and a **home**
photo composite, plus the site-wide branded default card - so each page gets a
distinct, correctly-sized social card instead of falling back to a generic image.

## How it works

`gen_card.py` renders six card sets, all from one brand system:

- **consulting** - each row of `cards.tsv` (`slug <TAB> title <TAB> tagline
  [<TAB> style]`) to `content/hire-hoi/ai-consultancy/<slug>/share-card.png`.
- **legal** - each row of `legal-cards.tsv` to `content/legal/<slug>/share-card.png`.
  `privacy` + `sub-processors` use the `hoiboy` style; `agit-story-guidelines`
  uses the `agit` style (navy `#0c1c2d` / orange `#da611c`). Its eyebrow is `LEGAL`,
  not a brand string: blog-priv#62 made every eyebrow the page's own parent trail.
- **hire-hoi** - each row of `hire-hoi-cards.tsv` to `content/hire-hoi/<slug>/share-card.png`,
  the top-level Hire Hoi leaf pages (e.g. `permanent-roles`). Same TSV shape as
  `cards.tsv`.
- **landings** - each content-relative landing path in `landing-cards.tsv` to that
  section-landing's own bundle (`content/<path>/share-card.png`), **including
  section roots** (`hire-hoi/`, `hire-hoi/ai-consultancy/`, `legal/`) and the blog
  category / `skills` / `community` sections. The card **title + tagline are read
  from that landing's own `_index.md` frontmatter** (title required; `description`
  becomes the tagline, shrunk to fit in full; **title-only** when there is no
  `description`). No taglines are stored in the TSV, so there is one source of
  truth and nothing to keep in sync. (blog-priv#61)
- **home** - `content/share-card.png`, a **photo composite** of `content/hoi-mug.jpg`
  (Hoi + the giant mug) filled to 1200x630 with a bottom scrim, the `hoiboy.uk`
  wordmark, and the site strapline. (blog-priv#61) It carries **no eyebrow at all**:
  the home page has no parent, so blog-priv#62's trail-derived eyebrow is empty and
  `eyebrow_svg` emits no text node rather than an empty one. It used to read
  `PERSONAL BLOG`.
- **default** - `content/default-card.png`, the `og:image` fallback for
  **taxonomy / term pages only** (`/tags/`, `/tags/<tag>/`, `/series/` and
  `/series/<series>/` - generated, no content bundle, so they cannot hold a
  co-located card). Replaced the old `hoi-mug.jpg`.
  This used to say `/tags/`, `/categories/*`. blog-priv#62 switched the `categories`
  taxonomy off, so `/categories/*` no longer generates at all - it survives only as a
  301 into `/blogs/*`, and the landings it duplicated own their own cards. `tags`
  and `series` are the two taxonomies this fallback still serves (verified against
  a build: `/series/` and `/series/bakeoff/` both resolve to `default-card`).

Run `python3 scripts/social-cards/gen_card.py [consulting] [legal] [hire-hoi]
[landings] [home] [default]` (no args = all six). `layouts/_partials/head.html`
picks up a page's own `share-card.*` as its `og:image` (resized to 1200 wide,
aspect preserved), and `default-card.png` as the taxonomy fallback.

**Guard:** `scripts/check_social_cards.py` (pre-commit + pre-publish + CI, with a
rendered-HTML backstop) fails the build on: a singular indexable page that is a
flat `.md`/`.markdown`/`.html` (Check A), a singular page that would fall back to
the default card (Check B), an indexable `_index.md` landing (section or home)
missing its own `share-card.*` (Check C - no hero fallback, since `head.html`'s
hero-pick is `.IsPage`-only), or an indexable auto-section missing its own card
(Check D - a TOP-LEVEL content directory Hugo renders as a list page with no
`_index.*` at all, so Check C cannot enumerate it; `/posts/` served the default this
way until blog-priv#62 added `content/posts/_index.md`. Check D also covers home
when `content/_index.md` is absent, which Check C cannot see either).

Between them these cover every page kind the site renders. One caveat worth knowing
rather than assuming away: in source-only mode there is no build to read, so a
section's served URL is derived from its content path, and a `[permalinks.section]`
rule makes those differ (`content/posts` serves at `/blogs/`). That URL is only used
to fnmatch `static/_headers` for noindex, so the blind spot is narrow - a stale glob
could silence one section - and it closes entirely when a build is present, since
`--built` hands the source check Hugo's own `trail.json` URL index.

Fix a Check D violation by adding the directory's `_index.md` and a
`landing-cards.tsv` row, not by hand-dropping a PNG: an auto-section can technically
hold a card (Hugo publishes the directory's files as page resources), but
`gen_card.py landings` reads each card's title and tagline from the landing's own
frontmatter, so without the `_index.md` there is nothing for the generator to read.

The `slug` is the page bundle path under `content/hire-hoi/ai-consultancy/`, so **nested
slugs work as-is** — a client case study at
`content/hire-hoi/ai-consultancy/portfolio/cu-architects/` is just the row
`portfolio/cu-architects <TAB> CU Architects <TAB> <tagline>`. Client
case-study cards use the **same template** (parent-trail eyebrow, which for these is
`HIRE HOI > AI CONSULTANCY > PORTFOLIO` since blog-priv#62 replaced the old
`HOIBOY AI LTD` brand string, page title,
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

- **Service pages** (`/hire-hoi/ai-consultancy/work-with-hoi`, `/automation-services`, `/ai-adoption-training`, `/claude-code-harness-architect`, `/ai-product-builder`, `/pricing-billing`, and the portfolio index): the card is **hidden** (the page's `og:image` only). It must NOT appear as a hero or in the bottom photo-gallery.
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
  the parent-trail eyebrow (`JOIN COMMUNITY > ASIANS & GINGERS IN TECH > AGIT
  FEATURED` since blog-priv#62; it was the bare `ASIANS & GINGERS IN TECH` before),
  the person's name (VT323) and role
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
