---
title: "You Can't Fix What You Can't See"
date: 2026-06-04T13:00:00+01:00
categories: [tech-ai]
tags: [observability, logging, ai, claude-code, production]
description: "Observability and logging are what stop an AI-built system failing silently. What they are, why you build them in from day one, and how they pair with tests."
---

<!-- iamhoi -->

Here is a fast way to set yourself up to fail. Build a whole system with AI, or just vibe code your way to something that runs, and never once make it tell you what it is doing inside. It will look fine. It will click and load and show you numbers. And the day something goes wrong, you will be standing there in the dark with no idea what broke, or where.

That blind spot is what observability fixes. If you are building anything you actually want to rely on, this matters as much as the [tests I wrote about last time](/posts/3-types-of-tests-for-production-systems/). The two go hand in hand, and I will get to why.

## What observability actually means

Don't let the word put you off. Observability is pretty much what it sounds like: being able to observe what your system is doing. You feed data in, and you can watch how it changes shape as it travels through, like breadcrumbs you can follow to see where a number came from and where it ended up. Track and trace, start to finish.

## Think of your own body

Here is the way I think about it. A production system is a bit like the human body systematically, and your body is the best observability setup there is. You have sensors all over it for touch, sight and hearing. On the inside it has its own warnings too: pain, nausea, vomiting, swelling. Even sweat pulls double duty, cooling you down and quietly flagging when something is off (a cold sweat is your body raising its hand). None of it is decoration. It is your body telling you, loudly, that something needs looking at. Pain and swelling in your abdomen, for example, tell you there is a problem somewhere in that area. It may not be enough to know exactly what is wrong, but you know where to tell the doctor to look, so they can investigate further, pinpoint the exact spot and cause, and come up with a possible fix.

A system you build needs the same thing. Its own senses, its own way of saying "this hurts, check here." Building one without that is like putting on a blindfold and trying to get from your house to somewhere across town, however far away it is. Why would you do that? You wouldn't cross a road without looking first, right? That would be dangerous! Shipping a system you can't see inside is the same kind of bet, it just takes longer to hurt you.

## Logging tells you when it works, and when it doesn't

Logging is the one form of this I lean on most. It is just a running record of what happened, something I can pull up and read myself, or hand to the AI and say "here, you read it, tell me where this went wrong." Nothing clever. A system that writes down what it is doing as it does it.

This is the whole point. Good logging tells me when the system is behaving the way it should, and just as importantly, when it isn't. When something breaks, I want it to break loudly. A big, ugly, unmissable error, not a quiet shrug that swallows the problem and carries on like nothing happened.

Because otherwise, how would you ever know? How do you know the thing you built is actually working, and not just looking like it is working? You can't. Not without it telling you.

## It is not only logs

Observability turns up in places you might not think of as observability at all.

That little confirmation tick that pops up after you click submit? That is a form of it. A signal back to you that the thing you asked for actually happened. But here is the catch, and it is a big one: that tick has to be earned. It needs to be wired to actually check the data was processed, or the job really kicked off, before it shows you the green light. A tick that fires the second you click, without checking anything, is worse than no tick at all. It is lying to your face.

An error message on a dashboard when one of your processes has fallen over is observability. So is an alert. I could keep going, but you get the idea. Anything that lets you, or the AI, see what the system is doing counts.

## Build it in, don't bolt it on

Here is where it ties back to the tests.

Observability is what lets you build the [three types of tests](/posts/3-types-of-tests-for-production-systems/) in the first place. The two work hand in hand to take a system from a rough concept, to a beta, to something genuinely ready for production. Without them, it isn't production ready. Full stop. Because the day something goes wrong, and it will, you won't know what went wrong or how to fix it.

And you have to build it in as you go. Bake it into the design from the start, not bolt it on later once you are already in trouble. I treat it as part of building the thing, not a chore for afterwards. It is the same rule my [SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness) bakes in: structured logging and fail-loud errors go in at the same time as the feature, never after the first incident.

## The gaps you can't see

Now, observability isn't bulletproof. I want to be honest about that.

You will leave gaps. The AI will leave gaps. And it is exactly these gaps that bite you, because when a system breaks in one of them, the failure gets swallowed up. No log, no error, no tick. Just data that quietly went in somewhere and never came out, and you staring at the screen trying to work out whether anything is even wrong.

{{< zoom-image src="observability.svg" alt="Data flows through three steps to a result. The first two steps each drop a breadcrumb onto a log trail. The third step fails silently with no log, so the data is swallowed and never reaches the result." title="A gap with no log is how data goes missing quietly" >}}

This is where a decent logging system earns its keep. It helps you pinpoint when and where the data flow disappears. And it is the other half of why the three types of tests matter so much. They track and trace your entire system end to end, and in doing so they flush out these observability gaps so you can fill them in. You end up with something cohesive, wired together properly, where you can follow one piece of data all the way from input, through every transformation, to the expected result at the other end.

## The last layer is you

There is one last layer, and it is the same one I finished on last time. You.

In the tests post I called this the fourth test, the one no machine runs: human intuition. That nagging feeling when something is off, even when every log is green and every test has passed. And here is what I have come to see: that feeling is observability too. When something seems wrong, some sensor in my human body is firing and setting off the gut feel, the same way a log line or an alert goes off inside a system. My instinct is just my own body's warning light.

Is the output what you expected, or is it way off? Sometimes it is genuinely hard to tell. Even I struggle with it. But when something is properly off, you will feel it. You notice. That human instinct is worth more than people give it credit for, so use it. The logs and the tests tell you what the machine can measure. You are the one who can look at the whole thing and go, "no, that's not right."

So that is the pair. Tests prove the parts, the wiring, and the whole machine. Observability is what lets the tests see anything at all, and what lets you and the AI find the fault when something slips through. Build them both in from the start, use your own senses on top, and you might just end up with something you can actually trust.

<!-- iamhoiend -->
