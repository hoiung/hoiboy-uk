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

## Theme upgrade procedure (custom theme)

This site ships a custom theme inside `layouts/` and `assets/`. There is no upstream theme submodule. "Theme upgrade" means hand-editing the layouts in this repo.

Manual verification checklist after any layout change:
1. `hugo --gc -e production` builds with zero warnings, zero errors
2. Local preview: `hugo server`, then check `/`, `/about/`, `/food/`, `/adventure/`, `/dance/`, `/tech/`, `/posts/foundation/`, `/tags/`
3. Sidebar renders, breadcrumbs render
4. CI green
5. Lighthouse score on homepage stays within baseline (`10_BASELINE_METRICS.md`)
6. Rollback path: `git revert` the layout commit
