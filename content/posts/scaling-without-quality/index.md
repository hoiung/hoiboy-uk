---
title: "Scaling Without Quality. Just Multiplying Bugs."
date: 2026-04-19
draft: false
categories: [tech-ai]
tags: [ai, claude-code, ai-orchestration, sst3, scaling, quality]
slug: scaling-without-quality
description: "Every big release brings a bug storm. AI makes the storms expensive. Scale multiplies whatever you've already got. Build the base right, scaling gets easy."
---

<!-- iamhoi -->
## Every Release Has a Bug Storm After It. AI Just Made the Storms Expensive

Every big release has a bug storm after it.

New version. Ship Monday. Firefight all week. Always...

And it's not because the team were lazy. The opposite. They scale when they genuinely think they've covered the edge cases, the test suite is green, everyone feels it's good enough to go. They do their due diligence. Then real users turn up, at real scale, and edge cases that nobody could have anticipated at ten users or a hundred users start showing the cracks.

That's been the pattern for 20+ years, across every team I've watched from the inside.

Think about the software entrepreneurs and businesses of every size actually live in every day. Facebook Ads, Amazon's reseller tools, YouTube's creator and admin console. GoDaddy's admin stack. WordPress, Joomla, and every CMS anyone's ever tried to run a site on. SugarCRM, vTigerCRM, Salesforce, and every CRM anyone's ever tried to run a sales team on. Apache, BIND, DHCP, Samba, CUPS, Postfix, and the rest of the open-source server stack that quietly keeps businesses running. Asterisk PBX, Trixbox, Skype SIP trunking, and every other VoIP telephony system I've had to keep alive. Remedy and the other ticketing systems I've used over the years. Printer drivers and tools. Windows (95, 98, 2000, XP, Server, take your pick). Every flavour of Linux. FreeBSD. OpenBSD. Practically every piece of software I've ever touched, at every tier of the stack, is fragile in its own way. And the list goes on...

None of these are simple apps that just store and show data. Some are massive platforms run by thousands of engineers. Others are open-source giants with decades of contributor history behind them. A bunch are "enterprise-grade" tools sold with very serious price tags and very serious training programmes to match. And most of them these days are SaaS (Software as a Service: pay a monthly subscription, use it hosted, never install anything). Even SaaS has to be customised, with intricate workflows and settings to get right. And the vendor is always fixing, upgrading, pushing the next piece of tech. What worked yesterday may not work today. They're ALL STILL fragile. Every one. Features ship faster than bugs get patched. Whole teams exist just to keep the thing afloat.

That's the universal tax of shipping software to real users. The product never actually stabilises. It just keeps getting bolted on to.

Now stack AI on top of all that. AI agent workflows (an "agent" is an AI you hand a job to, which can call tools, read files, and kick off other AIs to help it finish). Main agents calling more agents. Every action priced in tokens (the units AI companies bill by). And every token you burn troubleshooting a confidently-wrong output (or "hallucination" in polite industry speak, when the AI states something false with total authority) is money straight out of your pocket and into Claude, OpenAI, or Google.

It's the same chicken-and-egg problem tech's had for decades, wearing a new hat. Before AI, the cost was engineer-hours. Now it's tokens. Same leak, new invoice. The only reliable winner is whoever's selling the shovels. (Before: consultancies and contract devs. Now: the AI labs themselves.) Everyone else is running a scaling race where every unknown edge case costs more the bigger they get.

Here's the bit worth saying out loud: **scaling is a multiplier, not a creator.** Whatever you've got when you're running one orchestrator (the main AI agent running the show) gets multiplied the moment you're running a hundred of them. Small problems become manageable noise. Big problems become a really really nasty runaway disaster you can't claw back from. The quality of your system at one orchestrator is the quality at a hundred. Just louder.

And it's all moving faster than anything before it. That's AI's real gift. Things break faster now. They get fixed faster too. Which is exactly why the base quality of the thing you're scaling matters MORE. A tight system ships the fix same-day. A loose one ships ten more copies of the break before anyone notices.

If that sounds obvious, congratulations, you're one of the few. Because a lot of the AI agent world is doing the opposite right now. More models! More prompts (the instructions you type to an AI)! More parallel agents! Ship it in a weekend, patch the hallucinations by Tuesday.

