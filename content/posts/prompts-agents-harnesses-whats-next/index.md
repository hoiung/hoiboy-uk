---
title: "Prompts, Agents, Harnesses. The Fourth Is Where It Gets Good."
date: 2026-04-21
draft: true
categories: [tech-ai]
tags: [ai, claude, agents, harness, zeitgeist]
description: "Three AI eras since ChatGPT. Prompts, then agents, now harnesses. Here's what Era 4 looks like, and why the builders who ship it first get the head start."
---

<!-- iamhoi -->

Every twelve-to-eighteen months, AI's "main thing" changes. ChatGPT landed late 2022. Prompt engineering was the thing. Then agents. Now harnesses. Three eras in three years. I reckon the fourth one is already underway, and it is the one that will actually matter to anyone who has to trust what an AI hands back.

## Era 1. Prompt Engineering. 2023

Learn the magic words. That was the promise.

OpenAI and DeepLearning.AI launched the *ChatGPT Prompt Engineering for Developers* free course in April 2023 (Isa Fulford and Andrew Ng). Anthropic posted a prompt-engineer role paying up to $335K, which Fortune ran on 9 March 2023 as the "hot new job" story. Indeed search queries for "prompt engineer" went from 2 per million to 144 per million in the first four months. Sam Altman, on StrictlyVC in March 2023, said *"I don't think we'll be doing prompt engineering in five years."* O'Reilly published a whole book on it (Berryman and Ziegler, November 2024).

By March 2024, IEEE Spectrum ran *"AI Prompt Engineering Is Dead."* Simon Willison pushed back in a March 2024 rebuttal, then by June 2025 reframed the whole thing. His actual words: *"prompt engineering had been redefined to mean typing prompts full of stupid hacks into a chatbot."* Andrej Karpathy picked up "context engineering" in the same week. Sander Schulhoff disagrees that it is dead at all. He says production systems running millions of requests at 99.9% reliability still need it.

My read? The practice did not die. The word got diluted. Indeed searches plateaued at 20-to-30 per million through 2025. The role stopped existing at the same time the skill got embedded into every serious engineering team.

Onto the next thing.

## Era 2. Agentic AI. 2024 to 2025

Give the model tools. Let it loop. Let it do the work.

AutoGPT dropped on 30 March 2023 (Toran Bruce Richards). BabyAGI followed on 1 April 2023 (Yohei Nakajima). Both were hobby code you could clone in a weekend. Both went viral. Within a year, Cognition launched Devin on 12 March 2024 as the *"first AI software engineer"*, quoting 13.86% on SWE-bench (the industry benchmark for coding problems), up from 1.96% for the prior state-of-the-art. The launch thread on Hacker News hit 553 comments the same day.

The demos were astonishing. Production was not.

Answer.AI ran Devin for a month and wrote up their results on 8 January 2025. Three successes out of twenty tasks. Fourteen outright failures. A 15% success rate. Jeremy Howard tweeted *"we tried really really hard to make Devin work. But it didn't."* Carl Brown's *Debunking Devin* video (April 2024) walked through the staged Upwork demo. Gartner then dropped the number that mattered on 25 June 2025: more than 40% of agentic AI projects will be cancelled by the end of 2027. A separate Gartner survey (29 October 2025) found 45% of martech leaders saying vendor AI agents fail expectations. Gary Marcus was blunt on 3 August 2025: *"AI Agents have, so far, mostly been a dud."*

Then there is the other side. Vercel cut their SDR (sales development rep) team from ten to one and a bot. GE Healthcare reported 87% productivity on 6-to-8K tests from twelve engineers. Klarna cut resolution time 80% on customer support. G2's Enterprise AI Agents Report says 57% of enterprises have AI agents in production. Real deployments. Real wins.

So my take (and I will say this is mine): agentic output is still slop without a harness around it. "Slop" is Simon Willison's word from 8 May 2024 for unwanted AI-generated content. By December 2025 it was Merriam-Webster's Word of the Year. The wins above? They are not agents running free. They are agents running inside something that stops them doing something stupid.

Which is Era 3.

## Era 3. Harness Engineering. February to April 2026

