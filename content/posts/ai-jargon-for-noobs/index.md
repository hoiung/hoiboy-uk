---
title: "AI Jargon for Noobs"
date: 2026-06-22T12:00:00+01:00
draft: false
slug: ai-jargon-for-newbies
aliases: ["/posts/ai-jargon-for-noobs/"]
categories: [tech-ai]
tags: [ai, llm, jargon, beginners, harness]
description: "26 AI buzzwords (plus two the lists skip) in plain English, with an honest note on which I actually use and which I have never touched. Shoot me down."
---

<!-- iamhoi -->

I have been knee-deep in AI for about three years now, building with it most days, and I'm still nowhere near the bottom of it. Tip of the iceberg, honestly.

So this is not a lecture. It's my plain-English map of the jargon, the words that get thrown about like everyone was born knowing them. This is my understanding, dumbed right down. If I've got one wrong, brilliant, shoot me down (I learn that way).

One thing up front, because it trips people up. I build WITH AI. That does not mean my stuff runs ON AI. My trading system, the big one, has exactly zero AI inside it when it's live. Not a drop. It's plain old code, maths, and a broker connection. The AI was the builder, not the brain. Keep that split in your head and half this list makes more sense already.

Right. Twenty-six words from the usual lists, plus two more they always skip that I lean on hard. Some I use every single day. Some I have never once touched. I'll tell you which is which.

## The absolute basics (what's happening under the bonnet)

You don't need most of this to use AI well. But someone always asks, so here's the gist, fast.

**Tokens.** The little chunks of text the AI reads and writes, and bills you by. A word, a bit of a word, a comma, all tokens. Everything it does is really just chewing tokens, one after another. I watch these like a hawk. It's the meter running.

**Next-token prediction.** The actual trick under the bonnet. The AI does not "think" out a sentence, it guesses the next token, then the next, then the next, rolling a weighted dice every time. That's it. That one fact explains most of AI's weirdness (I wrote a whole post on it: [Deterministic vs Probabilistic](/posts/deterministic-vs-probabilistic/)).

{{< zoom-image src="dice-temperature.svg" alt="A diagram of next-token prediction as a weighted dice. The phrase 'the cat sat on the' points to a list of candidate next words with probability bars: 'mat' 61 percent, 'sofa' 18 percent, 'floor' 9 percent, 'roof' 2 percent. A temperature dial sits beside it, low temperature sharpening the odds toward the top choice, high temperature flattening them so longer-shot words get picked." title="Every word is a weighted dice roll. Temperature is the knob." >}}

**Temperature.** A knob for how wild those dice rolls get. Turn it low and it plays safe, turn it high and it gets creative (and risky). Everyone thinks temperature 0 makes it predictable. It doesn't. The odds get sharper, the dice are still dice. I don't touch this one. The tools I use hide it anyway.

**Context window.** The AI's short-term memory for one chat, measured in tokens. It used to be tiny, now it goes up to a million. Here's the bit people skip: stuffing it full makes the AI dumber, not smarter. I compact mine well before it's full, around the point things start to drift. Overfill it and you invite [hallucinations](/posts/why-ai-hallucination-keeps-happening/).

{{< zoom-image src="tokens-context.svg" alt="A diagram of the context window as a container. Text on the left is chopped into token chunks that flow into a tall window labelled 'context window, up to 1 million tokens'. The window has a fill bar: a green healthy zone at the bottom, an amber 'accuracy starts to drift' band higher up, and a red 'overfilled, hallucination risk' zone near the top, with a marker showing where Hoi compacts well before full." title="Tokens fill the context window. Full is not better." >}}

**Attention.** The clever bit inside that lets the AI weigh which words relate to which. "It" refers to what, exactly? Attention is how the model works that out. You genuinely don't need to know this to use AI. Moving on.

**Transformers.** The kind of engine nearly every modern AI is built on (the T in ChatGPT). That's the whole answer. File under "nice to know, never need".

**Inference.** A fancy word for the AI actually running. Tokens in, tokens out. When people say "inference is expensive", they mean every answer costs real money and time to generate. The bit you pay for, basically.

## Getting good answers out of it

This is where the real skill lives, and where I spend most of my time.

**Prompting.** The instructions you give it. The early days of working with AI were all about magic words. Useful, but it's the beginner rung (more on that ladder here: [Prompts, Agents, Harnesses](/posts/prompts-agents-harnesses-whats-next/)).

**Context engineering.** Prompting, grown up. It's deciding what the AI sees, and in what order, so it reads the right things first and stays on task. Same skill, posher name. This is most of what my harness actually does, and I live in it.

**Retrieval.** Going and fetching the real document before the AI answers, instead of trusting whatever it half-remembers. "Whatever this file says" beats "whatever the model reckons", every time. I use it constantly.

**RAG (retrieval-augmented generation).** Retrieval plus answering, bolted together. The grown-up version uses fancy databases. Mine is gloriously dumb: I point the AI at the right markdown file before it speaks. No database, no magic. Works a treat.

{{< zoom-image src="retrieval-grounding.svg" alt="A diagram contrasting two paths. Top path: a question goes straight to the AI, which answers from memory and produces a 'hallucination, confident but wrong' output in red. Bottom path: the same question first triggers a step that reads a real document or file, feeds it to the AI as grounding, and produces a 'grounded, backed by the source' output in green. A label notes Hoi's version uses plain files, not a vector database." title="Read the real source first. That's the whole trick against hallucination." >}}

