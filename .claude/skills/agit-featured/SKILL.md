---
name: agit-featured
description: Publish an Asians & Gingers in Tech (AGIT) community feature from a submission, kept in the member's own voice (form-only clarity edits, not Hoi's persona), in the house format. Use when Hoi pastes a submission email (name / role / superpowers / story + optional photo) and wants a feature page for hoiboy.uk plus a short social version and the shareable link.
---

# /agit-featured

Turn one AGIT submission into a published feature. The point of the series is to shine a light on the quiet, heads-down people doing brilliant work. The feature stays in the **member's own voice**: their story, their words, lightly edited for clarity only, never rewritten into Hoi's persona or a neutral corporate bio. (Hoi's own feature is the one exception, since it is Hoi writing about himself.)

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

## Voice: the member's own, edited for form only (mandatory)

A member feature is the member's story in the **member's own voice**. You are an editor, not a ghostwriter. Edit for **form only** (grammar, spelling, structure, flow, length) and never for facts, claims, or meaning:

- **Do**: fix grammar and spelling, tidy structure and flow, trim length, remove em dashes (CI hard fail).
- **Do NOT**: rewrite into Hoi's voice or any house persona; add facts, names, numbers, or dates the member did not give; sharpen an opinion into an accusation; or drop the member's hedges ("I felt", "I think", "in my experience") that keep a subjective statement subjective.
- Keep the member's own phrasing and any profanity verbatim. If a clarity edit would change the meaning, do not make it: ask Hoi.
- **Do NOT wrap a member feature in `<!-- iamhoi -->`.** That marker is Hoi's voice persona; a member feature is not in Hoi's voice, so the voice guard (`check-ai-writing-tells`) correctly skips it.
- **Escalate, do not decide.** If the story makes an allegation about an identifiable person or company (negative, critical, or reputation-affecting), stop and flag it to Hoi. Name people only where the account is positive and the author has permission (see the legal-safety gate); otherwise use a role or anonymise.

The one exception is **Hoi's own feature** (`hoi-aka-hoiboy-...`): that is Hoi writing about himself, so it IS in Hoi's voice and IS `<!-- iamhoi -->`-wrapped. For that one only, load the voice first: run `/voice blog` (closest register) and RAG `docs/research/11_VOICE_PROFILE.md`, `docs/research/12_AI_WRITING_TELLS.md`, and `../dotfiles/voice/base/VOICE_PROFILE.md`. Plain simple English, name Claude before ChatGPT if models come up. Every other feature stays in the member's voice.

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

Wrap the feature body in `<!-- iamhoi -->` ... `<!-- iamhoiend -->` **only for Hoi's own feature** (it is in Hoi's voice). A **member** feature is in the member's own voice, so it is NOT wrapped, and the voice guard skips it (see the Voice section above).

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

## Legal-safety gate (member features, must pass before publish)

