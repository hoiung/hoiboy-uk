---
title: "Why Does AI Hallucination Keep Happening?"
date: 2026-06-15T09:30:00+01:00
draft: false
categories: ["tech-ai"]
tags: ["ai", "llm", "context-window", "memory", "hallucination"]
description: "Forgetting, making things up, inventing features you never asked for. My plain-English take on why AI hallucinates, after far too many hours with it."
---

<!-- iamhoi -->

You have used an AI chat at some point. And at some point, it forgot what it was supposed to be doing. It ignored things you asked it to do. It made stuff up. It invented a feature you never asked for, then carried on like that was always the plan. And once in a while it just ignores you completely, no matter what you type into it.

People have a name for this. AI hallucination, or something along those lines. We all know what it looks like by now. What almost nobody explains is *why* it happens, and how. So here I am, writing about it based on my own experience and observation.

I have seen AI hallucinate so much, and in so many different ways, that I ended up building my own harness around it. Scripts, rules, standards, loops, workflows, whatever it took to stop it going off the rails or doing cowboy shit (destructive changes, or architecture and design logic that is the exact opposite of what was actually spec'd). And even with all of that, it still happens.

So we know roughly what happens when AI hallucinates. The question not many of us stop to ask is the obvious one. Why?

## First, a disclaimer

Before you take any of this as gospel: I am no brain expert, and I am no large language model (LLM) engineer who builds the tiny details of these things. But I have used AI far more than most people, and more than most tech engineers I know, so I reckon I can explain it in my own way. I hope it helps you understand a little, from where I am sitting. This is just my perspective.

The way I see it, AI behaves a lot like an actual person. It might handle certain tasks better than we can, sure. But it was humans who built it, and they built it from an understanding of how the human brain thinks. We have basically spent years trying to reverse engineer how the mind works, then turn that into code. And here is the bit we keep forgetting. Even as humans, we have a capacity. We have limits. So does the thing we built in our own image.

## How memory actually works

Most of this comes down to memory. So how does memory work?

I understand memory in a logical way, not the way a brain surgeon would. I spent years studying it, mostly trying to improve my own, and nearly everything I read came back to the same two things. Short term memory and long term memory. Why we need both. And why we also need to forget.

Forgetting is not a weakness. It is a feature. Your brain has to forget, otherwise it overloads, and it ends up clinging to stuff that does nothing for your survival. (I will skip the part about how movement and emotion help you hold on to memories. Let us keep it simple. Short term and long term.)

During the day you are constantly storing short term memory, and pulling it straight back out again. You read three things off a shopping list, walk down the aisle, and grab them, otherwise you would forget the moment you looked up. At the same time you are pulling from long term memory without even noticing. You know which bank card you want to pay with, and you know how to pay, because money matters that much in this lovely capitalist world. You glance at a price and think, bloody hell, that has gone up since last month. We are ridiculously efficient. We remember a lot. We also forget a lot. In fact we have to forget far more than we keep.

## AI has memory too, sort of

AI is similar, in its own way, though it is also held back by the limits of today's hardware and software. It has a kind of short term memory: a cache sitting in RAM (your computer's working memory), or small working files like JSON. I would call it shorter term memory, honestly. What it does not really have yet is long term memory. (I am not even sure I would count a CLAUDE.md or an AGENTS.md file as proper long term memory. A starting point, maybe. A note that tells it where to begin.) For anything more permanent it reaches out with fetch tools like RAG (retrieval-augmented generation, the bit that goes and reads files or a database before it answers you). In a way, we have tried to recreate memory inside a digital workflow.

None of that quite answers why it hallucinates. But it builds the picture. Because the single biggest reason AI wanders off into la-la land is something you have probably heard of by now. Context memory. And, again, almost nobody explains what context memory actually is.

## So what is context memory?

About six months ago, context memory sat at around 200K. This year we crossed into 1 million (1M) for the newer models, the Claude Sonnet upgrade and the Opus models.

The way I see it, context memory is working memory. The capacity of one chat window. (Most people call it the context window. I call it context memory because it fits the way I have been describing all this, but it is the same thing.) It is the short term workspace where your prompts, and the AI's input and output, all live while you work inside that one chat.

But how much is that, really? 200K, 1M, those numbers mean nothing to a normal person. So let me put it in context (no pun intended).

It is measured in tokens, which are just chunks of text, not quite the same as words. A rough rule of thumb is that 1,000 tokens works out to about 750 words. An average novel runs somewhere between 70,000 and 100,000 words. So 200K tokens is about two novels' worth. And 1M is somewhere around eight to ten novels.

You are probably thinking, that is loads. All those words, in a single chat. Especially a million.

Wrong.

## Still just scratching the surface

Think about what real work actually involves. A whole platform. A system. Large, messy, complex databases. The entire internet. Years of knowledge and hard-won expertise. That is a world away from the two-or-so books, or even the eight to ten, that today's models can hold in one chat without losing the plot.

