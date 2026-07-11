# Deployment

**Date**: 2026-04-07

## Architecture

```
push to main
   v
GitHub Actions ci.yml (build + lint + voice + traceability + lychee)
   v
ci.yml passes => workflow_run triggers deploy.yml
   v
deploy.yml asserts CF_PAGES_DEPLOY_HOOK secret present, then POSTs the hook
   v
Cloudflare Pages builds from main (auto-build disabled, hook-only)
   v
hoiboy.uk live (atomic deploy, last good build preserved)
```

## Cloudflare Pages settings (verified click path, April 2026 unified UI)

**Finding the Pages create form**: Cloudflare merged Workers and Pages into one dashboard. The default `Workers & Pages > Create application` button creates a Worker, NOT a Pages project. To create Pages, look for a small sublink labelled "Pages" inside the Create application flow. It is not prominent. Plan for 2 minutes of clicking around.

| Setting | Value |
|---|---|
| Project name | `hoiboy-uk` |
| Repo | `hoiung/hoiboy-uk` |
| Branch | `main` |
| Framework preset | **None** (do not pick Hugo from the dropdown, it overrides our settings) |
| Build command | `bash scripts/cloudflare-build.sh` |
| Build output directory | `public` (default may be wrong, set explicitly) |
| Root directory | `/` |

Env vars (Settings > Variables and Secrets > Production scope, all Plaintext not Secret):

