# hoiboy.uk

Personal blog of Hoi. Republished from 22 years of writing across various platforms, plus new posts.

**Live**: https://hoiboy.uk
**Stack**: Hugo (custom minimal theme, in-tree, ~15 files) + Cloudflare Pages + GitHub Actions
**Managed by**: Claude Code (Anthropic's CLI agent) operating under the **SST3** workflow.

## Built with SST3

This site is a deliberate portfolio piece. Every commit, every layout, every fix is the result of an AI agent (me, Claude) working under the **SST3 workflow**, a 5-stage solo agent process Hoi developed for AI-managed software delivery. The repo's commit history is itself the evidence: research, plan, implement, review, ship.

The SST3 workflow lives at: https://github.com/hoiung/sst3-ai-harness

What it gives this project:
- Issue-first scoping with quality mantras and verbatim guardrails
- Mandatory Ralph Review (Haiku → Sonnet → Opus tiers, planning-only) before merge
- Voice profile RAG (no AI tells, no em dashes, sentences sound like Hoi)
- "Fail fast, fix everything, no deferrals" engineering rules
- Cross-boundary contract verification (config keys, frontmatter schemas, deploy chain)

The bigger goal: **demonstrate AI agent orchestration end-to-end on a real, public, maintained product** as part of Hoi's AI Agent Orchestrator job hunt. If you're a hiring manager reading this, the commit history, the issue body, the docs/research/ trail, and the live site itself are all the same evidence. Read in any order.

## Repo layout

```
hoiboy-uk/
├── .hugo-version            # Pinned Hugo version, single source of truth
├── config/_default/         # hugo.toml, menus.toml, params.toml
├── assets/css/main.css      # Templated CSS, greyscale + warm accent
├── layouts/                 # Custom theme (~15 files, no upstream submodule)
│   ├── baseof.html
│   ├── _partials/
│   └── _default/
├── content/
│   ├── _index.md            # Homepage
│   ├── about.md
│   ├── posts/<slug>/        # Page bundles
│   └── {food,adventure,dance,tech}/  # Category section landings
├── scripts/                 # Frontmatter + traceability validators
├── docs/research/           # Planning trail (00 to 10)
├── lychee.toml              # Link checker config
├── .github/workflows/       # ci.yml + deploy.yml
└── CLAUDE.md                # AI workflow + project context
```

## Add a post

1. Create `content/posts/<slug>/index.md` with frontmatter:

   ```yaml
   ---
   title: "Post title"
   date: 2026-04-07
   categories: [food]
   tags: [ramen, tokyo]
   slug: post-slug
   ---
   ```

2. Drop any images in the same folder.
3. Commit, push. CI runs, then Cloudflare Pages rebuilds.

## Local preview

```bash
# Install Hugo extended at the pinned version (see CLAUDE.md for full setup)
hugo server
# http://localhost:1313
```

## Quality checks

- `pre-commit` runs file hygiene + markdownlint + frontmatter validator + config traceability
- GitHub Actions builds Hugo, lints markdown, voice-guards em dashes, validates frontmatter and config traceability, checks links
- Cloudflare Pages deploys ONLY on green CI via deploy hook (auto-build disabled, no race)

See `docs/research/` for the planning trail and tooling decisions.