Plenty of teams are sprinting. Not enough are stopping to ask whether the thing they're sprinting with is actually sound.

## Once Upon a Time, I Watched the Same Pattern Play Out in Different Scenarios

Same movie, different scenarios.

A team gets the pressure to ship. Quality slips a bit, as it does under pressure. Bugs pile up. Someone in leadership decides the fix is "more engineers" or "more automation" or "let's parallelise the pipeline". The org scales the work... and scaling doesn't fix the underlying quality. It just copies the same mess across more places.

Six months later you've got ten of everything. Ten versions of the same bug failing quietly without anyone noticing. The same lying test, copy-pasted ten times. And ten teams all confidently telling each other "it works on my machine" while the customer support queue catches fire.

Now with traditional software, at least the bugs are predictable. Same input, same broken output, the thing fails in a repeatable way, and someone clever enough eventually works it out.

With AI agents? The bugs are **unpredictable**. Same prompt (same instructions), three different outputs. One of them confidently wrong in a way that looks right enough to ship. Same input on Tuesday works. Wednesday it silently hallucinates a function that doesn't exist. Thursday it's scope-creeping: features you never asked for, hardcoded parameters everywhere, unwired functions left dangling, new code wired straight into dead code that goes nowhere. And it'll cheerfully claim it all works. Now multiply that by 50 concurrent agents.

And it gets worse. AI compounds wrong into right. If it's seen a broken pattern enough times, whether in its training data or pulled in via RAG (retrieval-augmented generation: fetching real examples into the prompt before the AI writes), it starts treating the bug AS the correct answer. Which is also why "AI slop" is a real problem. The internet is flooded with AI-generated code and AI-written articles now. The next round of AI reads all of it and thinks it's genuinely good engineering. It isn't. It's slop, confidently reproduced.

PS: I reckon the next real breakthrough in AI isn't more parameters or bigger context windows. It's figuring out fact from fiction. When the internet's 80% AI slop and 20% actual truth, whoever cracks that is the next game changer.

Or the labs figure out their own way to quarantine the clean facts from the slop. Which will cost tokens, obviously. The same labs creating the slop will happily charge you to sort it out. Selling shovels always wins. Create the problem, then sell the solution.

Which is basically misinformation. Same game the world's been playing for years, just accelerated now. Repeat a lie enough times and it turns into fact, because the masses keep repeating it. Some people call them sheeple. Either way, it's a very dangerous game.

Go on. Picture it. Picture the on-call shift at 3am, the pager going off, the logs lighting up on 50 different orchestrators at once.

That's the disaster I've been building the opposite of. Not on purpose. I was just trying to stop my own automated trading system from breaking every time an AI touched it. The harness came as a side-effect. Nine months ago. Refined weekly since.

Turned out I was ahead of the game. AI labs and indie builders are only talking about harnesses now, in the last couple of months or so. Feels like I was barking up the right tree and clocked what was missing with AI before most people did.

## So I Built [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) the Opposite Way

SST3-AI-Harness is the frame I built (by mistake) to run AI agents under strict rules. Scaffolding that keeps the AI honest. No hiring sprint. No parallel squads. One person directing a single main orchestrator, with one shared ruleset for everything.

The shape ended up being five stages of delivery (research, then a written issue, then a triple-check on the scope, then implementation, then a post-implementation review) with a three-model review loop at the end. Haiku, Sonnet, and Opus are three sizes of Claude, small to large. Haiku, the fast one, reads first for surface problems. Sonnet, the mid-size, reads for logic. Opus, the big brain, reads for architecture. If any of them flags something, the whole thing restarts from Haiku.

There are also 14 automatic checks that run every time new code gets saved. The boring housekeeping stuff: is there leftover debug code, are there shortcuts that silently hide bugs, is the AI slipping into generic voice, has it left merge conflicts in, is the file absurdly big. The kind of thing most teams patch after the fact, not before. A custom plugin won't let the AI tick off a checkbox without attaching evidence. Planning mode is the default (meaning the AI has to tell me what it's going to do before it does it, instead of just running off and changing files), so "have a look at this" never quietly turns into "accidentally deletes production".

None of it is glamorous. It's all just friction. Boring, constant, pedantic friction.

