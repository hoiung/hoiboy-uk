# Voice Guard Plan - Marker-Driven AI Tells Hook (cross-repo: dotfiles + hoiboy-uk)

**Date**: 2026-04-08
**Status**: Plan, awaiting review
**Reviewers**: Hoi
**Related**: hoiboy-uk issue #2 (closing), dotfiles `cv-linkedin/VOICE_PROFILE.md`, dotfiles `SST3/scripts/check-ai-writing-tells.py`

## Executive summary

A voice-tells pre-commit hook **already exists** in dotfiles (`SST3/scripts/check-ai-writing-tells.py`, 208 lines, runs on `^cv-linkedin/.*\.md$`). It catches em dashes, ~34 banned words, bold-first bullets, and negation framing - but it does **whole-file scans only**, has **no marker-region support**, has **drift** from `VOICE_PROFILE.md` (missing ~26 words and all 6 banned phrases), has a **latent bug** (MASTER_PROFILE listed in both whitelist and exempt list), runs in **dotfiles only**, and is **not wired into CI** anywhere.

**Plan**: extend the existing script in place. Add marker-region support, sync rules to a single source of truth, fix the bug, mirror into hoiboy-uk via a vendored wrapper, wire both into pre-commit AND CI.

**Single source of truth strategy**: extract banned-word/phrase/pattern lists from `VOICE_PROFILE.md` Section 8 into a Python module `SST3/scripts/voice_rules.py`. Both `check-ai-writing-tells.py` and a new sync-check script import from it. `VOICE_PROFILE.md` keeps the human-readable list with a `generated from voice_rules.py` header. A sync-check hook enforces drift detection between the two.

**Cross-repo strategy**: dotfiles owns the canonical script + rules. hoiboy-uk gets a vendored copy under `scripts/voice_guard.py` plus a vendored `voice_rules.py`. A sync-check (scheduled, not blocking) detects drift between dotfiles canonical and hoiboy-uk vendored. CI in both repos runs the local copy. Vendoring chosen over runtime cross-repo path because dotfiles is private and GH Actions cannot clone it without secrets, and a runtime dep on a sibling directory breaks portable CI.

## Findings (compressed from 3 subagents)

### Existing dotfiles hook (`SST3/scripts/check-ai-writing-tells.py`)
- 208 lines, stdlib only + `sst3_utils.fix_windows_console`
- Hardcoded constants: `EM_DASH = '\u2014'`, `AI_FLAGGED_WORDS` (34 words), `BOLD_BULLET_PATTERN` (threshold 3, or 20 for CV files), `NEGATION_PATTERN`
- CLI: `python check-ai-writing-tells.py file1.md file2.md ...` (pre-commit mode) or no args (default whitelist scan)
- Whitelist (`PUBLIC_FACING_GLOBS`): 5 files. Exempt (`EXEMPT_PATHS`): everything else useful.
- **Latent bug**: `MASTER_PROFILE.md` is in both `PUBLIC_FACING_GLOBS` AND `EXEMPT_PATHS`. Exempt wins in pre-commit mode.
- No marker-region support
- Banned phrases NOT enforced (only 1 negation regex)
- ~26 words from `VOICE_PROFILE.md` Section 8 are missing from the script

### dotfiles `.pre-commit-config.yaml`
- Hook `check-ai-writing-tells` registered, `files: ^cv-linkedin/.*\.md$`, `pass_filenames: true`
- 8 other local hooks already in place via the pre-commit framework

### dotfiles `.github/workflows/validate.yml`
- JSON/YAML/JS validation, markdownlint (`continue-on-error: true`), secrets grep
- **No voice check in CI**. Pushes from another machine bypass the guard.

