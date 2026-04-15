---
title: "SST3-AI-Harness. Why I Built a Hero Suit for AI."
date: 2026-04-15
categories: [tech-ai]
tags: [ai, claude-code, automation, ai-orchestration, sst3, governance]
slug: sst3-ai-harness-reshapeable-knife
description: "Why I built SST3-AI-Harness, how the reshapeable-knife idea works in practice, and why marketing, HR, finance, and R&D benefit as much as engineering."
---

<!-- iamhoi -->
## Once upon a time, I was staring at stock charts 6 to 12 hours a day

Anywhere between 6 and 12 hours depending on how busy the week was. Same patterns. Same indicators. Same exhausting slog of "is this a real bounce or am I about to get slapped in the face by the market?" Constantly trying to figure out what works and what doesn't, how it works, and why it works. Then figuring out how to test the thing that seemed to work. Then trying to work out whether it was ACTUALLY working or just overfitted nonsense that looked brilliant on paper and would fall apart the moment the stock's personality shifted. (I didn't have a backtest system back then, so "on paper" really meant manually reviewing charts by eye. Basically theory. Dangerous theory with no data to back it up.) The eBay side hustle was the thing I'd poke at whenever I had a little extra time. Honestly, mostly procrastination.

The trading platform though. That was the real project. And that's actually the reason [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) exists. I didn't set out to build a methodology framework. I set out to build a trading system, and I kept running head-first into the same wall: AI without guardrails, standards, governance, and (most importantly) PROCESS is a glorious mess. Actually, "process" is being generous. What process?

To actually get past theory and into something real, I had to pour in my entire life's worth of knowledge, experience, and engineering thought process. Every pattern I'd picked up across 20+ years of IT, every lesson from running small businesses, every hard-earned instinct from staring at charts long enough to know what NOT to trust. All of it went into turning "this might work" into "here's the data that proves it works, here's the test that proves it keeps working, and here's the guardrail that stops the AI from silently breaking it next week".

Workflow and process are the bits nobody talks about.

Quick definition while we're here, because I mix these up myself sometimes (they work so closely together that I'll often use them as if they mean the same thing, and mostly nobody cares, but they ARE different):

- **Process** is the WHAT and WHY. The rules, the standards, the quality bar. Static policy. "Every merge gets a 3-tier review. Silent fallbacks are banned. Every checkbox needs evidence." It's the expectation.
- **Workflow** is the HOW and WHEN. The concrete ordered sequence that turns the policy into actual behaviour. The moving parts. "Research, then Issue, then Triple-Check, then Implement, then Haiku review, then Sonnet review, then Opus review, then Merge, then Post-Implementation Review." It's the execution.

You need both. A process with no workflow is a pinned Notion doc nobody reads. A workflow with no process is a lot of clicking with no point. Put them together and you've got something that actually makes the AI produce real work in the right order at the right quality.

Process is basically the race-condition protection for the algorithm of your work. Things have to happen in a certain order. Prep needs to finish before the next stage can start. Skip a step and the whole thing either crashes, corrupts, or quietly produces rubbish that looks fine until a real user hits it. Workflow is how you force the right things to happen at the right time, in the right sequence, with the right inputs. Without both? Everything becomes a mess.

And the AI tools I'd tried were mostly spitting out confident-sounding garbage that took longer to fact-check than to just write the thing myself.

