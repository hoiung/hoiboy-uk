// brevo-webhook.test.js -- the new-subscriber alert endpoint (hoiboy-uk#56 AC 0.3)
// and the AGIT welcome email (#65 Phase 2).
//
// Same harness as tests/subscribe.test.js and for the same reason: the shipped file
// is evaluated in a `node:vm` context with its `export` stripped, so these drive the
// ACTUAL handler rather than a hand-mirrored copy that can drift while staying green.
// Un-stubbed fetch throws, so a test that forgets to arrange its upstream fails loudly
// instead of reaching the wire.
//
// The handler answers Brevo first and does the alert + welcome work inside
// context.waitUntil (#65 AC 2.1). `run()` below passes a waitUntil that collects the
// work and awaits it, so every assertion on calls and logs sees the finished work.
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

// The AGIT bindings. The invite is a fixture on a reserved domain, never a real
// WhatsApp link: tests/test_no_whatsapp_invite_links.py fails the build on one.
const INVITE_FIXTURE = 'https://invite.example/agit-fixture-7f3a9c';
const AGIT_ENV = {
  ...DEFAULT_ENV,
  BREVO_LIST_ID: '4',
  AGIT_LIST_ID: '43',
  AGIT_WELCOME_TEMPLATE_ID: '28',
  AGIT_WHATSAPP_INVITE_URL: INVITE_FIXTURE,
};

const EMAIL_URL = 'https://api.brevo.com/v3/smtp/email';
const CONTACTS_URL = 'https://api.brevo.com/v3/contacts';

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
  const EXPOSE = '\n;({ onRequestPost, tokensMatch, emailShape, escapeHtml, ALERT_TO, WATCHED_EVENTS,' +
    ' inviteUrl, RESEND_HINT })';
  const mod = vm.runInContext(RAW.replace(EXPORT_RE, '') + EXPOSE, context, { filename: ENDPOINT_PATH });
  assert.equal(typeof mod.onRequestPost, 'function', 'onRequestPost did not load');

  // Invoke the handler, then await every waitUntil promise it scheduled.
  async function run(request, env) {
    const pending = [];
    const res = await mod.onRequestPost({ request, env, waitUntil: (p) => pending.push(p) });
    await Promise.all(pending);
    return res;
  }
  return { mod, calls, logs, run };
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

function json(status, payload) {
  return new Response(JSON.stringify(payload), { status, headers: { 'content-type': 'application/json' } });
}

const alertCalls = (calls) => calls.filter((c) => c.url === EMAIL_URL && !JSON.parse(c.init.body).templateId);
const welcomeCalls = (calls) => calls.filter((c) => c.url === EMAIL_URL && JSON.parse(c.init.body).templateId);
const lastAlert = (calls) => {
  const a = alertCalls(calls);
  assert.ok(a.length >= 1, 'no operator alert was sent');
  return JSON.parse(a[a.length - 1].init.body);
};
// The exact sequence of upstream calls, as "METHOD url" with the welcome and the
// alert told apart, so a test can pin the order of the guarded steps.
const sequence = (calls) => calls.map((c) => {
  const method = (c.init && c.init.method) || 'GET';
  if (c.url === EMAIL_URL) return JSON.parse(c.init.body).templateId ? 'POST welcome' : 'POST alert';
  return `${method} ${c.url.replace(CONTACTS_URL, 'contacts')}`;
});

// A Brevo stand-in with one contact in it. `fail` swaps a step's answer, which is
// how the failure branches are reached; the contact store is updated by the PUT,
// so a second delivery sees the first delivery's marker.
function fakeBrevo({ contact = null, fail = {} } = {}) {
  const state = { contact: contact && JSON.parse(JSON.stringify(contact)) };
  async function impl(url, init) {
    const u = String(url);
    const method = (init && init.method) || 'GET';
    if (u.startsWith(`${CONTACTS_URL}/`)) {
      if (method === 'GET') {
        if (fail.read) return fail.read();
        return state.contact ? json(200, state.contact) : json(404, { code: 'document_not_found' });
      }
      if (method === 'PUT') {
        if (fail.mark) return fail.mark();
        Object.assign(state.contact.attributes, JSON.parse(init.body).attributes);
        return new Response(null, { status: 204 });
      }
    }
    if (u === EMAIL_URL && method === 'POST') {
      const isWelcome = Boolean(JSON.parse(init.body).templateId);
      if (isWelcome && fail.welcome) return fail.welcome();
      if (!isWelcome && fail.alert) return fail.alert();
      return json(201, { messageId: '<fixture@smtp>' });
    }
    if (method === 'DELETE') return new Response(null, { status: 204 });
    throw new Error(`unexpected ${method} ${u}`);
  }
  return { impl, state };
}

