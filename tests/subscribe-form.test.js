// subscribe-form.test.js -- node --test suite for the newsletter form's
// progressive-enhancement layer. hoiboy-uk#56 Stage 5.
//
// Both halves drive SHIPPED code, the arrangement tests/agit-form.test.js
// settled on and for the reason recorded there: a hand-mirrored copy lets the
// real thing and the tested thing drift apart while every test stays green.
//   - the pure assertions `require` the real helper out of the shipped file;
//   - the DOM assertions `eval` that same file inside jsdom, where the CommonJS
//     module wrapper is absent, so the browser path runs exactly as it ships.
//
// The MARKUP is lifted from layouts/_partials/subscribe-form.html rather than
// retyped, with Hugo's template expressions stripped. Same lesson: a retyped
// fixture would keep passing after the real form changed shape underneath it.
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { JSDOM, VirtualConsole } = require('jsdom');

const SRC_PATH = path.join(__dirname, '..', 'static', 'js', 'subscribe-form.js');
const SRC = fs.readFileSync(SRC_PATH, 'utf8');
const { messageFor, CHECK_INBOX_PATH } = require('../static/js/subscribe-form.js');

const PARTIAL_PATH = path.join(
  __dirname, '..', 'layouts', '_partials', 'subscribe-form.html',
);

// The shipped form markup, template expressions removed. Hugo comment blocks
// (`{{- /* ... */ -}}`) go first, because they contain prose that the general
// expression pattern would otherwise chew through.
const FORM_MARKUP = (() => {
  const raw = fs.readFileSync(PARTIAL_PATH, 'utf8');
  // Anchored on the closing </form></div> PAIR, not on the first </div>: the
  // form is full of nested field divs, so a lazy match to any </div> stops
  // inside the first one and drops the whole form.
  const block = raw.match(/<div class="subscribe-form">[\s\S]*?<\/form>\s*<\/div>/);
  assert.ok(block, 'the subscribe-form block was not found in the shipped partial');
  const html = block[0]
    .replace(/\{\{-?\s*\/\*[\s\S]*?\*\/\s*-?\}\}/g, '')
    .replace(/\{\{-?[\s\S]*?-?\}\}/g, 'TEST-VALUE');
  assert.ok(
    html.includes('<form') && html.includes('button type="submit"'),
    'the lifted markup lost its form or submit button; the strip is too greedy',
  );
  return html;
})();

function pageHtml({ withWidget }) {
  // Turnstile injects cf-turnstile-response itself, so the REAL form ships
  // without it. Absent is therefore the honest default and is exactly the state
  // a reader is in before the async widget resolves.
  const widgetInput = withWidget
    ? '<input type="hidden" name="cf-turnstile-response" value="turnstile-token">'
    : '';
  // INSIDE the form, which is where the real widget injects it. Appended after
  // the markup instead, it is in the document but not in the form, so
  // form.querySelector never sees it and every token-present test silently
  // exercises the token-absent path.
  const html = FORM_MARKUP.replace('</form>', `${widgetInput}</form>`);
  return `<!doctype html><html><body>${html}</body></html>`;
}