**Embeddings.** Turning text into a long list of numbers so a computer can spot "these two mean roughly the same thing". The maths behind search-by-meaning. On my list to play with one day. Never got round to it. Though I suspect the AI already has a version of this built in. Every time I use different words that mean the same thing, it still gets my meaning, so that understanding seems baked into the model already.

**Vector databases.** Where you store all those number-ified texts so you can search them by meaning, fast. Honestly? Never used one in anger. The fancy retrieval stack and me have not properly met yet.

**Semantic search.** Searching by meaning instead of exact words. I actually went the other way. I once tried a clever code-graph thing for this, it crashed on me constantly, so I ripped it out and went back to plain keyword search. Well, kinda: I built a wrapper, a plain script that searches across both the code and the docs, fast and cheap on tokens. Boring, reliable, mine. The full story: [No Graphs, Back to Basics](/posts/no-graphs-back-to-basics/). (Vectors are still on the someday list.)

**Grounding.** Tying the answer to something real, a document, a tool, an actual fact, so the AI can't just freestyle. My rule is blunt: the source decides, not the model. This is the antidote to the next one.

**Hallucination.** The AI confidently making stuff up, in the same calm voice it uses for true things. It isn't lying, it's just rolling dice and landing on plausible nonsense. The number one thing I design against (I had a proper rant about why it keeps happening: [Why AI Hallucination Keeps Happening](/posts/why-ai-hallucination-keeps-happening/)).

## Making it actually DO things

Talking is one thing. Pressing buttons is another.

**Tool calling.** Letting the AI use real tools instead of guessing in prose. Need a sum? It calls a calculator, so a number stays a number. Need today's price? It calls an API. This is the jump from chatbot to genuinely useful.

**Function calling.** The same idea, just the tidy version. The AI fills in a structured form (the tool name, the arguments) that your code can run without guesswork. Tool calling with its shirt tucked in.

**Agents.** AI that loops on its own: plan a step, do it, check the result, decide the next move. Not one answer, a little worker that keeps going. I run four to eight of these at once most days. Powerful stuff, but wild without a fence around them. The one I actually talk to I call the main agent, or the orchestrator.

{{< zoom-image src="agent-loop.svg" alt="A diagram of an agent loop. Four boxes in a circle: Plan, Act (call a tool), Observe (read the result), Decide, with an arrow looping back to Plan. The whole loop sits inside a dashed box labelled 'the harness: guardrails, rules it cannot break', showing the loop is contained. An arrow exits the harness box to a green 'safe result'." title="An agent loops on its own. The harness is the fence around it." >}}

**Sub-agents.** The helpers the main agent spins up to go do one focused job, then report back. I drive them through the orchestrator, I never talk to them directly. In my setup they only research and review, they never touch the real work, so one agent stays accountable for whatever ships.

## Tweaking the model itself (the stuff I never touch)

This is the heavy end, retraining the actual brain. I don't go here. I govern at the harness layer and leave the models to the labs. A quick gloss so the words stop being scary.

**Fine-tuning.** Taking a ready-made model and training it a bit more on your own narrow thing. Useful for some. I've never needed it.

**LoRA (low-rank adaptation).** A cheap shortcut to fine-tuning, you nudge a few small bits instead of retraining the whole lot. Same camp. Never touched it.

**Quantization.** Shrinking the model's numbers so it runs cheaper and faster, at the cost of a little sharpness. Matters a lot if you host your own. I don't.

**Distillation.** Training a small model to copy a bigger one, so you get most of the smarts for less money. (Not the same as me using a cheap model for easy jobs and a clever one for hard jobs. That's just picking the right tool.)

## Keeping it honest, and not breaking things

The unglamorous half that decides whether any of this is safe to ship.

**Evals.** Tests that check the AI behaves, instead of judging it by vibes. Mine run on three tiers, and for a laugh I even built a bake-off that pits ten different setups against the exact same job to see which one wins (the review side of it: [Shipping the Ralph Review Trio](/posts/shipping-ralph-review-trio/)).

**Guardrails.** The rules the AI is not allowed to break. Schemas that refuse junk, validators that catch it lying about its own work, hard stops. This is the heart of a [harness](https://github.com/hoiung/sst3-ai-harness), and it's most of why mine exists.

**Observability.** Logs and audit trails so you can actually see what the AI did, step by step, after the fact. I bake this in while I build, not after the first thing blows up (I learned that one the boring way: [Observability and Logging](/posts/observability-and-logging-for-production-systems/)).

**Harness.** Finally, the big one everyone's throwing around. It's most of the above, prompting, context engineering, tool calls, guardrails, evals, observability, bolted into one repeatable workflow that wraps the AI so it stops wandering off. The model is the engine. The harness is the rest of the car. I built my own, and honestly it's the whole reason any of this holds together ([the long version](/posts/why-do-we-need-an-ai-harness/)).

## So, the honest tally

Count them up. Of the twenty-six, I'm in maybe half every single day (tokens, context, prompting, agents, guardrails, grounding, the lot), plus the two the lists skip that I basically live in (sub-agents and the harness). A good chunk I have never once touched (fine-tuning, LoRA, vectors, the deep-ML end). And a few I just need to know exist.

That's the real picture of working with AI, by the way. It is not magic. It's a dice machine with a ton of plumbing bolted round it, and the skill is almost all in the plumbing. The AI was the builder, not the brain.

Got one wrong? Good. Tell me. That's how the iceberg gets smaller.

<!-- iamhoiend -->
