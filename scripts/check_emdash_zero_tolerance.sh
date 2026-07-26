#!/usr/bin/env bash
# Zero-tolerance em-dash (U+2014) guard for hoiboy.uk voice prose.
#
# SINGLE SOURCE OF TRUTH. Called by BOTH:
#   1. .github/workflows/ci.yml          : "Em-dash voice guard (zero tolerance)" step
#   2. .pre-commit-config.yaml           : "check-emdash-zero-tolerance" local hook
# so the local commit gate and CI can never drift. Before this script existed the
# grep lived only in CI; pre-commit's voice guard is marker-driven (only scans
# <!-- iamhoi --> prose + new posts), so an em dash in an UNMARKED docs reference
# file (e.g. docs/research/11_VOICE_PROFILE.md) sailed past every local hook, failed
# CI asynchronously after the push, and (because Deploy is gated on CI) SILENTLY
# FROZE the Cloudflare deploy for ~7h until someone noticed. See blog-priv#38.
#
# Scope rationale (keep identical in both callers, that is the point of one script):
#   content/posts excluded : voice-sacred legacy import (pre-AI corpus, issue #2)
#   meet-recorder excluded : tool page reproduces the consulting-ops verbal-consent
#                            script verbatim, em dashes intentional (consulting-ops#8)
#   scripts/ not in scope  : source code, not voice prose; voice rules apply only
#                            inside <!-- iamhoi --> markers (SST3 marker-driven model)
#
# ...with ONE carve-out from the content/posts exclusion: content/posts/_index.md.
# It is the /blogs/ hub landing (blog-priv#62 AC 4.1), not a legacy post. Hugo
# requires a section index to live at content/<section>/_index.md, so this page
# is stuck inside the legacy-exempt directory by the framework rather than by
# anything about its prose: it is new, post-cutoff, operator-approved copy that
# every category page links up to. Measured before adding it (2026-07-25): an em
# dash injected into that file passed this guard AND check_emdash_newposts.py,
# which selects via posts.rglob('index.md') and so never matches an _index.md.
# The marker-driven check-ai-writing-tells.py DOES catch it, because the hub has
# carried <!-- iamhoi --> markers since its first commit; re-measured 2026-07-26 by
# injecting an em dash, which returns exit 1 and 'TOTAL: 1 tells in 1 files'. So the
# gap this carve-out closes is grep-side only, and it is real: without the explicit
# name, this guard skips the file. Naming the file
# explicitly beats loosening --exclude-dir, which would drag in all 79 legacy
# posts. grep applies --exclude-dir only while recursing, so an explicitly named
# file inside an excluded directory is still read (asserted by the guard's own
# mutation test in scripts/test_emdash_hub_coverage.py).
#
# Em dashes are the single loudest AI-writing signature (VOICE_PROFILE.md §1).
# Fix a hit with a comma, colon, parentheses, ellipsis, or two sentences.
set -euo pipefail

EMDASH=$'—'
SCAN_PATHS=(content layouts assets config docs README.md content/posts/_index.md)

# -I skips binary files: the em-dash byte sequence (E2 80 94) can occur by chance
# inside compressed image data (e.g. a committed JPEG render), which is never voice
# prose. Without -I, grep -r reports "Binary file X matches" as a false positive.
matches=$(grep -rlnI --exclude-dir=posts --exclude-dir=meet-recorder "$EMDASH" "${SCAN_PATHS[@]}" 2>/dev/null || true)

if [ -n "$matches" ]; then
  echo "::error::Em dashes (U+2014) found in tracked voice files (zero-tolerance voice rule):" >&2
  echo "$matches" >&2
  echo "--- offending lines ---" >&2
  grep -rnI --exclude-dir=posts --exclude-dir=meet-recorder "$EMDASH" "${SCAN_PATHS[@]}" 2>/dev/null || true
  echo "Replace each em dash with a comma, colon, parentheses, ellipsis, or two sentences." >&2
  exit 1
fi

echo "OK: no em dashes in tracked voice files."
exit 0
