// agit-form.test.js -- node --test suite for the AGIT story minimum. hoiboy-uk#57.
//
// NOTHING HERE IS MIRRORED. The sibling suites (static/js/meet-recorder.test.js,
// tests/contribute.test.js) re-declare their subject's pure helpers locally and
// keep them in lock-step by code review, because those files export nothing.
// That is the exact failure class this issue removed: an implementation could
// ship `.value.length` while the mirror computed the normalised length, and
// every test would still pass green.
//
// So both halves below drive shipped code:
//   - the pure assertions `require` the real helper out of static/js/agit-form.js;
//   - the DOM assertions `eval` that same file inside jsdom, where the CommonJS
//     module wrapper is absent, so the browser path runs exactly as it ships.
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { JSDOM } = require('jsdom');

const SRC_PATH = path.join(__dirname, '..', 'static', 'js', 'agit-form.js');
const SRC = fs.readFileSync(SRC_PATH, 'utf8');
const { storyLength, STORY_MIN } = require('../static/js/agit-form.js');

// ----------------------------------------------------------------------
// The shipped helper, called directly (AC 1.0, AC 1.5)
// ----------------------------------------------------------------------

test('the real module exports its length helper, so these tests bind to shipped code', () => {
  assert.equal(typeof storyLength, 'function');
  assert.equal(STORY_MIN, 1200);
});

test('storyLength: a trailing newline is trimmed, so 1199 + Enter is still 1199', () => {
  // Shape B of the client/server agreement table. This is the discriminating
  // case: a member who types 1199 then presses Enter must be told to keep
  // writing rather than shown a green 1200 the server would then reject.
  assert.equal(storyLength('x'.repeat(1199) + '\n'), 1199);
});

test('storyLength: 1200 plain characters count as 1200', () => {
  assert.equal(storyLength('x'.repeat(1200)), 1200);
});

test('storyLength: interior control characters become one space each, never vanish', () => {
  // clean() REPLACES rather than strips, so an interior newline still occupies a
  // character. Were it stripped, the client would count lower than the server
  // and could block a story the server would have accepted.
  assert.equal(storyLength('a\nb'), 3);
  assert.equal(storyLength('a\tb\fc'), 5);
});

test('storyLength: empty and nullish inputs are zero, not a crash', () => {
  assert.equal(storyLength(''), 0);
  assert.equal(storyLength(null), 0);
  assert.equal(storyLength(undefined), 0);
  assert.equal(storyLength('   \n\t  '), 0);
});

test('storyLength: an astral emoji counts as its UTF-16 units, matching the server', () => {
  // Shape C. Both sides measure .length on a JS string, so both see 2 units for
  // one astral character. Agreement is what matters here, not the unit itself.
  assert.equal(storyLength('\u{1F600}'), 2);
});

// ----------------------------------------------------------------------
// The shipped browser path, under jsdom (AC 1.2, AC 1.4, AC 1.6)
// ----------------------------------------------------------------------

const PAGE = `<!doctype html><html><body>
  <div class="agit-form-wrap">
    <form method="POST" action="/api/contribute">
      <div class="agit-field"><input type="email" name="email" value="a@b.co"></div>
      <div class="agit-field"><input type="email" name="email_confirm" value="a@b.co"></div>
      <div class="agit-field">
        <textarea id="agit-feature" name="feature"></textarea>
        <p class="agit-count is-short" aria-live="polite">0</p>
      </div>
      <input type="hidden" name="cf-turnstile-response" value="turnstile-token">
      <div class="agit-field"><button type="submit">Send</button></div>
    </form>
  </div>
</body></html>`;

function mount(story) {
  const dom = new JSDOM(PAGE, { runScripts: 'outside-only' });
  const { window } = dom;
  const textarea = window.document.querySelector('[name="feature"]');
  if (story !== undefined) textarea.value = story;
  window.eval(SRC);
  return {
    window,
    textarea,
    form: window.document.querySelector('form'),
    counter: window.document.querySelector('.agit-count'),
    notice: () => window.document.querySelector('.agit-notice'),
  };
}

function submit(ctx) {
  // Dispatched directly rather than via requestSubmit(), which jsdom does not
  // implement. What matters is that OUR listener runs and gets to preventDefault.
  const ev = new ctx.window.Event('submit', { bubbles: true, cancelable: true });
  ctx.form.dispatchEvent(ev);
  return ev;
}

test('a 1199-character story is blocked, and the submit listener DID fire', () => {
  // The behavioural half of "minlength is not used". With minlength present
  // Chromium never fires this listener at all and renders its own two-number
  // message, so a firing listener plus our own worded notice is the proof that
  // the custom path is live rather than dead code behind native validation.
  const ctx = mount('x'.repeat(1199));
  const ev = submit(ctx);

  assert.equal(ev.defaultPrevented, true, 'a short story must not submit');
  const notice = ctx.notice();
  assert.ok(notice, 'the listener fired and rendered a notice element');
  assert.notEqual(notice.textContent.trim(), '', 'the notice must say something');
  assert.match(notice.textContent, /1200 characters/);
  assert.match(notice.textContent, /1199/, 'it tells them where they actually are');
});

