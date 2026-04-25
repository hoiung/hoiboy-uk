---
title: "Ultrathink Mode. Why I Keep Turning It Off."
date: 2026-04-18
draft: false
categories: [tech-ai]
tags: [claude, claude-code, llms, ai-workflow, productivity]
slug: overthink-mode
description: "Claude's highest effort setting burns more tokens than it saves. I call it overthink mode. Nine months of experiments, middle every time, across every model."
---

<!-- iamhoi -->

Every time Claude ships a new model or variant, one of my first jobs is to check the effort setting. Arrow keys until I land in the middle. Used to be middle of three. Now middle of five. Every time.

Claude Code currently gives me five steps on the dial: low, medium, high, xhigh, max. There's also an auto mode, which I never use (I'd rather not leave the setting to the UI). Across tools the top tiers go by different names. Ultrathink. Max mode. Extended thinking. Whatever the marketing team picked that week. I call them overthink mode. Because that's what they do.

## The pitch vs what actually happens

The pitch is simple. Crank the effort up, the model thinks harder, you get better answers. Sounds great! Who wouldn't want the smartest version of the smart thing?

Reality is different. Ultrathink burns through tokens the way a teenager burns through pocket money. You hand it a simple fix (with the answer already written out for it, in plain English), and instead of doing the one-line change, it goes off to "think about it" for a while. Comes back with a three-file refactor, a new abstraction you didn't ask for, and a paragraph explaining why your original request wasn't quite right.

Now you're spending more tokens telling it to undo the things you didn't ask for. Then more tokens again, because the undo "needed improving". By the time the simple fix is actually in, you've burned five times the tokens and twice the wall-clock time. For a one-liner.

I've not found a single use case where max effort doesn't fail drastically. Not one. It either overengineers, or it derails, or it starts doing weird shit in a direction nobody asked for.

What makes it worse is the way it overrides the harness. The harness I run has an explicit no-overengineering rule and a "read the chat for what we already agreed" rule. Max effort blows past both. Goes independent. Disconnects from the harness, disconnects from me, isolates itself in its own overthinking head, and then it's off. Doing. Doing. Doing. Stuck in its own little world implementing away, while I'm sat there waiting for the one-line change I actually asked for.

## The other end is just as bad

Low effort isn't where I keep the dial either. Drop it all the way down and the model stops checking itself. Misreads the file, skips the part of the ask it didn't feel like doing, writes code that compiles but doesn't do the thing. Different failure mode, same net result. Token waste, back-and-forth, frustration.

(Honest disclosure: I've not lived with low and medium for as long as the top tiers. The pain at the top is what made me dial back. The middle is what stuck. Speaking from my own experience, not a survey.)

Xhigh and max overthink. High sits in the middle of the five. High wins.

## My release-day ritual

Every time a new Claude model drops (Opus something, Sonnet something else, Haiku whatever), the effort setting resets on me. New model, same arrow-key shuffle. Open settings, arrow down to the effort row, skip past auto (never use it), step past low and medium, step back from xhigh and max, land on high. Done. Carry on with the actual work.

I've done this so many times it's pure muscle memory now. I've been experimenting with effort levels for the last nine or ten months, across every Claude release, and on ChatGPT's reasoning knob when OpenAI added one. Different names, different tier counts (Claude Code alone keeps changing how many steps and modes live on the dial), same dial underneath, same answer every single time.

Middle tier. Every model. Every release. Best of both worlds.

The tiers keep changing. The concept stays the same. That's the other reason I anchor on "the middle" as the rule, not on whichever label happens to hold it this quarter. The conceptual middle survives every UI reshuffle. Specific labels don't.

## Why balance wins (most of the time)

Life is about balance. I think AI is the same.

High-effort modes lean too hard into exploration. They go wide, consider alternatives nobody asked them to consider, second-guess the clear instructions you already gave. Low-effort modes lean too hard into execution. They go fast, skip context, ship something half-correct. The middle is the only setting that respects the instructions you already wrote, without spiralling off into a philosophy essay about them.

Same pattern on ChatGPT before I moved most of my work across to Claude Code. Cranked up to the top reasoning tier, got long-winded answers that missed the point. Dropped to the bottom, got fast answers that missed the point differently. The middle tier was the one that just did the thing.

Balanced things win. Not always, but most of the time, the middle road is where the good work lives.

## What I noticed running the harness

Most of my day is Claude Code driven through the [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) I built (it orchestrates research, review, implementation, and verification across multiple agents). When you're running dozens of automated tasks a week through a setup like that, you notice the patterns fast. The one that kept showing up: every time an agent was cranked to xhigh or max, the wall-clock time ballooned and the output quality dropped. Same task in the middle tier finished cleaner and cheaper.

The model didn't get dumber. Thinking harder just isn't the same as doing better work. The harder the model is told to think about a clearly-specified task, the more ways it invents to reinterpret the task. Clarity is a finite resource. Burning tokens on rethinking the ask erodes it.

Same thing humans do. We overthink. We overcomplicate. We overengineer. Sometimes KISS (keep it simple, stupid) is all that's needed to make progress.

## The setting I reset after every new release

If you're running these models day in, day out, here's the one setting I'd ask you to audit.

Open Claude Code (or ChatGPT, or whatever you're using). Find the effort dial. On Claude Code right now it's a five-step ladder (low, medium, high, xhigh, max) plus an auto mode I'd leave alone. Check where yours sits using command "/effort". If it's at xhigh or max, nudge it back. If it's at low or medium, nudge it up. Park it on high. The middle of the five.

Has anyone else run into this? I can't be the only one hitting the same pattern every release. Overthink mode sounds like a feature. In my experience it's a tax. (My friend Bear loves it. I don't. He probably has a use case I haven't run into.)

Middle every time. Nine or ten months in, same answer.

<!-- iamhoiend -->
