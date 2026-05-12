---
title: "Done With Building AI for Machines? I'm Building AI for People."
date: 2026-05-12
draft: false
categories: [entrepreneurship, tech-ai]
tags: [ai, harness, consulting, sme, launch, ai-managed-harness-services]
description: "I had AI infrastructure interviews lined up. Then I looked at how friends across industries actually use AI at work. So here is what I'm launching."
---

<!-- iamhoi -->

I had a few interviews lined up. Decent companies, decent AI roles. And then, halfway through the second one, the thing clicked.

I was about to be thrown into building AI infrastructure for things I do not really care about. Like building AI for machines. Cool work, no doubt. Smart people, big budgets, all the toys. But the actual product? Pipelines feeding pipelines feeding more pipelines, with the human bit pushed three floors away from where the AI lived.

Does that fire up my passion in AI? And thought, nope.

Not because the work was bad. Because *that* is not the problem I want to solve. And everyone is chasing the scale scale scale route from what I've seen. They focus more on quantity over quality. I'm like, slow down!

The problem I want to solve is sitting in every conversation I have had with friends over the last few months. People in law, finance, marketing, sales, ops, HR, design, customer support, you name it. Smart, capable, very very good at their actual job. And every single one of them is dealing with the same problem. Not the AI. The rollout.

## What I saw in the meantime

Here is the picture I kept getting, almost word for word, across totally different industries.