A lot of ChatGPT at first. Then Claude Code, specifically, after my friend Bear insisted I give it a try instead. (Bear is the nickname his close friends use for him, and also the name he'd rather I put on the record. He likes his privacy. Fair enough.) Claude was better. Much better. But still a cowboy without supervision.

And the AI slop online is EVERYWHERE. Those "build X in one ChatGPT / Claude chat window!" videos and threads? Most of them are rubbish. I've tried. Genuinely. I close the video the moment I see that pitch now.

What the AI builds in that mode might look pretty on the surface. Nice UI. Nice demo. Nice gif. But the inside is a mess. It doesn't work. It's not engineering. It's not functional. It's a sketch that looks like software.

That, right there, is one of the big reasons a lot of people give up on AI. They watched the hype videos. They tried the shortcut. It didn't work. They concluded AI is a fad. Which is half right (the "build-it-in-one-prompt" fad absolutely is) and completely wrong at the same time (AI with a proper harness is genuinely transformational). The fad is real. And yet it isn't.

You know that feeling when you buy the expensive power tool, and instead of cutting your work in half, it's added three new problems to your list? That was me with AI. Every. Single. Time.

Something had to give.

## What I built

[SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) is what I built to fix it.

Quick name decode, because people keep asking.

- **SST3 = Single Source of Truth v3.** The whole methodology framework is built on the idea that there should be ONE canonical place for every rule, every standard, every template, every anti-pattern. Not "it lives in three docs and they're out of sync". One source. Period. The 3 is the version (SST1 came first, SST2 fixed SST1's problems, SST3 fixed SST2's). Each version is a scar count, driven by real failures I kept hitting until I wrote a rule that stopped them.
- **AI-Harness** is the wrapper around the AI itself. The AI is the horse. The Harness is what makes it pull in the right direction without bolting off the field. Orchestration, governance, quality gates, enforcement. All of it.

Short version: it's a Single-Source-of-Truth methodology framework plus a stack of scripts, templates, and quality gates that turn raw Claude Code (or any LLM) into something you can ACTUALLY work with on real work.

Do I fully trust it? Absolutely not. And honestly, you should NEVER fully trust AI. That's rule number one. It doesn't matter how good the harness is, how shiny the guardrails are, how many reviews you stack. You always keep a human eye on it.

With [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) around the AI, my working trust level sits at about 80%. Not 100%. Not even 90%. Eighty. I'm a big believer in the 80:20 rule and this is no different. 80% of the output is clean enough to use with light review. The other 20% I still watch carefully, red pen in hand. That 20% is the grey area where the AI tends to fudge things, and over time you learn exactly where it usually tries to.

But that's miles better than before. Before, the ratio was flipped: maybe 20% usable, 80% slop and bullshit. The harness turned that around. Doesn't mean I've handed over the keys. Means the keys are safer in my hand while the AI does the driving under supervision.

It's the difference between "AI wrote the thing and I spent two hours fixing it" and "AI got much closer on the first pass because the harness made cutting corners significantly harder". Not magic. Not a guarantee. Just a much better base rate. AI is probabilistic, so you shift the odds. You don't eliminate risk.

Think horse harness, parachute harness, climbing harness. The bit that lets powerful things do useful work without killing anyone. The LLM is the horse. SST3 is the harness.

## The reshapeable knife

There's a metaphor I use in the [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) README and I want to expand on it, because a lot of people miss the point.

A knife is a knife is a knife. Right?

Wrong.

A chef's blade. A surgeon's scalpel. A butcher's cleaver. A ninja's throwing knife. All knives. Completely different tools. You wouldn't chop onions with a scalpel (possible, just not very practical, lol). You wouldn't perform open-heart surgery with a cleaver. You wouldn't take a chef's blade to a rooftop chase (maybe, but please don't). And you wouldn't slice your carrots into thin little sticks with a throwing knife, though you'd look very very cool trying.

The blade shape depends on the job. The user depends on knowing the job.

SST3 is a reshapeable knife. Out of the box, it's a generalist. Good at a lot of things, not a specialist in any. Finetune it to your work. Your domain. Your quality bar. Your non-negotiables. THAT is when it stops being a butter knife and becomes a scalpel.

I've finetuned mine for:

1. Production trading system development (10,000+ commits across three repos)
2. Blog writing with a distilled voice persona (built from my own writing over the years) plus a voice guard that catches AI tells before they ship
3. eBay listings where the output template has to survive eBay's weird HTML rules
4. CV, cover-letters, LinkedIn posts, and any professional writing that needs to sound like me, not ChatGPT's cousin. Same voice persona, same voice guard, applied wherever the writing needs to feel human-first
5. Deep research with a subagent swarm pattern
6. MCP server development for evidence-enforced GitHub operations
7. This blog. The whole site. Every post, every commit, every layout fix.

Same harness. Different edge. Same blade metal, just resharpened for the cut.

## Why I built it

Honestly? I did not set out to build a methodology framework. I set out to solve my own pain, and I built SST3 unknowingly. I only discovered the other frameworks LATER, at which point I ran proper deep-research comparisons and found that mine had features theirs did not, was simpler by design, and was customised to the work I was actually doing.

The pain was this. Raw Claude Code out of the box is noticeably better than ChatGPT for coding, and it is the reason my friend Bear told me to give it a shot. Good for short tasks. Terrible for anything longer than 30 minutes. It forgets what you told it. It introduces scope drift. It adds "helpful" fallbacks that hide bugs instead of failing loudly. It silently mocks tests so everything passes and nothing actually works. (I've been there. Many times. It's painful.)

The real question I kept hitting wasn't "can the AI code?", it was **"how do I make it much less likely that the AI ships garbage when I'm not watching, and much more likely that it hits the goal I set?"**. That is a governance question, not a prompt-engineering question. Not "what does the AI do", but "how do we know the AI did it right, and how do we make 'right' the more likely path?". AI is probabilistic. The harness shifts the odds. It does not erase them.

## The cowboy problem

Here's what Claude (or any LLM) does left unsupervised. I say this with love. I use it every day.

- It **takes shortcuts**. Skips the research stage. Dives into code before understanding the problem. Ships stuff that passes tests but doesn't actually work.
- It **silently falls back**. Can't find a config value? Defaults to zero. Missing data? Returns an empty string. You only find out 3 weeks later when a trade didn't execute or a report showed £0 revenue.
- It **mocks tests to pass**. Genuinely. It'll add `**kwargs` to a mock that silently swallows every argument you pass, and the test passes with a smile, and the real code doesn't propagate a single parameter.
- It **fires and forgets**. Launches a background job. Moves on. Never checks whether it finished, whether it got stuck, whether it errored out, or whether the output was actually produced. "Started" gets treated as "done". Broken gets treated as "done". A stack trace on stderr gets treated as "done". If nobody looks, nobody knows.
- It **ticks the boxes without evidence**. Marks a checkbox as complete. No proof. No artifact. No way to audit what actually happened.
- It **finds gaps and keeps quiet about them**. Spots a bug, an inconsistency, a bit of dead code, an obvious edge case nobody handled. Says nothing. Carries on. And then quietly **defers scoped items for no reason**, pushing "low priority" stickers on things it simply did not feel like doing. Every deferral is another gap added to the pile.
- It **loses context between sessions**. Starts fresh. Forgets the decisions you made yesterday. Contradicts itself. Re-implements things that already exist.
- It **duplicates work**. Instead of grep-ing for an existing helper, it writes a new one. Three versions of the same function drift over time. Nobody notices until something breaks.
- It **skims with grep, never traces**. It searches, finds a match, and stops. It does not track the function through every caller, every dependency, every config key, every workflow it touches. So when it makes a change, it has no idea if the change is good or bad. It just made it. Then stuff breaks somewhere else in the system that it never bothered to look at.
- It **applies fixes in isolation**. You ask it to fix one thing, it fixes that thing, and silently breaks three others because it only looked through one lens.
- It **spews confident hallucinations**. The tone never changes whether it's telling you the truth or inventing API calls that don't exist.
- It **stops mid-work to ask permission** for things that are obviously fine. Or (worse) doesn't stop when it SHOULD and blows through a destructive action.

It's a cowboy. It's a loose cannon. It's the Wild West with extra confidence. Brilliant when directed. Chaos when not.

[SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) is the sheriff.

## How the harness clamps the cowboy

Plain English, how it actually stops each of those:

- **Ordered workflow, no skipping.** Five stages (Research, Issue Creation, Triple-Check, Implementation, Post-Implementation Review). Each has entry and exit criteria. You can't dive straight into code because the code stage literally can't start until research is written down and verified.
- **`/Leader 1-6` stage commands.** The workflow above is not a wiki page you hope the AI read. It is a set of refined prompts (`/Leader 1` through `/Leader 6`) that invoke SST3 for each stage. `/Leader 1` dispatches the research swarm. `/Leader 2` drafts the issue. `/Leader 3` sanity-checks scope and creates the GitHub issue. `/Leader 4` implements. `/Leader 5` ships. `/Leader 6` runs the final audit. Each prompt pre-loads the standards, the anti-patterns, the sub-agent discipline rules, and the stage-specific guardrails. You type one slash command, the AI does the stage properly, and you cannot accidentally skip ahead because each stage signs off with a message pointing you to the next one. Refined prompts doing a heavy lift so the human doesn't have to re-explain the rules every session.
- **Fail loudly, never silently.** Banned defaults. Banned fallbacks. Banned "graceful degradation". If a config is missing, the system crashes at startup with a clear error message. You WANT it to crash. Loud failure is a gift.
- **Test the real pipeline, not a cartoon of it.** Rule: for anything touching a workflow, run a real end-to-end sample invocation (real CLI, real database, small basket of inputs) before closing the issue. Mocks that swallow kwargs are banned. Every parameter must be asserted explicitly.
- **Monitor, don't fire-and-forget.** Every background job must be tailed. Every script's exit code checked. Every side effect verified. "Started" is never "done".
- **Evidence-enforced checkboxes.** There's a custom MCP (Model Context Protocol) server that literally will not let the AI mark a checkbox as complete without pasting the proof (commit hash, test output, file diff, whatever). Accountability by construction.
- **Surface every gap, no silent deferrals.** If the AI spots a bug, a dead code path, an edge case nobody handled, an inconsistency in the data, it has to raise it. "I noticed this but it wasn't in scope" is not an acceptable answer. Every gap goes on the fix list. "Low priority" is banned as a deferral excuse. The only valid skip is a confirmed false positive, and the reasoning has to be written down with evidence.
- **Structured handover between sessions.** When context runs out, the AI writes a handover document to the GitHub issue FIRST. The next session reads the issue and picks up exactly where the last one left off. Nothing's in the AI's head alone.
- **Grep before writing anything.** Literal rule: before creating any new file, helper, rule, or function, search the codebase first with multiple synonyms. Update existing in place if found. Cuts duplicate drift way down.
- **Trace before changing.** Grep alone is surface-level. Before the AI modifies a function, config key, or contract, it has to trace every caller, every dependency, every workflow it touches, and understand the knock-on effects. If it can't explain the full picture, it doesn't get to make the change. That's how you stop "I fixed one thing and silently broke three others".
- **Single-source edits.** Every change has to pass every lens at once (voice, craft, wiring, standards). No "fix voice then break craft then patch wiring" zig-zag.
- **3-tier automated review before every merge.** Ralph (named after Ralph Wiggum, if Ralph can spot it, it's really wrong). Haiku catches surface issues (debug prints, missing files). Sonnet catches logic issues (null propagation, scope drift). Opus catches architectural issues (wiring across modules, contract mismatches). Any tier fails, you go back to Haiku and restart. No shortcuts.
- **14 pre-commit hooks.** Token budget, hardcoded parameters, silent fallbacks, secrets, voice tells, path drift, large files, merge conflicts. The commit literally gets rejected if you violate one. Good standards are the ones that are automatically enforced. Paper standards are just stories people tell each other.
- **"Proceed" never means "bypass process".** This is a big one. When a human says "okay, go ahead", the AI treats it as "proceed using the full process" not "skip the sweeps and Ralph reviews". Human approval doesn't remove guardrails.
- **Keep going until done.** The AI is specifically told NOT to stop mid-work to check in unless it's at 80% context, about to do something destructive, or genuinely stuck after investigation. Premature stopping is its own anti-pattern with its own rule.

That's the harness. It doesn't make Claude "smarter". It makes Claude ACCOUNTABLE. Every decision has a trace. Every shortcut has a gate. Every failure mode has a rule pointing at it.

Is it perfect? No. Is it very very much better than Claude Code out of the box? Absolutely yes.

## Not just an IT problem

Here's where most people stop reading because they think this is developer stuff. Don't.

Every department has its own SMEs (Subject Matter Experts, the people who actually know the job). Every department drowns in repetitive work. Every department has quality standards that get skipped under deadline pressure. [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) is NOT an IT tool. It's a methodology framework for wrapping AI with guardrails. And guardrails apply everywhere.

**Marketing.** Your brand voice is a voice profile. Your anti-vocab list (words your brand NEVER uses) is a guardrail. Your SEO checklist is a pre-commit hook. Your approval gates before a campaign goes live is a 3-tier review. The structure maps one-to-one. I literally built one for this blog so every new post gets scanned for AI tells before it goes live. Same playbook works for brand copy, ad scripts, press releases.

**HR.** Job description templates. Interview rubrics. Tone-of-voice guides. Bias sweeps. Every piece of HR content benefits from a voice guard and a factual-claim checker. The SME (your experienced HR lead) sets the rules. The AI produces the first draft. The harness enforces the standards. The reviewer spends 5 minutes instead of 30.

**Finance and accounting.** Regulatory disclosures. Audit-trail compliance. Report templates where a wrong number ends careers. A harness here is non-optional. You want fail-fast. You want evidence-enforced approvals. You want "no silent defaults". The same principles that stop an AI from silently mocking a failing test will stop an AI from silently rounding a tax figure.

**R&D.** Research protocols. Literature-review methodology. Hypothesis validation steps. The senior researcher's judgement becomes a checklist. Junior researchers follow the method. AI accelerates the grunt work INSIDE the method, not around it.

Pattern's always the same. SMEs set the rules. AI does the first pass. Harness enforces. Human reviews.

## Who benefits most

**Domain experts and SMEs.** You become a force multiplier. The harness captures your judgement as rules, templates, anti-patterns. The AI executes against your bar. You review the output with the eye of someone who can spot wrongness in three seconds. What used to take a week now takes a day. What used to take a day now takes an hour. (It's deeply satisfying when it clicks. Trust me on this one.)

**Juniors and people still learning.** This is the bit that usually gets it wrong and I want to be careful here.

AI with a well-built harness IS a good learning tool. The guardrails surface the standards. The Ralph Review pass/fail feedback teaches what "good" looks like. The anti-patterns list is basically "here are the mistakes your seniors already made, don't repeat them" as a reference card.

But.

Juniors should NOT depend on it. You need to learn the craft. You need to develop the attention to detail that only comes from doing the reps. If you let the harness do all the thinking, you'll look up in five years and realise you're still a junior, just with a shinier toolbelt.

Embrace it. Use it. Let it accelerate your learning. But also read the source. Do the work. Ask "why did the guardrail catch this?" and then go find out. The harness is the training wheels on a bike. Eventually you take the wheels off and you RIDE.

If you're still learning your field, the harness won't save you from bad judgement. You'll struggle to spot when the AI's output is wrong. You'll ship confident-sounding nonsense. That's not the harness failing you. That's trying to wear a hero suit before you've built the strength to carry it.

SMEs set the standards. Juniors learn by working inside them. That's always been how apprenticeships work. AI just speeds up the loop. It does NOT replace the apprenticeship.

## Why humans should WANT this

Here's the bit that doesn't get said enough. You SHOULD want to hand the mundane stuff to AI. Not because you're lazy. Because you're human.

Humans have an edge AI doesn't have. Creativity. Abstract thinking across 15 angles at once. The ability to hold two contradictory ideas in your head and find the third option neither of them saw. Genuine ingenuity. The weird leap of intuition that only makes sense in hindsight. AI isn't doing that right now and I don't think it's doing that any time soon. (People who disagree with me on this, I'm happy to be proved wrong. Watch this space.)

It was HUMANS who dreamed about going to the moon. Humans who wanted to fly. Humans who wanted to breathe underwater. Humans who looked at a dark room and thought "what if we could bottle lightning and hang it from the ceiling". The light bulb, the aeroplane, the submarine, the moon lander. None of them came from an algorithm. They came from a person staring at a wall, daydreaming about something that didn't exist yet. That is a uniquely human trick. Guard it.

So why are we spending our precious human hours on expense forms, data entry, boilerplate copy, formatting reports, chasing down the same five data points every Monday morning? That's not what humans are FOR.

The tasks that can be automated SHOULD be automated. That's not a threat. That's a gift. You get your brain back.

"But will AI take our jobs?" Not really. Not the way people fear. What it will do is shift the work. Less mundane. More thinking. More strategy. More creativity. More "what if we tried this completely different angle that nobody's thought of yet". The high-value stuff. The stuff AI can't figure out alone because it doesn't know your customers, your team, your instincts, your 20 years of hard-earned gut feel.

Companies are still made of people. Not the other way around. The companies that forget that will learn it the hard way. The companies that get it right will have humans doing human work at the top of their capability, with AI doing the grunt work underneath. That's the winning shape.

## Embrace it, don't avoid it

I keep hearing variations of "I don't use AI because it's unreliable / will replace me / hallucinates / doesn't understand my domain".

I hear you. But.

Every single one of those objections is solvable with the right setup. Unreliable? Add quality gates. Going to replace you? Not if you're the one directing it. Hallucinates? Add evidence-enforced checks. Doesn't understand your domain? YOU teach it the domain through your standards and templates. That's literally what a harness is for.

The people rejecting AI today are the same people who rejected spreadsheets in 1985 and email in 1995. They're not wrong about the problems. They're wrong about the solution. The solution is NOT "avoid it". The solution is "set it up properly".

And frankly? I'm a believer in Darwin's law. Survival of the fittest. Adapt or get adapted out. If you can't live and work in this AI tech age, you may need to change your day job. And soon enough, the company that hired you might just help you do that (not in the nice way). Harsh? A bit. True? Also a bit.

Better to be the person who learnt to work with AI than the person who got replaced by someone who did.

## Automation is compound interest

I automated a lot of my tedious work. Listing creation. Blog editing. CV iterations. Research digests. Literature sweeps. Chart scanning and automated trade strategies that used to eat my mornings, afternoons, and evenings. It took time to set up. Weeks in some cases. Worth every minute.

The complex workflows took longer. The trading platform. This blog. The custom MCP servers. Months of finetuning. The better part of a year in the heavier cases. Also worth it. I now have time I didn't have before. Actual time. The expensive, non-renewable kind.

What do I do with it?

I write this blog. I read more. I build experiments that have been sitting on my ideas list for literal years, on a home mini-lab stitched together from whatever I can find: laptop, Intel NUC, Chromebox, anything with a CPU and enough RAM to be useful. All of it powering the life automation that runs in the background while I get on with the rest. I work on passive-income ideas that were always one week away from starting. I do the research that the old me never had time for. The trading platform runs mostly without me. The eBay listings now take minutes instead of hours. The admin of having a life is down to maybe 30 minutes a day.

The rest is mine.

## How to get started

You don't need to copy my whole setup. Start small.

1. Pick ONE repetitive task you do at least weekly. Document it as a process.
2. Write down your quality standards for that task. What would "good" look like? What would "unacceptable" look like?
3. Turn the standards into a checklist. If it's a script, write a linter. If it's prose, write a word-ban list.
4. Get an AI to do the task. Let the checklist catch anything wrong.
5. Review. Refine the checklist. Run it again.

You've just built a micro-harness. That is SST3 in miniature. Now scale it to your second task. Your third. Your tenth.

The [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) repo is public on GitHub. MIT-licensed. Steal what's useful. Ignore what's not. Fork it, finetune it, ship it inside your own tooling. I wrote it to be a generalist with enough finetune points that it becomes a specialist in your hands.

Like the knife.

## The one-liner

If you take one thing from this post: **the AI doesn't know your standards. You do. A harness is how you teach the AI your standards and make sure it follows them.**

Everything else is implementation detail.

If you want the full reasoning on why I spend more tokens on scope than on code, I wrote that up separately: [Why I Spend More Tokens Refining Scope Than Writing Code](https://hoiboy.uk/posts/why-scope-beats-code/).

Watch this space. More posts coming on the specific bits. The Ralph Review system. The voice guard for writing. The MCP server for evidence-enforced GitHub operations. How I use subagent swarms for research. Plenty more where this came from.

And if you're sitting on a pile of tedious work thinking "there must be a better way", there is.

Go build your harness. Or steal mine.

Hoi x
<!-- iamhoiend -->
