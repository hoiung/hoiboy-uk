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
| `categories` | yes | list | Must be one of: `food`, `adventure`, `dance`, `tech` | `categories: [food]` |
| `tags` | yes | list | Lowercase, hyphenated, freeform | `tags: [ramen, tokyo, japan]` |
| `slug` | no | string | Overrides folder name in URL | `slug: best-ramen` |
| `draft` | no | bool | `true` skips production build | `draft: true` |
| `description` | no | string | <=160 chars, used in meta + OG | `description: "Field guide..."` |

**Validator**: `python3 scripts/validate_frontmatter.py` (also runs in CI and pre-commit). Hard fail on missing required fields, unknown categories, or malformed YAML.

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
| Legacy imports voice-sacred | `02_BLOG_IMPORT_PIPELINE.md` | Cleanup limited to format/encoding/dead links/image rehost. Words byte-identical to source. |
| British English | UK spelling, no Americanisms | Manual review |
| RAG before writing | Always retrieve from `MASTER_PROFILE.md` / `VOICE_PROFILE.md` Section 9 (anchor anecdotes) and Section 12 (verbatim sentences) before drafting | Skill rule, no auto-enforce |

## 6. Link rules

| Type | Rule |
|---|---|
| Internal | Relative: `[link](/about/)` or `[link](../other-post/)` |
| External | Absolute, https | `[link](https://example.com)` |
| Lychee CI | All link failures = CI fail (no warn-only). Known-flaky external domains added to `lychee.toml` exclude with `# added: YYYY-MM-DD; expires: YYYY-MM-DD (90 days)` comment |
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
- [ ] Category is one of {food, adventure, dance, tech}
- [ ] Voice tells clean (manual `check-ai-writing-tells.py` for new prose, skip for legacy)
- [ ] Zero em dashes (CI catches it but check locally first)
- [ ] Images in same folder, alt text present, max 1600px wide
- [ ] Local preview: `hugo server`, click around the post
- [ ] Headings start at `##`, no skipped levels
- [ ] Internal links resolve, external links live
- [ ] Commit with descriptive message
- [ ] Push, watch CI green, then live in ~90s
