# Blog Post Authoring

**Audience**: Hoi + Claude Code (AI agent)
**Format**: AI-First. Facts first, tables, no tutorial prose.

## 1. Post anatomy

Every post is a **page bundle**: a folder containing `index.md` plus any images.

```
content/posts/<slug>/
├── index.md      # frontmatter + body
├── header.jpg    # optional cover image
└── photo1.jpg    # any inline images, referenced by relative path
```

Folder name = canonical slug. Date prefix optional but recommended for sort stability:
`content/posts/2026-04-07-foundation/index.md`

## 2. Frontmatter contract

| Field | Required | Type | Rule | Example |
|---|---|---|---|---|
| `title` | yes | string | Quote the whole value if it contains a colon | `title: "Why: a manifesto"` |
| `date` | yes | ISO 8601 | `YYYY-MM-DD` minimum | `date: 2026-04-07` |
| `categories` | yes | list | Must be one of: `food-booze`, `adventure`, `dance`, `tech-ai`, `life`, `entrepreneurship`, `trading` | `categories: [food-booze]` |
| `tags` | yes | list | Lowercase, hyphenated, freeform | `tags: [ramen, tokyo, japan]` |
| `slug` | no | string | Overrides folder name in URL | `slug: best-ramen` |
| `draft` | no | bool | `true` skips production build | `draft: true` |
| `description` | no | string | <=160 chars, used in meta + OG | `description: "Field guide..."` |
| `series` | no | string | Groups posts under `/series/<name>/`. Use `bakeoff` for bake-off posts. Term page sorts by `order` ascending. | `series: bakeoff` |
| `order` | no | integer | 0-100. Position within the series (lower = earlier). 0 reserved for the series teaser/index post. | `order: 0` |

**Validator**: `python3 scripts/validate_frontmatter.py` (also runs in CI and pre-commit). Hard fail on missing required fields, unknown categories, or malformed YAML. Optional fields are not enforced for backward compatibility.

## 3. Image rules

| Rule | Detail |
|---|---|
| Location | Same folder as `index.md` (page bundle) |
| Reference | Relative: `![alt text](photo1.jpg)` not absolute |
| Alt text | Mandatory. Describe content, not "image of..." |
| Format | `.webp` preferred, `.jpg` for photos, `.png` only for screenshots/diagrams |
| Width | Max 1600px on the long edge before commit. Hugo image processing handles responsive sizes |
| Filename | Lowercase, hyphenated, descriptive |

## 4. Heading hierarchy

| Level | Use | Notes |
|---|---|---|
| `#` | RESERVED | Hugo injects from `title:` frontmatter. Never use in body. |
| `##` | Section headings | Body starts here |
| `###` | Sub-sections | |
| `####` | Rare | Question whether the section needs split |
| `#####+` | Forbidden | Restructure |

No skipped levels (`##` then `####`). Markdownlint enforces.

## 5. Voice rules (load-bearing)

| Rule | Source | Enforcement |
|---|---|---|
| Zero em dashes (the U+2014 character, looks like a long dash) | `feedback_no_em_dashes` memory | CI grep guard, hard fail |
| No AI-flagged words for NEW Hoi-voice prose | `VOICE_PROFILE.md` Section 0 | Manual: `python3 ../dotfiles/SST3/scripts/check-ai-writing-tells.py <file>` |
| iamhoi marker wrapping required for new Hoi-voice prose | AP #15 + `feedback_hoiboy_uk_voice_markers.md` | `python3 scripts/check-iamhoi-wrapping.py --check-only-new` (pre-commit hook 6) |
| Legacy imports voice-sacred | `02_BLOG_IMPORT_PIPELINE.md` | Cleanup limited to format/encoding/dead links/image rehost. Words byte-identical to source. |
| British English | UK spelling, no Americanisms | Manual review |
| RAG before writing | Always retrieve from `MASTER_PROFILE.md` / `VOICE_PROFILE.md` Section 9 (anchor anecdotes) and Section 12 (verbatim sentences) before drafting | Skill rule, no auto-enforce |

### 5a. iamhoi marker syntax

Wrap any first-person Hoi-voice prose in `<!-- iamhoi --> ... <!-- iamhoiend -->` so the voice guard scans it. Per-section wrapping is preferred for auditability over whole-file wrapping.

```markdown
## A section in Hoi's voice

<!-- iamhoi -->
First-person prose here. The voice guard scans this region for em dashes,
banned words, smart quotes, and other AI tells.
<!-- iamhoiend -->
```

**Skip a region within a wrapped section** (legitimate uses: quoting external methodology verbatim, quoting a banned word as an example, illustrating an AI tell):

```markdown
<!-- iamhoi -->
This part is scanned.

<!-- iamhoi-skip -->
This part is exempt. Use for verbatim external quotes that legitimately
contain banned words or em dashes.
<!-- iamhoi-skipend -->

This part is scanned again.
<!-- iamhoiend -->
```

**Whole-file bypass** (rare; use only when a file is structurally exempt, e.g. a research doc that quotes banned vocabulary as examples): place `<!-- iamhoi-exempt -->` as the first non-blank line of the file.

The wrapping enforcer (`scripts/check-iamhoi-wrapping.py`) blocks commits where a new post (date >= 2026-04-07) contains first-person prose but no `<!-- iamhoi -->` markers.

## 6. Link rules

| Type | Rule |
|---|---|
| Internal | Relative: `[link](/about/)` or `[link](../other-post/)` |
| External | Absolute, https. Example: `[link](https://example.com)` |
| Lychee CI | All link failures fail CI (no warn-only). Known-flaky external domains added to `lychee.toml` exclude with `added: YYYY-MM-DD; expires: YYYY-MM-DD` comment |
| Dead links | Replace with archive.org snapshot, OR remove with `[former link]` placeholder |

## 7. Drafts

```yaml
---
title: "draft post"
draft: true
---
```

Hugo skips drafts in production builds. Public repo + draft frontmatter = safe (the markdown is visible on GitHub but not on hoiboy.uk). To preview locally: `hugo server --buildDrafts`.

## 8. Publish checklist

- [ ] Frontmatter has all required fields (title, date, categories, tags)
- [ ] Category is one of {food-booze, adventure, dance, tech-ai, life, entrepreneurship, trading}
- [ ] If part of a series: `series: <name>` + `order: <int>` set; `/series/<name>/` index renders correctly under `hugo server`
- [ ] First-person Hoi-voice prose wrapped in `<!-- iamhoi --> ... <!-- iamhoiend -->` (pre-commit hook 6 enforces)
- [ ] Voice tells clean (manual `check-ai-writing-tells.py` for new prose, skip for legacy)
- [ ] Zero em dashes (CI catches it but check locally first)
- [ ] Images in same folder, alt text present, max 1600px wide
- [ ] **Hero image EXIF stripped**: `bash scripts/strip-exif.sh content/posts/<slug>/hero.webp` (manual step before commit; mutates files in-place, so NOT a pre-commit hook)
- [ ] Local preview: `hugo server`, click around the post
- [ ] Headings start at `##`, no skipped levels
- [ ] Internal links resolve, external links live
- [ ] **Pre-publish gate**: `bash scripts/pre-publish.sh content/posts/<slug>/`. Runs em-dash + voice-tells + frontmatter + word-count + secrets in one go (exit 0 = clean to publish)
- [ ] Commit with descriptive message
- [ ] Push, watch CI green, then live in ~90s
