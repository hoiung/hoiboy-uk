// POST /api/brevo-webhook -- the new-subscriber alert (#56 AC 0.3).
//
// WHY THIS EXISTS RATHER THAN A BREVO AUTOMATION.
// The operator asked to be told about "every new subscriber ... so I can easily
// keep track how many new subscribers". Brevo's Automations product would do it,
// but it has NO API: the v3 spec mentions "automation" 37 times and "workflow" 27,
// and not one is an endpoint -- they are all read-only account metadata. A dashboard
// workflow is also un-reviewable, un-testable, and cannot be handed to a client as a
// script, which is the whole point of docs/brevo-api-setup.md.
//
// Webhooks DO have endpoints, so the same alert becomes ordinary version-controlled
// code. It also fires on the RIGHT event. `listAddition` happens when Brevo adds the
// contact to the list, which under double opt-in is the CONFIRMATION click. Alerting
// from inside subscribe.js instead (the Issue's AC 3.7) would fire at SUBMISSION,
// counting people who never confirm and bots that cleared Turnstile -- a bigger
// number that answers a different question than the one the operator asked.
//
// AUTHENTICATION. Brevo does not sign its webhook calls: there is no HMAC header to
// verify. The URL itself is therefore the credential, so it carries a secret token
// that must match BREVO_WEBHOOK_TOKEN. Anyone who learns the URL can forge an alert,
// which is why the token is a Pages SECRET and why this endpoint does nothing except
// send a fixed-shape email to one hard-coded address. It never writes, never reads
// contacts, and never echoes attacker-supplied text into anything but that email.

const BREVO_EMAIL_ENDPOINT = "https://api.brevo.com/v3/smtp/email";
const BREVO_UNBLOCK_ENDPOINT = "https://api.brevo.com/v3/smtp/blockedContacts";

// Where the alert goes. The operator named this address; it is not configurable by
// the request, so a forged call cannot redirect the alert somewhere else.
const ALERT_TO = "hoiboyuk@gmail.com";

// Must match the registered webhook. Guards against a webhook that is later widened
// to more events or more lists than this handler was written for.
//
// BOTH SPELLINGS, and this is not defensive padding. Brevo's SUBSCRIPTION enum on
// POST /v3/webhooks is camelCase `listAddition`, but the payload it later DELIVERS
// carries `"event":"list_addition"` in snake_case. Matching only the name you
// subscribed with means every real delivery is silently ignored -- which is exactly
// what happened on this Issue's first live signup: the contact confirmed, landed on
// the list, and the operator got nothing, because this handler answered 200 Ignored.
// The camelCase form is kept in case Brevo ever aligns the two.
const WATCHED_EVENTS = ["list_addition", "listAddition"];

function textResponse(status, message) {
  return new Response(message, {
    status,
    headers: { "content-type": "text/plain; charset=utf-8" },
  });
}

