// subscribe.test.js -- node --test suite for the /api/subscribe Pages Function (#56).
//
// UNLIKE tests/contribute.test.js, this suite does NOT hand-mirror the helpers.
// contribute.js could not be loaded (ESM `export` inside a CommonJS package), so
// that file copies its pure helpers and relies on review plus a Python gate to keep
// the copies honest. Here the module is loaded for real: the single `export`
// keyword is stripped textually and the remaining source is evaluated in a
// `node:vm` context, which yields the ACTUAL shipped `onRequestPost` plus its
// module-private helpers. Nothing is duplicated, so nothing can drift.
//
// The strip is asserted, not assumed: if the source stops matching the expected
// export shape the loader throws instead of silently evaluating a module with no
// handler in it. A loader that quietly produced an empty module would make every
// assertion below vacuous, which is the failure mode this guard exists to prevent.
//
// One deliberate exception to "nothing is duplicated": KNOWN_CONSENT_VERSIONS is
// ALSO declared here as an explicit mirror, because tests/test_newsletter_consent_version.py
// asserts the three consent surfaces agree (form hidden input / endpoint / this
// mirror) and needs a literal to read. The mirror cannot drift silently: the
// `mirror` test below asserts it equals the value actually loaded from the endpoint.
'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ENDPOINT_PATH = path.join(__dirname, '..', 'functions', 'api', 'subscribe.js');

// The endpoint's consent-version list, mirrored for the Python traceability gate.
// Asserted equal to the loaded value by the `mirror` test below.
const KNOWN_CONSENT_VERSIONS_MIRROR = ['2026-08-03'];

const VALID_EMAIL = 'reader@example.com';
const BREVO_HOST = 'api.brevo.com';
const SITEVERIFY_HOST = 'challenges.cloudflare.com';

// ----------------------------------------------------------------------
// Loader: evaluate the REAL endpoint source in a controlled context.
// ----------------------------------------------------------------------

// Matches the ESM export prefix at the start of a top-level declaration. Anchored
// with /m so an `export` inside a string or comment mid-line cannot match.
const EXPORT_RE = /^export\s+(?=async\s+function\s|function\s|const\s|let\s)/gm;

function loadEndpoint() {
  const raw = fs.readFileSync(ENDPOINT_PATH, 'utf8');
  const stripped = raw.match(EXPORT_RE);
  assert.equal(
    stripped ? stripped.length : 0,
    1,
    'expected exactly one top-level `export` in functions/api/subscribe.js. If the ' +
      'module shape changed, this loader must be updated: evaluating a module whose ' +
      'handler was never exported would make every assertion in this file vacuous.',
  );

  const calls = [];
  const logs = [];

  const context = vm.createContext({
    Response,
    Request,
    FormData,
    Headers,
    URL,
    Buffer,
    // Captured rather than printed: the structured lines are assertable evidence
    // (repo AP #12), and printing them would bury the test runner's own output.
    console: {
      log: (line) => logs.push(line),
      error: (line) => logs.push(line),
    },
    // Default: any un-stubbed network call is a hard failure, so a test that
    // forgets to arrange its upstreams fails loudly instead of hitting the wire.
    fetch: async (url) => {
      throw new Error(`unstubbed fetch to ${String(url)}`);
    },
  });

  const EXPOSE =
    '\n;({ onRequestPost, clean, EMAIL_RE, isDuplicateCode, KNOWN_CONSENT_VERSIONS,' +
    ' FIELD_CAPS, MAX_BODY_BYTES, CHECK_INBOX_PATH, CONFIRMED_PATH, BREVO_DOI_ENDPOINT })';

  const mod = vm.runInContext(raw.replace(EXPORT_RE, '') + EXPOSE, context, {
    filename: ENDPOINT_PATH,
  });
  assert.equal(typeof mod.onRequestPost, 'function', 'onRequestPost did not load');

  return { mod, context, calls, logs };
}

