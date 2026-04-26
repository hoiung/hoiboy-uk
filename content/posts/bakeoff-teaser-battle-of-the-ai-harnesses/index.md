---
title: "Battle of the AI Harnesses: 10 Coding Agents, One Production-Grade Trading System"
date: 2026-04-26
draft: true
categories: [tech-ai]
tags: [bakeoff, harness, methodology, sst3-ai-harness, ai-agents]
series: bakeoff
order: 0
description: "Ten AI coding harnesses. One frozen issue. One eight-hour timer. The winner's code goes into a live trading system. Watch this space."
---

## Hook

<!-- iamhoi -->
A simple question. Which AI coding harness actually ships production-grade code under real constraints?

Not "which one demoes well in the marketing video". Not "which one has the prettiest agent graph". Which one, given the same shared issue and the same eight hours, produces code I would put in front of a live trading system without losing sleep.

I am running ten of them through the same gauntlet. One issue. One spec. One quality bar. Each harness gets the frozen brief in a tarball, eight hours of wall-clock time, no second attempts. The winner's code feeds into the next round of production controller work, on a system that already runs against a real brokerage with real money.

This post is the warm-up. The bake-off itself starts shortly. The full results, the per-harness deep dives, and the methodology autopsy land here once the dust has cleared.
<!-- iamhoiend -->

## The 10 contestants

<!-- iamhoi -->
The roster, in no particular order.

- **[SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness) (Single Source of Truth v3)**: my home-grown, methodology-led harness. Acts as the baseline bar everything else gets measured against.
- **Smolagents**: the lean floor. Hugging Face's minimal agent runtime. If a heavyweight harness cannot beat this, that is interesting in itself.
- **pydantic-ai**: lean and type-safe. Pydantic's bet on agent framework purity.
- **OpenAI Agents SDK**: lean and handoff-flavoured. The current SDK successor to OpenAI's earlier agent experiments.
- **CrewAI**: heavy on roles. Multi-agent crews with explicit personas.
- **LangGraph**: heavy on graph. Stateful directed-graph orchestration.
- **Google ADK**: heavy on observability. OpenTelemetry-native by default.
- **MAF (Microsoft Agent Framework)**: the AutoGen successor. Microsoft's enterprise pitch.
- **Agno**: the late entrant. Python-first, performance-focused.
- **Claude Agent SDK**: Anthropic-native reference baseline. As close to the model as you can get without writing your own loop.

Three "lean" floors. Four "heavy" frameworks. Two reference baselines. One home-grown experimental harness. Same issue, same clock, same scorecard.
<!-- iamhoiend -->

## The SST3 baseline

<!-- iamhoi -->
I built [SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness) before I knew LangChain or CrewAI existed. The patterns came out of twenty years of project management and engineering work, not from cargo-culting a popular framework.

It earns its place as the baseline because it is what I actually use, every day, on the production system being enhanced. If the bake-off proves that one of the off-the-shelf harnesses ships better code under the same constraints, I will say so out loud and adopt it. If not, the home-grown one keeps the seat. Both outcomes are interesting.

The bar is whatever SST3 produces. The other nine are graded against that.
<!-- iamhoiend -->

## How the bake-off stays fair

<!-- iamhoi -->
A bake-off is only worth reading if it is fair. The setup is deliberately boring on that front.

- **Equal input.** Every harness gets the same frozen issue, packaged as the same tarball. No live editing. No follow-up clarifications. What is in the tarball is what each harness sees.
- **Equal time.** Eight hours of wall-clock. The clock starts when the harness begins. Stops when it stops, or when the cap hits.
- **One shot.** No second attempts on the same issue. No "let me re-prompt and try again". Whatever the harness produces in eight hours is what gets scored.
- **Anti-fabrication gate.** Code that compiles but does not do what the spec says fails on a separate axis. A harness cannot win by producing plausible nonsense.
- **Eleven-column scorecard.** Code quality, observability, verification, monitoring, trading safety, deployability, documentation, anti-fabrication, plus three weighted aggregates. Pareto-frontier sanity check. Documented tiebreakers.
- **Cooling-off and rest days.** Fixed running order, set in advance, with rest days between heavy runs to keep my own measurement quality steady.

Full methodology lives in the public [bake-off repo](https://github.com/hoiung/bakeoff). It is locked before the first run starts so I cannot move the goalposts mid-experiment.
<!-- iamhoiend -->

## What is at stake

<!-- iamhoi -->
The winner is not getting a trophy. The winner's code goes into the next round of production controller enhancement on a system that already trades against a real brokerage.

That is why the rubric is the way it is. If a harness ships impressive-looking code that fails on observability or trading safety, it is not useful to me. The measurement is "would I put this in production tomorrow", not "did the demo run".

It also means the cost of getting this wrong is real. I am not running this for fun. The result of the bake-off changes which harness I bet on for the next year of work.
<!-- iamhoiend -->

## Watch this space

<!-- iamhoi -->
The first run starts shortly. Per-harness postmortems publish here as one arc once all ten runs are done, not in dribs and drabs. Bookmark the site, grab the RSS feed if you live in 2007, or just check back when the dust has settled.

The full methodology, the scorecard, the running order, and the rationale behind every design choice are all locked in the public [bake-off repo](https://github.com/hoiung/bakeoff). If you want to reproduce the experiment yourself, the templates will be there once the dust clears.

Watch this space as the battle begins.
<!-- iamhoiend -->
