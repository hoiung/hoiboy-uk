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

AI is not going to replace you. The lazy framing is that it will. AI assists. It does the generic bit well. What it does not do is *your* unique angle: the skillset, the creativity, the small judgment calls, the problem solving that only makes sense if you know the craft. Ingenuity is where humans still excel.

And generic is itself a product. ChatGPT out of the box is a generic product and it is worth hundreds of billions. But generic is not what most trades sell. Brands sell personality. Experts sell judgment. The moment your output is indistinguishable from the AI-generated baseline, you are one of a million voices using the same tool and the same prompt. Nothing to pay extra for. Prices collapse. Margins disappear. The harness does not save you from that. You do. The harness is the custom fit, the hero suit we tailor to you. The suit amplifies. The person inside is still the one making the call. Creativity, ingenuity, judgment. That is the human bit.

## Why the off-the-shelf slice will not fit

First, the honest bit. The lab products are genuinely useful for their target users.

Claude Cowork (launched 12 January 2026 as a research preview) gives non-coders the Claude Code agent in an interface they can actually use. Boris Cherny, the Claude Code lead, told Fortune on 24 January 2026 that users kept pointing out Claude Code was a general-purpose agent. Anthropic built Cowork "in about a week and a half" as the non-coder wrapper. CNBC's February follow-up: "built to give the average office worker a productivity boost." That is real value for spreadsheet-heavy office work.

Claude Design (launched 17 April 2026, powered by Opus 4.7) does the same trick for non-designers. Figma's share price dropped 7.28% on announcement day. Adobe lost 2.7%, Wix 4.7%. Mike Krieger (Anthropic's CPO) had resigned the Figma board three days earlier. That is a frontier lab telling a public market it can eat a product category without owning the UI.

Claude Code Desktop (redesigned 15 April 2026, often confused with Cowork) is still developer-focused. Parallel coding sessions, Git worktrees, pull-request review. Not for the non-coder. Anthropic split the personas cleanly because they could.

