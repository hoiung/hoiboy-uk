# Consulting Launch Checklist

Operator-facing runbook for replacing `OPERATOR_TODO_REPLACE_BEFORE_LAUNCH` placeholders in `data/consulting.yaml` and shipping the consulting landing pages to production.

Created per consulting-ops#2 Phase 0 AC 0.5. Distinct from `docs/AUTHORING.md` (blog-post authoring contract); this file covers the consulting URL-replacement procedure and the four protection gates around it.

## What this protects

The consulting landing pages render external CTAs (Cal.com, optionally Stripe) whose URLs live in `data/consulting.yaml`. Until the operator replaces the literal `OPERATOR_TODO_REPLACE_BEFORE_LAUNCH` substring with a real URL, four gates fire to prevent the placeholder from reaching production:

### Gate 1: Hugo shortcode mailto fallback

`layouts/_shortcodes/consulting-cta.html` detects the `OPERATOR_TODO_REPLACE_BEFORE_LAUNCH` substring at template-render time and falls back to a `mailto:hello@hoiboy.uk` link. Fail-LOUD-with-degraded-CTA: the page still ships a working contact path. Verify with `hugo --buildDrafts` against an `OPERATOR_TODO`-stuffed yaml; the rendered HTML should contain a `mailto:` href at the CTA seam.

### Gate 2: pre-publish.sh production-errorf

`scripts/pre-publish.sh` check #1 (`consulting-yaml-no-operator-todo`) greps `data/consulting.yaml` for the `OPERATOR_TODO` substring. Non-zero exit blocks publish with stderr message `consulting.yaml contains OPERATOR_TODO placeholder; refusing to publish`. Run `bash scripts/pre-publish.sh content/posts/<slug>/` against an `OPERATOR_TODO`-stuffed yaml - exits 1.

### Gate 3: Pre-commit hook

`.pre-commit-config.yaml` hook `consulting-yaml-no-operator-todo` runs on staged changes to `data/consulting.yaml`. Test with `pre-commit run --files data/consulting.yaml` against an `OPERATOR_TODO`-stuffed yaml - exits 1.

### Gate 4: Lychee rendered-HTML link check

`scripts/pre-publish.sh` check `consulting-link-liveness` runs `lychee` against `public/consulting/**/index.html` post-Hugo-build. A `cal.com/OPERATOR_TODO_REPLACE_BEFORE_LAUNCH/20min-discovery` URL would 404 and fail this gate. The `lychee.toml` `exclude_path` was tightened from `public` to `public/posts` so consulting paths are reachable.

## Replacement procedure (operator)

1. Configure the live Cal.com event per consulting-ops#2 Phase 1 AC 1.1 (Mon-Fri 12:00-15:00 UK, 30-min slots, 10-min buffer, max 3/day, syncs to `hoiung@gmail.com`). Capture the live event URL.
2. Edit `data/consulting.yaml` and replace `OPERATOR_TODO_REPLACE_BEFORE_LAUNCH` in the `harness_architect.calcom_booking` field with the live URL. The Stripe field is removed entirely in V2 (no Stripe Payment Link until V2 cash-engine validates).
3. Run `bash scripts/pre-publish.sh content/consulting/<slug>/` locally. Exit 0 is the gate. A consulting target reports **13 passed, 1 skipped**: the
`wordcount` gate is posts-only and skips by design for consulting pages.
4. Stage and commit. The pre-commit hook re-runs the yaml gate.
5. Push. CI re-runs the gates. Cloudflare deploy hook fires only on green.

## Verifying the gates work

Each gate has a verification command documented above. The historic-failure marker `OPERATOR_TODO_REPLACE_BEFORE_LAUNCH` is intentionally referenced in this file so pattern-matching tools can locate this checklist via grep - appearances in this document are documentation, not live placeholders. Stage 5 reviewers grepping for `OPERATOR_TODO` outside the audit-trail expect to find references only in this checklist (and only on this file under `hoiboy-uk/docs/`).

## Cross-reference

- consulting-ops#2 Phase 0 (this checklist + the four gates above)
- consulting-ops#2 Phase 1 (Cal.com setup procedure that produces the live URL)
- consulting-ops#2 Phase 2 (`data/consulting.yaml` V2 ladder structure)
- `docs/AUTHORING.md` (separate blog-post authoring contract - does NOT cover consulting)
