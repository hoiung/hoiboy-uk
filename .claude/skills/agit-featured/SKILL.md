---
name: agit-featured
description: Publish an Asians & Gingers in Tech (AGIT) community feature from a submission, written in Hoi's voice, in the house format. Use when Hoi pastes a submission email (name / role / superpowers / story + optional photo) and wants a feature page for hoiboy.uk plus a short social version and the shareable link.
---

# /agit-featured

Turn one AGIT submission into a published feature. The point of the series is to shine a light on the quiet, heads-down people doing brilliant work. Hoi is telling their story for them, so it is written in **his** voice, not a neutral bio.

Run from the `hoiboy-uk` repo root. Content changes go through the repo's normal branch + deploy flow.

## Input (what Hoi pastes)

The submission email from the form (`functions/api/contribute.js`). You can rely on exactly these fields, nothing else:

- **Name:** name and alias, e.g. "Hoi aka Hoiboy"
- **Email:** (do not publish it)
- **Tech role:** may be "(not given)"
- **Superpowers:** may be "(not given)"
- **Feature / story:** the free-text story
- an optional **photo** attached to the email

If a field is "(not given)", flex around it. Never invent facts the person did not give you. If the story is thin, ask Hoi for more before drafting rather than padding it.

## Voice (mandatory)

Before drafting, load the voice: run `/voice blog` (closest register) and RAG `docs/research/11_VOICE_PROFILE.md`, `docs/research/12_AI_WRITING_TELLS.md`, and `../dotfiles/voice/base/VOICE_PROFILE.md`. Plain simple English. Keep any profanity verbatim. Name Claude before ChatGPT if models come up. No em dashes (CI hard fail).

You are writing AS Hoi about someone he is featuring: warm, direct, a bit self-effacing on their behalf, no hype, no corporate "spotlight" tone.

## House format (mirror Hoi's own feature)

Read `content/community/agit-featured/hoi-aka-hoiboy-ai-product-engineer/index.md` for the live template. Same bold-label skeleton, **flexed per person** (drop a section if there is nothing real to put there, do not force all eight):

- Opening paragraph: one or two lines of context. Do NOT repeat the person's name in bold at the start (the page `<h1>` already shows it).
- `**Superpowers:**` short, punchy traits or quirks (not a skills list).
- `**Current role:**` one short line, the person's current role or title in tech (the same value as the `role` frontmatter that drives the index card). Placed right after Superpowers.
- `**What I quietly did:**` the concrete, uncredited work; close on a line tying back to the quiet ones.
- `**The identity bit:**` who they are outside the CV.
- `**The flex, nothing to do with tech:**` a non-tech achievement as a mini narrative (the label can carry a person-specific qualifier).
- `**Tech tip:**` one opinionated, practical tip.
- `**Life tip:**` one opinionated, practical tip, broader.
- `**To anyone reading who never puts their hand up:**` direct address to the reader, closing invite in the group's language.

Wrap the whole feature body in `<!-- iamhoi -->` ... `<!-- iamhoiend -->`.

## Publish the page

Create a leaf bundle `content/community/agit-featured/<slug>/`:

- **slug** = `<name>-<role>`, urlized (e.g. "Jane Smith" + "Data Engineer" -> `jane-smith-data-engineer`). Role is in the slug so two people with the same name stay distinct.
- **index.md** frontmatter:
  ```yaml
  ---
  title: "<Name aka Alias>"
  date: <NOT a future timestamp>   # see gotcha below
  description: "<=160 chars, one line, for the share card / meta"
  role: "<Tech role>"              # shown on the index card
  breadcrumbParent: "/community/agit-featured"
  hideDate: true
  ---
  ```