A member feature names real people and companies, and AGIT edits it before
publishing, so HOIBOY AI LTD is the publisher, not a neutral host. It goes
through the legal pipeline before it can go live (full rationale:
`/legal/agit-story-guidelines/` and issue #48):

1. **Save the member's original story verbatim, then run the edit-check.** Write
   the raw submitted story and the form-edited version to two text files:

   ```bash
   python3 scripts/check-agit-feature-edit.py \
     --original <original.txt> --edited <edited.txt> \
     --slug <slug> --record-dir <record-dir-OUTSIDE-the-public-repo>
   ```

   It stores the original verbatim as the legal record and FLAGS anything that
   looks like an added fact (a name / number / date in the edited version but not
   the original), a removed hedge, a stray em dash, or a big length change. Read
   every flag. If a flag is a real added fact, fix the edit (form only) and
   re-run. It flags candidates; you decide. Records hold PII, so keep
   `--record-dir` gitignored (`.agit-records/`) or outside the repo entirely.

2. **Clear every named person.** Run the publish gate:

   ```bash
   python3 scripts/check-agit-publish-gate.py --record <record-dir>/<slug>
   ```

   The first run writes a `clearance.json` listing every person named in the
   edited feature. For each name, set `status` to either `permissioned` (with a
   `note` recording the author's warranty that they have that person's
   permission) or `anonymised` (and actually change the feature to a role, then
   re-run the edit-check). Set `flags_cleared: true` once you have reviewed the
   edit-check flags. The gate exits non-zero until every name is cleared. No name
   goes live on a maybe.

3. **Diff before done.** Read `diff.txt` in the record (original vs edited) and
   confirm the edit changed form, not facts, before you publish.

4. **Get the member's emailed approval of the EXACT final wording, then confirm
   it.** Send the exact edited wording and record their reply:

   ```bash
   python3 scripts/agit_approval.py send --record <record-dir>/<slug> \
     --to <member-email> --title "<feature title>" \
     --wording-file <edited.txt> --slug <slug>
   # after they reply on that thread:
   python3 scripts/agit_approval.py poll --record <record-dir>/<slug> \
     --thread-id <thread-id> --member-email <member-email>
   ```

   The gate then requires `approval.json` with `approved: true` bound to the exact
   current wording (a later re-edit voids it). The approval detector is a
   CONSERVATIVE heuristic: it records `approved: true` only on a clean, unambiguous
   yes and fails safe on anything nuanced. It is a first pass, NOT the last word:
   open `approval.json`, READ the recorded `reply_text` AND every entry in
   `later_replies` (anything the member said after their decision), and confirm the
   member actually, unconditionally approved THIS wording before you publish. The
   publish gate prints a `[!]` line if there are later replies. If any reply is
   conditional, hedged, a question, or asks for a change, treat it as not approved
   and follow up (re-editing re-binds the wording hash and forces a fresh approval).
   (Live Gmail is an operator-runtime OAuth grant: `docs/gmail-approval-oauth-setup.md`.)

The publish gate is a HARD gate: if it exits non-zero, do NOT publish. No emailed
approval bound to the current wording on file, no publish. Ever.

## Guard floor (must pass before publish)

- The legal-safety gate above passes: `python3 scripts/check-agit-publish-gate.py --record <record-dir>/<slug>` exits 0 (every named person permissioned-or-anonymised, edit-check flags reviewed).
- `python3 scripts/check-ai-writing-tells.py --check-only-new content/community/agit-featured/<slug>/index.md` exits 0. (A member feature is not `iamhoi`-wrapped, so this skips it and passes; it only bites on Hoi's own feature.)
- `bash scripts/check_emdash_zero_tolerance.sh` exits 0 (zero em dashes).
- `python3 scripts/check-exif.py scripts/social-cards/agit-sources/<slug>.<ext>` exits 0 (the source photo carries no camera/GPS EXIF before it enters the public repo).
- The bundle has both generated images: `hero.jpg` (1080x1350) and `share-card.png` (1200x630).
- Eyeball both images: the circular AGIT logo watermark is visible bottom-right on each, name and role are fully inside the panel (not clipped or colliding with the logo).
- `hugo --gc --minify -e production` builds clean and the page appears in `public/community/agit-featured/<slug>/`.

## Design spec (frozen; do not redesign without operator sign-off)

The card look is defined by `scripts/social-cards/gen_agit_feature.py` and documented in `docs/research/07_DESIGN_TOKENS.md` (section "AGIT feature-image tokens"). In short: name in **VT323** up to 80px, role in **IBM Plex Mono** up to 28px, eyebrow 18px; navy `#0c1c2d`, orange `#da611c`, grey `#4f5b64`, panel gradient `#b5dae7` to `#f9ebdf`; circular AGIT logo watermark bottom-right (92px on the share-card, 20% of width on the hero). `hero.jpg` is portrait 4:5 (1080x1350), `share-card.png` is landscape 1200x630. To tweak sizing or fonts, edit those constants and regenerate the pair; never hand-edit the images.

## The outputs

Two things ship with each feature:

1. **The feature page** (published as above), at `https://hoiboy.uk/community/agit-featured/<slug>/`. The canonical home of the story.
2. **An instructional `social.md`** in the same bundle (`content/community/agit-featured/<slug>/social.md`) - the paste-ready social copy. It is a Hugo bundle **resource** (a leaf bundle only renders `index.md`), so it does NOT publish as a page: it is the private cheat-sheet for posting. Confirm it never lands in `public/` after a build.

### social.md - the social posts (native-first)

Social platforms downrank posts with an outbound link in the body, and for a community series, shareability beats driving clicks to hoiboy.uk (that traffic comes on its own). So both posts go **native**, with the source link in the **first comment**, not the body.

Write two posts into `social.md`, paste-ready:

1. **Full story + hashtags** - the person posts their full feature story natively: Facebook, or a LinkedIn **Article** (the LinkedIn feed hard-caps at ~3,000 chars / ~500 words, so a full story there is an Article, not a feed post). social.md supplies the hashtag set to append and the `Source:` first comment; it does NOT reproduce the story (the feature page is the single source, so it cannot drift).
2. **280-char X summary** - a tight cut that fits inside X's 280-char limit **including** its hashtags, plus the `Source:` first comment.

Hashtag core set: `#AsiansInTech #GingersInTech #AGIT`, plus per-person tags (role / domain, e.g. `#DataCentre #Automation`). The feature link (`https://hoiboy.uk/community/agit-featured/<slug>/`) is the `Source:` in the first comment of every post; never in the post body.

## Deploy

Content changes: commit the page bundle by explicit path and follow the repo's deploy flow (push to main -> CI -> Cloudflare deploy). Confirm the live URL returns 200 before telling Hoi it is up.
