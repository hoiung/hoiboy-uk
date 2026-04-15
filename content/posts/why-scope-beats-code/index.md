---
title: "Why I Spend More Tokens Refining Scope Than Writing Code"
date: 2026-04-15
categories: [tech-ai]
tags: [ai, claude-code, sst3, governance, project-management]
slug: why-scope-beats-code
description: "SST2 taught me the hard way. The scoping step costs tokens up front, but it is a tenth of what bad scope costs you later."
---

<!-- iamhoi -->

There was a version of me, about two years back, who thought the smart move was to point an AI agent at a problem and let it rip. Five agents. Ten agents. Fire away. Maximum throughput. What could go wrong.

A lot, as it turns out.

## What SST2 taught me

Before [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) there was SST2. SST2 looked like most mainstream agent frameworks still do. One orchestrator, a pool of specialist agents, coordination messages flying between them, and every agent holding a loaded write-access permission. Think LangChain or CrewAI shape, with my own guardrails welded on the side.

It was a disaster.

Some of that was my inexperience. Some of it was the tooling at the time. A big chunk of it was the 200K context window Claude was working with in late 2024, which was never going to hold a shared mental model of a production codebase across five concurrent agents. The agents would each pick their own direction. Each one confident. Each one writing code. Each one completely unaware that another agent had already written something contradictory three minutes earlier in a different file.

It was like letting five cowboys fire pistols in the same saloon. Nobody hit what they were aiming at. Everybody left a mess.

The worst part was that you only felt the pain months later. Long after the agents had finished and I'd moved on. By the time I noticed the damage, there was no memory of which agent changed what, or why. Debugging became archaeology. Digging up old bones to figure out why the wall was leaning.

I suspect my tradebook system still has stale, contradictory code from that era. I tried to clean it up. I genuinely did. Every time I thought I was done I'd find another buried fossil. At some point you just accept it. The production code has legacy technical debt I haven't fully exorcised, I've moved on, and the rule now is that new code doesn't touch the old mess or accidentally integrate with it.

That was the lesson. Multiple writer-agents create chaos that compounds silently. The chaos is invisible the day you ship. It shows up six months later when the whole thing starts behaving oddly and nobody can tell you why.

## Build it like Lego

So SST3 took the opposite route.

Focused. Narrow. One main orchestrator agent owns the writing, always. Subagents go out like a research team, not a coding team. They read, they analyse, they report back. They never touch the code. Each subagent also gets pointed at a different angle than the previous ones, so the orchestrator ends up with a 360-degree view of the problem instead of five copies of the same answer.

Then every angle gets double-checked and triple-checked by a second layer of subagents with a deliberately different prompt. The orchestrator verifies every finding against the actual source file (subagents can hallucinate too), and only then does the code get touched. One orchestrator. One writer. One source of truth for progress.

I think of it like Lego. One polished piece at a time. Each piece has to be gold-quality before it slots in next to the others. You do NOT stack two half-finished bricks and hope they'll settle. That is how you get a tower that leans on day one and falls over on day ninety.

This is the opposite of how most AI frameworks think about throughput. SST3 doesn't care how many agents you can run in parallel. It cares how few clean pieces you can ship per hour, with zero rework.

Slower per piece. Dramatically faster overall. (And much, much less archaeology later.)

The 1M context window that arrived in 2025 made this practical across bigger projects. The orchestrator can hold the Issue, the standards, the research, and the full diff without spilling context anywhere. The subagents absorb the high-volume reads on its behalf. The orchestrator stays coherent. The code stays coherent. No more cowboys.

## Why I spend more tokens on scope than on code

Here is the bit that surprises people.

Most of my tokens do not get spent writing code. They get spent refining the scope before a single line of code gets written. Research subagents. Issue drafting subagents. Sanity-check subagents verifying the draft against the research. Opposite-scoping checks. False-positive sweeps. Before/after illustrations for every change so the before can be compared against the after when we're done.

Sounds excessive, right? It is not.

The biggest killer of any project is unclear instructions and scope that is not well-defined. You can have the smartest team in the world and the best tools money can buy. If the scope is fuzzy, the output is fuzzy. Worse, you only discover the fuzziness AFTER you have already spent money and time building the wrong thing.

This is the single biggest lesson from two decades of Project Management, IT engineering, running my own businesses, and leading teams through plenty of failures and a fair number of successes. Taking the first step in the right direction is the most important decision you make. It is like having a map of where you want to get to. There are many routes. You want to pick the one that dodges the obstacles, challenges, and gotchas that would otherwise stop you from getting there.

I find it far cheaper to have a clear plan that is still flexible to changes than a loose plan that gets lost or misinterpreted. The loose plan costs you later. You look up months down the line, realise you have drifted further from the goal, and then you pay twice to find your way back. Cleaning up bad code is hard. Sometimes genuinely painful. Sometimes the scars never fully heal once the bad code has shipped to production.

