// Community "Get featured" submission handler (issue #43 Phase 2).
//
// Cloudflare Pages Function, route: POST /api/contribute
//   1. Reject an oversized body up front (content-length ceiling) before parsing.
//   2. Honeypot drop (silent redirect, no side effects).
//   3. Mandatory Turnstile server-side siteverify (403 on failure).
//   4. Validate + sanitise the text fields (CRLF / header-injection guard).
//   5. Size + magic-byte type gate on the optional photo (<= 10 MB, jpeg/png/webp).
//   6. Email a structured entry to the operator inbox (Cloudflare-native send),
//      photo attached. The email is the operator's primary notification channel,
//      so it is sent FIRST.
//   7. Best-effort archive the photo privately in R2 (the email already carries it,
//      so an R2 failure here neither fails the submission nor orphans a lone photo).
//   8. 303 redirect to the /thanks/ page.
//
// All secrets/bindings come from context.env (dashboard-configured); there are
// NO secret literals in this file. See docs/research/09_DEPLOYMENT.md.
//
// Email uses the Cloudflare Email Service REST API (POST /accounts/{id}/email/
// sending/send). The Pages dashboard has no send-email binding, so the Function
// authenticates with an API token (env.CF_EMAIL_TOKEN) instead. Sends to a
// verified Email Routing destination are free on any plan and allow up to a
// 25 MiB total message, so a 10 MB photo (~13.5 MB base64) fits comfortably.

// --- configuration (non-secret) ---
// The send can only deliver to a VERIFIED Email Routing destination address.
// hello@hoiboy.uk is a routing rule (it forwards here), not a destination address,
// so the send target is the verified destination directly. Same inbox hello@
// forwards to.
const TO_ADDR = "hoiboyuk@gmail.com";
// Sender on the hoiboy.uk routing domain; the local part is synthetic (Cloudflare
// allows sending from any address on a routing domain, so nothing to register).
const FROM_ADDR = "agit-noreply@hoiboy.uk";
const THANKS_PATH = "/community/asians-gingers-in-tech/thanks/";

const MAX_IMAGE_BYTES = 10 * 1024 * 1024; // 10 MB raw (~13.5 MB base64), well under the 25 MiB verified-destination email cap
// Reject the whole request body before parsing if its declared size exceeds the
// photo cap plus a small allowance for the text fields + multipart overhead.
const MAX_BODY_BYTES = MAX_IMAGE_BYTES + 256 * 1024;
const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

// field name -> max length (server-side length caps; a valid-token bot can still POST garbage)
const FIELD_CAPS = { name: 100, email: 254, email_confirm: 254, role: 150, superpowers: 300, feature: 8000 };
// Pragmatic email shape check (not full RFC 5322): non-space local@domain.tld.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function log(event, detail) {
  // Structured observability line (repo AP #12). One per decision branch.
  try {
    console.log(JSON.stringify({ fn: "contribute", event, ...detail }));
  } catch (_) {
    console.log(`contribute ${event}`);
  }
}

// Strip CR/LF/control characters so no field can inject email headers or
// break the MIME body. Trims and enforces a hard length cap.
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

// Drain a Blob's stream into a single Uint8Array. We read the photo once and
// reuse the bytes for the magic-byte sniff, the email attachment, and the R2
// archive. The whole blob is materialised in memory, bounded by the 10 MB size
// gate above (the 128 MB isolate memory is shared across concurrent requests).
// We drain via .stream() rather than a one-shot buffering read.
async function readAllBytes(blob) {
  const reader = blob.stream().getReader();
  const chunks = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    total += value.length;
  }
  const out = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.length;
  }
  return out;
}

// Chunked base64 (String.fromCharCode.apply blows the stack on large inputs).
function bytesToBase64(bytes) {
  let binary = "";
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}

