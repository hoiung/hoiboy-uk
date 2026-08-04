#!/bin/bash
# Regenerate every social card, in the only order that can work (blog-priv#62 AC 3.0).
#
# A card's eyebrow is the page's parent trail, read from public/<url>/trail.json —
# a file that only exists once Hugo has rendered the page. And both generators write
# share-card.png into content/ page bundles, never into static/, so a card written
# after a build is absent from public/ until Hugo runs again. That makes card
# generation a strict two-pass build:
#
#   1. hugo --minify          render pages -> emits the trail.json sidecars
#   2. gen_card.py            read each target's sidecar -> write share-card.png
#      gen_agit_feature.py      into content/<...>/ (fails loud on a missing sidecar)
#   3. hugo --minify          re-render so the new PNGs are copied into public/
#   4. check_social_cards.py  --strict: every indexable page owns its rendered card
#
# Nothing enforced this before: pre-publish.sh, ci.yml and .pre-commit-config.yaml
# only ever ran check_social_cards.py, never a generator, so a breadcrumb change
# could never re-derive an eyebrow. pre-publish.sh now calls this script.
#
# Usage:  bash scripts/gen-social-cards.sh
# Deps:   hugo (extended, version pinned in .hugo-version), rsvg-convert, Pillow.
# Exit:   0 = every card regenerated and verified; non-zero = first failing step.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

PUBLIC="${PUBLIC_DIR:-public}"

step() { printf '\n=== %s ===\n' "$1"; }

step "1/4 build (emit trail.json sidecars)"
hugo --minify --destination "$PUBLIC"

step "2/4 generate cards from each page's trail"
# HOIBOY_PUBLIC_DIR tells the generators where the sidecars are. They exit non-zero
# and name the bundle if one is missing — there is deliberately no default eyebrow,
# because a card silently falling back to a brand string is the drift #62 removes.
HOIBOY_PUBLIC_DIR="$PUBLIC" python3 scripts/social-cards/gen_card.py
HOIBOY_PUBLIC_DIR="$PUBLIC" python3 scripts/social-cards/gen_agit_feature.py

step "3/4 rebuild (copy the regenerated PNGs into $PUBLIC)"
hugo --minify --destination "$PUBLIC"

step "4/4 verify every indexable page owns its rendered card"
python3 scripts/check_social_cards.py --built "$PUBLIC" --strict --require-trails

printf '\nOK: social cards regenerated from the page trails and verified.\n'
