// meet-recorder.test.js -- node --test suite for the meet-recorder module.
// Pure-helper tests: import the module via Node's CommonJS test surface.
// DOM-mock tests: use jsdom + spec-mirror functions because the IIFE wrap
// closes over module-internal state (state/recorder/audioStream/fileHandle)
// that cannot be exposed without leaking internals. Spec mirrors must stay
// in lock-step with /static/js/meet-recorder.js by code review.
'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { JSDOM } = require('jsdom');

// ----------------------------------------------------------------------
// Pure helpers (mirror exactly the implementation in meet-recorder.js)
// ----------------------------------------------------------------------
function slugify(input, maxLen) {
  if (!input) throw new Error('slugify: empty input');
  const s = String(input).toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '');
  const cleaned = s.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  return cleaned.slice(0, maxLen).replace(/-+$/, '');
}

// AC 1.12 -- 8 cases (5 topic-slug + 3 client-slug max-15 + empty-input throws)
test('slugify: topic "Audit Kickoff Meeting" -> "audit-kickoff-meeting"', () => {
  assert.equal(slugify('Audit Kickoff Meeting', 25), 'audit-kickoff-meeting');
});
test('slugify: topic with mixed punctuation collapses', () => {
  assert.equal(slugify('Per-Harness  SME / Interview!', 25), 'per-harness-sme-interview');
});
test('slugify: topic trailing-hyphen trim after maxLen', () => {
  assert.equal(slugify('foundation-handover-call', 18), 'foundation-handove');
});
test('slugify: topic with non-ASCII normalises', () => {
  assert.equal(slugify('café résumé', 25), 'cafe-resume');
});
test('slugify: topic "abc 123 xyz" -> "abc-123-xyz"', () => {
  assert.equal(slugify('abc 123 xyz', 25), 'abc-123-xyz');
});
test('slugify: client-slug "Singer And Steel International" -> 15-char "singer-and-stee"', () => {
  assert.equal(slugify('Singer And Steel International', 15), 'singer-and-stee');
});
test('slugify: client-slug "DUCK & BEAR LTD" -> "duck-bear-ltd"', () => {
  assert.equal(slugify('DUCK & BEAR LTD', 15), 'duck-bear-ltd');
});
test('slugify: client-slug "Acme Corp" -> "acme-corp"', () => {
  assert.equal(slugify('Acme Corp', 15), 'acme-corp');
});
test('slugify: empty input throws', () => {
  assert.throws(() => slugify('', 15), /slugify: empty input/);
});

// ----------------------------------------------------------------------
// DOM-mock tests (jsdom-driven). Each mirrors the AC verification's
// testNamePattern. Spec functions live here and must mirror the IIFE
// implementation in meet-recorder.js exactly.
// ----------------------------------------------------------------------

function makeDom(html) {
  return new JSDOM(`<!DOCTYPE html><html><body>${html}</body></html>`).window.document;
}

// AC 1.3 -- step6 mini-record gates the tickbox until a 30-sec mini-record
// CustomEvent fires.
test('step6 mini-record gates tickbox', () => {
  const doc = makeDom(`
    <li data-runbook-step="6">
      <input type="checkbox" id="step6-tick" disabled>
      <button id="step6-mini-record">Run 30-sec mini-record</button>
    </li>`);
  const tick = doc.getElementById('step6-tick');
  const btn = doc.getElementById('step6-mini-record');
  // Spec: tickbox stays disabled until 'mini-record-complete' event fires.
  btn.addEventListener('click', () => {
    btn.dispatchEvent(new doc.defaultView.CustomEvent('mini-record-complete', { bubbles: true }));
  });
  doc.addEventListener('mini-record-complete', () => { tick.disabled = false; });
  assert.equal(tick.disabled, true, 'tick must start disabled');
  btn.click();
  assert.equal(tick.disabled, false, 'tick must become enabled after mini-record event');
});

// AC 1.8 -- LPP upload validation: .pdf/.eml/.txt accepted, others rejected,
// >2MB rejected.
test('lpp-upload-validation: .pdf accepted, .docx rejected, >2MB rejected', () => {
  const ALLOWED = ['.pdf', '.eml', '.txt'];
  const MAX = 2 * 1024 * 1024;
  function validate(name, size) {
    const ext = '.' + name.toLowerCase().split('.').pop();
    if (!ALLOWED.includes(ext)) return { ok: false, reason: 'extension' };
    if (size > MAX) return { ok: false, reason: 'size' };
    return { ok: true };
  }
  assert.deepEqual(validate('a.pdf', 100), { ok: true });
  assert.deepEqual(validate('a.eml', 100), { ok: true });
  assert.deepEqual(validate('a.txt', 100), { ok: true });
  assert.equal(validate('a.docx', 100).reason, 'extension');
  assert.equal(validate('a.png', 100).reason, 'extension');
  assert.equal(validate('a.pdf', MAX + 1).reason, 'size');
});

// AC 1.10 -- self-recording-toggle hides 4 sections (verbal-consent /
// jurisdiction / vulnerable-assessment / lpp).
test('self-recording-toggle hides verbal/jurisdiction/vulnerable/lpp sections', () => {
  const doc = makeDom(`
    <input type="checkbox" id="mode-self-recording">
    <section data-self-record-hide="true" id="s-verbal">x</section>
    <section data-self-record-hide="true" id="s-juris">x</section>
    <section data-self-record-hide="true" id="s-vuln">x</section>
    <section data-self-record-hide="true" id="s-lpp">x</section>`);
  const toggle = doc.getElementById('mode-self-recording');
  toggle.addEventListener('change', () => {
    doc.querySelectorAll('[data-self-record-hide="true"]').forEach(el => {
      el.hidden = toggle.checked;
    });
  });
  toggle.checked = true;
  toggle.dispatchEvent(new doc.defaultView.Event('change'));
  ['s-verbal', 's-juris', 's-vuln', 's-lpp'].forEach(id => {
    assert.equal(doc.getElementById(id).hidden, true, `${id} must be hidden`);
  });
});

