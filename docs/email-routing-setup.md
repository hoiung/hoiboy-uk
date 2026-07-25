# Email Routing Setup: hello@hoiboy.uk

Operator runbook for the free DIY email stack on `hoiboy.uk`. Goal: receive at `hello@hoiboy.uk` (forwarded to `hoiboyuk@gmail.com`) and reply back AS `hello@hoiboy.uk` from inside Gmail. Zero ongoing subscription cost. No enterprise email account.

**Status as of 2026-05-08** (re-verified via DNS 2026-06-01 and again 2026-07-25: MX + merged SPF + DKIM + DMARC all live): live and verified end-to-end. SPF + DKIM + DMARC all PASS in real-world delivery. See § "Verify DNS health (no token needed)" for the token-free re-check and § "Execution evidence" at the bottom.

> **This runbook now covers two Brevo flows.** hoiboy.uk was built on the older 4-record flow; `cuarchitects.co.uk` was onboarded on 2026-07-25 on Brevo's newer flow, which adds a branded subdomain and issues **no SPF include**. Following this page verbatim for a new domain will send you looking for records Brevo no longer gives you. Read Step 1 § 3 before touching DNS on a new domain, and treat the wizard's own record list as the source of truth over anything written here.

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
3. Brevo issues the DNS records. **There are now two different flows - read what the wizard actually gives you, do not assume this list.** Brevo is gradually rolling out a new domain-setup experience, so which one you get depends on the account and when the domain was onboarded.

    **Old flow (what hoiboy.uk was set up with, 2026-05-08): 4 records.** Brevo had already migrated to **CNAME-based DKIM** by this point, which is better than the older TXT-based DKIM because Brevo can rotate signing keys without forcing DNS edits.
    - `@` TXT - `brevo-code:<32-hex>` (account-specific verification)
    - `brevo1._domainkey` CNAME -> `b1.<zone>.dkim.brevo.com` (DKIM 1)
    - `brevo2._domainkey` CNAME -> `b2.<zone>.dkim.brevo.com` (DKIM 2)
    - `_dmarc` TXT -> `v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com` (Brevo aggregates DMARC reports for you)

    **Current flow (what cuarchitects.co.uk got, 2026-07-25): 7 records.** Same four as above, plus a **branded subdomain** - a prefix such as `em` that replaces Brevo's own domain in tracking links and, more importantly, carries the return path:
    - `em` CNAME -> `em-<zone>.brand.brevosend.com`
    - `img.em` CNAME -> `em-<zone>.img.brand.brevosend.com`
    - `r.em` CNAME -> `em-<zone>.r.brand.brevosend.com`

    Pick a prefix that is free in the zone and unambiguous. `em` is better than `mail` when Cloudflare Email Routing is already on the apex, because `mail.<zone>` reads like a mail server and will mislead whoever reads the DNS later.

    **The branded subdomain is not retrofittable on demand.** hoiboy.uk was checked on 2026-07-25 and the option is not exposed for it at all; the flow only appears where the new setup experience has rolled out. Do not go hunting for it on an old-flow domain. It only changes how tracking links look, so an old-flow domain that sends fine loses nothing by not having it.
4. Add the records in Cloudflare DNS. **Proxy must be OFF for every CNAME** (orange cloud breaks DKIM, and breaks the branded-subdomain CNAMEs too). Use the API path documented in `docs/cloudflare-api-token-setup.md` for reproducibility.

   Choose **Manual** when the wizard offers Automatic / Manual / Delegate. Automatic asks for standing write access to the whole DNS zone, and it is the option most likely to add a second SPF record rather than merging into the existing one (see below). Four to seven records is not worth a permanent third-party grant on the zone.
5. Trigger Brevo's verification - either UI button "Authenticate this email domain" OR API: `PUT /v3/senders/domains/hoiboy.uk/authenticate` (see brevo-api-setup.md § Phase B).

