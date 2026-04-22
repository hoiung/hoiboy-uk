---
title: "Brands Have Voices. People Do Too."
date: 2026-04-22
lastmod: 2026-04-22T11:00:00Z
draft: false
categories: [tech-ai]
tags: [voice-persona, writing, ai-tells, sst3, personal-brand, portfolio]
slug: your-voice-is-a-brand
description: "A brand has a voice. So do I. We analysed 12 years of my writing, encoded 61 rules the AI cannot break, and now AI writes like me (mostly), not like a consultant deck."
images:
  - hero.webp
---

<!-- iamhoi -->

A week ago I published the [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) reshapeable-knife post and closed it with "watch this space. More posts coming on the specific bits. The voice guard for writing." This is that post. It is about a marketing trick applied to a person.

Here is what drove it. 3 years of watching AI write, from ChatGPT through to Claude. The pattern does not shift. Mechanical. Generic. Buzzword-heavy. A love for uncommon acronyms everyday readers will not understand. Same tell across every new model. This post is what I did with the observation.

## Brands have a voice framework. So can a person

Every brand you know has a voice. Colours. A typography style. A shape. A tone of emotional triggers. A set of words it says and a set it refuses. Nike says "just do it." Nike does not say the consultant-deck filler a brand audit would flag on sight.

<!-- iamhoi-skip -->
(If you are wondering which filler: things like "at scale" and "circle back" would never survive a Nike brand review.)
<!-- iamhoi-skipend -->

That is not an accident. Somebody wrote the rules down, and now every designer, copywriter, and AI tool a brand touches produces on-brand assets because the framework is portable.

I have run businesses for 20+ years. When you are the whole team for most of that, you end up learning every trade that makes a business work, marketing included, and every trade that makes one fail. So when AI kept handing me consultant-deck drafts of my own blog, the marketer's reflex was the one that fired. I wanted my drafts back to sounding like me, not like everyone. And I thought: if a brand can encode its voice so AI produces on-brand assets, a person should be able to do the same. Personality is a brand, one scale down. That thought became a project.

This is the marketer's trick if you think about it. Brand guidelines exist because a brand has to produce consistent output across many people and many contexts. A designer does not wake up and decide what Nike sounds like that morning. The voice is encoded once; every piece of work downstream inherits it. The framework IS the voice. Point AI at that framework and you get on-brand output without having to re-explain the brand every time. Now run the same play on a person. A person can have a framework too. Voice rules, preferred words, banned words, cadence habits, sign-off patterns, sentence-shape preferences. Encode it once; every future AI draft inherits it. That was the bet this project was built on. The bet paid off.

## I treated my voice like a brand

Marketing people do 3 things. They collect the raw artefacts (ads, posts, taglines). They analyse the pattern. They write the rules down.

I did the same with my writing. 12 years of it. 59 entries. About 161,000 words. 8 separate platforms: a Joomla adventure blog (where my early dance writing also lived), 3 WordPress dance-community sites, 2 sets of Google Docs drafts, a Google Drive internal archive, and this Hugo blog. The goal was not to admire the archive. The goal was to pull the pattern out. That took a swarm of subagents in my [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) reading it all. No single AI context can hold 161,000 words and keep its attention honest.

350 sentences profiled. 9 voice registers (the sober technical me, the gym-rat me, the drunk-kebab me, the dance-fanatic me, the entrepreneur me, and 4 shades in between). 30 AI tells catalogued as smoking-gun absences (words AI loves that my writing has exactly zero of across 161,000 words). 37 rescue rules for when a draft had started to drift.

The big one was em dashes.

<!-- iamhoi-skip -->
(Em dash = the long horizontal bar: —. Not a hyphen. AI loves them.)
<!-- iamhoi-skipend -->

External research puts GPT-4.1 at 10.62 em dashes per 1,000 words. Humans average 3.23. My writing has 0 across 161,000 words. Sam Altman has publicly said ChatGPT's em-dash frequency was tuned during fine-tuning. Which is fine for ChatGPT. Just not fine for me.

