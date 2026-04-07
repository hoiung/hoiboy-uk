# hoiboy.uk

Personal blog of Senh Hoi Ung. Republished from 22 years of writing across various platforms, plus new posts.

**Live**: https://hoiboy.uk
**Stack**: Hugo (static site generator) + Cloudflare Pages
**Managed by**: Claude Code (AI agent), see commit history

## Repo layout

```
hoiboy-uk/
├── content/
│   ├── _index.md            # Homepage
│   └── posts/               # Blog posts as page bundles
│       └── <slug>/
│           ├── index.md     # Post body + frontmatter
│           └── *.png|jpg    # Co-located images
├── themes/                  # Hugo theme (git submodule, TBD)
├── static/                  # Site-wide static assets
├── docs/research/           # Planning, research notes, journey
├── scripts/                 # Import + maintenance scripts
├── config.toml              # Hugo config
└── CLAUDE.md                # AI workflow + project context
```

## Add a post

1. Create `content/posts/<slug>/index.md` with frontmatter:
   ```yaml
   ---
   title: "Post title"
   date: 2026-04-07
   tags: [tag1, tag2]
   ---
   ```
2. Drop any images in the same folder.
3. Commit, push. Cloudflare Pages rebuilds automatically.

## Local preview

```bash
hugo server --buildDrafts
# http://localhost:1313
```

## Quality checks

- `pre-commit` runs file hygiene + markdown lint on every commit
- GitHub Actions builds Hugo + checks links on push to main

See `docs/research/` for the planning trail and tooling decisions.