**SPF: only the old flow needs it, and then you EDIT the existing record, never add a second.** Cloudflare Email Routing writes its own SPF (`v=spf1 include:_spf.mx.cloudflare.net ~all`). Under the old flow Brevo's include gets appended to that same record:

```
v=spf1 include:_spf.mx.cloudflare.net include:spf.brevo.com ~all
```

Multiple SPF records on the same name break SPF validation entirely (permerror), and SPF fails outright rather than degrading, so this is a silent-breakage trap.

**The current flow does not ask for an SPF include at all.** cuarchitects.co.uk was authenticated on 2026-07-25 and Brevo issued no SPF record: the return path moves onto the branded subdomain, and DMARC passes on **DKIM alignment** instead (Brevo signs with `d=<your zone>`, which aligns with the From domain). Do not add `include:spf.brevo.com` by hand to a new-flow domain just because this runbook used to say so. Confirm alignment from real message headers rather than from the record list.

hoiboy.uk keeps its merged include because that is what its flow required and it works. Do not strip it.

**Sender registration: needed for the API path, NOT for SMTP relay on an authenticated domain.** Brevo's `POST /v3/senders` registers `hello@hoiboy.uk` as an active sender, and the API send path fails with `Sender is invalid / inactive` without it (hit for real 2026-05-08). See brevo-api-setup.md § Phase F.

For **Gmail send-as over SMTP relay this step is not required**: authenticating the domain auto-verifies every address on it, so a From address that has no sender entry still sends. Confirmed on `cuarchitects.co.uk` 2026-07-25 - four round-trip test sends succeeded while `chan@cuarchitects.co.uk` was absent from the Senders list entirely. Do not treat a missing sender entry as a fault, and do not go adding one to fix a send failure; if SMTP sends are failing, the cause is the SMTP login or the domain authentication, not the sender list.

Adding the domain sender anyway is still worth doing for tidiness, because it lets you remove the freemail sender below and clears the compliance warning. It verifies instantly with no emailed code once the domain is authenticated.

**Delete the freemail sender Brevo auto-creates at signup.** Brevo registers your account email as a sender, so a Gmail-based signup leaves a `<you>@gmail.com` sender in the list. It shows `DKIM: Default` and `DMARC: Freemail domain is not recommended`, and it is flagged as non-compliant with the Google / Yahoo / Microsoft bulk-sender requirements - correctly, because you do not own `gmail.com` and so it can never be DKIM-signed or DMARC-aligned. Nothing in this stack needs it: Gmail send-as composes go out as the domain address. Removed from the hoiboy.uk account on 2026-07-25; the domain sender `Hoi <hello@hoiboy.uk>` was already healthy (`DKIM: hoiboy.uk`, `DMARC is configured`) and is untouched. If a deletion ever breaks something, the symptom is the same `Sender is invalid / inactive` on send.

**Order matters when the freemail sender is the only one.** On a fresh account it is also flagged `Default`, and removing the last default sender is not something to attempt blind. Add the domain sender FIRST (it verifies instantly, no emailed code, because the domain is authenticated), make it default, and only then delete the freemail one. Done in that order on `cuarchitects.co.uk` 2026-07-25, ending at one healthy domain sender and no compliance warning on either account.

### Step 2: Brevo SMTP credentials

1. Brevo dashboard -> SMTP & API -> SMTP tab.
2. Server: `smtp-relay.brevo.com`
3. Port: 587
4. **Login**: NOT your Brevo account email - Brevo issues a separate SMTP-relay address shown on this page, format `aaaXXXXXX@smtp-brevo.com` (e.g. `aaa99a001@smtp-brevo.com`). Using the account email here returns `5.7.8 Authentication failed`. (Originally this runbook said "your Brevo account email" - that was wrong, corrected 2026-05-08 after a real auth failure during execution.)
5. SMTP key: click **Generate a new SMTP key**, pick **Standard variant** (64-char body, 90 chars total), copy the `xsmtpsib-...` value. Save in BW immediately - Brevo only shows it once.

