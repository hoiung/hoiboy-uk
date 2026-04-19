# SST3 Solo Workflow

## 5-Stage Solo Workflow Model

**Your Role**: Orchestrate research/review via subagent swarms; implement directly. See `../dotfiles/SST3/workflow/WORKFLOW.md` for full 5-stage workflow.

**Default: PLANNING MODE** — execute only when user says "work on #X" / "implement this". No file changes, no commits in planning mode. When unclear, ask.

**MANDATORY READING**:
1. `../dotfiles/SST3/standards/STANDARDS.md` (ALWAYS)
2. `../dotfiles/SST3/standards/ANTI-PATTERNS.md` (ALWAYS — 18 documented failure modes you must not repeat)
3. `{repository-name}/CLAUDE.md` (ALWAYS - replace with repo root)

**Reading Confirmation Checklist** (MUST display and complete):
- [ ] Read STANDARDS.md
- [ ] Read ANTI-PATTERNS.md
- [ ] Read {repository-name}/CLAUDE.md

**Critical behavioural rules** (full detail in STANDARDS.md + ANTI-PATTERNS.md):
- **GREP BEFORE WRITING/CODING**: before creating ANY new file, rule, memory, helper, hook, harness, function, class, component, workflow, process, design, or piece of logic — grep relevant directories with multiple synonyms. Update existing in place if found. New files only after grep confirms nothing exists. (AP #10)
- **MULTI-LAYER SUBAGENT DISCIPLINE** (AP #14): never stingy. Subagent count is DYNAMIC, scaled to cover every directory / file / claim category line-by-line — no stone left unturned. NOT 2-3 as a default. If the work has 12 claim categories, dispatch ≥12 subagents. Use LAYERS cross-checking each other from DIFFERENT angles (layer 2 ≠ layer 1 prompt). Main agent VERIFIES every subagent finding against source — never assume the subagent got it right. Every claim must be factually provable AND the proof method must be documented inline so future audits don't false-positive on it.
- **AP #9 Single-Source Edits**: every edit to a multi-research artefact must integrate ALL relevant sources in the same pass. Never apply one in isolation.
- **AP #11 Stopping vs Applying**: when an audit surfaces a documented violation, RUN the full process (false-positive sweep then apply). Don't stop to ask permission for fixes the standards already mandate. Don't apply without the sweep.
- **AP #12 No Observability**: every component needs structured logs, metrics, and audit trails AT WRITE TIME. Not after the first incident.
- **AP #13 "Proceed" ≠ "Bypass Process"**: when the user says okay / proceed / yes / go ahead, that means **proceed using the full standard process** — not skip the sweeps, gates, Ralph reviews, or guardrails. User authorisation never bypasses workflow.
- **AP #17 Keep Going Until Done**: do NOT stop mid-work to ask permission, wait for user confirmation, or "check in". Phase checkpoints post a comment to the Issue and CONTINUE. Stop ONLY for: (a) context at 80%+ of model window, (b) irreversible destructive action needing user consent (force-push, rm -rf, DROP TABLE, branch deletion), (c) genuinely stuck after investigation (not a first-response-to-friction reflex), (d) task complete. Warn at 70%, keep working until 80%. The 1M window exists to be used.
- **AP #16 Monitor, Don't Fire-and-Forget**: every script / command / subprocess / test / deployment / commit / push you launch must be verified end-to-end (tail logs, check exit code, verify output, confirm side effects). "Started" is not "done". For `run_in_background`, poll BashOutput. Be the user's eyes and ears, not just their executioner. If you cannot answer "what happened?" with specifics, you fired and forgot — go check NOW.
- **AP #18 Sample Invocation Validates Workflow**: for any change touching pipeline / backtest / SL1 / SL2 / orchestration / CLI-wiring / cross-module function-arg propagation — run an actual end-to-end sample invocation (real CLI, real DB, small liquid basket 8 tickers) BEFORE closing. Unit + smoke tests are necessary but NOT sufficient. Mocks that accept `**kwargs` silently discard params and do NOT prove propagation — assert `call_args.kwargs[...]` explicitly. Stage 4 Verification Loop mandatory gate. See STANDARDS.md "Testing Priority — Workflow Validation Gate".

**STOP if**: No GitHub Issue exists. Create Issue using `../dotfiles/SST3/templates/issue-template.md`.

### Solo Workflow Overview

**Context Window**: 1M tokens (Opus 4.6/Sonnet 4.6), 200K (Haiku 4.5)
**Content Budget**: ~42K tokens (STANDARDS.md + CLAUDE.md + Issue loaded at session start)
**Handover at**: 80% of model window (800K for 1M, 160K for Haiku) — STOP threshold, not routine. Warn at 70%. Keep working until 80%.
**Issue Header**: `## Solo Assignment (SST3 Automated)`
**Branch**: `solo/issue-{number}-{description}` (commit per file, no PR)
**Merge**: Direct merge to main after Ralph Review passes (BEFORE user review - protects work)

### Execution Guardrails (Built-in)

Pre-start read (CLAUDE.md + STANDARDS.md + Issue) → phase checkpoints (70%+ warn, 80%+ STOP) → post-compact re-read → verification loop until clean → user-review-checklist.md.

### Branch Safety (CRITICAL — DO NOT VIOLATE)

- **NEVER switch branches** (`git checkout main`, `git checkout -b`, `git switch`).
- **Always commit and push to the CURRENT active branch** — it will get merged later.
- If you need something on main, **ask the user** — do NOT switch yourself.
- The only exception is creating a NEW solo branch at the START of work.

### Command Interface

- `/start` — list repos, prompt selection, load CLAUDE.md, WAIT for task.
- `/SST3-solo` — load STANDARDS.md + repo CLAUDE.md, display summary, prompt for task, execute with guardrails.

Handover template: `../dotfiles/SST3/templates/chat-handover.md` (post checkpoint to Issue FIRST).

## External Research References

**Location**: `docs/research/` in project root
**Check BEFORE external research**: Existing research references
**Capture AFTER research**: If 3+ external resources found, create/update research reference
See: `../dotfiles/SST3/reference/research-reference-guide.md` for complete guide

## Quality Standards

**See STANDARDS.md** — Never Assume (read source before concluding), Fix Everything (no scope/language excuses, no priority deferrals), Critical Thinking (challenge with evidence). Only valid skip reason: confirmed false positive (document why).

**Voice Content Protection** — when editing Hoi-voice prose (CV, LinkedIn, cover letters, blogs): wrap in `<!-- iamhoi --> ... <!-- iamhoiend -->`. Canonical rules in `../dotfiles/SST3/standards/STANDARDS.md` "Voice Content Protection" + AP #15. Single source of truth for banned words: `../dotfiles/SST3/scripts/voice_rules.py`. (#406 F3.8 dedup.)

## Ralph Review Loop (MANDATORY)

**Subagents are PLANNING ONLY** - they review, they do NOT write code.

**Flow**: Implement → Haiku → Sonnet → Opus → **Merge to main** → User Review

| Tier | Model | Purpose | Invocation |
|------|-------|---------|------------|
| 1 | `haiku` (MANDATORY) | Surface checks | `Task(model=haiku, prompt="Review per SST3/ralph/haiku-review.md...")` |
| 2 | `sonnet` (MANDATORY) | Logic checks | `Task(model=sonnet, prompt="Review per SST3/ralph/sonnet-review.md...")` |
| 3 | `opus` (MANDATORY) | Deep analysis | `Task(model=opus, prompt="Review per SST3/ralph/opus-review.md...")` |

**On FAIL any tier**: Main agent fixes → Restart from Tier 1 (Haiku)
**On PASS all 3**: Merge to main immediately (protects work), then user review

**Checklists**: `../dotfiles/SST3/ralph/`

## Quick Reference

### 5-Stage Workflow (ORDER-DEPENDENT — no skipping, no reordering)
```
Stage 1: Research — subagent swarm → main agent writes /tmp (findings + gaps + plan)
Stage 2: Issue Creation — main agent from /tmp, illustrations, compact breaks, quality mantras verbatim
Stage 3: Triple-Check — subagents verify scope vs audit = 100%, chat history, dead code
Stage 4: Implementation — main agent implements, Verification Loop, Ralph Review, merge, user-review-checklist
Stage 5: Post-Implementation Review — subagent swarm: wiring, goal alignment, quality scan, regression tests
```

### Solo Execution Checklist (Stage 4)
```
## Working on Issue #X
Read CLAUDE.md, STANDARDS.md, Issue
Create branch: git checkout -b solo/issue-{X}-{description}
Execute phase 1, commit per file, push, post checkpoint
Execute phase 2, commit per file, push, post checkpoint
...
Run verification loop until clean (overengineering, reuse, duplication, fallbacks, wiring, regression, quality)
Run Ralph Review (Haiku → Sonnet → Opus)
Merge to main (BEFORE user review - protects work, check for conflicts first)
Post user-review-checklist.md (from TEMPLATE, ALL sections mandatory)
User reviews and approves
Cleanup branch, close Issue
```

### Emergency Procedures
- **Context overflow**: Create handover immediately
- **Stuck**: Re-read Issue, identify blocker, post to Issue
- **User compact**: Re-read CLAUDE.md, STANDARDS.md, Issue last comment

### MCP Configuration (Global)
- **Location**: `~/.claude.json` (user scope)
- **Verify**: Run `claude mcp list` or `/mcp` inside Claude Code
- **Servers**: chrome-devtools, github-checkbox, github, code-review-graph
- **code-review-graph**: Local AST knowledge graph (SQLite, Tree-sitter). 5 tools: graph, query, review, config, help (setup is a `config` sub-action). Local-only mode (`EMBEDDING_BACKEND=local`). Graph in `.code-review-graph/` (gitignored, regenerable). Parses 14 source languages (Python, TypeScript, TSX, JavaScript, Go, Rust, Java, C#, Ruby, C/C++, Kotlin, Swift, PHP, Solidity); NOT Markdown/YAML/JSON/SQL/TOML/shell. See `docs/guides/code-review-graph-playbook.md`.
- **Guide**: `../dotfiles/docs/guides/mcp-configuration.md`
- **Tool Selection**: See `../dotfiles/SST3/reference/tool-selection-guide.md`

### MCP Tools
- **Checkboxes**: `mcp__github-checkbox__update_issue_checkbox(issue_number, checkbox_text, evidence)`
- **Frontend**: Chrome DevTools MCP — guide `../dotfiles/docs/guides/chrome-devtools-mcp.md`, screenshots → `../screenshots/`
- **GitHub Issues**: issue_write, add_issue_comment, search_issues, get_file_contents, create_pull_request

### Google Drive Sync Conflicts
Edit fails with "File has been unexpectedly modified" → copy to `C:/temp/`, edit copy, copy back. See `docs/guides/google-drive-sync.md`.

---
<!-- ============================================================== -->
<!-- ⚠️ DO NOT MODIFY OR DELETE ANYTHING ABOVE THIS LINE ⚠️ -->
<!-- ============================================================== -->
<!-- All content ABOVE is SST3 standard managed by dotfiles issues -->
<!-- Modifications require dotfiles repository SST3 issue approval -->
<!-- Project-specific configuration begins BELOW this boundary -->
<!-- ============================================================== -->




















# Project-Specific Configuration

## Project Overview

Personal blog at **hoiboy.uk**, owned by Senh Hoi Ung (Hoi). Republishes ~22 years of writing from various legacy platforms plus new posts. Fully managed by Claude Code as a deliberate portfolio piece for AI Agent Orchestrator job applications — the commit history is itself evidence.

**Voice rule (cutoff: 2026-04-07)**: posts split into two universes by date.

- **Date < 2026-04-07** = legacy corpus. **Voice-sacred. NEVER edit the prose.** These ARE the voice persona research. They are evidence of pre-AI Hoi's voice. Cleanup is restricted to formatting, encoding fixes, broken markdown, dead links, image rehosting. The words stay untouched.
- **Date >= 2026-04-07** = new posts. Voice rules apply.

**Conditional reading (load ONLY when writing/editing a new post in Hoi's voice; do NOT read at session start):**

1. `docs/research/11_VOICE_PROFILE.md` (in-repo distilled voice rules)
2. `docs/research/12_AI_WRITING_TELLS.md` (in-repo research, why the rules exist)
3. `../dotfiles/cv-linkedin/VOICE_PROFILE.md` (canonical ~80K corpus analysis with verbatim sentence templates)

Then, before commit: `python3 scripts/check_voice_tells.py --check-only-new content/posts/<slug>/index.md`. This is the marker-driven voice guard (default = SKIP, opt in per region with `<!-- iamhoi -->` ... `<!-- iamhoiend -->` markers). It runs as a pre-commit hook AND in CI. Legacy posts (date < 2026-04-07) and untagged sections are silently skipped. See `docs/research/11_VOICE_PROFILE.md` "How to use the voice guard hook".

If you are NOT writing a new post (e.g. fixing CI, adding a layout, importing legacy, editing config), do NOT load these voice docs. Skip them and save the tokens.

## Technology Stack

- Generator: Hugo extended, version pinned in `.hugo-version` (currently 0.160.0)
- Theme: minimal custom theme inside `layouts/` and `assets/`. No upstream theme submodule.
- Content: Markdown (page bundles in `content/posts/<slug>/index.md`)
- Hosting: Cloudflare Pages, auto-build DISABLED, deploy gated by GHA on green CI
- Domain: hoiboy.uk (registered with Cloudflare)
- CI: GitHub Actions (Hugo build, markdownlint, lychee, em-dash voice guard, frontmatter, config traceability)

## Repository Structure

```
hoiboy-uk/
├── .hugo-version            # Hugo version pinned, single source of truth
├── lychee.toml              # Link checker config + allowlist
├── config/_default/
│   ├── hugo.toml            # baseURL, taxonomies, permalinks
│   ├── menus.toml           # Sidebar nav (main, categories, social)
│   └── params.toml          # Accent colour, build provenance, params
├── assets/css/main.css      # Templated CSS (~120 lines, greyscale + warm accent)
├── layouts/
│   ├── baseof.html          # Shell, sidebar + main + footer
│   ├── index.html           # Homepage
│   ├── _partials/           # head, sidebar, breadcrumbs, footer, post-list*, post-cards*
│   └── _default/            # single, list, taxonomy (handles /tags/ AND /food/)
├── content/
│   ├── _index.md            # Homepage stub
│   ├── about.md
│   ├── posts/<slug>/        # Page bundles
│   └── {food,adventure,dance,tech}/_index.md  # Section landings
├── scripts/
│   ├── validate_frontmatter.py
│   └── check_config_traceability.py
├── docs/research/           # Planning trail (00 to 10)
├── legacy/                  # Raw blog exports for Phase 1+ (gitignored)
├── .github/workflows/
│   ├── ci.yml               # Build, lint, voice, traceability, lychee
│   └── deploy.yml           # POSTs Cloudflare deploy hook on green CI
├── .pre-commit-config.yaml
├── .markdownlint.json
└── CLAUDE.md                # This file
```

## Development Setup

```bash
# Clone (no submodules, custom theme is in-tree)
git clone https://github.com/hoiung/hoiboy-uk
cd hoiboy-uk

# Install Hugo extended at the pinned version (NOT apt, which lags)
HUGO_VERSION=$(cat .hugo-version)
mkdir -p ~/.local/bin/hugo-versions/$HUGO_VERSION
cd ~/.local/bin/hugo-versions/$HUGO_VERSION
curl -sL https://github.com/gohugoio/hugo/releases/download/v$HUGO_VERSION/hugo_extended_${HUGO_VERSION}_linux-amd64.tar.gz -o hugo.tar.gz
tar -xzf hugo.tar.gz && rm hugo.tar.gz
ln -sf ~/.local/bin/hugo-versions/$HUGO_VERSION/hugo ~/.local/bin/hugo
cd -

# Local preview
hugo server
# http://localhost:1313

# Pre-commit hooks
pip install pre-commit
pre-commit install
```

## Project Standards

### Quality Checks
- **pre-commit**: file hygiene + markdownlint + frontmatter validator + config traceability
- **GitHub Actions ci.yml**: Hugo build, markdownlint-cli2, lychee, em-dash grep guard, frontmatter validator, config traceability
- **GitHub Actions deploy.yml**: POSTs Cloudflare deploy hook ONLY on green CI (auto-build disabled in Cloudflare to prevent racing)
- **No AI tells in NEW pages** (date >= 2026-04-07) written in Hoi's voice. RAG from `docs/research/11_VOICE_PROFILE.md` first, then the canonical `../dotfiles/cv-linkedin/VOICE_PROFILE.md`. Republished legacy posts (date < 2026-04-07) are exempt (pre-AI corpus = voice research itself, never touched).

### Adding a Post

See `docs/AUTHORING.md` for the full contract: frontmatter rules, image placement, heading hierarchy, voice rules, link rules, publish checklist. Quick version:

1. `content/posts/<slug>/index.md` with frontmatter: `title`, `date`, `categories: [<one of food-booze, adventure, dance, tech-ai, life, entrepreneurship, trading>]`, `tags: [...]`
2. Images in same folder as `index.md`, referenced by relative path with mandatory alt text
3. For any new prose (date >= 2026-04-07) written in Hoi's voice: RAG from `docs/research/11_VOICE_PROFILE.md` (in-repo) AND `../dotfiles/cv-linkedin/VOICE_PROFILE.md` (canonical) BEFORE drafting (no generic outputs, ever)
4. Commit, push. CI runs, then deploy hook fires, then live in ~90 seconds

### Importing Legacy Posts
- Raw exports go in `legacy/` (gitignored)
- Conversion scripts in `scripts/import_*.{sh,py}`
- Output: `content/posts/<slug>/index.md` page bundles
- Voice preserved verbatim. Cleanup limited to: encoding (`ftfy`), broken markdown, dead links, image rehosting
- See `docs/research/02_BLOG_IMPORT_PIPELINE.md`

### Git Workflow
- Branch: `solo/issue-{N}-description` for non-trivial work, direct to main for content drops
- Commits: small, descriptive, one logical change
- Commits authored by Claude Code — visible in history as portfolio evidence

## Common Commands

```bash
# Local preview
hugo server

# Production build
hugo --gc --minify -e production

# Run pre-commit on all files
pre-commit run --all-files

# Frontmatter validator
python3 scripts/validate_frontmatter.py

# Config traceability
python3 scripts/check_config_traceability.py

# Markdown lint manually
npx markdownlint-cli2 'content/**/*.md' 'docs/**/*.md'

# Link check
lychee --config lychee.toml './**/*.md'

# Break-glass deploy from local laptop (when GHA or Cloudflare is down)
# See docs/research/09_DEPLOYMENT.md for the full procedure.
wrangler pages deploy public --project-name=hoiboy-uk --branch=main
```

## Project-Specific Notes

- **Drafts**: use `draft: true` in frontmatter. Hugo skips them in production builds. Public repo + draft frontmatter = safe.
- **Legacy import is voice-sacred (date < 2026-04-07)**: never rewrite Hoi's prose during import. Only fix structure (encoding, dead links, image rehost). Legacy posts ARE the voice research; touching them corrupts the persona evidence.
- **Theme**: minimal custom theme (in-tree, ~15 files in `layouts/` + `assets/css/main.css`). Greyscale + warm terracotta accent + Inter. See `docs/research/01_STACK_AND_DESIGN.md` and `07_DESIGN_TOKENS.md`.
- **`check-ai-writing-tells.py`**: AVAILABLE in `../dotfiles/SST3/scripts/` but NEVER auto-wired. Run manually before publishing any new Hoi-voice content. Republished legacy posts are exempt (pre-AI corpus, false positive risk).
- **Em dashes**: ZERO in tracked files (CI hard fail). CLAUDE.md is exempt as SST3 internal doc per memory rule.

## Documentation Links

- README: `README.md`
- Research trail: `docs/research/`
- SST3 standards: `../dotfiles/SST3/standards/STANDARDS.md`
- Voice profile (in-repo, distilled): `docs/research/11_VOICE_PROFILE.md`
- Voice profile (canonical, full ~80K corpus analysis): `../dotfiles/cv-linkedin/VOICE_PROFILE.md`

---

*Template Version: SST3.0.0*
*Last Updated: 2026-04-07*