const MEMBER = (overrides = {}) => ({
  email: 'member@example.com',
  listIds: [43],
  attributes: { FIRSTNAME: 'Mem', AGIT_CONSENT_VERSION: '2026-10-15', AGIT_CONSENT_TIMESTAMP: '2026-10-15T00:00:00.000Z' },
  ...overrides,
});
const agitDelivery = (listIds = [43], email = 'member@example.com') => ({ ...LIST_ADDITION, email, list_id: listIds });

// ----------------------------------------------------------------------

test('config: a missing binding is named on the first request, not half-worked', async () => {
  const h = harness();
  const res = await h.run(post(), { BREVO_API_KEY: 'x' });
  assert.equal(res.status, 500);
  const line = h.logs.find((l) => l.includes('config-missing'));
  assert.ok(line, 'no config-missing log line');
  assert.match(line, /BREVO_WEBHOOK_TOKEN/);
  assert.equal(h.calls.length, 0, 'must not call upstream when unconfigured');
});

test('auth: a wrong token is refused and never reaches the body or the wire', async () => {
  const h = harness();
  const res = await h.run(post({ auth: 'wrong' }), DEFAULT_ENV);
  assert.equal(res.status, 403);
  assert.equal(h.calls.length, 0);
});

test('auth: a missing token is refused', async () => {
  const h = harness();
  const res = await h.run(post({ auth: null }), DEFAULT_ENV);
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
    const res = await h.run(post({ body: { event, email: 'a@example.com' } }), DEFAULT_ENV);
    assert.equal(res.status, 200, `${event} should be ignored`);
  }
  assert.equal(h.calls.length, 0, 'no alert should be sent for unrelated events');
});

test('listAddition sends exactly one alert, to the hard-coded operator address', async () => {
  const h = harness();
  const res = await h.run(post({ body: LIST_ADDITION }), DEFAULT_ENV);
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
  await h.run(post({ body: { ...LIST_ADDITION, to: 'attacker@example.com', sender: 'x@example.com' } }), DEFAULT_ENV);
  const sent = JSON.parse(h.calls[0].init.body);
  assert.equal(sent.to.length, 1);
  assert.equal(sent.to[0].email, 'hoiboyuk@gmail.com');
});

test('payload text is HTML-escaped into the alert body', async () => {
  const h = harness();
  await h.run(post({ body: { ...LIST_ADDITION, email: '<img src=x onerror=alert(1)>@example.com' } }), DEFAULT_ENV);
  const sent = JSON.parse(h.calls[0].init.body);
  assert.ok(!sent.htmlContent.includes('<img'), 'raw tag survived into the alert body');
  assert.ok(sent.htmlContent.includes('&lt;img'), 'expected the escaped form');
});

test('PII: the subscriber address never reaches a log line', async () => {
  // The repo-wide rule this Issue spent rounds 11-15 establishing. The alert email is
  // the only place the address legitimately appears.
  const h = harness();
  await h.run(post({ body: LIST_ADDITION }), DEFAULT_ENV);
  const joined = h.logs.join('\n');
  assert.ok(!joined.includes('reader@example.com'), `address leaked into logs: ${joined}`);
  assert.ok(joined.includes('alert-send'), 'the send should still be observable');
});

test('an upstream failure that stays failed returns 200: the subscription is unaffected', async () => {
  // A non-2xx would make Brevo retry, which cannot fix our outbound problem and
  // spends the shared 300/day cap.
  const h = harness({ fetchImpl: async () => new Response('nope', { status: 500 }) });
  const res = await h.run(post({ body: LIST_ADDITION }), DEFAULT_ENV);
  assert.equal(res.status, 200);
  const line = h.logs.find((l) => l.includes('alert-send') && l.includes('"ok":false'));
  assert.ok(line, 'a permanently failed send must be logged with ok:false');
  assert.match(line, /retryStatus/, 'the retry outcome must be recorded, not hidden');
});

