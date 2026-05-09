---
title: Privacy Notice
date: 2026-05-09
lastmod: 2026-05-09
description: Privacy Notice for TANTUNG LTD covering site personal data and consultancy engagements (including meeting recordings and AI-transcription).
hideDate: true
version: 1.0.0
---

This Privacy Notice covers the processing of personal data by **TANTUNG LTD** (UK Companies House 10566169), trading as hoiboy.uk for the AI Managed Harness Services consultancy.

It satisfies the controller's obligations under **UK GDPR Article 13** (information to be provided where personal data are collected from the data subject) and **UK GDPR Article 14** (information to be provided where personal data have not been obtained from the data subject, including the **30-day clock** for notification under Article 14(3)(a)).

## 1. Who we are (controller identity)

- **Controller**: TANTUNG LTD (UK Companies House 10566169)
- **Registered office**: address recorded in the prevailing engagement-letter for engaged clients; available on request via `hello@hoiboy.uk` for general enquiries
- **Contact email**: `hello@hoiboy.uk`
- **Data Protection contact**: Senh Hoi Ung (sole director). Email `hello@hoiboy.uk` for all data-protection queries, subject-access requests, erasure requests, and Article 21 objections

TANTUNG LTD does not have a separate Data Protection Officer (DPO). The sole director is the Data Protection contact and is accountable for all data-protection responsibilities under UK GDPR.

## 2. What this notice covers

This notice covers two scopes:

### Site visitor data (general)

- Visitor analytics: aggregated, anonymised page-view counts via privacy-preserving analytics. No individual tracking, no cookies beyond strictly-necessary, no advertising trackers.
- Contact-form / email enquiries: when you email `hello@hoiboy.uk`, your email address and message content are processed for the purpose of responding to your enquiry.

### Consultancy engagement data (engaged clients only)

- Audio recordings, video frames, transcripts, and AI-summaries from recorded sessions during AI Managed Harness Services engagements.
- Operator notes and engagement metadata (timestamps, attendee lists, meeting purpose, engagement-reference codes).
- Time-logs, invoices, and VAT records for billing and statutory retention.

## 3. Recording + AI-transcription (consultancy-engagement scope)

This section applies ONLY to clients who have signed an engagement-letter with TANTUNG LTD. Pre-engagement informal calls (discovery, scoping, qualification, including the 20-minute Cal.com discovery call at `cal.eu/hoiboyuk/discovery`) are NEVER recorded. The engagement-letter signature is the activation gate.

### Purposes and lawful basis (Article 6(1)(f))

We record and AI-transcribe consultancy sessions to capture decisions, action items, and verbatim quotes faithfully. Specifically:

- Faithful capture of B2B-consultancy decisions and verbatim quotes so that engagement outputs (audit reports, architecture proposals, build handovers, monthly maintenance reports) are anchored to the actual conversation rather than operator-recall.
- AI-assisted review for completeness via the operator-side AI-review pipeline.
- Audit-trail for billing and scope disputes.

Our **lawful basis** is **Article 6(1)(f) Legitimate Interest**. The Legitimate Interest Assessment (LIA) for each engagement is filed before the first recording session commences. We do NOT rely on a consent tickbox as the lawful basis; you are notified of the recording behaviour (this notice + the engagement-letter §7 + the verbal-on-record script) and have a standalone Article 21 right to object.

For HMRC-retained financial artefacts (time-logs, invoices, VAT records), our lawful basis is **Article 6(1)(c) Legal Obligation** (HMRC 6+1 year retention via Article 17(3)(b) override; statutory bases: Companies Act 2006 s.388 + VAT Act 1994 s.21 + VAT Regulations 1995 reg.31 + Corporation Tax Act 2010 enquiry-window buffer).

### Categories of personal data processed

- Audio: voice recordings of meeting speech.
- Video: camera frames where camera is enabled.
- Transcripts: speech-to-text content.
- AI-summaries: structured derived output from the LLM-review pipeline.
- Operator notes and metadata.

We do NOT use voice biometric identification or face-recognition; speaker-verification and face-recognition features are explicitly disabled across the recording stack.

### Recipients of your personal data (sub-processors)

Recordings and transcripts pass through a sub-processor pipeline. The current vendor list, location of processing, transfer mechanism, and per-vendor DPA reference are documented at the **[Sub-Processors](/legal/sub-processors/)** page on this site.

