// Community "Get featured" submission handler (issue #43 Phase 2).
//
// Cloudflare Pages Function, route: POST /api/contribute
//   1. Honeypot drop (silent 200, no side effects).
//   2. Mandatory Turnstile server-side siteverify (403 on failure).
//   3. Validate + sanitise the text fields (CRLF / header-injection guard).
//   4. Size + type gate on the optional photo (<= 3.5 MB, jpeg/png/webp).
//   5. Store the photo privately in R2 (streamed).
//   6. Email a structured entry to hello@hoiboy.uk (Cloudflare-native send),
//      photo attached.
//   7. 303 redirect to the /thanks/ page.
//
// All secrets/bindings come from context.env (dashboard-configured); there are
// NO secret literals in this file. See docs/research/09_DEPLOYMENT.md.
//
// Email uses the Cloudflare Email Service send-email binding object API
// (env.AGIT_MAILER.send({to, from, subject, text, attachments})); the base64
// attachment content keeps the whole message under the 5 MiB cap.

// --- configuration (non-secret; addresses live on the hoiboy.uk domain) ---
const TO_ADDR = "hello@hoiboy.uk";
const FROM_ADDR = "noreply@hoiboy.uk";
const FROM_NAME = "AGIT submissions";
const THANKS_PATH = "/community/asians-gingers-in-tech/thanks/";

const MAX_IMAGE_BYTES = 3.5 * 1024 * 1024; // 3.5 MB — keeps the base64 attachment under the 5 MiB Cloudflare-native email cap
const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

// field name -> max length (server-side length caps; a valid-token bot can still POST garbage)
const FIELD_CAPS = { title: 200, name: 100, role: 150, feature: 8000 };

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

// Read a Blob fully via its stream (never buffer the whole Blob in one shot:
// the 128 MB isolate memory is shared across concurrent requests, and the R2
// put streams the same Blob independently).
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

  let form;
  try {
    form = await request.formData();
  } catch (_) {
    log("bad-request", { reason: "formData parse failed" });
    return textResponse(400, "Could not read the form.");
  }

  // 1. Honeypot: a real user never fills the hidden "website" field.
  if (form.get("website")) {
    log("honeypot-drop", {});
    // Look successful to the bot; do NOT store or email.
    return Response.redirect(new URL(THANKS_PATH, request.url), 303);
  }

  // 2. Turnstile siteverify (mandatory).
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

  // 3. Text fields: sanitise + length-cap, then presence-check the essentials.
  const title = clean(form.get("title"), FIELD_CAPS.title);
  const name = clean(form.get("name"), FIELD_CAPS.name);
  const role = clean(form.get("role"), FIELD_CAPS.role);
  const feature = clean(form.get("feature"), FIELD_CAPS.feature);
  if (!title || !name || !feature) {
    log("validation-reject", { title: !!title, name: !!name, feature: !!feature });
    return textResponse(400, "Please fill in the title, your name, and your story.");
  }

  // Consent must be explicitly ticked (Art 9 special-category: ethnicity + photo).
  if (!form.get("consent")) {
    log("validation-reject", { reason: "consent not given" });
    return textResponse(400, "Please tick the consent box so we can publish your feature.");
  }

  // 4. Optional photo: size + type gate.
  const image = form.get("photo");
  const hasPhoto = image && typeof image === "object" && typeof image.stream === "function" && image.size > 0;
  if (hasPhoto) {
    if (image.size > MAX_IMAGE_BYTES) {
      log("size-type-reject", { reason: "too large", size: image.size });
      return textResponse(413, "That photo is over the 3.5 MB limit. Please upload a smaller one.");
    }
    if (!ALLOWED_IMAGE_TYPES.includes(image.type)) {
      log("size-type-reject", { reason: "bad type", type: image.type });
      return textResponse(415, "Please upload a JPEG, PNG, or WebP image.");
    }
  }

  // 5. Store the photo privately in R2 (streamed), and read it via the stream
  //    for the email attachment (see readAllBytes note above).
  let photoBase64 = null;
  let photoType = null;
  let photoFilename = null;
  if (hasPhoto) {
    photoType = image.type;
    const ext = photoType === "image/png" ? "png" : photoType === "image/webp" ? "webp" : "jpg";
    photoFilename = `photo.${ext}`;
    const key = `agit-submissions/${crypto.randomUUID()}-${photoFilename}`;
    try {
      await env.AGIT_UPLOADS.put(key, image.stream(), {
        httpMetadata: { contentType: photoType },
        customMetadata: { title, name, submittedAt: new Date().toISOString() },
      });
      photoBase64 = bytesToBase64(await readAllBytes(image));
      log("r2-store", { key, size: image.size, ok: true });
    } catch (err) {
      log("r2-store", { ok: false, error: String(err) });
      return textResponse(502, "We could not save your photo. Please try again.");
    }
  }

  // 6. Email the structured entry to hello@hoiboy.uk via the Cloudflare Email
  //    Service send-email binding (object builder API; base64 attachment).
  const subject = `${title} : ${name}`.slice(0, 240);
  const bodyText = [
    `Title: ${title}`,
    `Name: ${name}`,
    `Tech role: ${role || "(not given)"}`,
    "",
    "Feature / story:",
    feature,
    "",
    hasPhoto ? "(Photo attached, and archived privately in R2.)" : "(No photo submitted.)",
  ].join("\n");

  const message = {
    to: TO_ADDR,
    from: { email: FROM_ADDR, name: FROM_NAME },
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
    await env.AGIT_MAILER.send(message);
    log("email-send", { ok: true, hasPhoto });
  } catch (err) {
    log("email-send", { ok: false, error: String(err), code: err && err.code });
    return textResponse(502, "We saved your entry but could not email it. Please try again.");
  }

  // 7. Success -> redirect (303 so the browser re-requests with GET).
  return Response.redirect(new URL(THANKS_PATH, request.url), 303);
}