### dotfiles `cv-linkedin/VOICE_PROFILE.md`
- Section 8 (line 246) has the canonical anti-vocab list as a prose paragraph. ~60 banned words.
- Section 19 (line 544) "AI tells Hoi NEVER makes"
- Section 20 (line 582) "AI -> Hoi rescue rules"
- Section 23 (line 700) "DO/DON'T summary"
- Top-10 quick ref at line 775
- BANNED phrases lines 266-272 (6 entries)
- KEEP list lines 250-256 (overrides naive bans: passion, journey, deeply, truly, navigate-literal, back to basics, attention to detail)
- Format is markdown prose + bullets, not machine-parseable as-is
- No marker blocks

### CV/LinkedIn writing surface (dotfiles cv-linkedin/)
- **Whole-file safe** (pure Hoi voice): `CV_AI_TRANSFORMATION.md`, `CV_AI_TRANSFORMATION_FULL.md`, `CURRENT_CV.md`, `COVER_LETTER_*.md`, `CURRENT_LINKEDIN.md`
- **Mostly voice with meta tail**: `LINKEDIN_UPDATE_GUIDE.md` (sections 1-8 voice, 9-12 procedural)
- **Mixed voice + structured data - need region tags**: `MASTER_PROFILE.md`, `AI_SKILLS_AND_PORTFOLIO.md`
- **Must stay exempt** (AI-to-AI docs, voice corpus, research): `VOICE_PROFILE.md`, `PERSONA_CONTEXT.md`, `INTERVIEW_PREP_BANK.md`, `HIRER_PROFILE.md`, `INTERPERSONAL_SKILLS_REFERENCE.md`, `METRIC_PROVENANCE.md`, `HANDOVER_*.md`, `README.md`, `job-research/**`, `voice-corpus/**`, `voice-analysis-reports/**`
- **Future**: `cv-linkedin/applications/**/*.md` (not exists yet) for per-company outputs

### hoiboy-uk current state
- Pre-commit framework v4.5.1 installed and in use (`.pre-commit-config.yaml` has 4 hooks, none voice-related)
- CI em-dash guard runs at `ci.yml:69-79` over `content layouts assets config docs scripts README.md --exclude-dir=posts` (legacy `content/posts/` exempt)
- No voice script in hoiboy-uk
- `docs/research/11_VOICE_PROFILE.md` (in-repo distilled rules) and `12_AI_WRITING_TELLS.md` (research) already in repo
- Voice cutoff date: **2026-04-07** (foundation post). Anything dated `>= 2026-04-07` = new = voice rules apply.

### Cross-repo plumbing
- Both repos are siblings under `/home/hoiung/DevProjects/`. No submodules, no symlinks.
- hoiboy-uk references dotfiles via relative path `../dotfiles/...` in CLAUDE.md, research docs
- hoiboy-uk CI does NOT clone dotfiles (`actions/checkout` with `submodules: false`), so any runtime dependency on dotfiles content fails on the CI runner
- dotfiles is private; cross-repo CI checkout requires a deploy key or PAT - adds friction

## Design

### 1. Marker syntax (greenfield, no existing convention)

Two forms supported, both invisible in rendered Markdown.

**Region opt-IN** (scan only inside the markers, ignore the rest of the file):
```markdown
<!-- iamhoi -->
This block is Hoi voice and gets voice-checked.
Em dashes here will fail. Banned words like "delve" will fail.
<!-- iamhoiend -->

Anything outside the tags is ignored. You can put structured data,
code blocks, machine-readable tables, recruiter notes, JD copy-paste,
methodology metadata, anything - voice guard does not look at it.
```

**File-level opt-OUT** (skip the entire file regardless of whitelist):
```markdown
<!-- iamhoi-exempt -->
```
First non-blank line of the file. Documents intent inline.

**Region opt-OUT inside an otherwise voice-tracked file** (skip a noisy block in a Hoi-voice document):
```markdown
<!-- iamhoi-skip -->
This block is exempt. Useful for quoting JD text, recruiter messages,
or referenced banned words inside an example.
<!-- iamhoi-skipend -->
```

**Tag aliases** for non-Markdown contexts (Python comments, plain text):
- `# iamhoi` / `# iamhoiend`
- `# iamhoi-exempt`
- `# iamhoi-skip` / `# iamhoi-skipend`

