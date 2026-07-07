---
title: "I Built My Own Automated Meeting Notes. Three Attempts."
date: 2026-05-12T12:00:00+01:00
draft: false
categories: [tech-ai]
tags: [meeting-notes, transcription, self-hosted, whisper, automation, over-engineering]
description: "Bypassed the £9-40/month meeting-notes SaaS market entirely. Ended up with £0/month transcription that bills against the Claude plan I already pay for."
---

<!-- iamhoi -->

I handwrite notes during every client meeting. The notes are detailed enough to drive the work afterwards. This post is not about replacing them.

I wanted a transcript alongside, as a sanity check against my own notes. So I built my own. Two reasons.

First, I didn't want another £9-40/month SaaS subscription forever for what's basically Whisper plus a summariser, both open-source and free. Second, I wanted to test how accurate self-hosted transcription has actually got in 2026. Plenty of marketing copy out there. Not much "I ran a real meeting through this and here's what came out the other side".

Could a one-person operation, on the main computer I use for work, put together something that does what the SaaS does? And would the transcript be accurate enough to actually use?

Turned out: yes. Took three attempts.

## The SaaS-fatigue setup

Google Meet add-ons. Many of them. The free ones either crashed before they even started, didn't install properly, or got stuck in a login loop. The free tiers that did work were capped. Two recordings a month. For a feature I'd run on every client call. Useless. The paid tiers were £9-40 a month. Forever.