And I was not precious about the data either. 1 of the 59 entries (an early post I had let ChatGPT polish before I knew better) has 7 em dashes in 270 words. That sample sits in the archive as a control. It is what I sound like when I hand the pen over. The other 58 entries are what I sound like when I hold it. The contrast is the proof.

## KISS is why the rules look the way they do

There is a personal principle underneath all of this. Keep It Simple, Stupid. I treat every reader as a person who might not have English as a first language. My writing uses short sentences, concrete nouns, contractions. The smartest people I know explain things in plain English. The ones trying to sound smart reach for elevated filler vocabulary AI was trained on.

<!-- iamhoi-skip -->
(The banned-word file names them: delve, tapestry, meticulous, pivotal, furthermore, seamless, innovative, cutting-edge, impactful. There are 61 of those. I will not pretend I did not include examples.)
<!-- iamhoi-skipend -->

To be clear, KISS is not this blog's argument. It is the reason the rules look the way they do. A different writer would end up with a different list.

## What the code actually does

Rules are no good if nobody enforces them. So I encoded them.

The single source of truth is `voice_rules.py`. 61 banned words. 7 banned phrases (cover-letter openers, hedging preambles, career humble-brags).

<!-- iamhoi-skip -->
(Named for the archive: "I am writing to express my interest", "It is worth noting that", "Throughout my career, I have". There are 7.)
<!-- iamhoi-skipend -->

10 keep-list overrides for authentic me-vocabulary that AI tools also happen to use (passion, journey, deeply, truly, navigate, fundamentals, fall in love, back to basics, attention to detail, passionate). That keep-list was load-bearing. Without it, a naive banned-word sweep would sanitise the warmest parts of my voice out, and public me would start sounding like a compliance memo.

The guard itself is a 432-line Python script, `check_voice_tells.py`. 7 detection types. Em dashes. Banned words. Banned phrases. Smart quotes. Unicode arrows (AI's favourite way to draw a diagram nobody asked for). A negation-framing pattern (the "it's not X, it's Y" shape AI reaches for about 3 times a page). A bold-first-bullet pattern (AI's favourite layout, the one that turns every document into a slide deck).

There is a marker system on top. By default the guard scans nothing. A draft opts in by wrapping the prose in `<!-- iamhoi -->` and `<!-- iamhoiend -->` HTML comments. A skip-hole inside a region lets me quote banned words in an example block without tripping the guard. That default was deliberate. I have years of pre-AI legacy posts on this site, and those posts ARE the voice research. Scanning them would flag words I had used sincerely and corrupt the persona evidence. Default-skip keeps the back catalogue untouched while every new post gets the full treatment.

It runs as a pre-commit hook, in 3 continuous integration (CI) steps (the voice guard itself, an em-dash grep belt-and-braces, and a unit-test suite for the marker state machine), and as a drift guard that refuses to let the vendored Python copy diverge from the canonical. Binary pass or fail. There is no warning tier. I tried one. The sentence-rhythm heuristics I wrote for it were too brittle on short content, and I shipped without it rather than ship a guard that cried wolf. That is the honest-engineering line: if I cannot make the rule work in practice, the rule does not ship.