When we add or replace a sub-processor, we email affected Clients the change with effective-date **at least 30 days out**. Clients (and, indirectly, data subjects acting through Clients) may object on reasonable grounds within those 30 days.

### Cross-border transfers and safeguards

Some sub-processors are located outside the United Kingdom. We rely on the following transfer mechanisms:

- **UK Extension to the EU-US Data Privacy Framework (DPF)** for US-resident vendors that are DPF-active (verified at https://www.dataprivacyframework.gov/list).
- **Standard Contractual Clauses (SCCs) + UK International Data Transfer Addendum (IDTA) + Transfer Risk Assessment (TRA)** as fallback where a vendor is not DPF-active or delists.
- **UK adequacy decision** for EU-resident vendors.

Supplementary measures include encryption at rest, encryption in transit, and operator-side PII redaction before transmission to AI-review sub-processors.

### Retention periods

| Artefact | Retention period |
|---|---|
| Raw audio + video recording | 30 days post-engagement-close OR 7 days post-transcript-verification, whichever is later |
| Transcript | 180 days post-engagement-close |
| Sanitised AI-summary | 6 years post-engagement-close (Limitation Act 1980 mirror) |
| Time-logs, invoices, VAT records (where personal data appears) | 6+1 years (HMRC statutory obligation; sanitise-and-retain) |

After the retention window, we destroy the per-engagement encryption key (NIST 800-88 Purge), rendering all artefacts encrypted with that key cryptographically inaccessible.

## 4. Site visitor data

### Visitor analytics

We use privacy-preserving analytics that aggregate page-view counts without setting cookies or tracking individuals. No personal data is collected via analytics.

### Contact-form / email enquiries

When you email `hello@hoiboy.uk`, your email address and message content are processed for the purpose of responding to your enquiry. Lawful basis: Article 6(1)(f) Legitimate Interest (responding to inbound enquiries is a routine business communication purpose). Retention: enquiry threads are retained for 12 months from last reply, then deleted unless you have entered a paid engagement (in which case the engagement scope below applies).

## 5. Your data-subject rights

Under UK GDPR, you have the following rights:

- **Article 15 right of access**: request a copy of the personal data we hold about you.
- **Article 16 right to rectification**: request correction of inaccurate personal data.
- **Article 17 right to erasure**: request deletion of your personal data. Where HMRC statutory retention applies (time-logs, invoices, VAT records), we sanitise-and-retain rather than fully delete; where it does not (recordings, transcripts, AI-summaries), we cryptographically erase.
- **Article 18 right to restriction**: request that we restrict processing while we resolve a rectification or erasure dispute.
- **Article 20 right to portability**: where applicable, request a copy of the data in a structured, commonly used, machine-readable format.
- **Article 21 right to object** (handled standalone, NOT collapsed into erasure): object at any time to the recording-related processing under our Article 6(1)(f) Legitimate Interest basis. We cease processing forward; existing recordings stay under Legitimate Interest unless you also invoke Article 17.

To exercise any of these rights, email `hello@hoiboy.uk` with your request. We respond within one calendar month.

## 6. Right to lodge a complaint with the ICO

You have the right to lodge a complaint with the **Information Commissioner's Office (ICO)** if you believe we have failed to meet our UK GDPR obligations.

- Website: https://ico.org.uk/make-a-complaint/
- Helpline: 0303 123 1113
- Address: Information Commissioner's Office, Wycliffe House, Water Lane, Wilmslow, Cheshire, SK9 5AF

We encourage you to email us at `hello@hoiboy.uk` first so we can attempt to resolve concerns directly, but you are not required to do so before lodging an ICO complaint.

## 7. Article 14 specific notice (where personal data have not been obtained from the data subject)

Where you (the data subject) are notified of this Privacy Notice indirectly, for example you are a third-party engineer invited by our Client to a recorded session and you are receiving this notice via the Client (not directly from us), UK GDPR Article 14 applies and we provide notice within the 30-day clock under Article 14(3)(a). The information in sections 1-6 above applies equally; the source of your personal data in this case is the Client who invited you to the recorded session.

## 8. Changes to this notice

We may update this notice over time (for example, when a sub-processor changes, or when retention windows are revised). Material changes are communicated to active engagements via the engagement-letter signatory's email address. The version-controlled history of this notice is reflected in the `lastmod` date at the top of this page.
