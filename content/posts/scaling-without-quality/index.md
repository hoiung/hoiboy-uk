---
title: "Scaling Without Quality Is Just Multiplying Bugs."
date: 2026-04-20
categories: [tech-ai]
tags: [ai, claude-code, ai-orchestration, sst3, scaling, quality]
slug: scaling-without-quality
description: "Every big release brings a bug storm. Scale multiplies whatever you've already got. Build the base right, then scaling becomes the easy part."
---

<!-- iamhoi -->
## Every Release Has a Bug Storm After It. AI Just Made the Storms Expensive

Every big release has a bug storm after it.

New version. Ship Monday. Firefight all week. Always.

And it's not because the team were lazy. The opposite. They scale when they genuinely think they've covered the edge cases. When the test suite is green. When everyone feels it's good enough to go. They do their due diligence. Then real users turn up, at real scale, and edge cases that nobody could have anticipated at ten users or a hundred users start showing the cracks.

That's been the pattern for 20+ years, across every team I've watched from the inside.

Think about the software most of us actually live in every day. Facebook Ads, Amazon's reseller tools, YouTube's creator and admin console. GoDaddy's admin stack. WordPress, Joomla, and every CMS anyone's ever tried to run a site on. SugarCRM, vTigerCRM, Salesforce, and every CRM anyone's ever tried to run a sales team on. Printer drivers and tools. Windows. Every flavour of Linux. Practically every piece of software I've ever touched, at every tier of the stack, is fragile in its own way. And the list goes on...

None of these are simple apps that just store and show data. Some are massive platforms run by thousands of engineers. Some are open-source giants with decades of contributor history. Some are "enterprise-grade" tools sold with very serious price tags and very serious training programmes. And they're ALL STILL fragile. Every one. Features ship faster than bugs get patched. Whole teams exist just to keep the thing afloat.

That's the universal tax of shipping software to real users. The product never actually stabilises. It just keeps getting bolted on to.

Now stack AI on top of all that. AI agent workflows. Main agents calling more agents. Every action priced in tokens (the units AI companies bill by). And every token you burn troubleshooting a confidently-wrong output is money straight out of your pocket and into Claude, OpenAI, or Google.

It's the same chicken-and-egg problem tech's had for decades, wearing a new hat. Before AI, the cost was engineer-hours. Now the cost is tokens. Different currency, same leak. The only reliable winner is whoever's selling the shovels. (Before: consultancies and contract devs. Now: the AI labs themselves.) Everyone else is running a scaling race where every unknown edge case costs more the bigger they get.

Here's the bit nobody seems to say out loud: **scaling is a multiplier, not a creator.** Whatever you've got when you're running one orchestrator (the main AI agent running the show) gets multiplied the moment you're running a hundred of them. Small problems become manageable noise. Big problems become a runaway disaster you can't claw back from. The quality of your system when you're running one is the quality of your system when you're running a hundred, just louder.

And it's all moving faster than anything before it. That's AI's real gift. Things break much faster now. They also get fixed much faster. The cycle has compressed, which is exactly why the base quality of the thing you're scaling matters more, not less. A tight system ships the fix the same day the break happens. A loose one ships ten copies of the break before anyone notices.

If that sounds obvious, congratulations, you're one of the few. Because a lot of the AI agent world is racing in the opposite direction right now. More models! More prompts! More parallel agents! Ship it in a weekend, patch the hallucinations by Tuesday.

Everyone's sprinting. Nobody's stopping to ask whether the thing they're sprinting with is actually sound.

## Once Upon a Time, I Watched the Same Pattern Play Out in Different Buildings

Same film, different buildings.

A team gets the pressure to ship. Quality slips a bit, as it does under pressure. Bugs pile up. Someone in leadership decides the fix is "more engineers" or "more automation" or "let's parallelise the pipeline". The org scales the work... and scaling doesn't fix the underlying quality. It just copies the same mess across more places.

Six months later you've got ten of everything. Ten versions of the same bug that fails quietly without anyone noticing. Ten copies of the same test that lies to you. Ten teams confidently telling each other "it works on my machine" while the customer support queue catches fire.

Now with traditional software, at least the bugs are predictable. Same input, same broken output, the thing fails in a repeatable way, and someone clever enough eventually works it out.

With AI agents? The bugs are **unpredictable**. Same prompt, three different outputs. One of them confidently wrong in a way that looks right enough to ship. Same input on Tuesday works, same input on Wednesday silently hallucinates a function that doesn't exist, and on Thursday it invents a library. Now multiply that by 50 concurrent agents.

Go on. Picture it. Imagine the on-call shift. Imagine the logs.

That's the disaster I've been building the opposite of, on purpose, for the last two-ish years.

## So I Built [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) the Opposite Way

No hiring sprint. No parallel squads. One person directing one main orchestrator, with one shared set of rules applied to everything.

The shape ended up being five stages of delivery (research, then a written issue, then a triple-check on the scope, then implementation, then a post-implementation review) with a three-model review loop at the end. Haiku reads first for surface problems. Sonnet reads for logic. Opus reads for architecture. If any of them flags something, the whole thing restarts from Haiku.

There are also 14 automatic checks that run every time new code gets saved: token budget, template drift, debug code left in, silent fallbacks, hardcoded params, voice tells, path drift, large files, merge conflicts. The kind of thing most teams patch after the fact, not before. A custom plugin won't let the AI tick off a checkbox without attaching evidence. Planning mode is the default, so "have a look at this" never quietly turns into "accidentally deletes production".

None of it is glamorous. It's all just friction. Boring, constant, pedantic friction.

Numbers, for context: 10,000-odd commits across three repos, 1,860 issues at 99.4% close rate, 11,100-plus automated tests running against real broker APIs. One person running it. Deliberately.