Numbers, for context: 10,000+ commits across four repos, 1,860+ issues at 99.4% close rate, 11,100+ automated tests running against real broker systems (the actual trading platforms, not test stubs). One person running it. Deliberately.

## SST3 Is Fragile Too. Especially When Claude Releases a New Version

Honest answer...

SST3 is not some polished, finished machine. It's a working system I'm constantly patching and second-guessing. Every time Claude releases a new model or a new version of an existing one, I get a little panicky. A bit fidgety... (yes, the SST3 creator gets fidgety over Anthropic release notes, sue me). Sometimes I stick with the older model for another few weeks, occasionally a full month, while Claude irons out the new one. Because new models can wreak havoc on SST3 with fresh hallucinations and all sorts of crap I can't predict.

And I get it wrong regularly. I'll fine-tune SST3 thinking SST3 is the problem when actually the problem is the new model. Waste a day rewiring something that was fine. Then a week later the penny drops. Other times I do need to realign SST3 to work better with the latest model, and that's hours of work too.

Fix. Unfix. Improve. Figure out how to make it work. Repeat.

It's hard work.

Which is why I close the tab on every "vibe coded an entire app in 3 hours" video or article the moment it loads on my Google newsfeed. Load of rubbish. Trust me... the people making those clips are missing the actual work that happens before and after the clip, where the thing goes from demo-toy to something that doesn't fall over the moment a user does something unexpected.

SST3 being fragile is fine, though. Because the whole point isn't that SST3 eliminates bugs. It doesn't. The point is that when the surprises hit (and they always do), the machinery around me absorbs them without everything melting down at once. Small problem stays small...

## And the Interesting Part: Scaling It Is Simpler Than Scaling a Team

We live in a hierarchical world where somebody is paying you to deliver on time and expecting a return on their investment. Shit rolls downhill. Deadlines get committed to above your head. Engineering teams end up shipping before they're ready, because on-time delivery is what they're being paid for.

When you're the one running the harness top to bottom, the way I do with SST3, that specific pressure disappears. Which is where this gets interesting.

When the harness is built right, scaling it comes down to copying, not rebuilding. The whole thing is packaged. Workflow, process, governance, standards, review loop, pre-commit hooks (automatic checks that fire every time code gets saved, blocking bad stuff before it lands), planning mode, evidence rules, context-handover protocol (how a half-finished job gets passed from one AI session to the next without losing track), the lot. Put it in a box. Duplicate the box. Stand up another main orchestrator. Everything inherits: workflow, governance, standards, quality floor, all of it in every instance, without me having to retrain anyone or rewrite anything.

The reason is simple. The harness isn't coupled to me. It's coupled to the rules. Copy the rules, copy the quality floor. That's it. Whoever runs the harness next (human or AI) inherits the enforcement layer, not me.

People have noticed, to be fair. "Harness Engineering" and "AI Harness" are floating around as terms now because enough of the industry has clocked that scaling without governance, without guidelines, without a harness, is dangerous. The penny has dropped.

But for the orgs that didn't build the enforcement layer early, the penny dropped too late. They've got the people, the budget, the parallel agents. And no enforcement layer, because there was never time for it, because the moment someone mentioned it a director said "we'll revisit that after we ship". So when they scale, every new team inherits the same silent defaults, confident hallucinations everywhere, broken test patterns that pass the automated tests but mean absolutely nothing in production.

And now the mess is 10x. For the ones who rushed ahead without a harness.

Scaling multiplied what they had. The base was fragile. When they scaled up, the fragility multiplied with it.

## The Multiplier Thing. Finally in Plain Words

I was operating on instinct for ages. "Fix it now, don't batch the fixes, don't defer, no scope excuses, no language excuses." It's the line buried all over SST3's standards.

The reason clicked hard recently when I was looking at the SST3-AI-Harness repo and thinking about how I'd roll it out if a team wanted to use it tomorrow.

The answer wasn't "rewrite anything". The answer was: **package, duplicate, onboard.** Each new orchestrator inherits the frozen harness. Same 5-stage lifecycle. The 14 hooks (those automatic checks I mentioned). Ralph Review (the three-model Haiku-Sonnet-Opus cross-check from earlier, named after the "Ralph" loop technique where you run the same work through the loop until it's clean). Planning-default. And the 80% context-handover threshold. AIs have a memory limit; at 80% full SST3 forces a handover to a fresh session before the AI starts forgetting earlier parts of the job and breaking things. They don't re-invent any of it. They inherit the quality floor.

