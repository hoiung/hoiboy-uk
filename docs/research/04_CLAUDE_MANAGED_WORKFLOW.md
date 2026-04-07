# Claude-Managed Workflow

**Date**: 2026-04-07

## The loop (updated 2026-04-07: GHA-gated, no auto-build race)

```
GitHub repo (hoiung/hoiboy-uk, public)
        |
        |  git push to main
        v
GitHub Actions ci.yml (build + lint + voice + traceability + lychee)
        |
        |  workflow_run on success
        v
GitHub Actions deploy.yml (POSTs Cloudflare deploy hook)
        |
        v
Cloudflare Pages (auto-build DISABLED, hook-only)
        |
        v
hoiboy.uk (live)
```

- One source of truth: the GitHub repo
- Cloudflare auto-build is DISABLED. Deploy is triggered by GHA on green CI only. Prevents the race where Cloudflare and GHA build the same commit in parallel.
- Custom domain (hoiboy.uk) attaches in one click since Cloudflare is the registrar.
- Free SSL, free CDN, free hosting.
- See `09_DEPLOYMENT.md` for the full procedure.

## Day-to-day collaboration

**New post:**
- Hoi: "publish my draft about X, here's the text"
- Claude: creates `content/posts/<slug>/index.md`, adds frontmatter, drops images, commits, pushes

**Edit existing post:**
- Claude opens the file, edits, commits. Diff visible in GitHub history.

**New page** (e.g. /now, /uses):
- Create `content/<slug>.md`, link in sidebar nav config, commit

**Theme tweak:**
- Edit `themes/.../assets/css/`, commit. Live in 10 seconds.

**Bulk import** of legacy blogs:
- Run scripts in `scripts/`, dump output into `content/posts/`, commit in batches

## Division of labour

| Task | Hoi | Claude |
|---|---|---|
| Decide what to publish | yes | no |
| Write the words | yes | no (voice sacred) |
| Tag / categorise | optional | yes (proposes, Hoi confirms) |
| Markdown formatting | no | yes |
| Images: download, resize, rehost | no | yes |
| Commit + push | no | yes |
| Cloudflare deploy | no | automatic |
| Domain / DNS one-time setup | yes | walks through |
| Theme design tweaks | tells Claude what to do | yes |

## Why GitHub specifically

1. **Version history** — every edit reversible
2. **Diffs are reviewable** — Hoi can eyeball before merging if he wants a gate
3. **Issues = editorial backlog** — "Republish 2008 Java rant" becomes Issue #12
4. **PRs as optional safety net** — Claude pushes to a `solo/` branch, Hoi merges. Or trust direct-to-main.
5. **Cloudflare Pages reads it natively** — no CI config needed, Cloudflare detects Hugo automatically
6. **Free, forever** — at this scale

## Why public

1. **CV evidence.** Targeting AI Agent Orchestrator roles. Public repo with Claude-authored commit history *is* the portfolio.
2. **Diehl does it.** Recognised pattern in the technical-blogger world.
3. **Content is public anyway** — hiding the markdown source adds nothing.
4. **Forkability** — someone likes the setup, forks it. Free distribution with Hoi's name on it.
5. **Issues become a public editorial backlog** (or stay private by just not using them publicly).

Drafts stay safe with Hugo's `draft: true` frontmatter (skipped in production builds) or in a local `drafts/` folder.

## Repo conventions

- **Branch**: direct to `main` for content drops; `solo/issue-N-description` for non-trivial structural work
- **Commits**: small, descriptive, one logical change. Authored by Claude Code, visible as portfolio evidence.
- **Issues**: editorial backlog and technical work tracking. Use SST3 issue template for non-trivial work.
- **Voice rule (load-bearing)**: never edit Hoi's prose during import. Cleanup only.
