# Blog Import Pipeline

**Date**: 2026-04-07
**Goal**: Import ~22 years of legacy posts from various platforms into Hugo page bundles. Voice preserved verbatim. Cleanup limited to formatting, encoding, broken markdown, dead links, image rehosting.

## Platform Exports

| Platform | Export method | Best tool | Notes |
|---|---|---|---|
| **WordPress** | Tools > Export (WXR XML) | `npx wordpress-export-to-markdown` | Gold standard. Frontmatter, slugs, downloads images, dates/categories/tags. |
| **Blogger** | Settings > Manage Blog > Back up content (Atom XML) | `blog2md` (npm) | Or convert to WXR via `google-blog-converters` then pipe through wordpress-export-to-markdown |
| **Medium** | Settings > Account > Download your information (.zip) | `medium-2-md` | Medium HTML is messy — post-process needed |
| **Tumblr** | API | `tumblr-utils` (`tumblr_backup.py`) | Downloads posts as JSON/HTML plus all media |
| **Dead/archived sites** | n/a | `wayback-machine-downloader` (Ruby gem) | Then `wget --mirror --convert-links --page-requisites` for offline copies |

## HTML → Markdown Conversion

**Pandoc is the winner** for blog content — best table/footnote/blockquote handling:

```bash
pandoc -f html -t gfm-raw_html --wrap=none input.html -o output.md
```

`gfm` = GitHub-flavoured markdown. `-raw_html` strips leftover `<div>` junk.

Alternatives:
- `turndown` (JS): good for browser/Node pipelines, easier to customise per-element rules (e.g. Medium figure captions)
- `html2text` (Python): weaker — mangles nested lists. Avoid.

## Frontmatter Normalisation

Target Hugo frontmatter:

```yaml
---
title: "..."
date: 2008-05-14
tags: [python, blogging]
slug: original-slug
draft: false
---
```

- Keep original slug to preserve URLs (add Cloudflare redirects if old URLs differ)
- Dates in ISO 8601
- Categories collapsed into tags (Diehl-style — tags only)

`wordpress-export-to-markdown` emits this automatically. For others, parse the source XML/JSON and write frontmatter via a Python post-processor (`python-frontmatter` lib).

## Image Handling

- Download all `![](http...)` images locally into the post's bundle folder: `content/posts/<slug>/`
- Rewrite links to relative paths
- Avoids dead hotlinks forever
- Tools: `wordpress-export-to-markdown --save-images=true` does this; for others, 20 lines of Python with `markdown-it-py` + `requests`

## Broken Link / Dead Embed Detection

- **`lychee`** (Rust) — fastest markdown/HTML link checker
  - `lychee --offline ./content` for offline check
  - `lychee ./content` for live check
- For dead links: query `archive.org` Wayback Availability API, swap in snapshot URLs
- Strip/flag dead YouTube/Twitter embeds with a regex pass

## Encoding Fixes

- `ftfy` (Python) — fixes mojibake (`â€™` → `'`, etc) common in old WordPress exports
- Run as a single pass over all imported markdown after conversion

## Claude Code Workflow

```
hoiboy-uk/
├── legacy/                       # Raw exports (gitignored)
│   ├── wordpress/export.xml
│   ├── blogger/blog.xml
│   ├── medium/posts/
│   └── tumblr/*.json
├── scripts/
│   ├── import.sh                 # Orchestrator: runs each converter
│   ├── normalise_frontmatter.py  # YAML cleanup, tag collapse
│   ├── download_images.py        # Rehost remote images locally
│   ├── fix_encoding.py           # ftfy pass
│   └── check_links.sh            # lychee runner
└── content/posts/<slug>/index.md
```

Flow:
1. User dumps raw exports into `legacy/`
2. `scripts/import.sh` runs each converter into `content/posts/`
3. Python post-processor normalises frontmatter
4. Image downloader rehosts everything
5. `ftfy` pass fixes encoding
6. `lychee` checks all links, flags broken ones
7. Claude reviews the output, fixes structural issues, **never touches the prose**
8. Commit in batches (e.g. one commit per year of posts)

## Voice preservation rule

This is the non-negotiable. The whole point of republishing 22 years is the corpus is already Hoi's voice. Editing it would defeat the purpose. Cleanup is limited to:

- Markdown structure (headings, lists, links)
- Encoding artefacts
- Dead links and broken embeds
- Image rehosting

The actual words stay byte-identical to the source.
