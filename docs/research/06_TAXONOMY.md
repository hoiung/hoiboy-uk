# Taxonomy

**Date**: 2026-04-07

> **SUPERSEDED IN PART. Read this box before the body.** This is the original
> planning document and it is kept for the decision trail, not as a description of
> the current site. Three of its decisions have since been reversed or overtaken;
> each reversal is recorded in "Update (2026-07-25, blog-priv#62)" at the bottom
> rather than edited away, because a decision quietly deleted is a decision nobody
> can audit. Current state in one line: **7 categories, served at
> `/blogs/<category>/`, rendered by `layouts/_default/list.html`, with no
> `categories` taxonomy at all.**

## Decision

- **Categories** (primary, sidebar nav): `food`, `adventure`, `dance`, `tech`
- **Tags** (secondary, freeform): `ramen`, `tokyo`, `salsa`, `hugo`, `python`, etc.

Diverges from Diehl's tags-only model because Hoi's content spans **distinct topic areas**, not one niche. Categories give clean top-level navigation; tags handle the long tail.

## Frontmatter pattern

```yaml
---
title: "Best ramen in Shimokitazawa"
date: 2019-08-12
categories: [food-booze]
tags: [ramen, tokyo, japan]
slug: best-ramen-shimokitazawa
---
```

## Rules

- **One primary category per post** by default .  keeps nav clean
- Cross-over posts can have multiple categories (`[adventure, dance]` for a dance trip to Cuba), used sparingly
- **Tags are unlimited** and freeform
- Category names are lowercase and **must be one of the 7 section slugs exactly**:
  `food-booze`, `adventure`, `dance`, `tech-ai`, `life`, `entrepreneurship`, `trading`.
  Not all are single words, and this is not cosmetic: blog-priv#62 made an unknown
  category a HARD BUILD FAILURE (`errorf` in `layouts/_partials/breadcrumb-trail.html`
  and `layouts/_default/single.html`), because a category with no `_index.md` landing
  used to emit a silently dead link. The old "single word" wording is what produced the
  `categories: [food]` frontmatter example this file used to carry, which built fine
  before blog-priv#62 and is a hard build failure after it; the example above was
  corrected to `[food-booze]` in the same change.
  `docs/AUTHORING.md` is the canonical list.

## Hugo wiring

`config.toml` declares both taxonomies:

```toml
[taxonomies]
  category = "categories"
  tag = "tags"
```

Hugo auto-generates:
- `/categories/food/` .  list of food posts
- `/categories/adventure/`, `/categories/dance/`, `/categories/tech/`
- `/tags/<tag>/` .  list per tag
- `/categories/` .  index of all categories
- `/tags/` .  index of all tags

Sidebar nav links to the four category pages directly: `/food/`, `/adventure/`, `/dance/`, `/tech/` (with permalink rewrites in config so URLs stay short).

## Sidebar nav (FLAT .  never grows)

```
hoiboy.uk
─────────
Index
About
─────────
Food
Adventure
Dance
Tech
─────────
GitHub  LinkedIn  RSS
```

Sidebar shows category names only. Clicking a category goes to its landing page in the main content area. Sidebar size is constant regardless of how many posts exist.

**Why flat and not a tree**: at hundreds of posts the tree sidebar gets visually unwieldy and ships a huge DOM on every page. Putting the post list in the main content area scales forever, loads faster, is mobile-friendly.

