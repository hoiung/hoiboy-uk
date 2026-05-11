---
title: "Meet recorder (operator-only)"
layout: single
noindex: true
hideDate: true
sitemap:
  disable: true
---

<noscript>This tool requires JavaScript and a Chromium browser. Open in Chrome / Edge / Brave.</noscript>

<div id="fail-loud-banner" hidden role="alert"></div>
<p id="background-throttle-warning" hidden role="alert">Tab is hidden — Chromium may throttle MediaRecorder. Keep this tab visible during recording.</p>

<section id="section-mode-toggle-top" aria-label="Recording mode">
  <fieldset>
    <legend>Recording mode</legend>
    <label><input type="radio" name="mode" id="mode-personal" value="personal" checked /> Personal recording for my own notes (default)</label>
    <label><input type="radio" name="mode" id="mode-compliance" value="compliance" /> Client session needing full compliance recording</label>
  </fieldset>
  <p id="banner-cal-com-never-recorded" role="note">Pre-engagement Cal.com discovery calls are NEVER recorded. Engagement-letter must be signed before recording.</p>
  <p id="banner-last-session" hidden role="note"></p>
</section>

<section id="section-inbox" aria-label="Inbox directory">
  <h2>1. Pick the encrypted-volume inbox directory</h2>
  <p>Browser writes <code>.webm</code> + <code>.meta.json</code> here. Directory MUST equal <code>${WHISPER_INBOX}</code> on the master so the systemd path-unit fires.</p>
  <label>WHISPER_INBOX leaf name (operator-typed, must match the picked dir):
    <input id="whisper-inbox-config" type="text" placeholder="whisper-inbox" />
  </label>
  <button id="btn-pick-inbox" type="button">Pick directory…</button>
  <p>Resolved: <code id="inbox-resolved">(none picked yet)</code></p>
  <p id="inbox-path-warning" hidden role="alert"></p>
</section>

<section id="section-engagement" aria-label="Engagement gate">
  <h2>2. Engagement-letter gate</h2>
  <p>Recorder reads <code>.engagements.json</code> at page load. Tick to attest the engagement letter is signed and Recording §3 = <code>enabled-and-attendees-notified</code> (or <code>mixed</code> with this session ticked enabled). See <a href="https://hoiboy.uk/legal/privacy/" rel="noopener">Privacy Notice</a>.</p>
  <label><input type="checkbox" id="attestation-engagement-letter-signed" /> I attest engagement letter is signed and Recording row §3 enables this session.</label>
  <p>Engagements registry source: <code>{fsa-dir}/.engagements.json</code> — see <a href="/js/meet-recorder.engagements.schema.json">engagements.json schema</a>. Operator hand-edits this file.</p>
</section>

<section id="section-runbook-checklist" aria-label="Pre-meeting runbook checklist">
  <h2>3. Pre-meeting checklist (10 items, T-5 min)</h2>
  <p>Source: <code>consulting-ops/runbooks/recording-pre-meeting-procedure.md</code> §(a). Any FAIL = recording OFF for this session OR session re-scoped to written-summary-only.</p>
  <ol>
    <li data-runbook-step="1"><label><input type="checkbox" id="runbook-step-1" /> Engagement-letter signed AND Recording row §3 = <code>enabled-and-attendees-notified</code> (or <code>mixed</code> with this session ticked enabled).</label></li>
    <li data-runbook-step="2"><label><input type="checkbox" id="runbook-step-2" /> Attendees identified — every name on the calendar invite + Client/third-party status confirmed + Article 13 / 14(3)(a) notification status known.</label></li>
    <li data-runbook-step="3"><label><input type="checkbox" id="runbook-step-3" /> Third-party joiner consent — Client warrants Article 14(3)(a) notification within 30 days; Privacy Notice link sent at invite time.</label></li>
    <li data-runbook-step="4"><label><input type="checkbox" id="runbook-step-4" /> Meeting purpose in invite explicitly states recording behaviour and links the public Privacy Notice.</label></li>
    <li data-runbook-step="5"><label><input type="checkbox" id="runbook-step-5" /> Calendar invite issued ≥24h ahead with recording-disclosure (else document rationale in permission-log).</label></li>
    <li data-runbook-step="6">
      <label><input type="checkbox" id="runbook-step-6" disabled /> Recording stack verified — 30-second mini-recording with audible playback PASSED.</label>
      <button id="runbook-step-6-mini-record" type="button">Run 30-sec test</button>
      <button id="runbook-step-6-playback-ok" type="button">Playback OK</button>
    </li>
    <li data-runbook-step="7"><label><input type="checkbox" id="runbook-step-7" /> Per-client encrypted volume mounted; raw artefact landing path verified writeable.</label></li>
    <li data-runbook-step="8"><label><input type="checkbox" id="runbook-step-8" /> Background-capture risk assessed — home-office / closed-door / directional mic; no bystanders within mic range.</label></li>
    <li data-runbook-step="9"><label><input type="checkbox" id="runbook-step-9" /> Verbal-script ready (3-sentence script + jurisdiction-specific addendum if any).</label></li>
    <li data-runbook-step="10"><label><input type="checkbox" id="runbook-step-10" /> ROPA entry pre-staged with date / purpose / attendees / consent-method / jurisdiction-screen-result / vulnerable-attendee-assessment-result / DPF-re-verification-result / recording-stack.</label></li>
  </ol>