test('1199 characters plus Enter is still blocked, not rounded up to 1200', () => {
  const ctx = mount('x'.repeat(1199) + '\n');
  const ev = submit(ctx);
  assert.equal(ev.defaultPrevented, true);
  assert.match(ctx.notice().textContent, /1199/);
});

test('a 1200-character story passes the length gate', () => {
  const ctx = mount('x'.repeat(1200));
  const ev = submit(ctx);
  assert.equal(ev.defaultPrevented, false, 'a long-enough story must proceed');
  assert.equal(ctx.notice(), null, 'nothing to complain about');
});

test('the length check runs BEFORE the Turnstile check', () => {
  // AC 1.6 ordering, asserted by behaviour rather than by source position:
  // with BOTH a short story and a missing token, the member must be told about
  // the story. Nobody should solve a CAPTCHA for a submission that cannot
  // succeed anyway.
  const ctx = mount('x'.repeat(10));
  ctx.window.document.querySelector('[name="cf-turnstile-response"]').value = '';
  submit(ctx);
  const text = ctx.notice().textContent;
  assert.match(text, /1200 characters/);
  assert.doesNotMatch(text, /verification/, 'the CAPTCHA nudge must not win this race');
});

test('the email-match check still runs BEFORE the length check', () => {
  // The guard was inserted between two existing checks; this pins the upper
  // edge so a later reorder cannot silently demote the email typo warning.
  const ctx = mount('x'.repeat(10));
  ctx.window.document.querySelector('[name="email_confirm"]').value = 'typo@b.co';
  submit(ctx);
  assert.match(ctx.notice().textContent, /email addresses do not match/);
});

test('the counter updates on input, change and paste, one number each time', () => {
  // Bound to the three events rather than to keypresses: paste, autofill,
  // drag-dropped text and undo all change the value without a keystroke.
  for (const eventName of ['input', 'change', 'paste']) {
    const ctx = mount('');
    assert.equal(ctx.counter.textContent, '0', `${eventName}: starts at zero`);

    ctx.textarea.value = 'y'.repeat(412);
    ctx.textarea.dispatchEvent(new ctx.window.Event(eventName, { bubbles: true }));

    assert.equal(ctx.counter.textContent, '412', `${eventName} must update the counter`);
  }
});

test('the counter is one bare number, never a fraction', () => {
  // The operator ruled out "412 / 1200" explicitly: it reads as an exact target
  // rather than a floor. The rendered text must be digits and nothing else.
  const ctx = mount('');
  ctx.textarea.value = 'z'.repeat(613);
  ctx.textarea.dispatchEvent(new ctx.window.Event('input', { bubbles: true }));
  assert.match(ctx.counter.textContent, /^\d+$/);
  assert.doesNotMatch(ctx.counter.textContent, /\//);
  assert.doesNotMatch(ctx.counter.textContent, /1200/);
});

test('the counter flips its state class at the minimum, not before', () => {
  const ctx = mount('');
  const setTo = (n) => {
    ctx.textarea.value = 'q'.repeat(n);
    ctx.textarea.dispatchEvent(new ctx.window.Event('input', { bubbles: true }));
  };

  setTo(1199);
  assert.ok(ctx.counter.classList.contains('is-short'), '1199 is short');
  assert.ok(!ctx.counter.classList.contains('is-met'), '1199 is not met');

  setTo(1200);
  assert.ok(ctx.counter.classList.contains('is-met'), '1200 is met');
  assert.ok(!ctx.counter.classList.contains('is-short'), '1200 is no longer short');

  setTo(900);
  assert.ok(ctx.counter.classList.contains('is-short'), 'deleting text goes back to short');
});

test('the counter reflects text already in the field on load', () => {
  // Back-navigation restores the textarea value without firing any event, so a
  // counter that only listens would sit at a stale server-rendered 0.
  const ctx = mount('w'.repeat(1500));
  assert.equal(ctx.counter.textContent, '1500');
  assert.ok(ctx.counter.classList.contains('is-met'));
});

test('the counter counts the way the submit gate does, on the same value', () => {
  // The counter and the gate must never disagree: showing green and then
  // blocking is the specific failure this pairing exists to prevent.
  const ctx = mount('');
  ctx.textarea.value = 'x'.repeat(1200) + '\n';
  ctx.textarea.dispatchEvent(new ctx.window.Event('input', { bubbles: true }));

  assert.equal(ctx.counter.textContent, '1200');
  assert.ok(ctx.counter.classList.contains('is-met'), 'the counter says green');
  assert.equal(submit(ctx).defaultPrevented, false, 'so the submit must go through');
});