That's only possible because of the last nine months of insisting on quality when it felt slow.

Every pre-commit hook came from getting burned. Silent fallbacks got banned because they hide bugs. The evidence-enforcement rule exists because AI agents will tick any checkbox you give them, cheerfully, if you don't make them show receipts.

None of it looked strategic at the time. It looked like over-engineering, a one-person obsession with pedantic rules. It wasn't. It was me building the groundwork that later made duplicating the harness simpler than duplicating a team, one boring rule at a time.

Fake either/or. Real question: **when you scale, what gets multiplied?**

Everything does. The good stuff, the bad stuff, the AI slop, all of it. You just hope the good wins louder than the slop. That's the whole gamble. Build a base where the good has a chance.

If the answer is "mess"... good luck. You'll need it.

## The Goal Is to Keep the Problems Small and Manageable

There's always a price. Pay now, or pay later.

That's the decision every org dodges, because deferring the bill feels like winning. Sometimes "pay cheap, pay twice" does work out. Most times... it doesn't. And at AI-agent scale, "pay later" means paying the hallucination tax on every one of 50 orchestrators at once, not just the one. The bill compounds with the scaling factor.

That's the line I keep going back to. Quality first.

Not "eliminate problems". Fantasy. You'll always have bugs, edge cases, something surprising turning up in production that no test covered. AI agents make this ten times worse than traditional software because the bugs aren't reproducible and the agents are confidently wrong in convincing ways.

But if your base system is tight, small problems stay small.

A failing test gets caught in Haiku review. Silent fallbacks? The pre-commit hook kills them. A checkbox ticked without evidence? The plugin rejects it. And a confidently-wrong output gets flagged by the Ralph triple-pass before it goes anywhere dangerous. None of these are individually dramatic. They're just friction. Pedantic friction that stops small problems from ever snowballing into the sort of problem that ends a startup.

Does AI still lie through any of these? Sometimes. Minimal is acceptable.

Don't chase bug-free perfection either. By then you've missed the gravy train and the competition's moved past you. Know when it's good enough.

Now multiply that by 50 orchestrators, each running the same harness. The friction multiplies. So does the quality floor, and the recovery speed. Things will still break, of course. But when they do, each instance has the same repair machinery ready to catch it before it goes anywhere dangerous.

That's the whole thing, in one line.

**Build the box right. Duplicate it. Scale the quality.**

It's the opposite of the industry default. Which is exactly why I'm betting on it.

## Footnote: I Built SST3 Under 200K. AI's at 1M Now

Worth noting the context I built this in.

Nine months ago, the best context window I could get was 200K tokens. That's what Claude Code shipped with. And SST3 itself, loaded at session start (CLAUDE.md, STANDARDS.md, ANTI-PATTERNS.md, current issue), chewed up as much as 100K. That's 50% of my working memory gone before I'd written a single line of new code.

It didn't hit 100K on day one either. It crept up as I kept finding gaps and holes in the workflow, new anti-patterns to document, new rules that had to be canonical. Every gap meant a hard decision: keep it, bin it, or keep it short and hope the AI doesn't skip over the short version because it wasn't clear enough. That last trade-off was the hardest one on most days. Short saves tokens. Short also gets skimmed.

The struggle was real. Every new rule I added to SST3 had to earn its place. Every anti-pattern entry had to justify the tokens it cost. I was always trimming, dedup'ing, compacting to stay inside the budget. Lego pieces snapped together precisely or not at all. There wasn't spare budget for sloppy design.

In hindsight, I'm glad I built it under that pressure. If I'd had 1M tokens from day one, SST3 would probably be twice the size, do half the work, and cost three times the tokens per run. The 200K constraint forced the harness to stay lean. Now that AI's comfortably in the 1M era, I get to keep the lean harness AND have around 700K free for actual problem-solving. The last 200K is a danger zone. Hallucinations spike, agents start going rogue. So 800K is the real working cap, not 1M.

Scarcity as a design tool. Unintentional, but it worked.
<!-- iamhoiend -->