**Expiry: set NO EXPIRY** (operator decision 2026-07-25). The key is domain-scoped, rate-limited to the free-tier daily cap, held in BW and revocable in one click, so a leak is bounded and fixable. An expiry, by contrast, takes down a live business channel silently. Rotation dates that nobody honours are theatre; an unattended expiry is an outage.

⚠️ **No-expiry does not remove all expiry risk.** Brevo's own dialog states that SMTP keys **also expire after 90 days of inactivity, regardless of the set expiry date**. On a low-volume domain that is the more likely of the two failure modes, and it lands at the worst time: a quiet period kills the key, then the first enquiry in months arrives and the reply will not send. There is no notification. The symptom is an authentication error on send; the fix is to generate a new key and update it in Gmail and BW.

**Do not activate "block unauthorized IP addresses" for SMTP keys.** That feature assumes mail leaves from a few fixed IPs. With Gmail "Send mail as", the SMTP connection to Brevo is made by Google's outbound infrastructure, which is a large shifting pool you cannot enumerate. Activating it rejects every send.

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
5. Spam-check: send a test to `https://www.mail-tester.com` (free tool). Write a couple of real paragraphs - a bare "test" with a signature attached scores badly for reasons that have nothing to do with your setup (see below).

**Read the authentication section, not the headline score.** What proves the stack is working is:

```
DKIM_VALID      Message has at least one valid DKIM signature
DKIM_VALID_AU   ...and it comes from the author's domain   <-- the one that matters
SPF_PASS        sender matches SPF record
                "You're properly authenticated"
```

`DKIM_VALID_AU` is author-domain alignment, which is what DMARC actually requires. On a new-flow domain with no SPF include (see Step 1 § 3) this is carrying DMARC unaided, so confirm it rather than assuming it.

**Expect roughly 8.6/10, not 9+, and do not chase the difference.** Measured on BOTH `hoiboy.uk` and `cuarchitects.co.uk` on 2026-07-25: identical score, identical deductions, both authenticating perfectly. The gap is two content rules:

- `-1.048 HTML_IMAGE_ONLY_16` - the test message is mostly signature, so the image-to-text ratio trips a rule aimed at image-only spam. A real email with body prose does not trigger it.
- `-0.5` for two images with no `alt` attribute.

⚠️ **Those two images are Brevo open-tracking pixels, and you cannot remove them.** They are injected at send time and look like this:

```html
<img width="1" height="1" src="https://<hash>.r.af.d.sendibt2.com/tr/op/...">
<img style="display:none"  src="https://<hash>.r.af.d.sendibt2.com/tr/op/...">
```

`sendibt2.com` is Brevo and `/tr/op/` is open tracking. **Brevo has no way to disable tracking on SMTP transactional** - campaigns can turn off URL tracking, SMTP cannot, and it is a long-standing known limitation on their own community forum. The only lever is "Anonymous email tracking" (Settings > Automations > Transactional emails > Tracking), which still injects the pixel and merely unlinks the data from contacts, so it recovers none of the score. It is also gated behind an Automations onboarding wizard.

Do NOT act on mail-tester's advice to "add an empty alt attribute" - the tags are not in your signature and you cannot edit them. Do not go hunting through the signature for images that are not there. The correct response is to ignore the deduction.

Accepted as a known limitation 2026-07-25. 8.6 is comfortably not-spam. The only clean fix is leaving Brevo (Cloudflare Email Sending has no marketing-tracking baggage, but needs the Workers Paid plan at ~$5/mo, which is the recurring cost this whole stack exists to avoid). Revisit only if deliverability actually degrades. Be aware the pixel means recipients are tracked on open, which is unremarkable for campaigns but is worth knowing for one-to-one client correspondence.