function jsonResponse(status, payload) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

// Arrange both upstreams. `turnstile` is the siteverify outcome; `brevo` is either
// a Response or a function producing one, so a test can model a network throw.
function arrangeFetch({ context, calls }, { turnstile = { success: true }, brevo } = {}) {
  context.fetch = async (url, init) => {
    const target = String(url);
    calls.push({ url: target, init });
    if (target.includes(SITEVERIFY_HOST)) return jsonResponse(200, turnstile);
    if (target.includes(BREVO_HOST)) {
      if (typeof brevo === 'function') return brevo();
      return brevo || jsonResponse(201, { id: 1 });
    }
    throw new Error(`unexpected fetch to ${target}`);
  };
}

const DEFAULT_ENV = {
  // The secret guard flags any api_key assignment. This one is a fixture handed to a
  // stubbed fetch that never leaves the process; the real key is a Pages binding.
  BREVO_API_KEY: 'test-api-key', // secret-allow (test fixture, never a real credential)
  BREVO_LIST_ID: '42',
  BREVO_DOI_TEMPLATE_ID: '7',
  TURNSTILE_SECRET_KEY: 'test-turnstile-secret',
};

// Build a POST Request. `fields` overrides the happy-path form; a null value
// DELETES that field, which is how the absent-field cases are expressed.
function buildRequest(fields = {}) {
  const base = {
    name: 'A Reader',
    email: VALID_EMAIL,
    consent: 'on',
    consent_version: KNOWN_CONSENT_VERSIONS_MIRROR[0],
    'cf-turnstile-response': 'turnstile-token',
  };
  const merged = { ...base, ...fields };
  const body = new FormData();
  for (const [key, value] of Object.entries(merged)) {
    if (value === null || value === undefined) continue;
    body.append(key, value);
  }
  return new Request('https://hoiboy.uk/api/subscribe', { method: 'POST', body });
}

// Run one request end to end. Returns the Response plus the captured side effects.
async function submit({ fields, env, turnstile, brevo } = {}) {
  const harness = loadEndpoint();
  arrangeFetch(harness, { turnstile, brevo });
  const response = await harness.mod.onRequestPost({
    request: buildRequest(fields),
    env: { ...DEFAULT_ENV, ...(env || {}) },
  });
  return { response, calls: harness.calls, logs: harness.logs, mod: harness.mod };
}

const brevoCalls = (calls) => calls.filter((c) => c.url.includes(BREVO_HOST));

// Every rejection path must leave the marketing list untouched. Asserted on its
// own so a failure names the real problem: a write that should not have happened.
function assertNoBrevoWrite(calls) {
  assert.equal(
    brevoCalls(calls).length,
    0,
    'the endpoint contacted Brevo on a path that must not write',
  );
}

// ----------------------------------------------------------------------
// Unit tier: the module-private helpers, loaded rather than copied.
// ----------------------------------------------------------------------

test('unit: clean strips CR/LF so a field cannot inject a header, and caps length', () => {
  const { clean } = loadEndpoint().mod;
  const out = clean('Reader\r\nBcc: attacker@evil.example', 200);
  assert.ok(!out.includes('\r'));
  assert.ok(!out.includes('\n'));
  assert.equal(clean('  padded  ', 200), 'padded');
  assert.equal(clean('abcdef', 3), 'abc');
  assert.equal(clean(null, 10), '');
  assert.equal(clean(undefined, 10), '');
});

test('unit: EMAIL_RE accepts plausible addresses and rejects malformed ones', () => {
  const { EMAIL_RE } = loadEndpoint().mod;
  for (const good of ['a@b.co', 'hoi@hoiboy.uk', 'first.last+tag@sub.example.com']) {
    assert.equal(EMAIL_RE.test(good), true, good);
  }
  for (const bad of ['', 'plainstring', 'no@domain', 'spaces in@x.com', '@nolocal.com']) {
    assert.equal(EMAIL_RE.test(bad), false, bad);
  }
});