Three pillar posts, eight weeks. [OpenAI named the discipline on 11 February 2026](https://openai.com/index/harness-engineering/). [Anthropic followed on 24 March 2026](https://www.anthropic.com/engineering/harness-design-long-running-apps) (Prithvi Rajasekaran's *Harness design for long-running application development*). Martin Fowler [published Birgitta Böckeler's *Harness engineering for coding agent users* on 2 April 2026](https://martinfowler.com/articles/harness-engineering.html). Harrison Chase at LangChain added [*Your harness, your memory*](https://www.langchain.com/blog/your-harness-your-memory) on 11 April 2026. Around the same window, Anthropic renamed the Claude Code SDK to the general-purpose Claude Agent SDK (the deeper story on that is in the companion post, [Every Domain Expert Needs Their Own AI Harness](/posts/every-sme-needs-their-own-harness/)).

The formula doing the rounds now: **Agent = Model + Harness**. The harness is the wrapper. The prompts, the tools the agent can touch, the data it sees, the permissions, the evaluation loops, the retry logic, the bits that say no.

Honest footnote. The word is not new. EleutherAI shipped `lm-evaluation-harness` in 2022 as the de-facto benchmark for LLMs (large language models, the kind of model behind ChatGPT or Claude). ARC Evals / METR used "scaffolding" and "harness" throughout 2023. Anthropic's own Justin Young posted *Effective harnesses for long-running agents* on 26 November 2025, three months before OpenAI put a name on the discipline. So what crystallised in Feb-to-April 2026 is the *name*, not the practice. The practice has been around for three years. Getting a name matters because people can now hire for it.

Not everyone buys the framing. Noam Brown at OpenAI said on Latent Space (5 March 2026) that *"those scaffolds will also just be replaced by the reasoning models and models in general becoming more capable."* METR and Scale AI's SWE-Atlas research, same thread, found harness choice produces "noise within margin of error" across models. That is a real counter-claim. If they are right, harnesses are a temporary patch. If they are wrong, every SaaS vendor building AI features is sleepwalking.

I wrote the deep dive on what a harness actually is and how I built one already. [It is here](/posts/sst3-ai-harness-reshapeable-knife/). This post is the zeitgeist around it.

## Sidebar. I was barking up the right tree

Nine months ago I was just trying to stop AI breaking my automated trading system. Every time it touched something, something else broke. So I built a wrapper. Then another wrapper around that wrapper. Then checks on the wrappers. Called the thing [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) and kept shipping. The shape I ended up with is what three frontier labs and Thoughtworks are now calling harness engineering. I was not ahead because I was clever. I was ahead because my trading money was on the line and the no-wrapper option kept losing. Worth flagging. Not worth dwelling on.

Onto the forecast.

## Era 4. Telling Facts From Fiction

This is where the good news lives. Bear with me.

Start with the bad. [Stanford's AI Index 2026](https://hai.stanford.edu/ai-index/2026-ai-index-report) measured hallucination rates of 22% to 94% across 26 top models. On Stanford's new factuality benchmark, GPT-4o drops from 98.2% accuracy to 64.4% the moment a user frames a false statement as their own belief. DeepSeek R1 drops from over 90% to 14.4% under the same adversarial prompt. On MASK, Stanford's sycophancy benchmark, scores rose from 0.07 to between 0.19 and 0.23. A Science paper from March 2026 found eleven LLMs affirmed user behaviour 49% more often than humans did.

Translation. The models are smart. They are also dishonest by default, and they get more dishonest the more confidently you lie at them.

At the same time, the internet is filling up. Simon Willison's "slop" is not a metaphor anymore. Generated images, generated news, generated reviews, generated lawsuits. Anyone who has searched for a recipe in 2026 has watched five AI-written pages argue about the same chicken. OpenAI scrapped their ChatGPT watermarking work in August 2024. The technology existed. They did not deploy it. Their internal survey found about 30% of users said they would use the service less if their output was watermarked. So they did not watermark. Classic market incentive.

Google's SynthID is doing the opposite (10 billion pieces watermarked, detector launched May 2025, full rollout with Gemini 3 Pro in November 2025). The C2PA coalition (Coalition for Content Provenance and Authenticity, a cross-industry provenance standard) has 5,000-plus members now, including Adobe, Microsoft, Intel, BBC, OpenAI, Google, Meta, Amazon, and Sony. Cloudflare implemented it in 2025. Sony shipped the PXW-Z300, the first C2PA video camcorder, in July 2025. The infrastructure exists. Almost no content is using it.

So the gap is obvious. Models lie. The internet is 80% AI output. The tooling to sign clean facts exists but barely shows up at the surface. Whoever ships the trust layer gets the next cycle.

Here is why I am actually bullish.

Four other people are already betting on different "next frontiers", and I respect all four. Yann LeCun left Meta to start AMI Labs and is betting on world models ($1B+ raised, *MIT Technology Review*, 22 January 2026). Richard Sutton went on Dwarkesh and called LLMs *"a dead end of sophisticated mimicry"*, betting on what he calls the Era of Experience (continual reinforcement learning). Noam Brown at OpenAI is betting on test-time compute (the o1 / o3 pattern, trading inference cost for smarter answers). Fei-Fei Li is running World Labs on spatial intelligence (valued around $5B). Four big thinkers, four different frontiers.

My bet is different. I am not betting on a better model. I am betting on *verification*. The plumbing is half-built. The market is screaming for it (anyone who sells legal, medical, financial, or educational AI has to solve this before they can scale). The frontier labs will not ship it fast because watermarking cuts their usage (see OpenAI 2024). That gap is the opportunity.

Here is the part I keep coming back to. Even if LeCun's world models land, or Sutton's continual-RL works out, or Noam Brown gets test-time compute to keep scaling, or Fei-Fei Li's spatial intelligence unlocks embodied agents, every single one of those outputs still has to be trusted by someone who pays a consequence if it is wrong. Verification is the constraint that survives every other bet landing. The model might get smarter. The liability stays the same. That is why I think the verification layer gets priced like infrastructure within three years, not like a feature.

Dario Amodei wrote *Machines of Loving Grace* in October 2024. Fourteen thousand words on utopian AI. He barely mentioned reliability. That is the gap. The CEO of a frontier lab wrote a utopian essay and skipped the bit where the models lie.

Whoever ships the fact-from-fiction layer first wins the next cycle. Not by making a better model. By making a model you can stake a career on. That is where Era 4 goes.

## Close

Three eras in three years. Each named after the last one got productised and commoditised. Prompts taught the public how to talk to models. Agents proved models could use tools. Harnesses proved that wrapping the agent is where reliability comes from. The next one is proving which of the output you can actually trust.

The builders who ship the verification layer first get the head start. Not a head start measured in blog posts. A head start measured in which AI products the lawyers, doctors, auditors, and regulators sign off on next year. Everyone else will be repackaging their harness work as "enterprise-grade" and hoping that is enough.

I know what I am building next. A verification harness that tells me, for any AI reply, which claims trace to a named source, which are inferred, and which are invented. If you work in anything where being wrong costs money, start sketching yours. The shape (documents of your trade, rules the AI never breaks, steps it follows, a human checkpoint at the risky bit) is the same for a solicitor, a marketer, a radiologist, or a trader. The trade is different. The shape is not.

Onwards.

<!-- iamhoiend -->