The scanner accepts both HTML-comment and `#`-prefix forms via a single regex.

### 2. File-selection logic (after marker support lands)

For each candidate file (passed by pre-commit or matched by CI glob):

1. If file matches `EXEMPT_PATHS` glob -> skip (existing behaviour, kept for backstop)
2. Else read the file:
   - If first non-blank line matches `<!-- iamhoi-exempt -->` -> skip
   - If file contains any `<!-- iamhoi -->` markers -> scan ONLY tagged regions (region opt-in mode)
   - Else if file is in `PUBLIC_FACING_GLOBS` -> scan whole file minus any `<!-- iamhoi-skip -->` regions (legacy behaviour, kept)
   - Else -> skip (file is not opted-in via either marker or whitelist)
3. For each scannable region, run all rule checks
4. Report findings grouped by rule type, with file:line and the offending text

### 3. Single source of truth for rules

**New file**: `SST3/scripts/voice_rules.py`

```python
"""Single source of truth for voice rules.

Generated from cv-linkedin/VOICE_PROFILE.md Section 8 (anti-vocab),
Section 19 (banned phrases), and the hardcoded format rules.

Edit this file to update rules. Then run scripts/sync-voice-profile.py
to regenerate the markdown excerpt in VOICE_PROFILE.md and the
mirror in hoiboy-uk/scripts/voice_rules.py.
"""

EM_DASH = "\u2014"

# Section 8 KEEP BANNED list - full ~60 words
BANNED_WORDS = [
    "delve", "leverage", "spearhead", "synergy", "stakeholder", "robust",
    "seamless", "cutting-edge", "innovative", "impactful", "facilitate",
    "harness", "furthermore", "moreover", "pivotal", "tapestry",
    "landscape", "realm", "underscore", "meticulous", "beacon", "testament",
    "dynamic", "holistic", "ecosystem", "low-hanging fruit", "touch base",
    "circle back", "deliverable", "bandwidth", "moving forward", "align",
    "alignment", "actionable", "at scale", "iterate", "unpack",
    "gain traction", "reach out", "results-driven", "detail-oriented",
    "proven track record", "strategic initiative", "drive measurable impact",
    "committed to excellence", "dedicated team player",
    "cross-functional collaboration",
    # AI memoir tells
    "devoured", "dabbled", "avid", "rooted in", "as I evolved",
    "grounded well-rounded",
]

# Banned multi-word phrases
BANNED_PHRASES = [
    "It's worth noting that",
    "It's important to remember",
    "Throughout my career, I have",
    "I am excited to explore opportunities",
    "I am writing to express my interest",
    "Passionate about driving",
    "In summary,",
    "Moreover,",  # as a sentence opener
    "Furthermore,",
    "Additionally,",
]

# Authentic-Hoi exceptions: word might match a substring of a banned phrase,
# but if it appears in this list it is allowed in isolation.
KEEP_LIST = [
    "passion", "passionate", "journey", "deeply", "truly",
    "navigate",  # literal only - dance floor, 2D/3D
    "back to basics", "attention to detail",
]

# Format rules (regex sources, used by checker)
BOLD_BULLET_PATTERN = r"^\s*[-*]\s+\*\*[^*]+\*\*:\s"
NEGATION_PATTERN = r"[Ii]t'?s not .{3,30}, it'?s"
SMART_QUOTE_CHARS = ["\u201c", "\u201d", "\u2018", "\u2019"]  # curly quotes
UNICODE_ARROW_CHARS = ["\u2192", "\u21d2"]  # -> ⇒
```

`VOICE_PROFILE.md` Section 8 keeps the prose explanation but the actual list moves under a header `<!-- BEGIN voice_rules.py mirror -->` ... `<!-- END voice_rules.py mirror -->` so a sync script can update it from `voice_rules.py` and hard-fail on drift.

### 4. Sync script (drift detector)

**New file**: `SST3/scripts/sync-voice-profile.py`