test('a blocklisted operator address self-heals: unblock, retry, and say so', async () => {
  // THE SILENT KILLER. Brevo puts an unsubscribe link on these alerts and Gmail
  // shows it beside the sender. One click blocklists the operator, every future
  // alert is refused, and because this endpoint answers 200 either way nothing
  // anywhere reports it. The alerts would just stop.
  let sends = 0;
  const h = harness({
    fetchImpl: async (url, init) => {
      // 204 is a null-body status: `new Response('', {status:204})` THROWS.
      if (init && init.method === 'DELETE') return new Response(null, { status: 204 });
      sends += 1;
      return sends === 1
        ? new Response('blocked', { status: 400 })
        : new Response('{}', { status: 201 });
    },
  });
  const res = await h.run(post({ body: LIST_ADDITION }), DEFAULT_ENV);

  // The 200 is decided before the work runs (AC 2.1), so the outcome is read from
  // the logs, not from the response text.
  assert.equal(res.status, 200);
  assert.equal(sends, 2, 'the send must be retried after the unblock');

  const unblock = h.calls.find((c) => c.init && c.init.method === 'DELETE');
  assert.ok(unblock, 'the unblock endpoint was never called');
  assert.match(unblock.url, /blockedContacts\/hoiboyuk%40gmail\.com$/,
    'the unblock must target the operator address, url-encoded');

  const line = h.logs.find((l) => l.includes('alert-recover') && l.includes('"ok":true'));
  assert.ok(line, 'a recovered send must be logged distinctly from a clean one');
});

test('a network throw is caught, logged, and still 200', async () => {
  const h = harness({ fetchImpl: async () => { throw new Error('offline'); } });
  const res = await h.run(post({ body: LIST_ADDITION }), DEFAULT_ENV);
  assert.equal(res.status, 200);
  assert.ok(h.logs.some((l) => l.includes('network')));
});

test('a non-JSON body is rejected without touching the wire', async () => {
  const h = harness();
  const res = await h.run(post({ raw: 'not json at all' }), DEFAULT_ENV);
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
  const res = await h.run(post({ body: { event: 'list_addition', email: 'r@example.com', list_id: [4] } }), DEFAULT_ENV);
  assert.equal(res.status, 200);
  assert.equal(h.calls.length, 1, 'snake_case list_addition must raise an alert');
});

test('both spellings are watched, so a Brevo rename cannot silently kill alerts', () => {
  const { mod } = harness();
  assert.ok(mod.WATCHED_EVENTS.includes('list_addition'), 'delivered spelling missing');
  assert.ok(mod.WATCHED_EVENTS.includes('listAddition'), 'subscription spelling missing');
});

// ----------------------------------------------------------------------
// #65: answer first, work after.
// ----------------------------------------------------------------------

test('work runs in waitUntil after the 200', async () => {
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  let completed = 0;
  const h = harness({
    fetchImpl: async () => {
      await gate;
      completed += 1;
      return json(201, {});
    },
  });
  const pending = [];
  const res = await h.mod.onRequestPost({ request: post({ body: LIST_ADDITION }), env: DEFAULT_ENV, waitUntil: (p) => pending.push(p) });
  assert.equal(res.status, 200, 'Brevo must get its 200 before the alert send finishes');
  assert.equal(pending.length, 1, 'the work must be handed to waitUntil');
  assert.equal(completed, 0, 'no send may have completed before the 200');
  release();
  await Promise.all(pending);
  assert.equal(completed, 1);
  assert.equal(alertCalls(h.calls).length, 1);
});

// ----------------------------------------------------------------------
// #65 AC 2.2: the welcome, once, only for a signed-up member.
// ----------------------------------------------------------------------

test('welcome sent once for a new AGIT member', async () => {
  const brevo = fakeBrevo({ contact: MEMBER() });
  const h = harness({ fetchImpl: brevo.impl });
  const res = await h.run(post({ body: agitDelivery() }), AGIT_ENV);
  assert.equal(res.status, 200);
  assert.deepEqual(sequence(h.calls), [
    'GET contacts/member%40example.com', 'PUT contacts/member%40example.com', 'POST welcome', 'POST alert',
  ]);
  const marker = JSON.parse(h.calls[1].init.body);
  assert.deepEqual(Object.keys(marker.attributes), ['AGIT_WELCOME_SENT', 'AGIT_LEFT']);
  assert.match(marker.attributes.AGIT_WELCOME_SENT, /^\d{4}-\d{2}-\d{2}T/);
  assert.equal(marker.attributes.AGIT_LEFT, '');
  assert.match(lastAlert(h.calls).htmlContent, /AGIT welcome email: sent/);
});