The code behind this blog lives at [github.com/hoiung/hoiboy-uk](https://github.com/hoiung/hoiboy-uk). Click through if you want to read the script. It is not long.

## What I got wrong along the way

The rules bit me the day I wrote them. The first internal doc said the banned-word list had ~60 entries. The actual Python file had 76. A gap between what I thought I had built and what I had built. Caught on a later audit; fixed the doc to match the code. The code was ground truth; my memory of it was fiction.

And then the scaling-without-quality draft a few weekends ago. AI padded a paragraph with a specific coworker anecdote that never happened. It sounded good. It was not true. I called it out at the time with "stop making shit up" twice in one session. The 3-fabrication-categories rule (no invented scenes, no aphorisms, no strawmen) went into the voice profile that evening. Rule 1 caught rule 1's own drafting session. The rules work because I apply them to me first.

Even this post. Drafting inside the harness, the post-implementation review swarm caught 2 fabrications the main agent slipped in. One invented platform list. One invented timeline. Flagged with file and line receipts; fixed. The point is not that AI invents things. It does, constantly. The point is the harness catches more than I catch alone.

## Applying the same persona everywhere

Once the voice was encoded it stopped being a blog thing and became a framework. Same framework, plugged into every surface that produces writing with my name on it. A quick tour.

Blog first. The `/blog` skill I use in [Claude Code](https://claude.com/claude-code) pulls the voice profile into context on every new post, including this one. The pre-commit hook catches banned words before I see them in the editor.

The CV is where the framework really earns its keep. Draft tailored to the job posting, banned-word scan, voice-guard run, plain-English check on every acronym. Outcomes language only, no recruiter-bait stock phrases.

<!-- iamhoi-skip -->
(Specifically the "dedicated team player" / "proven track record" / "results-driven" family that any human with a CV knows by heart and every ATS rewards anyway.)
<!-- iamhoi-skipend -->

LinkedIn inherits the same filter. Posts, profile headline, about section. Even the headline gets the voice treatment before it ships.

Cover letters are where the framework pays its rent most visibly. Every application has a bespoke first paragraph that sounds like me, not a template. The `/job-hunter` skill handles it via 2 codified lenses (VOICE, the same as this blog; HIRER, how hiring managers actually read a CV), plus an unconventional-research workflow pulling company-insider signal from Reddit, Blind, Glassdoor verbatim, engineering blogs, and regulatory filings. Not just the company's marketing site. Prepping for a Bolt screen last week, that workflow surfaced the European Union (EU) Platform Work Directive 2024/2831 and the UK tribunal case from November 2024. Neither on the jobs page. Both the actual risk exposure for the role.

Emails come next. Cold follow-ups, recruiter replies, client comms. Same voice filter. Drafts that move through my harness get the pre-commit discipline. Drafts I write inside someone else's client tool get a mental banned-word list instead.

Businesses last. Product descriptions for an online store I run, website copy for a side project called id8u, reply macros for customer-support tickets. Small-commerce English is usually the first place brand voice collapses. It does not have to.

The [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) framework underneath wires the voice profile into every one of those skills. If an AI draft sneaks a banned word through, the pre-commit hook catches it. If the hook misses, CI catches it. If both miss, the drift guard catches stale rule copies. 3 layers, 1 source of truth.

One receipt on whether any of this dilutes my voice. I keep a private draft of every big post uncensored, alongside the version I publish publicly. On a recent side-by-side across about 8,000 words, the two versions were 95% identical. I softened exactly 1 line (too personal about a family member). Professional me is not a different person from private me. The rails did their job.

## Where I am with it now

This was always going to be a refining process. The rules started wrong. The doc said ~60 banned words when the code had 76. The keep-list grew as the guard kept flagging warm vocabulary I actually use. The warning tier shipped as OFF because the heuristic was too brittle. I spent the first couple of months fixing drift the guard surfaced.

I am past that phase now. I do not refine the rules often any more, only when the same pattern or the same problem shows up frequently. What I still do, and will always do, is the human-in-the-loop manual sanity check on every draft. Read it through once. Brush up the sentences that do not quite feel right. Double-check any fact or number that looks off. Overall: 90-95% good to go after that pass. The other 5-10% is my thumbprint.

## What AI is still better at than me

This post is not anti-AI. I use AI every day and will not stop. AI is much better than me at tedious work. Frontmatter. Hugo builds. Link checks. Grep-for-anomalies across 40 posts. Writing test scaffolding. Catching a typo I read past 4 times.

The voice persona is a rail, not a replacement. It draws a line. AI handles the tedious work it is great at. A human brief and a voice rail handle anything with my name on it that the public will read. That trade-off is the whole point. AI got better; my public writing did not get worse. If anything, it got more consistently me.

## What this does not do

The rules are living code, not a one-shot framework. AI models will change. New tells will emerge. I expect to add to the banned-word list (45% of job seekers were using AI on CVs in 2024, 64% of recruiters noticed an uptick, and the floor on "what counts as AI tell" keeps shifting upward). I expect one of today's rules to look silly in 2 years when model behaviour shifts again. That is fine. The guard is easy to change. The voice analysis is the thing you do once.

One more counterargument worth pre-empting. Does encoding your voice dilute it? On the 8,000-word side-by-side I already mentioned, 1 line changed in the whole document. 95% identical. The rails keep AI drafts honest. They do not overwrite me.

## Bloopers. Catches from this very build

Two categories. Harness catches. My catches on re-read. Separated so you see the lines.

### What the harness caught autonomously

The pre-commit voice guard caught banned words on my first try at the Nike example. The two buzzwords I had quoted were both on the banned list, even though I was quoting them as things Nike does NOT say. The regex does not care about rhetorical framing. Wrapped the quote in an iamhoi-skip block.

A 3-tier AI review pass inside the harness (next post is on that) caught a fabricated platform list. An earlier draft named Blogger, Medium, Substack, Tumblr, and WhatsApp voice-note transcripts as the 8 platforms. None appear in my written-life inventory. Category-1 fabrication. Replaced with the real tech stack.

A post-implementation review swarm caught 7 other things: the date maths ("Six days ago" was actually 7), 3 count errors ("45 rescue rules" was 37, "60 posts" was 40, "3 CI jobs" was 3 steps in 1 job), 2 acronyms used without inline expansion (CI and EU), the Story Spine missing its "every day, here is what I was doing before" beat, the brand-voice thesis being underdeveloped (1 sentence originally), and the applications section running too thin.

### What I caught on human-in-the-loop re-read

5 category-1 fabrications slipped past every layer of the harness and landed on my own read. "Drafting for months" (not true). "Years in marketing before tech" (not true; 20+ years running businesses). "The father-of-two me" in the voice registers (no kids). "The dance-teacher me" next to it (fanatic, not teacher). "Found mine on Tumblr" in the closer (never used Tumblr). Each one plausible. Each one invented. Fixed on re-read.

Plus smaller voice edits. "A shape" and "a tone of emotional triggers" added to the brand-voice list. A "(mostly)" added to the SEO description for honesty. Joomla reframed as my adventure blog rather than a dance site. "Brand teams" swapped for plain "Marketing people". Em dash spelled out for readers new to the character.

### What the harness blocks going forward

One re-read catch was private business detail that never should have shipped. An early draft named my eBay store by product category. I scrubbed it to generic framing, force-pushed history so the specific is gone from every commit, then extended the harness. New memory rule: personal business specifics are private. New pre-commit blocklist in every public repo I own. Future drafts trying to re-introduce a blocked term get refused. The rails caught something new, so now they catch it everywhere.

Add it all up and it maps onto the 5-10% thumbprint pass mentioned earlier. Harness does the factual, structural, lexical. I do the context and the first-person reality it has no way to know. Neither works alone.

## The "watch this space" post

A week ago I closed the [reshapeable-knife post](/posts/sst3-ai-harness-reshapeable-knife/) with "watch this space. More posts coming on... the voice guard for writing." This is the one. Next up is the Ralph Review system. For the sister argument about reaching for the simple tool when it works rather than the clever one that does not, see the [LLM Wiki debate post](/posts/llm-wiki-debate/).

If this sounds like a framework you could build for yourself, you probably have more raw material than you think. Mine came from archives I had stopped opening years ago.

<!-- iamhoiend -->