| Name | Value |
|---|---|
| `HUGO_VERSION` | `0.160.0` (must match `.hugo-version` exactly; Cloudflare's runner uses this to install Hugo) |
| `HUGO_ENV` | `production` |
| `GOMEMLIMIT` | `2GiB` |

**Critical**: `HUGO_VERSION` MUST be set as a Pages env var. Setting it via shell substitution in the build command (e.g. `HUGO_VERSION=$(cat .hugo-version) hugo ...`) does NOT override the runner's pre-baked Hugo version. The env var is what triggers Cloudflare's runner to install the right version.

### Branch control (Settings > Build > Branch control)

| Setting | Value |
|---|---|
| Production branch | `main` |
| Enable automatic production branch deployments | **UNCHECKED** (deploys come from GHA, not git push) |
| Preview branch | **None (Disable automatic branch deployments)** |

After saving, Cloudflare will display a banner: "Automatic production branch deployments are disabled for your git integration." That is the design. Ignore the banner.

Custom domain (NOT inside Settings):
- Custom Domains is a TOP-LEVEL TAB on the project page, alongside Deployments / Functions / Settings. Do not look for it under Settings.
- Click **Set up a custom domain** > enter `hoiboy.uk` > **Continue** > **Activate domain**
- One click since Cloudflare registrar (no DNS faff)
- Optional: add `www.hoiboy.uk` and configure a 301 redirect to apex via Cloudflare DNS or Page Rules
- "Always Use HTTPS" enabled by default

## GitHub Actions secret

| Secret | Source | Use |
|---|---|---|
| `CF_PAGES_DEPLOY_HOOK` | Cloudflare Pages > Settings > Builds & deployments > Deploy hooks > Add deploy hook (name: `gha-main`, branch: `main`) | `deploy.yml` POSTs this URL on green CI |

`deploy.yml` fails LOUDLY if the secret is unset.

Rotation: revoke + recreate the deploy hook in Cloudflare, then update the secret in GitHub Settings > Secrets and variables > Actions.

## Community submission form (Pages Function)

The community "Get featured" form (issue #43 Phase 2) posts to a Cloudflare Pages Function.

**Function**: `functions/api/contribute.js`, route `POST /api/contribute`. A top-level `functions/` directory auto-deploys via the same git-connected Cloudflare Pages build that builds `public/` (no `ci.yml` / `deploy.yml` change needed). This was proven live with a throwaway `functions/ping.js` probe before the real Function was written (Phase 2a).

**Bindings and secrets** (Cloudflare dashboard: `Workers & Pages > hoiboy-uk > Settings`; NO `wrangler.toml`, which would lock out dashboard edits):

| Name | Type | Where | Purpose |
|---|---|---|---|
| `TURNSTILE_SECRET_KEY` | Secret (encrypted) | Settings > Variables and Secrets > Production | Server-side Turnstile `siteverify` |
| `AGIT_UPLOADS` | R2 bucket binding | Settings > Bindings > Add > R2 bucket | Private photo storage (bucket `agit-submissions`, private) |
| `CF_EMAIL_TOKEN` | Secret (encrypted) | Settings > Variables and Secrets > Production | Cloudflare API token (Email Sending: Edit) for the REST send |
| `CF_ACCOUNT_ID` | Secret (encrypted) | Settings > Variables and Secrets > Production | Account ID in the REST endpoint URL |

The Turnstile **site key** is public and lives in the form HTML (`content/community/asians-gingers-in-tech/index.md`, the `data-sitekey` on the `cf-turnstile` div). It is NOT a secret; commit it.

**Email: the zero-DNS-chore path (REST API, not a binding).** The Cloudflare **Pages** dashboard has no send-email binding (email bindings are Workers-only, configured via a Wrangler config file, which this project deliberately avoids). So the Function sends via the Email Service **REST API** instead: `POST https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/email/sending/send` with `Authorization: Bearer {CF_EMAIL_TOKEN}` and a JSON body `{to, from, subject, text, attachments}`. Per Cloudflare docs, sends to a **verified destination address** are free on any plan **when only Email Routing is configured**, so you do NOT onboard the domain to Email Sending (no `cf-bounce` SPF/DKIM/DMARC records). The only requirements: (a) the `to` is a **verified Email Routing destination address** (`hoiboyuk@gmail.com`, the address the `hello@hoiboy.uk` routing rule already forwards to; note a routing-rule address like `hello@hoiboy.uk` is NOT itself a destination address and cannot be a send target), and (b) the `from` is on a **routing domain** (`agit-form@hoiboy.uk`, since `hoiboy.uk` is the routing domain; the local part is synthetic and needs no registration, so a distinct AGIT sender is easy to filter on in Gmail).

**Provisioning (operator, one-time, dashboard)**:

1. Turnstile: create a widget for `hoiboy.uk`; paste the site key into the form; store the secret key as the `TURNSTILE_SECRET_KEY` Pages secret.
2. R2: create a **private** bucket `agit-submissions`; bind it as `AGIT_UPLOADS` (Settings > Bindings > Add > R2 bucket); redeploy so the binding takes effect.
3. Email: create a **Cloudflare API token** with the **Email Sending: Edit** permission (My Profile > API Tokens > Create Token > Custom token), store it as the `CF_EMAIL_TOKEN` Pages secret, and store the account ID as the `CF_ACCOUNT_ID` Pages secret. Confirm `hoiboyuk@gmail.com` is a **verified** Email Routing destination address (it already is, as the `hello@hoiboy.uk` routing rule forwards to it). Keep the `hello@hoiboy.uk` routing rule regardless, since it is the site's public contact address and is independent of the form. Redeploy so the secrets take effect.

**Retention (R2 lifecycle rule): REQUIRED go-live gate.** On the `agit-submissions` bucket, add an object-lifecycle rule that **expires objects 90 days after creation** (R2 > bucket > Settings > Object lifecycle rules). This auto-purges unpublished submission photos and is what backs the live 90-day promise in the Privacy Notice. Set it **before** the form accepts real submissions, since the legal promise is otherwise unbacked (no code path enforces retention; R2 lifecycle is dashboard-only). Mirrored in the Privacy Notice and the Sub-Processors page.

**Observability**: the Function emits a structured `console.log` JSON line at each decision branch (honeypot drop, Turnstile fail, size/type reject, R2 store, email send). View them under the project's Functions logs / real-time logs.

## Hugo version pinning

`.hugo-version` at repo root is the single source of truth.

- CI reads it, asserts the installed binary matches, fails on mismatch
- Cloudflare reads it via `HUGO_VERSION=$(cat .hugo-version)` in the build command (Pages supports shell substitution in build commands)
- If shell substitution ever breaks: fallback is to set `HUGO_VERSION` as a Pages env var matching `.hugo-version`. CI will detect the drift on the next build.

## Build cache

CI persists `resources/_gen` and `/tmp/hugo_cache` keyed on `hashFiles('.hugo-version', 'content/**', 'assets/**', 'layouts/**', 'config/**')`. Including `.hugo-version` in the key is critical: a Hugo bump must bust the cache to prevent stale image-pipeline artefacts (known Hugo footgun).

Cache hygiene step: `find resources/_gen -atime +30 -delete` before save. Caps unbounded growth.

## Cache invalidation on Hugo bump

1. Bump `.hugo-version`
2. Push. Cache key auto-busts because `.hugo-version` is in the hash.
3. Cloudflare Pages cache: clear via dashboard if needed (Pages > Settings > Builds & deployments > Build cache > Clear cache).

## Atomic rollback

Cloudflare Pages keeps deployment history. Rollback options:

**Dashboard (fastest)**: Pages > Deployments > pick a previous successful deploy > Manage deployment > Rollback to this deployment.

**Wrangler CLI**:
```bash
npm install -g wrangler
wrangler login
wrangler pages deployment list --project-name=hoiboy-uk
wrangler pages deployment rollback <deployment-id> --project-name=hoiboy-uk
```

**Smoke test post-rollback**:
```bash
curl -I https://hoiboy.uk
curl -s https://hoiboy.uk/build-info.json
```

## Break-glass: deploy from local laptop

When GHA or Cloudflare is down, deploy manually:

```bash
# Required: Node.js 18+, wrangler, Cloudflare API token (Pages: Edit scope)
npm install -g wrangler

# Token storage: store in ~/.cloudflare-token (chmod 600), or 1Password, or pass.
# NEVER commit. To revoke: Cloudflare dashboard > My Profile > API Tokens > Roll.
export CLOUDFLARE_API_TOKEN=$(cat ~/.cloudflare-token)
export CLOUDFLARE_ACCOUNT_ID=<your-account-id>

cd ~/DevProjects/hoiboy-uk
HUGO_VERSION=$(cat .hugo-version) hugo --gc --minify -e production
wrangler pages deploy public --project-name=hoiboy-uk --branch=main
```

**Caveat (issue #43)**: `wrangler pages deploy public` uploads ONLY the `public/` output directory. It does NOT ship the top-level `functions/` directory, so a break-glass deploy this way will **not** update (and may drop) the `/api/contribute` submission handler. Functions only ship through the git-connected Cloudflare build. If you must break-glass a Functions change, run `wrangler pages deploy` from the repo root (so it picks up `functions/`) rather than pointing it at `public/`, or restore the git-connected build path first.

## Theme upgrade procedure (custom theme)

This site ships a custom theme inside `layouts/` and `assets/`. There is no upstream theme submodule. "Theme upgrade" means hand-editing the layouts in this repo.

Manual verification checklist after any layout change:
1. `hugo --gc -e production` builds with zero warnings, zero errors
2. Local preview: `hugo server`, then check `/`, `/about/`, `/food-booze/`, `/adventure/`, `/dance/`, `/tech-ai/`, `/posts/foundation/`, `/tags/`
3. Sidebar renders, breadcrumbs render
4. CI green
5. Lighthouse score on homepage stays within baseline (`10_BASELINE_METRICS.md`)
6. Rollback path: `git revert` the layout commit