// Constant-time-ish compare. Workers has no timingSafeEqual, and a plain === leaks
// the shared prefix through timing. Length is compared first because an early return
// on differing length is not a secret worth protecting.
function tokensMatch(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// Log the local-part length rather than the address. The repo's PII discipline
// (rounds 11-15 of this Issue) is that a subscriber address never reaches a log line;
// the alert email is the only place it legitimately appears.
function emailShape(email) {
  if (typeof email !== "string" || !email.includes("@")) return "invalid";
  const [local, domain] = email.split("@");
  return `${local.length}@${domain.length}`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

export async function onRequestPost({ request, env }) {
  const fn = "brevo-webhook";
  const log = (event, detail) => {
    try {
      console.log(JSON.stringify({ fn, event, ...detail }));
    } catch (_) {
      console.log(`${fn} ${event}`);
    }
  };

  // 0. Fail loud on config, same contract as subscribe.js: name what is missing on
  //    the FIRST request rather than half-working.
  const missing = [];
  if (!env.BREVO_API_KEY) missing.push("BREVO_API_KEY");
  if (!env.BREVO_WEBHOOK_TOKEN) missing.push("BREVO_WEBHOOK_TOKEN");
  if (missing.length) {
    log("config-missing", { missing });
    return textResponse(500, "This endpoint is not configured.");
  }

  // 1. Authenticate before reading the body, so an unauthenticated caller cannot
  //    make us parse arbitrary JSON.
  const supplied = new URL(request.url).searchParams.get("token");
  if (!tokensMatch(supplied || "", env.BREVO_WEBHOOK_TOKEN)) {
    log("auth-reject", { supplied: Boolean(supplied) });
    return textResponse(403, "Forbidden.");
  }

  let payload;
  try {
    payload = await request.json();
  } catch (_) {
    log("bad-payload", { reason: "not json" });
    return textResponse(400, "Expected JSON.");
  }

  // 2. Brevo sends every subscribed event to the same URL. Ignore anything that is
  //    not the one we registered for, and say so with a 200: a non-2xx would make
  //    Brevo retry a delivery we deliberately do not want.
  const event = payload && payload.event;
  if (!WATCHED_EVENTS.includes(event)) {
    // The event name is logged so a future spelling change is diagnosable from the
    // logs rather than from a silent absence of alerts.
    log("ignored-event", { event: typeof event === "string" ? event : null });
    return textResponse(200, "Ignored.");
  }

  const email = payload.email || payload["email_address"] || "";
  if (!email) {
    log("bad-payload", { reason: "no email on listAddition" });
    return textResponse(200, "Ignored.");
  }

  // 3. Send the alert. Plain transactional send, no template, so this cannot break
  //    when the operator edits the DOI template.
  const listIds = Array.isArray(payload.list_id) ? payload.list_id : [];
  const safeEmail = escapeHtml(email);
  const body = {
    sender: { name: "hoiboy.uk", email: "hello@hoiboy.uk" },
    to: [{ email: ALERT_TO }],
    subject: `New newsletter subscriber: ${email}`,
    htmlContent:
      `<p>Someone confirmed their subscription to hoiboy.uk.</p>` +
      `<p><strong>${safeEmail}</strong></p>` +
      `<p>List: ${escapeHtml(listIds.join(", ") || "unknown")}</p>` +
      `<p>This fired on Brevo's listAddition event, which under double opt-in means ` +
      `they clicked the confirmation link. They are a confirmed subscriber, not just ` +
      `someone who typed an address into the form.</p>`,
  };

  let resp;
  try {
    resp = await fetch(BREVO_EMAIL_ENDPOINT, {
      method: "POST",
      headers: {
        "api-key": env.BREVO_API_KEY,
        "content-type": "application/json",
        accept: "application/json",
      },
      body: JSON.stringify(body),
    });
  } catch (err) {
    log("alert-send", { ok: false, reason: "network", error: String(err) });
    // 200 on purpose. The subscriber IS on the list; only our notification failed.
    // A non-2xx would have Brevo retry, which cannot fix our outbound problem and
    // would spend the shared 300/day cap on retries.
    return textResponse(200, "Alert failed, subscription unaffected.");
  }

  if (!resp.ok) {
    // SELF-HEAL THE ONE FAILURE NOBODY WOULD EVER NOTICE.
    //
    // Brevo attaches an unsubscribe link to these alerts, and Gmail renders it right
    // next to the sender name. One click puts ALERT_TO on Brevo's transactional
    // blocklist, after which every future alert is refused. Because this handler
    // answers 200 regardless (so Brevo does not retry against the shared 300/day
    // cap), the alerts would simply stop, with no error anywhere and nothing for the
    // operator to notice except an eventual suspicion that nobody has subscribed in
    // a while. That is the worst shape a bug can have: silent, permanent, and
    // triggered by a button placed in front of you on every message.
    //
    // The remedy is attempted on ANY non-2xx rather than by matching Brevo's
    // blocked-recipient error string, because that exact string is UNVERIFIED here
    // and pattern-matching an unverified message is how this Issue already lost an
    // afternoon. The unblock is idempotent and harmless: a 404 just means the
    // address was not blocked, in which case the retry is the ordinary retry that a
    // transient upstream failure deserves anyway.
    const firstStatus = resp.status;
    let unblockStatus = null;
    try {
      const unblock = await fetch(
        `${BREVO_UNBLOCK_ENDPOINT}/${encodeURIComponent(ALERT_TO)}`,
        { method: "DELETE", headers: { "api-key": env.BREVO_API_KEY, accept: "application/json" } },
      );
      unblockStatus = unblock.status;
      resp = await fetch(BREVO_EMAIL_ENDPOINT, {
        method: "POST",
        headers: {
          "api-key": env.BREVO_API_KEY,
          "content-type": "application/json",
          accept: "application/json",
        },
        body: JSON.stringify(body),
      });
    } catch (err) {
      log("alert-recover", { ok: false, firstStatus, unblockStatus, error: String(err) });
      return textResponse(200, "Alert failed, subscription unaffected.");
    }

    if (!resp.ok) {
      log("alert-send", {
        ok: false, firstStatus, unblockStatus, retryStatus: resp.status,
        shape: emailShape(email),
      });
      return textResponse(200, "Alert failed, subscription unaffected.");
    }
    // Recorded distinctly so a recovered send is visible in the logs rather than
    // looking identical to one that worked first time.
    log("alert-recover", { ok: true, firstStatus, unblockStatus, shape: emailShape(email) });
    return textResponse(200, "Alerted after recovery.");
  }

  log("alert-send", { ok: true, shape: emailShape(email), lists: listIds.length });
  return textResponse(200, "Alerted.");
}