function mount({ withWidget = true, fetchImpl } = {}) {
  // NAVIGATION, and exactly what these tests can and cannot prove about it.
  // jsdom implements no navigation and reports the attempt on its virtual
  // console. `window.location` is non-configurable at BOTH the window and the
  // location level, so `assign` cannot be stubbed and the destination URL is not
  // recoverable -- the reported message carries no URL.
  //
  // So these count navigation ATTEMPTS, which is the direction that matters:
  // every failure path must produce ZERO. A success producing exactly one, with
  // no notice and the form still locked, is the strongest honest statement
  // available here. The destination itself is covered where it IS observable --
  // functions/api/subscribe.js redirects to CHECK_INBOX_PATH and
  // tests/subscribe.test.js asserts that 303 end to end.
  const navigations = [];
  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', (err) => {
    if (/navigation/i.test(err.message)) navigations.push(err.message);
  });

  const dom = new JSDOM(pageHtml({ withWidget }), {
    runScripts: 'outside-only',
    url: 'https://hoiboy.uk/some-post/',
    virtualConsole,
  });
  const { window } = dom;

  // The recorder WRAPS whatever implementation the test supplies, rather than
  // being part of the default one. Recording only in the default made `calls`
  // silently empty for every test that passed its own fetchImpl -- so the
  // in-flight test asserted "exactly one POST" against a counter nothing wrote
  // to, and would have passed just as well had the script fired ten.
  const calls = [];
  const respond = fetchImpl || function () {
    return Promise.resolve({
      ok: true, redirected: true, url: 'https://hoiboy.uk/newsletter/check-inbox/',
    });
  };
  window.fetch = function (url, init) {
    calls.push({ url, init });
    return respond(url, init);
  };

  const resets = [];
  window.turnstile = { reset: () => resets.push(true) };

  window.eval(SRC);

  const form = window.document.querySelector('.subscribe-form form');
  assert.ok(form, 'the lifted markup produced no form for the script to bind to');
  form.action = '/api/subscribe';

  return {
    window, form, calls, navigations, resets,
    button: () => form.querySelector('button[type="submit"]'),
    notice: () => form.querySelector('.subscribe-notice'),
  };
}

function submit(ctx) {
  // Dispatched directly rather than via requestSubmit(), which jsdom does not
  // implement. What matters is that OUR listener runs and can preventDefault.
  const ev = new ctx.window.Event('submit', { bubbles: true, cancelable: true });
  ctx.form.dispatchEvent(ev);
  return ev;
}

const settle = () => new Promise((r) => setTimeout(r, 0));

// ----------------------------------------------------------------------
// The shipped helper, called directly
// ----------------------------------------------------------------------

test('the real module exports its message helper, so these tests bind to shipped code', () => {
  assert.equal(typeof messageFor, 'function');
  assert.equal(CHECK_INBOX_PATH, '/newsletter/check-inbox/');
});

test('messageFor: a 403 names the verification check rather than blaming the reader', () => {
  // The status a reader gets for submitting before the async Turnstile widget
  // resolved. "You look like a bot" would be both wrong and unactionable.
  assert.match(messageFor(403), /verification check/i);
});

test('messageFor: every failure status yields actionable text, never an empty string', () => {
  for (const status of [400, 403, 413, 429, 500, 502, 503, 418]) {
    const msg = messageFor(status);
    assert.equal(typeof msg, 'string');
    assert.ok(msg.length > 20, `status ${status} produced a uselessly short message`);
  }
});

test('messageFor: a rate limit asks for later, it does not invite an immediate retry', () => {
  // Brevo's send cap is account-wide, so "try again" here would invite the retry
  // storm functions/api/subscribe.js turns a 429 into a 503 to avoid.
  assert.match(messageFor(429), /few minutes/i);
  assert.match(messageFor(503), /few minutes/i);
});

// ----------------------------------------------------------------------
// The shipped browser path, under jsdom
// ----------------------------------------------------------------------

test('markup: the lifted fixture is the real form, honeypot and consent included', () => {
  // Guards the strip above. If it ever over-matches, the DOM tests below would
  // silently be exercising a stub.
  assert.ok(FORM_MARKUP.includes('name="email"'), 'no email field');
  assert.ok(FORM_MARKUP.includes('name="website"'), 'no honeypot');
  assert.ok(FORM_MARKUP.includes('name="consent_version"'), 'no consent version');
});

test('no Turnstile token yet: the submit is held and the reader is told why', async () => {
  // The reachable case. The loader is `async defer`, so a reader who fills two
  // short fields fast submits before the widget resolves. Before this layer that
  // was a server 403 rendered as bare text/plain, with their typing gone.
  const ctx = mount({ withWidget: false });
  const ev = submit(ctx);
  await settle();

  assert.equal(ev.defaultPrevented, true, 'the native POST must not go out');
  assert.equal(ctx.calls.length, 0, 'nothing should reach the server');
  assert.match(ctx.notice().textContent, /verification check/i);
  assert.equal(ctx.window.document.location.pathname, '/some-post/', 'still on the page');
});

