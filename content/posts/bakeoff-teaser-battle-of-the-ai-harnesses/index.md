---
title: "10 AI Harnesses. One Job. Watch This."
date: 2026-04-26
draft: true
categories: [tech-ai]
tags: [bakeoff, harness, methodology, sst3-ai-harness, ai-agents]
series: bakeoff
order: 0
description: "Ten AI coding harnesses. One frozen brief. One shot each. The winner ships into a live trading system. Watch this space."
---

## The Setup

<!-- iamhoi -->
A simple question. Which AI coding harness would actually ship code I'd put in front of a live trading system? Not the one that demos best on YouTube. Not the one with the prettiest agent graph. The one that gets the job done... when getting it wrong costs me real money.

I have been building a production trading platform for the last few years. Same [SST3-AI-Harness/framework](https://github.com/hoiung/sst3-ai-harness) (Single Source of Truth v3) underneath. Same five-stage workflow. Same Ralph review trio (Haiku, Sonnet, Opus, in that order, restart from the top on any fail). It works. It ships. It runs.

But every other week, some new agent framework shows up in my feeds. CrewAI! LangGraph! Smolagents! AutoGen-renamed-to-MAF! Each one promises to be the One True Way to wrangle an LLM into shipping real code. I'd been ignoring them (my harness/framework already works, why fix what isn't broken?) but the noise kept getting louder.

So I figured... fine. Let's actually find out. Properly.
<!-- iamhoiend -->

## The Itch

<!-- iamhoi -->
Most people pick a framework based on the README and a YouTube demo. I am running a bake-off.

Same brief. Same clock. Same scorecard. Ten harnesses, all aimed at the same job: build one autonomous controller feature for the production trading platform. The winner's code goes into the live system. The losers go on the shelf.

(Yes, this is going to take weeks. Yes, I know I could have just picked Claude Agent SDK and called it done. No, that's not the point.)

The point is I want to KNOW. Not "the docs look nice", not "the discord seems active", not "this guy on Twitter swears by it". I want to know which one ships. And the only way to know is to put them in the same room, give them the same job, and see what falls out the other side.
<!-- iamhoiend -->

## The 10 Contestants

<!-- iamhoi -->
Three lean floors. Four heavyweight frameworks. Two reference baselines. One home-grown experimental harness/framework. All in.

The lean floors are **Smolagents** (Hugging Face's minimalist runtime, the "if you can't beat THIS, why are you adding any abstraction at all" floor), **pydantic-ai** (Pydantic's bet on type-safe agent purity), and **OpenAI Agents SDK** (handoff-flavoured, the SDK successor to OpenAI's earlier agent experiments).

The heavyweights are **CrewAI** (multi-agent crews with explicit personas, the framework most people meme about), **LangGraph** (stateful directed-graph orchestration, currently the LinkedIn buzzword leader), **Google ADK** (OpenTelemetry-native, the only one that natively pretends to care about observability), and **MAF** (Microsoft Agent Framework, the AutoGen rename, Microsoft's enterprise pitch).

The reference baselines are **Claude Agent SDK** (Anthropic-native, as close to the model as you can get without writing your own loop) and **Agno** (the late entrant, Python-first, performance-focused).

And the home-grown one is **[SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness)** (Single Source of Truth v3). My own. Built from first principles before I knew LangChain or CrewAI existed, on top of twenty years of project management and engineering scar tissue. Currently runs both my production trading platform AND this very blog you are reading. Two production systems on the same harness/framework, two completely different domains... so the "domain-agnostic" claim is real, not theoretical. (I have written more about how SST3 reshapes itself per task in an [earlier SST3 deep dive](/posts/sst3-ai-harness-reshapeable-knife/), if you want it.)

SST3 is the bar. The other nine are graded against what it produces. If one of them beats it, I will say so out loud and adopt it. If not, the home-grown one keeps the seat. Both outcomes are interesting. Both are in scope.
<!-- iamhoiend -->

## The Rules

<!-- iamhoi -->
A bake-off is only worth reading if it is fair. The setup is deliberately, deliberately, deliberately boring on that front.

*Same input.* Every harness gets the same frozen brief, packaged as the same tarball. No live editing. No follow-up clarifications. What is in the tarball is what each harness sees... and that's it.

*Same time.* Eight hours of wall-clock. The clock starts when the harness begins. Stops when it stops. Or when the cap hits. Whichever comes first.

*One shot.* No second attempts on the same brief. No "let me re-prompt and try again". Whatever the harness produces in eight hours is what gets scored. The first run is the last run.

*Anti-fab gate.* Code that compiles but does not do what the spec says fails on a separate axis. A harness cannot win by producing plausible nonsense (the AI agent equivalent of lying with a straight face). Fail-loud beats fail-quiet, every time.

*Eleven-column scorecard.* Code quality, observability, verification, monitoring, trading safety, deployability, documentation, anti-fabrication, plus three weighted aggregates. Pareto sanity check. Documented tiebreakers, written down before the first run.

*Cooling-off and rest days.* Fixed running order, set in advance, with rest days between heavy runs to keep MY OWN measurement quality steady. (I am the dumbest part of this experiment. The bake-off is also a measurement of how well I judge the bake-off, and that needs sleep too.)

Full methodology lives in the public [bake-off repo](https://github.com/hoiung/bakeoff). Locked before the first run starts. So I cannot move the goalposts mid-experiment, no matter how much I might want to.
<!-- iamhoiend -->

## What's at Stake

<!-- iamhoi -->
The winner does not get a trophy. The winner's code goes into the next round of production controller enhancement. On a system that already trades against a real brokerage. With real money.

That is why the rubric is the way it is. If a harness ships impressive-looking code that fails on observability or trading safety, it is not useful to me. The measurement is "would I put this in production tomorrow", not "did the demo run and look pretty in the YouTube video".

It also means the cost of getting this wrong is real. I am not running this for fun (well, mostly). The result of the bake-off changes which harness/framework I bet on for the next year of work. Possibly longer.

Most people would just pick a framework from someone else's comparison blog post. I am writing the comparison blog post... by actually building production code in all ten of them.

Different angle. Same result. Much more reliable.
<!-- iamhoiend -->

## Watch This Space

<!-- iamhoi -->
The first run starts shortly. Per-harness postmortems publish here as one arc once all ten runs are done... not in dribs and drabs. Bookmark the site. Grab the RSS feed (yes, RSS, like it's 2007). Or just check back when the dust has settled.

The full methodology, the scorecard, the running order, and the rationale behind every design choice. All locked in the public [bake-off repo](https://github.com/hoiung/bakeoff). If you want to reproduce the experiment yourself, the templates will be there once the dust clears.

Until then... ten harnesses, one job, may the best one win.

Watch this space as the battle begins.
<!-- iamhoiend -->
