// brevo-webhook.test.js -- the new-subscriber alert endpoint. hoiboy-uk#56 AC 0.3.
//
// Same harness as tests/subscribe.test.js and for the same reason: the shipped file
// is evaluated in a `node:vm` context with its `export` stripped, so these drive the
// ACTUAL handler rather than a hand-mirrored copy that can drift while staying green.
// Un-stubbed fetch throws, so a test that forgets to arrange its upstream fails loudly
// instead of reaching the wire.
'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ENDPOINT_PATH = path.join(__dirname, '..', 'functions', 'api', 'brevo-webhook.js');
const RAW = fs.readFileSync(ENDPOINT_PATH, 'utf8');
const EXPORT_RE = /^export\s+/gm;

const AUTH_FIXTURE = 'unit-fixture-abcdefghijklmnop';
const DEFAULT_ENV = { BREVO_API_KEY: 'xkeysib-test', BREVO_WEBHOOK_TOKEN: AUTH_FIXTURE }; // secret-allow (synthetic test env; the real binding name cannot be renamed)

function harness({ fetchImpl } = {}) {
  const calls = [];
  const logs = [];
  const context = vm.createContext({
    Response, Request, Headers, URL, Buffer,
    console: { log: (l) => logs.push(l), error: (l) => logs.push(l) },
    fetch: async (url, init) => {
      calls.push({ url: String(url), init });
      if (fetchImpl) return fetchImpl(url, init);
      return new Response('{}', { status: 201, headers: { 'content-type': 'application/json' } });
    },
  });
  const EXPOSE = '\n;({ onRequestPost, tokensMatch, emailShape, escapeHtml, ALERT_TO, WATCHED_EVENTS })';
  const mod = vm.runInContext(RAW.replace(EXPORT_RE, '') + EXPOSE, context, { filename: ENDPOINT_PATH });
  assert.equal(typeof mod.onRequestPost, 'function', 'onRequestPost did not load');
  return { mod, calls, logs };
}

function post({ auth = AUTH_FIXTURE, body = {}, raw } = {}) {
  const url = auth === null
    ? 'https://hoiboy.uk/api/brevo-webhook'
    : `https://hoiboy.uk/api/brevo-webhook?token=${encodeURIComponent(auth)}`;
  return new Request(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: raw !== undefined ? raw : JSON.stringify(body),
  });
}

// Brevo's documented DELIVERY payload for this event. Note `list_addition` in
// snake_case: the subscription enum on POST /v3/webhooks is camelCase `listAddition`,
// and matching only that spelling silently ignored the first real signup on this
// Issue. This fixture is the shape Brevo actually sends.
const LIST_ADDITION = {
  id: 'xxxxxx', email: 'reader@example.com', event: 'list_addition',
  key: 'k', list_id: [4], date: '2026-08-05 04:24:00', ts: 1604937111,
};

// ----------------------------------------------------------------------

test('config: a missing binding is named on the first request, not half-worked', async () => {
  const h = harness();
  const res = await h.mod.onRequestPost({ request: post(), env: { BREVO_API_KEY: 'x' } });
  assert.equal(res.status, 500);
  const line = h.logs.find((l) => l.includes('config-missing'));
  assert.ok(line, 'no config-missing log line');
  assert.match(line, /BREVO_WEBHOOK_TOKEN/);
  assert.equal(h.calls.length, 0, 'must not call upstream when unconfigured');
});

test('auth: a wrong token is refused and never reaches the body or the wire', async () => {
  const h = harness();
  const res = await h.mod.onRequestPost({ request: post({ auth: 'wrong' }), env: DEFAULT_ENV });
  assert.equal(res.status, 403);
  assert.equal(h.calls.length, 0);
});

test('auth: a missing token is refused', async () => {
  const h = harness();
  const res = await h.mod.onRequestPost({ request: post({ auth: null }), env: DEFAULT_ENV });
  assert.equal(res.status, 403);
});

test('auth: token compare is length-then-constant-time, not a shared-prefix ===', () => {
  const { mod } = harness();
  assert.equal(mod.tokensMatch('abc', 'abc'), true);
  assert.equal(mod.tokensMatch('abc', 'abd'), false);
  // A correct PREFIX must not pass. This is the failure a naive startsWith would ship.
  assert.equal(mod.tokensMatch('ab', 'abc'), false);
  assert.equal(mod.tokensMatch('abcd', 'abc'), false);
  assert.equal(mod.tokensMatch(undefined, 'abc'), false);
});

test('an unrelated event is ignored with 200, so Brevo does not retry it', async () => {
  const h = harness();
  for (const event of ['opened', 'click', 'unsubscribed', 'contactDeleted']) {
    const res = await h.mod.onRequestPost({ request: post({ body: { event, email: 'a@example.com' } }), env: DEFAULT_ENV });
    assert.equal(res.status, 200, `${event} should be ignored`);
  }
  assert.equal(h.calls.length, 0, 'no alert should be sent for unrelated events');
});