- Reads `voice_rules.py` (importable) and `cv-linkedin/VOICE_PROFILE.md` (parsed for the marker block)
- Compares. Hard-fails if they differ.
- `--write` mode rewrites the marker block in VOICE_PROFILE.md from voice_rules.py
- Same script also compares `dotfiles/SST3/scripts/voice_rules.py` against `hoiboy-uk/scripts/voice_rules.py` if both exist; hard-fails on drift; `--write` syncs hoiboy-uk from dotfiles

Wired into pre-commit on `voice_rules.py` and `VOICE_PROFILE.md`.

### 5. Extend `check-ai-writing-tells.py` (in-place edits)

Changes to the existing script:

1. **Import rules from `voice_rules.py`** instead of hardcoded constants. Delete inline lists.
2. **Add marker-region scanner**: new function `extract_voice_regions(text) -> list[(start_line, end_line, text)]`. Handles `<!-- iamhoi -->` opt-in, `<!-- iamhoi-skip -->` opt-out (within an opt-in region), `<!-- iamhoi-exempt -->` file-level skip, plus `#`-prefix aliases.
3. **Add phrase checker**: new function `check_phrases(text, line_offset)` scans for `BANNED_PHRASES` (case-insensitive substring match, word-boundary aware).
4. **Update file-selection logic** per Design section 2.
5. **Fix MASTER_PROFILE bug**: remove from `EXEMPT_PATHS` (it should be scanned per the whitelist intent).
6. **Add `--check-only-new` flag** for hoiboy-uk: parses frontmatter `date:` field and skips files dated `< 2026-04-07` (legacy voice-sacred). Default off.
7. **Add `--report-format=json` flag** for CI integration.

### 6. Vendor into hoiboy-uk

**New file**: `hoiboy-uk/scripts/voice_rules.py` (copied from dotfiles)
**New file**: `hoiboy-uk/scripts/check_voice_tells.py` (copied from dotfiles, slightly adapted: removes the cv-linkedin specific defaults, defaults to `content/posts/**/*.md` with `--check-only-new` for the cutoff)

Both files have a header:
```python
"""COPY of dotfiles/SST3/scripts/{voice_rules,check-ai-writing-tells}.py.
Canonical lives in dotfiles. Drift is detected by sync-voice-profile.py
which runs in pre-commit on both repos.
"""
```

The drift-detect runs `diff` on the file pair (canonical vs vendored). Hard-fails on any difference. `--write` mode copies canonical -> vendored.

### 7. Pre-commit wiring

**dotfiles `.pre-commit-config.yaml`** - modify existing hook + add sync-check:

```yaml
- id: check-ai-writing-tells
  name: AI writing tells (em dash, banned words/phrases, formatting)
  entry: python3 SST3/scripts/check-ai-writing-tells.py
  language: system
  files: ^cv-linkedin/.*\.md$
  pass_filenames: true

- id: sync-voice-profile
  name: Sync voice rules between voice_rules.py and VOICE_PROFILE.md mirror block
  entry: python3 SST3/scripts/sync-voice-profile.py --check
  language: system
  files: '^(SST3/scripts/voice_rules\.py|cv-linkedin/VOICE_PROFILE\.md)$'
  pass_filenames: false
```

**hoiboy-uk `.pre-commit-config.yaml`** - add 2 new hooks:

```yaml
- id: check-voice-tells
  name: AI writing tells in tagged regions and new posts
  entry: python3 scripts/check_voice_tells.py --check-only-new
  language: system
  files: '^(content/posts/.*\.md|content/_index\.md|content/about\.md|docs/research/.*\.md)$'
  pass_filenames: true

- id: sync-voice-rules
  name: Voice rules drift check (vendored vs dotfiles canonical)
  entry: python3 scripts/sync_voice_rules.py --check
  language: system
  files: '^scripts/(voice_rules|check_voice_tells)\.py$'
  pass_filenames: false
```

The sync hook only fires when the local copies change; it then verifies they match dotfiles canonical.

### 8. CI wiring