test('unit: isDuplicateCode matches only a string code naming a duplicate', () => {
  const { isDuplicateCode } = loadEndpoint().mod;
  assert.equal(isDuplicateCode('duplicate_parameter'), true);
  assert.equal(isDuplicateCode('DUPLICATE_PARAMETER'), true);
  assert.equal(isDuplicateCode('invalid_parameter'), false);
  assert.equal(isDuplicateCode(null), false);
  assert.equal(isDuplicateCode(undefined), false);
  assert.equal(isDuplicateCode(429), false);
});

test('mirror: the consent-version list here equals the endpoint it is mirrored from', () => {
  const { KNOWN_CONSENT_VERSIONS } = loadEndpoint().mod;
  // Spread into a same-realm array first: the vm context has its own Array
  // constructor, so a strict deep-equal on the loaded value fails on prototype
  // identity even when every element matches.
  assert.deepEqual(
    [...KNOWN_CONSENT_VERSIONS],
    KNOWN_CONSENT_VERSIONS_MIRROR,
    'the mirror above has drifted from functions/api/subscribe.js. The Python ' +
      'traceability gate reads this literal, so a drifted mirror makes that gate ' +
      'assert against a list the endpoint does not use.',
  );
});

// ----------------------------------------------------------------------
// Workflow tier: the assembled handler against stubbed upstreams (AC 4.4).
// ----------------------------------------------------------------------

test('workflow: a valid submission sends the exact Brevo double opt-in request', async () => {
  const { response, calls, mod } = await submit();

  assert.equal(response.status, 303);
  assert.equal(response.headers.get('location'), 'https://hoiboy.uk/newsletter/check-inbox/');

  const sent = brevoCalls(calls);
  assert.equal(sent.length, 1, 'expected exactly one Brevo write');
  assert.equal(sent[0].url, mod.BREVO_DOI_ENDPOINT);
  assert.equal(sent[0].init.method, 'POST');
  assert.equal(sent[0].init.headers['api-key'], DEFAULT_ENV.BREVO_API_KEY);
  assert.equal(sent[0].init.headers['content-type'], 'application/json');

  // Field by field, not "a fetch happened": the endpoint reference requires
  // email, includeListIds, templateId and redirectionUrl, and a wrong list id
  // would silently subscribe readers to the wrong audience.
  const payload = JSON.parse(sent[0].init.body);
  assert.equal(payload.email, VALID_EMAIL);
  assert.deepEqual(payload.includeListIds, [42]);
  assert.equal(payload.templateId, 7);
  assert.equal(payload.redirectionUrl, 'https://hoiboy.uk/newsletter/confirmed/');
  assert.equal(payload.attributes.FIRSTNAME, 'A Reader');
  assert.equal(payload.attributes.CONSENT_VERSION, KNOWN_CONSENT_VERSIONS_MIRROR[0]);

  // The ids are NUMBERS. Brevo rejects the string forms, and the env bindings
  // arrive as strings, so the Number() coercion is load-bearing.
  assert.equal(typeof payload.includeListIds[0], 'number');
  assert.equal(typeof payload.templateId, 'number');

  // Submission time, which is the Article 7(1) evidence the Privacy Notice promises.
  assert.match(payload.attributes.CONSENT_TIMESTAMP, /^\d{4}-\d{2}-\d{2}T[\d:.]+Z$/);
});

test('workflow: Turnstile is verified BEFORE Brevo is contacted', async () => {
  const { calls } = await submit();
  assert.equal(calls.length, 2);
  assert.ok(calls[0].url.includes(SITEVERIFY_HOST), 'siteverify must be the first call');
  assert.ok(calls[1].url.includes(BREVO_HOST));
});