This is not a PM cliche. This is somebody who has lived through the cleanup three or four times and does not want to live through it again.

## The snowball nobody warns you about

Here is the sneaky part about gaps in scope. They do not announce themselves on day one.

Small gaps sit there quietly. Every new feature you build on top of them inherits the same weak foundation. Miss a gap this week. The next piece layers on top of it. Then the one after that. Before you know it, you have a snowball rolling down the hill, and by the time you notice, it is the size of a house.

You end up with a fragile production system that breaks the moment the wind changes direction. A trading strategy that works on Tuesdays but somehow loses money on Thursdays. A checkbox that ticks itself without evidence. A config key that nobody reads. A test that passes because the mock silently swallowed the argument it was supposed to check.

None of those sound like "the project is failing". All of them quietly erode the ground under it. One by one. Month after month.

This is what technical debt actually is. Not a backlog of todo items. A slow accumulation of half-decisions that compound in interest like a credit card you forgot you signed up for.

And SST3 is built specifically to stop that snowball from forming. Every gap gets flagged at scope time. Every checkbox needs evidence before it ticks. Every phase gets reviewed by three different models at increasing depth (that's Ralph Review, named after Ralph Wiggum; if Ralph can spot it, it is really wrong). Every silent fallback is treated as a bug, not a feature.

There is a specific reason I layer three reviewers instead of one. A single reviewer gets blind spots. Two reviewers might share the same blind spots because they were trained on similar data. Three reviewers with three different prompts and three different depths catch different things. Haiku is cheap and quick, so I use it for surface problems (missing files, unchecked boxes, debug prints, obvious naming issues). Sonnet goes deeper into logic (null paths, fallback traps, contradictions between the scope and the implementation). Opus does the architectural audit (overengineering, silent coupling, design drift). If any tier fails, the orchestrator fixes and restarts from Haiku. No shortcuts. No "looks good to me" without evidence.

The point is not to be perfect. The point is to stop the rot before it has somewhere to sit.

It is more expensive per piece in tokens. Obviously. You are spending tokens on research, on verification, on triple-checks, on review. But it is a magnitude cheaper overall, because you are not constantly rebuilding on top of foundations that were already rotten.

Pay a bit more in the planning phase. Pay a fortune less in the cleanup phase. There is no third option. There is only "pay now" and "pay ten times more later".

## The three ways AI quietly goes off-piste

If I had to summarise two years of AI scar tissue into three bullets, it would be these:

**1. It makes things up.** Confidently. With citations. You ask for an acronym expansion and it hands you a plausible-sounding phrase that simply is not true. I have watched an AI invent a project name from nothing, repeat it three times across a conversation as if it were fact, and only back down when I dropped actual source files in front of it. If you do not triple-check claims against a primary source, you will ship fiction. (This has happened in this very workflow. Yes, in the post you are reading right now. The harness is what caught it.)

**2. It overengineers.** You ask for a two-bullet summary. It returns a three-phase implementation plan with a decision gate, a Ralph review, and a compact break. You ask it to trim a README section. It tries to restructure the whole file and front-load the install instructions you did not ask to touch. Agents love adding things. They love making scope bigger and more "complete". What you wanted was smaller, faster, simpler. What they deliver without guardrails is bigger, slower, busier.

**3. It does the opposite of what was agreed.** This one is the quietest and the most dangerous. You agree on direction A in the chat. Five minutes and two subagents later, the implementation is subtly doing direction B. Not defiant. Not malicious. Just drift. The agent followed the last piece of context it prioritised, and the last piece was not the user decision from earlier. Without an explicit "opposite-scoping check" built into the process, drift wins more often than it should.

These are the failure modes the harness exists to catch. Scope-first is how you give yourself the hooks to notice any of the three before they hit production. Each one compounds if unchecked. Each one is cheaper to catch at scope time than at cleanup time. None of them are theoretical. All three have happened to me, in real work, inside real shipped code, before I learned to scope properly.

## The one-liner

If you only take one thing away from this post: the AI doesn't know your standards. You do. A harness is how you teach the AI your standards and make sure it follows them. Scope is the bit where you teach the harness what "good" looks like. Skimp on that step and the rest of the system cannot save you.

I spend more tokens on scope than on code. It is not a quirk. It is the whole method.

If you want the longer story about why the harness exists and how the cross-department stuff works, I wrote that up separately: [SST3-AI-Harness. Why I Built a Hero Suit for AI.](https://hoiboy.uk/posts/sst3-ai-harness-reshapeable-knife/). If you want the code and the repo, [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) is public. Clone, install, and give it a weekend. The scoping step feels heavy the first time. By the third Issue you will wonder how you ever shipped anything without it.

<!-- iamhoiend -->
