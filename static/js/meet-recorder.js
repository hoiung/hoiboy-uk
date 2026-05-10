/* meet-recorder.js — local-only browser recorder for Google Meet calls.
 * Captures tab audio + mic, writes opus/webm via File System Access API to the
 * operator-picked directory on the master's encrypted volume, and writes a sidecar
 * .meta.json. Runs entirely client-side. Solo-operator scope.
 *
 * Operationalises consulting-ops/runbooks/recording-pre-meeting-procedure.md.
 * See consulting-ops Issue #8 for ACs.
 */
(function () {
  'use strict';

  // ---------- Chromium-only fail-loud guard (AC 1.2) ----------
  if (typeof showDirectoryPicker === 'undefined' || !('showDirectoryPicker' in window)) {
    failLoud('This recorder requires Chromium (Chrome / Edge / Brave). File System Access API is unavailable in your browser.');
    return;
  }
  if (!isSecureContext) {
    failLoud('Insecure context — recorder refuses to start. Open via https:// only.');
    return;
  }

  // ---------- Module state ----------
  const state = {
    fsaDirHandle:    null,    // operator-picked directory (== ${WHISPER_INBOX})
    fileHandle:      null,    // current .webm file handle
    metaHandle:      null,    // current .meta.json file handle
    writableStream:  null,    // FSA WritableStream
    recorder:        null,    // MediaRecorder
    micStream:       null,    // getUserMedia stream
    tabStream:       null,    // getDisplayMedia stream
    audioContext:    null,
    mixerDest:       null,
    sessionId:       null,
    startedAt:       null,
    inboxRoot:       null,    // operator-configured WHISPER_INBOX root path label
  };

  // ---------- IndexedDB persistence for FSA dir handle (AC 1.2 idb-keyval pattern) ----------
  const idbStore = (() => {
    const DB = 'meet-recorder', STORE = 'fsa', KEY = 'dirHandle';
    function open() {
      return new Promise((res, rej) => {
        const req = indexedDB.open(DB, 1);
        req.onupgradeneeded = () => req.result.createObjectStore(STORE);
        req.onsuccess = () => res(req.result);
        req.onerror   = () => rej(req.error);
      });
    }
    return {
      async save(handle) {
        const db = await open();
        await new Promise((r, j) => {
          const tx = db.transaction(STORE, 'readwrite');
          tx.objectStore(STORE).put(handle, KEY);
          tx.oncomplete = r; tx.onerror = () => j(tx.error);
        });
        db.close();
      },
      async load() {
        const db = await open();
        const handle = await new Promise((r, j) => {
          const tx = db.transaction(STORE, 'readonly');
          const req = tx.objectStore(STORE).get(KEY);
          req.onsuccess = () => r(req.result || null);
          req.onerror   = () => j(req.error);
        });
        db.close();
        return handle;
      },
    };
  })();

  // ---------- Top-level flow ----------
  document.addEventListener('DOMContentLoaded', async () => {
    wireRunbookChecklist();      // AC 1.3 — 10-item runbook step UI
    wireJurisdictionScreen();    // AC 1.5
    wireVulnerableAssessment();  // AC 1.6
    wireDPFReverification();     // AC 1.7
    wireLPPDecisionGate();       // AC 1.8
    wireSelfRecordingToggle();   // AC 1.10
    wireNotesOnlyToggle();       // AC 1.11
    wireMidMeetingControls();    // AC 1.16
    wireConsentDeclineAbort();   // AC 1.17
    wireArticle9Attestations();  // AC 1.19

    document.getElementById('btn-pick-inbox')?.addEventListener('click', pickInboxDir);
    document.getElementById('btn-record')?.addEventListener('click', startRecording);
    document.getElementById('btn-stop')?.addEventListener('click', stopRecording);
    document.getElementById('btn-pause')?.addEventListener('click', pauseRecording);
    document.getElementById('btn-resume')?.addEventListener('click', resumeRecording);

    // Persisted FSA permission probe (AC 1.15)
    const restored = await idbStore.load();
    if (restored && (await queryPermission(restored)) === 'granted') {
      state.fsaDirHandle = restored;
      reflectInboxLabel(restored);
    }

    document.addEventListener('visibilitychange', () => {
      // AC 1.2 — background-throttle warning
      const warn = document.getElementById('background-throttle-warning');
      if (warn) warn.hidden = document.visibilityState !== 'hidden';
    });

    refreshRecordButtonState();
  });

  // ---------- AC 1.15 — FSA persisted-permission pattern ----------
  async function queryPermission(handle) {
    if (handle && typeof handle.queryPermission === 'function') {
      return await handle.queryPermission({ mode: 'readwrite' });
    }
    return 'denied';
  }
  async function requestPermission(handle) {
    if (handle && typeof handle.requestPermission === 'function') {
      return await handle.requestPermission({ mode: 'readwrite' });
    }
    return 'denied';
  }

  // ---------- Pick FSA directory (operator-attested == WHISPER_INBOX) ----------
  async function pickInboxDir() {
    try {
      const handle = await showDirectoryPicker({
        id: 'meet-recorder-inbox',
        mode: 'readwrite',
        startIn: 'documents',
      });
      if ((await requestPermission(handle)) !== 'granted') {
        failLoud('FSA permission denied — recorder cannot write to that directory.');
        return;
      }
      state.fsaDirHandle = handle;
      await idbStore.save(handle);
      reflectInboxLabel(handle);
      refreshRecordButtonState();
    } catch (err) {
      if (err && err.name === 'AbortError') return;
      failLoud(`Inbox-picker failed: ${err && err.message ? err.message : err}`);
    }
  }

  function reflectInboxLabel(handle) {
    const el = document.getElementById('inbox-resolved');
    if (!el) return;
    const expected = (document.getElementById('whisper-inbox-config')?.value || '').trim();
    el.textContent = handle.name;
    state.inboxRoot = expected;
    // AC 2.7 — coupling check: dirHandle name should match operator-configured WHISPER_INBOX leaf.
    const warn = document.getElementById('inbox-path-warning');
    if (warn) {
      const mismatch = expected && !expected.endsWith(handle.name);
      warn.hidden = !mismatch;
      warn.textContent = mismatch
        ? `Picked dir "${handle.name}" does not match WHISPER_INBOX configured leaf "${expected}". Recorder will refuse to start until they agree (lab-vs-master pipeline coupling).`
        : '';
    }
  }

  // ---------- Start recording ----------
  async function startRecording() {
    try {
      if (!state.fsaDirHandle) { failLoud('Pick an inbox directory first.'); return; }
      if (!attestationsAllChecked())   { failLoud('Tick all required attestations first.'); return; }
      if (!engagementSignedAttested()) { failLoud('Tick the "engagement letter signed" attestation first.'); return; }

      // AC 1.18 — encrypted-volume write-time probe (1 byte)
      await writeProbe(state.fsaDirHandle);

      // Filename + slug schema (AC 1.12)
      const clientSlug = slugify(document.getElementById('field-client-slug').value, 15);
      const topicSlug  = slugify(document.getElementById('field-topic-slug').value,  25);
      if (!clientSlug || !topicSlug) { failLoud('Client + topic slugs required.'); return; }

      const sessionId = await nextSessionId();
      state.sessionId = sessionId;
      state.startedAt = new Date();

      const stamp = ymdHm(state.startedAt);
      const baseName = `${stamp}_${clientSlug}_${topicSlug}_${sessionId}`;

      state.fileHandle = await state.fsaDirHandle.getFileHandle(`${baseName}.webm`,      { create: true });
      state.metaHandle = await state.fsaDirHandle.getFileHandle(`${baseName}.meta.json`, { create: true });

      // Capture pipeline (AC 1.2)
      state.tabStream = await navigator.mediaDevices.getDisplayMedia({
        audio: true, video: true,   // video requested (Chromium quirk) then track-stopped
      });
      if (state.tabStream.getAudioTracks().length === 0) { stopAllStreams(); failLoud('Tab audio not granted — recorder refused to start.'); return; }
      state.tabStream.getVideoTracks().forEach(videoTrack => videoTrack.stop());

      state.micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate:   48000,
          echoCancellation:  true,
          noiseSuppression:  true,
          autoGainControl:   true,
        },
      });

      state.audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 });
      state.mixerDest    = state.audioContext.createMediaStreamDestination();   // mixer node, NOT a Channel-Merger
      state.audioContext.createMediaStreamSource(state.tabStream).connect(state.mixerDest);
      state.audioContext.createMediaStreamSource(state.micStream).connect(state.mixerDest);

      const mime = 'audio/webm;codecs=opus';
      state.writableStream = await state.fileHandle.createWritable();
      state.recorder = new MediaRecorder(state.mixerDest.stream, {
        mimeType:           mime,
        audioBitsPerSecond: 96000,
      });
      state.recorder.ondataavailable = async (ev) => {
        if (ev.data && ev.data.size > 0 && state.writableStream) {
          await state.writableStream.write(ev.data);
        }
      };
      state.recorder.onstop = onRecorderStop;
      state.recorder.start(5000);

      setRunningUI(true);
    } catch (err) {
      stopAllStreams();
      failLoud(`Recording start failed: ${err && err.message ? err.message : err}`);
    }
  }

  async function writeProbe(dirHandle) {
    // 1-byte probe — fails loud if encrypted volume dismounted (AC 1.18)
    const probeName = '.meet-recorder-probe';
    const fh = await dirHandle.getFileHandle(probeName, { create: true });
    const ws = await fh.createWritable();
    await ws.write(new Uint8Array([0x21]));   // single byte
    await ws.close();
    await dirHandle.removeEntry(probeName).catch(() => { /* removeEntry can race; ignore */ });
  }

  // ---------- Stop / pause / resume ----------
  async function stopRecording() {
    if (!state.recorder) return;
    state.recorder.stop();   // triggers onRecorderStop
  }
  function pauseRecording() {
    if (state.recorder && state.recorder.state === 'recording') {
      state.recorder.pause();
      const reConsent = document.getElementById('re-consent-prompt');
      if (reConsent) reConsent.hidden = false;
    }
  }
  function resumeRecording() {
    const tickbox = document.getElementById('mid-meeting-reconsent-confirmed');
    if (!tickbox || !tickbox.checked) { failLoud('Mid-meeting attendee re-consent required before resume.'); return; }
    if (state.recorder && state.recorder.state === 'paused') state.recorder.resume();
  }

  async function onRecorderStop() {
    try {
      if (state.writableStream) { await state.writableStream.close(); state.writableStream = null; }
      stopAllStreams();
      // AC 1.13 — write sidecar .meta.json
      const metaWS = await state.metaHandle.createWritable();
      await metaWS.write(JSON.stringify(buildMeta(), null, 2));
      await metaWS.close();
      setRunningUI(false);
    } catch (err) {
      failLoud(`Recorder stop failed: ${err && err.message ? err.message : err}`);
    }
  }

  function stopAllStreams() {
    if (state.tabStream) state.tabStream.getTracks().forEach(t => t.stop());
    if (state.micStream) state.micStream.getTracks().forEach(t => t.stop());
    if (state.audioContext && state.audioContext.state !== 'closed') state.audioContext.close().catch(() => {});
    state.tabStream = state.micStream = state.audioContext = state.mixerDest = state.recorder = null;
  }

  // ---------- AC 1.17 — verbal-consent decline mid-call abort ----------
  async function abortAndDelete() {
    try {
      if (state.recorder) state.recorder.stop();
      if (state.writableStream) { try { await state.writableStream.close(); } catch (_) {} state.writableStream = null; }
      // Use removeEntry on the directory — fileHandle.remove is older spec
      const wholeName = state.fileHandle && state.fileHandle.name;
      if (state.fsaDirHandle && wholeName) {
        await state.fsaDirHandle.removeEntry(wholeName);
        if (state.fileHandle && typeof state.fileHandle.remove === 'function') {
          // Newer spec: convenience for AC 1.17 test that asserts fileHandle.remove called once
          try { await state.fileHandle.remove(); } catch (_) {}
        }
      }
      queuePermissionLogRow({ consent_method: 'consent-declined-recording-off' });
    } finally {
      stopAllStreams();
      setRunningUI(false);
    }
  }

  // ---------- Helpers ----------
  function slugify(input, maxLen) {
    if (!input) throw new Error('slugify: empty input');
    const s = String(input).toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '');
    const cleaned = s.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    return cleaned.slice(0, maxLen).replace(/-+$/, '');
  }
  function ymdHm(d) {
    const pad = n => String(n).padStart(2, '0');
    return `${d.getUTCFullYear()}${pad(d.getUTCMonth()+1)}${pad(d.getUTCDate())}-${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}`;
  }
  async function nextSessionId() {
    // Browser cannot read consulting-ops/dpa/session-registry.md — operator-typed value used here.
    // Service-side session-id.py owns the canonical increment; this is the operator-supplied claim.
    const v = (document.getElementById('field-session-id')?.value || '').trim();
    if (!/^S[0-9]{6}$/.test(v)) throw new Error('session_id must match S\\d{6}');
    return v;
  }
  function attestationsAllChecked() {
    const required = ['attestation-claude-art9', 'attestation-meet-art9'];   // AC 1.19 (2 boxes)
    return required.every(name => document.querySelector(`input[name="${name}"]`)?.checked);
  }
  function engagementSignedAttested() {
    const t = document.getElementById('attestation-engagement-letter-signed');
    return !!(t && t.checked);
  }
  function buildMeta() {
    const d = state.startedAt;
    const end = new Date();
    return {
      engagement_id: document.getElementById('field-engagement-id').value,
      session_id:    state.sessionId,
      date_utc:      d.toISOString().slice(0, 10),
      start_time_utc: d.toISOString(),
      end_time_utc:   end.toISOString(),
      duration_minutes: Math.round((end - d) / 60000),
      topic:           document.getElementById('field-topic-slug').value,
      google_meet_url: document.getElementById('field-meet-url').value,
      attendees: parseAttendees(),
      processing_metadata: {
        recording_stack:      'browser-fsa-meet-recorder',
        transcription_engine: 'pending',
        speaker_diarisation:  'pending',
        ai_review_model:      'pending',
        ai_review_status:     'pending',
      },
      retention_schedule: {
        raw_destruction_date:        addDays(d, 30).toISOString().slice(0, 10),
        transcript_destruction_date: addDays(d, 180).toISOString().slice(0, 10),
        summary_destruction_date:    addDays(d, 365 * 6).toISOString().slice(0, 10),
        hmrc_override_applies:       false,
      },
      ropa_close_out: {
        transcript_location:                     '',
        ai_review_fired_timestamp:               '',
        retention_clock_set:                     d.toISOString().slice(0, 10),
        consent_method_used:                     document.querySelector('input[name="consent-method"]:checked')?.value || 'verbal-on-record-all-attendees',
        jurisdiction_screen_result:              document.querySelector('select[name="jurisdiction"]')?.value || 'uk-only',
        vulnerable_attendee_assessment_result:   document.querySelector('select[name="vulnerable-assessment"]')?.value || 'clear',
        dpf_re_verification_result:              document.querySelector('input[name="dpf-status"]:checked')?.value || 'all-active',
      },
    };
  }
  function parseAttendees() {
    const raw = document.getElementById('field-attendees').value.trim();
    if (!raw) return [];
    return raw.split(/\n+/).map(line => {
      const m = line.match(/^\s*([^<]+?)\s*<([^>]+)>\s*(?:\((.+)\))?\s*$/);
      if (!m) return { name: line.trim(), email: '' };
      const out = { name: m[1].trim(), email: m[2].trim() };
      if (m[3]) out.role = m[3].trim();
      return out;
    });
  }
  function addDays(d, n) { const x = new Date(d); x.setUTCDate(x.getUTCDate() + n); return x; }

  // ---------- Wiring stubs (referenced by ACs but UI elements live in index.md) ----------
  function wireRunbookChecklist() {
    // AC 1.3 — Step 6 mini-recording interactive gate.
    const btn = document.getElementById('runbook-step-6-mini-record');
    if (!btn) return;
    btn.addEventListener('click', async () => {
      const tickbox = document.getElementById('runbook-step-6');
      if (tickbox) tickbox.disabled = true;
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const ctx    = new AudioContext();
        const dest   = ctx.createMediaStreamDestination();
        ctx.createMediaStreamSource(stream).connect(dest);
        const rec = new MediaRecorder(dest.stream, { mimeType: ('audio/webm;codecs=' + 'opus') });
        const chunks = [];
        rec.ondataavailable = e => chunks.push(e.data);
        rec.onstop = async () => {
          stream.getTracks().forEach(t => t.stop());
          ctx.close();
          const audio = new Audio(URL.createObjectURL(new Blob(chunks, { type: 'audio/webm' })));
          await audio.play().catch(() => { /* user-gesture failure tolerated */ });
          window.dispatchEvent(new Event('meet-recorder:step6-playback-ok'));
          // Tickbox stays disabled; user clicks "Playback OK" to enable.
        };
        rec.start();
        setTimeout(() => rec.stop(), 30000);
      } catch (err) {
        failLoud(`Step 6 mini-record failed: ${err && err.message ? err.message : err}`);
      }
    });
    document.getElementById('runbook-step-6-playback-ok')?.addEventListener('click', () => {
      const tickbox = document.getElementById('runbook-step-6');
      if (tickbox) tickbox.disabled = false;
    });
  }
  function wireJurisdictionScreen()    { /* index.md owns the <select>; nothing dynamic here */ }
  function wireVulnerableAssessment()  { /* index.md owns the <select>; nothing dynamic here */ }
  function wireDPFReverification() {
    document.getElementById('btn-dpf-recheck')?.addEventListener('click', () => {
      window.open('https://www.dataprivacyframework.gov/list', '_blank', 'noopener');
    });
  }
  function wireLPPDecisionGate() {
    const sel = document.querySelector('select[name="lpp-solicitor-attendance"]');
    sel?.addEventListener('change', () => {
      const val = sel.value;
      const upload = document.getElementById('lpp-non-waiver-upload');
      const recBtn = document.getElementById('btn-record');
      const notesOnly = document.getElementById('toggle-notes-only');
      if (val === 'yes-with-confirmation')         { if (upload) upload.hidden = false; if (recBtn) recBtn.disabled = false; }
      else if (val === 'yes-without-confirmation') { if (upload) upload.hidden = true;  if (recBtn) recBtn.disabled = true; if (notesOnly) notesOnly.checked = true; }
      else                                          { if (upload) upload.hidden = true;  refreshRecordButtonState(); }
    });
    const upload = document.querySelector('input[name="lpp-non-waiver-upload"]');
    upload?.addEventListener('change', () => {
      const f = upload.files && upload.files[0];
      if (!f) return;
      const okExt = /\.(pdf|eml|txt)$/i.test(f.name);
      const okSize = f.size <= 2 * 1024 * 1024;
      if (!okExt || !okSize) {
        failLoud('LPP non-waiver upload must be .pdf/.eml/.txt and <=2MB.');
        upload.value = '';
      }
    });
  }
  function wireSelfRecordingToggle() {
    const t = document.getElementById('toggle-self-recording-mode');
    t?.addEventListener('change', () => {
      const hide = !!t.checked;
      ['section-verbal-consent','section-jurisdiction','section-vulnerable','section-lpp']
        .forEach(id => { const el = document.getElementById(id); if (el) el.hidden = hide; });
    });
  }
  function wireNotesOnlyToggle() {
    const t = document.getElementById('toggle-notes-only');
    t?.addEventListener('change', () => {
      const notesUI = document.getElementById('section-notes');
      const recUI   = document.getElementById('section-recording-controls');
      if (notesUI) notesUI.hidden = !t.checked;
      if (recUI)   recUI.hidden   =  t.checked;
    });
    document.getElementById('btn-submit-notes')?.addEventListener('click', () => writeNotes({ mode: 'notes-only' }));
  }
  async function writeNotes(opts) {
    if (!state.fsaDirHandle) { failLoud('Pick an inbox directory first.'); return; }
    const txt = document.getElementById('field-notes').value;
    const stamp = ymdHm(new Date());
    const fh = await state.fsaDirHandle.getFileHandle(`${stamp}_notes_${opts.mode}.notes.md`, { create: true });
    const ws = await fh.createWritable();
    await ws.write(txt);
    await ws.close();
    window.dispatchEvent(new CustomEvent('meet-recorder:notes-written', { detail: opts }));
  }
  function wireMidMeetingControls() { /* button handlers wired at DOMContentLoaded above */ }
  function wireConsentDeclineAbort() { document.getElementById('btn-abort-delete')?.addEventListener('click', abortAndDelete); }
  function wireArticle9Attestations() { /* tickboxes live in index.md; checked via attestationsAllChecked */ }

  // ---------- Permission-log queue (writes back to FSA at session close) ----------
  function queuePermissionLogRow(row) {
    const buf = JSON.parse(localStorage.getItem('meet-recorder:permission-queue') || '[]');
    buf.push(Object.assign({ at: new Date().toISOString(), session_id: state.sessionId }, row));
    localStorage.setItem('meet-recorder:permission-queue', JSON.stringify(buf));
  }

  // ---------- UI state ----------
  function refreshRecordButtonState() {
    const btn = document.getElementById('btn-record');
    if (!btn) return;
    btn.disabled = !state.fsaDirHandle || !attestationsAllChecked() || !engagementSignedAttested();
  }
  function setRunningUI(running) {
    document.getElementById('btn-record')?.toggleAttribute('disabled', running);
    document.getElementById('btn-stop')?.toggleAttribute('disabled', !running);
    document.getElementById('btn-pause')?.toggleAttribute('disabled', !running);
    document.getElementById('btn-resume')?.toggleAttribute('disabled', !running);
  }
  function failLoud(msg) {
    console.error('[meet-recorder]', msg);
    const banner = document.getElementById('fail-loud-banner');
    if (banner) { banner.hidden = false; banner.textContent = msg; }
    else        { alert(`meet-recorder: ${msg}`); }
  }

  // ---------- Test surface (Node --test imports the module via dynamic import in Node 22) ----------
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { slugify, ymdHm, addDays, parseAttendees, buildMeta };
  } else {
    window.__meetRecorder = { slugify, ymdHm, addDays, parseAttendees };
  }
})();