test('workflow: a structured log line is emitted for the successful write', async () => {
  const { logs } = await submit();
  const parsed = logs.map((line) => JSON.parse(line));
  const written = parsed.find((entry) => entry.event === 'brevo-doi');
  assert.ok(written, 'no brevo-doi observability line was emitted');
  assert.equal(written.ok, true);
  assert.equal(written.duplicate, false);
});

// ----------------------------------------------------------------------
// Adversarial corpus (AC 4.5). Each asserts the HTTP status AND that no Brevo
// write happened on a path where one must not.
// ----------------------------------------------------------------------

test('missing-consent: an unticked consent box is rejected and writes nothing', async () => {
  const { response, calls } = await submit({ fields: { consent: null } });
  assert.equal(response.status, 400);
  assertNoBrevoWrite(calls);
});

test('absent-version: a submission with no consent_version is rejected', async () => {
  const { response, calls } = await submit({ fields: { consent_version: null } });
  assert.equal(response.status, 400);
  assertNoBrevoWrite(calls);
});

test('unknown-version: an unrecognised consent_version is rejected, never defaulted', async () => {
  for (const version of ['2026-01-01', 'latest', '']) {
    const { response, calls } = await submit({ fields: { consent_version: version } });
    assert.equal(response.status, 400, `version ${JSON.stringify(version)} was accepted`);
    assertNoBrevoWrite(calls);
  }
});

test('honeypot: a filled hidden field looks successful to the bot but writes nothing', async () => {
  const { response, calls } = await submit({ fields: { website: 'http://spam.example' } });
  // Indistinguishable from success, so the bot gets no signal it was caught.
  assert.equal(response.status, 303);
  assert.equal(response.headers.get('location'), 'https://hoiboy.uk/newsletter/check-inbox/');
  assertNoBrevoWrite(calls);
  // And it short-circuits before Turnstile, so a drop costs no siteverify call.
  assert.equal(calls.length, 0);
});

test('turnstile-absent: a submission with no Turnstile token is refused', async () => {
  // No token posted, so siteverify sees an empty response value and fails it.
  const { response, calls } = await submit({
    fields: { 'cf-turnstile-response': null },
    turnstile: { success: false, 'error-codes': ['missing-input-response'] },
  });
  assert.equal(response.status, 403);
  assertNoBrevoWrite(calls);
});

test('turnstile-fail: a siteverify rejection stops the request at 403', async () => {
  const { response, calls, logs } = await submit({
    turnstile: { success: false, 'error-codes': ['invalid-input-response'] },
  });
  assert.equal(response.status, 403);
  assertNoBrevoWrite(calls);
  assert.ok(
    logs.map((l) => JSON.parse(l)).some((e) => e.event === 'turnstile-fail'),
    'a refused challenge must leave an observability trail',
  );
});

test('over-length: an email past the 254 cap is rejected, never truncated', async () => {
  const { mod } = loadEndpoint();
  const tooLong = `${'a'.repeat(mod.FIELD_CAPS.email)}@example.com`;
  const { response, calls } = await submit({ fields: { email: tooLong } });
  assert.equal(response.status, 400);
  assertNoBrevoWrite(calls);
});

test('over-length boundary: a 255-char address whose truncation would still be valid', async () => {
  // This is the dangerous case and the reason the length check runs on the RAW
  // value. Truncating this address to 254 characters yields a DIFFERENT address
  // that still satisfies EMAIL_RE, so a truncating endpoint would silently send
  // the confirmation to whoever that shortened address belongs to.
  const { mod } = loadEndpoint();
  const cap = mod.FIELD_CAPS.email;
  const domain = '@example.com';
  const local = 'b'.repeat(cap + 1 - domain.length);
  const address = local + domain;
  assert.equal(address.length, cap + 1);
  assert.equal(mod.EMAIL_RE.test(address), true, 'the probe address must itself be valid');
  assert.equal(
    mod.EMAIL_RE.test(address.slice(0, cap)),
    true,
    'and its truncation must also be valid, or this case proves nothing',
  );

  const { response, calls } = await submit({ fields: { email: address } });
  assert.equal(response.status, 400);
  assertNoBrevoWrite(calls);
});

