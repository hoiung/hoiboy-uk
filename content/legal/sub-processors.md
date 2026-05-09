---
title: Sub-processors
date: 2026-05-09
lastmod: 2026-05-09
description: TANTUNG LTD sub-processor list (AI Managed Harness Services) - vendor names, services, data categories, locations, transfer mechanisms, DPA references.
hideDate: true
version: 1.0.0
---

This page lists the sub-processors engaged by **TANTUNG LTD** (UK Companies House 10566169) for the AI Managed Harness Services consultancy. It mirrors the source-of-truth Annex 2 of the **Data Processing Agreement (DPA) Schedule** attached to the Master Services Agreement (MSA) and to each Statement of Work (SOW) signed under it.

When a sub-processor is added or replaced, affected clients are emailed the change with an effective-date at least 30 days out. Clients may object on reasonable grounds within those 30 days; an unresolved objection means the affected SOW may be terminated with pro-rata refund per SOW §5.

## Current sub-processors

| Vendor | Service | Categories of data processed | Location of processing | Transfer mechanism (UK to data location) | DPA link | Last-verified date |
|---|---|---|---|---|---|---|
| **Anthropic** (Anthropic, PBC) | Claude API for transcript review and 8-section summarisation | Operator-redacted transcripts, summarisation prompts | US (Anthropic primary) | DPF + UK Extension (verify at https://www.dataprivacyframework.gov/list at engagement start); SCCs + UK IDTA + TRA fallback | https://www.anthropic.com/legal/dpa | 2026-05-09 |
| **Google** (Google LLC / Google Ireland Limited via Google Workspace EU instance) | Google Meet recording + storage | Audio + video stream of recorded meetings (operator-controlled record toggle) | EU (Google Workspace EU region) | DPF + UK Extension; SCCs + UK IDTA fallback | https://workspace.google.com/terms/dpa_terms.html | 2026-05-09 |
| **Backblaze** (Backblaze, Inc.) | B2 encrypted cloud backup of per-client encrypted volume | Encrypted blobs (Restic chunk-encrypted; Backblaze sees ciphertext only) | US (Backblaze primary US datacentres) | DPF + UK Extension; SCCs + UK IDTA + TRA fallback | https://www.backblaze.com/company/data-processing-addendum.html | 2026-05-09 |
| **Whisper-local** (representational entry; OpenAI Whisper open-source model running on operator workstation) | Local audio-to-text transcription | Raw audio (decrypted in-memory only during transcription) | UK (operator workstation in UK) | N/A (no third-party transfer; on-device processing) | N/A (open-source model; no DPA needed) | 2026-05-09 |
| **Cloudflare** (Cloudflare, Inc.) | Email Routing for `hello@hoiboy.uk` inbound (consent / objection / erasure-request emails relating to recordings) | Inbound email metadata + body (transient routing only) | US (Cloudflare primary, global edge network) | DPF + UK Extension; SCCs + UK IDTA fallback | https://www.cloudflare.com/cloudflare-customer-dpa/ | 2026-05-09 |
| **Brevo** (Sendinblue SAS) | SMTP relay for outbound transactional emails (consent confirmations, erasure receipts, sub-processor change notifications) | Email metadata + body (transient relay; Brevo retains delivery logs per their DPA) | EU (Brevo France) | EU adequacy + UK adequacy (Brevo France-resident); no SCCs needed for UK to EU | https://www.brevo.com/legal/termsofuse/ (DPA section) | 2026-05-09 |

## Change-notification mechanism

When this page updates, affected Clients on active engagements receive an email to the engagement-letter signatory's email address with:

- The vendor change (added / replaced / removed).
- The effective-date (at least 30 days from the notification date per Article 28(2) general written authorisation flow).
- A summary of the operational impact (which artefact category is affected; which transfer mechanism applies).
- The Client's right to object on reasonable grounds within the 30-day window.
- The pro-rata refund right per SOW §5 if objection cannot be resolved.

## Cross-references

- **MSA §13** Data protection + meeting recording - cross-cutting framework.
- **SOW §7.7** Recording + AI-transcription anchor - controller-classification + activation gate + retention table.
- **DPA Schedule Annex 2** - source-of-truth canonical version of this list (per-engagement attached to each MSA + SOW).
- **[Privacy Notice](/legal/privacy/)** - data-subject-facing Privacy Notice for site visitors and engaged clients.

## Update cadence

This page is reviewed at:

- Engagement start (per-vendor DPF re-verification).
- Annual sub-processor list refresh (12-month cadence from previous refresh date).
- Ad-hoc on vendor delisting notice or material vendor change.

Last reviewed: 2026-05-09.