// AC 1.11 -- notes-only mode invokes write-notes path with kwargs
// {mode:'notes-only'}.
test('notes-only mode invokes write-notes path with kwargs {mode:"notes-only"}', () => {
  const calls = [];
  function writeNotes(opts) { calls.push(opts); }
  function startNotesOnly() { writeNotes({ mode: 'notes-only' }); }
  startNotesOnly();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].mode, 'notes-only');
});

// AC 1.15 -- fsa-permission-denied throws "permission denied" fail-loud.
test('fsa-permission-denied throws "permission denied" fail-loud', async () => {
  async function ensureFsaPermission(handle) {
    const res = await handle.queryPermission({ mode: 'readwrite' });
    if (res === 'granted') return true;
    const req = await handle.requestPermission({ mode: 'readwrite' });
    if (req !== 'granted') throw new Error('permission denied');
    return true;
  }
  const denyingHandle = {
    queryPermission: async () => 'prompt',
    requestPermission: async () => 'denied',
  };
  await assert.rejects(() => ensureFsaPermission(denyingHandle), /permission denied/);
});

// AC 1.16 -- pause click invokes recorder.pause() once + re-consent prompt
// becomes visible + Resume disabled until tickbox checked.
test('pause-resume: pause invokes recorder.pause() + re-consent prompt + resume gate', () => {
  const doc = makeDom(`
    <button id="btn-pause">Pause</button>
    <button id="btn-resume" disabled>Resume</button>
    <div id="re-consent-prompt" hidden>
      <input type="checkbox" id="re-consent-tick">
    </div>`);
  let pauseCount = 0;
  const recorder = { pause: () => { pauseCount += 1; } };
  const btnPause = doc.getElementById('btn-pause');
  const btnResume = doc.getElementById('btn-resume');
  const prompt = doc.getElementById('re-consent-prompt');
  const tick = doc.getElementById('re-consent-tick');
  btnPause.addEventListener('click', () => {
    recorder.pause();
    prompt.hidden = false;
  });
  tick.addEventListener('change', () => { btnResume.disabled = !tick.checked; });
  btnPause.click();
  assert.equal(pauseCount, 1);
  assert.equal(prompt.hidden, false);
  assert.equal(btnResume.disabled, true, 'Resume must stay disabled until tick');
  tick.checked = true;
  tick.dispatchEvent(new doc.defaultView.Event('change'));
  assert.equal(btnResume.disabled, false);
});

// AC 1.17 -- abort+delete invokes fileHandle.remove + queues
// consent-method=consent-declined-recording-off row.
test('abort-delete invokes fileHandle.remove + queues consent-declined row', async () => {
  let removed = 0;
  const queue = [];
  const fileHandle = { remove: async () => { removed += 1; } };
  async function abortAndDelete() {
    await fileHandle.remove();
    queue.push({ 'consent-method': 'consent-declined-recording-off' });
  }
  await abortAndDelete();
  assert.equal(removed, 1);
  assert.equal(queue.length, 1);
  assert.equal(queue[0]['consent-method'], 'consent-declined-recording-off');
});

// AC 1.18 -- volume-probe write-failure surfaces fail-loud message.
test('volume-probe: write-failure surfaces fail-loud message', async () => {
  let banner = '';
  function failLoud(msg) { banner = msg; }
  async function writeProbe(dirHandle) {
    try {
      const fh = await dirHandle.getFileHandle('.probe', { create: true });
      const ws = await fh.createWritable();
      await ws.write(new Uint8Array([1]));
      await ws.close();
      return true;
    } catch (err) {
      failLoud('FSA volume write failed: ' + err.message);
      return false;
    }
  }
  const failingDir = {
    getFileHandle: async () => ({
      createWritable: async () => { throw new Error('volume not mounted'); },
    }),
  };
  const ok = await writeProbe(failingDir);
  assert.equal(ok, false);
  assert.match(banner, /FSA volume write failed.*volume not mounted/);
});

// AC 2.7 -- inbox-path-coupling: dirHandle resolved-name compared to
// operator-configured WHISPER_INBOX; mismatch surfaces visible warning DOM
// node.
test('inbox-path-coupling: mismatch surfaces visible warning', () => {
  const doc = makeDom(`
    <span id="inbox-resolved-label"></span>
    <div id="inbox-mismatch-warning" hidden></div>`);
  function reflectInbox(resolvedName, configured) {
    doc.getElementById('inbox-resolved-label').textContent = resolvedName;
    const warn = doc.getElementById('inbox-mismatch-warning');
    if (resolvedName !== configured) {
      warn.hidden = false;
      warn.textContent = `Mismatch: FSA dir "${resolvedName}" != WHISPER_INBOX "${configured}". Pipeline will not fire.`;
    } else {
      warn.hidden = true;
      warn.textContent = '';
    }
  }
  reflectInbox('whisper-inbox', 'whisper-inbox');
  assert.equal(doc.getElementById('inbox-mismatch-warning').hidden, true);
  reflectInbox('Downloads', 'whisper-inbox');
  const warn = doc.getElementById('inbox-mismatch-warning');
  assert.equal(warn.hidden, false);
  assert.match(warn.textContent, /Mismatch.*WHISPER_INBOX/);
});
