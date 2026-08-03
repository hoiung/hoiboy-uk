// Newsletter double opt-in subscribe handler (issue #56 Phase 3).
//
// Cloudflare Pages Function, route: POST /api/subscribe
//   0. Fail loud if any of the three Brevo bindings is absent.
//   1. Reject an oversized body up front (content-length ceiling) before parsing.
//   2. Honeypot drop (silent redirect, no side effects).
//   3. Mandatory Turnstile server-side siteverify (403 on failure).
//   4. Validate the two fields. An over-length email is REJECTED, never truncated.
//   5. Consent presence + known-version allowlist, fail loud on absent/unknown.
//   6. Brevo double-opt-in call (this is the only write).
//   7. 303 redirect to the "check your inbox" page.
//
// Ordering rationale: the worse failure here is losing a subscriber, not missing a
// notification. So nothing is written until Turnstile and consent both pass, and the
// binding check runs before any of it, so a misconfigured deploy is loud on the very
// first request rather than after a visitor has already filled the form.
//
// All secrets/bindings come from context.env (dashboard-configured); there are NO
// secret literals in this file. See docs/research/09_DEPLOYMENT.md.
//
// Turnstile: verified against env.TURNSTILE_SECRET_KEY, the binding the AGIT form
// already uses. One Turnstile widget config serves the whole domain, so this endpoint
// adds no new Turnstile provisioning.
//
// Reuse note: functions/api/contribute.js is NOT importable (one export, every helper
// module-private), so the few helpers below are written for this endpoint rather than
// hand-mirrored from it a third time.

// --- configuration (non-secret) ---
// Where the browser lands after a successful POST. This is deliberately NOT the
// confirmation page: at this point the address is unverified, and telling someone
// they are subscribed before they click the email would make the double opt-in a
// lie. CONFIRMED_PATH is where Brevo sends them AFTER the click.
const CHECK_INBOX_PATH = "/newsletter/check-inbox/";
const CONFIRMED_PATH = "/newsletter/confirmed/";

const BREVO_DOI_ENDPOINT = "https://api.brevo.com/v3/contacts/doubleOptinConfirmation";

// The whole request is two short text fields plus a Turnstile token (~2 KB), so this
// ceiling is generous. It exists to reject a junk body before it is buffered at all.
const MAX_BODY_BYTES = 32 * 1024;

// field name -> max length. A valid-token bot can still POST garbage, so these are
// enforced server-side regardless of the maxlength attributes on the form.
const FIELD_CAPS = { name: 100, email: 254 };

// Consent-label versions this endpoint accepts. The form posts the version of the
// label it rendered, so the stored record shows which wording was actually agreed to.
// An unknown or absent version is REJECTED rather than defaulted: a silent default
// would relabel a submission as consenting to wording it never saw. Newest first;
// keep older entries so an in-flight submission from a cached page still validates.
// MUST match the hidden input in layouts/_partials/subscribe-form.html and the mirror
// in tests/subscribe.test.js. Gate: tests/test_newsletter_consent_version.py
const KNOWN_CONSENT_VERSIONS = ["2026-08-03"];

// Pragmatic email shape check (not full RFC 5322): non-space local@domain.tld.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function log(event, detail) {
  // Structured observability line (repo AP #12). One per decision branch.
  try {
    console.log(JSON.stringify({ fn: "subscribe", event, ...detail }));
  } catch (_) {
    console.log(`subscribe ${event}`);
  }
}

