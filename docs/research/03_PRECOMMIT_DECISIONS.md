# Pre-commit and CI Decisions

**Date**: 2026-04-07
**Sources audited**: `auto_pb_swing_trader/.pre-commit-config.yaml`, `dotfiles/SST3/scripts/`, `dotfiles/.github/workflows/`.

## Principle

Minimum useful set. This is a markdown-first blog, not a trading system. Quality engineering matters even for simple repos, but only the checks that actually catch bugs in this context.

## From auto_pb_swing_trader pre-commit

| Hook | hoiboy-uk relevance | Decision |
|---|---|---|
| `ruff-lint` (Python) | No Python in repo (just import scripts in `scripts/`) | SKIP |
| `ruff-format` (Python) | Same | SKIP |
| `check-added-large-files` | Block accidental binary uploads | **COPY** (1MB cap) |
| `check-case-conflict` | Cross-platform safety (WSL ↔ Cloudflare Linux build) | **COPY** |
| `check-merge-conflict` | Catch leftover `<<<<<<<` markers | **COPY** |
| `check-json` | No JSON in repo currently | SKIP (add later if needed) |
| `check-toml` | Hugo config could be TOML | DEFERRED (add when config.toml lands) |
| `check-yaml` | Hugo config could be YAML, GH Actions are YAML, frontmatter is YAML-ish | **COPY** |
| `debug-statements` | Python-only, irrelevant | SKIP |
| `end-of-file-fixer` | Standard text file hygiene | **COPY** |
| `mixed-line-ending` | LF enforcement, critical for Git on WSL | **COPY** (`--fix=lf`) |
| `trailing-whitespace` | Standard markdown cleaning | **COPY** |

### Custom trading hooks
All 7 (`check-modularity`, `no-temp-folder`, `check-unix-timestamps`, `validate-yaml-structure`, `check-timeframe-constants`, `check-data-service-bypass`, `sync-version`) are domain-specific. **SKIP all.**

## Markdown-specific (new, not in trading repo)

| Hook | Purpose | Decision |
|---|---|---|
| `markdownlint-cli` | Heading hierarchy, link syntax, list consistency | **ADD** (with relaxed config .  `MD013` line length off, `MD033` HTML allowed for any embeds) |
| `markdown-link-check` | Catch broken markdown link syntax | DEFERRED .  `lychee` in CI covers this better |
| `cspell` | Spell check | SKIP .  Hoi has 22 years of prose with proper nouns and slang. Too noisy. |
| Frontmatter validator | Ensure `title`, `date`, `tags` present | DEFERRED .  Hugo build will fail if frontmatter is broken. CI catches it. |

## From SST3

| Tool | Purpose | Decision |
|---|---|---|
| `check-ai-writing-tells.py` | Detect em dashes, AI-flagged words, bold-first bullets | **AVAILABLE BUT NOT BLOCKING.** False-positive risk on republished pre-AI corpus is high. Run manually on NEW posts only, never enforce on `content/posts/` automatically. |

Documented in CLAUDE.md so future-me doesn't wire it as a pre-commit hook by accident.

## CI (GitHub Actions)

`.github/workflows/ci.yml` runs on push to `main` and PRs:

1. **Hugo build (`--minify --gc`)** .  catches config errors, broken templates, missing layouts
2. **markdownlint-cli2** .  full repo lint
3. **lychee** .  link check, offline + live (`fail: false` for now .  flag, don't block)

Cloudflare Pages does its own production build. CI is the safety net before Cloudflare even sees the commit.

## Final pre-commit config

See `.pre-commit-config.yaml` in repo root. Six file-hygiene hooks + markdownlint scoped to `content/` and `docs/`.

```bash
# Install
pip install pre-commit
pre-commit install

# Run on all files
pre-commit run --all-files
```