test('no welcome when AGIT_WELCOME_SENT is set', async () => {
  const contact = MEMBER();
  contact.attributes.AGIT_WELCOME_SENT = '2026-10-15T01:00:00.000Z';
  const h = harness({ fetchImpl: fakeBrevo({ contact }).impl });
  await h.run(post({ body: agitDelivery() }), AGIT_ENV);
  assert.deepEqual(sequence(h.calls), ['GET contacts/member%40example.com', 'POST alert']);
  assert.match(lastAlert(h.calls).htmlContent, /AGIT welcome email: already sent \(skipped\)/);
});

test('no welcome without an AGIT signup record', async () => {
  // On the AGIT list (say, added by hand in the dashboard) but never through the
  // form: no AGIT_CONSENT_VERSION, so no invite. And a contact not on the list at all.
  for (const contact of [MEMBER({ attributes: { FIRSTNAME: 'X' } }), MEMBER({ listIds: [4] })]) {
    const h = harness({ fetchImpl: fakeBrevo({ contact }).impl });
    await h.run(post({ body: agitDelivery() }), AGIT_ENV);
    assert.deepEqual(sequence(h.calls), ['GET contacts/member%40example.com', 'POST alert']);
    assert.match(lastAlert(h.calls).htmlContent, /AGIT welcome email: skipped: no AGIT signup record/);
  }
});

test('no welcome when the marker write fails', async () => {
  const h = harness({ fetchImpl: fakeBrevo({ contact: MEMBER(), fail: { mark: () => json(500, {}) } }).impl });
  await h.run(post({ body: agitDelivery() }), AGIT_ENV);
  assert.deepEqual(sequence(h.calls), [
    'GET contacts/member%40example.com', 'PUT contacts/member%40example.com', 'POST alert',
  ]);
  assert.match(lastAlert(h.calls).htmlContent, /AGIT welcome email: FAILED \(marker write 500\)/);
});

test('newsletter-only list_id sends no welcome', async () => {
  const h = harness({ fetchImpl: fakeBrevo({ contact: MEMBER() }).impl });
  await h.run(post({ body: agitDelivery([4]) }), AGIT_ENV);
  assert.deepEqual(sequence(h.calls), ['POST alert']);
  assert.ok(!lastAlert(h.calls).htmlContent.includes('AGIT welcome email'));
});

test('a repeat event sends no second welcome', async () => {
  const brevo = fakeBrevo({ contact: MEMBER() });
  const h = harness({ fetchImpl: brevo.impl });
  await h.run(post({ body: agitDelivery() }), AGIT_ENV);
  await h.run(post({ body: agitDelivery() }), AGIT_ENV);
  assert.deepEqual(sequence(h.calls), [
    'GET contacts/member%40example.com', 'PUT contacts/member%40example.com', 'POST welcome', 'POST alert',
    'GET contacts/member%40example.com', 'POST alert',
  ]);
  assert.equal(welcomeCalls(h.calls).length, 1);
});

test('string list ids are matched as numbers', async () => {
  const h = harness({ fetchImpl: fakeBrevo({ contact: MEMBER({ listIds: ['43'] }) }).impl });
  await h.run(post({ body: agitDelivery(['43']) }), AGIT_ENV);
  assert.deepEqual(sequence(h.calls), [
    'GET contacts/member%40example.com', 'PUT contacts/member%40example.com', 'POST welcome', 'POST alert',
  ]);
});

test('a throwing contact read still sends the alert with FAILED', async () => {
  for (const read of [() => { throw new TypeError('network down'); }, () => new Response('not json', { status: 200 })]) {
    const h = harness({ fetchImpl: fakeBrevo({ contact: MEMBER(), fail: { read } }).impl });
    const res = await h.run(post({ body: agitDelivery() }), AGIT_ENV);
    assert.equal(res.status, 200);
    assert.deepEqual(sequence(h.calls), ['GET contacts/member%40example.com', 'POST alert']);
    const alert = lastAlert(h.calls);
    assert.match(alert.htmlContent, /AGIT welcome email: FAILED \((TypeError|SyntaxError)\)/);
    assert.match(alert.subject, /^New AGIT member: /);
  }
});

