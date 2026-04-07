# hoiboy.uk

Personal blog of Hoi. Republished from 22 years of writing across various platforms, plus new posts.

**Live**: https://hoiboy.uk
**Stack**: Hugo (custom minimal theme) + Cloudflare Pages
**Managed by**: Claude Code (AI agent), see commit history

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