</section>

<section id="section-verbal-consent" aria-label="Verbal-consent script">
  <h2>4. Verbal-consent script (read verbatim, ~30s, capture verbal yes ON the recording)</h2>
  <p data-verbal-consent-script>I'm starting the recording. This session is being recorded on video and audio and will be transcribed with the help of AI tools so I can review it accurately during the [PURPOSE] for [CLIENT]. The recording, transcript, and any AI-generated summary are stored encrypted on my workstation under TANTUNG LTD as data controller, retained per our engagement letter, and you can ask for them to be deleted at any time by emailing hello@hoiboy.uk — I'll confirm deletion in writing within one calendar month under UK GDPR Article 17. Is everyone here happy for me to continue recording? [PAUSE FOR VERBAL YES.]</p>
  <p>Tokens: <code>[PURPOSE]</code> = audit / foundation setup / per-harness build / SME interview / handover. <code>[CLIENT]</code> = Client legal name from engagement-letter.</p>
</section>

<section id="section-jurisdiction" aria-label="Jurisdiction screen">
  <h2>5. Jurisdiction screen</h2>
  <label>Per-attendee jurisdiction:
    <select name="jurisdiction" required>
      <option value="uk-only">UK-only attendees</option>
      <option value="cipa-state-with-addendum">US CIPA-state attendee — addendum read on record</option>
      <option value="bdsg-german-employee">German employee — BDSG works-council written-form confirmed</option>
      <option value="cnil-french-employee">French employee — CNIL one-off scope confirmed on record</option>
      <option value="unknown-jurisdiction-off">Unknown jurisdiction — RECORDING OFF</option>
    </select>
  </label>
</section>

<section id="section-vulnerable" aria-label="Vulnerable-attendee assessment">
  <h2>6. Vulnerable-attendee assessment</h2>
  <label>Outcome:
    <select name="vulnerable-assessment" required>
      <option value="clear">Clear — no concerns</option>
      <option value="language-barrier-interpreter-needed">Language barrier — interpreter needed</option>
      <option value="capacity-concern-recording-off">Capacity concern — RECORDING OFF / written-summary-only</option>
      <option value="coercion-pattern-flagged">Coercion pattern flagged — RECORDING OFF</option>
    </select>
  </label>
</section>

<section id="section-dpf" aria-label="DPF re-verification">
  <h2>7. DPF re-verification (engagement-start cadence)</h2>
  <button id="btn-dpf-recheck" type="button">Open DPF list (new tab)</button>
  <p>Per <code>recording-pre-meeting-procedure.md</code> §(f), re-verify each sub-processor's DPF + UK Extension status:</p>
  <ul>
    <li><label><input type="checkbox" name="subprocessor-anthropic" /> Anthropic — Active on dataprivacyframework.gov</label></li>
    <li><label><input type="checkbox" name="subprocessor-google" /> Google (Meet) — Active</label></li>
    <li><label><input type="checkbox" name="subprocessor-backblaze" /> Backblaze (B2 storage) — Active</label></li>
    <li><label><input type="checkbox" name="subprocessor-cloudflare" /> Cloudflare — Active</label></li>
    <li><label><input type="checkbox" name="subprocessor-brevo" /> Brevo — Active</label></li>
  </ul>
  <fieldset><legend>Overall DPF re-verification result:</legend>
    <label><input type="radio" name="dpf-status" value="all-active" checked /> All Active</label>
    <label><input type="radio" name="dpf-status" value="fallback-to-sccs" /> Fallback to SCCs + UK IDTA + TRA</label>
    <label><input type="radio" name="dpf-status" value="skipped" /> Skipped (document why in permission-log)</label>
  </fieldset>
</section>