test('listAddition sends exactly one alert, to the hard-coded operator address', async () => {
  const h = harness();
  const res = await h.mod.onRequestPost({ request: post({ body: LIST_ADDITION }), env: DEFAULT_ENV });
  assert.equal(res.status, 200);
  assert.equal(h.calls.length, 1, 'exactly one upstream send');
  const sent = JSON.parse(h.calls[0].init.body);
  assert.equal(sent.to[0].email, 'hoiboyuk@gmail.com');
  assert.match(sent.subject, /reader@example\.com/);
  assert.equal(h.calls[0].init.headers['api-key'], 'xkeysib-test');
});

test('the alert destination cannot be redirected by the payload', async () => {
  // The URL is the only credential, so a leaked URL must not become a way to mail
  // arbitrary people from this domain.
  const h = harness();
  await h.mod.onRequestPost({
    request: post({ body: { ...LIST_ADDITION, to: 'attacker@example.com', sender: 'x@example.com' } }),
    env: DEFAULT_ENV,
  });
  const sent = JSON.parse(h.calls[0].init.body);
  assert.equal(sent.to.length, 1);
  assert.equal(sent.to[0].email, 'hoiboyuk@gmail.com');
});

test('payload text is HTML-escaped into the alert body', async () => {
  const h = harness();
  await h.mod.onRequestPost({
    request: post({ body: { ...LIST_ADDITION, email: '<img src=x onerror=alert(1)>@example.com' } }),
    env: DEFAULT_ENV,
  });
  const sent = JSON.parse(h.calls[0].init.body);
  assert.ok(!sent.htmlContent.includes('<img'), 'raw tag survived into the alert body');
  assert.ok(sent.htmlContent.includes('&lt;img'), 'expected the escaped form');
});

test('PII: the subscriber address never reaches a log line', async () => {
  // The repo-wide rule this Issue spent rounds 11-15 establishing. The alert email is
  // the only place the address legitimately appears.
  const h = harness();
  await h.mod.onRequestPost({ request: post({ body: LIST_ADDITION }), env: DEFAULT_ENV });
  const joined = h.logs.join('\n');
  assert.ok(!joined.includes('reader@example.com'), `address leaked into logs: ${joined}`);
  assert.ok(joined.includes('alert-send'), 'the send should still be observable');
});

test('an upstream failure returns 200: the subscription is unaffected', async () => {
  // A non-2xx would make Brevo retry, which cannot fix our outbound problem and
  // spends the shared 300/day cap.
  const h = harness({ fetchImpl: async () => new Response('nope', { status: 500 }) });
  const res = await h.mod.onRequestPost({ request: post({ body: LIST_ADDITION }), env: DEFAULT_ENV });
  assert.equal(res.status, 200);
  const line = h.logs.find((l) => l.includes('alert-send'));
  assert.match(line, /"ok":false/);
});

test('a network throw is caught, logged, and still 200', async () => {
  const h = harness({ fetchImpl: async () => { throw new Error('offline'); } });
  const res = await h.mod.onRequestPost({ request: post({ body: LIST_ADDITION }), env: DEFAULT_ENV });
  assert.equal(res.status, 200);
  assert.ok(h.logs.some((l) => l.includes('network')));
});

test('a non-JSON body is rejected without touching the wire', async () => {
  const h = harness();
  const res = await h.mod.onRequestPost({ request: post({ raw: 'not json at all' }), env: DEFAULT_ENV });
  assert.equal(res.status, 400);
  assert.equal(h.calls.length, 0);
});

test('emailShape reports lengths, never the address itself', () => {
  const { mod } = harness();
  assert.equal(mod.emailShape('abcd@example.com'), '4@11');
  assert.equal(mod.emailShape('nonsense'), 'invalid');
});

test('REGRESSION: the delivered snake_case event name is accepted', async () => {
  // The defect this file exists to prevent. Brevo's subscription enum is camelCase
  // `listAddition`; the payload it delivers says `list_addition`. Matching only the
  // name you subscribed with makes every real delivery a silent 200 Ignored -- the
  // contact confirms, lands on the list, and the operator is told nothing.
  const h = harness();
  const res = await h.mod.onRequestPost({
    request: post({ body: { event: 'list_addition', email: 'r@example.com', list_id: [4] } }),
    env: DEFAULT_ENV,
  });
  assert.equal(res.status, 200);
  assert.equal(h.calls.length, 1, 'snake_case list_addition must raise an alert');
});

test('both spellings are watched, so a Brevo rename cannot silently kill alerts', () => {
  const { mod } = harness();
  assert.ok(mod.WATCHED_EVENTS.includes('list_addition'), 'delivered spelling missing');
  assert.ok(mod.WATCHED_EVENTS.includes('listAddition'), 'subscription spelling missing');
});