test('success: one POST, then the page navigates away and stays locked', async () => {
  const ctx = mount();
  submit(ctx);
  await settle();

  assert.equal(ctx.calls.length, 1, 'exactly one POST');
  assert.equal(ctx.calls[0].init.method, 'POST');
  assert.equal(ctx.navigations.length, 1, 'success must navigate exactly once');
  assert.equal(ctx.notice(), null, 'a success must not report an error');
  // Still locked on purpose: the browser is leaving, and re-enabling the button
  // would offer a second submit during the hand-off.
  assert.equal(ctx.button().disabled, true);
});

test('failure: the reader keeps what they typed and is told what happened', async () => {
  // The whole point of this layer. Previously a 502 replaced the page with bare
  // text/plain: no navigation, no back link, name and email gone.
  const ctx = mount({
    fetchImpl: () => Promise.resolve({ ok: false, redirected: false, status: 502 }),
  });
  ctx.form.querySelector('[name="name"]').value = 'Ada';
  ctx.form.querySelector('[name="email"]').value = 'ada@example.com';

  submit(ctx);
  await settle();

  assert.equal(ctx.navigations.length, 0, 'a failure must not navigate away');
  assert.equal(ctx.form.querySelector('[name="name"]').value, 'Ada');
  assert.equal(ctx.form.querySelector('[name="email"]').value, 'ada@example.com');
  assert.match(ctx.notice().textContent, /went wrong/i);
});

test('failure: the button and the Turnstile token are both made usable again', async () => {
  // A Turnstile token is SINGLE USE. Without the reset, a second attempt re-sends
  // a spent token and earns another 403 -- the first failure would trap the
  // reader in a loop no amount of retrying escapes.
  const ctx = mount({
    fetchImpl: () => Promise.resolve({ ok: false, redirected: false, status: 502 }),
  });
  submit(ctx);
  await settle();

  assert.equal(ctx.button().disabled, false, 'the button must be clickable again');
  assert.equal(ctx.resets.length, 1, 'the spent Turnstile token must be reset');
  assert.equal(ctx.form.hasAttribute('aria-busy'), false);
});

test('network failure: an unreachable server is reported, not swallowed', async () => {
  const ctx = mount({ fetchImpl: () => Promise.reject(new Error('offline')) });
  submit(ctx);
  await settle();

  assert.match(ctx.notice().textContent, /could not reach/i);
  assert.equal(ctx.button().disabled, false);
});

test('a second submit while one is in flight is dropped', async () => {
  let resolve;
  const ctx = mount({ fetchImpl: () => new Promise((r) => { resolve = r; }) });

  submit(ctx);
  submit(ctx);
  await settle();
  assert.equal(ctx.calls.length, 1, 'double-click must not fire two subscribes');

  resolve({ ok: true, redirected: true, url: 'https://hoiboy.uk/newsletter/check-inbox/' });
  await settle();
});

test('no fetch: the script stands aside so the plain form still works', async () => {
  // Progressive, not required. Where fetch is missing the native POST must go
  // out untouched -- a half-enhanced form that swallowed the submit would be
  // worse than the bare error page this layer replaces.
  const dom = new JSDOM(pageHtml({ withWidget: true }), {
    runScripts: 'outside-only', url: 'https://hoiboy.uk/some-post/',
  });
  dom.window.fetch = undefined;
  dom.window.eval(SRC);

  const form = dom.window.document.querySelector('.subscribe-form form');
  const ev = new dom.window.Event('submit', { bubbles: true, cancelable: true });
  form.dispatchEvent(ev);

  assert.equal(ev.defaultPrevented, false, 'the native submit must proceed');
});

test('the notice is announced, and clears rather than leaving a stale error', async () => {
  const ctx = mount({
    fetchImpl: () => Promise.resolve({ ok: false, redirected: false, status: 500 }),
  });
  submit(ctx);
  await settle();
  assert.equal(ctx.notice().getAttribute('role'), 'alert');

  // A retry must not show the previous failure while the new one is in flight.
  ctx.window.fetch = () => new Promise(() => {});
  submit(ctx);
  assert.equal(ctx.notice().textContent, '', 'the stale error should be cleared');
});