// ----------------------------------------------------------------------
// #65 AC 2.3: the send, and where the invite link may never appear.
// ----------------------------------------------------------------------

test('welcome send carries only the template id and the invite param', async () => {
  const h = harness({ fetchImpl: fakeBrevo({ contact: MEMBER({ email: 'member@example.com' }) }).impl });
  await h.run(post({ body: agitDelivery([43], 'MEMBER@Example.com') }), AGIT_ENV);
  const welcome = welcomeCalls(h.calls);
  assert.equal(welcome.length, 1);
  assert.deepEqual(JSON.parse(welcome[0].init.body), {
    templateId: 28,
    to: [{ email: 'member@example.com' }],
    params: { INVITE_URL: INVITE_FIXTURE },
  });
  assert.equal(h.calls[0].url, `${CONTACTS_URL}/member%40example.com`, 'the contact is read by its lower-cased address');
});

test('a malformed invite URL fails loud', async () => {
  for (const bad of ['', '   ', 'http://invite.example/x', 'https://invite.example/a b', 'invite.example/x']) {
    const h = harness({ fetchImpl: fakeBrevo({ contact: MEMBER() }).impl });
    await h.run(post({ body: agitDelivery() }), { ...AGIT_ENV, AGIT_WHATSAPP_INVITE_URL: bad });
    assert.deepEqual(sequence(h.calls), ['POST alert'], `invite ${JSON.stringify(bad)} was used`);
    assert.match(lastAlert(h.calls).htmlContent, /AGIT welcome email: NOT sent \(missing AGIT_WHATSAPP_INVITE_URL\)/);
    const line = h.logs.map((l) => JSON.parse(l)).find((e) => e.event === 'config-missing');
    assert.deepEqual(line.missing, ['AGIT_WHATSAPP_INVITE_URL']);
  }
  // Surrounding whitespace is trimmed, not fatal.
  const { mod } = harness();
  assert.equal(mod.inviteUrl(`  ${INVITE_FIXTURE}\n`), INVITE_FIXTURE);
});

test('invite link never reaches a log line or the alert', async () => {
  const echo = () => new Response(JSON.stringify({ code: 'invalid_parameter', message: `bad ${INVITE_FIXTURE}` }), { status: 400 });
  const paths = [
    {},                                                          // success
    { welcome: echo },                                           // a 4xx that echoes the request
    { welcome: () => { throw new TypeError(`fetch failed for ${INVITE_FIXTURE}`); } }, // a network throw
  ];
  for (const fail of paths) {
    const h = harness({ fetchImpl: fakeBrevo({ contact: MEMBER(), fail }).impl });
    await h.run(post({ body: agitDelivery() }), AGIT_ENV);
    for (const line of h.logs) {
      assert.ok(!line.includes(INVITE_FIXTURE), `invite link in a log line: ${line}`);
      assert.ok(!line.includes('member@example.com'), `member address in a log line: ${line}`);
    }
    const alert = lastAlert(h.calls);
    assert.ok(!JSON.stringify(alert).includes(INVITE_FIXTURE), 'invite link in the operator alert');
  }
});

// ----------------------------------------------------------------------
// #65 AC 2.4 + 2.5: bindings and the member-side unblock.
// ----------------------------------------------------------------------

