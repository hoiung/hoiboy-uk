---
title: "Every Domain Expert Needs Their Own AI Harness"
date: 2026-04-21
draft: true
categories: [tech-ai, entrepreneurship]
tags: [ai, sme, harness, claude, domain-experts]
description: "Frontier labs are productising general-to-specialised AI. Their SKUs are not your workflow. Every domain expert should be building their own harness."
---

<!-- iamhoi -->

You are a lawyer. A marketer. An HR lead. A financial adviser. A physiotherapist. A teacher. A recruiter. A trader. You have watched AI chew through developer jobs for eighteen months, and you have been quietly asking when it is your turn. Not *if* AI comes for your work. *When*, and in what shape.

Here is the shape. The frontier labs build one big model. They discover it is good at lots of things. They slice off the profitable slices and productise them. Developers got Claude Code. Non-devs are getting Claude Cowork. Designers are getting Claude Design. The next slice is yours.

But that slice will be optimised for *their* funnel, not your trade. It will be priced for their revenue target. It will be designed around the parts of your job that happen to be easy to automate for everyone, not the parts where *your* expertise earns a living. When it lands, it will look like a sharper version of the chatbot you already have, and it will leave a hole where the vertical-specific knowledge ought to be.

The real play is different. Every domain expert should be building their own harness.

## Why the off-the-shelf slice will not fit

First, the honest bit. The lab products are genuinely useful for their target users.

Claude Cowork (launched 12 January 2026 as a research preview) gives non-coders the Claude Code agent in an interface they can actually use. Boris Cherny, the Claude Code lead, told Fortune on 24 January 2026 that users kept pointing out Claude Code was a general-purpose agent. Anthropic built Cowork "in about a week and a half" as the non-coder wrapper. CNBC's February follow-up: "built to give the average office worker a productivity boost." That is real value for spreadsheet-heavy office work.

Claude Design (launched 17 April 2026, powered by Opus 4.7) does the same trick for non-designers. Figma's share price dropped 7.28% on announcement day. Adobe lost 2.7%, Wix 4.7%. Mike Krieger (Anthropic's CPO) had resigned the Figma board three days earlier. That is a frontier lab telling a public market it can eat a product category without owning the UI.

Claude Code Desktop (redesigned 15 April 2026, often confused with Cowork) is still developer-focused. Parallel coding sessions, Git worktrees, pull-request review. Not for the non-coder. Anthropic split the personas cleanly because they could.

Now the framing. Each of these SKUs is optimised for *the lab's* business model. Cowork is an upsell into Pro and Team subscriptions. Design is a research-preview signal to investors that Anthropic Labs is encroaching on every vertical. Code Desktop is developer retention. None of them is a tool you can shape into *your* workflow. They are all Anthropic's interpretation of what a lawyer or a marketer or a designer needs. If you want the wrapping to match your actual trade, you have to build the wrapping.

And this is not an Anthropic problem. Google shipped Workspace Studio on 19 March 2026 ("puts custom agent creation in the hands of every employee"). OpenAI did the whole arc years ago: Custom GPTs (November 2023), Operator (January 2025), ChatGPT Agent later in 2025, then GPT-5.2-Codex for coding specifically. Every frontier lab is running the same play. They all sell the horizontal product. None of them ships your vertical.

## The pattern they keep admitting in public

Here is where it gets interesting. The labs know the model is generalising, and they know the value is in specialising it. They keep saying so out loud.

Anthropic's Claude Mythos Preview announcement (7 April 2026, the cybersecurity research release in Project Glasswing) says the bit nobody is meant to notice. Their exact words:

> "We did not explicitly train Mythos Preview to have these capabilities. Rather, they emerged as a downstream consequence of general improvements in code, reasoning, and autonomy."

Translation. We built a general-purpose model. It became a security expert on its own. We did not plan that.

And then, more usefully, the Claude Agent SDK rename on 29 September 2025 (SDK stands for software development kit, the thing developers plug into):

