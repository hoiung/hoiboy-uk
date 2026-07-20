---
title: Brevo API + SMTP setup runbook (transactional email for hoiboy.uk)
purpose: Canonical recipe for setting up Brevo as the outbound email layer for hoiboy.uk, fully API-driven where possible. Captures the API key vs SMTP key distinction, Brevo's 'separate SMTP login' gotcha, the actual API endpoints (with the v3 path quirks), domain authentication two-step, sender registration requirement, transactional template push, and rotation cadence. Designed to be reproducible for paid clients.
last_verified: 2026-05-08
related:
  - docs/email-routing-setup.md (the orchestrating runbook - Cloudflare inbound + Brevo outbound)
  - docs/cloudflare-api-token-setup.md (companion, same scoped-credential discipline)
  - docs/cal-eu-setup.md (Path B Worker uses Brevo API to send transactional emails)
---

This is the runbook for setting up Brevo (formerly Sendinblue) as the outbound transactional email service for `hoiboy.uk`. **Mostly API-driven.** The only steps that genuinely require the browser are the initial signup, the first API + SMTP key generation (chicken-and-egg - the API to manage keys requires a key), and Gmail "Send mail as" (Gmail has no API for adding send-as identities).

When we set up Brevo for paid clients, this runbook is the canonical path. Everything is reproducible.

## Brevo's free tier and why we picked it

- **300 outbound emails/day, perpetual free, no card on file.** For solo consultancy reply traffic + Cal.com-driven booking emails this never bites.
- **Domain auth via DKIM (CNAME-based)** - proper deliverability, not the "via brevo.com" footer of less-hardened SaaS senders.
- **Free transactional templates** with `{{ params.X }}` substitution syntax - server-side templating means the Cloudflare Worker just sends `{template_id, params}` instead of constructing email bodies.
- **Free webhooks** for delivery / open / click events - useful for the eventual "did the prospect open the booking confirmation?" telemetry layer.
- **Generous SMTP relay** for Gmail "Send mail as" outbound.

Alternatives if Brevo's policy ever changes: Resend (3,000/month free), SendGrid (100/day free), Mailgun Flex (100/day trial). Brevo is the most generous as of 2026-05-08.

## The three credentials Brevo issues

Brevo has **three distinct credential types** that are easy to confuse. They are not interchangeable.