test('missing AGIT bindings never block the newsletter alert', async () => {
  // No AGIT_LIST_ID: an AGIT event cannot be told apart, so EVERY alert carries the line.
  for (const listIds of [[4], [43]]) {
    const env = { ...AGIT_ENV };
    delete env.AGIT_LIST_ID;
    const h = harness({ fetchImpl: fakeBrevo({ contact: MEMBER() }).impl });
    const res = await h.run(post({ body: agitDelivery(listIds) }), env);
    assert.equal(res.status, 200);
    assert.deepEqual(sequence(h.calls), ['POST alert']);
    const alert = lastAlert(h.calls);
    assert.match(alert.subject, /^New newsletter subscriber: /);
    assert.match(alert.htmlContent, /AGIT welcome email: NOT sent \(missing AGIT_LIST_ID\)/);
  }
  // A missing template id or invite on an AGIT event: no welcome attempted, line names it.
  for (const name of ['AGIT_WELCOME_TEMPLATE_ID', 'AGIT_WHATSAPP_INVITE_URL']) {
    const env = { ...AGIT_ENV };
    delete env[name];
    const h = harness({ fetchImpl: fakeBrevo({ contact: MEMBER() }).impl });
    await h.run(post({ body: agitDelivery([43, 4]) }), env);
    assert.deepEqual(sequence(h.calls), ['POST alert']);
    assert.match(lastAlert(h.calls).htmlContent, new RegExp(`AGIT welcome email: NOT sent \\(missing ${name}\\)`));
    assert.ok(h.logs.some((l) => l.includes('config-missing') && l.includes(name)));
  }
});

test('a failed welcome never unblocks the member', async () => {
  const brevo = fakeBrevo({
    contact: MEMBER(),
    fail: { welcome: () => json(400, { code: 'blocked' }), alert: (() => { let n = 0; return () => (n++ === 0 ? json(400, {}) : json(201, {})); })() },
  });
  const h = harness({ fetchImpl: brevo.impl });
  await h.run(post({ body: agitDelivery() }), AGIT_ENV);
  const deletes = h.calls.filter((c) => c.init && c.init.method === 'DELETE');
  assert.equal(deletes.length, 1, 'only the operator alert self-heals');
  assert.match(deletes[0].url, /blockedContacts\/hoiboyuk%40gmail\.com$/);
  assert.ok(!deletes.some((c) => c.url.includes('member')), 'the member was unblocked');
  assert.match(lastAlert(h.calls).htmlContent, /AGIT welcome email: FAILED \(welcome send 400\)/);
});

// ----------------------------------------------------------------------
// #65 AC 2.6: the alert says what this delivery did.
// ----------------------------------------------------------------------

test('alert labels a new AGIT member who was already a subscriber', async () => {
  const h = harness({ fetchImpl: fakeBrevo({ contact: MEMBER({ listIds: [4, 43] }) }).impl });
  await h.run(post({ body: agitDelivery([4, 43]) }), AGIT_ENV);
  const alert = lastAlert(h.calls);
  assert.equal(alert.subject, 'New AGIT member: member@example.com');
  assert.ok(alert.htmlContent.startsWith('<p>Someone joined Asians &amp; Gingers in Tech.</p>'));
  assert.match(alert.htmlContent, /AGIT welcome email: sent/);
});

test("alert labels an existing member's newsletter signup", async () => {
  const contact = MEMBER({ listIds: [43, 4] });
  contact.attributes.AGIT_WELCOME_SENT = '2026-10-15T01:00:00.000Z';
  const h = harness({ fetchImpl: fakeBrevo({ contact }).impl });
  await h.run(post({ body: agitDelivery([43, 4]) }), AGIT_ENV);
  const alert = lastAlert(h.calls);
  assert.equal(alert.subject, 'New newsletter subscriber: member@example.com');
  assert.match(alert.htmlContent, /AGIT welcome email: already sent \(skipped\)/);
  assert.equal(welcomeCalls(h.calls).length, 0);
});

test('an already-sent AGIT-only delivery is a list addition', async () => {
  const contact = MEMBER();
  contact.attributes.AGIT_WELCOME_SENT = '2026-10-15T01:00:00.000Z';
  const h = harness({ fetchImpl: fakeBrevo({ contact }).impl });
  await h.run(post({ body: agitDelivery([43]) }), AGIT_ENV);
  assert.equal(lastAlert(h.calls).subject, 'List addition: member@example.com');
});

test('alert reports a failed welcome and how to resend', async () => {
  const h = harness({ fetchImpl: fakeBrevo({ contact: MEMBER(), fail: { welcome: () => json(429, {}) } }).impl });
  await h.run(post({ body: agitDelivery() }), AGIT_ENV);
  const alert = lastAlert(h.calls);
  assert.equal(alert.subject, 'New AGIT member: member@example.com');
  assert.match(alert.htmlContent, /AGIT welcome email: FAILED \(welcome send 429\)/);
  assert.ok(alert.htmlContent.includes('Resend a welcome'), 'the FAILED line must name the resend procedure');
});