**dotfiles `validate.yml`** - add a job:

```yaml
voice-tells:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: '3.12' }
    - name: AI writing tells (full repo scan)
      run: python3 SST3/scripts/check-ai-writing-tells.py
    - name: Voice rules sync check
      run: python3 SST3/scripts/sync-voice-profile.py --check
```

**hoiboy-uk `ci.yml`** - add a step after the existing em-dash guard:

```yaml
- name: AI writing tells (new posts + tagged regions)
  run: python3 scripts/check_voice_tells.py --check-only-new content/ docs/
```

Note: the voice rules sync-check in hoiboy-uk CI is skipped because dotfiles is not present on the CI runner. Sync is enforced locally via pre-commit only. Drift is detected when a developer commits - same gate as CV/LinkedIn voice today.

### 9. Bug fixes rolled in

- `MASTER_PROFILE.md` removed from `EXEMPT_PATHS` (currently in both lists).
- Word list expanded from 34 to ~60 to match VOICE_PROFILE Section 8.
- Banned phrases (6) enforced for the first time.
- Top-10 quick-ref patterns from VOICE_PROFILE line 775 added as named regex group.

## Phasing

### Phase 1 - dotfiles canonical extension (no hoiboy-uk yet)
- [ ] Create `SST3/scripts/voice_rules.py` with full word/phrase/pattern lists from VOICE_PROFILE.md
- [ ] Refactor `check-ai-writing-tells.py` to import from `voice_rules.py`, delete inline constants
- [ ] Add marker-region scanner (`extract_voice_regions`)
- [ ] Add phrase checker
- [ ] Update file-selection logic (whitelist + markers + exempt)
- [ ] Fix MASTER_PROFILE bug
- [ ] Add `--check-only-new`, `--report-format=json` flags
- [ ] Create `sync-voice-profile.py` and the marker block in `VOICE_PROFILE.md`
- [ ] Update dotfiles `.pre-commit-config.yaml` (sync-check hook only - voice hook stays as-is, just smarter now)
- [ ] Run pre-commit on every cv-linkedin file, fix any new findings or add region tags
- [ ] Add `voice-tells` job to `validate.yml`
- [ ] Atomic commit per file, push, verify CI green

### Phase 2 - hoiboy-uk vendoring + integration
- [ ] Copy `voice_rules.py` and `check-ai-writing-tells.py` (renamed `check_voice_tells.py`) into `hoiboy-uk/scripts/`
- [ ] Adapt defaults for hoiboy-uk: scan `content/posts/**/*.md`, honour cutoff date `2026-04-07`
- [ ] Create `hoiboy-uk/scripts/sync_voice_rules.py` (drift checker)
- [ ] Add 2 new hooks to `hoiboy-uk/.pre-commit-config.yaml`
- [ ] Add CI step in `hoiboy-uk/ci.yml`
- [ ] Run pre-commit + CI; fix findings or tag regions
- [ ] Atomic commit per file

### Phase 3 - region-tag rollout in dotfiles
- [ ] Add `<!-- iamhoi -->` regions to `MASTER_PROFILE.md` voice-prose sections
- [ ] Add `<!-- iamhoi -->` regions to `AI_SKILLS_AND_PORTFOLIO.md` voice-prose sections
- [ ] Add `<!-- iamhoi-skip -->` regions to `LINKEDIN_UPDATE_GUIDE.md` procedural sections (optional)
- [ ] Re-run hook, confirm no false positives

### Phase 4 - documentation
- [ ] Update `dotfiles/cv-linkedin/VOICE_PROFILE.md` Section 8 with the marker block + sync notes
- [ ] Update `hoiboy-uk/docs/research/11_VOICE_PROFILE.md` with marker syntax docs
- [ ] Update `hoiboy-uk/CLAUDE.md` voice rule section to mention the hook
- [ ] Update `dotfiles/CLAUDE.md` if needed
- [ ] Add `docs/research/13_VOICE_GUARD_HOOK.md` in hoiboy-uk explaining the marker syntax + cross-repo sync model

