---
title: Cloudflare API token — scoped-token recipe (principle of least privilege)
purpose: Reusable runbook for creating narrow Cloudflare API tokens for automation tasks. Captures the philosophy (least privilege), the actual permissions matrix per task type, and the create + revoke procedures. Designed to be the canonical reference when we automate Cloudflare work for clients — they'll use the same patterns.
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

1. **Least privilege** — tick only the permissions the specific task needs. If the task is "add 5 DNS records", the permissions are `DNS:Read` + `DNS:Edit` + `Zone:Read`. Not "Edit zone" (which lets you change nameservers). Not "Account: All" (which lets you do anything).
2. **TTL** — every automation token gets a 7-day expiry by default. If we forget to revoke, Cloudflare kills it for us. The only exception is long-running production deploy-hook tokens (e.g. break-glass Pages deploy), which still get reviewed quarterly.
3. **Revoke after the task is done** — even if the token has TTL. Belt and braces.

The blast radius of a leaked token is bounded by these three. With all three: leak = up to 7 days of "they could do this one narrow thing on this one zone". Without any of these: leak = "they have full control of the Cloudflare account, indefinitely".

## Why we don't use the global API key

Cloudflare's "Global API Key" (in profile settings) has full account access with no expiry, no scope, and is shown in plaintext to anyone who can read your profile page. It exists for legacy compatibility. Don't use it for anything.

## Why we don't use "All zones" or "Account: All Permissions"

Two arguments, both load-bearing:

1. **Personal account is the dogfood for client accounts.** The client-grade pattern is scoped tokens. If we use looser security on personal "for convenience", we end up with two patterns: the looser one we're familiar with and the tighter one we hand to clients. The looser one wins by default. So we practise the discipline on ourselves.
2. **Permission scoping is a forcing function for understanding.** If you can't articulate which permissions a task needs, you don't understand the task well enough to automate it for someone else. The act of mapping "task -> permissions" is part of the value we offer clients.

## The token creation flow

### Step 1 — Open the API tokens page

https://dash.cloudflare.com/profile/api-tokens

### Step 2 — Create token

Click **Create Token**. You can either:

- **Use a template** (e.g. "Edit zone DNS") — pre-fills common patterns, then you customise
- **Create custom token** — start from blank, build up

For most tasks, the template is faster but produces a slightly broader token than necessary. The custom path is recommended once you know the permission matrix below.

### Step 3 — Set permissions (custom token path)

In the **Permission policies** section:

- **Effect**: `Allow`
- **Resources**: scope as narrowly as possible. Options:
  - `Account` — for permissions Cloudflare designs as account-scoped (Workers, Pages, KV, R2)
  - `Specified zone` → pick exact zone (e.g. `hoiboy.uk`) — for everything zone-scoped (DNS, SSL, Email Routing Rules)
  - `Include all zones from an account` — AVOID. Always pick a specific zone.
- **Permission groups**: tick only what the task needs (see matrix below)

### Step 4 — Set TTL

In **Token expiration**:

- Tick **Start date** → today
- Tick **End date** → today + 7 days

### Step 5 — IP filter