test('a newsletter-only alert is unchanged', async () => {
  // Golden: the subject and body today's handler sends for a [4] event, byte for byte.
  const golden = {
    sender: { name: 'hoiboy.uk', email: 'hello@hoiboy.uk' },
    to: [{ email: 'hoiboyuk@gmail.com' }],
    subject: 'New newsletter subscriber: reader@example.com',
    htmlContent:
      '<p>Someone confirmed their subscription to hoiboy.uk.</p>' +
      '<p><strong>reader@example.com</strong></p>' +
      '<p>List: 4</p>' +
      "<p>This fired on Brevo's listAddition event, which under double opt-in means " +
      'they clicked the confirmation link. They are a confirmed subscriber, not just ' +
      'someone who typed an address into the form.</p>',
  };
  // With every binding set, as production is. (Without AGIT_LIST_ID the alert gains
  // the NOT-sent line on purpose; that case is the missing-bindings test above.)
  const h = harness();
  await h.run(post({ body: LIST_ADDITION }), AGIT_ENV);
  assert.equal(h.calls.length, 1);
  assert.deepEqual(JSON.parse(h.calls[0].init.body), golden);
});

// ----------------------------------------------------------------------
// #65 AC 2.8: the workflow, form POST to welcome, in one harness run.
// ----------------------------------------------------------------------

test('agit signup to welcome, end to end in the harness', async () => {
  // 1. The AGIT form POST through the real subscribe.js, against a stubbed Brevo.
  const subscribePath = path.join(__dirname, '..', 'functions', 'api', 'subscribe.js');
  const subRaw = fs.readFileSync(subscribePath, 'utf8');
  const subCalls = [];
  const subCtx = vm.createContext({
    Response, Request, FormData, Headers, URL, Buffer,
    console: { log: () => {}, error: () => {} },
    fetch: async (url, init) => {
      subCalls.push({ url: String(url), init });
      if (String(url).includes('challenges.cloudflare.com')) return json(200, { success: true });
      return json(201, {});
    },
  });
  const sub = vm.runInContext(subRaw.replace(/^export\s+/gm, '') + '\n;({ onRequestPost })', subCtx, { filename: subscribePath });
  const form = new FormData();
  for (const [k, v] of Object.entries({
    audience: 'agit', name: 'Mem', email: 'member@example.com', member_consent: 'on',
    member_consent_version: '2026-10-15', consent_version: '2026-08-03', 'cf-turnstile-response': 't',
  })) form.append(k, v);
  const subEnv = { ...AGIT_ENV, TURNSTILE_SECRET_KEY: 'ts', BREVO_DOI_TEMPLATE_ID: '7', AGIT_DOI_TEMPLATE_ID: '27' };
  const subRes = await sub.onRequestPost({ request: new Request('https://hoiboy.uk/api/subscribe', { method: 'POST', body: form }), env: subEnv });
  assert.equal(subRes.status, 303);
  const doi = JSON.parse(subCalls.find((c) => c.url.endsWith('/contacts/doubleOptinConfirmation')).init.body);

  // 2. Brevo, on the confirm click, creates the contact the DOI call described and
  //    fires list_addition. The contact is built FROM the DOI payload, so a signup
  //    that stopped writing AGIT_CONSENT_VERSION would get no welcome here.
  const contact = { email: doi.email, listIds: doi.includeListIds, attributes: { ...doi.attributes } };
  const brevo = fakeBrevo({ contact });
  const h = harness({ fetchImpl: brevo.impl });
  await h.run(post({ body: agitDelivery(doi.includeListIds) }), AGIT_ENV);

  // 3. A second, later delivery for the same member (say they subscribe in the footer).
  await h.run(post({ body: agitDelivery([...doi.includeListIds, 4]) }), AGIT_ENV);

  const welcome = welcomeCalls(h.calls);
  assert.equal(welcome.length, 1, 'exactly one welcome across both deliveries');
  assert.deepEqual(JSON.parse(welcome[0].init.body).params, { INVITE_URL: INVITE_FIXTURE });
  const alerts = alertCalls(h.calls).map((c) => JSON.parse(c.init.body).htmlContent);
  assert.equal(alerts.length, 2);
  assert.match(alerts[0], /AGIT welcome email: sent/);
  assert.match(alerts[1], /AGIT welcome email: already sent \(skipped\)/);
});
