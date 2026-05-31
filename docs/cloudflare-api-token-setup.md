---
title: Cloudflare API token - hoiboy.uk execution evidence (recipe relocated)
purpose: The generic, reusable Cloudflare API token recipe has moved to the dotfiles canonical runbook. This file retains only the hoiboy.uk-specific token execution evidence.
last_verified: 2026-05-31
related:
  - dotfiles/docs/runbooks/cloudflare-control.md (the canonical reusable recipe - token model, setup, Workers/Pages, crawlability)
  - docs/email-routing-setup.md (consumes the token below)
---

## Recipe relocated

The reusable Cloudflare token recipe (least-privilege philosophy, User-vs-Account distinction, the token creation flow, the permission matrix, Bitwarden storage and retrieval, the "things to NEVER tick" list, and the revocation runbook) is now the single canonical source at:

`dotfiles/docs/runbooks/cloudflare-control.md`

That runbook also adds the hybrid two-token model, the Account API token step-by-step, the Workers and Pages create/deploy permissions, the API read/write recipes, and the per-site crawlability checklist. Read it there; do not re-derive any of it here.

This file keeps ONLY the hoiboy.uk-specific execution evidence below, because it records what was actually done on this site (the real token created and the Brevo email DNS records it wrote).

## Execution evidence - 2026-05-08

Token created and used during the email-routing-setup execution:

- **Name**: `hoiboy-uk-cloudflare-automation`
- **Type**: Account API token (NOT User token - see the User-vs-Account distinction in the dotfiles canonical runbook; the misclassification cost ~5 minutes of debugging "Invalid API Token" before we realised)
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
- **Rotation reminder**: 2026-08-06 (rotate at 2026-07-27 with 10-day buffer). NOTE: this token is being retired into the two-token model per the replacement procedure in the dotfiles canonical runbook.

**Status**: ACTIVE (slated for replacement).

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