> "To reflect this broader vision, we're renaming the Claude Code SDK to the Claude Agent SDK... the agent harness that powers Claude Code can power many other types of agents, too."

Translation. We built this thing for coders. It works for everyone. We are renaming it so people stop thinking it is only for code.

That is Anthropic, in their own words, confirming what Hoi has been saying for nine months. General AI does not stay general. It specialises. The only question is who gets to shape the specialisation. If it is the lab, the lab owns the trade's workflow. If it is the trade, the trade owns the lab's output.

## The prescription

A harness is the wrapper around the general model. The prompts that tell it your job. The tools it is allowed to touch. The data it sees. The permissions that stop it doing something stupid. The evaluation loops that catch when it lies. The retry logic. The bits that say no.

That wrapper is where your trade lives.

If you are a solicitor, your harness knows your jurisdiction, your precedents, your clause templates, the names of the judges in your local court, and what you never ever promise a client over email. If you are a marketer, your harness knows your brand voice, your product catalogue, your channel rules, your compliance list, and what you would never let a junior copywriter send. If you are a trader, your harness knows your strategies, your instruments, your risk limits, your broker's API quirks, and the twelve ways a model has previously tried to put your money in the wrong account.

The general model underneath does the thinking. The harness does the trade.

This is not theoretical. Salesforce, SAP, Atlassian, Bloomberg, and every serious vertical-SaaS vendor is already shipping this shape. The difference is their harness is *their* product, locked to *their* customers. Yours is yours. You control the prompts, the data, the tools, the updates, the exits. If the underlying model changes, you change one configuration. If your trade rules change, you change the harness.

## Evidence it works

I built mine nine months ago. Not for a business plan. For a problem. My automated trading system kept breaking every time AI touched it. Files renamed in ways that snapped my imports. Refactors that silently changed the rounding logic. Dependencies updated on a Saturday morning because a model thought it was helping. So I wrote a wrapper to stop the AI doing anything I had not signed off. Then another wrapper. Then checks on the wrappers. Then tests on the checks. The thing became [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) and I kept shipping.

It is public, it is reshapeable, and the full write-up of what it does and how it was built is [here](/posts/sst3-ai-harness-reshapeable-knife/). What matters for this post is the shape, not the code. The harness sits on top of whichever model I am using that month. It does not care. If Anthropic ships a better Claude tomorrow, great. If OpenAI shifts the goalposts again, fine. The harness knows my trading workflow. It does not care what Anthropic is planning next quarter.

That shape is reproducible. Any domain expert with a trade worth automating can build an equivalent. The lab ships the horizontal; the expert ships the vertical; the harness is the interface between them. The person who knows the trade best writes the harness best. That is you, not them.

## How to start (without writing any code yourself)

If you have never written a line of code, good news. Harness engineering in 2026 does not need you to. The frontier labs now ship tooling that lets a non-developer define a harness in plain English. Anthropic's Agent Skills (the SKILL.md open-standard spec, published 16 October 2025) lets anyone write a capability as a markdown file. Claude Projects (the Pro and Team feature with 200K-context curated knowledge bases) lets anyone seed a domain. Your harness can start as four things: a set of documents that describe your trade, a set of rules the AI never breaks, a set of steps it must follow, and a human checkpoint at the risky bits.

Start there. Most trades get a lot of the way with that shape alone. The engineering layers (evaluation loops, retry logic, permission models, automated tests) come later, when the harness has proved its worth.

## Close

The frontier labs will keep shipping slices. More Coworks, more Designs, more vertical SKUs. Some will be useful to you. None of them will be *yours*.

The ones who start now get two things. A working harness that matches their actual trade, today. And a moat that keeps working as the models underneath improve. A better model in 2027 makes your harness better. A better lab SKU in 2027 makes their shareholders better. Not quite the same thing.

AI labs sell the tool. You bring the trade. That is where the expertise goes durable.

Build the harness. It is yours.

<!-- iamhoiend -->
