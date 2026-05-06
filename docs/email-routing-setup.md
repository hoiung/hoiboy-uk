# Email Routing Setup: hello@hoiboy.uk

Operator runbook for the free DIY email stack on `hoiboy.uk`. Goal: receive at `hello@hoiboy.uk` (forwarded to `hoiboyuk@gmail.com`) and reply back AS `hello@hoiboy.uk` from inside Gmail. Zero ongoing subscription cost. No enterprise email account.

Two halves:

- **Inbound (receive)**: Cloudflare Email Routing — free tier, included with Cloudflare DNS hosting.
- **Outbound (send-as)**: Brevo SMTP relay — 300 emails/day free forever + Gmail "Send mail as" feature.

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

1. Sign up at https://www.brevo.com (free, no card).
2. In Brevo dashboard -> Senders, Domains & Dedicated IPs -> Domains -> Add `hoiboy.uk`.
3. Brevo gives 3 DNS records to add:
    - `brevo-code._domainkey.hoiboy.uk` (TXT, DKIM signing key)
    - `mail._domainkey.hoiboy.uk` (TXT, second DKIM record)
    - `_dmarc.hoiboy.uk` (TXT, DMARC policy — Brevo recommends `v=DMARC1; p=none; rua=mailto:hoiboyuk@gmail.com`)
4. Add all 3 records in Cloudflare DNS. Cloudflare proxy should be OFF for these (they are TXT records; proxy only applies to A/AAAA/CNAME).
5. Click "Authenticate this domain" in Brevo. Verification takes 5-30 minutes for DNS propagation.

Note: Brevo will also ask for an SPF record. Cloudflare Email Routing already added an SPF record (`v=spf1 include:_spf.mx.cloudflare.net ~all`). Append Brevo's SPF include so both inbound forwarding AND outbound SMTP work: `v=spf1 include:_spf.mx.cloudflare.net include:spf.brevo.com ~all`. Edit the existing TXT record; do NOT add a second SPF record (multiple SPF records break SPF validation entirely).

### Step 2: Brevo SMTP credentials

1. Brevo dashboard -> SMTP & API -> SMTP.
2. Server field: `smtp-relay.brevo.com`
3. Port field: 587
4. Login field: your Brevo account email.
5. SMTP-key field: click "Generate a new SMTP key" to obtain a fresh credential token (this is NOT your Brevo account login; the key is a separate token). Save it locally; Brevo only shows it once.

### Step 3: Gmail "Send mail as"

1. In `hoiboyuk@gmail.com` -> Settings (cog) -> See all settings -> Accounts and Import -> Send mail as -> "Add another email address".
2. Name: `Hoi` (or `Hoi Ung`, your call).
3. Email: `hello@hoiboy.uk`.
4. Untick "Treat as an alias" (this makes the From: header show `hello@hoiboy.uk`, not `hoiboyuk@gmail.com via brevo`).
5. Next -> SMTP server settings:
    - SMTP Server field: `smtp-relay.brevo.com`
    - Port field: 587
    - Username field: your Brevo account email (from Step 2)
    - SMTP-key field: the SMTP key generated in Step 2
    - Secured connection using TLS (default).
6. Save. Gmail sends a verification email to `hello@hoiboy.uk`, which Cloudflare forwards back to `hoiboyuk@gmail.com`. Click the verification link.
7. Test: compose a new email in Gmail; in the From: dropdown, pick `hello@hoiboy.uk`. Send to a different external address (your personal Gmail, a friend, or a temp address). Verify the received email shows From: `hello@hoiboy.uk`.

### Step 4: default From: address

In Gmail Settings -> Accounts and Import -> "When replying to a message" -> select "Reply from the same address the message was sent to". This makes replies to `hello@hoiboy.uk`-routed emails default to sending FROM `hello@hoiboy.uk` automatically.

## Volume and growth

Brevo free tier: 300 outbound emails/day. For solo consultancy reply traffic this is comfortable. If volume ever exceeds:

- Brevo paid tier: $25/month for 20K/month + dedicated IP — only if scaled past 300/day.
- Migration path: same SMTP credentials get rotated when upgrading; no Gmail re-config.
- Alternative DIY: self-host Postfix on a £5/mo VPS — significant time investment, not recommended for a solo operator.

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

## Cross-reference

- `consulting-ops/playbook-harness-architect.md` — engagement playbook that consumes `hello@hoiboy.uk` as the canonical contact.
- `consulting-ops/replies.md` — reply templates that direct prospects to email at `hello@hoiboy.uk`.
- `data/consulting.yaml` `harness_architect.calcom_booking` — Cal.com URL replaces empty string post-Phase-1 (separate from email routing).
