---
title: Cal.com booking funnel — API-driven setup runbook
purpose: Reproducible recipe for setting up the discovery-call booking funnel on Cal.com via API, including regional instance split, endpoint discovery, event-type config, the 5 Hoi-voice email templates, and lessons learned. Designed to be duplicable for future paid-client onboarding (each client may need their own Cal.com or equivalent).
last_verified: 2026-05-07
related:
  - data/consulting.yaml (calcom_booking field)
  - layouts/shortcodes/consulting-cta.html (UI consumer)
  - docs/email-routing-setup.md (Brevo SMTP stack — relevant if going webhook→Worker route)
---

This is the runbook for setting up the `hello@hoiboy.uk` consulting discovery-call funnel on Cal.com. **Most of it is API-driven** so you can reproduce it for future paid clients without click-trail-by-hand UI walkthroughs. The exception is OAuth consent screens (Google Calendar / Google Meet) which by design must be browser-driven.

## Regional instance split (THE critical lesson)

Cal.com runs **two separate production instances**:

| Region | UI base | API base | Booking link prefix |
|---|---|---|---|
| United States (default) | `https://cal.com` | `https://api.cal.com/v2` | `https://cal.com/<username>/<slug>` |
| Europe | `https://cal.eu` | `https://api.cal.eu/v2` | `https://cal.eu/<username>/<slug>` |

**API keys are NOT cross-region.** A `cal_live_*` key generated on the EU instance will return `401 CustomThrottlerGuard - Invalid API Key` against `api.cal.com`, and vice versa.

**How to tell which instance you are on**: log in via browser, look at the URL bar. If the username link reads `cal.eu/yourname` you are on EU; if `cal.com/yourname` you are on US. Mirrors apply to API hosts.

**Burned 6 minutes of probing before noticing this** — see Lessons Learned section.

## Authentication

```
Authorization: Bearer cal_live_<32-hex-chars>
cal-api-version: 2024-06-14    # required for most endpoints
```

Required version header per endpoint family (Cal.com versions endpoints independently — passing the wrong value sometimes degrades to an older response shape, sometimes 404s):

| Endpoint family | `cal-api-version` |
|---|---|
| `/v2/me` | (no header needed) |
| `/v2/event-types` | `2024-06-14` |
| `/v2/schedules` | `2024-06-11` |
| `/v2/bookings` | `2024-08-13` |
| `/v2/webhooks` | (verify before use; not yet exercised in this runbook) |

## Misleading error messages — read these BEFORE you panic

Cal.com's `CustomThrottlerGuard` runs before authentication, so its errors do **not** correctly distinguish between "bad key" and "right key, wrong region/host". The two confusing patterns:

| Symptom | What it usually means |
|---|---|
| `401 CustomThrottlerGuard - Invalid API Key` on every endpoint | Wrong region (EU key against `.com` host or vice versa). Check your booking-link URL bar. |
| `404 NotFoundException — Cannot GET /v2/<path>` while other endpoints 401 | Auth IS working; the path or version header is wrong for this endpoint family. |
| `401 CustomThrottlerGuard - Invalid API Key` on a fresh key only | Key never persisted (modal closed before save) OR signup email not yet verified. |

## The setup procedure

### Phase A — Browser-only (cannot be automated)

1. Sign up at the appropriate region (`https://cal.com/signup` for US, `https://cal.eu/signup` for EU) using "Sign up with Google" so Calendar + Meet auth flows are one-click. Email verification is automatic with the Google flow.
2. Pick username. Tried order: `hoi` → `hoiboy` → `hoiboyuk`. Username chosen for this account: `hoiboyuk`.
3. Onboarding flow connects Google Calendar (OAuth consent screen).
4. Settings → Apps → install Google Meet (auto-binds to the Google account).
5. Settings → Developer → API keys → Create new → expiry 7 days for setup, copy the key value into a scratch buffer **before closing any modal**, then verify the key appears in the keys list with the expected name. If it does not appear in the list, regenerate.

### Phase B — API setup (this runbook)

All requests use `Authorization: Bearer ${CAL_API_KEY}`. Examples below assume `CAL_API_KEY` and `CAL_BASE` are exported:

```bash
export CAL_API_KEY="cal_live_<your-key>"   # secret-allow (placeholder)
export CAL_BASE="https://api.cal.eu/v2"   # or https://api.cal.com/v2 for US
```

#### Step 1 — Verify auth and identify yourself

```bash
curl -s -H "Authorization: Bearer ${CAL_API_KEY}" "${CAL_BASE}/me" | jq
```

Expect HTTP 200 with `id`, `email`, `name`. Note the `id` (becomes `ownerId` in subsequent objects).

#### Step 2 — Inspect the default schedule

A "Working hours" schedule is created automatically on signup, defaulting to Mon-Fri 09:00-17:00 in the timezone you picked at signup. Inspect first; PATCH if you want different hours.

For hoiboy.uk we wanted Mon-Fri **11:00-18:00 Europe/London** (corrected 2026-05-08 — the auto-default 09:00-17:00 was rolled with by accident initially):

```bash
curl -s -X PATCH -H "Authorization: Bearer $CAL_API_KEY" \
  -H "cal-api-version: 2024-06-11" -H "Content-Type: application/json" \
  -d '{
    "name": "Working hours",
    "timeZone": "Europe/London",
    "isDefault": true,
    "availability": [
      {"days": ["Monday","Tuesday","Wednesday","Thursday","Friday"],
       "startTime": "11:00", "endTime": "18:00"}
    ]
  }' "https://api.cal.eu/v2/schedules/42584"
```

The PATCH on schedules requires `name` + `timeZone` + `availability` to be present even if you're only changing one of them (Cal.com treats schedule PATCH as a full-state replacement, not a diff). Without all three fields, the response is HTTP 200 but the missing fields silently revert.

```bash
curl -s -H "Authorization: Bearer ${CAL_API_KEY}" -H "cal-api-version: 2024-06-11" \
  "${CAL_BASE}/schedules" | jq
```

Record the `id` (becomes `scheduleId` for the event type). For this account: `42584`.

If the default does not match what you want, PATCH it. Schema: `availability` is an array of `{days:[...], startTime:"HH:MM", endTime:"HH:MM"}` blocks; `timeZone` is an IANA TZ string.

#### Step 3 — Confirm Google Meet is connected

The default 30-min event type created on signup will show `locations[0].integration: "google-meet"` and a `credentialId` if Meet is properly bound. List event types:

```bash
curl -s -H "Authorization: Bearer ${CAL_API_KEY}" -H "cal-api-version: 2024-06-14" \
  "${CAL_BASE}/event-types" | jq
```

If the default event type is missing the `google-meet` location or `credentialId`, go back to Phase A step 4.

#### Step 4 — Create the discovery event type

POST `/v2/event-types` (`cal-api-version: 2024-06-14`) with payload:

```json
{
  "lengthInMinutes": 20,
  "title": "20 min discovery call",
  "slug": "discovery",
  "description": "A focused 20 minutes to listen to what you are trying to solve and figure out together if I am the right person to help. No slide deck. No sales pitch.",
  "locations": [
    {"type": "integration", "integration": "google-meet"}
  ],
  "bookingFields": [
    {"type": "text", "slug": "company-name", "label": "Company name", "required": true, "placeholder": "e.g. ACME Ltd"},
    {"type": "text", "slug": "ai-tool-today", "label": "What AI tool or coding agent are you using today?", "required": false, "placeholder": "e.g. ChatGPT, Claude, Cursor, none yet"},
    {"type": "text", "slug": "distinct-roles", "label": "Roughly how many distinct roles or workflows in your business would AI need to support?", "required": true, "placeholder": "e.g. 1 (solo), 3-5 (small team), 10+ (multiple departments)"},
    {"type": "textarea", "slug": "hope-to-get", "label": "Briefly, what are you hoping to get from this 20 minutes?", "required": true, "placeholder": "One workflow, one problem, one question — whatever is top of mind."}
  ],
  "minimumBookingNotice": 720,
  "beforeEventBuffer": 10,
  "afterEventBuffer": 10,
  "scheduleId": 42584
}
```

**Booking field design rationale**:

- `company-name` (required): identity signal; useful even when email domain matches the company because corporate names diverge from primary domains (e.g. holding company vs trading name)
- `ai-tool-today` (optional): conversational ice-breaker; "none yet" is a valid answer and signals different audience segment
- `distinct-roles` (required): THE highest-signal qualifier for harness-engagement scope. Hoi's thesis: harness count tracks roles, not headcount. A 5-person agency with 5 distinct roles (marketer/designer/copywriter/ops/founder) needs more harnesses than a 20-person SaaS with 3 (engineering/sales/founder). Worked-example placeholder lets prospects self-categorize without numerical anxiety
- `hope-to-get` (required textarea): open-ended discovery — what's actually keeping them up at night

We deliberately do NOT ask for the prospect's website. Email domain often gives it; for Gmail-domain users without domain match, that's itself a useful signal ("hobby project" vs "company"). Form length stays minimal (4 custom + 2 default = 6 visible fields total) for conversion.

`minimumBookingNotice` is in **minutes** (720 = 12h). `beforeEventBuffer` / `afterEventBuffer` ditto. Default booking fields (`name`, `email`, `location`, `notes`, `guests`, `rescheduleReason`, `title`) are added automatically; you only specify your **custom** fields, they get appended.

Response includes `bookingUrl` confirming the public link.

#### Step 5 — Add 30-day rolling booking window + per-day booking limit

The create endpoint does not accept `bookingWindow` or `bookingLimitsCount` in the create payload (silently ignored). Use PATCH after creation:

```bash
# Booking window: 30 days rolling
curl -s -X PATCH -H "Authorization: Bearer ${CAL_API_KEY}" -H "cal-api-version: 2024-06-14" \
  -H "Content-Type: application/json" \
  -d '{"bookingWindow":{"type":"businessDays","value":30,"rolling":true}}' \
  "${CAL_BASE}/event-types/${EVENT_TYPE_ID}"

# Per-day booking cap (4 bookings/day for hoiboy.uk)
curl -s -X PATCH -H "Authorization: Bearer ${CAL_API_KEY}" -H "cal-api-version: 2024-06-14" \
  -H "Content-Type: application/json" \
  -d '{"bookingLimitsCount":{"day":4}}' \
  "${CAL_BASE}/event-types/${EVENT_TYPE_ID}"
```

`bookingWindow.type` accepts `businessDays | calendarDays | range`. `rolling: true` = "always 30 days from today"; `false` = fixed window from creation date.

`bookingLimitsCount` accepts `{day, week, month, year}` — any subset. Cal.com Free supports `day` (verified 2026-05-08); `week`/`month`/`year` may be Pro-only on some accounts.

**Effect of the daily cap**: once the cap is reached on a given day, the public booking page hides ALL remaining slots for that day. Cal.com applies the limit at the slots-API level, so it's enforced consistently between the public booking page AND any direct API booking attempts. Looks "fully booked" to the prospect; no manual intervention required.

#### Step 6 — Patch the consulting page

The page consumes `data/consulting.yaml` via the `consulting-cta` shortcode at `layouts/shortcodes/consulting-cta.html`, which auto-flips between `mailto:hello@hoiboy.uk` fallback and the live booking URL based on the presence of `calcom_booking`.

```yaml
# data/consulting.yaml
calcom_booking: "https://cal.eu/hoiboyuk/discovery"
```

After commit + push, Cloudflare Pages auto-deploys. Run `hugo server --buildDrafts --bind 0.0.0.0` locally first to confirm both top + bottom CTAs render the live link.

## Email workflows — two architectural paths

Cal.com workflows are **not exposed in the v2 personal API** as of 2026-05-07. Confirmed by probing 6 endpoint variants, all 404. The v2 docs hint at workflow endpoints under team/org contexts (e.g. `/v2/orgs-teams-workflows/`) but personal accounts cannot reach them.

You have two real options.

### Path A — Cal.com built-in workflows via UI

Manual paste of templates A-E + operator-side reminder into Cal.com → Workflows → New, one workflow per trigger type. Free tier supports email actions. **Footer of every email shows "Powered by Cal.com" branding** which is the main downside.

Trigger mapping per template:

| Template | Cal.com trigger | Action | Status (post 2026-05-08 cadence decision) |
|---|---|---|---|
| A — Booking confirmation | New booking | Send email to attendee | ✅ Active |
| B — 24h reminder | 24 hours before event starts | Send email to attendee | ✅ Active |
| C — 1h reminder | 1 hour before event starts | Send email to attendee | 💤 **Dormant** (template pushed to Brevo, Worker doesn't fire). Cal.com's hardcoded 1h email + 1h notification reminder (Lessons #11) covers the same window for any attendee whose calendar app honors embedded iCal reminders (Google Calendar always does; Outlook / Apple Calendar mostly do). Re-enable in Worker cron if real-world bookings show Outlook/Apple attendees missing reminders. |
| D — Reschedule confirmation | Event rescheduled | Send email to attendee | ✅ Active |
| E — Cancellation acknowledgement | Event cancelled | Send email to attendee | ✅ Active |
| Operator reminder | 2 hours before event starts | Send email to host (Hoi) | ✅ Active — T-2h gives proper context-switch + prep time for the host without prepping too early. Was originally drafted at T-15min, then T-30min, settled at T-2h (2026-05-08 design iteration) |

The 5 templates verbatim are in the next section.

### Path B — Webhook → Cloudflare Worker → Brevo SMTP

Cal.com webhooks ARE in the v2 API (`/v2/webhooks`). Configure them to fire on:

- `BOOKING_CREATED` → triggers Template A
- `BOOKING_RESCHEDULED` → triggers Template D
- `BOOKING_CANCELLED` → triggers Template E
- `MEETING_STARTED` (i.e. event-just-starting) — Cal.com does not natively support pre-event triggers via webhook on free tier, so 24h and 1h reminders need a separate cron worker that polls upcoming bookings and fires Templates B + C

A Cloudflare Worker receives each webhook, picks the appropriate template, calls Brevo's HTTP API (Workers can't open raw SMTP sockets) with `templateId` + `params` — Brevo renders the template server-side and sends From: `hello@hoiboy.uk`.

**Pros**: branded sender, no "Powered by Cal.com" footer, lives in code (`hoiboy-uk/workers/cal-com-email-bridge/` — proposed location), reproducible runbook for future clients.

**Cons**: ~80-150 lines of TypeScript across the Worker + cron, plus the cron-poll for B + C reminders (Cal.com webhooks don't natively fire pre-event triggers on free tier). Requires Brevo API key in Worker secrets.

### Email infrastructure status — UNBLOCKED 2026-05-08

The email layer Path B depends on is **fully live and verified**:

- ✅ Cloudflare Email Routing inbound (`hello@hoiboy.uk` → `hoiboyuk@gmail.com`)
- ✅ Brevo domain authenticated (DKIM CNAMEs + DMARC + SPF appended)
- ✅ Brevo sender registered (`hello@hoiboy.uk` id 2, active)
- ✅ All 6 Hoi-voice templates pushed as Brevo transactional templates (IDs 1-6, all with `replyTo: hello@hoiboy.uk`)
- ✅ Brevo HTTP API key + SMTP key both stored in BW
- ✅ Test send proven: `messageId: <202605081349.74248579397@smtp-relay.mailin.fr>`, headers showed DKIM PASS, TLS encrypted

**What remains for Path B (Worker build):**

- [ ] Generate Cal.com webhook secret (random 32-char), store in BW
- [ ] Configure Cal.com webhooks via API: `POST /v2/webhooks` for BOOKING_CREATED + BOOKING_RESCHEDULED + BOOKING_CANCELLED triggers, target = Worker URL
- [ ] Build the Cloudflare Worker: webhook receiver + cron for B/C/operator reminders
- [ ] Worker secrets via `wrangler secret put`: BREVO_API_KEY (from BW), CAL_API_KEY (long-lived, not the 7-day setup one), CAL_WEBHOOK_SECRET (from BW)
- [ ] Worker KV namespace for "already-sent" deduplication
- [ ] Deploy + smoke test (book a real test event, verify A fires; reschedule, verify D fires; cancel, verify E fires; rely on cron logs for B/C/operator)
- [ ] Patch `data/consulting.yaml` `calcom_booking` to flip the landing page CTA from `mailto:` fallback to live booking URL

See `docs/brevo-api-setup.md` § "The 6 templates pushed" for template IDs the Worker references.

## The 5 Hoi-voice email templates (canonical, verbatim)

These templates are the canonical source. They are also reproduced in the part-3 handover memory; if you ever modify them, update both places.

### Template A — Booking confirmation

```
Subject: Booked - 20 min with Hoi, {EVENT_DATE} at {EVENT_TIME}
```

```
Hi {ATTENDEE},

Booked. {EVENT_DATE} at {EVENT_TIME} (UK time), 20 minutes on Google Meet.

Joining link: {MEETING_URL}
(Calendar invite has the same link, in case this email gets buried.)

What this 20 minutes is NOT:
- A slide deck.
- A sales pitch.
(Both of those are just me talking at you, which is the opposite of useful here.)

What this 20 minutes IS:
- I listen to what you are actually trying to solve.
- We figure out together if I am the right person to help, or not.
- We agree the next step (company audit, no audit, or "go away Hoi", all fair).

What would help (not homework, just things to think about):
- One workflow that, if AI got it right, would matter to your business this quarter.
- One thing AI got wrong for you recently (hallucination, wrong file, wrong tone, wrong anything).
- Roughly how many people in the company touch the workflow above.

If something comes up and the time no longer works, the calendar invite has a reschedule link (one click, pick a new slot, no awkward email exchange).

See you {EVENT_DATE}.

Hoi
hello@hoiboy.uk
hoiboy.uk/consulting/claude-code-harness-architect/

TANTUNG LTD (Companies House 10566169)
```

### Template B — 24-hour reminder

```
Subject: Tomorrow - 20 min with Hoi at {EVENT_TIME}
```

```
Hi {ATTENDEE},

Quick nudge. We are on for tomorrow, {EVENT_DATE} at {EVENT_TIME} (UK time).

Google Meet: {MEETING_URL}

If something has come up, hit the reschedule link in the calendar invite (one click, no awkward email). Better to move it than to no-show.

Talk tomorrow.

Hoi
```

### Template C — 1-hour reminder

```
Subject: In an hour - Google Meet link inside
```

```
Hi {ATTENDEE},

We are on in an hour ({EVENT_TIME} UK).

Google Meet: {MEETING_URL}

Hoi
```

### Template D — Reschedule confirmation

```
Subject: Rescheduled - new time {EVENT_DATE} at {EVENT_TIME}
```

```
Hi {ATTENDEE},

Got it. New time: {EVENT_DATE} at {EVENT_TIME} (UK time), 20 minutes on Google Meet.

Joining link: {MEETING_URL}

Same plan as before, just different clock face. See you then.

Hoi
```

### Template E — Cancellation acknowledgement

```
Subject: Cancellation noted
```

```
Hi {ATTENDEE},

Noted, no problem.

If you want to come back later (different week, different month, different question), the booking page is here: https://cal.eu/hoiboyuk/discovery

Or just email hello@hoiboy.uk and tell me what changed.

Hoi
```

### Operator-side reminder (2 hours before event → host)

```
Subject: Discovery call in 2 hours — {ATTENDEE} from {COMPANY}
```

```
Discovery call with {ATTENDEE} from {COMPANY} starting in 2 hours.

Brief:
- AI tool today: {AI_TOOL_TODAY}
- Distinct roles / workflows: {DISTINCT_ROLES}
- Hoping to get: {HOPE_TO_GET}

Google Meet: {MEETING_URL}
```

**Cadence iteration history (2026-05-08)**: drafted as T-15min → bumped to T-30min for switching time → bumped to T-1h for proper prep → settled at T-2h after iterating with the host. Lesson: pre-call prep window is host-preference-driven, not best-practice-driven; whatever works for the operator's actual mental switching cost wins. Capture the choice at the runbook level so it doesn't drift.

## Lessons learned (the things that cost real time)

1. **Region split is invisible until you check the URL bar.** Spent ~6 minutes thinking the API key was malformed when it was simply issued on EU and being used against US. The error message (`CustomThrottlerGuard - Invalid API Key`) is misleading — it is a regional-host mismatch, not a bad key. **First diagnostic step on any 401**: confirm regional alignment between key origin and API host.
2. **`CustomThrottlerGuard` runs before auth, so its errors do not actually mean "invalid".** Treat 401 from it as "this key cannot reach this throttler" — possible causes are region mismatch, key not yet persisted, or wrong endpoint version header.
3. **404 is good news.** A 404 NotFoundException after auth means the key worked; you are just hitting a path that does not exist (often because the wrong `cal-api-version` was sent). When sweeping endpoints to identify versions, watch for the 401→404 transition — that is the version snapping into place.
4. **Personal API keys are limited.** Workflows, advanced webhook configs, and team/org features may be inaccessible. Plan for a hybrid (API for what is exposed + UI for the rest, OR webhook-handler architecture for a fully code-driven setup).
5. **Default schedule is RARELY exactly what you want.** A signup creates a "Working hours" schedule defaulting to Mon-Fri 09:00-17:00 in the user's onboarding-selected timezone. **Always inspect AND ask the operator** before assuming the default fits. We rolled with the default 09:00-17:00 initially in this engagement; operator wanted 11:00-18:00. Cost: zero, fixed via single PATCH. But it's a reminder — defaults are starting points, not final answers.
5a. **Schedule PATCH is full-state replacement, not diff.** PATCH `/v2/schedules/{id}` requires `name` + `timeZone` + `availability` even if you're only changing one of them. Sending only the changed field returns HTTP 200 but silently reverts the unsent fields to defaults. Always send the full schedule object.
5b. **`bookingLimitsCount` enforces caps at the slots-API level.** Setting `{day: 4}` makes the public booking page hide all remaining slots once 4 bookings exist for that day. Cal.com Free supports `day` (verified); `week`/`month`/`year` may be Pro-only on some accounts.

11. **Cal.com REPLACES Google Calendar default reminders with hardcoded 1-hour reminders.** When Cal.com creates events on the host's connected Google Calendar, it sets `reminders: {useDefault: false, overrides: [{method: "email", minutes: 60}, {method: "popup", minutes: 60}]}`. Your configured calendar default doesn't apply; Cal.com's 1-hour reminder fires instead.
    - **Empirically verified 2026-05-08**: 2 test bookings (id 1041405 + 1041499) both showed 1h email + 1h notification despite host's calendar default being set to 30 min.
    - **API check**: Cal.com v2 `/v2/calendars` exposes connected calendars but does NOT expose a "default reminders" override field for free-tier event-types. No Free-tier path to change the hardcoded 1h via API.
    - **Diagnostic history**: this lesson iterated through 3 versions during the session. First captured as "Cal.com strips all reminders" (host saw `Notifications only apply to you` — but on the wrong calendar; turned out to be a different Google account where the calendar was synced via sharing, and reminder defaults don't sync across accounts). Then corrected to "Cal.com replaces with hardcoded 1h reminders" (verified on the correct connected calendar). Then verified persists across multiple bookings and across calendar-default changes.
    - **Implication for cadence**: Brevo Template C (1h attendee reminder) becomes redundant for typical Google-Calendar attendees because Cal.com's iCal-embedded 1h reminder already covers them. Template is kept in Brevo as a dormant asset (push cost zero) but Worker doesn't fire. Re-enable later if real-world data shows Outlook / Apple Calendar attendees missing reminders due to client-side stripping of embedded reminders.
    - **Implication for host**: 1h calendar reminder fires automatically (good). T-2h Brevo Template 6 (operator pre-call brief) remains the FIRST timing nudge with the booking-question answers surfaced — calendar reminders only show "what + when + meet link", not the brief content.
    - **Workarounds if 1h becomes problematic**: (a) manual per-event reminder edit on host's calendar (one click; not scalable); (b) Cal.com Pro tier workflows can customize reminders ($144/year, skipped for zero-subscription ethos); (c) accept the hardcode as Cal.com platform behavior.
6. **`bookingWindow` does not accept create-time payloads.** It is silently dropped on POST `/v2/event-types`. PATCH after creation. Same probably applies to other settings flagged `disabled: true` in default responses; verify by reading the response, not assuming the create payload was honoured.
7. **`minimumBookingNotice` is in minutes.** Easy to misread as hours when reading docs casually. 12 hours = 720, not 12.
8. **Custom booking fields append, not replace.** The defaults (`name`, `email`, `location`, `notes`, `guests`, `rescheduleReason`, `title`) come back in the response automatically; do not include them in your create payload or you will create duplicates.
9. **OAuth-driven onboarding skips email verification.** "Sign up with Google" pre-verifies the email, so no confirmation email arrives. Not a bug — Google's verification is trusted.
10. **API key value is shown ONCE.** The Cal.com generate-key modal shows the value once and a "this is the only time you will see this" warning. Always copy into a scratch buffer FIRST, close modal SECOND, verify the key appears in the keys-list page THIRD. If the keys list does not show it, the key was never persisted; regenerate.

## Execution evidence — 2026-05-08

| What | Value |
|---|---|
| Cal.com region | EU (`cal.eu`, API `api.cal.eu`) |
| Username | `hoiboyuk` |
| Booking URL | https://cal.eu/hoiboyuk/discovery |
| Event type | id 284432, "20 min discovery call", slug `discovery`, 20 min, 10-min before/after buffers, 12h min notice, 30-day rolling booking window |
| Daily booking cap | 4 per day (`bookingLimitsCount.day = 4`) |
| Schedule | id 42584, Mon-Fri **11:00-18:00 Europe/London** (corrected from auto-default 09:00-17:00) |
| Custom booking fields (4) | `company-name` (req), `ai-tool-today` (opt), `distinct-roles` (req — added 2026-05-08), `hope-to-get` (req textarea) |
| Default location | Google Meet integration, credentialId 61497 |
| Live test booking | id 1041405, uid `83GC1L3fhD5mwPKEna9vsa`, 2026-05-11 11:00 BST, Google Meet `https://meet.google.com/rdg-huya-vjr` — used to verify the booking flow + send Cal.com's default email so Hoi could compare against Brevo's Hoi-voice templates |

### Cadence iteration on operator brief (lessons in real-time)

Drafted T-15min → bumped T-30min → bumped T-1h → settled **T-2h**. Each iteration was the host realising prep time matters more than they initially thought. Documenting because future-Hoi (or future client running similar discovery calls) will likely settle on a different number — process matters more than the literal time.

### Cadence iteration on attendee reminders

Drafted full A+B+C+D+E. Considered "Light" cadence (drop C). Re-enabled C as insurance after discovering Cal.com strips calendar reminders. Final: A active, B active, **C active (insurance)**, D active, E active. See Lessons #11 for why C is load-bearing not optional.

## Reproduction checklist (for the next client / instance)

- [ ] Phase A complete (signup + Google OAuth + Meet + API key generated and confirmed in keys list)
- [ ] Region identified (URL bar check: `cal.com` or `cal.eu`)
- [ ] `CAL_API_KEY` and `CAL_BASE` exported in shell
- [ ] `GET /v2/me` returns 200 with expected email + name
- [ ] Schedule confirmed Mon-Fri 09:00-17:00 in correct timezone (PATCH if not)
- [ ] Default 30-min event type shows `google-meet` location with `credentialId`
- [ ] `discovery` event type created (POST), response includes `bookingUrl`
- [ ] Booking window patched to 30 days rolling
- [ ] Path A or Path B chosen for emails
- [ ] If Path A: 5 workflows + operator reminder pasted into Cal.com UI from the canonical templates above
- [ ] If Path B: webhook configured + Worker deployed + Brevo SMTP wired
- [ ] `data/consulting.yaml` `calcom_booking` patched to live URL
- [ ] Local Hugo render confirms both top + bottom CTAs flip from `mailto:` fallback
- [ ] Test booking from incognito browser → confirms attendee email arrives + meeting link works + calendar invite lands
- [ ] API key revoked once setup is complete (Settings → Developer → API keys → delete)

## File-of-record

Primary: this file (`docs/cal-com-setup.md`).
Secondary (handover memory): `~/.claude/projects/-home-hoiung-DevProjects/memory/HANDOVER_consulting_ops_2_stage4_part3_2026-05-07.md` § "Cal.com setup (current state — Hoi-blocked)".
Templates also duplicated in handover memory; if changed, update both.