- **Feature images (branded pair)**: do NOT hand-save `hero.<ext>`. The generator produces both images from one source photo:
  1. Save the submitted photo (EXIF-stripped) to `scripts/social-cards/agit-sources/<slug>.<ext>` (any orientation is fine, the generator handles it): `python3 -c "from PIL import Image,ImageOps; ImageOps.exif_transpose(Image.open('<submitted-photo>')).convert('RGB').save('scripts/social-cards/agit-sources/<slug>.jpg',quality=95)"`
  2. Add a row to `scripts/social-cards/agit-features.tsv` (tab-separated): `<slug><TAB><Name aka Alias><TAB><Tech role>` (leave the role field empty if "(not given)").
  3. Run `python3 scripts/social-cards/gen_agit_feature.py <slug>` (needs `rsvg-convert` + Pillow). It writes two images into the bundle: `hero.jpg` (portrait 4:5, AGIT logo watermark, EXIF-stripped: the section INDEX card + the person's direct-social image) and `share-card.png` (branded landscape 1200x630: photo inset + name + role + AGIT branding, AGIT logo watermark: the feature-page HERO + the og:image link-preview).
  **Image placement (final design, commit 3b8bb2a, do not regress):** on an agit-featured feature page the on-page HERO is the landscape `share-card.png` (chosen by `hero-pick.html`), and `head.html` uses that same `share-card.png` as the og:image. The section index at `/community/agit-featured/` uses the portrait `hero.jpg` as its card (`list.html` pins the card image to `hero.*`, NOT `hero-pick`). So do NOT add an inline `<img>` in the markdown, and do NOT tell the submitter which orientation to send (any photo is fine, the share card insets it). Run the generator with no slug argument to regenerate every feature's pair after a design change.

**Date gotcha:** `hugo -e production` drops future-dated pages (`buildFuture: false`), so the page silently will not appear if `date` is even a few hours ahead of the deploy build clock. Use today's date at a time already passed, or the previous day. The date only orders the index (it is hidden on the page).

## Guard floor (must pass before publish)

- `python3 scripts/check-ai-writing-tells.py --check-only-new content/community/agit-featured/<slug>/index.md` exits 0.
- `bash scripts/check_emdash_zero_tolerance.sh` exits 0 (zero em dashes).
- `python3 scripts/check-exif.py scripts/social-cards/agit-sources/<slug>.<ext>` exits 0 (the source photo carries no camera/GPS EXIF before it enters the public repo).
- The bundle has both generated images: `hero.jpg` (1080x1350) and `share-card.png` (1200x630).
- Eyeball both images: the circular AGIT logo watermark is visible bottom-right on each, name and role are fully inside the panel (not clipped or colliding with the logo).
- `hugo --gc --minify -e production` builds clean and the page appears in `public/community/agit-featured/<slug>/`.

## Design spec (frozen; do not redesign without operator sign-off)

The card look is defined by `scripts/social-cards/gen_agit_feature.py` and documented in `docs/research/07_DESIGN_TOKENS.md` (section "AGIT feature-image tokens"). In short: name in **VT323** up to 80px, role in **IBM Plex Mono** up to 28px, eyebrow 18px; navy `#0c1c2d`, orange `#da611c`, grey `#4f5b64`, panel gradient `#b5dae7` to `#f9ebdf`; circular AGIT logo watermark bottom-right (92px on the share-card, 20% of width on the hero). `hero.jpg` is portrait 4:5 (1080x1350), `share-card.png` is landscape 1200x630. To tweak sizing or fonts, edit those constants and regenerate the pair; never hand-edit the images.

## The three outputs

Give Hoi all three:

1. **The feature page** (published as above). The traffic driver.
2. **A short social version**: a tight, punchy cut of the story in Hoi's voice, short enough to paste directly into a LinkedIn / Instagram / TikTok post body (aim ~100 to 150 words; no links in the body). This is what he posts.
3. **The canonical link** `https://hoiboy.uk/community/agit-featured/<slug>/`, for Hoi to drop as the **first comment** on the social post and to quote as the source, so the in-body-link penalty (LinkedIn) is avoided while still driving traffic to the site.

## Deploy

Content changes: commit the page bundle by explicit path and follow the repo's deploy flow (push to main -> CI -> Cloudflare deploy). Confirm the live URL returns 200 before telling Hoi it is up.
