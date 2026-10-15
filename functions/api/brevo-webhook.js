// POST /api/brevo-webhook -- the new-subscriber alert (#56 AC 0.3) and the AGIT
// welcome email (#65 Phase 2).
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
// THE AGIT WELCOME. When the delivery's list_id contains the AGIT list, the handler
// reads the contact and sends the welcome email (WhatsApp invite) once: only if the
// contact is on the AGIT list, carries AGIT_CONSENT_VERSION (written by the signup
// form, so no form submission = no invite) and has no AGIT_WELCOME_SENT yet. It
// writes AGIT_WELCOME_SENT BEFORE sending, so a repeat delivery skips. Brevo's
// list_id lists EVERY list the contact is now on, so that marker is what stops a
// member's later newsletter signup from sending a second invite. The invite link
// comes from the AGIT_WHATSAPP_INVITE_URL secret as a template param; it is never
// logged, never put in the alert, never stored at Brevo outside the sent email.
//
// AUTHENTICATION. Brevo does not sign its webhook calls: there is no HMAC header to
// verify. The URL itself is therefore the credential, so it carries a secret token
// that must match BREVO_WEBHOOK_TOKEN. Anyone who learns the URL can forge a call,
// which is why the token is a Pages SECRET. A forged call can at most send the
// operator an alert, or send the welcome to a contact who signed up for it and has
// not had it yet: the contact read, not the payload, decides who gets an invite.
// Attacker-supplied text is only ever echoed, escaped, into the operator alert.

const BREVO_EMAIL_ENDPOINT = "https://api.brevo.com/v3/smtp/email";
const BREVO_UNBLOCK_ENDPOINT = "https://api.brevo.com/v3/smtp/blockedContacts";
const BREVO_CONTACTS_ENDPOINT = "https://api.brevo.com/v3/contacts";

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

// What a FAILED welcome line tells the operator to do. The procedure lives in the
// docs, so this names it rather than restating it.
const RESEND_HINT = "To resend it, follow \"Resend a welcome\" in docs/brevo-api-setup.md.";

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

// Same rule as subscribe.js: a binding id must be a positive integer, not merely set.
function isPositiveId(v) {
  return Number.isInteger(Number(v)) && Number(v) > 0 && String(v).trim() !== "";
}

// The invite link, trimmed, or null when it is not a plain https URL. A link with
// whitespace inside would be split by a mail client into a broken button.
function inviteUrl(value) {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed.startsWith("https://") || /\s/.test(trimmed)) return null;
  return trimmed;
}

function brevoHeaders(env) {
  return { "api-key": env.BREVO_API_KEY, "content-type": "application/json", accept: "application/json" };
}

// The AGIT welcome, as a sequence of guarded steps. Returns the alert line's status:
// "sent", "already sent (skipped)", "skipped: no AGIT signup record", or
// "FAILED (<step> <status>)". A failed read or marker write sends nothing. Errors are
// logged by step and status only: never a response body, never the address, never
// the invite link.
async function sendAgitWelcome(email, invite, env, log) {
  const agitListId = Number(env.AGIT_LIST_ID);
  const contactUrl = `${BREVO_CONTACTS_ENDPOINT}/${encodeURIComponent(email.toLowerCase())}`;
  const shape = emailShape(email);

  const read = await fetch(contactUrl, { method: "GET", headers: brevoHeaders(env) });
  if (!read.ok) {
    log("agit-welcome", { ok: false, step: "contact-read", status: read.status, shape });
    return `FAILED (contact read ${read.status})`;
  }
  const contact = await read.json();
  const listIds = Array.isArray(contact.listIds) ? contact.listIds.map(Number) : [];
  const attributes = (contact && contact.attributes) || {};
  if (!listIds.includes(agitListId) || !attributes.AGIT_CONSENT_VERSION) {
    log("agit-welcome", { ok: true, outcome: "no-signup-record", shape });
    return "skipped: no AGIT signup record";
  }
  if (attributes.AGIT_WELCOME_SENT) {
    log("agit-welcome", { ok: true, outcome: "already-sent", shape });
    return "already sent (skipped)";
  }
  const to = contact.email;
  if (typeof to !== "string" || !to.includes("@")) {
    log("agit-welcome", { ok: false, step: "contact-email", shape });
    return "FAILED (contact read returned no email)";
  }

  // The marker goes on BEFORE the send, so a second delivery for this confirm
  // finds it and skips. Clearing AGIT_LEFT here is what lets a former member
  // re-join and get a fresh invite.
  const mark = await fetch(contactUrl, {
    method: "PUT",
    headers: brevoHeaders(env),
    body: JSON.stringify({ attributes: { AGIT_WELCOME_SENT: new Date().toISOString(), AGIT_LEFT: "" } }),
  });
  if (!mark.ok) {
    log("agit-welcome", { ok: false, step: "marker-write", status: mark.status, shape });
    return `FAILED (marker write ${mark.status})`;
  }

  const send = await fetch(BREVO_EMAIL_ENDPOINT, {
    method: "POST",
    headers: brevoHeaders(env),
    body: JSON.stringify({
      templateId: Number(env.AGIT_WELCOME_TEMPLATE_ID),
      to: [{ email: to }],
      params: { INVITE_URL: invite },
    }),
  });
  if (!send.ok) {
    log("agit-welcome", { ok: false, step: "welcome-send", status: send.status, shape });
    return `FAILED (welcome send ${send.status})`;
  }
  log("agit-welcome", { ok: true, outcome: "sent", shape });
  return "sent";
}

