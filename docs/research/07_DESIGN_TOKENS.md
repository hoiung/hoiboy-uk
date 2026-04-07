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
