---
title: "Deterministic vs Probabilistic. Same Input, Different Answer."
date: 2026-06-06T12:00:00+01:00
draft: false
slug: deterministic-vs-probabilistic
categories: [tech-ai]
tags: [ai, llm, determinism, probabilistic, harness]
description: "Same input, same answer, or a different one every time? It is the one distinction that explains why raw AI feels like a slot machine, and why a harness exists."
---

<!-- iamhoi -->

Two words. They explain almost everything that feels strange about AI.

Deterministic, and probabilistic. More boring words for you to learn about AI, I know. Stick with me since these are very important and because the gap between the two is the whole game, and almost nobody spells it out before throwing you in.

## Deterministic: same input, same output

A deterministic system gives you the same answer every single time. Put `2 + 2` in, get `4` out. Today, tomorrow, on my laptop, on yours. A database query against the same data, a hash function, a humble little script... all deterministic. Same input, same output, every time. No surprises. No mood.

This is what we have built software on for decades. You write a test, you assert the exact answer, you trust it forever. Predictable is the point.

## Probabilistic: same input, who knows

A probabilistic system rolls a dice. Same question in, and you can get a different answer out, run after run.

An LLM (the thing under Claude, ChatGPT, all of them) is probabilistic right down to the bone. For every word it writes, it ranks the candidates with a probability attached, then it picks one off a weighted dice. Fresh roll, every token. So the same prompt hands you a different answer tomorrow. Sometimes slightly. Sometimes wildly. (I wrote a whole post on the dice machine, so I will spare you the rerun here.)

And no, setting `temperature = 0` does not save you. Temperature is just the knob for how wild those dice rolls get. Turn it down and the model plays safe, leaning hard on its top pick. Turn it up and it gets creative (a polite word for it makes more up). Some assume dialling it to zero makes the thing predictable. It doesn't... the odds get sharper, the dice are still dice. A raw LLM cannot be made 100% deterministic. That is simply how the thing works.

{{< zoom-image src="dice-temperature.svg" alt="A diagram of next-token prediction as a weighted dice. The phrase 'the cat sat on the' points to a list of candidate next words with probability bars: 'mat' 61 percent, 'sofa' 18 percent, 'floor' 9 percent, 'roof' 2 percent. A temperature dial sits beside it, low temperature sharpening the odds toward the top choice, high temperature flattening them so longer-shot words get picked." title="Every word is a weighted dice roll. Temperature is the knob." >}}

## So why does the distinction matter?

Because the moment you know which half you are holding, you know how to build with it.

Here is the part people skip. On its own, a raw probabilistic LLM is so unpredictable that it is barely usable for anything serious. No control, no guarantees, nothing you would trust with real money or real users. It dazzles you on Monday and embarrasses you on Tuesday. Brilliant and useless at the same time. Without a deterministic layer built around it, the value drops to roughly nothing.

Now, the examples up top were dumbed right down to make the point land. Push more complex inputs through and the gap starts to show. Ask an AI for `2 + 2` and you will still get `4` every time. But that is likely because it quietly reaches for a tool, runs the sum through a calculator, then joins that clean answer back up with its own probabilistic words.

So the fix is a hybrid. You take the probabilistic LLM and wrap it in deterministic scaffolding. Schemas that refuse junk. Validators that retry when the model lies about its own output. Tool calls where a number has to be a real number. The boring same-every-time stuff, wrapped around the clever never-the-same stuff. One half gives you the control. The other gives you the magic. You need both, working together. Take either away and the whole thing falls over.

That wrapper has a name. The harness.

## Same model, three levels of control

{{< zoom-image src="cones.svg" alt="Three panels showing the same probabilistic LLM with more deterministic harness stacked on top. A raw LLM sprays outputs at random with no cone. The general harness that ships with every AI tool gives a wide cone that lands a few on target, with most falling short and several scattering outside. Your own custom harness, bolted on top, tightens the cone onto your bullseye, with only the odd stray outside." title="Raw LLM, the general harness it ships with, then your own on top" >}}

Picture a radar firing outputs at a target.

A raw LLM, on its own, has no cone at all. It sprays everywhere. Most outputs miss, plenty miss wildly, and you are back at the slot machine.

Here is the bit worth getting straight. Every AI tool you actually touch already comes with a general harness baked in. Claude, ChatGPT, Perplexity, the coding agents, they all ship with one. That default harness is what gives you a cone at all, instead of pure spray. It helps a lot. But it is built for everyone, so it aims at a generic target, not yours, and the labs keep changing it whenever they like, with zero input from you.

The bit you actually bolt on is your own custom harness, stacked on top of theirs. That is when the cone tightens right onto your bullseye. The general layer gives you the basics. Your custom layer knows your trade, your rules, the exact thing you are trying to hit. And because it is yours, it does not move when a lab ships an update underneath. (More on why every expert ends up building that top layer: [Every SME Needs Their Own AI Harness](/posts/every-sme-needs-their-own-harness/).)

And those dots still landing outside the cones, even with a harness? A general one lets more slip. Your own lets fewer. Neither gets to zero. A harness shifts the odds hard in your favour, it never gets them to perfect.

## The lesson in one stat

Here is the bit that surprised even me. When someone [reverse-engineered Claude Code and counted the lines](https://arxiv.org/abs/2604.14228), under 2% of it was the actual AI decision logic. The other 98% was plain deterministic plumbing. (A third-party line count of the code, mind you, not Anthropic's own number, and not a measure of where the cleverness lives. The intelligence is still all in the model. But the sheer bulk of the machine bolted around it? Deterministic.)

The probabilistic part is the magic. The deterministic part is most of the actual engineering. You need both, working together. A hybrid approach is what makes it reliable-ish.

AI is probabilistic. The harness shifts the odds. It does not erase them. If you want the long version, start here: [Why Do We Need an AI Harness?](/posts/why-do-we-need-an-ai-harness/)

<!-- iamhoiend -->