test('duplicate: an address already on the list answers exactly as a fresh success', async () => {
  const { response, calls } = await submit({
    brevo: () => jsonResponse(400, { code: 'duplicate_parameter', message: 'already exists' }),
  });
  // A distinct status here would let anyone probe whether an address is subscribed.
  assert.equal(response.status, 303);
  assert.equal(response.headers.get('location'), 'https://hoiboy.uk/newsletter/check-inbox/');
  assert.equal(brevoCalls(calls).length, 1, 'the duplicate is detected from a real attempt');
});

test('rate-limit: a Brevo 429 becomes a 503 rather than a retry storm', async () => {
  const { response, logs } = await submit({
    brevo: () => jsonResponse(429, { code: 'too_many_requests' }),
  });
  assert.equal(response.status, 503);
  const entry = logs.map((l) => JSON.parse(l)).find((e) => e.reason === 'rate-limit');
  assert.ok(entry, 'the rate-limit branch must be observable');
  assert.equal(entry.status, 429);
});

test('brevo-5xx: an upstream server error becomes a 502 and writes nothing further', async () => {
  const { response, logs } = await submit({
    brevo: () => jsonResponse(503, { code: 'internal_error' }),
  });
  assert.equal(response.status, 502);
  assert.ok(logs.map((l) => JSON.parse(l)).some((e) => e.reason === 'upstream'));
});

test('brevo-5xx network throw: an unreachable upstream also becomes a 502', async () => {
  const { response, logs } = await submit({
    brevo: () => {
      throw new Error('connection reset');
    },
  });
  assert.equal(response.status, 502);
  assert.ok(logs.map((l) => JSON.parse(l)).some((e) => e.reason === 'network'));
});

// ----------------------------------------------------------------------
// Configuration and body guards (steps 0 and 1).
// ----------------------------------------------------------------------

test('a missing Brevo binding fails loud on the first request, per binding name', async () => {
  for (const missing of ['BREVO_API_KEY', 'BREVO_LIST_ID', 'BREVO_DOI_TEMPLATE_ID']) {
    const { response, calls, logs } = await submit({ env: { [missing]: '' } });
    assert.equal(response.status, 500, `${missing} absent did not fail loud`);
    assertNoBrevoWrite(calls);
    const entry = logs.map((l) => JSON.parse(l)).find((e) => e.event === 'config-missing');
    assert.ok(entry, 'a misconfigured deploy must be visible in the logs');
    assert.deepEqual(entry.missing, [missing]);
  }
});

test('an oversized declared body is refused before it is parsed', async () => {
  const harness = loadEndpoint();
  arrangeFetch(harness, {});
  const request = new Request('https://hoiboy.uk/api/subscribe', {
    method: 'POST',
    headers: { 'content-length': String(harness.mod.MAX_BODY_BYTES + 1) },
    body: 'x',
  });
  const response = await harness.mod.onRequestPost({ request, env: DEFAULT_ENV });
  assert.equal(response.status, 413);
  assertNoBrevoWrite(harness.calls);
  const entry = harness.logs.map((l) => JSON.parse(l)).find((e) => e.event === 'size-reject');
  assert.equal(entry.source, 'header', 'the header fast-path should be what rejected this');
});

// A body delivered as a stream, which is the shape a chunked sender produces.
//
// Worth being precise about what is and is not special here, because the
// distinction is easy to get backwards: Node does not set content-length on a
// Request at all (fetch computes it at send time), so EVERY request this file
// builds already omits the header, and the test below pins that. What a streamed
// body adds is a body whose length genuinely is not knowable up front, so the
// capped read is doing real work rather than measuring an in-memory buffer.
function streamedRequest(bytes, contentType) {
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(bytes);
      controller.close();
    },
  });
  return new Request('https://hoiboy.uk/api/subscribe', {
    method: 'POST',
    headers: { 'content-type': contentType },
    body: stream,
    duplex: 'half',
  });
}

