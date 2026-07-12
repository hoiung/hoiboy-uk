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

Read `content/community/agit-featured/hoi-aka-hoiboy-ai-engineer/index.md` for the live template. Same bold-label skeleton, **flexed per person** (drop a section if there is nothing real to put there, do not force all eight):

- Opening paragraph: one or two lines of context. Do NOT repeat the person's name in bold at the start (the page `<h1>` already shows it).
- `**Superpowers:**` short, punchy traits or quirks (not a skills list).
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
- **hero.jpg** (or hero.png): save the submitted photo into the bundle as `hero.<ext>`, then `bash scripts/strip-exif.sh content/community/agit-featured/<slug>/hero.<ext>`. `single.html` renders it at the top automatically, so do NOT add an inline `<img>` in the markdown. The index card crops it to 4:5 portrait, so prefer a portrait-friendly frame; a wide landscape shot gets centre-cropped on the card.

**Date gotcha:** `hugo -e production` drops future-dated pages (`buildFuture: false`), so the page silently will not appear if `date` is even a few hours ahead of the deploy build clock. Use today's date at a time already passed, or the previous day. The date only orders the index (it is hidden on the page).

## Guard floor (must pass before publish)

- `python3 scripts/check-ai-writing-tells.py --check-only-new content/community/agit-featured/<slug>/index.md` exits 0.
- `bash scripts/check_emdash_zero_tolerance.sh` exits 0 (zero em dashes).
- `hugo --gc --minify -e production` builds clean and the page appears in `public/community/agit-featured/<slug>/`.

## The three outputs

Give Hoi all three:

1. **The feature page** (published as above). The traffic driver.
2. **A short social version**: a tight, punchy cut of the story in Hoi's voice, short enough to paste directly into a LinkedIn / Instagram / TikTok post body (aim ~100 to 150 words; no links in the body). This is what he posts.
3. **The canonical link** `https://hoiboy.uk/community/agit-featured/<slug>/`, for Hoi to drop as the **first comment** on the social post and to quote as the source, so the in-body-link penalty (LinkedIn) is avoided while still driving traffic to the site.

## Deploy

Content changes: commit the page bundle by explicit path and follow the repo's deploy flow (push to main -> CI -> Cloudflare deploy). Confirm the live URL returns 200 before telling Hoi it is up.
