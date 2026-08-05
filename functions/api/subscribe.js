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
const UPSTREAM_BODY_CAP = 8 * 1024;

// field name -> max length. A valid-token bot can still POST garbage, so these are
// enforced server-side regardless of the maxlength attributes on the form.
const FIELD_CAPS = { name: 100, email: 254 };

// Consent-label versions this endpoint accepts. The form posts the version of the
// label it rendered, so the stored record shows which wording was actually agreed to.
// An unknown or absent version is REJECTED rather than defaulted: a silent default
// would relabel a submission as consenting to wording it never saw. Newest first;
// keep older entries so an in-flight submission from a cached page still validates.
// MUST match the hidden input in layouts/_partials/subscribe-form.html, the mirror
// in tests/subscribe.test.js, AND the version quoted in prose in
// content/legal/privacy/index.md -- FOUR surfaces, all four gated.
// Gate: tests/test_newsletter_consent_version.py
const KNOWN_CONSENT_VERSIONS = ["2026-08-03"];

// Pragmatic email shape check (not full RFC 5322): non-space local@domain.tld.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Marker for a value redacted because we HELD it (see redactString). Distinct
// from redactPii's `[email-redacted]`, which means "this merely looked like an
// address". The two are worth telling apart when reading a log: the first is a
// guarantee, the second is a pattern match.
const REDACTED_VALUE = "[redacted]";

// Shortest value worth redacting by literal match. A submitted email always
// clears this -- the shortest address anyone can type is six characters -- so
// the defect this exists to fix is fully covered. A very short NAME does not
// clear it, and that is deliberate: literal redaction is a blind substring
// replace, so a 2-character name like `on` would rewrite every ordinary word
// containing it in an upstream error body, garbling the diagnostic the log
// exists to provide while protecting nothing. Under-redacting a 1-3 character
// name is the lesser harm and is recorded here as a known limit rather than
// silently traded away.
//
// This threshold is NOT what keeps a held value away from a log line's own
// STRUCTURE. It cannot be: `name`, `code` and `size` all clear it, and a name
// of `code` once deleted that key from the finished line. Structure is
// protected by redactLine being shape-only -- see there.
const MIN_PROTECTED_LENGTH = 4;

// How many nested JSON escapings of a held value to generate when matching.
// Escaping compounds with nesting: an upstream body escapes a value once, our
// own serialisation escapes it again, and a JSON-in-JSON body escapes it twice.
// Exactly two levels were hard-coded here, which is the fixed-depth guess
// redactDeep's own docstring rejects one level down. Levels are generated to a
// fixpoint now; this only bounds the walk so a pathological value cannot spin.
const MAX_ESCAPE_LEVELS = 6;

// Strip address-SHAPED tokens out of text before it reaches a log.
//
// Upstream error bodies get echoed into our logs so a failure is diagnosable,
// and an upstream is free to quote back the value it rejected. That would put a
// subscriber's email address into a log line, which contradicts what
// content/legal/sub-processors/index.md publishes about this Function: that the
// submitted fields are handled in transit only and the request is not persisted.
//
// This is the SECOND of two redaction passes, and the weaker one. It catches an
// address we never held -- one an upstream quoted at us that no visitor of ours
// submitted -- which is the only case a literal match cannot cover. It runs at
// the capture point AND again over the serialised log line (see redactLine).
//
// It is deliberately NOT the primary defence, because it can only match what its
// character class admits, and that class is strictly narrower than EMAIL_RE's:
// see redactString for the gap and why widening this pattern is the wrong fix.
//
// The error stays diagnosable: the shape, the status and the upstream code all
// survive, only the address does not.
function redactPii(text) {
  if (typeof text !== "string") return text;
  // The LOCAL part deliberately allows an apostrophe; the domain does not.
  // RFC 5322 atext permits it unquoted, EMAIL_RE above accepts it, and real
  // subscribers have it (O'Brien, D'Angelo). Excluding it from the local class
  // meant `o'brien@example.com` redacted only from the apostrophe onward and
  // logged `o'[email-redacted]` -- a surviving local-part fragment, the same
  // defect as the truncation leak, reached by a different route (Ralph Tier 2).
  // A domain cannot contain one, so it stays excluded there and the pattern
  // still cannot run across a quoted JSON boundary.
  return text.replace(/[^\s"<>@,;:()]+@[^\s"'<>@,;:()]+\.[^\s"'<>@,;:()]+/g, "[email-redacted]");
}