A few months ago, IT or someone above IT bought a Copilot (because it's free) or ChatGPT seat (the cheapest package) for everyone. *"Here you go, off you go, you are AI enabled now."* And that was pretty much it.

Cringe.

(The companies' upper management already know this is a terrible rollout. They know nobody has figured out yet how to use AI properly and cost-effectively.)

So what do people actually do with it? They figure out the bits that work and quietly use those. Copy and paste into AI chat. Summarise this email thread. Tidy up this draft. Pull the key points out of a 40-page PDF. Connect it to the inbox and let it prioritise what to read first. Useful! Genuinely useful. Saves real time.

But it is *assistant-tier* usefulness. Low-level. The thing fetches your coffee, it does not run your workflow.

I understand why people use it the way they do. It's the limitations of a single AI chat interface (not quite the same as Claude Code). The problem with using a single chat (instead of a workflow with an orchestrator agent plus swarms of subagents) is the *context window* (the chat's working memory). A single chat has one, capped at 1M tokens (was 200K! until recently). There is not enough context window to retrieve, process, and store whatever the task at hand needs. You're only able to "skim" the surface of whatever task you're trying to do, rather than a deep dive.

Using subagents effectively allows each agent to have its own token window. That frees the main orchestrator agent from doing the doing. Instead, it collates and presents tasks, and coordinates with you, the user.

There are also different ways to use subagents and agentic AI (the broader name for AI that goes off and acts on its own, not just chats back at you). I use mine completely differently. My workflow doesn't allow subagents to implement. They can only research and dump into research files, and summarise, and then provide feedback to the main orchestrator, who is the only allowed agent to implement any changes.

Sorry for the long explanation, but I had to try and fit the reason why single-chat AI use has extreme limitations, why it's so restricted, and not too effective when it comes to more complex tasks that have multiple layers of research, planning, and implementation (simplified for brevity). I didn't even mention the quality-control loop back for each stage, and more. But let's stop here at the technical explanations.

Every single SME user I spoke to has been bitten by an AI hallucination of some form. Confident, fluent, completely wrong. Names invented. Numbers invented. Citations invented. Caught it in time? Lucky. Did not catch it? Embarrassing at best, expensive at worst. Once that happens too often, they stop trusting the tool for anything that matters, and they retreat back to the assistant-tier safe stuff. Summaries. Tidying. Prioritising. The low-stakes corner.

What stood out the most: every user I spoke to does not know how to use subagents (think of them as specialist mini-AIs that handle one part of a job and report back), they do not know what a harness is, and they do not know how to set up their AI properly to unleash its real capabilities. Yes, there are generic skills and installable packages out there, but it is like a minefield. Who has time to learn, test, and fine-tune all of that on top of their own work and deliverables? Work already has enough pressure as it is, and here come the staff layoffs, so now you have even more on your plate!

So the seat keeps getting renewed. The dashboard keeps showing usage. The company tells itself it is "AI enabled". And the actual work, the work that pays the bills, is still being done the same way it was two years ago.

## The question nobody is answering

There is one real question and almost nobody is asking it out loud.

Does the AI you bought actually increase productivity, or is it creating more friction than it removes?

And productivity here does not mean *more output*. It means delivering quality, on the things that actually matter, that add value to the business. Not looking busy. Not pumping out 10x the volume of an artefact your customer reads once and forgets. Quantity is only useful if the *quality* justifies it. If the quality drops because your quality control cannot keep up, you are just multiplying slop. And slop costs tokens. Tokens cost money. Bad output costs reputation. So you are paying twice for output your team has to clean up.

This is where a harness comes in.

The point of an [SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness) (or any properly built custom AI harness, the framework that wraps the raw AI in checks, context, tooling, and guardrails specific to your trade) is to lift that assistance level from low to mid+ with much more consistency. Not perfect. Not magic. Mid+. The thing handles the next class of work up: drafts that pass quality control on the first pass most of the time, decisions that are recommended with sources and reasoning, tasks that finish themselves cleanly when the input is well-scoped.

The way I think about it is a basic 80:20 rule. Does the AI deliver 80% of the work to an acceptable standard ("quality in the deliverance", as I like to put it)? Then the remaining 20% is Human-in-the-loop, which means *you* (the actual domain expert) guide and refine the last mile, sign off on the parts that need your judgment, and reject what does not pass your own bar.

80% AI doing the grind. 20% you, doing the judgment. That is the split that works in a real business. Not 100% AI fire-and-forget (slop factory). Not 100% human typing into a chatbot (assistant-tier ceiling). The harness is what makes the 80:20 actually possible day after day.

## Why I said no

Back to my interviews. I had a not-so-heated debate with one interviewer, just a clash of perspective. They were pushing for low hanging fruits, and I disagreed. I think there is a time and place for low hanging fruits, but I measure based on value. If you have 100 low hanging fruits that each produce +£1 of value and take 1 day per fruit, then that is only +£100 after 100 days. Whereas if you are targeting *value*, where the time and output is greater than +£100 after 100 days (for example, 10 higher hanging fruits at +£100 in 10 days each, that's +£1,000 after 100 days), then I would rather focus my time and effort on that. Because there is such a thing as a limited resource (my time), and the value-led route produces a 10x long-term result. The interviewer didn't get it. But that's okay. Some mindsets look at pleasing stakeholders with quantity (100 qty vs 10 qty). I am here to solve a problem and deliver value! Hence why I like to say "No" a lot, which can cause friction sometimes. The facade and the fake productivity, the company-politics game, I'd rather not play it.

I am pretty much done with the corporate grind. I am pretty comfortable where I am right now, with the pullback swing trading system automation gone live, side gigs, and properties income. The grind is fine in your 20s, even your early 30s. After a certain point, it starts costing you more than it pays. The entrepreneur spirit is not always a culture fit either, because I like to say "no" a lot and have my own ways for getting things done. For good reasons. And I do not want to be forced into shipping something that goes against my professional principles just because a roadmap or a stakeholder said so and wants something done a subpar way, or overengineered. Working on a project or building something on a scope I know will fail, it sucks, and it tarnishes the reputation as my name is on the project. You are probably sitting here thinking, *"oh, it is your job to convince the stakeholder to build differently."* Yeah, okay... not always. Not if it isn't my job or pay grade. I know when to pick my fights, and sometimes I know when it is time to move on.

And one more thing. I like to design things simple, because simple works, but do simple *well*. This is quality. I try to avoid overengineering, trying to be clever, or using gimmicks. Gimmicks generally are what they are: gimmicks. Functionally terrible, but they may look great, or try to be clever (but isn't), and say what problem they solve on paper (but not mention any of the problems it creates). Do everything simple well. That is the way.

## What I want to build instead

I want to work with people, in close proximity. Not over a wall, not via a strategy deck, not as a faceless vendor on a slack channel. I want to sit next to the person whose job it actually is, watch them work, find the friction, and build them a custom AI harness that takes the boring grind off their plate so they can spend their time on the bit only a human can do.

It does not matter what trade. It does not matter what domain. Lawyer, marketer, ops lead, finance person, recruiter, physio, teacher, designer, architect, interior designer, civil engineer, customer support hero, you name it. If you are a subject matter expert in something, I am confident I can build you a custom harness that automates and helps manage the tedious grinds in your job. The same harness pattern that runs my own businesses (yes, plural, including a side eBay store and a live trading system) is the same one I want to bring to yours.

What if you are a jack-of-all-trades, an entrepreneur, C-level, Manager, Director, VP? Yeah, as long as you have your own workflow, I can build a harness to make your life easier and get Claude Code working with you, not against you.

And I want to teach you how to use it. Properly. Not "here is a tool, off you go". Not a 30-minute Zoom and a Notion page. Close proximity, hands-on, until the harness is part of your day and not a thing you sometimes remember to open.

The whole point is to bring AI adoption up to where its real capability lives. Reduce the slop. Stop people from throwing the tool away because it is creating more problems than it solves. The tool is not the problem. The fit is the problem. I fix the fit. Anyone here wants a custom-fit hero suit? :D

## AI Managed Harness Services

So that is what I am launching.

It is called **AI Managed Harness Services** and you can [read the whole offer here](/consulting/claude-code-harness-architect/). The full breakdown is on the page, but the shape is: a free 20-minute discovery call to see if there is a fit, then an audit-first ladder (your company structure, your foundation, then one harness at a time per trade or workflow), then an ongoing Monthly Maintenance Package once the harnesses are in production. Sequential. Audit-led. No 50-page strategy deck. Real builds, owned by you.

UK-based. International clients welcome (travel at cost, no markup, I'm not in this to profit on expenses).

## A soft discount for the first three

One last bit, then I will let you go.

I am opening up a discount for the first three clients to come through the door. Not a giveaway, but enough to be meaningful. And the reason for it is honest: those first three are going to help me **dogfood** my own consulting workflow. The discount is to be discussed, because I am not working on a one-year project on a discount, lol. It won't take me that long to dogfood on a live client, so it will be time-based, like maybe the first 1-3 months discounted.

(Plain English bit. "Dogfood" is a thing software people say. It comes from the old "we eat our own dog food" line, meaning the company that builds the dog food has to actually feed it to their own dogs before they sell it to anyone else. In other words: you use your own product, in real conditions, before you charge full price for it. That is what I am doing here.)

I have spent months building the playbook for AI Managed Harness Services. The shape of it works. But until I have run real clients through it end to end, I will not know exactly where some of the friction points are. The first three engagements are how I find that friction and tune it out. You get a real harness build at a discounted rate. I get to fine-tune the workflow before the playbook hardens into its final shape. Mutual benefit. Honest trade.

If that sounds like you, the discovery-call link is on the [AI Managed Harness Services page](/consulting/claude-code-harness-architect/). 20 minutes, free, no pitch deck.

What are you waiting for? Go go go!

<!-- iamhoiend -->