So it always surprises me when people lean on AI like it knows everything, and follow its advice without a second thought. A single chat can only take in a small slice of all that. Even a whole swarm of them working together still struggles. AI is still just a tool, and it is only ever scratching the surface of any real subject matter or domain expertise.

That is exactly why humans are not getting replaced any time soon. And if they ever are, then we have a serious problem! I suspect a lot of the corporate cuts you hear about are either using AI as a convenient excuse to downsize, or they are a mistake that someone will be quietly trying to undo before long.

## It fills up faster than you think

It fills up far quicker than you would expect. And a decent chunk gets burned while the AI pokes around trying to work out what you actually want from it. As the context fills, the older 200K models started to crack around the 70% mark, and from there the hallucination got worse fast. Like falling off a cliff. That is more or less why they capped them at 200K in the first place. With the 1M window, I start noticing it more around 50 to 60% full.

The longer the chat runs, the less you can trust it. Context bloat. It has more and more variables to juggle, more relationships to build between all of it, more data to make sense of, all so it can hand you back something a human understands. That is why I lean on guardrails and loops inside a harness to keep it sane a bit longer, or to force a compact (squash the chat down, summarise it, hand it over, so a long session can keep running without losing the plot).

So in reality, 200K or 1M is not a lot. First you feed it the initial context just to get going. Then you factor in the waste: the wrong turns in its searches, the corrections you have to make, and that nasty drop-off once the window starts filling. By my rough reckoning, that leaves you maybe 25% of genuinely useful, high-quality work.

Shit, isn't it...

But knowing that is the entire point. It is what helps you cut the hallucinations down, and keep as much quality in your work as you can. Because the moment a hallucination creeps in, it does not just cost you that one bad answer. It quietly creates more work for you to find and fix later, often long after you have moved on. Anyone who has used AI for real work for a while knows that sinking feeling. It is part of why I keep saying that [learning this stuff properly is hard](/posts/learning-ai-is-hard/).

## Short term memory vs long term memory

So far I have been talking about the problems with short term memory. I have not said much about long term memory for AI, and the honest truth is there isn't a worthwhile solution for it yet. There was an attempt at it called LLM Wiki, which I wrote about in [one of my own posts](/posts/llm-wiki-debate/). I don't think it is a good approach, though. It creates more problems than it solves. Others have tried to build on top of it, and Google recently put out something along similar lines. I still reckon we are a long way off solving long term memory properly, but we will get there eventually, at the pace AI is moving.

## How to go about it

Like I said, I lean on a harness, something that wraps all of this in guardrails, governance, and a fair bit more, so the AI has less room to wander off. I have written about why that matters in [why every subject matter expert needs their own AI harness](/posts/every-sme-needs-their-own-harness/).

A few other tips. Keep your implementations small. Build in little blocks, one piece at a time, just like Lego, rather than trying to spin up an entire system, platform or app in one go. Try to build the whole thing at once and you will get slop. (I wrote a whole post on that one too: [why I spend more tokens refining scope than writing code](/posts/why-scope-beats-code/).)

And there is more to building one small block at a time. You learn as you go. You start to understand your own architecture and your design intent. It does not matter whether you can code or not, you will learn to read code just by staring at the screen while it builds each small block. That part matters more than people think. Because if you do not know how your own app or platform works, then who does?

At the end of the day, engineering is about substance. Functional, practical, reliable, robust, self-healing. If your software cannot do those, and it is just a flashy app or platform, then it is all air and no substance. And the way you get there is not by piling on cleverness. It is the opposite: the KISS principle. Keep it simple, stupid.

And while I am at it, vibe coding does not work. It never has, and it never will. Do not believe the bullshit out there, and especially not the people who act like it does. Vibe coding is not engineering. It is just AI slop, and lazy humans with no real engineering skills to show for it, who use it as clickbait. Don't be fooled.

And remember, using AI is not about making your idea look pretty. Otherwise you just end up with something pretty. Pretty shit, that is. It is like wrapping shit in gold foil. If it smells like shit, and tastes like shit, even if it does not quite look like shit, it is still shit.

## What I actually do about it

So that is my take, after a lot of hours sat with the likes of Claude and ChatGPT. None of it is gospel. It is observation.

Understanding why it hallucinates is what lets me build the right tooling around it. It tells me when to compact, how to break a big job into smaller pieces, when to hand parts off to subagents, and how to shape a workflow so the context memory stays manageable instead of quietly rotting. Most of that runs on its own now, baked into my harness, [SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness), which I built for Claude Code specifically and tuned around exactly these limits. You can tweak it for other models if you fancy. I made it free for anyone to use on GitHub, so go have a look.

None of this makes the hallucination vanish. It still happens. It probably always will, a little. But once you understand why, you stop fighting the tool and start working with it. And honestly, that is most of the battle.

<!-- iamhoiend -->