A quick clarification worth heading off. "Controlling your computer" can mean two different things. Running commands, installing things, editing files, spinning up services, managing programs: that is the admin side, and [Claude Code](https://code.claude.com/docs/en/overview) has done it since its research preview on 24 February 2025. Moving the mouse, clicking the UI, filling forms by seeing the screen: that is [Computer Use](https://www.anthropic.com/news/3-5-models-and-computer-use), launched four months earlier on 22 October 2024. Two different capabilities, both already shipped. When Anthropic's marketing says "Claude can now control your computer" for Cowork, they usually mean the UI side.

Now my read on it. Each of these SKUs (stock keeping units, the label retailers and software vendors use for every saleable product variant) is optimised for *the lab's* business model. Cowork is an upsell into Pro and Team subscriptions. Design is a research-preview signal to investors that Anthropic Labs is encroaching on every vertical. Code Desktop is developer retention. None of them is a tool you can shape into *your* workflow. They are all Anthropic's interpretation of what a lawyer or a marketer or a designer needs. If you want the wrapping to match your actual trade, you have to build the wrapping.

And this is not an Anthropic problem. Google shipped Workspace Studio on 19 March 2026 ("puts custom agent creation in the hands of every employee"). OpenAI did the whole arc years ago: Custom GPTs (November 2023), Operator (January 2025), ChatGPT Agent later in 2025, then GPT-5.2-Codex for coding specifically. Every frontier lab is running the same play. They all sell the horizontal product. None of them ships your vertical.

## The pattern they keep admitting in public

Here is where it gets interesting. The labs know the model is generalising, and they know the value is in specialising it. They keep saying so out loud.

[Anthropic's Claude Mythos Preview announcement](https://red.anthropic.com/2026/mythos-preview/) (7 April 2026, the cybersecurity research release in Project Glasswing) says the bit nobody is meant to notice. Their exact words:

> "We did not explicitly train Mythos Preview to have these capabilities. Rather, they emerged as a downstream consequence of general improvements in code, reasoning, and autonomy."

Translation. We built a general-purpose model. It became a security expert on its own. We did not plan that.

And then, more usefully, the [Claude Agent SDK rename on 29 September 2025](https://claude.com/blog/building-agents-with-the-claude-agent-sdk) (SDK stands for software development kit, the thing developers plug into):

> "To reflect this broader vision, we're renaming the Claude Code SDK to the Claude Agent SDK... the agent harness that powers Claude Code can power many other types of agents, too."

Translation. We built this thing for coders. It works for everyone. We are renaming it so people stop thinking it is only for code.

Reading between the lines, I do not fully buy "emerged on its own". Anthropic's own 244-page system card describes new RL (reinforcement learning, the training technique that rewards good behaviour and penalises bad) environments added specifically to penalise privilege escalation, destructive cleanup, and unwarranted scope expansion. Cyber-adjacent behaviours by any reading. The composition of the rest of the training is deliberately undisclosed. So "pure emergence" is the narrative, not a verified fact. [Independent reviewers](https://thezvi.substack.com/p/claude-mythos-the-system-card) note the training section is not importantly different from what Claude Opus got, yet Opus cannot find vulnerabilities at the 83% first-attempt success rate Mythos is hitting. Convenient.

The timing of the public reveal is worth naming too. Anthropic was publicly [removed from Pentagon contracts on 27 February 2026](https://www.cnn.com/2026/02/26/tech/anthropic-rejects-pentagon-offer) after refusing the Department of Defense's demand for "unfettered access". OpenAI picked up the Pentagon deal the same day. Three days later, Anthropic was formally designated a "supply chain risk", the first such designation ever applied to an American company. Mythos Preview and Project Glasswing launched on 7 April 2026. One day later, Anthropic lost its [DC Circuit appeal against the federal ban](https://www.cnbc.com/2026/04/08/anthropic-pentagon-court-ruling-supply-chain-risk.html). By 19 April, [Axios reported the NSA was using Mythos despite the Defense blacklist](https://www.axios.com/2026/04/19/nsa-anthropic-mythos-pentagon). Today (21 April) [Trump says a DoD deal is "possible" again](https://www.cnbc.com/2026/04/21/trump-anthropic-department-defense-deal.html). Mainstream business press is calling the launch an "unexpected growth engine" and a "pariah-to-White-House-ally pivot". The capabilities are real. The timing of the public reveal is not coincidence.

That is Anthropic, in their own words, confirming what I have been saying for nine months. General AI does not stay general. It specialises. The only question is who gets to shape the specialisation. If it is the lab, the lab owns the trade's workflow. If it is the trade, the trade owns the lab's output.

## The prescription

A harness is the wrapper around the general model. The prompts that tell it your job. The tools it is allowed to touch. The data it sees. The permissions that stop it doing something stupid. The evaluation loops that catch when it lies. The retry logic. The bits that say no.

That wrapper is where your trade's governance lives.

For a solicitor: rules for how to cite precedent, anti-patterns for what never goes in a client email, a workflow that pulls from your jurisdiction's case law before any clause gets drafted. For a marketer: brand-voice rules, channel-compliance checks, a workflow that runs a brief through the brand guide before the copy gets written. For a trader: hard position-size limits, anti-patterns for every way a model has previously misread an instruction as permission to trade, a forced human checkpoint before anything goes live. The knowledge of the trade (your case law, your brand guide, your strategy notes, your broker's API (application programming interface, the channel a program uses to talk to another program) quirks) lives in the documents and references you feed in.

The general model underneath does the thinking. The harness does the governing. You still do the trade.

Here is the part that compounds. Once the harness is in place, it also governs how new skills and tools get built for your trade. The same standards, anti-patterns, workflows, verifications, and checks that stop the AI doing something stupid today also apply when you ask the AI to help extend the harness tomorrow. Write a new approval workflow. Add a new compliance check. Build a new skill for a specific case type. The governance that protects the output also protects the build. The harness teaches the AI how to write more harness, correctly, for your vertical. That is the moat. Every skill you add respects the rules you already set. Every future AI build session starts from higher ground.

This is not theoretical. Vertical-SaaS vendors have been shipping this shape for a couple of years already. Salesforce calls theirs Agentforce, Atlassian ships Rovo, SAP has Joule, Bloomberg has BloombergGPT. The difference is their harness is *their* product, locked to *their* customers. Yours is yours. You control the prompts, the data, the tools, the updates, the exits. If the underlying model changes, you change one configuration. If your trade rules change, you change the harness.

## Evidence it works

I built mine nine months ago. Not for a business plan. For a problem. My automated trading system kept breaking every time AI touched it. Files renamed in ways that snapped my imports. Refactors that silently changed the rounding logic. Dependencies updated on a Saturday morning because a model thought it was helping. So I wrote a wrapper to stop the AI doing anything I had not signed off. Then another wrapper. Then checks on the wrappers. Then tests on the checks. The thing became [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) and I kept shipping.

It is public, it is reshapeable, and the full write-up of what it does and how it was built is [here](/posts/sst3-ai-harness-reshapeable-knife/). What matters for this post is the shape, not the code. The harness sits on top of the model, not baked into it. If Anthropic ships a better Claude tomorrow, great. The harness governs my trading workflow regardless. The shape would port to other LLMs in principle, but I run Claude Code exclusively. It is the best on the market, and keeping the harness tuned to each new Claude Code release is already enough work without also tracking every other lab's roadmap. If you are building your own harness (or borrow/steal mine to customise), pick one LLM and work with it. Do not thin your hours trying to fine-tune across every lab in the market.

Since then, I have reshaped the same harness for other verticals. My CV and LinkedIn work (governance around voice, fact-checking). This blog (the harness governs every post, which is why it sounds like me, not like a generic AI tech take). Our eBay side business (listing rules, photography standards, description anti-patterns). Two friends took the same approach for their own trades: one for a coaching practice, one for an architecture studio. More are on the way. None of them needed me to rewrite the underlying wrapper. New rules, new documents, new workflows. The approach held.

The approach is reproducible. Any domain expert with a trade worth automating can build their own harness the same way. The lab ships the general-purpose model. The expert ships the trade-specific harness on top. Whoever knows the trade best writes that harness best. That is you, not them. Once you have it, use the harness to build every new skill your discipline needs. Same governance each time. The expertise compounds.

## How to start (without writing any code yourself)

If you have never written a line of code, good news. Harness engineering in 2026 does not need you to. The frontier labs now ship tooling that lets a non-developer define a harness in plain English. Anthropic's [Agent Skills](https://www.anthropic.com/news/skills) (the SKILL.md open-standard spec, published 16 October 2025) lets anyone write a capability as a markdown file. Claude Projects (the Pro and Team feature with 200K-context curated knowledge bases) lets anyone seed a domain.

Your starting harness is three governance layers: a set of rules the AI never breaks, a set of steps it must follow, and a human checkpoint at the risky bits. The harness wraps around the documents that describe your trade (your brand guide, your case law, your strategy notes), so the model consults them correctly instead of guessing.

For a marketer, the three governance layers might look like `approval-list.md` (who signs off what), `channel-rules.md` (what goes where, and what never does), and a hard stop that makes a human press the button before anything goes public. The documents it wraps: your brand guide, product catalogue, past approved copy. For a solicitor, swap the content but keep the shape: drafting rules, filing workflow, partner sign-off at the risky moments, all wrapping a precedent library and your jurisdiction's case law. Start there. Most trades get a lot of the way with that shape alone. The deeper engineering layers (evaluation loops, retry logic, permission models, automated tests) come later, when the harness has proved its worth.

## Close

The frontier labs will keep shipping slices. More Coworks, more Designs, more vertical SKUs. Some will be useful to you. None of them will be *yours*.

The ones who start now get two things. A working harness that matches their actual trade, today. And a moat that keeps working as the models underneath improve. A better model in 2027 makes your harness better. A better lab SKU in 2027 makes their shareholders better. Not quite the same thing.

AI labs sell the tool. You bring the trade. That is where the expertise goes durable.

Build the harness. It is yours.

(If you want the wider picture around this, three AI eras in three years and where I think the fourth one is heading, the companion post is [Prompts, Agents, Harnesses. The Fourth Is Where It Gets Good.](/posts/prompts-agents-harnesses-whats-next/).)

<!-- iamhoiend -->