// Re-emit a normal multipart form as a streamed body, preserving the boundary.
async function streamedFormRequest(fields = {}) {
  const seed = buildRequest(fields);
  const contentType = seed.headers.get('content-type');
  const bytes = new Uint8Array(await seed.arrayBuffer());
  return streamedRequest(bytes, contentType);
}

test('every request this harness builds omits content-length', () => {
  // Pinned because it is the reason the size ceiling went unexercised for so
  // long. If a future Node starts populating the header here, the two
  // header-absent tests below would quietly start taking the fast path and stop
  // testing the capped read, while still passing. This fails first instead.
  assert.equal(buildRequest().headers.get('content-length'), null);
});

test('a real browser POST, which does declare its length, is not made worse', async () => {
  // The counterpart to the streamed cases: an accurate content-length under the
  // ceiling must take the fast path and skip the capped read entirely. Without
  // this, the whole suite would only ever prove the header-absent branch.
  const harness = loadEndpoint();
  arrangeFetch(harness, {});
  const seed = buildRequest();
  const bytes = new Uint8Array(await seed.arrayBuffer());
  const request = new Request('https://hoiboy.uk/api/subscribe', {
    method: 'POST',
    headers: {
      'content-type': seed.headers.get('content-type'),
      'content-length': String(bytes.byteLength),
    },
    body: bytes,
  });

  const response = await harness.mod.onRequestPost({ request, env: DEFAULT_ENV });
  assert.equal(response.status, 303);
  assert.ok(
    harness.calls.find((c) => String(c.url).includes('brevo.com')),
    'a normally-declared submission must still reach Brevo'
  );
  assert.ok(
    !harness.logs.map((l) => JSON.parse(l)).some((e) => e.event === 'size-reject'),
    'a correctly-sized declared body must not trip the ceiling'
  );
});

test('a streamed body with no content-length still reaches the handler intact', async () => {
  const harness = loadEndpoint();
  arrangeFetch(harness, {});
  const request = await streamedFormRequest();
  const response = await harness.mod.onRequestPost({ request, env: DEFAULT_ENV });

  // The point is not merely that it was allowed through: the capped read has to
  // hand formData() a body it can still parse, boundary and all. A 303 plus a
  // real Brevo write is the only outcome that proves the re-wrap is lossless.
  assert.equal(response.status, 303);
  const write = harness.calls.find((c) => String(c.url).includes('brevo.com'));
  assert.ok(write, 'the streamed submission never reached Brevo, so the body was mangled');
});

test('an oversized streamed body is refused even though it declares no length', async () => {
  const harness = loadEndpoint();
  arrangeFetch(harness, {});
  const oversized = new Uint8Array(harness.mod.MAX_BODY_BYTES + 1);
  const request = streamedRequest(oversized, 'multipart/form-data; boundary=x');
  const response = await harness.mod.onRequestPost({ request, env: DEFAULT_ENV });

  assert.equal(response.status, 413);
  assertNoBrevoWrite(harness.calls);
  const entry = harness.logs.map((l) => JSON.parse(l)).find((e) => e.event === 'size-reject');
  assert.ok(entry, 'an oversized streamed body must be visible in the logs, not silently dropped');
  assert.equal(entry.source, 'stream', 'the header path cannot have caught this one');
});

test('a missing name is rejected even when every other field is valid', async () => {
  const { response, calls } = await submit({ fields: { name: null } });
  assert.equal(response.status, 400);
  assertNoBrevoWrite(calls);
});

test('a malformed email is rejected before any upstream write', async () => {
  const { response, calls } = await submit({ fields: { email: 'not-an-address' } });
  assert.equal(response.status, 400);
  assertNoBrevoWrite(calls);
});
