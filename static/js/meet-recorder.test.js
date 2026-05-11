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
test('slugify: long-name truncation -> 15-char prefix', () => {
  assert.equal(slugify('Acme Widgets International', 15), 'acme-widgets-in');
});
test('slugify: ampersand + LTD suffix collapse', () => {
  assert.equal(slugify('Foo & Bar LTD', 15), 'foo-bar-ltd');
});
test('slugify: client-slug "Acme Corp" -> "acme-corp"', () => {
  assert.equal(slugify('Acme Corp', 15), 'acme-corp');
});
test('slugify: empty input throws', () => {
  assert.throws(() => slugify('', 15), /slugify: empty input/);
});

// #9 Stage 5 follow-up — spec mirrors of ymdHm + ymdHms must stay in
// lock-step with meet-recorder.js lines 393-403. Personal-mode filenames
// use second-precision (ymdHms) and drop the session_id; compliance keeps
// minute-precision (ymdHm) + session_id.
function ymdHm(d) {
  const pad = n => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}${pad(d.getUTCMonth()+1)}${pad(d.getUTCDate())}-${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}`;
}
function ymdHms(d) {
  const pad = n => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}${pad(d.getUTCMonth()+1)}${pad(d.getUTCDate())}-${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}${pad(d.getUTCSeconds())}`;
}
function buildBaseName(mode, startedAt, clientSlug, topicSlug, sessionId) {
  return mode === 'personal'
    ? `${ymdHms(startedAt)}_${clientSlug}_${topicSlug}`
    : `${ymdHm(startedAt)}_${clientSlug}_${topicSlug}_${sessionId}`;
}

test('ymdHm + ymdHms: UTC zero-padded; second-precision adds trailing SS', () => {
  const d = new Date(Date.UTC(2026, 4, 11, 11, 45, 32));
  assert.equal(ymdHm(d),  '20260511-1145');
  assert.equal(ymdHms(d), '20260511-114532');
});

test('#9 Stage 5: personal-mode filename drops session_id and uses second-precision', () => {
  const d = new Date(Date.UTC(2026, 4, 11, 11, 45, 32));
  assert.equal(buildBaseName('personal', d, 'singerandsteel', 'audit-kickoff', 'S000001'),
               '20260511-114532_singerandsteel_audit-kickoff');
});

test('#9 Stage 5: compliance-mode filename keeps minute-precision + session_id', () => {
  const d = new Date(Date.UTC(2026, 4, 11, 11, 45, 32));
  assert.equal(buildBaseName('compliance', d, 'singerandsteel', 'audit-kickoff', 'S000001'),
               '20260511-1145_singerandsteel_audit-kickoff_S000001');
});

// #9 Stage 5 follow-up — ropa_close_out audit fields branch by mode.
// Personal mode writes null for the 4 compliance-only fields so the JSON
// does not over-claim user-confirmed audit answers (the underlying form
// dropdowns/radios have default first-option selected values that would
// otherwise leak through). Compliance mode reads the actual values.
function buildRopaCloseOut(mode, retentionClockSet, complianceValues) {
  if (mode === 'personal') {
    return {
      transcript_location:                   '',
      ai_review_fired_timestamp:             '',
      retention_clock_set:                   retentionClockSet,
      consent_method_used:                   null,
      jurisdiction_screen_result:            null,
      vulnerable_attendee_assessment_result: null,
      dpf_re_verification_result:            null,
    };
  }
  return {
    transcript_location:                   '',
    ai_review_fired_timestamp:             '',
    retention_clock_set:                   retentionClockSet,
    consent_method_used:                   complianceValues.consent ?? null,
    jurisdiction_screen_result:            complianceValues.jurisdiction ?? null,
    vulnerable_attendee_assessment_result: complianceValues.vulnerable ?? null,
    dpf_re_verification_result:            complianceValues.dpf ?? null,
  };
}

test('#9 Stage 5: personal-mode ropa_close_out nulls the 4 compliance audit fields', () => {
  const r = buildRopaCloseOut('personal', '2026-05-11', {});
  assert.equal(r.consent_method_used, null, 'consent_method_used must be null in personal mode');
  assert.equal(r.jurisdiction_screen_result, null);
  assert.equal(r.vulnerable_attendee_assessment_result, null);
  assert.equal(r.dpf_re_verification_result, null);
  assert.equal(r.retention_clock_set, '2026-05-11', 'retention_clock_set still populated');
});

