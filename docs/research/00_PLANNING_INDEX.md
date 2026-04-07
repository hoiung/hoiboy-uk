# hoiboy.uk — Planning Trail

This folder maps the journey from "I have 22 years of blogs" to a live, Claude-managed site at hoiboy.uk.

## Index

1. [01_STACK_AND_DESIGN.md](01_STACK_AND_DESIGN.md) — Static site generator comparison + Diehl design reference. Decision: **Hugo**.
2. [02_BLOG_IMPORT_PIPELINE.md](02_BLOG_IMPORT_PIPELINE.md) — How to import 22 years of legacy posts from WordPress / Blogger / Medium / Tumblr / archived sites into clean markdown.
3. [03_PRECOMMIT_DECISIONS.md](03_PRECOMMIT_DECISIONS.md) — Which pre-commit hooks and CI checks to copy from auto_pb_swing_trader and SST3, and which to skip.
4. [04_CLAUDE_MANAGED_WORKFLOW.md](04_CLAUDE_MANAGED_WORKFLOW.md) — How the GitHub repo + Cloudflare Pages + Claude Code loop works day to day.
5. [05_PHASING_AND_SOURCES.md](05_PHASING_AND_SOURCES.md) — Confirmed sources (WordPress backup, HTML scraps, Google Docs/docx) and the 4-phase rollout (Foundation → WP → HTML → docx).

## Key decisions so far

| Decision | Choice | Date |
|---|---|---|
| Static site generator | **Hugo** (Zola as fallback) | 2026-04-07 |
| Hosting | Cloudflare Pages (free, native Hugo support) | 2026-04-07 |
| Domain | hoiboy.uk (already registered with Cloudflare) | 2026-04-07 |
| Repo visibility | **Public** (portfolio evidence for AI Agent Orchestrator job hunt) | 2026-04-07 |
| Repo name | `hoiung/hoiboy-uk` | 2026-04-07 |
| Design reference | stephendiehl.com (greyscale, IBM Plex, sidebar nav, tags-only) | 2026-04-07 |
| Theme | TBD — candidates: `risotto`, `archie`, `hugo-paper` | open |
| Voice rule | Hoi's prose is sacred. Never edited. Cleanup only. | 2026-04-07 |

## Open questions (waiting on user)

1. ~~Where do the 22 years of blogs live?~~ **Answered 2026-04-07**: WordPress backup (primary), scattered local HTML, Google Docs/.docx. See `05_PHASING_AND_SOURCES.md`.
2. Roughly how many posts? How many images?
3. Sidebar nav items from day one (Index, Blog, Tags, About, GitHub, LinkedIn, RSS, anything else)?
4. Any look/feel non-negotiables beyond "minimal like Diehl"? (dark mode, photo on homepage, your own colour, serif body)
5. Theme pick: `risotto` (recommended starting point) vs `archie` vs `hugo-paper` vs custom?
