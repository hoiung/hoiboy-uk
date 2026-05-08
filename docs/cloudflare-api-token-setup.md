---
title: Cloudflare API token - scoped-token recipe (principle of least privilege)
purpose: Reusable runbook for creating narrow Cloudflare API tokens for automation tasks. Captures the philosophy (least privilege), the actual permissions matrix per task type, and the create + revoke procedures. Designed to be the canonical reference when we automate Cloudflare work for clients - they'll use the same patterns.
last_verified: 2026-05-08
related:
  - docs/email-routing-setup.md (consumes a Zone DNS-scoped token)
  - docs/cal-com-setup.md (Path B Worker deployment will need a Workers-scoped token)
  - docs/research/09_DEPLOYMENT.md (uses a Pages deployment token for break-glass)
---

This is the canonical recipe for creating Cloudflare API tokens for automation. **Never use the global API key.** Always create scoped tokens with TTL and the minimum permissions for the task.

When we automate Cloudflare work for paid clients, this is the pattern they will use. Practising it on our own setup first means we know it works and we can hand them a battle-tested runbook.

## The principle: least privilege + TTL + revoke

Three rules, all three required:

1. **Least privilege** - tick only the permissions the specific task needs. If the task is "add 5 DNS records", the permissions are `DNS:Read` + `DNS:Edit` + `Zone:Read`. Not "Edit zone" (which lets you change nameservers). Not "Account: All" (which lets you do anything).
2. **TTL** - every automation token gets an expiry. Default depends on use case: **7 days for one-off setup work** (single task you'll finish in a session), **90 days for ongoing automation** (e.g. recurring DNS edits, Worker deployments, integration with persistent BW-stored credentials). 90-day tokens enforce quarterly rotation discipline. Long-running production deploy-hook tokens (e.g. break-glass Pages deploy) still get reviewed quarterly, replaced annually.
3. **Revoke after the task is done** - even if the token has TTL. Belt and braces.

The blast radius of a leaked token is bounded by these three. With all three: leak = up to 7 days of "they could do this one narrow thing on this one zone". Without any of these: leak = "they have full control of the Cloudflare account, indefinitely".

## Why we don't use the global API key

Cloudflare's "Global API Key" (in profile settings) has full account access with no expiry, no scope, and is shown in plaintext to anyone who can read your profile page. It exists for legacy compatibility. Don't use it for anything.

## User API tokens vs Account API tokens (THE critical distinction)

Cloudflare has **two parallel token systems** and it is not obvious from the dashboard navigation. They are NOT interchangeable:

| Aspect | User API Tokens | Account API Tokens |
|---|---|---|
| Where created | `dash.cloudflare.com/profile/api-tokens` ("My Profile" → API Tokens) | `dash.cloudflare.com/<account_id>/api-tokens` ("Manage Account" → API Tokens) |
| Owned by | A user identity (you, personally) | An account (organisation-like) |
| Verify endpoint | `GET /v4/user/tokens/verify` | `GET /v4/accounts/{account_id}/tokens/verify` |
| Auth header | Same (`Authorization: Bearer cfat_...`) | Same (`Authorization: Bearer cfat_...`) |
| Used by | Solo operator personal automation | Team-shared automation, CI/CD, infra-as-code, multi-member accounts |
| Survives user deletion | No (token dies with user) | Yes (token persists if account exists) |

**The trap**: a token created in one section returns `Invalid API Token` against the verify endpoint of the OTHER section. Same prefix (`cfat_`), same length, same Bearer header - but different storage backend. We hit this exact issue 2026-05-08 when verifying the freshly-created token against `/user/tokens/verify` and got a misleading 401.

**Recommendation for solo + future-client work**: prefer Account API tokens. They survive personnel changes, are associated with the org rather than an individual, and the API endpoints we use (DNS records, Workers, Pages) all accept either kind once the verify endpoint is correct. Personal-only tooling (e.g. `wrangler login` flow for local development) uses User tokens by Cloudflare's design.

**How to verify which kind you have**: just try both verify endpoints. The one that returns `success: true` is the right one. If neither works, the token didn't persist - re-create.

## Why we don't use "All zones" or "Account: All Permissions"

Two arguments, both load-bearing:

1. **Personal account is the dogfood for client accounts.** The client-grade pattern is scoped tokens. If we use looser security on personal "for convenience", we end up with two patterns: the looser one we're familiar with and the tighter one we hand to clients. The looser one wins by default. So we practise the discipline on ourselves.
2. **Permission scoping is a forcing function for understanding.** If you can't articulate which permissions a task needs, you don't understand the task well enough to automate it for someone else. The act of mapping "task -> permissions" is part of the value we offer clients.

## The token creation flow

### Step 1 - Open the API tokens page

For Account-owned tokens (recommended for ongoing automation):
- `dash.cloudflare.com` → click the account name → **Manage Account** → **API Tokens**

For User-owned tokens (personal-only tooling):
- `https://dash.cloudflare.com/profile/api-tokens`

The flow below is the same on both pages. Pick deliberately based on the User-vs-Account distinction above.

### Step 2 - Create token

Click **Create Token**. You can either:

- **Use a template** (e.g. "Edit zone DNS") - pre-fills common patterns, then you customise
- **Create custom token** - start from blank, build up

For most tasks, the template is faster but produces a slightly broader token than necessary. The custom path is recommended once you know the permission matrix below.

### Step 3 - Set permissions (custom token path)

In the **Permission policies** section:

- **Effect**: `Allow`
- **Resources**: scope as narrowly as possible. Options:
  - `Account` - for permissions Cloudflare designs as account-scoped (Workers, Pages, KV, R2)
  - `Specified zone` → pick exact zone (e.g. `hoiboy.uk`) - for everything zone-scoped (DNS, SSL, Email Routing Rules)
  - `Include all zones from an account` - AVOID. Always pick a specific zone.
- **Permission groups**: tick only what the task needs (see matrix below)

### Step 4 - Set TTL

In **Token expiration**:

- Tick **Start date** → today
- Tick **End date** → today + N days, where N depends on use case:
  - **7 days** for one-off setup work (single task you'll finish in a session, then revoke)
  - **90 days** for ongoing automation (recurring DNS edits, Worker deployments, integration with persistent BW-stored credentials). Forces quarterly rotation discipline.

90-day tokens require a calendar reminder for rotation since Cloudflare won't auto-warn until close to expiry.

### Step 5 - IP filter

Leave blank for typical use. Only useful if you have a known static IP for your automation runner (we don't, currently).

### Step 6 - Continue to summary, review, create

Cloudflare shows a summary page. Verify scope is narrow. Click **Create Token**.

The token value is displayed **once only**. Copy it before closing the page. If you lose it, delete and recreate.

### Step 7 - Store in Bitwarden

Don't paste the token into chat or commit it. Save it in Bitwarden with this structure:

| Field | Value |
|---|---|
| Item type | Login |
| Name | `<system>-<scope>-<purpose>` (e.g. `hoiboy-uk-cloudflare-automation`) |
| Username | The Cloudflare **account ID** (32-char hex, find at `dash.cloudflare.com/<account_id>/...` in URL bar) |
| Password | The token value |
| URI | The dashboard URL where you created the token |
| Notes | Scope summary, creation date, expiry date, list of consumers, rotation date |

Account ID as username is deliberate: Account-scoped tokens use endpoints like `/accounts/{account_id}/...` so retrieving the account ID alongside the token saves a round-trip.

### Step 8 - Verify

Pick the right verify endpoint based on User-vs-Account (see distinction section above):

```bash
# Account-owned token:
curl -s -H "Authorization: Bearer ${CF_TOKEN}" \
  "https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT_ID}/tokens/verify"

# User-owned token:
curl -s -H "Authorization: Bearer ${CF_TOKEN}" \
  "https://api.cloudflare.com/client/v4/user/tokens/verify"
```

Should return `"status": "active"` with an `expires_on` field. If `Invalid API Token`, try the OTHER verify endpoint before assuming the token is broken.

### Step 9 - Retrieve it from BW for use

Pattern (consistent across all our automation runbooks - Cloudflare, Brevo, Cal.com, etc.):

```bash
# In your terminal (not Claude's), unlock Bitwarden:
bw unlock --raw

# Paste the printed BW_SESSION token into chat. The agent does the rest:
echo -n "<BW_SESSION token from above>" > /tmp/.bw-session
chmod 600 /tmp/.bw-session

# Subsequent retrievals:
export BW_SESSION="$(cat /tmp/.bw-session)"
source ~/DevProjects/lab-ops/scripts/utils/bw-helpers.sh
bw sync >/dev/null 2>&1   # MANDATORY for freshly-created items (Bitwarden cache invalidation)

# Get token + account ID:
CF_TOKEN="$(bw_get hoiboy-uk-cloudflare-automation)"  # secret-allow (BW retrieval, not a literal secret)
CF_ACCOUNT_ID="$(bw get item hoiboy-uk-cloudflare-automation | python3 -c 'import json,sys; print(json.load(sys.stdin)[chr(34)+"login"+chr(34)][chr(34)+"username"+chr(34)])')"  # secret-allow (BW retrieval - extracts account ID from username field)
```

The `bw sync` is non-optional after creating fresh items - `bw_get` returns "item not found" misleadingly without it. Captured as auto-memory `feedback_bw_sync_required_for_fresh_items.md`.

### Step 10 - Revoke after task is complete

For 7-day tokens: don't wait for TTL. After the task ends, go to the same dashboard page, find the token, click **Roll** (rotates value, keeps permissions) or **Delete** (removes entirely).

For 90-day tokens: rotate at 80 days (10-day buffer for testing the new value before old expires). Replace value in BW + update consumers, then delete the old token.

Update the source runbook with `[REVOKED yyyy-mm-dd]` marker (no inline reason; the reason goes in the runbook prose).

## Permission matrix (per task type)

The right permissions for common automation tasks. Each row shows the minimum scope.

### Add / edit DNS records on a zone

| Permission | Read | Edit | Resource scope |
|---|---|---|---|
| DNS | ✅ | ✅ | Specified zone |
| Zone | ✅ | ❌ | Specified zone |

`Zone:Read` is needed to resolve zone name → zone ID (the DNS records API requires zone ID, not name). `Zone:Edit` is NOT needed - we are editing **records inside a zone**, not the zone itself.

**Example use cases**: adding TXT/CNAME for SaaS verification (Brevo, SendGrid, Stripe), adding subdomain CNAME for a Worker route, fixing a stale A record.

### Verify Email Routing config on a zone

| Permission | Read | Edit | Resource scope |
|---|---|---|---|
| Email Routing Rules | ✅ | ❌ | Specified zone |

Optional addition to a DNS-editing token. Lets the automation confirm `hello@hoiboy.uk` route is active without bouncing through the dashboard. Add `Edit` only if the automation actually creates routes (rare - Email Routing setup is usually one-time UI work).

### Deploy / update a Cloudflare Worker

| Permission | Read | Edit | Resource scope |
|---|---|---|---|
| Workers Scripts | ✅ | ✅ | Account (Workers can't be zone-scoped) |
| Workers KV Storage | ✅ | ✅ | Account |
| Workers Routes | ✅ | ✅ | Specified zone (for binding the Worker to a hostname) |

Workers are account-level resources by Cloudflare design - you can't restrict a Workers token to "only this Worker". The closest scope is "this account". For client work, this means each client gets their own Cloudflare account, NOT a shared one.

### Deploy Cloudflare Pages

| Permission | Read | Edit | Resource scope |
|---|---|---|---|
| Cloudflare Pages | ✅ | ✅ | Account |

For automation that runs `wrangler pages deploy`. Already documented in `docs/research/09_DEPLOYMENT.md` for the break-glass deploy path.

### Read-only audit

| Permission | Read | Edit | Resource scope |
|---|---|---|---|
| (any of: Zone, DNS, SSL, Email Routing Rules) | ✅ | ❌ | Specified zone |

For automation that reads state but never modifies. Useful for monitoring, drift detection, "is the SPF record what I expect" health checks.

## Execution evidence - 2026-05-08

Token created and used during the email-routing-setup execution:

- **Name**: `hoiboy-uk-cloudflare-automation`
- **Type**: Account API token (NOT User token - see distinction section above; the misclassification cost ~5 minutes of debugging "Invalid API Token" before we realised)
- **Account ID**: stored as username field in BW
- **Policies** (1 policy):
  - Effect: Allow
  - Resources: Specified zone → `hoiboy.uk`
  - Permission groups: `DNS:Read`, `DNS:Edit`, `Zone:Read`, `Email Routing Rules:Read`
- **TTL**: 2026-05-08 → 2026-08-06 (90 days, ongoing-automation cadence)
- **BW item**: `hoiboy-uk-cloudflare-automation`
- **Used for**:
  - Adding 4 new Brevo DNS records (1 TXT for verification, 2 CNAME for DKIM, 1 TXT for DMARC) via `POST /v4/zones/{id}/dns_records`
  - Patching existing SPF record (TXT) via `PATCH /v4/zones/{id}/dns_records/{record_id}` to append `include:spf.brevo.com`
  - Verifying with `GET /v4/accounts/{id}/tokens/verify`
- **Rotation reminder**: 2026-08-06 (rotate at 2026-07-27 with 10-day buffer)

**Status**: ACTIVE.

### Actual API calls made (for reference)

```bash
# Resolve zone ID
curl -s -H "Authorization: Bearer $CF_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones?name=hoiboy.uk"

# Add DNS record (TXT or CNAME, same shape)
curl -s -X POST -H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json" \
  -d '{"type":"TXT","name":"hoiboy.uk","content":"<value>","ttl":1,"proxied":false}' \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records"

# PATCH existing record
curl -s -X PATCH -H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json" \
  -d '{"content":"<new value>"}' \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID"

# DoH propagation check (no auth needed; bypasses local cache)
curl -s -H "accept: application/dns-json" \
  "https://1.1.1.1/dns-query?name=hoiboy.uk&type=TXT"
```

`name` field accepts either bare hostname (`hoiboy.uk`, `_dmarc`) or FQDN (`_dmarc.hoiboy.uk`); Cloudflare normalises to FQDN in the response. `ttl: 1` means "Auto" in the dashboard. `proxied: false` is required for TXT/CNAME records used by email auth (orange cloud breaks DKIM/SPF).

### Lessons learned

1. **User vs Account API token distinction is invisible until verify fails.** Always know which kind you have. Default to Account for org-grade use.
2. **`CustomThrottlerGuard - Invalid API Key` does NOT mean the key is malformed.** It can mean: wrong verify endpoint (User vs Account), wrong region (when applicable to other services), token didn't persist on Cloudflare's side, or rare cases where the throttler can't index the key. Treat 401 as "verify against the OTHER scope or recreate".
3. **404 after a successful auth is good news.** Means the token works; the path or version header is wrong. Useful for endpoint discovery sweeps.
4. **`bw sync` is non-optional after creating fresh BW items.** Without it `bw_get` returns "item not found" misleadingly.
5. **Cloudflare DNS subdomains may show stale negative cache via 1.1.1.1 DoH.** Authoritative NS query bypasses negative cache. After ~15-30s the public resolvers refresh.

## Things to NEVER tick (for typical automation)

These are the easy mistakes that creep in if you're not deliberate.

| Permission | Why never tick |
|---|---|
| `Zone:Edit` (zone-level) | Lets the token modify zone itself - nameservers, plan, registrar settings. NOT what you need for DNS-record edits. |
| `Account:Account Settings:Edit` | Lets the token modify account-wide settings, members, billing. Massive blast radius. |
| `Zone Settings:*` | SSL mode, security level, browser cache, dev mode. Unrelated to most automation. |
| `Zone DNS Settings:*` | DNSSEC, zone-level DNS config. Different from individual DNS records. |
| `Apps:Edit` | Cloudflare Apps (legacy product). Not relevant to most modern workflows. |
| `Cloudflare Workers Routes:Edit` on `All zones` | Should always be specified zone. |
| `Page Rules:Edit` | Legacy product, replaced by Transform Rules / Configuration Rules. |

## Revocation runbook

When done with a task:

1. https://dash.cloudflare.com/profile/api-tokens
2. Find the token by name (e.g. `black-fire-381e`)
3. Click the row → **Roll** (rotates value, keeps permissions) OR **Delete** (removes entirely)
4. For end-of-task: **Delete**. For "I think the token leaked": **Roll**.
5. Update any runbook that referenced the token. Add a `[REVOKED yyyy-mm-dd]` marker (no inline reason; the reason goes in the runbook prose).

## When TTL is not enough

The 7-day TTL is the right default for most automation. There are two cases where we keep tokens longer:

1. **Production deploy hooks** (e.g. GHA `CF_PAGES_DEPLOY_HOOK`) - review quarterly per `docs/research/09_DEPLOYMENT.md`. These need permissions to remain stable across releases.
2. **Long-running Worker bindings** - environment variables that the Worker uses at runtime (e.g. to call back into Cloudflare API). These get a separate token with strictly read-only permissions on whatever the Worker needs to read.

In all other cases: 7-day TTL, revoke after task.

## How clients use this

When automating Cloudflare work for paid clients, the engagement model is:

1. Client creates a custom API token following this runbook (we send them the link)
2. Client picks the permission matrix row that matches the task we are doing
3. Client sets TTL = engagement duration + buffer (typically 7-14 days)
4. Client pastes the token into our intake (encrypted channel - never email plaintext)
5. We do the work, document it, and tell them when to revoke
6. Client revokes the token at engagement close

This pattern lives at the procurement layer (alongside the "GitHub organisation" requirement on the consulting page). It is not a sales objection - it is professional security practice that the client should welcome.

## Cross-references

- `docs/email-routing-setup.md` - consumes the DNS-scoped token from this runbook to add Brevo records
- `docs/cal-com-setup.md` - Path B Cloudflare Worker deployment will need the Workers-scoped row from the matrix
- `docs/research/09_DEPLOYMENT.md` - Pages deployment break-glass uses the Pages-scoped row from the matrix
- Cloudflare API token docs: https://developers.cloudflare.com/fundamentals/api/get-started/create-token/