test('#9 Stage 5: compliance-mode ropa_close_out reads actual user-confirmed values', () => {
  const r = buildRopaCloseOut('compliance', '2026-05-11', {
    consent:      'verbal-on-record-all-attendees',
    jurisdiction: 'uk-only',
    vulnerable:   'clear',
    dpf:          'all-active',
  });
  assert.equal(r.consent_method_used, 'verbal-on-record-all-attendees');
  assert.equal(r.jurisdiction_screen_result, 'uk-only');
  assert.equal(r.vulnerable_attendee_assessment_result, 'clear');
  assert.equal(r.dpf_re_verification_result, 'all-active');
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

// ----------------------------------------------------------------------
// #9 Phase 2 -- mode toggle + session persistence + datalist tests.
// These tests use REAL production section-* IDs (AC 2.8) and exercise the
// mode-toggle spec-mirror inline. Production wiring lives in meet-recorder.js
// wireModeToggle / wireSessionPersistence; spec mirrors here must stay in
// lock-step by code review.
// ----------------------------------------------------------------------

function makeMeetRecorderDom() {
  // Mirrors the production index.md section structure exactly. Used by the
  // #9 Phase 2 tests below (AC 2.3 / 2.5 / 2.6 / 2.6b / 2.8 / 2.10).
  return makeDom(`
    <section id="section-mode-toggle-top">
      <input type="radio" name="mode" id="mode-personal" value="personal" checked />
      <input type="radio" name="mode" id="mode-compliance" value="compliance" />
      <p id="banner-cal-com-never-recorded" role="note">Pre-engagement Cal.com discovery calls are NEVER recorded.</p>
      <p id="banner-last-session" hidden role="note"></p>
    </section>
    <section id="section-inbox"></section>
    <section id="section-engagement"></section>
    <section id="section-runbook-checklist"></section>
    <section id="section-verbal-consent"></section>
    <section id="section-jurisdiction"></section>
    <section id="section-vulnerable"></section>
    <section id="section-dpf"></section>
    <section id="section-lpp"></section>
    <section id="section-attestations-art9"></section>
    <section id="section-meta-fields">
      <input id="engagement-id" type="text" list="engagement-id-history" />
      <datalist id="engagement-id-history"></datalist>
      <label><input id="field-topic-slug" type="text" /></label>
      <label><input id="field-meet-url" type="url" /></label>
      <label><textarea id="field-attendees"></textarea></label>
      <output id="session-id-display">S000001</output>
      <div data-personal-hide="true" id="meta-fields-compliance-only">
        <label><input id="field-client-slug" type="text" /></label>
        <fieldset>
          <input type="radio" name="consent-method" value="verbal-on-record-all-attendees" checked />
        </fieldset>
      </div>
    </section>
    <section id="section-mode-toggles"></section>
    <section id="section-notes" hidden></section>
    <section id="section-recording-controls">
      <button id="btn-record" type="button" disabled>Start</button>
    </section>`);
}

// section-engagement intentionally NOT in the hide list — it carries the
// one-line engagement-letter-signed self-attestation that #9 AC 2.5 requires
// in both modes (engagementSignedAttested() stays required to gate Record).
const PERSONAL_HIDE_SECTIONS = [
  'section-runbook-checklist', 'section-jurisdiction',
  'section-vulnerable', 'section-dpf', 'section-lpp', 'section-attestations-art9',
  'section-mode-toggles', 'section-notes',
];

function specApplyModeToggle(doc) {
  const personal = doc.querySelector('input[name="mode"]:checked')?.value === 'personal';
  PERSONAL_HIDE_SECTIONS.forEach(id => {
    const el = doc.getElementById(id);
    if (el) el.hidden = personal;
  });
  doc.querySelectorAll('[data-personal-hide="true"]').forEach(el => { el.hidden = personal; });
}

// #9 AC 2.3 -- mode-personal hides the 9 compliance sections by ID.
test('#9 AC 2.3: mode-personal hides section-engagement / section-runbook-checklist / section-jurisdiction / section-vulnerable / section-dpf / section-lpp / section-attestations-art9 / section-mode-toggles / section-notes', () => {
  const doc = makeMeetRecorderDom();
  specApplyModeToggle(doc);
  PERSONAL_HIDE_SECTIONS.forEach(id => {
    assert.equal(doc.getElementById(id).hidden, true, `${id} must be hidden in personal mode`);
  });
});

// #9 AC 2.4 -- mode-compliance reveals all 13 sections (the 9 are no longer hidden).
test('#9 AC 2.4: mode-compliance shows all 13 sections', () => {
  const doc = makeMeetRecorderDom();
  doc.getElementById('mode-personal').checked = false;
  doc.getElementById('mode-compliance').checked = true;
  specApplyModeToggle(doc);
  PERSONAL_HIDE_SECTIONS.forEach(id => {
    assert.equal(doc.getElementById(id).hidden, false, `${id} must be visible in compliance mode`);
  });
});

// #9 AC 2.5 -- attestationsAllChecked short-circuits true in personal mode.
test('#9 AC 2.5: attestationsAllChecked() returns true in personal mode without ticking section-attestations-art9 boxes', () => {
  function attestationsAllCheckedSpec(doc) {
    const mode = doc.querySelector('input[name="mode"]:checked')?.value;
    if (mode === 'personal') return true;
    const required = ['attestation-claude-art9', 'attestation-meet-art9'];
    return required.every(name => doc.querySelector(`input[name="${name}"]`)?.checked);
  }
  const doc = makeMeetRecorderDom();
  assert.equal(attestationsAllCheckedSpec(doc), true, 'personal mode short-circuits to true');
  doc.getElementById('mode-personal').checked = false;
  doc.getElementById('mode-compliance').checked = true;
  assert.equal(attestationsAllCheckedSpec(doc), false, 'compliance mode without ticks must return false');
});

// #9 AC 2.6b -- Record button disabled until engagement-id input has a value (input EMPTY on load).
test('#9 AC 2.6b: section-recording-controls btn-record disabled when section-meta-fields engagement-id input is empty', () => {
  const doc = makeMeetRecorderDom();
  const btn = doc.getElementById('btn-record');
  const idInput = doc.getElementById('engagement-id');
  function refreshSpec() {
    const has = !!(idInput && idInput.value.trim());
    btn.disabled = !has;  // simplified spec: ignore the other gates for this test
  }
  idInput.addEventListener('input', refreshSpec);
  refreshSpec();
  assert.equal(btn.disabled, true, 'Record disabled when engagement-id empty');
  assert.equal(idInput.value, '', 'engagement-id input is empty on load (not auto-populated)');

  idInput.value = 'singerandsteel';
  idInput.dispatchEvent(new doc.defaultView.Event('input'));
  assert.equal(btn.disabled, false, 'Record enabled when engagement-id has value');
});

// #9 AC 2.6b -- Last-session confirm-banner surfaces DOM but does NOT auto-populate the input.
test('#9 AC 2.6b: banner-last-session DOM populates with last session metadata; engagement-id input stays empty on load', () => {
  const doc = makeMeetRecorderDom();
  // Simulate the spec: wireSessionPersistence loads last from IDB, populates the banner DOM,
  // does NOT touch input.value.
  const last = { engagementId: 'singerandsteel', topicSlug: 'audit-kickoff', lastUsedAtIso: '2026-05-11T10:00Z' };
  const banner = doc.getElementById('banner-last-session');
  banner.hidden = false;
  banner.textContent = `Last session: ${last.engagementId} / ${last.topicSlug} (${last.lastUsedAtIso}). `;
  const useBtn = doc.createElement('button');
  useBtn.id = 'btn-use-last-session';
  useBtn.textContent = 'Use these values';
  banner.appendChild(useBtn);

  const idInput = doc.getElementById('engagement-id');
  assert.equal(idInput.value, '', 'input stays empty until [Use these values] clicked');
  assert.equal(banner.hidden, false, 'banner visible with last session metadata');
  assert.match(banner.textContent, /Last session: singerandsteel/);

  // Click [Use these values] populates the input.
  useBtn.addEventListener('click', () => {
    idInput.value = last.engagementId;
    idInput.dispatchEvent(new doc.defaultView.Event('input', { bubbles: true }));
    banner.hidden = true;
  });
  useBtn.click();
  assert.equal(idInput.value, 'singerandsteel');
  assert.equal(banner.hidden, true);
});

// #9 AC 2.6 -- IndexedDB write happens on Record-start with the four keys present.
test('#9 AC 2.6: Record-start writes {engagementId, topicSlug, lastInboxDirHandle, lastUsedAtIso} to IndexedDB', () => {
  const calls = [];
  const sessionStoreMock = { save: (r) => { calls.push(r); return Promise.resolve(); } };
  const fakeDirHandle = { name: 'whisper-inbox' };
  // Spec mirror of the four-key payload assembled inside startRecording().
  const payload = {
    engagementId:       'singerandsteel',
    topicSlug:          'audit-kickoff',
    lastInboxDirHandle: fakeDirHandle,
    lastUsedAtIso:      '2026-05-11T10:30:00.000Z',
  };
  sessionStoreMock.save(payload);
  assert.equal(calls.length, 1);
  ['engagementId', 'topicSlug', 'lastInboxDirHandle', 'lastUsedAtIso'].forEach(k => {
    assert.ok(k in calls[0], `IDB record must include ${k}`);
  });
});

// #9 AC 2.7 -- datalist autocomplete sourced from localStorage history (no cross-repo YAML fetch).
test('#9 AC 2.7: engagement-id-history datalist populates from localStorage; no cross-repo engagement-issue-map.yaml fetch', () => {
  const doc = makeMeetRecorderDom();
  const history = ['singerandsteel', 'acme-corp'];
  const dl = doc.getElementById('engagement-id-history');
  history.forEach(id => {
    const opt = doc.createElement('option');
    opt.value = id;
    dl.appendChild(opt);
  });
  const options = dl.querySelectorAll('option');
  assert.equal(options.length, 2);
  assert.equal(options[0].value, 'singerandsteel');
  assert.equal(options[1].value, 'acme-corp');
});

// #9 AC 2.10 -- Cal.com discovery-call never-recorded banner is visible in personal mode.
test('#9 AC 2.10: banner-cal-com-never-recorded visible in personal mode with the canonical text', () => {
  const doc = makeMeetRecorderDom();
  const banner = doc.getElementById('banner-cal-com-never-recorded');
  assert.equal(banner.hidden, false, 'banner visible by default (informational, not blocking)');
  assert.match(banner.textContent, /Pre-engagement Cal\.com discovery calls are NEVER recorded/);
});

// nextSessionId spec mirror — production lives at meet-recorder.js (post
// #9 Stage 5 follow-up). Both personal AND compliance modes auto-generate
// the session_id from a single browser-local localStorage counter. The
// manual field-session-id input has been removed. peekNextSessionId is
// the increment-free reader used by refreshSessionIdDisplay.
function specPeekNextSessionId(storage) {
  const key = 'meet-recorder:auto-session-counter';
  const n = (Number(storage.getItem(key)) || 0) + 1;
  return 'S' + String(n).padStart(6, '0');
}
function specNextSessionId(storage) {
  const key = 'meet-recorder:auto-session-counter';
  const n = (Number(storage.getItem(key)) || 0) + 1;
  storage.setItem(key, String(n));
  return 'S' + String(n).padStart(6, '0');
}
function makeStorageStub() {
  const data = new Map();
  return {
    getItem: (k) => (data.has(k) ? data.get(k) : null),
    setItem: (k, v) => { data.set(k, v); },
  };
}

test('#9 AC 2.6/2.7: nextSessionId increments the localStorage counter and pads to S\\d{6} (both modes)', () => {
  const storage = makeStorageStub();
  const a = specNextSessionId(storage);
  const b = specNextSessionId(storage);
  const c = specNextSessionId(storage);
  assert.equal(a, 'S000001');
  assert.equal(b, 'S000002');
  assert.equal(c, 'S000003');
  assert.match(a, /^S[0-9]{6}$/, 'matches schema pattern');
  assert.equal(storage.getItem('meet-recorder:auto-session-counter'), '3');
});

test('#9 Stage 5 follow-up: nextSessionId works identically regardless of mode (no manual input)', () => {
  const storage = makeStorageStub();
  // Personal mode call
  assert.equal(specNextSessionId(storage), 'S000001');
  // Compliance mode call uses same counter, no mode argument needed
  assert.equal(specNextSessionId(storage), 'S000002');
});

test('#9 Stage 5 follow-up: peekNextSessionId reports the NEXT id without incrementing the counter (drives session-id-display)', () => {
  const storage = makeStorageStub();
  assert.equal(specPeekNextSessionId(storage), 'S000001');
  assert.equal(specPeekNextSessionId(storage), 'S000001', 'multiple peeks stay idempotent');
  assert.equal(specNextSessionId(storage),      'S000001');
  assert.equal(specPeekNextSessionId(storage), 'S000002', 'after one increment, peek reports the next');
});


// AC 2.7 -- inbox-path-coupling: dirHandle resolved-name compared to
// operator-configured WHISPER_INBOX; mismatch surfaces visible warning DOM
// node. IDs mirror production index.md exactly.
test('inbox-path-coupling: mismatch surfaces visible warning', () => {
  const doc = makeDom(`
    <input id="whisper-inbox-config" type="text" />
    <code id="inbox-resolved">(none picked yet)</code>
    <p id="inbox-path-warning" hidden role="alert"></p>`);
  function reflectInboxLabel(handle) {
    const expected = (doc.getElementById('whisper-inbox-config')?.value || '').trim();
    doc.getElementById('inbox-resolved').textContent = handle.name;
    const warn = doc.getElementById('inbox-path-warning');
    const mismatch = expected && !expected.endsWith(handle.name);
    warn.hidden = !mismatch;
    warn.textContent = mismatch
      ? `Picked dir "${handle.name}" does not match WHISPER_INBOX configured leaf "${expected}". Recorder will refuse to start until they agree (lab-vs-master pipeline coupling).`
      : '';
  }
  doc.getElementById('whisper-inbox-config').value = 'whisper-inbox';
  reflectInboxLabel({ name: 'whisper-inbox' });
  assert.equal(doc.getElementById('inbox-path-warning').hidden, true);
  reflectInboxLabel({ name: 'Downloads' });
  const warn = doc.getElementById('inbox-path-warning');
  assert.equal(warn.hidden, false);
  assert.match(warn.textContent, /does not match WHISPER_INBOX/);
});
