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

```
hoiboy.uk
─────────
Index
Food
Adventure
Dance
Tech
─────────
Tags
About
─────────
GitHub
LinkedIn
RSS
```

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