## File-by-file change list (estimate)

| Repo | File | Change | Lines |
|---|---|---|---|
| dotfiles | `SST3/scripts/voice_rules.py` | NEW | ~80 |
| dotfiles | `SST3/scripts/check-ai-writing-tells.py` | EXTEND in place | +60, -30 |
| dotfiles | `SST3/scripts/sync-voice-profile.py` | NEW | ~120 |
| dotfiles | `cv-linkedin/VOICE_PROFILE.md` | Add marker block in Section 8 | +20 |
| dotfiles | `cv-linkedin/MASTER_PROFILE.md` | Add 1-2 region tags | +4 |
| dotfiles | `cv-linkedin/AI_SKILLS_AND_PORTFOLIO.md` | Add region tags | +4 |
| dotfiles | `.pre-commit-config.yaml` | Add sync-check hook | +6 |
| dotfiles | `.github/workflows/validate.yml` | Add voice-tells job | +12 |
| hoiboy-uk | `scripts/voice_rules.py` | NEW (vendored) | ~80 |
| hoiboy-uk | `scripts/check_voice_tells.py` | NEW (vendored + adapted) | ~250 |
| hoiboy-uk | `scripts/sync_voice_rules.py` | NEW | ~60 |
| hoiboy-uk | `.pre-commit-config.yaml` | Add 2 hooks | +14 |
| hoiboy-uk | `.github/workflows/ci.yml` | Add CI step | +4 |
| hoiboy-uk | `CLAUDE.md` | Update voice rule section | +5 |
| hoiboy-uk | `docs/research/11_VOICE_PROFILE.md` | Add marker syntax docs | +20 |
| hoiboy-uk | `docs/research/13_VOICE_GUARD_HOOK.md` | NEW | ~150 |

Total: ~1000 lines added across both repos, ~30 lines deleted.

## Open questions for review

1. **Marker name**: `iamhoi` is what you proposed. Alternatives: `voice`, `hoi-voice`, `voice-on/off`, `iamhoi/iamnothoi`. Stick with `iamhoi`?

2. **Region semantics**: opt-in by default (must wrap in `<!-- iamhoi -->` to scan) OR opt-out by default (scan everything, must wrap in `<!-- iamhoi-skip -->` to exempt)?
   - **Recommended: hybrid** - files in the existing whitelist scan whole-file by default (backward compat), other files scan only tagged regions. New files default to "tag to scan". This means CV/cover letters don't need any tag changes; only mixed files like MASTER_PROFILE need `<!-- iamhoi -->` wrappers to opt sections in.

3. **Cutoff handling in hoiboy-uk**: scan `content/posts/` only for files dated `>= 2026-04-07` (parse frontmatter). Anything older = legacy = exempt. This matches the existing CLAUDE.md cutoff rule.

4. **Vendored vs runtime cross-repo dep**: I chose vendoring with sync-check because (a) dotfiles is private and CI cannot clone it without a deploy key, (b) runtime relative path breaks portability. Acceptable, or do you want to invest in deploy-key cross-repo CI checkout instead?