// Read a request body, refusing to buffer more than `cap` bytes. Returns the
// bytes, or null if the body is over the cap. The stream is cancelled on the
// first chunk that crosses the line, so a sender cannot force us to hold an
// arbitrarily large body just by withholding a content-length header.
async function readCapped(request, cap) {
  if (!request.body) return new Uint8Array(0);

  const reader = request.body.getReader();
  const chunks = [];
  let total = 0;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > cap) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }

  const joined = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    joined.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return joined;
}

// An UPSTREAM response body, read with a ceiling. The REQUEST body has always
// been capped (readCapped above); the upstream reply was not, so a large or
// malformed body was pulled whole into an isolate's memory and then run through
// the entire redaction chain -- by-value forms times escape levels, each a
// linear scan -- before the 500-char slice bounded anything at all. The slice
// bounded what was STORED, never the work.
//
// Cutting a body raises the straddle hazard that `detail` is redacted BEFORE
// truncation to avoid: an address severed mid-token matches no pattern, and its
// local part lands verbatim in a structured log (Ralph round 15, reproduced end
// to end). A trailing-token trim was written here to close that, then removed --
// it could not be reached, let alone tested. UPSTREAM_BODY_CAP is 8 KB while
// `detail` keeps only the first 500 characters, so the cut is always ~7.7 KB
// past anything that can be logged. Defensive code that cannot fire is worse
// than none: it reads as protection and is never exercised.
//
// That safety is a RELATIONSHIP between two numbers, not a property of this
// function, so it is pinned by a test rather than by this comment. Raise the
// slice above the cap and the hazard returns.
async function readCappedText(response, cap) {
  if (!response.body) return "";

  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    total += value.byteLength;
    if (total >= cap) {
      await reader.cancel();
      break;
    }
  }

  // Trimmed to `cap`, NOT to `total`. Stopping the read is not the same as
  // bounding it: a body delivered as ONE chunk is already in `chunks` by the
  // time the check runs, so keeping `total` bytes would keep the entire body and
  // the ceiling would be decorative. This is not hypothetical -- the first
  // version did exactly that, and its two tests passed anyway because the
  // 500-char slice hid the miss. Copy only what the cap allows.
  const kept = Math.min(total, cap);
  const joined = new Uint8Array(kept);
  let offset = 0;
  for (const chunk of chunks) {
    if (offset >= kept) break;
    const room = kept - offset;
    joined.set(chunk.byteLength > room ? chunk.subarray(0, room) : chunk, offset);
    offset += chunk.byteLength;
  }
  // Decoded through Response rather than TextDecoder: both exist in Workers, but
  // Response is already the primitive this file builds every reply with, so the
  // helper adds no new runtime global for a harness to have to provide.
  return await new Response(joined).text();
}

// Every spelling a value can take inside an ALREADY-SERIALISED JSON line. The
// line is built by JSON.stringify, so `"pat"@example.net` appears in it as
// `\"pat\"@example.net`. Matching only the raw form would miss precisely the
// shapes this redactor exists to catch, because the characters that force the
// escaping are the same ones the shape pattern cannot handle.
function literalForms(value) {
  const forms = [];
  let form = value;
  for (let level = 0; level < MAX_ESCAPE_LEVELS; level += 1) {
    if (!forms.includes(form)) forms.push(form);
    const next = JSON.stringify(form).slice(1, -1);
    if (next === form) break;
    form = next;
  }
  // Longest first, so a deeper escaping is replaced before a shallower form
  // whose characters it contains.
  return forms.sort((a, b) => b.length - a.length);
}