**Update (2026-07-23, blog-priv#59):** the sidebar has since grown beyond the category nav this doc specifies. It now also carries a **Hire Hoi** section (AI Consultancy, ICT Consultancy, Permanent Roles) above the categories, plus a Join Community section and social links. Those sections are defined in `config/_default/menus.toml`, not here; this doc remains authoritative for the category nav only.

## Category landing pages (main content area)

When you click "Food", the main content area shows posts grouped by year (newest first):

```
Home › Food

Food
────

2024
  Best ramen in Shimokitazawa
  Pho in Hanoi at 6am
  Why pad thai is overrated

2023
  Cooking laksa from scratch
  ...

2019
  ...
```

Same pattern for `/adventure/`, `/dance/`, `/tech/`.

## Breadcrumbs (everywhere)

Every page has a breadcrumb trail at the top of the main content:

- `/` → `Home`
- `/food/` → `Home › Food`
- `/food/best-ramen-shimokitazawa/` → `Home › Food › Best ramen in Shimokitazawa`

## Hugo implementation

- **Sidebar**: standard flat partial (`layouts/partials/sidebar.html`) .  ~15 lines
- **Category landing**: SUPERSEDED. Landings are Hugo SECTIONS, not taxonomy terms, and render through `layouts/_default/list.html`, which cross-filters `site.RegularPages` on `Params.categories`. No taxonomy template is involved.
- **Breadcrumbs**: walking `.Parent` chain (`layouts/partials/breadcrumbs.html`) .  ~15 lines
- All native Hugo, no plugins
- Congo theme has breadcrumbs and grouped taxonomy pages built in .  even less work for us

## Import categorisation strategy (Phase 1 onwards)

WordPress backup will have its own historical categories. Strategy: **Hybrid C** (auto-assign obvious, flag ambiguous).

| Source signal | Auto-assign to |
|---|---|
| WP category contains `recipe`, `cook`, `eat`, `food`, `restaurant` | `food` |
| WP category contains `travel`, `trip`, `hike`, `adventure` | `adventure` |
| WP category contains `dance`, `salsa`, `bachata`, `kizomba`, `dj` | `dance` |
| WP category contains `code`, `tech`, `programming`, `dev`, `linux` | `tech` |
| Multiple matches | Flag for manual review |
| No matches | Flag for manual review |

Flagged posts go into `docs/research/categorisation-review.md` as a checklist for Hoi to triage in batches.

## Future categories

Add by editing `config.toml` and the sidebar partial. No migration needed .  existing posts keep their categories. New category just shows up in nav.

## Update (2026-07-25, blog-priv#62)

Three reversals, recorded rather than silently applied (AP #28: a doc that states
an intent has to state the reversal too, or the next reader re-derives the old
decision from a document that still argues for it).

**1. Short root-level category URLs are REVERSED.** The body says the sidebar
links to `/food/`, `/adventure/` and so on, "with permalink rewrites in config so
URLs stay short". That was a deliberate choice and it is now undone: the 7
categories are served at `/blogs/<category>/`.

Why: root-level category URLs put blog categories on the same footing as the real
top-level sections, so `/entrepreneurship/` sat beside `/hire-hoi/` and `/legal/`
as if it were the same kind of thing. It is not. `Blogs` is a real level in the
information architecture, and the site now says so in all four places that express
it: the URL, the on-page breadcrumb (`Home > Blogs > Tech & AI > <post>`), the
sidebar heading, and the social-card eyebrow. Every retired URL 301s
(`static/_redirects`); posts moved too, `/posts/<slug>/` to `/blogs/<slug>/`.

**2. The `categories` taxonomy is switched OFF.** The body declares
`category = "categories"` under `[taxonomies]`. It is gone. It produced 8
indexable `/categories/*` URLs listing exactly the same posts as the landings,
not `noindex`, rendering the literal word "Categories" with mangled auto-titles
("Tech-Ai"). Two indexable pages listing identical content compete; the landings
win because they are hand-titled and now canonical. `/categories/*` 301s into
`/blogs/*`. **`tags` (217 URLs) and `series` (2 URLs) are untouched.**

What was removed is the taxonomy MAPPING only. The `categories:` front-matter key
stays on all 79 posts and is load-bearing: `breadcrumb-trail.html`,
`related-posts.html`, `_default/list.html` and `_default/single.html` all read
`.Params.categories`, so stripping the key would empty every landing and break the
post breadcrumb. Asserted by `scripts/test_taxonomy_cleanup.py`.

**3. There are 7 categories, not 4.** The body names `food`, `adventure`, `dance`,
`tech`. The live set, in the operator's stated order, is: Tech & AI,
Entrepreneurship, Trading, Food & Booze, Adventure, Dance, Life
(`tech-ai`, `entrepreneurship`, `trading`, `food-booze`, `adventure`, `dance`,
`life`). `config/_default/menus.toml` is the authoritative list; templates and
tests read it rather than hardcoding slugs.

**Where the current contract lives**: `config/_default/hugo.toml` `[permalinks]`
and `[taxonomies]`; `config/_default/menus.toml`; `static/_redirects`;
`content/posts/_index.md` (the `/blogs/` hub). Enforced by
`scripts/test_permalink_contract.py`, `test_redirects_order.py`,
`test_redirects_coverage.py`, `test_hub_listing.py`,
`test_section_keyed_regression.py` and `test_taxonomy_cleanup.py`.
