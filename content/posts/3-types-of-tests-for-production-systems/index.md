---
title: "3 Types of Tests I Build for Production Systems"
date: 2026-06-04T12:00:00+01:00
categories: [tech-ai]
tags: [testing, ai, claude-code, production, trading-systems]
description: "Unit, workflow, and end-to-end tests are how I know a system works. What each one catches, why AI forgets the wiring, and the one final check that's all human."
---

<!-- iamhoi -->

You can build a thing that looks finished, runs without crashing, and is still quietly wrong. That's the part nobody warns you about when coding with AI. The code compiles, the screen shows numbers, everything *feels* done, and underneath, a calculation is off by a decimal or a function is sitting there never actually being called. With AI doing the typing, this happens more, not less.

So when I build something real, like my [automated swing-trading system](/posts/building-a-production-grade-trading-system-with-claude-code/), I don't trust "it ran." I trust tests (lots and lots of tests). There are three types I use to cover as many edge cases as possible and get to a reliable, robust system that's ready for production.

I've baked this straight into my [SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness): any system it builds has to ship all three tiers of tests by default. No skipping a tier just because a feature looks too simple to bother with (that's usually the exact bit that breaks later). That rule is the reason a build burns a lot more tokens than just hammering out the feature and walking away. It costs more up front. But a system with no tests is a system you can't refine, can't trust, and definitely can't put anywhere near real money. So I pay the tax.

Here are the three, smallest to biggest.

## 1. Unit tests: is this one cog correct?

The first tier is the boring one. But boring is necessary. Thousands of tiny tests that check correctness at the lowest level. Per-function. Per-calculation. Does this maths return the right number, does this helper handle an empty list, does this one little cog do exactly what it's supposed to.

I have a lot of these. Over 6,700 in the trading system alone (more than ten thousand once you count all the parametrised variants, where one test definition quietly fans out into hundreds of cases). They're cheap to run, they run on every change, and they catch the dumb stuff before it ever has a chance to grow up into a real bug.

Quick note on naming, because people muddle this (I did too). These low-level checks are *unit* tests. "Regression testing" isn't a fourth type sitting next to them, it just means re-running your whole suite after a change to confirm you didn't break something that used to work. So all three tiers below are your regression net. The unit tier is just the bottom of it.

Think of one piston in a car engine. You want to know that single part is machined right and does its job, on its own, before you bolt anything to it.

## 2. Workflow tests: are the cogs actually wired together?

Here's the gap AI loves to fall into.

Claude Code (or any other model) will happily write you a perfect function. Clean, correct, passes its unit test. And then forget to wire it into the actual workflow. The calculation exists. It's just never called. Nothing fails, nothing screams, the feature simply isn't there, and your green unit tests tell you everything's fine.

That's what the second tier is for. A module or a component, with all the functions that talk to each other, tested together. Not "does this part work" but "do these parts work *as a group*, in the different ways they're meant to interact." I push them through the combinations on purpose, because wiring bugs only show up when two correct things meet and one of them was never plugged in.

The piston is fine. Now does the engine actually run?

This is also where lazy testing quietly betrays you. A mock that swallows whatever you throw at it will accept a call that passes the wrong thing, and your test goes green over a bug. So the assertions have to check the real wiring, not just that *a* call happened. (Same energy as my [three-tier Ralph Review](/posts/shipping-ralph-review-trio/) for code: one layer is never enough.)

## 3. End-to-end tests: drive the whole car

The third tier is my favourite, because it's the closest thing to reality without being live.

I build tests that inject into the data streams, or feed in the input, that kicks off a workflow across the *entire* system. Then I get the AI to watch the data as it travels. Through the modules, the components, the helpers, all of it, and check what pops out the other end is exactly what should pop out.

{{< zoom-image src="pipeline.svg" alt="End-to-end test: known input flows left to right through the system's modules, components and helpers, and must come out matching the expected result." title="One end-to-end test" >}}

It's two checks in one. Data integrity (the numbers stayed right the whole way through) and wiring (every handoff between parts actually happened, and nothing failed silently in the dark). End-to-end, hence E2E, means start to finish with nothing mocked out in the middle.

Take the car out for a driving test. Not "the engine runs on the bench," but the whole thing, on the test track, behaving the way you intended.

## The trick that makes all of them work

Every one of these tests runs on pre-defined inputs where I already know the expected output. That's the whole game. I know what should come out, so if something else comes out, the test fails loudly and points at where it went wrong. No quiet shrug, no plausible-looking-but-wrong answer slipping through. A loud, ugly, unmissable failure. Then I kick off the AI to go investigate.

For the workflow and E2E tiers especially, this only works if the system was built with proper observability underneath. Clear logging at every step, alerts or messages when something breaks, and fail-loud errors that are actually readable so I (or the AI) can diagnose them fast. A test can tell you *that* something broke. Good observability tells you *where* and *why*. I won't go into that here, it deserves its own post, [which is now up](/posts/observability-and-logging-for-production-systems/).

## The catch nobody mentions: they need upkeep

I'll be honest about the cost. Build a system this way and every change you make afterwards means tests need updating and refactoring, sometimes many times over. The test tools are tools, and tools need maintaining to stay reliable. It's real ongoing work.

Worth it though. How else would you actually *know* what you built is working? So I get the AI to help build and maintain all three tiers as a system moves from concept, to beta, to a production release, and through every refinement after that. The tests grow up alongside the thing they're testing.

## The fourth test: human intuition

There's a final test, and it's the one no machine can run. It comes down to human intuition.

No matter how green every tier is, you still have to use the thing. Take it for a test drive on the real roads. For the trading system that meant running real tickers and just... letting it run. Reviewing every page and feature, clicking every button. Using it day to day. Watching whether it *feels* like it's behaving right.

That part is subjective, and you need an eye for detail to do it well. You have to notice when something feels slightly off, especially when it comes to calculations, metrics, grades, even when nothing technically failed. That instinct, that something feels off or doesn't seem right. It sends me back in, questioning and deep-diving with Claude Code at each step, to work out whether something really is wrong, or whether I'm just seeing ghosts and having a human hallucination.

Funny how we worry about AI hallucinating. We do plenty of it ourselves.

So that's the stack. Three tiers of tests that prove the parts, the wiring, and the whole machine. Then human intuition, the one thing no test suite can replace. The first three tell me the system is correct. The last one tells me it's right.

<!-- iamhoiend -->