// Replace every occurrence of one literal, ignoring case where that is safe.
//
// Not a regex: the needle is visitor-supplied and would have to be escaped
// before it could be used as a pattern. Case-insensitive because an upstream is
// free to normalise the case of an address it echoes back, and a local part can
// carry characters the shape pass cannot match, so a case-sensitive compare left
// `"Pat"@Example.net` leaking when it came back lowercased.
//
// Case folding can change a string's LENGTH (Unicode special-casing), which
// would misalign the index arithmetic below. Where that happens this falls back
// to an exact compare rather than risk a wrong offset: missing a case variant is
// a smaller harm than corrupting the text, and the fallback is precise.
function replaceLiteral(text, needle, replacement) {
  if (!needle) return text;
  const hay = text.toLowerCase();
  const pin = needle.toLowerCase();
  if (hay.length !== text.length || pin.length !== needle.length) {
    return text.split(needle).join(replacement);
  }
  let out = "";
  let from = 0;
  for (;;) {
    const at = hay.indexOf(pin, from);
    if (at === -1) break;
    out += text.slice(from, at) + replacement;
    from = at + needle.length;
  }
  return out + text.slice(from);
}

// Strip every known value out of one string, in each of its spellings.
//
// This is what closes the alphabet gap. EMAIL_RE accepts `"` `<` `>` `,` `;`
// `:` `(` `)` in a local part; redactPii's character class excludes exactly
// those. When one sits immediately before the `@`, the shape pattern cannot
// reach the `@` at all, nothing matches, and the FULL address is logged --
// `"patriley"@example.net` is the executed reproduction. Holding the literal
// removes the dependency on shape entirely: an accepted address is redactable
// because we have it, whatever it looks like.
//
// Widening the character class was tried twice -- the apostrophe fix, then the
// truncation fix -- and each widening left a narrower gap rather than closing
// the class. There is no third widening; the class is not the mechanism.
//
// Replacement is `split`/`join`, not a regex: the value is visitor-supplied and
// would otherwise need escaping before it could be used as a pattern.
function redactString(text, known) {
  let out = text;
  for (const value of known) {
    for (const form of literalForms(value)) {
      out = replaceLiteral(out, form, REDACTED_VALUE);
    }
  }
  return out;
}

// Redact every string ANYWHERE in a log detail, before it is serialised.
//
// Redacting only the finished line is not enough, because escaping compounds
// with nesting. An upstream error body is itself JSON, so an address inside it
// is already escaped once by the time we hold it as a string, and serialising
// that string into our own line escapes it a second time. Matching a fixed
// number of escaping levels would be the same guess-the-symptom mistake as
// widening the character class: the next nesting level reopens the hole.
//
// Walking the structure removes the guess. Each string is redacted while it is
// still a plain value, at whatever depth it sits, so no amount of subsequent
// serialisation can hide it.
function redactDeep(value, known) {
  if (typeof value === "string") return redactString(value, known);
  if (Array.isArray(value)) return value.map((item) => redactDeep(item, known));
  if (value && typeof value === "object") {
    const out = {};
    for (const [key, item] of Object.entries(value)) {
      out[key] = redactDeep(item, known);
    }
    return out;
  }
  return value;
}

// Value pass then shape pass, over RAW text we have read but not yet serialised
// -- an upstream error body at its capture point. The order is load-bearing:
// the shape pass rewrites part of an address whose local part carries a
// character its class excludes, which destroys the literal the value pass is
// holding, so the value pass must go first.
function redactText(text, known) {
  return redactPii(redactString(text, known));
}

// Final pass over the SERIALISED line: by SHAPE only.
//
// By-value redaction must NOT run here. A held value is arbitrary visitor text
// and the literal replace is blind, so a name of `code` or `reason` rewrote a
// structural KEY of the finished line -- deleting the diagnostic field, or
// emitting invalid JSON when the name carried a quote. Values are already
// redacted one level down by redactDeep, where each is still a plain string and
// cannot collide with structure. That is the only level at which a blind
// replace is safe; this level catches an address we never held.
function redactLine(line) {
  return redactPii(line);
}

