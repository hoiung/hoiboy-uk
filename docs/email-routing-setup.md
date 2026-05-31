# Email Routing Setup: hello@hoiboy.uk

Operator runbook for the free DIY email stack on `hoiboy.uk`. Goal: receive at `hello@hoiboy.uk` (forwarded to `hoiboyuk@gmail.com`) and reply back AS `hello@hoiboy.uk` from inside Gmail. Zero ongoing subscription cost. No enterprise email account.

**Status as of 2026-05-08**: live and verified end-to-end. SPF + DKIM + DMARC all PASS in real-world delivery. See § "Execution evidence" at the bottom.

This runbook is the **orchestrating overview**. The lower-level mechanics - Cloudflare API tokens, Brevo API setup, transactional templates - live in dedicated runbooks (cross-referenced inline). When automating this for paid clients, this is the entry point; consumers read the per-system runbooks for the specifics.

Two halves:

- **Inbound (receive)**: Cloudflare Email Routing - free tier, included with Cloudflare DNS hosting. See `docs/cloudflare-api-token-setup.md` for the DNS API procedure + hoiboy.uk token history; the generic token recipe now lives in `dotfiles/docs/runbooks/cloudflare-control.md`.
- **Outbound (send-as)**: Brevo SMTP relay - 300 emails/day free forever + Gmail "Send mail as" feature. See `docs/brevo-api-setup.md` for the API key + SMTP key + transactional templates procedure.

## Why this stack

- Cloudflare Email Routing forwards but does NOT host an SMTP server, so it cannot send replies. That gap needs a free SMTP relay.
- Brevo (formerly Sendinblue) gives 300 outbound emails/day on the perpetual-free tier with no card on file. For a solo consultancy doing low-volume reply-driven email, 300/day never bites.
- Alternatives if Brevo policy changes: Resend (3,000/month free), SendGrid (100/day free), Mailgun Flex (100/day free trial), Forward Email (limited free with paid send-from upgrade). Brevo is the most generous as of 2026-05.

## Inbound: Cloudflare Email Routing

Pre-req: hoiboy.uk DNS is hosted on Cloudflare (already true per existing setup).

1. Open Cloudflare dashboard -> hoiboy.uk -> Email -> Email Routing.
2. Enable Email Routing. Cloudflare auto-adds the required MX + SPF DNS records (3 MX records + 1 TXT). Approve.
3. Custom address: `hello` -> destination address: `hoiboyuk@gmail.com`. Click "Add and save".
4. Verify the destination: Cloudflare emails `hoiboyuk@gmail.com` with a verification link. Click it.
5. (Optional) Catch-all: route `*@hoiboy.uk` -> `hoiboyuk@gmail.com` so any future address works without per-alias setup.

Test: send an email from any external account to `hello@hoiboy.uk`; it should arrive in `hoiboyuk@gmail.com` inbox within seconds.

## Outbound: Brevo SMTP relay + Gmail "Send mail as"

### Step 1: Brevo signup + domain auth

**See `docs/brevo-api-setup.md` § Phase A + Phase B for the full procedure (mostly API-driven).**

Summary:

1. Sign up at https://www.brevo.com (free, no card).
2. In Brevo dashboard -> Senders, Domains & Dedicated IPs -> Domains -> Add `hoiboy.uk` -> Authenticate the domain yourself.
3. Brevo gives 4 DNS records to add (Brevo migrated to **CNAME-based DKIM** - better than the older TXT-based DKIM because Brevo can rotate signing keys without forcing DNS edits):
    - `@` TXT - `brevo-code:<32-hex>` (account-specific verification)
    - `brevo1._domainkey` CNAME -> `b1.<zone>.dkim.brevo.com` (DKIM 1)
    - `brevo2._domainkey` CNAME -> `b2.<zone>.dkim.brevo.com` (DKIM 2)
    - `_dmarc` TXT -> `v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com` (Brevo aggregates DMARC reports for you)
4. Add all 4 records in Cloudflare DNS. **Proxy must be OFF for the CNAMEs** (orange cloud breaks DKIM). Use the API path documented in `docs/cloudflare-api-token-setup.md` for reproducibility.
5. Trigger Brevo's verification - either UI button "Authenticate this email domain" OR API: `PUT /v3/senders/domains/hoiboy.uk/authenticate` (see brevo-api-setup.md § Phase B).

**SPF: edit existing record, do NOT add second.** Cloudflare Email Routing's SPF (`v=spf1 include:_spf.mx.cloudflare.net ~all`) needs Brevo's include appended:

```
v=spf1 include:_spf.mx.cloudflare.net include:spf.brevo.com ~all
```

Multiple SPF records on the same name break SPF validation entirely.

**Sender registration is required even with domain auth.** Brevo's `POST /v3/senders` registers `hello@hoiboy.uk` as an active sender. Without this step, sends fail with `Sender is invalid / inactive`. See brevo-api-setup.md § Phase F.