## SST3 Is Fragile Too. Especially When Claude Releases a New Version

Let me not lie about this.

SST3 is not some polished, finished machine. It's a working system I'm constantly patching, tuning, and second-guessing. Every time Claude releases a new model or a new version of an existing one, I get a little panicky. A bit fidgety. Sometimes I stick with the older model for another few weeks, occasionally a full month, while Claude irons out the new one. Because new models can wreak havoc on SST3 with fresh hallucinations and all sorts of crap I can't predict.

And I get it wrong regularly. I'll fine-tune SST3 thinking SST3 is the problem when actually the problem is the new model. Waste a day rewiring something that was fine. Then a week later the penny drops. Other times I do need to realign SST3 to work better with the latest model, and that's hours of work too.

Fix. Unfix. Improve. Figure out how to make it work. Repeat.

It's hard work.

Which is why I close the tab on every "vibe coded an entire app in 3 hours" video the moment it loads. Load of rubbish. The people making those clips are missing the 50 hours of actual work that happens before and after the clip, where the thing goes from demo-toy to something that doesn't fall over the moment a user does something unexpected.

SST3 being fragile is fine, though. Because the whole point isn't that SST3 eliminates bugs. It doesn't. The point is that when the surprises hit (and they always do), the machinery around me absorbs them without everything melting down at once. Small problem stays a small problem.

## And the Interesting Part: Scaling It Is Simpler Than Scaling a Team

Here's what I find interesting.

A lot of engineers I've worked with know quality-first is the smarter bet. They'd build that way if they could. But we live in a hierarchical world where somebody is paying you to deliver on time and expecting a return on their investment. Shit rolls downhill. Deadlines get committed to above your head. Engineering teams end up shipping before they're ready, not because they don't know better, but because on-time delivery is the thing they're being paid for.

When you're the one running the harness top to bottom, the way I do with SST3, that specific pressure disappears. Which is where this gets interesting.

When the harness is built right, scaling it comes down to copying, not rebuilding. The whole thing is packaged. Workflow, process, governance, standards, review loop, pre-commit hooks, planning mode, evidence rules, context-handover protocol, the lot. Put it in a box. Duplicate the box. Stand up another main orchestrator. Same workflow. Same governance. Same standards. Same quality floor, in every instance, without me having to retrain anyone or rewrite anything.

The reason is simple. The harness isn't coupled to me. It's coupled to the rules. Copy the rules and you've copied the quality floor. You're not scaling a person. You're scaling the enforcement layer that keeps whoever is running the harness (human or AI) on track.

Compare that with any scaling org that didn't build the enforcement layer early. They've got the people. They've got the budget. They've got the parallel agents. What they don't have is the enforcement layer, because there was never time for it, because the moment someone mentioned it a director said "we'll revisit that after we ship". So when they scale, every new team inherits the same silent defaults, the same confident hallucinations, the same broken test patterns that passed the automated tests but mean absolutely nothing in production.

And now the mess is 10x.

Scaling multiplied what they had. The base was fragile. When they scaled up, the fragility multiplied with it.

## The Multiplier Thing. Finally in Plain Words

It took me a while to put this into words properly. I was operating on instinct. "Fix it now, don't batch the fixes, don't defer, no scope excuses, no language excuses." Same line I've been saying to every engineer I've ever worked with, for years.

But the reason clicked hard recently when I was looking at the SST3-AI-Harness repo and thinking about how I'd roll it out if a team wanted to use it tomorrow.

The answer wasn't "rewrite anything". The answer was: **package, duplicate, onboard.** Each new orchestrator inherits the frozen harness. Same 5-stage lifecycle. Same 14 hooks. Same Ralph Review. Same planning-default. Same 80% context-handover threshold that prevents the kind of context-overflow disasters that wipe an afternoon's work. They don't re-invent anything. They inherit the quality floor.

And that's only possible because of the last two years of insisting on quality when it felt slow.

Every pre-commit hook I added came from getting burned. Every silent fallback banned because they hide bugs. Every evidence-enforcement rule written because AI agents will tick any checkbox you give them, cheerfully, if you don't make them show receipts.

None of it looked strategic at the time. It looked like over-engineering. It looked like a one-person obsession with pedantic rules. It wasn't. It was me building the groundwork that later made duplicating the harness simpler than duplicating a team, one boring rule at a time.

The problem isn't quality-first vs scale-first. That's a fake either/or. The real question is: **when you finally scale, what do you want multiplied?**

If the answer is "signal", you have to build the signal first. Before you have anyone to scale to. Before the pressure hits.

If the answer is "mess"... good luck. You'll need it.

## The Goal Is to Keep the Problems Small and Manageable

That's the line I keep going back to.

Not "eliminate problems". Fantasy. You'll always have bugs. You'll always have edge cases. You'll always have something surprising turn up in production that no test covered. AI agents make this ten times worse than traditional software because the bugs aren't reproducible and the agents are confidently wrong in convincing ways.

But if your base system is tight, small problems stay small.

A failing test gets caught in Haiku review. A silent fallback gets caught in a pre-commit hook. A checkbox ticked without evidence gets rejected by the plugin. A confidently wrong output gets flagged by the Ralph triple-pass. None of these things are individually dramatic. They're just friction. Constant, boring, pedantic friction that stops small problems from ever snowballing into the sort of problem that ends a startup.

Now multiply that by 50 orchestrators, each running the same harness. The friction is multiplied. So is the quality floor. So is the recovery speed. Things will still break, of course. But when they do, each instance has the same repair machinery ready to catch it before it goes anywhere dangerous.

That's the whole thesis, condensed.

**Build the box right. Duplicate it. Scale the quality.**

It's the opposite of the industry default. Which is exactly why I'm betting on it.
<!-- iamhoiend -->