**SPF failure mode**, if the auth section is not clean: on an old-flow domain the SPF record must contain both `include:_spf.mx.cloudflare.net` and `include:spf.brevo.com` merged into a SINGLE TXT record, never two separate ones. On a new-flow domain there is no Brevo include at all and adding one by hand is not the fix.

## Verify DNS health (no token needed)

All email-critical records are public DNS, so you can confirm the setup is live with zero Cloudflare token (re-verified green 2026-06-01):

```bash
DOH(){ curl -s -H 'accept: application/dns-json' "https://1.1.1.1/dns-query?name=$1&type=$2"; }
DOH hoiboy.uk MX             | jq -r '.Answer[]?.data'              # 3x route{1,2,3}.mx.cloudflare.net = inbound routing live
DOH hoiboy.uk TXT            | jq -r '.Answer[]?.data' | grep spf1 # one merged SPF: include _spf.mx.cloudflare.net + spf.brevo.com
DOH _dmarc.hoiboy.uk TXT     | jq -r '.Answer[]?.data'             # v=DMARC1; p=...
DOH brevo1._domainkey.hoiboy.uk CNAME | jq -r '.Answer[]?.data'    # b1.hoiboy-uk.dkim.brevo.com (DKIM selector 1; brevo2 = selector 2)
```

Clean MX + a single merged SPF + resolving DKIM CNAMEs + a DMARC record = inbound routing and outbound auth are both healthy. The forwarding **destination** (`hoiboyuk@gmail.com`) and its verified state are NOT in public DNS - confirm those via the Email Routing API (`GET /zones/{id}/email/routing/rules`, read-only token is enough) or the dashboard.

## Ongoing maintenance

- Brevo SMTP key rotates only if compromised; otherwise indefinite (set to no-expiry, 2026-07-25). The one thing that can still kill it unattended is Brevo's **90-day inactivity** expiry, which applies regardless of the expiry setting - see Step 2.
- DNS records are static; Cloudflare auto-renews any verifications it owns.
- No subscription, no card, no auto-renewal trap.
- DMARC report aggregation: Brevo emails weekly DMARC reports to `hoiboyuk@gmail.com` per the `rua=` setting; review monthly for delivery health.
- **Tightening DMARC (optional hardening):** the policy starts at `p=none` (monitor-only, the safe default). Once the weekly Brevo reports confirm all legit mail (Gmail send-as + Brevo) passes SPF/DKIM alignment, ramp the `_dmarc` TXT `p=none` -> `p=quarantine` -> `p=reject` (optionally gate with `pct=25` first to apply the policy to a fraction of mail while you build confidence). This is a single **DNS edit**: do it in the Cloudflare dashboard (DNS -> edit the `_dmarc` TXT record), or via `PATCH /zones/{id}/dns_records/{record_id}` using a short-lived **DNS:Edit** per-task control token. The standing read-only `cloudflare-verify-readonly` token CANNOT write - that is by design. See the two-token model in `dotfiles/docs/runbooks/cloudflare-control.md`.

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
- Cloudflare Worker (Path B in `docs/cal-eu-setup.md`): not yet built. Will consume the Brevo API key for transactional sends triggered by Cal.com webhooks.

## Cross-reference

- `docs/cloudflare-api-token-setup.md` - hoiboy.uk token history + DNS API procedure (generic token recipe relocated to `dotfiles/docs/runbooks/cloudflare-control.md`)
- `docs/brevo-api-setup.md` - Brevo API + SMTP runbook + transactional templates
- `docs/cal-eu-setup.md` - Cal.com booking funnel + Path B Worker plan that consumes this email stack
- `consulting-ops/playbook-harness-architect.md` - engagement playbook that consumes `hello@hoiboy.uk` as the canonical contact
- `consulting-ops/replies.md` - reply templates that direct prospects to email at `hello@hoiboy.uk`
- `data/consulting.yaml` `harness_architect.calcom_booking` - Cal.com URL replaces empty string post-Phase-1 (separate from email routing)