// Magic-byte sniff: return the true image type from the leading bytes, ignoring
// the client-declared Content-Type (which a caller POSTing directly can forge).
// Returns one of ALLOWED_IMAGE_TYPES, or null if the bytes match no allowed
// format. Mirrored by tests/contribute.test.js (keep in lock-step).
function sniffImageType(bytes) {
  if (!bytes || bytes.length < 12) return null;
  // JPEG: FF D8 FF
  if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return "image/jpeg";
  // PNG: 89 50 4E 47 0D 0A 1A 0A
  if (
    bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47 &&
    bytes[4] === 0x0d && bytes[5] === 0x0a && bytes[6] === 0x1a && bytes[7] === 0x0a
  ) return "image/png";
  // WebP: "RIFF" .... "WEBP"
  if (
    bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46 &&
    bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50
  ) return "image/webp";
  return null;
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

export async function onRequestPost(context) {
  const { request, env } = context;

  // 1. Cheap up-front guard: reject an oversized body before buffering/parsing it.
  const declaredLength = Number(request.headers.get("content-length") || 0);
  if (declaredLength > MAX_BODY_BYTES) {
    log("size-type-reject", { reason: "body too large", declaredLength });
    return textResponse(413, "That submission is too large. Please upload a smaller photo.");
  }

  let form;
  try {
    form = await request.formData();
  } catch (_) {
    log("bad-request", { reason: "formData parse failed" });
    return textResponse(400, "Could not read the form.");
  }

  // 2. Honeypot: a real user never fills the hidden "website" field.
  if (form.get("website")) {
    log("honeypot-drop", {});
    // Look successful to the bot; do NOT store or email.
    return Response.redirect(new URL(THANKS_PATH, request.url), 303);
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

  // 4. Text fields: sanitise + length-cap, then presence-check the essentials.
  const name = clean(form.get("name"), FIELD_CAPS.name);
  const email = clean(form.get("email"), FIELD_CAPS.email);
  const emailConfirm = clean(form.get("email_confirm"), FIELD_CAPS.email_confirm);
  const role = clean(form.get("role"), FIELD_CAPS.role);
  const superpowers = clean(form.get("superpowers"), FIELD_CAPS.superpowers);
  const feature = clean(form.get("feature"), FIELD_CAPS.feature);
  if (!name || !email || !feature) {
    log("validation-reject", { name: !!name, email: !!email, feature: !!feature });
    return textResponse(400, "Please fill in your name, email, and your story.");
  }
  if (!EMAIL_RE.test(email)) {
    log("validation-reject", { reason: "bad email format" });
    return textResponse(400, "That email address does not look right. Please check it.");
  }
  if (email.toLowerCase() !== emailConfirm.toLowerCase()) {
    log("validation-reject", { reason: "email mismatch" });
    return textResponse(400, "The two email addresses do not match. Please check them.");
  }

  // Consent must be explicitly ticked (Art 9 special-category: ethnicity + photo).
  if (!form.get("consent")) {
    log("validation-reject", { reason: "consent not given" });
    return textResponse(400, "Please tick the consent box so we can publish your feature.");
  }

  // 5. Optional photo: size gate, then read the bytes once and verify the real
  //    format by magic bytes (never trust the client-declared Content-Type).
  const image = form.get("photo");
  const hasPhoto = image && typeof image === "object" && typeof image.stream === "function" && image.size > 0;
  let photoBytes = null;
  let photoBase64 = null;
  let photoType = null;
  let photoFilename = null;
  if (hasPhoto) {
    if (image.size > MAX_IMAGE_BYTES) {
      log("size-type-reject", { reason: "too large", size: image.size });
      return textResponse(413, "That photo is over the 10 MB limit. Please upload a smaller one.");
    }
    photoBytes = await readAllBytes(image);
    photoType = sniffImageType(photoBytes);
    if (!photoType || !ALLOWED_IMAGE_TYPES.includes(photoType)) {
      log("size-type-reject", { reason: "bad type", declaredType: image.type });
      return textResponse(415, "Please upload a JPEG, PNG, or WebP image.");
    }
    const ext = photoType === "image/png" ? "png" : photoType === "image/webp" ? "webp" : "jpg";
    photoFilename = `photo.${ext}`;
    photoBase64 = bytesToBase64(photoBytes);
  }

  // 6. Email the structured entry to the operator inbox via the Cloudflare Email
  //    Service REST API (base64 attachment). The email is the operator's primary
  //    channel, so it is sent BEFORE the R2 archive: if the email fails there is
  //    nothing stored to orphan.
  if (!env.CF_ACCOUNT_ID || !env.CF_EMAIL_TOKEN) {
    log("email-send", { ok: false, error: "missing CF_ACCOUNT_ID / CF_EMAIL_TOKEN binding" });
    return textResponse(500, "The form is not fully configured yet. Please try again later.");
  }

  const subject = `AGIT story: ${name}`.slice(0, 240);
  const bodyText = [
    `Name: ${name}`,
    `Email: ${email}`,
    `Tech role: ${role || "(not given)"}`,
    `Superpowers: ${superpowers || "(not given)"}`,
    "",
    "Feature / story:",
    feature,
    "",
    hasPhoto ? "(Photo attached.)" : "(No photo submitted.)",
  ].join("\n");

  // reply_to = submitter's email so a Reply in the inbox reaches them (the send
  // itself must stay from the routing domain; the submitter is never a `from`).
  const message = {
    to: TO_ADDR,
    from: FROM_ADDR,
    reply_to: email,
    subject,
    text: bodyText,
  };
  if (photoBase64) {
    message.attachments = [
      {
        content: photoBase64,
        filename: photoFilename,
        type: photoType,
        disposition: "attachment",
      },
    ];
  }

  try {
    const resp = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${env.CF_ACCOUNT_ID}/email/sending/send`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.CF_EMAIL_TOKEN}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(message),
      },
    );
    if (!resp.ok) {
      const detail = (await resp.text()).slice(0, 500);
      log("email-send", { ok: false, status: resp.status, detail });
      return textResponse(502, "Something went wrong sending your story. Please try again.");
    }
    log("email-send", { ok: true, hasPhoto });
  } catch (err) {
    log("email-send", { ok: false, error: String(err) });
    return textResponse(502, "Something went wrong sending your story. Please try again.");
  }

  // 7. Best-effort archive the photo privately in R2. The email already carries
  //    the photo, so a failure here is logged but does NOT fail the submission
  //    (and never leaves a stored photo with no notification reaching us).
  if (hasPhoto) {
    const key = `agit-submissions/${crypto.randomUUID()}-${photoFilename}`;
    try {
      await env.AGIT_UPLOADS.put(key, photoBytes, {
        httpMetadata: { contentType: photoType },
        customMetadata: { name, submittedAt: new Date().toISOString() },
      });
      log("r2-store", { key, size: image.size, ok: true });
    } catch (err) {
      log("r2-store", { ok: false, error: String(err) });
    }
  }

  // 8. Success -> redirect (303 so the browser re-requests with GET).
  return Response.redirect(new URL(THANKS_PATH, request.url), 303);
}