// Build a per-request logger, plus the `protect` handle that registers a value
// for redaction.
//
// The known-value set is created HERE, once per invocation, and MUST NOT be
// module-level: a Worker isolate serves concurrent requests off a single module
// instance, so a shared mutable set would leak one visitor's address into
// another visitor's log line -- a worse bug than the one this fixes.
//
// Redaction happens where the line is WRITTEN, not at each capture point. The
// previous design redacted at capture and claimed that meant "a future log line
// cannot reintroduce the leak by forgetting", but it was wired at exactly one
// capture point, so every other request-derived field bypassed it. Redacting at
// the write boundary is the only placement a new log call cannot opt out of.
function createLogger(fn) {
  const known = new Set();

  function protect(value) {
    if (typeof value !== "string") return;
    if (value.length < MIN_PROTECTED_LENGTH) return;
    known.add(value);
  }

  function log(event, detail) {
    // Structured observability line (repo AP #12). One per decision branch.
    let line;
    try {
      line = JSON.stringify({ fn, event, ...redactDeep(detail, known) });
    } catch (_) {
      line = `${fn} ${event}`;
    }
    console.log(redactLine(line));
  }

  // For text captured OUTSIDE a log call (the upstream error body, which is
  // parsed for its `code` before it is ever logged). ORDER IS THE POINT:
  // redactText runs the by-value pass FIRST, on the pristine text, then the
  // shape pass. The shipped inversion -- redactPii at capture, by-value later
  // -- leaked, because on an address with an excluded character MID-local-part
  // the shape pass rewrites the suffix, destroys the exact literal the
  // by-value pass was holding, and the prefix survives every later pass. The
  // two redactors only stack in this order.
  // NOT redactLine: that one is deliberately shape-only and takes no `known`
  // set. Handing it the known values lets a submitted field literal-replace
  // its way through the SERIALISED line and rewrite the line's own structure,
  // which is what produced the subscribe-status oracle. Values are redacted
  // one level down by redactDeep, where they cannot collide with structure.
  function redact(text) {
    return redactText(text, known);
  }

  return { log, protect, redact };
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
    { method: "POST", body }
  );
  return await resp.json();
}

// Brevo signals "this contact is already on the list" with a 4xx carrying a `code`
// field. The exact spelling is matched loosely, and the raw code is logged on every
// non-2xx, because the precise string is UNVERIFIED until AC 0.5's live probe runs
// against the real account.
//
// The loose match is safe in ONE direction for free: an unrecognised duplicate
// spelling degrades to a 502 the operator can see in the logs. The OTHER direction
// is not free, and the caller is what makes it safe -- a loose substring would
// otherwise match a 429 or 5xx whose code merely CONTAINS "duplicate", answering
// 303 "check your inbox" to someone who will never receive an email. So the caller
// consults this only on a 4xx that is not 429; the status class, not this function,
// is what rules out the retryable failures (Ralph round 22 Tier 3).
function isDuplicateCode(code) {
  return typeof code === "string" && code.toLowerCase().includes("duplicate");
}

