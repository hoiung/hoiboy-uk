// Behavioural coverage for the SHIPPED functions/api/contribute.js handler (#56).
//
// Why this file exists, and why it is separate from tests/contribute.test.js:
//
// contribute.test.js hand-mirrors the pure helpers and never loads the real
// module. Its stated reason (see its header) is that contribute.js is ESM inside
// a CommonJS package. That reason was true when it was written and was made
// OBSOLETE by this very Issue, which built the technique that solves it: read the
// source, strip the single top-level `export`, and evaluate it in a node:vm
// context. tests/subscribe.test.js has done exactly that from the start.
//
// The gap that left was not theoretical. Ralph Tier 3 showed that a one-token
// change to contribute.js reopens the round-1 size-ceiling bypass on the endpoint
// that accepts 10MB uploads, while the ENTIRE delivered gate set stays green:
// the parity gate passes (it compares helper bodies byte-for-byte, and the mutant
// is in the handler, not a helper), and the JS suite passes (nothing executes
// this handler). Byte-equality with a tested twin transfers evidence for the
// helper BODIES, never for the handler WIRING.
//
// So this file covers the wiring #56 changed on this endpoint, and nothing else.
// The existing mirror tests are left alone: replacing them is not this Issue's
// job, and they still pass.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const ENDPOINT_PATH = path.join(__dirname, '..', 'functions', 'api', 'contribute.js');

const EXPORT_RE = /^export\s+(?=async\s+function\s|function\s|const\s|let\s)/gm;

function loadEndpoint() {
  const raw = fs.readFileSync(ENDPOINT_PATH, 'utf8');

  // Asserted, not assumed: if the module ever grows a second top-level export,
  // the strip below would silently produce a different module and every
  // assertion in this file would pass vacuously against a handler-less object.
  const stripped = raw.match(EXPORT_RE);
  assert.equal(
    stripped ? stripped.length : 0,
    1,
    'expected exactly one top-level `export` in contribute.js; the vm load below ' +
      'is only valid while that holds'
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
    Blob,
    ReadableStream,
    btoa,
    crypto,
    console: { log: (line) => logs.push(line), error: (line) => logs.push(line) },
    fetch: async (url, init) => {
      calls.push({ url: String(url), init });
      if (String(url).includes('siteverify')) {
        return new Response(JSON.stringify({ success: true }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        });
      }
      return new Response(JSON.stringify({ ok: true }), {
        status: 202,
        headers: { 'content-type': 'application/json' },
      });
    },
  });

  const EXPOSE = '\n;({ onRequestPost, MAX_BODY_BYTES, readCapped, redactPii })';
  const mod = vm.runInContext(raw.replace(EXPORT_RE, '') + EXPOSE, context, {
    filename: ENDPOINT_PATH,
  });

  assert.equal(typeof mod.onRequestPost, 'function', 'onRequestPost did not load');
  return { mod, calls, logs };
}

const ENV = {
  TURNSTILE_SECRET_KEY: 'test-secret', // secret-allow (test fixture, never a real credential)
  CF_ACCOUNT_ID: 'test-account', // secret-allow (test fixture, never a real account id)
  CF_EMAIL_TOKEN: 'test-token', // secret-allow (test fixture, never a real credential)
  AGIT_UPLOADS: null,
};

const BOUNDARY = '----contributeE2E';

function streamed(bytes) {
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(bytes);
      controller.close();
    },
  });
  return new Request('https://hoiboy.uk/api/contribute', {
    method: 'POST',
    headers: { 'content-type': `multipart/form-data; boundary=${BOUNDARY}` },
    body: stream,
    duplex: 'half',
  });
}

function noUpstreamCall(calls) {
  const upstream = calls.filter((c) => !String(c.url).includes('siteverify'));
  assert.equal(upstream.length, 0, `expected no upstream call, got ${JSON.stringify(upstream)}`);
}

test('the size ceiling rejects an over-cap streamed body with no content-length', async () => {
  // The exact mutant Ralph Tier 3 demonstrated survives every other gate:
  // gating the rejection on the header (`capped === null && declaredLength > 0`)
  // reopens this path, because a chunked request has declaredLength 0.
  const harness = loadEndpoint();
  const oversized = new Uint8Array(harness.mod.MAX_BODY_BYTES + 1);

  const response = await harness.mod.onRequestPost({ request: streamed(oversized), env: ENV });

  assert.equal(response.status, 413);
  noUpstreamCall(harness.calls);
  const entry = harness.logs.map((l) => JSON.parse(l)).find((e) => e.event === 'size-type-reject');
  assert.ok(entry, 'an over-cap body must be visible in the logs, not silently dropped');
  assert.equal(entry.source, 'stream', 'the header path cannot have caught a headerless request');
});

for (const [label, header] of [
  ['not a number', 'notanumber'],
  ['empty string', ''],
  ['negative', '-1'],
  ['an undersized lie', '10'],
]) {
  test(`the size ceiling holds when content-length is ${label}`, async () => {
    const harness = loadEndpoint();
    const oversized = new Uint8Array(harness.mod.MAX_BODY_BYTES + 1);
    const request = new Request('https://hoiboy.uk/api/contribute', {
      method: 'POST',
      headers: {
        'content-type': `multipart/form-data; boundary=${BOUNDARY}`,
        'content-length': header,
      },
      body: oversized,
    });

    const response = await harness.mod.onRequestPost({ request, env: ENV });

    assert.equal(
      response.status,
      413,
      `an over-cap body was accepted with content-length ${JSON.stringify(header)}`
    );
    noUpstreamCall(harness.calls);
  });
}

test('a body under the cap is not rejected and still parses', async () => {
  // Redaction and the ceiling must not cost the happy path: the capped read has
  // to hand formData() a body it can still parse, boundary and all.
  const harness = loadEndpoint();
  const body = Buffer.from(
    `--${BOUNDARY}\r\nContent-Disposition: form-data; name="website"\r\n\r\nbot\r\n--${BOUNDARY}--\r\n`,
    'utf8'
  );

  const response = await harness.mod.onRequestPost({
    request: streamed(new Uint8Array(body)),
    env: ENV,
  });

  // The honeypot path: looks like success to a bot, makes no upstream call.
  assert.equal(response.status, 303);
  noUpstreamCall(harness.calls);
  assert.ok(
    harness.logs.map((l) => JSON.parse(l)).some((e) => e.event === 'honeypot-drop'),
    'the body did not parse, so the capped read mangled it'
  );
});

test('redactPii strips an address from upstream text before it can be logged', () => {
  const harness = loadEndpoint();
  const redacted = harness.mod.redactPii(
    '{"message":"rejected for contact targetvictim@example.com","code":"bad_request"}'
  );

  assert.ok(!redacted.includes('targetvictim@example.com'), 'the address survived redaction');
  assert.ok(redacted.includes('[email-redacted]'), 'redaction is not deletion');
  assert.ok(redacted.includes('bad_request'), 'the upstream code must survive; it is the diagnostic');
});