// Strip CR/LF/control characters and trim. Length is checked BEFORE this runs, so
// the slice here is a belt-and-braces floor and never the thing that shortens a
// real submission.
function clean(value, max) {
  return String(value == null ? "" : value)
    .replace(/[\r\n\t\f\v\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, " ")
    .trim()
    .slice(0, max);
}

function textResponse(status, message) {
  return new Response(message, {
    status,
    headers: { "content-type": "text/plain; charset=utf-8" },
  });
}

async function verifyTurnstile(secret, response, remoteip) {
  const body = new FormData();
  body.append("secret", secret);
  body.append("response", response || "");
  if (remoteip) body.append("remoteip", remoteip);
  const resp = await fetch(
    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    { method: "POST", body },
  );
  return await resp.json();
}

// Brevo signals "this contact is already on the list" with a 4xx carrying a `code`
// field. The exact spelling is matched loosely, and the raw code is logged on every
// non-2xx, because the precise string is UNVERIFIED until AC 0.5's live probe runs
// against the real account. A loose match plus a logged raw value fails safe in both
// directions: an unrecognised duplicate spelling degrades to a 502 the operator can
// see in the logs, rather than a silent wrong answer.
function isDuplicateCode(code) {
  return typeof code === "string" && code.toLowerCase().includes("duplicate");
}

export async function onRequestPost(context) {
  const { request, env } = context;

  // 0. Fail loud on a missing binding. Checked per name, not by one alternation, so
  //    a deploy carrying two of the three cannot pass this guard.
  const missingBindings = [];
  if (!env.BREVO_API_KEY) missingBindings.push("BREVO_API_KEY");
  if (!env.BREVO_LIST_ID) missingBindings.push("BREVO_LIST_ID");
  if (!env.BREVO_DOI_TEMPLATE_ID) missingBindings.push("BREVO_DOI_TEMPLATE_ID");
  if (missingBindings.length > 0) {
    log("config-missing", { missing: missingBindings });
    return textResponse(500, "The subscribe form is not fully configured yet. Please try again later.");
  }

  // 1. Cheap up-front guard: reject an oversized body before buffering/parsing it.
  const declaredLength = Number(request.headers.get("content-length") || 0);
  if (declaredLength > MAX_BODY_BYTES) {
    log("size-reject", { declaredLength });
    return textResponse(413, "That submission is too large.");
  }

  let form;
  try {
    form = await request.formData();
  } catch (_) {
    log("bad-request", { reason: "formData parse failed" });
    return textResponse(400, "Could not read the form.");
  }

  // 2. Honeypot: a real person never fills the hidden "website" field.
  if (form.get("website")) {
    log("honeypot-drop", {});
    // Look successful to the bot; do NOT write anything.
    return Response.redirect(new URL(CHECK_INBOX_PATH, request.url), 303);
  }

  // 3. Turnstile siteverify (mandatory).
  const turnstileResponse = form.get("cf-turnstile-response");
  const remoteip = request.headers.get("CF-Connecting-IP") || "";
  let outcome;
  try {
    outcome = await verifyTurnstile(env.TURNSTILE_SECRET_KEY, turnstileResponse, remoteip);
  } catch (err) {
    log("turnstile-fail", { reason: "siteverify request errored", error: String(err) });
    return textResponse(403, "Verification failed. Please try again.");
  }
  if (!outcome || outcome.success !== true) {
    log("turnstile-fail", { codes: (outcome && outcome["error-codes"]) || null });
    return textResponse(403, "Verification failed. Please try again.");
  }

  // 4. Fields. The length check runs on the RAW value, before any sanitising: a
  //    255-character address truncated to 254 still satisfies EMAIL_RE, so the
  //    confirmation would go to whatever address the truncation happens to spell.
  //    Reject it instead.
  let email = String(form.get("email") == null ? "" : form.get("email"));
  if (email.length > FIELD_CAPS.email) {
    log("validation-reject", { reason: "over-length email", length: email.length });
    return textResponse(400, "That email address is too long. Please check it.");
  }
  email = clean(email, FIELD_CAPS.email);
  const name = clean(form.get("name"), FIELD_CAPS.name);

  if (!name || !email) {
    log("validation-reject", { name: !!name, email: !!email });
    return textResponse(400, "Please fill in your name and email.");
  }
  if (!EMAIL_RE.test(email)) {
    log("validation-reject", { reason: "bad email format" });
    return textResponse(400, "That email address does not look right. Please check it.");
  }

  // 5. Consent must be explicitly ticked, and we must know WHICH label was ticked.
  if (!form.get("consent")) {
    log("validation-reject", { reason: "consent not given" });
    return textResponse(400, "Please tick the box to confirm you want the emails.");
  }
  const consentVersion = clean(form.get("consent_version"), 32);
  if (!KNOWN_CONSENT_VERSIONS.includes(consentVersion)) {
    log("validation-reject", { reason: "unknown consent version", consentVersion: consentVersion || null });
    return textResponse(400, "This form is out of date. Please reload the page and try again.");
  }

  // 6. Brevo double opt-in. Brevo emails the confirmation link and only adds the
  //    contact to the list once it is clicked, so this call creates no confirmed
  //    subscriber on its own.
  //
  //    CONSENT_TIMESTAMP is the SUBMISSION time. The CONFIRMATION time is Brevo's
  //    own double-opt-in date on the contact. Both are needed and they are not the
  //    same fact: the first evidences when this label was accepted, the second when
  //    the address was verified. The Privacy Notice (AC 1.2) states that this pair
  //    is stored, so these attributes are what make that claim true and what
  //    discharges the Article 7(1) burden of proving consent.
  const doiPayload = {
    email,
    attributes: {
      FIRSTNAME: name,
      CONSENT_VERSION: consentVersion,
      CONSENT_TIMESTAMP: new Date().toISOString(),
    },
    includeListIds: [Number(env.BREVO_LIST_ID)],
    templateId: Number(env.BREVO_DOI_TEMPLATE_ID),
    redirectionUrl: new URL(CONFIRMED_PATH, request.url).toString(),
  };

  let resp;
  try {
    resp = await fetch(BREVO_DOI_ENDPOINT, {
      method: "POST",
      headers: {
        "api-key": env.BREVO_API_KEY,
        "content-type": "application/json",
        accept: "application/json",
      },
      body: JSON.stringify(doiPayload),
    });
  } catch (err) {
    log("brevo-doi", { ok: false, reason: "network", error: String(err) });
    return textResponse(502, "Something went wrong signing you up. Please try again.");
  }

  if (!resp.ok) {
    const detail = (await resp.text()).slice(0, 500);
    let code = null;
    try {
      code = JSON.parse(detail).code;
    } catch (_) {
      code = null;
    }

    // Already on the list: answer exactly as a fresh success does. A distinct
    // status here would let anyone test whether a given address is subscribed.
    if (isDuplicateCode(code)) {
      log("brevo-doi", { ok: true, duplicate: true, status: resp.status, code });
      return Response.redirect(new URL(CHECK_INBOX_PATH, request.url), 303);
    }

    // Brevo's send cap is shared account-wide, so a retry storm is the worse
    // failure. Tell the visitor to come back rather than retrying in the Function.
    if (resp.status === 429) {
      log("brevo-doi", { ok: false, reason: "rate-limit", status: resp.status, code, detail });
      return textResponse(503, "We are sending a lot of email right now. Please try again in a few minutes.");
    }

    log("brevo-doi", { ok: false, reason: "upstream", status: resp.status, code, detail });
    return textResponse(502, "Something went wrong signing you up. Please try again.");
  }

  log("brevo-doi", { ok: true, duplicate: false, status: resp.status, consentVersion });

  // 7. Success -> redirect (303 so the browser re-requests with GET).
  return Response.redirect(new URL(CHECK_INBOX_PATH, request.url), 303);
}