export async function onRequestPost(context) {
  const { request, env } = context;

  // Per-request logger. `protect` registers a value so that every subsequent
  // log line has it stripped, whatever field it travels in and whoever quotes
  // it back at us. Created per invocation on purpose -- see createLogger.
  const { log, protect, redact } = createLogger("subscribe");

  // 0. Fail loud on a missing binding. Checked per name, not by one alternation, so
  //    a deploy carrying two of the three cannot pass this guard.
  //    The two id bindings are additionally checked to be POSITIVE INTEGERS, not
  //    merely present. Truthiness alone let `BREVO_LIST_ID = "   "` through, and
  //    `Number("   ")` is 0, so the request went out as `includeListIds: [0]` --
  //    fail-closed at Brevo, but not the loud-on-first-request behaviour the
  //    header comment promises (Ralph round 22 Tier 3).
  const isPositiveId = (v) => Number.isInteger(Number(v)) && Number(v) > 0 && String(v).trim() !== "";
  const missingBindings = [];
  if (!env.BREVO_API_KEY) missingBindings.push("BREVO_API_KEY");
  if (!isPositiveId(env.BREVO_LIST_ID)) missingBindings.push("BREVO_LIST_ID");
  if (!isPositiveId(env.BREVO_DOI_TEMPLATE_ID)) missingBindings.push("BREVO_DOI_TEMPLATE_ID");
  if (missingBindings.length > 0) {
    log("config-missing", { missing: missingBindings });
    return textResponse(500, "The subscribe form is not fully configured yet. Please try again later.");
  }

  // 1. Size ceiling.
  //
  // content-length is a CLIENT-SUPPLIED hint, not a fact. A chunked request
  // carries none at all, and reading an absent header as 0 puts it under every
  // ceiling, so trusting it alone made this guard optional: omit the header and
  // an unbounded body reached formData() while the log line claiming a reject
  // never emitted. The header is therefore only a cheap fast-path reject. When
  // it is absent the body is read directly with a hard cap, and the stream is
  // cancelled the moment the cap is passed so nothing larger is ever buffered.
  // The header is a HINT and nothing more. It is client-supplied, so it can be
  // absent (chunked), or present and unparseable, or present and a lie. Any
  // branch that decides whether to bound the read BY consulting the header is
  // therefore bypassable by choosing the right header value. Two versions of
  // this guard shipped with exactly that shape and both were bypassable: first
  // by omitting the header, then by sending one that is not a number.
  //
  // So the header no longer selects anything. The body is ALWAYS read through
  // the cap. A credible declared length can only make us reject EARLIER, before
  // reading anything at all; it can never make us skip the bound.
  const declaredLength = Number(request.headers.get("content-length"));
  if (Number.isFinite(declaredLength) && declaredLength > MAX_BODY_BYTES) {
    log("size-reject", { source: "header", declaredLength });
    return textResponse(413, "That submission is too large.");
  }

  const capped = await readCapped(request, MAX_BODY_BYTES);
  if (capped === null) {
    log("size-reject", { source: "stream", declaredLength });
    return textResponse(413, "That submission is too large.");
  }
  // Re-wrap the bytes we read so formData() still has a body to parse. The
  // content type carries the multipart boundary, so it has to come across.
  const bodySource = new Response(capped, {
    headers: { "content-type": request.headers.get("content-type") || "" },
  });

  let form;
  try {
    form = await bodySource.formData();
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

  // Register both BEFORE the first log call that could carry either. The email
  // is the value this endpoint exists to protect; the name is registered too
  // because it is sent to Brevo as FIRSTNAME and an upstream error body is free
  // to quote back the payload it rejected.
  protect(email);
  protect(name);

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
    // Redacted HERE, at capture, so every use below is safe by construction.
    // The ORDER inside redact() is load-bearing three times over:
    //   1. BY VALUE FIRST, on the pristine text. Running the shape pass first
    //      leaked: on an address with an excluded character MID-local-part it
    //      rewrites the suffix to [email-redacted], destroying the exact
    //      literal the by-value pass was holding, and the prefix survives.
    //   2. Shape pass second, for an address we never held.
    //   3. REDACT BEFORE TRUNCATING. The reverse order leaked: an address
    //      straddling offset 500 was cut mid-token, no pattern matched what
    //      was left, and the local part landed verbatim in a structured log.
    // The slice still bounds what we store, it just no longer decides what
    // the redactors can see.
    const raw = await readCappedText(resp, UPSTREAM_BODY_CAP);

    // CONTROL FLOW READS THE PRISTINE BODY, never the redacted copy.
    // Redaction is a lossy transform over visitor-supplied literals, so parsing
    // the redacted text let a submitted name of `code` delete the very key this
    // branch reads. A duplicate then fell through to 502 while a fresh signup
    // returned 303 -- precisely the subscribe-status oracle the duplicate
    // branch below exists to prevent.
    let code = null;
    try {
      code = JSON.parse(raw).code;
    } catch (_) {
      code = null;
    }

    const detail = redact(raw).slice(0, 500);

    // Already on the list: answer exactly as a fresh success does. A distinct
    // status here would let anyone test whether a given address is subscribed.
    // 4xx-and-not-429 only: a 429 or 5xx whose code happens to contain
    // "duplicate" is a RETRYABLE failure, and answering it as a duplicate would
    // tell the visitor to check an inbox no email is coming to.
    const isClientError = resp.status >= 400 && resp.status < 500 && resp.status !== 429;
    if (isClientError && isDuplicateCode(code)) {
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