// Decide this delivery's AGIT part. `delivery` = the list_id contains the AGIT list;
// `line` = the "AGIT welcome email:" status, or null when there is nothing to say.
async function agitPart(email, listIds, env, log) {
  if (!isPositiveId(env.AGIT_LIST_ID)) {
    // Without the id an AGIT delivery cannot be told from a newsletter one, so the
    // line goes on EVERY alert: a misconfiguration the operator has to see.
    log("config-missing", { missing: ["AGIT_LIST_ID"] });
    return { delivery: false, line: "NOT sent (missing AGIT_LIST_ID)" };
  }
  if (!listIds.map(Number).includes(Number(env.AGIT_LIST_ID))) return { delivery: false, line: null };

  const missing = [];
  if (!isPositiveId(env.AGIT_WELCOME_TEMPLATE_ID)) missing.push("AGIT_WELCOME_TEMPLATE_ID");
  const invite = inviteUrl(env.AGIT_WHATSAPP_INVITE_URL);
  if (!invite) missing.push("AGIT_WHATSAPP_INVITE_URL");
  if (missing.length) {
    log("config-missing", { missing });
    return { delivery: true, line: `NOT sent (missing ${missing.join(", ")})` };
  }

  try {
    return { delivery: true, line: await sendAgitWelcome(email, invite, env, log) };
  } catch (err) {
    // A network error or a non-JSON body. The name only: String(err) can carry a URL.
    const reason = (err && err.name) || "error";
    log("agit-welcome", { ok: false, step: "exception", reason, shape: emailShape(email) });
    return { delivery: true, line: `FAILED (${reason})` };
  }
}

// The operator alert. A delivery without the AGIT list gets today's alert byte for
// byte. An AGIT delivery is labelled by what THIS delivery did, never by list_id
// alone, because list_id lists every list the contact is on.
function buildAlert(email, listIds, agit, env) {
  const safeEmail = escapeHtml(email);
  const listLine = `<p>List: ${escapeHtml(listIds.join(", ") || "unknown")}</p>`;
  const newsletterParagraph =
    `<p>This fired on Brevo's listAddition event, which under double opt-in means ` +
    `they clicked the confirmation link. They are a confirmed subscriber, not just ` +
    `someone who typed an address into the form.</p>`;
  const agitLine = agit.line === null
    ? ""
    : `<p>AGIT welcome email: ${escapeHtml(agit.line)}</p>` +
      (agit.line.startsWith("FAILED") ? `<p>${escapeHtml(RESEND_HINT)}</p>` : "");

  if (!agit.delivery) {
    return {
      subject: `New newsletter subscriber: ${email}`,
      htmlContent:
        `<p>Someone confirmed their subscription to hoiboy.uk.</p>` +
        `<p><strong>${safeEmail}</strong></p>` + listLine + newsletterParagraph + agitLine,
    };
  }

  const joined = agit.line === "sent" || agit.line.startsWith("FAILED");
  const onNewsletter = isPositiveId(env.BREVO_LIST_ID)
    && listIds.map(Number).includes(Number(env.BREVO_LIST_ID));
  if (joined) {
    return {
      subject: `New AGIT member: ${email}`,
      htmlContent:
        `<p>Someone joined Asians &amp; Gingers in Tech.</p>` +
        `<p><strong>${safeEmail}</strong></p>` + listLine + agitLine +
        `<p>This fired on Brevo's listAddition event: they clicked the confirmation link ` +
        `in the AGIT signup email.</p>`,
    };
  }
  if (onNewsletter) {
    return {
      subject: `New newsletter subscriber: ${email}`,
      htmlContent:
        `<p>Someone confirmed their subscription to hoiboy.uk.</p>` +
        `<p><strong>${safeEmail}</strong></p>` + listLine + agitLine + newsletterParagraph,
    };
  }
  return {
    subject: `List addition: ${email}`,
    htmlContent:
      `<p>A contact was added to a list.</p>` +
      `<p><strong>${safeEmail}</strong></p>` + listLine + agitLine,
  };
}