(Some of these tools are genuinely good. The teams who build them are doing real work. But £9-40/month forever for what is, fundamentally, a transcription pipeline plus a summariser? Maths doesn't add.)

For larger organisations the SaaS makes sense. Running your own transcript tools doesn't scale economically: the cost of designing, building, and maintaining them versus the value they bring. £9-40/month is just a drop in the ocean for them. Tool adoption is also a problem for non-techies. I don't have that barrier.

## Attempt 1: Claude Code overengineered when I asked for simple

I asked for a simple feature: record a Google Meet, transcribe it, turn it into a digital note I could compare against my handwritten ones. What came back was airport security.

Recording someone's voice has legal exposure if you're doing it for the wrong reasons in the wrong jurisdiction, so the harness researched all of it and built all of it. UK GDPR. Lawful-basis decision-making. Article 9 special-category if anyone mentions health. Article 30 records of processing. DPIAs. LIAs.

12 operator runbooks. 4 contract templates with ~2,600 words of recording clauses. A 33-row solicitor sign-off queue. A jurisdiction-selector screen. A vulnerable-attendee assessment. An LPP (legal professional privilege) decision gate.

Click-count to start recording: 28. Twenty-eight clicks. To press record.

~30,000 tokens of compliance machinery for a meeting-notes app. The GitHub Issue body hit the 65,000-character limit halfway through and the audit trail had to migrate into a comment. That was the moment to stop and ask if the scope was right. It wasn't asked.

## The realisation

Overengineered. It built a barrier to actual use. No paying clients yet, no regulated engagements, no contract disputes pending. The actual use case is a transcript as cross-check on my handwritten notes after the call. Not legal evidence. Not damages-grade.

When you build for the use case in front of you, you do simple things. When you build for the use case you might one day have, you build airport security.

Refactor.

## The cut-back

- Contracts: 7,354 words -> under 300. Recording sections now read "I might record this for note-taking accuracy. Ask me not to and I won't."
- UI: 13 gating sections -> 4 visible fields. Clicks-to-Record: 28 -> 3.
- 8 runbooks prefixed `DORMANT - activate only for regulated-industry client`. Not deleted. Hidden. The scaffolding stays in the repo, one mode-flip away if a regulated client ever lands.

The pattern worth pulling out: "don't delete, just hide". Building simple today doesn't mean throwing away scaffolding you wrote imagining a more complex future. Put the complex bits behind a flag that defaults off. The [SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness) rhythm enforces this naturally: scope to the use case in front of you, mark the rest dormant.

## Attempt 2: built it but never ran it

The cut-back landed. Pipeline code written. Tests green. Merged. Job done.

Except no one had actually run it end-to-end on the machine it was supposed to run on.

Python dependencies never `pip install`ed. The systemd EnvironmentFile had `%h/whisper-inbox` as a literal string because systemd specifiers don't expand inside env-file content (only in directive values). The systemd path-unit was a confirmed dead end on WSL2 because Windows-side filesystem changes don't propagate inotify events through the 9p layer to Linux. The engagement-issue-map.yaml only had one client entry.

In short: the code was written, but the pipeline didn't exist on the machine that was meant to run it. A pipeline that exists as code is not a pipeline that runs. Attempt 2 was a built thing in a git repo, not a running thing in production.

## The final wiring (after 3 attempts), in ASCII

Here's what the actual stack does today, end to end:

```text
Browser meet-recorder  (records .webm + .meta.json in-tab)
        |
        v
~/whisper-inbox/  (symlink to Google Drive folder)
        |
        v   systemd user timer, every 60 seconds
whisper-watcher.service -> whisper-watcher.sh
        |
        |   [skip if .posted.json or .redacted.md already exists]
        v
transcribe-file.py
        |--> faster-whisper (medium model, int8 quantisation, CPU)
        |--> whisperX alignment
        |--> pyannote 3.1 diarization (figures out who's speaking)
        |
        v   writes .transcript.md
redact-pii.py
        |--> 5 PII classes: email, phone, money amount, attendee name,
             whole-line redact on Article 9 keywords
        |--> writes .redacted.md + redaction-key.md
        |
        v   PIPELINE STOPS HERE - operator-triggered next step
/summarise-meeting <redacted.md> [--post]  (Claude Code skill)
        |--> reads engagement-issue-map.yaml
        |--> writes .summary.md
        |--> optional: posts a comment to the matching GitHub Issue
```

A few notes on this, because not everything's obvious.

**Browser records straight to disk.** The meet-recorder is a tiny static page running on my own domain. Uses the browser File System Access API to write the `.webm` and a small `.meta.json` (attendees, topic, session id) directly to the folder I pick. No server in the middle. No upload to anyone.

**Google Drive symlink** so the recording is also backed up to Drive without an extra copy step. The Linux pipeline reads the same file. Belt and braces. Praying Google Drive doesn't do that weird override thing where stale content sticks even when new content writes over it.

**Polling timer, not a path-unit.** The first attempt used a systemd path-unit (the "watch this folder, fire when a file appears" pattern). Doesn't work on WSL2 (the Linux-on-Windows compatibility layer) because Windows-side filesystem changes don't propagate inotify events through the 9p filesystem layer to Linux. Switched to a 60-second polling timer. Cruder, but it actually fires.

**Whisper on CPU, not GPU.** It runs on the main computer I use for work, no GPU on this box. 13 minutes of audio takes about 24 minutes of CPU wall-clock on the medium model. Roughly 1.8x slower than real-time. Not fast. Fast enough for asynchronous use (record the meeting, go do something else, come back to a transcript). I'd have preferred a separate lab machine to test on first, but the lab box's spec isn't up to scratch (would take forever on a transcript). Production it is.

**Summariser is a Claude Code skill, not a Python script.** Big architectural call this one. The first version had a `summarise.py` that called the Anthropic API with my own API key. Worked, but per-token API charges would have negated the whole point of this build. Trading a £9-40/month flat SaaS subscription for a metered API bill isn't a win, it's the same problem in a different shape. The Claude Code skill version triggers manually, bills against the Max 20x plan I already pay for, no API key. Same result. Actually free at the margin.

## Attempt 3: 36 unit tests passed, the real CLI failed five different ways

Pipeline wired this time. Deps installed. Timer firing. Pytest 36/36 green. Linter happy. shellcheck happy. Hit record on a real call (asking a bank about opening a business account, peak mundane, transcript opens "Is it working?" and ends "Cool man, catch you later, take care, take care, bye bye").

Then the live pipeline ran. And it failed. Five different ways.

Three were whisperx 3.8.5 API drift: a dropped `__version__` attribute, the `DiarizationPipeline` class moved to a submodule, a kwarg renamed from `use_auth_token` to `token`. One was pip's resolver quietly upgrading my CPU torch pin back to a CUDA build via a transitive pyannote dep. One was a third HuggingFace licence gate the runbook didn't know existed (pyannote.audio 4.0.4 added `speaker-diarization-community-1` for the speaker-embedding step). Plus a regex bug in the PII redactor that was eating filename timestamps as phone numbers.

Zero of the five caught by the 36 unit tests. They were integration bugs by definition: different libraries, deps, and licences colliding at runtime. Unit tests can't catch those, that's a different layer of testing. The harness calls it the sample-invocation gate: real CLI, real data, real machine.

That rule paid for itself in one afternoon.

## What it does today

Simple. Mundane. Exactly what I wanted.

Record a meeting. Wait. Come back later. There's a transcript in the inbox with speakers labelled (SPEAKER_00, SPEAKER_01) and a redacted version where any mentioned email addresses, phone numbers, money amounts, and pre-curated attendee names have been replaced with placeholders. Money mentioned was £10, redacted to `<AMOUNT_A>`. Phone numbers (when there are any) become `<PHONE_A>`, `<PHONE_B>`.

When I want a summary, I open Claude Code and type `/summarise-meeting <path-to-redacted.md>`. The skill reads the transcript, reads the existing GitHub Issue for that engagement (linked via a small YAML mapping file), produces a summary, and if I add `--post` it drops the summary as a comment on the Issue. Closes the loop.

Accuracy isn't 100%. Met my 80:20 rule though, 80% is good enough. Mixes words up sometimes (`free` instead of `three` was my favourite). Speaker diarization mixed the two voices up here and there. But what I actually care about is whether the context comes through, and that mostly does. Bonus: if it's not accurate enough to be used as legal evidence, that works in my favour. This was always a noting tool, never meant for evidence.

Audit:

- Audio in: 13 minutes 13 seconds
- CPU wall-clock: about 24 minutes (faster-whisper medium model, int8 quantisation, no GPU)
- Peak RAM: 2 to 3 GB
- Disk after the run: about 9 MB original `.webm` + small transcript + smaller summary
- Cost: £0 of new spend per month. The Max 20x plan was already paid for. The hardware is the production machine I already use for work. The HuggingFace licences are free.

## What went well, what didn't

**Went well:**

- £0 of new monthly spend, in a world where every meeting-notes SaaS wanted £15-40
- The "sample invocation gate" rule caught five bugs that 36 passing unit tests hadn't
- Diarization mostly works on real two-speaker audio (not perfect, mixes voices occasionally; good enough to follow who said what)
- Skill-not-script architecture removed API-key management as a whole category of work
- The dormant-classify pattern saved the compliance scaffolding without making it the default

**Didn't go well:**

- I over-built the first attempt by something like an order of magnitude. The scope I cut on the refactor was scope I should never have written in the first place
- The first version was merged without an end-to-end smoke test. Three deployment bugs sat silently for days because nobody had actually run the pipeline against a real file
- whisperx 3.8.5 surfaced three separate API-drift bugs in one session. Pinning library versions tighter would have prevented this. I didn't pin. My fault
- pip's resolver quietly undid my CPU torch pin via a transitive pyannote dependency. Now explicitly pinned. Lesson: when you have a CPU-locked wheel, install it with `--index-url https://download.pytorch.org/whl/cpu` BEFORE the rest of requirements, not as part of `pip install -r requirements.txt`
- The first PII regex was structurally wrong. Word boundaries alone are not enough; phone numbers need a positive structural marker (parens or separator) to avoid swallowing date-time tokens
- 8 hours of keyboard time over three days, of which probably 2.5 hours were directly attributable to the over-engineering on attempt 1. Time I won't get back

## The meta-lesson

Two rules surfaced. Both obvious in retrospect, both skipped on the first attempt.

**Build for the use case in front of you.** Mark the rest dormant. Don't delete it (you might need it one day). Just don't make it the default. The dormant-classify pattern lets the over-engineered scaffolding stay one mode-flip away without poisoning today's UX.

**Unit tests pass = each piece is built right. Doesn't mean the pieces fit together.** You need three layers. Unit tests (each cog works). Workflow tests (a subset of cogs work together). End-to-end tests (the whole thing runs in production, against real data, on the real machine). Skip the last one and you ship code that passes 36/36 in isolation and fails five ways the moment someone hits Record. The harness calls the last one the sample-invocation gate. Following it on attempt 3 caught all five bugs in one afternoon.

And the experiment itself answered its own question. Self-hosted transcription in 2026 on the main computer I use for work is accurate enough to be useful as a notes complement. £0/month, no vendor in the loop, runs while I'm doing something else. Whatever else this build did or didn't do, the experiment came in green.

## Welcome to coding with AI

I don't vibe-code entire platforms or apps in one go. I try to build my workflow in smaller pieces. And even smaller pieces require so much work to review in detail. Decision-making along the way about what actually works for you and your business. Being ready to be flexible. Patience to change directions when you need to. As you can see across these three attempts!

But doing it this way, you also learn a lot about the architecture. Writing the blog about my journey really helps me understand the cogs and wheels turning inside. So you know if it's been built right. Or not.

That gap I covered earlier, where Claude Code wrote 36 unit tests and called it done? I've noticed it do that often. My SST3 workflow tries to prevent it, but I haven't got a permanent fix yet. The AI still skims over it. Which is why I have to review and re-align the implementations along the way.

This is also one of the reasons you need an engineer mindset to build something. You have to know exactly what you're trying to build, why, and for who. Vibe-coding and leaving the AI to do its own shit doesn't work. Not yet.

<!-- iamhoiend -->
