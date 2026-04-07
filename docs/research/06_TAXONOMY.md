# Taxonomy

**Date**: 2026-04-07

## Decision

- **Categories** (primary, sidebar nav): `food`, `adventure`, `dance`, `tech`
- **Tags** (secondary, freeform): `ramen`, `tokyo`, `salsa`, `hugo`, `python`, etc.

Diverges from Diehl's tags-only model because Hoi's content spans **distinct topic areas**, not one niche. Categories give clean top-level navigation; tags handle the long tail.

## Frontmatter pattern

```yaml
---
title: "Best ramen in Shimokitazawa"
date: 2019-08-12
categories: [food]
tags: [ramen, tokyo, japan]
slug: best-ramen-shimokitazawa
---
```

## Rules

- **One primary category per post** by default — keeps nav clean
- Cross-over posts can have multiple categories (`[adventure, dance]` for a dance trip to Cuba), used sparingly
- **Tags are unlimited** and freeform
- Category names are lowercase, single word

## Hugo wiring

`config.toml` declares both taxonomies:

```toml
[taxonomies]
  category = "categories"
  tag = "tags"
```

Hugo auto-generates:
- `/categories/food/` — list of food posts
- `/categories/adventure/`, `/categories/dance/`, `/categories/tech/`
- `/tags/<tag>/` — list per tag
- `/categories/` — index of all categories
- `/tags/` — index of all tags

Sidebar nav links to the four category pages directly: `/food/`, `/adventure/`, `/dance/`, `/tech/` (with permalink rewrites in config so URLs stay short).

## Sidebar nav (planned)

**Tree-style, fully expanded by default, scrollable, collapsible per-category.**

```
hoiboy.uk
─────────
Index
About
─────────
▼ Food
   Best ramen in Shimokitazawa
   Pho in Hanoi at 6am
   ...
▼ Adventure
   Hiking the Annapurna circuit
   ...
▼ Dance
   First salsa congress
   ...
▼ Tech
   (future)
─────────
GitHub  LinkedIn  RSS
```

### Behaviour

- **Fully expanded by default** — every post title visible at first paint
- **Per-category collapse** via `<details>/<summary>` (semantic HTML, works without JS)
- **State persistence** via localStorage — folded categories stay folded next visit (~15 lines vanilla JS)
- **Scrollable** — sidebar `position: sticky; overflow-y: auto; height: 100vh`. Long lists scroll independently of main content.
- **No pagination** in sidebar — at hundreds of posts the DOM list is fine. No virtual scrolling until 5000+ posts.

### Implementation

- Hugo data: `.Site.Taxonomies.categories` → iterate posts within each category
- Custom sidebar partial (`layouts/partials/sidebar.html`) — ~30 lines
- Overrides theme default sidebar
- Theme base: **`risotto`** (minimal CSS, clean partials, easiest to override)
- Fallback if risotto fights us: write a bare theme from scratch (~200 lines, full control)

### Future option

If at scale (~500+ posts) the sidebar feels unwieldy, add year sub-grouping inside each category:

```
▼ Food
   ▼ 2024
      Best ramen in Shimokitazawa
   ▼ 2019
      Pho in Hanoi at 6am
```

Defer this until import is done and we can see how it actually feels.

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

Add by editing `config.toml` and the sidebar partial. No migration needed — existing posts keep their categories. New category just shows up in nav.