Leave blank for typical use. Only useful if you have a known static IP for your automation runner (we don't, currently).

### Step 6 — Continue to summary, review, create

Cloudflare shows a summary page. Verify scope is narrow. Click **Create Token**.

The token value is displayed **once only**. Copy it before closing the page. If you lose it, delete and recreate.

### Step 7 — Use it

```bash
curl -s -H "Authorization: Bearer ${CF_API_TOKEN}" \
  "https://api.cloudflare.com/client/v4/user/tokens/verify"
```

Should return `"status": "active"`. If anything else, the token didn't save or the permissions are wrong.

### Step 8 — Revoke after task is complete

Don't wait for TTL. Go back to https://dash.cloudflare.com/profile/api-tokens, find the token, click **Roll** or **Delete**. Update any runbook with `[REVOKED yyyy-mm-dd]` so future-you knows the token in the runbook is dead.

## Permission matrix (per task type)

The right permissions for common automation tasks. Each row shows the minimum scope.

### Add / edit DNS records on a zone

| Permission | Read | Edit | Resource scope |
|---|---|---|---|
| DNS | ✅ | ✅ | Specified zone |
| Zone | ✅ | ❌ | Specified zone |

`Zone:Read` is needed to resolve zone name → zone ID (the DNS records API requires zone ID, not name). `Zone:Edit` is NOT needed — we are editing **records inside a zone**, not the zone itself.

**Example use cases**: adding TXT/CNAME for SaaS verification (Brevo, SendGrid, Stripe), adding subdomain CNAME for a Worker route, fixing a stale A record.

### Verify Email Routing config on a zone

| Permission | Read | Edit | Resource scope |
|---|---|---|---|
| Email Routing Rules | ✅ | ❌ | Specified zone |

Optional addition to a DNS-editing token. Lets the automation confirm `hello@hoiboy.uk` route is active without bouncing through the dashboard. Add `Edit` only if the automation actually creates routes (rare — Email Routing setup is usually one-time UI work).

### Deploy / update a Cloudflare Worker

| Permission | Read | Edit | Resource scope |
|---|---|---|---|
| Workers Scripts | ✅ | ✅ | Account (Workers can't be zone-scoped) |
| Workers KV Storage | ✅ | ✅ | Account |
| Workers Routes | ✅ | ✅ | Specified zone (for binding the Worker to a hostname) |

Workers are account-level resources by Cloudflare design — you can't restrict a Workers token to "only this Worker". The closest scope is "this account". For client work, this means each client gets their own Cloudflare account, NOT a shared one.

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

## The 2026-05-08 token (this session)

For reference, the token created during the email-routing-setup execution had:

- **Name**: black-fire-381e (Cloudflare auto-generated)
- **Policies** (1 policy):
  - Effect: Allow
  - Resources: Specified zone → `hoiboy.uk`
  - Permission groups: `DNS:Read`, `DNS:Edit`, `Zone:Read`, `Email Routing Rules:Read`
- **TTL**: 2026-05-08 to 2026-05-15
- **Used for**: adding 4 Brevo TXT/CNAME records + editing existing SPF record

**Status**: REVOKED ON [yyyy-mm-dd UPDATE WHEN DONE].

## Things to NEVER tick (for typical automation)

These are the easy mistakes that creep in if you're not deliberate.

| Permission | Why never tick |
|---|---|
| `Zone:Edit` (zone-level) | Lets the token modify zone itself — nameservers, plan, registrar settings. NOT what you need for DNS-record edits. |
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

1. **Production deploy hooks** (e.g. GHA `CF_PAGES_DEPLOY_HOOK`) — review quarterly per `docs/research/09_DEPLOYMENT.md`. These need permissions to remain stable across releases.
2. **Long-running Worker bindings** — environment variables that the Worker uses at runtime (e.g. to call back into Cloudflare API). These get a separate token with strictly read-only permissions on whatever the Worker needs to read.

In all other cases: 7-day TTL, revoke after task.

## How clients use this

When automating Cloudflare work for paid clients, the engagement model is:

1. Client creates a custom API token following this runbook (we send them the link)
2. Client picks the permission matrix row that matches the task we are doing
3. Client sets TTL = engagement duration + buffer (typically 7-14 days)
4. Client pastes the token into our intake (encrypted channel — never email plaintext)
5. We do the work, document it, and tell them when to revoke
6. Client revokes the token at engagement close

This pattern lives at the procurement layer (alongside the "GitHub organisation" requirement on the consulting page). It is not a sales objection — it is professional security practice that the client should welcome.

## Cross-references

- `docs/email-routing-setup.md` — consumes the DNS-scoped token from this runbook to add Brevo records
- `docs/cal-com-setup.md` — Path B Cloudflare Worker deployment will need the Workers-scoped row from the matrix
- `docs/research/09_DEPLOYMENT.md` — Pages deployment break-glass uses the Pages-scoped row from the matrix
- Cloudflare API token docs: https://developers.cloudflare.com/fundamentals/api/get-started/create-token/