### Step 2: Brevo SMTP credentials

1. Brevo dashboard -> SMTP & API -> SMTP tab.
2. Server: `smtp-relay.brevo.com`
3. Port: 587
4. **Login**: NOT your Brevo account email - Brevo issues a separate SMTP-relay address shown on this page, format `aaaXXXXXX@smtp-brevo.com` (e.g. `aaa99a001@smtp-brevo.com`). Using the account email here returns `5.7.8 Authentication failed`. (Originally this runbook said "your Brevo account email" - that was wrong, corrected 2026-05-08 after a real auth failure during execution.)
5. SMTP key: click **Generate a new SMTP key**, pick **Standard variant** (64-char body, 90 chars total), copy the `xsmtpsib-...` value. Save in BW immediately - Brevo only shows it once.

Both the SMTP login and SMTP key are stored in BW item `brevo-hoiboy-uk-smtp` (login in username field, key in password field). See `docs/brevo-api-setup.md` § Phase D for the full BW pattern.

### Step 3: Gmail "Send mail as"

**See `docs/brevo-api-setup.md` § Phase I for the full step-by-step including all Gmail auto-fill gotchas.** Summary here:

1. In `hoiboyuk@gmail.com` -> Settings (cog) -> See all settings -> Accounts and Import -> Send mail as -> "Add another email address".
2. Name: `Senh Hoi Ung` (or `Hoi`, your call).
3. Email: `hello@hoiboy.uk`.
4. **Tick** "Treat as an alias" - the send-as address belongs to the same person as the Gmail account. (Original guidance in this runbook said untick, that was wrong; the "via" annotation people worry about is controlled by DKIM alignment, not this checkbox. Corrected 2026-05-08.)
5. **Leave** "Specify a different reply-to address" BLANK - replies should go to `hello@hoiboy.uk` which already routes back to Gmail. Putting the personal Gmail in this field would leak the operator address.
5. Next -> SMTP server settings:
    - SMTP Server field: `smtp-relay.brevo.com`
    - Port field: 587
    - Username field: **the Brevo SMTP login** (e.g. `aaa99a001@smtp-brevo.com` - NOT your Brevo account email; see Step 2)
    - SMTP-key field: the SMTP key generated in Step 2
    - Secured connection using TLS (default).

⚠️ **Gmail auto-fills the WRONG SMTP server.** Gmail reads MX records and pre-populates `route3.mx.cloudflare.net` (or similar). Cloudflare's MX is INBOUND only - you MUST override. Same gotcha for Username field: Gmail pre-fills just `hello` (the local part), not the actual SMTP login. Override all four fields explicitly.

6. Save. Gmail sends a verification email to `hello@hoiboy.uk`, which Cloudflare forwards back to `hoiboyuk@gmail.com`. Click the verification link.
7. After verification, set `hello@hoiboy.uk` as the **default** Send-as (under Send mail as: section, click `make default` next to it).
8. Test: compose a new email in Gmail; in the From: dropdown, pick `hello@hoiboy.uk`. Send to a different external address (your personal Gmail, a friend, or a temp address). Verify the received email shows From: `hello@hoiboy.uk`.

### Step 4: default From: address

In Gmail Settings -> Accounts and Import -> "When replying to a message" -> select "Reply from the same address the message was sent to". This makes replies to `hello@hoiboy.uk`-routed emails default to sending FROM `hello@hoiboy.uk` automatically.

## Volume and growth

Brevo free tier: 300 outbound emails/day. For solo consultancy reply traffic this is comfortable. If volume ever exceeds:

- Brevo paid tier: $25/month for 20K/month + dedicated IP - only if scaled past 300/day.
- Migration path: same SMTP credentials get rotated when upgrading; no Gmail re-config.
- Alternative DIY: self-host Postfix on a £5/mo VPS - significant time investment, not recommended for a solo operator.

The free tier comfortably covers cash-engine outreach + reply traffic at the cadence in `consulting-ops/playbook-harness-architect.md` (10-20/day connection requests + reply SLA on inbound).

## Testing the round-trip

Once both halves are wired:

1. From an external address (your phone, a friend's account), email `hello@hoiboy.uk`.
2. Confirm inbound: `hoiboyuk@gmail.com` receives within 30 seconds.
3. Reply from Gmail. The From: field should auto-populate to `hello@hoiboy.uk` per Step 4.
4. Confirm outbound: the external recipient sees the reply From: `hello@hoiboy.uk`, NOT `hoiboyuk@gmail.com`.
5. Spam-check: send a test to `https://www.mail-tester.com` (free tool); aim for 9/10 or higher. SPF + DKIM + DMARC alignment determines deliverability. Common failure: SPF has both `include:_spf.mx.cloudflare.net` and `include:spf.brevo.com` correctly merged into a single TXT record (NOT two separate SPF records).

## Ongoing maintenance

- Brevo SMTP key rotates only if compromised; otherwise indefinite.
- DNS records are static; Cloudflare auto-renews any verifications it owns.
- No subscription, no card, no auto-renewal trap.
- DMARC report aggregation: Brevo emails weekly DMARC reports to `hoiboyuk@gmail.com` per the `rua=` setting; review monthly for delivery health.

## Reply-To gotcha

Brevo defaults the Reply-To header on transactional sends to your Brevo account email (`hoiboyuk@gmail.com`). For brand-grade outbound this leaks the operator's personal Gmail. Reply-To MUST match From - set per-template via `PUT /v3/smtp/templates/{id}` body `{"replyTo":"hello@hoiboy.uk"}`, or per-send in `POST /v3/smtp/email`. Replies still route to your Gmail inbox via Cloudflare Email Routing - but the recipient never sees the personal address. See `docs/brevo-api-setup.md` § "Reply-To override pattern" for the full procedure. We hit this exact issue 2026-05-08 during the first test send.

## Execution evidence - 2026-05-08

Both halves of the stack are live and verified end-to-end.

### Inbound (Cloudflare Email Routing)

- Cloudflare Email Routing enabled on `hoiboy.uk`
- Cloudflare-managed DNS records added: 3 MX (`route1/2/3.mx.cloudflare.net`) + 1 SPF (later edited to append Brevo)
- Custom address `hello@hoiboy.uk` -> `hoiboyuk@gmail.com` (verified via Cloudflare email confirmation)
- Real-world test: external account -> `hello@hoiboy.uk` arrives in `hoiboyuk@gmail.com` within seconds

### Outbound (Brevo)

- Brevo free-tier account on `hoiboyuk@gmail.com`, plan `free`, 300 emails/day cap
- Domain `hoiboy.uk` authenticated via API trigger (`PUT /v3/senders/domains/.../authenticate`) - DNS records: brevo-code TXT, brevo1+brevo2 CNAMEs (CNAME-based DKIM), DMARC TXT, SPF appended
- Sender `Hoi <hello@hoiboy.uk>` registered, id 2, active, SPF + DKIM passing
- API key + SMTP key (Standard variant) in BW: items `brevo-hoiboy-uk-worker-api` + `brevo-hoiboy-uk-smtp`
- 6 transactional templates pushed (IDs 1-6), all with `replyTo: hello@hoiboy.uk` after the Reply-To fix
- Test send 2026-05-08 13:49 UTC - `messageId: <202605081349.74248579397@smtp-relay.mailin.fr>` - delivered, headers show `signed-by: hoiboy.uk` (DKIM PASS), TLS encrypted

### Credentials live in BW

| Item | Type | Owner | Notes |
|---|---|---|---|
| `cloudflare-verify-readonly` | Cloudflare API token (read-only) | (account) | RETIRED + REPLACED the old `hoiboy-uk-cloudflare-automation` token on 2026-06-01. Standing read-only across ALL zones (Zone/Zone Settings/DNS/Email Routing/Pages/Workers Scripts/Account Settings Read), no expiry. DNS/email **writes** now use a short-lived per-task control token, not a standing one. Two-token model: `dotfiles/docs/runbooks/cloudflare-control.md` |
| `brevo-hoiboy-uk-worker-api` | Brevo HTTP API key | (Brevo account login) | Used by Cloudflare Worker (Path B). Calendar rotation 2026-08-06 |
| `brevo-hoiboy-uk-smtp` | Brevo SMTP key (Standard variant) | (Brevo SMTP login) | Used by Gmail Send-as. Calendar rotation 2026-08-06 |

### Pending

- Gmail Send-as: still TBD (Phase I in `docs/brevo-api-setup.md`). UI-only, needs the SMTP login + key from BW.
- Cloudflare Worker (Path B in `docs/cal-com-setup.md`): not yet built. Will consume the Brevo API key for transactional sends triggered by Cal.com webhooks.

## Cross-reference

- `docs/cloudflare-api-token-setup.md` - hoiboy.uk token history + DNS API procedure (generic token recipe relocated to `dotfiles/docs/runbooks/cloudflare-control.md`)
- `docs/brevo-api-setup.md` - Brevo API + SMTP runbook + transactional templates
- `docs/cal-com-setup.md` - Cal.com booking funnel + Path B Worker plan that consumes this email stack
- `consulting-ops/playbook-harness-architect.md` - engagement playbook that consumes `hello@hoiboy.uk` as the canonical contact
- `consulting-ops/replies.md` - reply templates that direct prospects to email at `hello@hoiboy.uk`
- `data/consulting.yaml` `harness_architect.calcom_booking` - Cal.com URL replaces empty string post-Phase-1 (separate from email routing)
