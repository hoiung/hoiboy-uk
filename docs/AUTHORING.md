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
| `date` | yes | ISO 8601 | Use a **full timestamp** `YYYY-MM-DDTHH:MM:SS+01:00` (BST) / `+00:00` (GMT), not a bare date (see ordering note below) | `date: 2026-06-04T13:00:00+01:00` |
| `categories` | yes | list | Must be one of: `food-booze`, `adventure`, `dance`, `tech-ai`, `life`, `entrepreneurship`, `trading` | `categories: [food-booze]` |
| `tags` | yes | list | Lowercase, hyphenated, freeform | `tags: [ramen, tokyo, japan]` |
| `slug` | no | string | Overrides folder name in URL | `slug: best-ramen` |
| `draft` | no | bool | `true` skips production build | `draft: true` |
| `description` | **yes** | string | Used in meta + OG. Its **presence** is gated since 2026-07-20 (blog-priv#55); without one the page inherits the site-default description and ships as a near-duplicate. Write it unique per page and aim for 155-160 chars (the `/blog` skill's Quick Headline Checklist is the single source for that figure), but see the note below: neither is enforced | `description: "Field guide..."` |
| `lastmod` | no | ISO 8601 | Set **explicitly** when a post is genuinely revised. See the note below | `lastmod: 2026-07-20T10:00:00+01:00` |
| `series` | no | string | Groups posts under `/series/<name>/`. Use `bakeoff` for bake-off posts. Term page sorts by `order` ascending. | `series: bakeoff` |
| `order` | no | integer | 0-100. Position within the series (lower = earlier). 0 reserved for the series teaser/index post. | `order: 0` |

**Validator**: `python3 scripts/validate_frontmatter.py` (also runs in CI and pre-commit). Hard fail on missing required fields, unknown categories, or malformed YAML. Remaining optional fields are not enforced for backward compatibility.

The validator walks **both** `content/posts/` and `content/consulting/` (project pages, including `portfolio/<client>/` and section `_index.md`). Project pages carry a smaller required set, `title` + `description` only, because they have no categories/tags taxonomy and several legitimately carry no date. Scope a run with `--scope posts` or `--scope consulting`.

**What the description gate does and does not check.** It checks **presence only**. It does NOT check that a description is unique, and it does NOT check length, so a copy-pasted description or a 300-character one passes every hook. Uniqueness and the length guide are conventions you hold yourself to. Two consequences worth knowing. First, **17 pages inside the gate's scope already exceed 160 characters** (9 posts + 8 consulting), plus 2 more outside it, so 19 across `content/` as a whole. All pre-existing, none a build failure. Second, the walk covers posts and consulting only, so everything else under `content/` is outside it. That is wider than just the 7 category landing pages: `content/community/`, `content/legal/` and `content/skills/` are outside it too. The category landings serve the site-default description by design (see the index/taxonomy carve-out in blog-priv#55). The rest are a different case and are not uniformly compliant: `content/legal/` (4 of 4) and `content/skills/` (1 of 1) carry their own descriptions, but `content/community/_index.md` does not and currently renders the site default. `content/_index.md` and `content/private/` are also outside the gate. Nothing enforces any of this, so a new page added outside `posts/` and `consulting/` can ship a duplicate description and no hook will complain. Write the description yourself and do not expect to be caught.

**`lastmod` (set it by hand, only when the post genuinely changed)**: when you materially revise a published post, add an explicit `lastmod:` timestamp. Hugo exposes it as `.Lastmod` for `article:modified_time` and JSON-LD `dateModified`, so consumers can tell a real revision from an untouched archive post.

Two rules govern it:

1. **`enableGitInfo` is REJECTED** (operator decision, 2026-07-20). It derives `lastmod` from commit time, which means a formatting fix, an encoding repair or an image rehost on a voice-sacred legacy post would broadcast that post as freshly updated. Across a 22-year archive that turns routine maintenance into a wave of false revision dates. Set the field by hand or leave it absent.
2. **Do not set it for cosmetic edits.** A typo fix, a broken-link repair or a frontmatter backfill is not a revision. If the words a reader sees did not meaningfully change, leave `lastmod` alone.

**Honesty note on freshness.** Treat this as record-keeping, not as an optimisation. The freshness lever is **UNVERIFIED**: the 2026-07-19 GEO/AEO evidence brief never evaluates freshness as a citation factor (it mentions the word once, only when summarising this retraction), and the only in-repo text that framed it as a GEO factor was the doc 16 sentence retracted under blog-priv#55 Phase 3. Accurate revision dates are worth having on their own terms. Do not claim the field lifts AI citation or search ranking, because nothing we have supports that.

**`date` and the production build (don't future-date)**: Hugo silently drops **future-dated** posts from the production build (`buildFuture` is off), the same way `draft: true` does (§7). The trap is timezone: the site is configured `timeZone = "Europe/London"` in `hugo.toml`, but Cloudflare builds in **UTC**. A post dated `YYYY-MM-DD` (midnight) published in the small hours of UK time can still be "the future" in UTC. The London `timeZone` setting makes a bare date resolve to UK midnight (e.g. `2026-06-04` = `23:00Z` on the 3rd) so a same-day UK publish builds correctly, but do not date a post **ahead** of the day you actually publish, or Cloudflare will build the site without it (it vanishes from its URL and every category/section listing while a stale copy may still appear to serve). Symptom + fix history: the 3-types-of-tests post, 2026-06-04. Never remove the `timeZone` line from `hugo.toml`.

**`date` and listing order (always stamp a time)**: Hugo sorts listings by date descending; when two posts share the same **calendar day** with a bare `YYYY-MM-DD` (which resolves to 00:00), the dates tie and Hugo falls back to an arbitrary tiebreak (title / file path), so a newer post can render **below** an older one. Fix: give every post a **full timestamp** with a real time component, so same-day posts have a strictly later instant and the newest sorts on top. The site renders date-only everywhere a reader sees it (`single.html` = `"2 January 2006"`, listings = `"2 Jan"`), so the time is invisible on the page; it only sharpens `article:published_time` / JSON-LD `datePublished` (a plus). When publishing a second post on a day that already has one, set its time later than the existing post's. Use the correct London offset for the date: `+01:00` during BST (late Mar to late Oct), `+00:00` during GMT. All existing posts were backfilled to timestamps on 2026-06-04 (order-preserving). Symptom: the observability post landing below 3-types-of-tests, 2026-06-04.

## 3. Image rules

| Rule | Detail |
|---|---|
| Location | Same folder as `index.md` (page bundle) |
| Reference | Relative: `![alt text](photo1.jpg)` not absolute |
| Alt text | Mandatory. Describe content, not "image of..." |
| Format | `.webp` preferred, `.jpg` for photos, `.png` only for screenshots/diagrams |
| Width | Max 1600px on the long edge before commit. Hugo image processing handles responsive sizes |
| Filename | Lowercase, hyphenated, descriptive |

### 3a. Reusing a house diagram across posts

The harness family shares two house diagrams instead of re-drawing the same idea in every post:

- `cones.svg` shows what a harness DOES. Home post: `/posts/why-do-we-need-an-ai-harness/`.
- `harness-layers.svg` shows what a harness IS. Home post: `/consulting/claude-code-harness-architect/`.

To reuse one in another post, reference its home-post URL (mechanic (b)) instead of copying the file into the new page bundle:

```text
{{< zoom-image src="/posts/why-do-we-need-an-ai-harness/cones.svg" alt="accurate description of the image" title="short caption tailored to THIS post" >}}
```

- **No copy.** One physical file per diagram lives in its home bundle; every reuse points at that published URL. Do not copy the SVG into the consuming bundle, because copies drift out of sync.
- **Alt stays accurate to the image.** The `alt` may be identical across reuses (correct, since the image is identical). Only the visible `title` caption varies per post. Keep captions voice-clean: no em dash, no `voice_rules.py` banned words.
- **Redundancy trap.** Do not place a diagram right next to prose that already restates it word for word. Put it where the argument is made in words but the reader gets no visual. A nearby paraphrase is fine; a verbatim restatement is not.
- **Recurrence ceiling.** Reuse `cones.svg` in at most 4 posts and `harness-layers.svg` in at most 4. The core explainers carry BOTH diagrams: `sst3-ai-harness-reshapeable-knife` and `every-sme-needs-their-own-harness` (both as reuses), plus `why-do-we-need-an-ai-harness` (its native `cones.svg` alongside a reused `harness-layers.svg` where it defines what a harness is). Every other post carries at most one.
- **Rename caveat.** The reuse URL couples to the home post's slug. If either home post (`why-do-we-need-an-ai-harness` or `claude-code-harness-architect`) is renamed or moved, the reuse refs 404 with no CI catch: lychee excludes `content/posts` and `public/posts`, and the `zoom-image` shortcode passes `src` through raw with no resource check. So grep every reuse ref for the old path and fix them all in the same commit:

```text
grep -rlE 'src="/posts/why-do-we-need-an-ai-harness/cones\.svg"' content/
grep -rlE 'src="/consulting/claude-code-harness-architect/harness-layers\.svg"' content/
```

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
| iamhoi marker wrapping required for new Hoi-voice prose | AP #15 + `feedback_hoiboy_uk_voice_markers.md` | `python3 scripts/check-iamhoi-wrapping.py --check-only-new` (pre-commit hook 4) |
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

## 6a. Internal links: section landings list, posts host

Posts live at `/posts/<slug>/` regardless of category. Section landings (`/dance/`, `/food-booze/`, `/tech-ai/`, `/life/`, `/entrepreneurship/`, `/trading/`, `/adventure/`) are auto-generated index pages from Hugo's category taxonomy. They LIST the posts in that category. They DO NOT HOST individual posts.

A link like `/dance/some-post/` is broken even though it looks plausible. The post is at `/posts/some-post/`; `/dance/` is the category landing where Hugo lists all dance posts. Cloudflare's fallback silently routes 404s to the homepage, so the bug surfaces as "click goes to homepage".

| Form | Routes to |
|---|---|
| `/posts/some-post/` | `content/posts/some-post/index.md` (the post) |
| `/dance/` | `content/dance/_index.md` (auto-generated category landing) |
| `/dance/some-post/` | Cloudflare fallback returns the homepage HTML (HTTP 200, but no real page, the bug class) |

Worked example. Cross-linking another post:

```markdown
[the 2016 London rant](/posts/how-to-avoid-becoming-a-terrible-dancer-in-london/) still holds up.
```

NOT:

```markdown
[the 2016 London rant](/dance/how-to-avoid-becoming-a-terrible-dancer-in-london/) ← broken, do not use
```

The `scripts/validate_internal_links.py` pre-commit hook + CI step rejects the broken form with an actionable hint (`did you mean /posts/<slug>/?`). Run it manually any time: `python3 scripts/validate_internal_links.py`.

## 7. Drafts

```yaml
---
title: "draft post"
draft: true
---
```

Hugo skips drafts in production builds. Public repo + draft frontmatter = safe (the markdown is visible on GitHub but not on hoiboy.uk). To preview locally: `hugo server --buildDrafts`.

## 8. Publish checklist

- [ ] Frontmatter has all required fields (title, date, categories, tags, description)
- [ ] Category is one of {food-booze, adventure, dance, tech-ai, life, entrepreneurship, trading}
- [ ] If part of a series: `series: <name>` + `order: <int>` set; `/series/<name>/` index renders correctly under `hugo server`
- [ ] First-person Hoi-voice prose wrapped in `<!-- iamhoi --> ... <!-- iamhoiend -->` (pre-commit hook 4 enforces)
- [ ] Voice tells clean (manual `check-ai-writing-tells.py` for new prose, skip for legacy)
- [ ] Zero em dashes (CI catches it but check locally first)
- [ ] Images in same folder, alt text present, max 1600px wide
- [ ] **Hero image EXIF stripped**: `bash scripts/strip-exif.sh content/posts/<slug>/hero.webp` (manual step before commit; mutates files in-place, so NOT a pre-commit hook). Detection IS auto-enforced: the read-only `scripts/check-exif.py` runs in pre-commit + CI and fails on identifying EXIF (camera Make/Model/serial/Artist/GPS).
- [ ] Local preview: `hugo server`, click around the post
- [ ] Headings start at `##`, no skipped levels
- [ ] Internal links resolve, external links live
- [ ] **Pre-publish gate**: `bash scripts/pre-publish.sh content/posts/<slug>/`. Runs all 14 gates (consulting-yaml, em-dash, voice-tells, frontmatter, frontmatter-project-pages, social-cards, no-future-date, wordcount, secrets, svg-dimensions, hugo-build, social-cards-rendered, rendered-link-liveness, consulting-link-liveness) in one go (exit 0 = clean to publish). The rendered-HTML lychee (`rendered-link-liveness`) and `consulting-link-liveness` checks are **manual-only, NOT CI-enforced**: they need a full local `hugo --buildDrafts` build plus live external-URL probing, so they stay in this manual pre-publish step. CI runs the markdown-level lychee (`./**/*.md`) as the automated link tier; nothing elsewhere claims these two rendered checks are CI-enforced.

  **Neither link tier checks a post.** `lychee.toml` `exclude_path` contains **both** `public/posts` and `content/posts`, so for a post target the rendered tier and the CI markdown tier each report `0 Total` and pass without checking anything. Measured: a post returns 0 links on both tiers, a consulting page returns 37 on the rendered tier. The exclusions are deliberate and predate blog-priv#55, so **the links in a new post must be checked by hand** before you publish. Do not read a green pre-publish run as evidence that a post's links resolve. Same caveat, same wording, in the `CAVEAT:` paragraph of the gate-8 entry in `scripts/pre-publish.sh`'s header block.
- [ ] Commit with descriptive message
- [ ] Push, watch CI green, then live in ~90s