| Credential | Format | Used by | Where to find / generate |
|---|---|---|---|
| **API key** (HTTP) | `xkeysib-<88 chars>` (89 total) | The Cloudflare Worker. Anything calling Brevo's HTTP REST API. | Brevo dashboard → SMTP & API → **API Keys** tab |
| **SMTP key** | `xsmtpsib-<82 chars>` (90 total - Standard variant) | Gmail "Send mail as". Anything sending via Brevo's SMTP relay. | Brevo dashboard → SMTP & API → **SMTP** tab |
| **MCP server API key** | (variable; Brevo's MCP transport) | Claude Code / Claude Desktop registering Brevo as an MCP server | Same API Keys tab; "Generate MCP server API key" button |

**Cloudflare Workers cannot speak SMTP** (no raw socket support in the Workers runtime), so they must use the HTTP API key. **Gmail Send-as cannot speak HTTP** (it's an SMTP client by design), so it needs the SMTP key. We need both for Path B.

**MCP key**: skip unless you're integrating Brevo into a steady-state Claude Code workflow (frequent ongoing email management). For one-off setup or production Worker use, regular API key is sufficient.

### Standard vs Short SMTP key variant

When generating the SMTP key, Brevo offers two variants:

| Variant | Length | Use when |
|---|---|---|
| Standard | 64 chars | Always. Production-grade entropy, paste from password manager. |
| Short | 15 chars | Legacy systems with credential-length limits. None of our consumers have this. |

**Always pick Standard.** Short exists for compatibility, not for security.

## Setup procedure

### Phase A - Browser-only (≤2 min, cannot be automated)

1. Sign up at https://www.brevo.com with your account email (free tier, no card).
2. During onboarding, pick:
   - Industry: closest match (not load-bearing)
   - Monthly volume: <500 / "just getting started"
   - Goal: "Send transactional emails"
3. Skip any paid-tier upsell prompts.

### Phase B - Domain authentication (browser + DNS)

This step requires DNS records. The DNS half is API-driven via Cloudflare; only the Brevo "Add domain" + "Authenticate" clicks are browser. See `docs/cloudflare-api-token-setup.md` for the Cloudflare API token + DNS API procedure.

1. Brevo dashboard → top-right account name → **Senders, Domains & Dedicated IPs** → **Domains** tab → **Add a domain** → `hoiboy.uk`.
2. Pick **Authenticate the domain yourself** (not the auto-add option - gives full control + audit trail).
3. Brevo shows 4 DNS records to add:

| Record | Type | Name | Content |
|---|---|---|---|
| Brevo verification | TXT | `@` (root) | `brevo-code:<32-hex-chars>` (specific to your account) |
| DKIM 1 | CNAME | `brevo1._domainkey` | `b1.<zone>.dkim.brevo.com` |
| DKIM 2 | CNAME | `brevo2._domainkey` | `b2.<zone>.dkim.brevo.com` |
| DMARC | TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com` |

   Note: **Brevo uses CNAME-based DKIM**, NOT TXT-based DKIM. CNAME-based is better practice - Brevo can rotate the actual signing key without forcing you to update DNS again.

   Note: the DMARC `rua=` value points to `rua@dmarc.brevo.com` (Brevo aggregates DMARC reports for you in the dashboard). If you want raw DMARC reports yourself, set `rua=mailto:dmarc@hoiboy.uk` instead - but Brevo's aggregation is more useful than reading raw XML.

4. **Also edit the existing SPF record** (Cloudflare Email Routing already created one; do NOT add a second). Append Brevo's include:

   ```
   v=spf1 include:_spf.mx.cloudflare.net include:spf.brevo.com ~all
   ```

   Multiple SPF records on the same name break SPF validation entirely. Edit the existing one.

5. After DNS records are live (verify via DoH lookup - see `docs/cloudflare-api-token-setup.md` for the exact curl), trigger Brevo's verification:

   - **UI path**: Brevo dashboard → Domains → click **Authenticate this email domain** for `hoiboy.uk`.
   - **API path** (recommended for automation):
     ```bash
     curl -s -X PUT -H "api-key: $BREVO_API_KEY" -H "content-type: application/json" \
       "https://api.brevo.com/v3/senders/domains/hoiboy.uk/authenticate"
     ```
     Returns `{"domain_name":"hoiboy.uk","message":"Domain has been authenticated successfully."}` on success.

6. Verify domain status:

   ```bash
   curl -s -H "api-key: $BREVO_API_KEY" "https://api.brevo.com/v3/senders/domains" | jq
   ```

   Look for `authenticated: true` and `verified: true` on `hoiboy.uk`.

### Phase C - Generate API key + SMTP key (browser, ≤2 min)

1. Brevo dashboard → top-right account name → **SMTP & API**.
2. **API Keys** tab → **Generate a new API key** → name `hoiboy-uk-worker` → copy the `xkeysib-...` value.
3. **SMTP** tab → **Generate a new SMTP key** → name `gmail-send-as` → variant **Standard** → copy the `xsmtpsib-...` value.
4. Note the **SMTP login** shown on the SMTP page. It is **NOT your Brevo account email**. It is a Brevo-issued address like `aaa99a001@smtp-brevo.com`. This is critical - using your Brevo account email as SMTP login fails with `5.7.8 Authentication failed` (we hit this 2026-05-08).

### Phase D - Store both in Bitwarden

Same pattern as `docs/cloudflare-api-token-setup.md`:

| Field | API key item | SMTP key item |
|---|---|---|
| Item type | Login | Login |
| Name | `brevo-hoiboy-uk-worker-api` | `brevo-hoiboy-uk-smtp` |
| Username | `hoiboyuk@gmail.com` (Brevo account login - identifies which Brevo account owns this key) | `aaa99a001@smtp-brevo.com` (the actual SMTP relay login Brevo issued) |
| Password | `xkeysib-...` | `xsmtpsib-...` |
| URI | `https://app.brevo.com/settings/keys/api` | `https://app.brevo.com/settings/keys/smtp` |
| Notes | Key name, scope, creation date, expiry target, list of consumers | Same shape |

Username field meaning is consistent across both: "the login you'd use against the corresponding system". For HTTP API there's no username (key is a header); we use the Brevo account email as identifier-of-ownership.

### Phase E - Retrieve from BW + verify (API-driven)

```bash
# In your terminal (not Claude's), unlock Bitwarden:
bw unlock --raw
# Paste BW_SESSION token to agent. Agent persists it:
echo -n "<BW_SESSION>" > /tmp/.bw-session
chmod 600 /tmp/.bw-session

# Agent retrieves both:
export BW_SESSION="$(cat /tmp/.bw-session)"
source ~/DevProjects/lab-ops/scripts/utils/bw-helpers.sh
bw sync >/dev/null 2>&1  # MANDATORY for fresh items
export BREVO_API_KEY="$(bw_get brevo-hoiboy-uk-worker-api)"  # secret-allow (BW retrieval, not a literal secret)
export BREVO_SMTP_KEY="$(bw_get brevo-hoiboy-uk-smtp)"
export BREVO_SMTP_LOGIN="$(bw get item brevo-hoiboy-uk-smtp | python3 -c \
  'import json,sys; print(json.load(sys.stdin)[\"login\"][\"username\"])')"

# Verify API key:
curl -s -H "api-key: $BREVO_API_KEY" "https://api.brevo.com/v3/account" | jq '.email'
# Should return your Brevo account email.

# Verify SMTP key (TLS + AUTH probe, no actual send):
python3 -c "
import os, smtplib
s = smtplib.SMTP('smtp-relay.brevo.com', 587, timeout=10)
s.ehlo(); s.starttls(); s.ehlo()
s.login(os.environ['BREVO_SMTP_LOGIN'], os.environ['BREVO_SMTP_KEY'])
print('OK')
s.quit()
"
# Should print 'OK' and exit 0.
```

### Phase F - Register the sender address

**Domain auth is necessary but not sufficient.** Brevo requires individual sender addresses to also be registered, even on authenticated domains. Without this step, Brevo rejects template creation and email sends with `Sender is invalid / inactive`.

```bash
curl -s -X POST -H "api-key: $BREVO_API_KEY" -H "content-type: application/json" \
  -d '{"name":"Hoi","email":"hello@hoiboy.uk"}' \
  "https://api.brevo.com/v3/senders"
```

Returns `{"id": <number>, "spfError": false, "dkimError": false}` on success. The `spfError`/`dkimError` flags come back `false` ONLY if domain authentication is in place - useful sanity check.

If you skip domain auth and try to register a sender, Brevo sends a verification email to that address and you must click the link. With domain auth, registration is silent and immediate.

### Phase G - Push transactional templates

The Hoi-voice templates live as canonical text in `docs/cal-eu-setup.md`. Push them as Brevo templates so the Cloudflare Worker can reference them by ID instead of hardcoding bodies.

**Endpoint**: `POST /v3/smtp/templates` (with slash, NOT `/smtpTemplates` camelCase - that path returns 404, we hit this 2026-05-08).

```bash
curl -s -X POST -H "api-key: $BREVO_API_KEY" -H "content-type: application/json" \
  -d '{
    "templateName": "C - 1h reminder",
    "subject": "In an hour - Google Meet link inside",
    "sender": {"name": "Hoi", "email": "hello@hoiboy.uk"},
    "htmlContent": "<p>Hi {{ params.attendee }},</p><p>We are on in an hour ({{ params.event_time }} UK).</p><p>Google Meet: {{ params.meeting_url }}</p><p>Hoi</p>",
    "isActive": true
  }' \
  "https://api.brevo.com/v3/smtp/templates"
```

Returns `{"id": <number>}` - capture this; the Worker will reference the template by ID.

**Brevo placeholder syntax**: `{{ params.<key> }}`. The Worker passes `params: {attendee: "...", event_time: "...", ...}` in the send call; Brevo substitutes server-side. Don't double-substitute on the Worker side - pass raw user data, let Brevo handle templating.

For the canonical Hoi-voice template texts (subjects + bodies + which params each one consumes), see `docs/cal-eu-setup.md` § "The 5 Hoi-voice email templates".

### Phase H - Send a test email (proves end-to-end)

```bash
curl -s -X POST -H "api-key: $BREVO_API_KEY" -H "content-type: application/json" \
  -d '{
    "templateId": <id-from-phase-G>,
    "to": [{"email": "hoiboyuk@gmail.com", "name": "Test recipient"}],
    "params": {
      "attendee": "Test recipient",
      "event_time": "now (test)",
      "meeting_url": "https://meet.google.com/test-link"
    }
  }' \
  "https://api.brevo.com/v3/smtp/email"
```

Returns `{"messageId": "<...>"}` on accept. Email arrives in `hoiboyuk@gmail.com` within seconds.

**Verify in Gmail**: open the email, "Show original" (3-dot menu), confirm:
- `SPF: PASS` (with `mailfrom=spf.brevo.com`)
- `DKIM: PASS` with `d=hoiboy.uk` (proves CNAME-based DKIM is signing as our domain, not Brevo's)
- `DMARC: PASS`

If any of these fail, the email layer is not production-ready. SPF can be debugged at https://www.mail-tester.com - send a test, get a 9/10 or higher score.

### Phase I - Gmail "Send mail as" (browser only, ~5 min)

Gmail has no API for adding a send-as identity. UI required. Multiple gotchas where Gmail auto-fills the wrong values from your MX records - read each step carefully.

#### Step I-1 - Open Send-as setup

1. Go to https://mail.google.com (logged in as `hoiboyuk@gmail.com`)
2. Top-right **cog** ⚙ → **See all settings**
3. **Accounts and Import** tab
4. **Send mail as:** section → **Add another email address**

#### Step I-2 - Identity

A popup opens with three fields:

- **Name:** `Senh Hoi Ung` (or `Hoi`, your call - appears in recipients' From: dropdown)
- **Email address:** `hello@hoiboy.uk`
- **Treat as an alias:** ✅ **TICK**

##### "Treat as an alias" - what it actually means

Gmail's documentation is sparse here. The actual semantics:

| State | Meaning | Use when |
|---|---|---|
| ✅ Ticked (alias) | Gmail treats `hello@hoiboy.uk` as the SAME PERSON as the Gmail account. Replies thread normally; no `Sender:` header added. | The send-as address is YOU (different brand/domain, same person). This is our case. |
| ❌ Unticked (separate identity) | Gmail adds a `Sender: hoiboyuk@gmail.com` header revealing your actual Gmail account, then displays "via gmail.com" in some clients. Use for delegated sending (assistant on behalf of CEO, service account on behalf of role). | The send-as address is SOMEONE ELSE you have permission to send for. |

For solo consultancy where `hello@hoiboy.uk` IS you: **TICK**. Untick is a delegation pattern, not a deliverability pattern. The "via brevo.com" annotation people sometimes worry about is controlled by **DKIM signing alignment** (handled at Brevo domain auth level), NOT by this checkbox. With proper DKIM (which we have), there's no "via" annotation regardless of this setting.

Click **Next Step**.

#### Step I-3 - SMTP credentials

⚠️ **Gmail auto-fills the WRONG values** because it reads your MX records to pre-populate. You must override all three.

| Field | Gmail auto-fill (WRONG) | Correct value | Source |
|---|---|---|---|
| SMTP Server | `route3.mx.cloudflare.net` (or similar `route1/2/3.mx.cloudflare.net`) | `smtp-relay.brevo.com` | Hardcoded - Brevo's relay |
| Port | `587` ✅ | `587` | Hardcoded - leave as-is |
| Username | `hello` (just the local part) | `aaa99a001@smtp-brevo.com` (your specific value differs) | BW item `brevo-hoiboy-uk-smtp` → **username field** |
| Password | (empty) | The SMTP key (`xsmtpsib-...`) | BW item `brevo-hoiboy-uk-smtp` → **password field** |
| Secured connection | TLS ✅ | TLS | Leave as-is |

Why Gmail's auto-fill is wrong: Cloudflare Email Routing's MX records (`route1/2/3.mx.cloudflare.net`) are **inbound-only servers** - they accept incoming mail for forwarding but do NOT accept SMTP connections for outbound. Gmail can't tell from DNS alone. We override with the actual outbound SMTP relay.

⚠️ **The Username gotcha:** Brevo issues a separate SMTP login (`aaaXXXXXX@smtp-brevo.com`) shown on the SMTP page in your Brevo dashboard. Using your Brevo account email (`hoiboyuk@gmail.com`) returns `5.7.8 Authentication failed`. The BW item we created in Phase D already has the correct value in the username field - paste from there.

⚠️ **There's also an optional "Specify a different reply-to address" field** in the identity step. **LEAVE BLANK.** With it blank, replies go to the From: address (`hello@hoiboy.uk`) which routes through Cloudflare → Gmail anyway. Putting `hoiboyuk@gmail.com` here would defeat the Reply-To leak fix we applied at the Brevo template layer. Three concepts to distinguish:

- **Treat as alias** (Gmail) - same-person flag, controls the `Sender:` header
- **Reply-to field** (Gmail Send-as) - overrides Reply-To header for compose-time sends from Gmail
- **Brevo template `replyTo`** - overrides Reply-To for transactional sends from the Worker

All three must point to `hello@hoiboy.uk` (or be left blank where blank means "use From"). Never put the personal Gmail in any of them.

Click **Add Account**.

#### Step I-4 - Verify ownership

Gmail sends a verification email to `hello@hoiboy.uk`. Path:

1. Brevo doesn't see this email - it goes via Google's outbound to Cloudflare's MX
2. Cloudflare Email Routing forwards it to `hoiboyuk@gmail.com`
3. You see a Gmail message from `Gmail Team` titled "Gmail Confirmation - Send Mail as hello@hoiboy.uk"
4. Click the verification link inside (or copy the confirmation code into the popup)

This step doubles as an **end-to-end inbound test**: if the verification email lands, the Cloudflare Email Routing layer is healthy.

#### Step I-5 - Set as default + reply behaviour

After verification, Gmail returns you to **Settings → Accounts and Import**.

1. Under **Send mail as:** - find `Senh Hoi Ung <hello@hoiboy.uk>` → click **make default**
2. Under **When replying to a message:** - pick **Reply from the same address the message was sent to**

The default-default ensures any new compose starts From: `hello@hoiboy.uk` (no dropdown click needed each time). The reply-from-same-address ensures replies to mail received at `hello@hoiboy.uk` go out From: `hello@hoiboy.uk` automatically.

Optional but recommended:

3. Under **Sender information** (if shown) - pick **Show this address only (hello@hoiboy.uk)** to suppress any "sent by hoiboyuk@gmail.com" annotation in clients that respect it.

#### Step I-6 - Round-trip test

This proves the entire stack - inbound + outbound + DKIM signing - under real-world load.

1. From your phone or any non-Gmail account, send TO `hello@hoiboy.uk` (subject and body anything)
2. Wait ~30 sec - should arrive in `hoiboyuk@gmail.com` Gmail inbox
3. **Reply** from Gmail. The From: dropdown should auto-show `hello@hoiboy.uk` (default + reply-from-same-address combined)
4. **Send** the reply
5. **Check** the external account - reply should appear From: `hello@hoiboy.uk`, no "via gmail.com" or "via brevo.com" annotations

For full verification, "Show original" the received reply on the external side and confirm:
- `signed-by: hoiboy.uk` (DKIM PASS - proves outbound DKIM signing works)
- `mailed-by: smtp-relay.brevo.com` (proves it went through Brevo, not via Gmail's own SMTP)
- TLS encrypted in transit
- No `Sender:` header revealing `hoiboyuk@gmail.com`

If any check fails, debug at https://www.mail-tester.com - send a test, get a 9/10+ score, fix anything that drops points (typically SPF alignment if you forgot to merge include:spf.brevo.com into the existing record, or DKIM if the CNAMEs aren't propagating).

## Rotation cadence

Brevo does **not** offer built-in TTL on API or SMTP keys (Cloudflare does; Brevo doesn't). Rotation is calendar-driven.

| Credential | Default rotation | Rotation procedure |
|---|---|---|
| API key | 90 days | Generate new key in Brevo UI → update BW item → update Worker secret binding (`wrangler secret put BREVO_API_KEY`) → revoke old key |
| SMTP key | 90 days | Generate new key → update BW item → update Gmail Send-as SMTP password (UI: Settings → Accounts → Send mail as → edit) → revoke old key |
| MCP key | n/a (not currently used) | If activated later, same 90-day cadence |

**Calendar reminders are mandatory** - Brevo won't email you about expiring keys. Set 90-day calendar reminder when a key is generated.

**On rotation: 10-day buffer.** Generate new key, update consumers, verify everything works, THEN revoke old. Don't revoke first and risk email outage during cutover.

## Bitwarden retrieval pattern (consistent across all our credential runbooks)

```bash
# Once per session:
echo -n "<BW_SESSION token from `bw unlock --raw`>" > /tmp/.bw-session
chmod 600 /tmp/.bw-session

# Per command:
export BW_SESSION="$(cat /tmp/.bw-session)"
source ~/DevProjects/lab-ops/scripts/utils/bw-helpers.sh
bw sync >/dev/null 2>&1  # MANDATORY for fresh items (Bitwarden cache invalidation)
export BREVO_API_KEY="$(bw_get brevo-hoiboy-uk-worker-api)"  # secret-allow (BW retrieval, not a literal secret)
```

The `bw sync` is non-optional for items created in the same session - without it, `bw_get` returns "item not found" misleadingly. Captured as auto-memory `feedback_bw_sync_required_for_fresh_items.md`.

## Execution evidence - 2026-05-08

| What | Value |
|---|---|
| Brevo account | `hoiboyuk@gmail.com` (free tier) |
| Domain | `hoiboy.uk` - authenticated + verified via API |
| Sender | `Hoi <hello@hoiboy.uk>` - id 2, active, SPF + DKIM passing |
| API key | `xkeysib-...` (89 chars) - BW: `brevo-hoiboy-uk-worker-api` |
| SMTP key | `xsmtpsib-...` (90 chars, Standard variant) - BW: `brevo-hoiboy-uk-smtp` |
| SMTP login | `aaa99a001@smtp-brevo.com` (Brevo-issued, NOT account email) |
| Templates pushed | 6 transactional templates (IDs 1-6) - Hoi-voice, mapped to Cal.com booking lifecycle. Saved at `/tmp/brevo-template-ids.json` |
| First test send | 2026-05-08 13:49 UTC - `messageId: <202605081349.74248579397@smtp-relay.mailin.fr>` - delivered to `hoiboyuk@gmail.com` From `Hoi <hello@hoiboy.uk>` |
| Rotation reminder | 2026-08-06 (90 days, both keys rotate together) |

### The 6 templates pushed

| ID | Name | Trigger (Cal.com event) | Recipient |
|---|---|---|---|
| 1 | A - Booking confirmation | `BOOKING_CREATED` | Attendee |
| 2 | B - 24h reminder | cron: 24h before event | Attendee |
| 3 | C - 1h reminder | (dormant - Worker does NOT fire) | Attendee |
| 4 | D - Reschedule confirmation | `BOOKING_RESCHEDULED` | Attendee |
| 5 | E - Cancellation acknowledgement | `BOOKING_CANCELLED` | Attendee |
| 6 | Operator - 2 hour pre-call brief | cron: 2 hours before event | Operator (`hello@hoiboy.uk`) |

**Note on cadence iteration**: template 6 was originally drafted at T-15min ("starting in 15 min" framing), bumped to T-30min, then T-1h, settled at **T-2h** (2026-05-08 design iteration with the host). Template subject + body were PUT-updated each time via `PUT /v3/smtp/templates/6` with `{subject, htmlContent}` in body - confirms Brevo's PUT endpoint accepts partial updates (other fields like `replyTo`, `sender`, `templateName` preserved). Template 6 also gained a `distinct_roles` line in body when the Cal.com event-type added the matching booking field 2026-05-08.

The Worker (Path B in `docs/cal-eu-setup.md`) will consume these template IDs.

## Lessons learned (the things that cost real time)

1. **`/v3/smtpTemplates` does NOT exist.** The correct path is `/v3/smtp/templates` (with slash). Brevo's older Sendinblue v3 API used the camelCase path; v3 in 2026 uses slash-separated. Sweep with multiple variants when in doubt - `404 Invalid route/ method passed` is the diagnostic signal that you have the wrong path.
2. **Domain authentication does NOT auto-validate just because DNS records exist.** Brevo needs the explicit "authenticate" trigger (UI button OR `PUT /v3/senders/domains/{domain}/authenticate`). DNS is necessary but not sufficient.
3. **Sender registration is required even with domain auth.** `POST /v3/senders` is non-optional. Without it: `Sender is invalid / inactive` on every send.
4. **Brevo SMTP login is NOT your account email.** It's a Brevo-issued generated address `aaaXXXXXX@smtp-brevo.com` shown on the SMTP tab. The runbook in `docs/email-routing-setup.md` originally said "your Brevo account email" - that was wrong (or Brevo changed it), corrected 2026-05-08.
5. **API key vs SMTP key vs MCP key are three different credentials.** The dashboard offers all three on adjacent buttons. Be deliberate about which you generate. Length: API key ≈ 89 chars, SMTP key (Standard) ≈ 90 chars - close enough to be confused on visual inspection.
6. **MCP server keys are for steady-state Claude Code integration**, not one-shot setup. Skip them unless you're actively using Brevo from Claude Code on a recurring basis.
7. **`bw sync` after creating fresh BW items is non-optional.** Otherwise `bw_get` returns "item not found" misleadingly even though the item exists.
8. **Cloudflare Workers cannot speak SMTP.** No raw socket support in the runtime. Workers use the HTTP API; Gmail Send-as uses SMTP. We need both keys for Path B.
9. **Brevo templates use `{{ params.X }}` substitution on the server.** Don't double-substitute on the Worker side. Pass raw user data, let Brevo render.
10. **Empty params render as blank, not error.** During the first test send, `meeting_url` was not passed and the line "Google Meet:" rendered with nothing after the colon. Brevo doesn't fail the send; it just leaves the placeholder empty. Worker must always pass all expected params, or templates need defensive defaults.
11. **Reply-To defaults to the Brevo account email, NOT the From: address.** Hit this 2026-05-08: first test send had `from: Hoi <hello@hoiboy.uk>` but `reply-to: hoiboyuk@gmail.com`. For brand-grade outbound, Reply-To MUST match From - leaks the operator's personal Gmail otherwise. Fix: either set `replyTo` per-template via `PUT /v3/smtp/templates/{id}` body `{"replyTo":"hello@hoiboy.uk"}`, or set `replyTo` per-send in `POST /v3/smtp/email`. We patched all 6 templates with the correct Reply-To. Worker should also set `replyTo` defensively in case template defaults change.

12. **Gmail Send-as auto-fills the WRONG SMTP server.** It reads MX records and pre-populates `route3.mx.cloudflare.net` (Cloudflare Email Routing's inbound MX). Cloudflare's MX is inbound-only - it cannot send. You MUST override to `smtp-relay.brevo.com`. Same gotcha for Username field: Gmail pre-fills just `hello` (local part of address being added), not the actual SMTP login.
13. **Gmail "Treat as alias" semantics are widely misunderstood.** The right value depends on whether the send-as address represents the SAME PERSON or a delegated identity. For solo-operator brand emails (`hello@hoiboy.uk` IS Hoi): TICK. For "assistant sends on behalf of CEO" patterns: untick. The "via" annotation is controlled by DKIM alignment, NOT by this checkbox - earlier draft of this runbook had this wrong, corrected 2026-05-08.
14. **Three Reply-To controls exist, all need consistent values.** (a) Gmail Send-as Reply-To field, (b) Brevo template `replyTo` field, (c) Brevo per-send `replyTo` override. All three must point to `hello@hoiboy.uk` (or be left blank where blank means "use From"). Putting the personal Gmail in any of them leaks the operator address. Document explicitly when teaching this pattern to clients - it's the single most error-prone deliverability config.

### Reply-To override pattern

Template-level (sets default Reply-To for all sends using this template):

```bash
curl -s -X PUT -H "api-key: $BREVO_API_KEY" -H "content-type: application/json" \
  -d '{"replyTo":"hello@hoiboy.uk"}' \
  "https://api.brevo.com/v3/smtp/templates/$TEMPLATE_ID"
```

Returns HTTP 204 (no body) on success. Confirm via `GET /v3/smtp/templates/{id}` - look for `"replyTo": "hello@hoiboy.uk"` in response.

Per-send override (overrides template default for a specific send):

```bash
curl -s -X POST -H "api-key: $BREVO_API_KEY" -H "content-type: application/json" \
  -d '{
    "templateId": 3,
    "to": [...],
    "replyTo": {"email": "hello@hoiboy.uk", "name": "Hoi"},
    "params": {...}
  }' \
  "https://api.brevo.com/v3/smtp/email"
```

## Reproduction checklist (for the next client / instance)

- [ ] Phase A: Brevo signup with destination email
- [ ] Phase B: Add domain → choose "Authenticate yourself" → 4 DNS records added in registrar (use Cloudflare API token if registrar is Cloudflare; see `docs/cloudflare-api-token-setup.md`) → existing SPF appended (don't duplicate) → DoH propagation verified → `PUT /senders/domains/{name}/authenticate` returns success → `GET /senders/domains` shows `authenticated: true`
- [ ] Phase C: API key + SMTP key (Standard variant) generated; SMTP login noted
- [ ] Phase D: Both stored in BW with the documented item structure
- [ ] Phase E: Retrieved from BW; both verified via curl + Python smtplib probe
- [ ] Phase F: Sender address registered (`POST /senders`); `spfError: false, dkimError: false`
- [ ] Phase G: Templates pushed; IDs captured to `/tmp/brevo-template-ids.json` or equivalent
- [ ] Phase H: Test send delivered; SPF/DKIM/DMARC PASS confirmed in raw headers
- [ ] Phase I: Gmail Send-as configured with the Brevo SMTP login (NOT account email); reply-from-same-address default set; round-trip test passed
- [ ] 90-day rotation reminder set in calendar
- [ ] Worker (Path B) deployed (separate runbook - `docs/cal-eu-setup.md` § Path B)

## Cross-references

- `docs/email-routing-setup.md` - orchestrating runbook (Cloudflare inbound + Brevo outbound)
- `docs/cloudflare-api-token-setup.md` - companion runbook, same scoped-credential discipline
- `docs/cal-eu-setup.md` - § "Path B" consumes Brevo API key for Worker-driven transactional sends
- Brevo developer hub: https://developers.brevo.com/
- Brevo API reference index: https://developers.brevo.com/reference
