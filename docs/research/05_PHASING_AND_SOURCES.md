# Phasing and Content Sources

**Date**: 2026-04-07

## Sources confirmed by Hoi

1. **WordPress backup** (largest, primary source)
2. **Scattered HTML files** saved locally over the years
3. **Google Docs and .docx files**

No Blogger / Medium / Tumblr to worry about. Phased import.

## Phase 0 — Foundation (next session)

Goal: live "Hello world" on hoiboy.uk before any content lands.

- [ ] Install Hugo extended on WSL (`sudo apt install hugo` or download binary)
- [ ] Pick theme — recommended start: `risotto` (closest to Diehl aesthetic)
- [ ] Add theme as git submodule under `themes/`
- [ ] Write `config.toml`: site title, baseURL `https://hoiboy.uk`, sidebar nav, tag taxonomy
- [ ] Local preview works (`hugo server`)
- [ ] Connect Cloudflare Pages → `hoiung/hoiboy-uk` repo
- [ ] Attach custom domain `hoiboy.uk` (one click — Cloudflare registrar)
- [ ] Verify live deploy
- [ ] One placeholder post to confirm the loop works end-to-end

## Phase 1 — WordPress wave

Source: WordPress backup XML (WXR format).

- [ ] Drop XML in `legacy/wordpress/` (gitignored)
- [ ] `scripts/import_wordpress.sh` runs `npx wordpress-export-to-markdown --input=legacy/wordpress/export.xml --output=content/posts --save-images=true`
- [ ] Restructure into page bundles (each post = folder with `index.md` + images)
- [ ] `scripts/normalise_frontmatter.py` — collapse categories into tags, add `slug`, ensure `date` ISO 8601
- [ ] `scripts/fix_encoding.py` — ftfy pass for mojibake
- [ ] `lychee` link check, log dead links to `docs/research/dead-links-wave1.md`
- [ ] Commit in batches by year (`git commit -m "Import WordPress posts: 2008"`)
- [ ] User review pass — Hoi confirms voice intact

## Phase 2 — HTML scraps wave

Source: scattered local HTML files.

- [ ] Drop in `legacy/html/`
- [ ] `scripts/import_html.sh` walks directory, runs `pandoc -f html -t gfm-raw_html --wrap=none` per file
- [ ] Date detection chain: filename pattern → `<meta>` tags → `<time>` element → file mtime → manual flag
- [ ] Slug from filename
- [ ] Same encoding + link-check passes
- [ ] Commit in batches

## Phase 3 — Google Docs / .docx wave

Source: Google Docs (exported as .docx) and existing .docx files.

- [ ] Export Google Docs as .docx into `legacy/docx/`
- [ ] `scripts/import_docx.sh` runs `pandoc -f docx -t gfm --extract-media=content/posts/<slug>/`
- [ ] Pandoc handles inline images automatically via `--extract-media`
- [ ] Manual date assignment (Google Docs metadata is unreliable)
- [ ] Manual review for any Google-specific embeds (links to other Docs, comments)
- [ ] Commit per doc or per topic batch

## Cross-wave guarantees

- **Voice**: prose byte-identical to source. Cleanup limited to structure, encoding, dead links, image rehosting.
- **URLs**: keep original slugs where known. Cloudflare Pages redirect rules handle any URL changes.
- **Idempotency**: every import script can be re-run without duplicating posts (skip if `index.md` exists).
- **Rollback**: each wave is its own set of commits. `git revert` works at the batch level.