5. **Severity levels**: should we have HARD FAIL vs WARN tiers? Current script is binary (any tell = exit 1). I propose:
   - HARD FAIL: em dashes, banned words, banned phrases, smart quotes, unicode arrows
   - WARN (prints, doesn't fail): bold-first bullet pattern (already threshold-gated), negation framing, sentence-length uniformity (if we add it)
   - This lets you commit a deliberately stylized cover letter without fighting the script.

6. **Sentence rhythm check**: VOICE_PROFILE.md flags "smooth uniform sentence length" as a top tell. Implementing it = compute mean + stddev, fail if stddev/mean ratio is too low. Risky for short content. **Recommend defer** to a later phase, or implement as WARN-only.

7. **What other repos eventually need this?**: If you're going to use this pattern in more repos in future, vendor + sync gets noisy fast. Consider publishing `voice_rules.py` + `check-ai-writing-tells.py` as an installable package (`pip install hoi-voice-guard`) sourced from the dotfiles SST3-AI-Harness public mirror. **Defer until 3rd repo needs it** - 2 repos doesn't justify the packaging overhead yet.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Vendored copies drift from canonical | Medium | sync-check hook in pre-commit on both repos. Hard-fails on diff. |
| New hook breaks an in-flight commit because of an existing tell in a CV section | High | Phase 1 rollout includes "run pre-commit on every file, fix or tag". Catches all existing tells in one batch. |
| False positives from authentic Hoi words ("passion", "journey") | Low | KEEP_LIST in voice_rules.py overrides. Already tested in current script via 2026-04-07 refinement. |
| Markdown rendering breaks because of `<!-- iamhoi -->` HTML comments | None | HTML comments are stripped by all Markdown renderers. |
| Hugo build slows down because of script call | Negligible | Script is stdlib only, ~200 lines, runs in <100 ms on a single file. |
| Pre-commit ergonomics: dev forgets to wrap a new section | Medium | Hook reminds via output: "no `<!-- iamhoi -->` markers found in $file; treating as exempt. Add markers to enable voice check, or add to whitelist." |
| Sync-check fails on push from another machine | Low | Sync-check is local-only. CI in dotfiles runs the canonical, CI in hoiboy-uk runs the vendored. Drift surfaces at next pre-commit. |

## What this plan does NOT cover

- Dance/blog content style guide (formatting, image rules, link rules) - already in `docs/AUTHORING.md`
- Hugo build optimisation - separate concern
- Spelling / grammar checks - markdownlint and human review handle this
- Adding the Top-10 patterns from VOICE_PROFILE Section 22 ("temptation warnings") - defer to Phase 5 (would need new regex patterns and is scope creep for v1)
- Migration of cover letters into a `cv-linkedin/applications/{Company}/` folder - separate workflow change
- Renaming `check-ai-writing-tells.py` -> `voice_guard.py` - out of scope, name is fine
- Removing the old `check-ai-writing-tells.py` from dotfiles - out of scope, we extend in place

## Alternatives considered and rejected

**A. Build a brand-new script in hoiboy-uk, ignore dotfiles entirely.**
Rejected: duplicates effort, drifts immediately, ignores 208 lines of working code.

**B. Make hoiboy-uk depend on dotfiles at runtime via `../dotfiles/SST3/scripts/...`.**
Rejected: works locally, breaks in GH Actions CI (dotfiles not checked out, private repo, deploy key friction).

**C. Cross-repo CI checkout with deploy key.**
Rejected for v1: setup overhead, secret management, single-point-of-failure on the deploy key. Vendoring is simpler and the sync-check catches drift.

**D. Publish `voice_rules.py` as a pip package.**
Rejected for v1: 2 repos doesn't justify packaging. Reconsider when 3rd repo needs it.

**E. Skip the marker-driven approach, just expand the whitelist.**
Rejected: defeats the original premise. User explicitly wants tagged regions so mixed files (research docs, blog posts with meta, MASTER_PROFILE) work without wholesale exemption.

**F. Use frontmatter `voice: hoi` flag instead of inline markers.**
Rejected: works for whole-file tagging, doesn't work for region-level tagging within mixed files. Markers are strictly more expressive. (Could ALSO support frontmatter as an alias, but inline markers stay primary.)

## Estimated effort

- Phase 1 (dotfiles): 2-3 hours including testing
- Phase 2 (hoiboy-uk vendoring): 1 hour
- Phase 3 (region tags): 30 minutes
- Phase 4 (docs): 30 minutes

Total: half a day. Single solo branch in each repo, atomic commits, CI green check at each phase.

## Next steps

1. **You review this plan**, flag changes
2. I create issues in both repos using `issue-template.md` from SST3 (one issue per repo, cross-linked)
3. Subagent triple-check of each issue scope vs this plan
4. Implementation per phase with Stage 5 review at the end
5. User-review-checklist on each issue before close

---

**Awaiting your review.**