// Send the alert, with the one self-heal this endpoint has. Logs its own outcome;
// returns nothing, because the 200 to Brevo was decided before this ran.
async function sendAlert(alert, email, listIds, env, log) {
  const body = {
    sender: { name: "hoiboy.uk", email: "hello@hoiboy.uk" },
    to: [{ email: ALERT_TO }],
    subject: alert.subject,
    htmlContent: alert.htmlContent,
  };

  let resp;
  try {
    resp = await fetch(BREVO_EMAIL_ENDPOINT, {
      method: "POST", headers: brevoHeaders(env), body: JSON.stringify(body),
    });
  } catch (err) {
    log("alert-send", { ok: false, reason: "network", error: (err && err.name) || "error" });
    return;
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
    //
    // Scoped to ALERT_TO only. The member-side welcome send never unblocks: a member
    // who clicked unsubscribe on an AGIT email chose that, and is asked to email us.
    const firstStatus = resp.status;
    let unblockStatus = null;
    try {
      const unblock = await fetch(
        `${BREVO_UNBLOCK_ENDPOINT}/${encodeURIComponent(ALERT_TO)}`,
        { method: "DELETE", headers: { "api-key": env.BREVO_API_KEY, accept: "application/json" } },
      );
      unblockStatus = unblock.status;
      resp = await fetch(BREVO_EMAIL_ENDPOINT, {
        method: "POST", headers: brevoHeaders(env), body: JSON.stringify(body),
      });
    } catch (err) {
      log("alert-recover", { ok: false, firstStatus, unblockStatus, error: (err && err.name) || "error" });
      return;
    }

    if (!resp.ok) {
      log("alert-send", {
        ok: false, firstStatus, unblockStatus, retryStatus: resp.status,
        shape: emailShape(email),
      });
      return;
    }
    // Recorded distinctly so a recovered send is visible in the logs rather than
    // looking identical to one that worked first time.
    log("alert-recover", { ok: true, firstStatus, unblockStatus, shape: emailShape(email) });
    return;
  }

  log("alert-send", { ok: true, shape: emailShape(email), lists: listIds.length });
}

export async function onRequestPost(context) {
  const { request, env } = context;
  const fn = "brevo-webhook";
  const log = (event, detail) => {
    try {
      console.log(JSON.stringify({ fn, event, ...detail }));
    } catch (_) {
      console.log(`${fn} ${event}`);
    }
  };

  // 0. Fail loud on config, same contract as subscribe.js: name what is missing on
  //    the FIRST request rather than half-working. The AGIT bindings are checked in
  //    the AGIT branch instead, so a missing one never blocks the newsletter alert.
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

  // 3. Answer Brevo now and do the work after the response. Brevo documents no
  //    retry or timeout for this event, so a slow reply risks a duplicate delivery;
  //    the AGIT marker makes a duplicate harmless, and answering first makes one
  //    less likely. The outcome of the work is in the logs, not in this response.
  const listIds = Array.isArray(payload.list_id) ? payload.list_id : [];
  context.waitUntil((async () => {
    const agit = await agitPart(email, listIds, env, log);
    await sendAlert(buildAlert(email, listIds, agit, env), email, listIds, env, log);
  })());
  return textResponse(200, "Accepted.");
}
