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
// asserts the consent surfaces agree (form hidden input / endpoint / this
// mirror, plus the version quoted in prose in content/legal/privacy/index.md --
// four in total) and needs a literal to read. The mirror cannot drift silently: the
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
    ' FIELD_CAPS, MAX_BODY_BYTES, CHECK_INBOX_PATH, CONFIRMED_PATH, BREVO_DOI_ENDPOINT,' +
    ' redactPii, literalForms, MAX_ESCAPE_LEVELS })';

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

test('honeypot: an EMPTY hidden field is what every real browser posts, and must not drop', async () => {
  // The shipped input (layouts/_partials/subscribe-form.html) carries no
  // `disabled`, so a browser submits `website=` on EVERY legitimate signup.
  // The predicate is `if (form.get("website"))`, correct only because "" is
  // falsy -- and the filled-field test above cannot see that. Ralph round 22
  // Tier 3 proved the gap: changing the predicate to `!== null` dropped 100%
  // of real subscriptions, returned a success-looking 303, and left all 114
  // JS tests and all 693 Python tests green. This asserts the empty case
  // explicitly, so the truthiness semantics are pinned rather than assumed.
  // Premise guard FIRST: the fixture must actually post the field, or this
  // test passes for the wrong reason -- an ABSENT field is also falsy, so an
  // omitted `website` would satisfy the assertions below while proving
  // nothing about the empty-string case that real traffic sends.
  const posted = await buildRequest({ website: '' }).formData();
  assert.ok(posted.has('website'), 'fixture must POST website, not omit it');
  assert.equal(posted.get('website'), '', 'fixture must post website EMPTY');

  const { response, calls } = await submit({ fields: { website: '' } });
  assert.equal(response.status, 303);
  // A real Brevo double opt-in write happened: the honeypot did NOT fire.
  const brevo = calls.find((c) => String(c.url).includes('/v3/contacts/doubleOptinConfirmation'));
  assert.ok(brevo, 'an empty honeypot must reach Brevo, not be silently dropped');
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

test('duplicate: a RETRYABLE failure whose code contains "duplicate" is not answered as one', async () => {
  // Ralph round 22 Tier 3. isDuplicateCode is a loose substring match, so a 429
  // or 5xx merely CONTAINING "duplicate" used to short-circuit to 303 "check
  // your inbox" -- to someone who will never receive an email, and who cannot
  // retry because we told them it worked. The status class is what rules this
  // out, so both retryable classes are asserted here.
  const rateLimited = await submit({
    brevo: () => jsonResponse(429, { code: 'duplicate_request_throttled' }),
  });
  assert.equal(rateLimited.response.status, 503, 'a 429 stays retryable, never a 303');

  const serverError = await submit({
    brevo: () => jsonResponse(500, { code: 'a duplicate was detected downstream' }),
  });
  assert.equal(serverError.response.status, 502, 'a 5xx stays an error, never a 303');
});

test('config: a whitespace-only id binding is refused as loudly as an absent one', async () => {
  // Ralph round 22 Tier 3. The guard was truthiness-only, so "   " passed it and
  // Number("   ") is 0 -- the request went out as includeListIds: [0]. Fail-closed
  // at Brevo, but not the loud-on-the-first-request behaviour the header promises.
  for (const bad of ['   ', 'not-a-number', '0', '-1']) {
    const { response, calls } = await submit({ env: { BREVO_LIST_ID: bad } });
    assert.equal(response.status, 500, `BREVO_LIST_ID=${JSON.stringify(bad)} must be refused`);
    assertNoBrevoWrite(calls);
  }
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

// The header-value space, not just the two values a previous fix happened to
// handle. Round 1 of review found an ABSENT header bypassed the ceiling; the fix
// for it branched on `=== null`, and round 2 found that a header which is present
// but does not parse to a number bypasses it just as completely: `NaN > cap` is
// false so the fast-reject misses, and `!== null` is true so the bounded read was
// skipped. Both bugs lived in the same place, a branch that asked the header
// whether to bound the read. The cap no longer consults the header at all, and
// these cases pin that: every one of them sends a body OVER the cap.
for (const [label, header] of [
  ['not a number', 'notanumber'],
  ['empty string', ''],
  ['negative', '-1'],
  ['a lie, far under the true size', '10'],
  ['whitespace', '   '],
  ['hex-looking', '0x1'],
]) {
  test(`an oversized body is refused when content-length is ${label}`, async () => {
    const harness = loadEndpoint();
    arrangeFetch(harness, {});
    const oversized = new Uint8Array(harness.mod.MAX_BODY_BYTES + 1);
    const request = new Request('https://hoiboy.uk/api/subscribe', {
      method: 'POST',
      headers: { 'content-type': 'multipart/form-data; boundary=x', 'content-length': header },
      body: oversized,
    });

    const response = await harness.mod.onRequestPost({ request, env: DEFAULT_ENV });
    assert.equal(
      response.status,
      413,
      `an over-cap body was accepted with content-length ${JSON.stringify(header)}`
    );
    assertNoBrevoWrite(harness.calls);
    assert.ok(
      harness.logs.map((l) => JSON.parse(l)).some((e) => e.event === 'size-reject'),
      'an over-cap body must always be visible in the logs, whatever the header claimed'
    );
  });
}

// Brevo is free to quote the value it rejected. content/legal/sub-processors
// publishes that this Function handles the submitted fields in transit only and
// does not persist the request, so an upstream error body that echoes the
// address must not carry it into a structured log line.
for (const [label, brevoBody] of [
  ['a validation error quoting the address', { code: 'invalid_parameter', message: `Attribute is invalid for contact ${VALID_EMAIL}` }],
  ['a duplicate error quoting the address', { code: 'unknown_thing', message: `Contact ${VALID_EMAIL} already exists` }],
]) {
  test(`the subscriber address never reaches a log line via ${label}`, async () => {
    const { logs } = await submit({ brevo: () => jsonResponse(400, brevoBody) });
    const joined = logs.join('\n');

    assert.ok(
      !joined.includes(VALID_EMAIL),
      `the submitted address appeared verbatim in a log line:\n${joined}`
    );
    // The error must still be diagnosable: redaction is not deletion. The
    // marker pinned here is [redacted], the BY-VALUE one: the submitted
    // address is held via protect(), and the value pass runs FIRST at capture
    // (running the shape pass first destroyed the held literal and leaked the
    // local-part prefix -- Ralph round 14 Tier 3). [email-redacted] would mean
    // the weaker shape pass got there first, which is the defective order.
    assert.ok(
      joined.includes('[redacted]'),
      'the upstream detail was dropped entirely rather than redacted; an ' +
        'operator needs the error text to diagnose a non-JSON upstream failure'
    );
    assert.ok(
      joined.includes(brevoBody.code),
      'the upstream code must survive redaction, it is the diagnostic'
    );
  });
}

// Both fixtures above are one-line objects well under 500 characters, so the
// `.slice(0, 500)` on the log path is a no-op for them and they held while the
// shipped code still truncated BEFORE redacting. That order leaked: an address
// cut mid-token stopped matching the redactor and its local part went into the
// log verbatim (Ralph Tier 3).
//
// This is a SEPARATE test rather than another row in the loop above, because the
// loop's "redaction is not deletion" assertion cannot hold here and pretending
// otherwise would be the fixture lying. The offsets that leak under the old
// order are exactly those where the address STARTS before 500 and ENDS after it,
// and at every one of them the 17-character `[email-redacted]` marker also
// crosses the cut and is itself truncated. Demanding the whole marker would make
// the straddle case unconstructible.
//
// Padding 442 is computed, not guessed: it puts the address at offset 489, so it
// starts inside the window and ends outside it.
// An address the redactor's own character class cannot match leaks with no
// truncation involved at all -- the same surviving-local-part outcome as the
// straddle case, reached by a different route. The local class excluded the
// apostrophe, which RFC 5322 permits unquoted and which EMAIL_RE above accepts,
// so `o'brien@example.com` logged as `o'[email-redacted]` (Ralph Tier 2). Real
// subscribers have these names; this is not a theoretical address.
const APOSTROPHE_EMAIL = `o${String.fromCharCode(39)}brien@example.com`;

test('an address whose local part contains an apostrophe is fully redacted', async () => {
  // A NON-duplicate code on purpose: isDuplicateCode() routes a duplicate to a
  // branch that logs no `detail` at all, so the address would be absent rather
  // than redacted and the last assertion below would be testing nothing.
  const body = {
    code: 'invalid_parameter',
    message: `Attribute is invalid for contact ${APOSTROPHE_EMAIL}`,
  };
  const { logs } = await submit({ brevo: () => jsonResponse(400, body) });
  const joined = logs.join('\n');

  assert.ok(
    !joined.includes(APOSTROPHE_EMAIL),
    `the address appeared verbatim in a log line:\n${joined}`
  );
  assert.ok(
    !joined.includes(`o${String.fromCharCode(39)}`),
    `the local-part fragment before the apostrophe survived redaction, which is ` +
      `the defect the character class caused:\n${joined}`
  );
  assert.ok(
    joined.includes('[email-redacted]'),
    'the address must be redacted, not merely absent'
  );
});

// The apostrophe fix above widened redactPii's local character class by one
// character. The straddle fix before it reordered redact-and-truncate. Both
// treated a SYMPTOM, and a third symptom was waiting: the class is still
// strictly narrower than the class EMAIL_RE admits.
//
// EMAIL_RE is `/^[^\s@]+@[^\s@]+\.[^\s@]+$/` -- anything without a space or an
// `@`. redactPii's local class is `[^\s"<>@,;:()]+`, which additionally excludes
// `"` `<` `>` `,` `;` `:` `(` `)`. Every one of those is therefore ACCEPTED by
// the endpoint and INVISIBLE to the redactor. When one sits immediately before
// the `@`, the pattern cannot reach the `@` at all, so nothing matches and the
// whole address is logged verbatim -- no truncation and no partial redaction
// involved, which is why neither earlier fix caught it.
//
// A quoted local part is the shape a real user can actually produce, and it is
// valid per RFC 5321 section 4.1.2. The address below is synthetic and uses an
// RFC 2606 reserved domain.
//
// The fix is NOT a fourth widening. `protect(email)` registers the literal that
// was accepted, and redactLine strips that literal from the serialised line, so
// redaction no longer depends on the address matching any pattern at all.
const QUOTED_EMAIL = `${String.fromCharCode(34)}patriley${String.fromCharCode(34)}@example.net`;

test('an address the shape redactor cannot match is redacted by value', async () => {
  // Guard the fixture: if EMAIL_RE ever stops accepting this, the endpoint would
  // reject it at validation and the log assertions below would pass vacuously.
  const harnessProbe = loadEndpoint();
  assert.equal(
    harnessProbe.mod.EMAIL_RE.test(QUOTED_EMAIL),
    true,
    'the probe address must be ACCEPTED by the endpoint, or this test proves nothing'
  );

  // ...and prove the shape redactor genuinely cannot handle it, which is the
  // whole premise. If a future change makes redactPii match this, that is fine,
  // but this test would no longer be covering the value-redaction path and must
  // be re-pointed rather than left as a passing no-op.
  assert.ok(
    harnessProbe.mod.redactPii(QUOTED_EMAIL).includes('patriley'),
    'redactPii now matches this address, so this test no longer exercises the ' +
      'by-value path it exists to cover. Re-point it at a shape it still misses.'
  );

  const body = {
    code: 'invalid_parameter',
    message: `Attribute is invalid for contact ${QUOTED_EMAIL}`,
  };
  const { logs } = await submit({
    fields: { email: QUOTED_EMAIL },
    brevo: () => jsonResponse(400, body),
  });
  const joined = logs.join('\n');

  assert.ok(
    !joined.includes(QUOTED_EMAIL),
    `the address appeared verbatim in a log line:\n${joined}`
  );
  assert.ok(
    !joined.includes('patriley'),
    `the local part survived into a log line. This is the leak: EMAIL_RE ` +
      `accepted a character redactPii's class excludes, so the shape pattern ` +
      `never matched and nothing was replaced:\n${joined}`
  );
  assert.ok(
    joined.includes('[redacted]'),
    'the address must be redacted by value, not merely absent'
  );
  assert.ok(
    joined.includes(body.code),
    'the upstream code must still survive; it is the diagnostic that remains'
  );
});

test('the submitted address is stripped from EVERY log line, not just the captured body', async () => {
  // redactPii was wired at exactly one capture point (the upstream error body),
  // so any OTHER log line carrying a request-derived value bypassed it entirely.
  // Redaction now happens where the line is written, so a log call that never
  // touches an upstream response is covered too.
  //
  // `consent_version` is the vehicle: it is request-derived, it is logged by
  // value on the unknown-version branch, and it never passes through redactPii.
  const { logs } = await submit({
    fields: { email: QUOTED_EMAIL, consent_version: QUOTED_EMAIL },
  });
  const joined = logs.join('\n');

  assert.ok(
    joined.includes('unknown consent version'),
    `the unknown-consent-version branch must be the one that fired, or this ` +
      `test is not exercising the bypass path:\n${joined}`
  );
  assert.ok(
    !joined.includes('patriley'),
    `a request-derived field carried the address into a log line that never ` +
      `passes through the capture-point redactor:\n${joined}`
  );
});

// The position of the excluded character decides which failure mode fires.
// At the local-part BOUNDARY (QUOTED_EMAIL above) the shape pattern cannot
// reach the `@` at all, so it is INERT and the held literal survives intact
// for the by-value pass. MID-local-part, the pattern matches the SUFFIX
// (`x@example.net`), rewrites it to `[email-redacted]`, and in doing so
// DESTROYS the exact literal the by-value pass was holding -- the two
// defences cannibalise instead of stacking, and the prefix leaks. Found by
// Ralph round 14 Tier 3 with the shipped capture order
// `redactPii(text).slice(...)`; the fix runs the by-value pass FIRST, on the
// pristine text, via the logger's redact() (value, then shape, then slice).
const MID_LOCAL_EMAIL = 'patriley,x@example.net';

test('an excluded character MID-local-part cannot cannibalise the held literal', async () => {
  const harnessProbe = loadEndpoint();
  assert.equal(
    harnessProbe.mod.EMAIL_RE.test(MID_LOCAL_EMAIL),
    true,
    'the probe address must be ACCEPTED by the endpoint, or this test proves nothing'
  );

  // Prove the premise: on this address the shape redactor is DESTRUCTIVE, not
  // inert. It must rewrite part of the address (so a shape-first capture no
  // longer contains the held literal) while leaving the local-part prefix
  // behind. If either half stops holding, the fixture no longer exercises the
  // cannibalisation order and must be re-pointed, not left as a passing no-op.
  const shapeApplied = harnessProbe.mod.redactPii(MID_LOCAL_EMAIL);
  assert.notEqual(
    shapeApplied,
    MID_LOCAL_EMAIL,
    'redactPii is now inert on this address; that is the QUOTED_EMAIL case, ' +
      'already covered above. Re-point this fixture at a shape it rewrites.'
  );
  assert.ok(
    shapeApplied.includes('patriley'),
    'redactPii now fully matches this address, so this test no longer ' +
      'exercises the partial-rewrite path it exists to cover. Re-point it.'
  );

  const body = {
    code: 'invalid_parameter',
    message: `Attribute is invalid for contact ${MID_LOCAL_EMAIL}`,
  };
  const { logs } = await submit({
    fields: { email: MID_LOCAL_EMAIL },
    brevo: () => jsonResponse(400, body),
  });
  const joined = logs.join('\n');

  assert.ok(
    !joined.includes('patriley'),
    `the local part survived into a log line. The shape pass ran BEFORE the ` +
      `by-value pass, rewrote the address's suffix, and destroyed the held ` +
      `literal the by-value pass would have matched:\n${joined}`
  );
  assert.ok(
    joined.includes(body.code),
    'the upstream code must still survive; it is the diagnostic that remains'
  );
});

// A held value is arbitrary visitor text and the literal replace is blind, so
// the level it runs at decides whether it can collide with STRUCTURE. Two
// levels were wrong and are pinned here (Ralph round 15 Tier 3):
//
//   1. It ran over the raw upstream body BEFORE JSON.parse read `code` for
//      control flow. A name of `code` deleted that key, so a duplicate fell
//      through to the 502 branch while a fresh signup still got 303 -- a
//      subscribe-status oracle, the exact thing the duplicate branch exists to
//      prevent. Control flow now parses the pristine body.
//   2. It ran over the finished JSON line, where a name of `name`/`reason`
//      rewrote a structural key and a name containing a quote emitted invalid
//      JSON. redactDeep already redacts values one level down, where they
//      cannot collide with structure, so the line pass is shape-only now.
//
// These names are ordinary strings a real visitor can type; the form sets no
// pattern and its maxlength is client-side only.
const STRUCTURAL_NAMES = ['code', 'duplicate', 'name', 'reason', 'message'];

test('a crafted name cannot turn a duplicate into a distinguishable response', async () => {
  // The duplicate and success paths must stay indistinguishable to the caller
  // whatever the name is, or the form answers "is this address subscribed?".
  const duplicateBody = { code: 'duplicate_parameter', message: 'Contact already exist' };
  const seen = new Map();

  for (const name of ['A Reader', ...STRUCTURAL_NAMES]) {
    const { response } = await submit({
      fields: { name, email: VALID_EMAIL },
      brevo: () => jsonResponse(400, duplicateBody),
    });
    seen.set(name, `${response.status} ${response.headers.get('location') || ''}`.trim());
  }

  const baseline = seen.get('A Reader');
  for (const name of STRUCTURAL_NAMES) {
    assert.equal(
      seen.get(name),
      baseline,
      `submitting name=${JSON.stringify(name)} changed the duplicate response to ` +
        `"${seen.get(name)}" while a plain name gives "${baseline}". That difference ` +
        `is a subscribe-status oracle: anyone could test whether an address is ` +
        `already on the list.`
    );
  }
});

// The success line carries only {fn,event,ok,duplicate,status,consentVersion},
// so driving ONLY that branch leaves four of the five crafted names touching no
// key at all and asserting nothing. Each branch is therefore exercised
// separately: the upstream-error line is the one carrying `code`, `reason` and
// `detail`, and `message` only ever appears inside an echoed body.
const LOG_BRANCHES = [
  ['success', undefined],
  ['upstream-error', () => jsonResponse(400, { code: 'invalid_parameter', message: 'Attribute is invalid' })],
  ['rate-limit', () => jsonResponse(429, { code: 'too_many_requests', message: 'Slow down' })],
];

test('a crafted name cannot corrupt the structure of a log line', async () => {
  // Differential, not a fixed expectation: the log line's KEY SET must be the
  // same whatever the visitor typed. Asserting only that a couple of named
  // keys survive is too weak -- `duplicate` is itself a key on the success
  // line, so a blind replace renames it while `fn` and `event` sit untouched
  // and a narrower check passes with the corruption live.
  const keysFor = (logs) =>
    logs.map((line) => Object.keys(JSON.parse(line)).sort().join(','));

  for (const [label, brevo] of LOG_BRANCHES) {
    const baseline = await submit({
      fields: { name: 'A Reader', email: VALID_EMAIL },
      brevo,
    });
    const expected = keysFor(baseline.logs);
    assert.ok(expected.length > 0, `the ${label} branch emitted no baseline log line`);

    for (const name of STRUCTURAL_NAMES) {
      const { logs } = await submit({ fields: { name, email: VALID_EMAIL }, brevo });
      assert.ok(
        logs.length > 0,
        `no log line was emitted on the ${label} branch for name=${JSON.stringify(name)}`
      );

      for (const line of logs) {
        assert.doesNotThrow(
          () => JSON.parse(line),
          `name=${JSON.stringify(name)} produced a log line that is not valid JSON ` +
            `on the ${label} branch. A blind literal replace over the serialised ` +
            `line rewrote its own structure:\n${line}`
        );
      }

      assert.deepEqual(
        keysFor(logs),
        expected,
        `name=${JSON.stringify(name)} changed the KEY SET of a ${label} log line. A ` +
          `held value was replaced inside the finished JSON, so a visitor renamed ` +
          `or deleted a structural field:\n${logs.join('\n')}`
      );
    }
  }
});

// An upstream is free to normalise the case of an address before quoting it
// back. The literal we hold is what the visitor typed, so a case-sensitive
// compare misses the echo -- and for an address the SHAPE pass also cannot
// match, nothing redacts it at all. Both halves are needed for this to bite,
// which is why the fixture carries a quote (shape pass blind) AND differs in
// case (literal pass blind unless it folds case).
const MIXED_CASE_EMAIL = `${String.fromCharCode(34)}PatRiley${String.fromCharCode(34)}@Example.net`;
const LOWERCASED_ECHO = MIXED_CASE_EMAIL.toLowerCase();

test('an address echoed back in a different case is still redacted', async () => {
  const harnessProbe = loadEndpoint();
  assert.equal(
    harnessProbe.mod.EMAIL_RE.test(MIXED_CASE_EMAIL),
    true,
    'the probe address must be ACCEPTED by the endpoint, or this test proves nothing'
  );
  // Premise: the shape pass must be unable to rescue this, or the test would
  // pass through redactPii and never exercise the literal compare at all.
  assert.ok(
    harnessProbe.mod.redactPii(LOWERCASED_ECHO).includes('patriley'),
    'redactPii now matches the echoed form, so this test no longer covers the ' +
      'case-folding literal compare it exists for. Re-point it at a shape it misses.'
  );
  assert.notEqual(
    LOWERCASED_ECHO,
    MIXED_CASE_EMAIL,
    'the echo must differ in case from what was submitted, or nothing is proven'
  );

  const body = {
    code: 'invalid_parameter',
    message: `Attribute is invalid for contact ${LOWERCASED_ECHO}`,
  };
  const { logs } = await submit({
    fields: { email: MIXED_CASE_EMAIL },
    brevo: () => jsonResponse(400, body),
  });
  const joined = logs.join('\n');

  assert.ok(
    !joined.toLowerCase().includes('patriley'),
    `the address survived because the upstream echoed it in a different case ` +
      `than the visitor typed, and the literal compare is case-sensitive:\n${joined}`
  );
  assert.ok(
    joined.includes(body.code),
    'the upstream code must still survive; it is the diagnostic that remains'
  );
});

// The behavioural fixture below reaches ONE escaping level beyond what the old
// generator produced, which pins the historical regression but not the property.
// It cannot: a body nested deeply enough to need level 3 is not something a
// realistic upstream sends, so driving the endpoint can never distinguish "walks
// to a fixpoint" from "hard-coded one level deeper". The generator is therefore
// asserted DIRECTLY here, which is the only place the property is observable.
//
// Correcting this file's own earlier wording: the shipped generator returned
// `[escaped, value]` -- two FORMS at ONE escaping level, not two levels. A
// regression to a hard-coded depth of 2 would satisfy the behavioural fixture
// while still being the same guess-the-symptom mistake, and is what this test
// exists to catch.
test('unit: literalForms keeps escaping to a fixpoint, not to a fixed depth', () => {
  const { literalForms, MAX_ESCAPE_LEVELS } = loadEndpoint().mod;
  const escapeOnce = (s) => JSON.stringify(s).slice(1, -1);

  const value = QUOTED_EMAIL;
  const level1 = escapeOnce(value);
  const level2 = escapeOnce(level1);
  const level3 = escapeOnce(level2);

  assert.notEqual(level1, value, 'the probe value must actually require escaping');
  assert.notEqual(level3, level2, 'the probe value must keep growing under escaping');

  const forms = literalForms(value);
  assert.ok(forms.includes(value), 'the raw spelling must be matched');
  assert.ok(forms.includes(level1), 'one escaping level must be matched');
  assert.ok(
    forms.includes(level2),
    'two escaping levels must be matched: an upstream that quotes a rejected ' +
      'payload nests JSON inside a JSON string'
  );
  assert.ok(
    forms.includes(level3),
    'THREE escaping levels are not matched, so the generator is capped at a ' +
      'fixed depth rather than walking to a fixpoint. Whatever depth is ' +
      'hard-coded, one more level reopens the gap -- the same guess-the-symptom ' +
      'mistake as widening a character class.'
  );

  // Termination, so "walks to a fixpoint" cannot mean "walks forever": a value
  // that never stops growing under escaping is bounded, and one that DOES reach
  // a fixpoint stops early rather than padding out to the bound.
  assert.ok(
    forms.length <= MAX_ESCAPE_LEVELS,
    `the walk produced ${forms.length} forms, above the ${MAX_ESCAPE_LEVELS} bound`
  );
  // Spread into a host array first: the value comes from the vm context, so its
  // Array prototype is a different realm's and deepEqual compares prototypes.
  const settled = [...literalForms('plain-reader')];
  assert.deepEqual(
    settled,
    ['plain-reader'],
    'a value that needs no escaping must yield exactly one form; anything more ' +
      'means the walk is padding rather than stopping at its fixpoint'
  );
});

test('an address nested two JSON levels deep in an echo is still redacted', async () => {
  // Escaping COMPOUNDS. An upstream that quotes a rejected payload embeds JSON
  // inside a JSON string, so by the time we read the wire text the address is
  // escaped twice, and the generator that shipped reached only one level. This
  // is the historical regression; the fixpoint PROPERTY is pinned by the unit
  // test above, which is the only place a depth-2 hard-code is distinguishable.
  const nested = JSON.stringify({ email: QUOTED_EMAIL });
  const body = {
    code: 'invalid_parameter',
    message: `rejected payload: ${nested}`,
  };

  // Premise: the address must really be doubly escaped on the wire, or this is
  // just the single-level case wearing a different fixture.
  const wire = JSON.stringify(body);
  assert.ok(
    !wire.includes(QUOTED_EMAIL),
    'the fixture is not escaped at all on the wire; it cannot prove a deep walk'
  );
  assert.ok(
    !wire.includes(JSON.stringify(QUOTED_EMAIL).slice(1, -1)),
    'the fixture is only SINGLY escaped on the wire, which the old fixed-depth ' +
      'matcher already handled. Nest it deeper or this test proves nothing.'
  );

  const { logs } = await submit({
    fields: { email: QUOTED_EMAIL },
    brevo: () => jsonResponse(400, body),
  });
  const joined = logs.join('\n');

  assert.ok(
    !joined.includes('patriley'),
    `the address survived at a nesting depth the escaped-form generator does ` +
      `not reach. Escaping compounds; the walk must go to a fixpoint:\n${joined}`
  );
  assert.ok(
    joined.includes(body.code),
    'the upstream code must still survive; it is the diagnostic that remains'
  );
});

// A quote in the name is the sharpest form of the structural case: it does not
// merely rename a key, it terminates a JSON string early.
test('a name containing a quote cannot emit an unparseable log line', async () => {
  const { logs } = await submit({
    fields: { name: `${String.fromCharCode(34)},${String.fromCharCode(34)}ok${String.fromCharCode(34)}:`, email: VALID_EMAIL },
  });
  assert.ok(logs.length > 0, 'no log line was emitted');
  for (const line of logs) {
    assert.doesNotThrow(
      () => JSON.parse(line),
      `a name carrying a quote broke the log line's own JSON:\n${line}`
    );
  }
});

test('an address straddling the 500-char log cut is still not leaked', async () => {
  const body = {
    code: 'invalid_parameter',
    message: `${'x'.repeat(442)} contact ${VALID_EMAIL} rejected`,
  };
  const { logs } = await submit({ brevo: () => jsonResponse(400, body) });
  const joined = logs.join('\n');

  const localPart = VALID_EMAIL.split('@')[0];
  assert.ok(
    !joined.includes(VALID_EMAIL),
    `the address appeared verbatim in a log line:\n${joined}`
  );
  assert.ok(
    !joined.includes(localPart),
    `the address was cut mid-token and its local part "${localPart}" survived ` +
      `into a log line, which is the exact defect redact-before-truncate fixes:\n${joined}`
  );
  assert.ok(
    joined.includes(body.code),
    'the upstream code must still survive; it is the diagnostic that remains'
  );
});

test('the encoding a real browser actually sends is handled', async () => {
  // subscribe-form.html declares no enctype, so a browser posts
  // application/x-www-form-urlencoded. Every other test in this file builds a
  // FormData body, which is multipart. So the whole suite was exercising an
  // encoding the shipped form never sends: the same shape as the round-1
  // content-length lesson, where the tests all took a path real traffic does not.
  const harness = loadEndpoint();
  arrangeFetch(harness, {});
  const body = new URLSearchParams({
    name: 'A Reader',
    email: VALID_EMAIL,
    consent: 'on',
    consent_version: KNOWN_CONSENT_VERSIONS_MIRROR[0],
    'cf-turnstile-response': 'turnstile-token',
  });
  const request = new Request('https://hoiboy.uk/api/subscribe', {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });

  const response = await harness.mod.onRequestPost({ request, env: DEFAULT_ENV });

  assert.equal(response.status, 303);
  const write = harness.calls.find((c) => String(c.url).includes('brevo.com'));
  assert.ok(write, 'a urlencoded submission never reached Brevo');
  // And the payload has to be right, not merely present: the capped read plus
  // re-wrap must preserve urlencoded bodies as faithfully as multipart ones.
  const sent = JSON.parse(write.init.body);
  assert.equal(sent.email, VALID_EMAIL);
  assert.equal(sent.attributes.FIRSTNAME, 'A Reader');
  assert.equal(sent.attributes.CONSENT_VERSION, KNOWN_CONSENT_VERSIONS_MIRROR[0]);
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

// Every other ceiling test submits `MAX_BODY_BYTES + 1`, which proves only that
// something ABOVE the cap is refused -- an off-by-one that refuses the cap
// itself satisfies all of them. The boundary is documented as inclusive
// (`total > cap` rejects), so a body of exactly MAX_BODY_BYTES is a legitimate
// submission and must not be size-rejected. Asserted on BOTH the streamed and
// the declared-length path, because they reject at different points.
//
// The assertion is "not a size rejection", not "accepted": a raw padded buffer
// is not parseable multipart, so the request rightly fails LATER at the form
// parse. Demanding 200 here would pin the wrong thing.
for (const [label, makeRequest] of [
  ['streamed', (bytes) => streamedRequest(bytes, 'multipart/form-data; boundary=x')],
  [
    'declared-length',
    (bytes) =>
      new Request('https://hoiboy.uk/api/subscribe', {
        method: 'POST',
        headers: {
          'content-type': 'multipart/form-data; boundary=x',
          'content-length': String(bytes.length),
        },
        body: bytes,
      }),
  ],
]) {
  test(`a body of exactly MAX_BODY_BYTES is not size-rejected (${label})`, async () => {
    const harness = loadEndpoint();
    arrangeFetch(harness, {});
    const exact = new Uint8Array(harness.mod.MAX_BODY_BYTES);
    assert.equal(
      exact.length,
      harness.mod.MAX_BODY_BYTES,
      'the fixture must be exactly at the cap, or the boundary is not under test'
    );

    const response = await harness.mod.onRequestPost({
      request: makeRequest(exact),
      env: DEFAULT_ENV,
    });

    const sizeReject = harness.logs
      .map((l) => JSON.parse(l))
      .find((e) => e.event === 'size-reject');
    assert.equal(
      sizeReject,
      undefined,
      `a body of exactly MAX_BODY_BYTES was size-rejected on the ${label} path. ` +
        `The cap is inclusive: only a body STRICTLY larger may be refused, so ` +
        `this is an off-by-one that silently rejects a legitimate maximal ` +
        `submission:\n${JSON.stringify(sizeReject)}`
    );
    assert.notEqual(
      response.status,
      413,
      `a body of exactly MAX_BODY_BYTES returned 413 on the ${label} path`
    );
  });
}

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

// --- Upstream body ceiling (#56 Stage 5 findings 6 and 7) --------------------
//
// The REQUEST body has always been capped; the upstream RESPONSE was read whole
// and then run through the entire redaction chain before the 500-char slice
// bounded anything. Two properties, and the second is what makes the first safe.
//
// Both of these were first written to assert the WHOLE address was absent, and
// both passed against a deliberately broken reader -- the complete address was
// still present in the text, so the shape redactor matched it and the leak the
// tests were named for could not occur. They assert on a surviving FRAGMENT now,
// which is the thing that actually escapes redaction.
const CAP_BYTES = 8 * 1024;

function brevoBody(text) {
  return () => new Response(text, {
    status: 400,
    headers: { 'content-type': 'application/json' },
  });
}

test('upstream: a Brevo error body is bounded, not merely stopped at the cap', async () => {
  // A marker planted past the cap AND inside the first 500 characters of what a
  // whole-body read would produce, so the 500-char slice cannot hide the miss.
  // Reaching it requires the reader to have kept bytes it should have dropped.
  const marker = 'MARKER_PAST_THE_CAP';
  const body = `{"code":"${'x'.repeat(CAP_BYTES)}${marker}","message":"padding"}`;

  const { response, logs } = await submit({ brevo: brevoBody(body) });

  assert.equal(response.status, 502, 'a non-duplicate 4xx is still a 502');
  assert.ok(
    !logs.join('\n').includes(marker),
    'content from beyond the cap reached a log line, so the read was not bounded'
  );
});

test('upstream: the cap stays far above what is ever logged', async () => {
  // The reason readCappedText needs no straddle handling of its own, pinned as a
  // relationship rather than left in a comment. `detail` is redacted BEFORE it is
  // truncated because an address severed mid-token matches no pattern and its
  // local part survives (Ralph round 15). Cutting the READ carries that same
  // hazard -- but only if the cut can land inside what gets logged.
  //
  // It cannot, while the cap sits an order of magnitude above the slice. A
  // trailing-token trim was written for this and removed: it could not fire, so
  // it could not be tested, and untestable defensive code reads as protection
  // without being any. Narrow the gap and that reasoning stops holding, so this
  // asserts the gap instead of trusting a comment to be re-read.
  const source = fs.readFileSync(ENDPOINT_PATH, 'utf8');

  const capMatch = source.match(/const UPSTREAM_BODY_CAP = ([^;]+);/);
  assert.ok(capMatch, 'UPSTREAM_BODY_CAP is gone; this gate is asserting nothing');
  const cap = Function(`return (${capMatch[1]})`)();

  const sliceLengths = [...source.matchAll(/redact\([^;]*?\)\.slice\(0,\s*(\d+)\)/g)]
    .map((m) => Number(m[1]));
  const rawSlices = [...source.matchAll(/\bdetail\s*=\s*redact\([^;]*?\.slice\(0,\s*(\d+)\)/g)]
    .map((m) => Number(m[1]));
  const logged = Math.max(0, ...sliceLengths, ...rawSlices);

  assert.ok(logged > 0, 'no redact(...).slice(0, N) found; the shape changed');
  assert.ok(
    cap >= logged * 4,
    `UPSTREAM_BODY_CAP (${cap}) is no longer comfortably above the ${logged} ` +
    `characters actually logged. The read cut can now land inside the logged ` +
    `window, so an address straddling it survives as an unmatchable fragment. ` +
    `Either restore the gap or reinstate a boundary trim WITH a test that fires.`
  );
});