<section id="section-lpp" aria-label="LPP decision-gate">
  <h2>8. LPP decision-gate</h2>
  <p>Source: <code>consulting-ops/runbooks/lpp-decision-gate.md</code>.</p>
  <label>Solicitor attendance:
    <select name="lpp-solicitor-attendance">
      <option value="no">No solicitor attending</option>
      <option value="yes-with-confirmation">Solicitor attending — non-waiver confirmation available</option>
      <option value="yes-without-confirmation">Solicitor attending — NO non-waiver confirmation (lpp-non-waiver / lpp-decision-gate)</option>
    </select>
  </label>
  <p id="lpp-non-waiver-upload" hidden>
    <label>Upload non-waiver confirmation (.pdf/.eml/.txt, ≤2MB):
      <input type="file" name="lpp-non-waiver-upload" accept=".pdf,.eml,.txt" />
    </label>
  </p>
</section>

<section id="section-attestations-art9" aria-label="Article 9 stack-config attestations">
  <h2>9. Article 9 stack-config attestations</h2>
  <label><input type="checkbox" name="attestation-claude-art9" /> I attest the Anthropic workspace setting is opted-out of training.</label>
  <label><input type="checkbox" name="attestation-meet-art9" /> I attest the Google Meet workspace settings have speaker-verification + face-recognition DISABLED.</label>
</section>

<section id="section-meta-fields" aria-label="Session metadata">
  <h2>10. Session metadata (written into <code>.meta.json</code> sidecar)</h2>
  <p>The four fields below are shared between personal and compliance modes. The compliance-only block below the separator appears only when compliance mode is selected.</p>

  <label>Engagement ID: <input id="engagement-id" type="text" list="engagement-id-history" placeholder="singerandsteel" /></label>
  <datalist id="engagement-id-history"></datalist>
  <label>Topic slug (≤25 lowercase a-z 0-9 -): <input id="field-topic-slug" type="text" maxlength="25" placeholder="audit-kickoff" /></label>
  <label>Google Meet URL: <input id="field-meet-url" type="url" placeholder="https://meet.google.com/abc-defg-hij" /></label>
  <label>Attendees (one name per line; <code>Name &lt;email&gt; (role)</code> also accepted for compliance mode):
    <textarea id="field-attendees" rows="4" placeholder="Sarah Mock&#10;Tom Steel"></textarea>
  </label>

  <div data-personal-hide="true" id="meta-fields-compliance-only">
    <hr />
    <p><strong>Compliance-only fields (visible in compliance mode):</strong></p>
    <label>Session ID (S\d{6}, source: <code>dpa/session-registry.md</code>): <input id="field-session-id" type="text" pattern="^S[0-9]{6}$" placeholder="S000001" /></label>
    <label>Client slug (≤15 lowercase a-z 0-9 -): <input id="field-client-slug" type="text" maxlength="15" placeholder="singerandsteel" /></label>
    <fieldset><legend>Consent method used:</legend>
      <label><input type="radio" name="consent-method" value="verbal-on-record-all-attendees" checked /> Verbal on-record (all attendees)</label>
      <label><input type="radio" name="consent-method" value="operator-self-recording (no attendee)" /> Operator-self-recording (no attendee)</label>
      <label><input type="radio" name="consent-method" value="consent-declined-recording-off" /> Consent declined — recording OFF</label>
    </fieldset>
  </div>
</section>

<section id="section-mode-toggles" aria-label="Mode toggles">
  <h2>11. Mode toggles</h2>
  <label><input type="checkbox" id="toggle-self-recording-mode" /> Operator-self-recording mode (no attendee — verbal-consent / jurisdiction / vulnerable / LPP screens hidden).</label>
  <label><input type="checkbox" id="toggle-notes-only" /> Notes-only mode (operator pastes notes — no recording, redaction + summarisation still fire on the master).</label>
</section>

<section id="section-notes" aria-label="Notes-only" hidden>
  <h2>12. Notes-only entry</h2>
  <textarea id="field-notes" rows="12" placeholder="Operator notes — pasted, will be AI-redacted and 5-section-summarised on the master."></textarea>
  <button id="btn-submit-notes" type="button">Submit notes</button>
</section>

<section id="section-recording-controls" aria-label="Recording controls">
  <h2>13. Recording controls</h2>
  <button id="btn-record" type="button" disabled>Start recording</button>
  <button id="btn-stop"   type="button" disabled>Stop</button>
  <button id="btn-pause"  type="button" disabled>Pause</button>
  <button id="btn-resume" type="button" disabled>Resume</button>
  <button id="btn-abort-delete" type="button">Abort + Delete (consent declined mid-call)</button>
  <p id="re-consent-prompt" hidden>
    New attendee joined — re-run the verbal-consent script for them, then tick:
    <label><input type="checkbox" id="mid-meeting-reconsent-confirmed" /> Mid-meeting attendee re-consent captured on record.</label>
  </p>
</section>

<script src="/js/meet-recorder.js" defer></script>
