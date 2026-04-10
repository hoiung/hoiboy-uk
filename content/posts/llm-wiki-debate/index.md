---
title: "Do We Actually Need LLM Wiki?"
date: 2026-04-10
categories: [tech-ai]
tags: [ai, llm, knowledge-management, obsidian, markdown]
slug: llm-wiki-debate
description: "Bear sent me the LLM Wiki gist. But what problem does it solve, and does the solution create more engineering problems than what it's trying to fix?"
---

<!-- iamhoi -->

My mate Bear sent me a link the other day. "Have you seen this?"

It was some gist about something called LLM Wiki. Went viral apparently. I didn't even clock who wrote it at first (turns out it was Andrej Karpathy, a fairly big deal in AI). I just skim-read what it was proposing and immediately started having questions. We were two bottles deep at this point (a Burgundy and a Chablis, pre-dinner) so naturally I had a lot of questions. By the time we'd finished dinner and worked through 2 ports each, 2 martinis each, a negroni each, and an old fashioned each... I had even more questions.

The pitch: instead of throwing documents into a vector database and hoping retrieval finds the right chunk, let the LLM build and maintain a wiki. Three folders of markdown. Sources go in, the LLM reads them, writes summary pages, cross-links everything, keeps an index. Knowledge compiled once, kept current.

Bear was on the fence. I had questions.

## What it proposes

Three layers. Raw sources (immutable, the LLM reads but never modifies). A wiki folder for LLM-generated markdown (summaries, entity pages, concept pages, the works). And a schema file telling the LLM how to structure everything.

When you drop a new article into sources, the LLM reads it, writes a summary page, updates the index, and revises any related pages. A single source might touch 10-15 wiki pages. There's a lint operation for periodic health checks: contradictions, stale claims, orphan pages.

Here's the thing though... it's literally markdown files in folders. The "wiki" is just more .md files that the LLM generates from your original .md files.

So we're adding a layer. What does the layer actually buy us?

## What problem is it solving?

I started ranting at Bear over the Chablis. What's wrong with Obsidian? What's wrong with a folder of .md files with sensible names?

Obsidian already gives you a graph view, rich markdown rendering, backlinks, full-text search, tags, folders, plugins like Dataview for live queries. You can publish it as a website with Obsidian Publish. Humans get a polished UI. The LLM gets the same .md files it can already read and write. No extra layer needed!

Think about it logically. What problem does LLM Wiki actually solve? Does the solution create more engineering problems than what it's trying to fix? I just had so many questions.

Because here's the thing... my current workflow already does this. I spin up multiple subagents to do research, they dump summaries into .md files, those files get indexed per project repo in a docs subfolder with an index.md. That's it. No wiki engine. No special architecture. Just agents writing markdown into folders with an index. Sound familiar?

Most AI coding tools already use a CLAUDE.md or similar file. One markdown file. The LLM reads it at session start, knows the project context. When things change, you edit the file. Next session picks it up immediately. No re-compilation, no re-indexing, no cascade of wiki page updates. Just... edit the file.

## The staleness problem

By this point we were on the martinis and I was properly going.

The LLM writes wiki page A from source articles 1, 2, and 3. Six months later, article 3 is outdated. The wiki page still references it as current. The LLM doesn't know the source is stale unless someone tells it. So now you need a process to flag stale sources, a process to re-ingest, a process to cascade updates through every wiki page that touched the stale source, and a process to verify the cascade didn't introduce new errors. That's a maintenance burden on top of a maintenance burden!

And it gets worse as it grows. One stale wiki page is easy to fix. A thousand stale pages? That's a lot of housekeeping. Every cross-reference is a propagation path for outdated information. The more interconnected the wiki (which is supposed to be the strength, remember), the faster things drift.

So now you've got a system that's supposed to save you time... but it needs constant babysitting to stay accurate. That doesn't sound like a solution. That sounds like a new problem.

And there's compounding hallucination on top of that. The LLM summarises a source into a wiki page. Gets 95% right, 5% slightly off. Later it synthesises that page with others into a comparison. The 5% error is now baked in. Next layer compounds it again. You're playing the telephone game with no correction mechanism. With plain .md files, you're always reading the source. No intermediary. No accumulated drift.

## Forgetting is a feature

I was on the old fashioneds by now (don't judge, it was a long dinner) and this is where it got philosophical.

Cognitive science research actually supports the idea that forgetting isn't a flaw. It's a feature! A 2022 study in Frontiers in Computational Neuroscience found that agents with structured memory can forget a large percentage of older memories without any performance loss. And here's the kicker... some forgetting actually improved performance compared to agents with unbounded memory. Remembering LESS made them BETTER.

The brain does this deliberately. Neuroscience research shows it prunes unnecessary synaptic connections during sleep. The mechanism removes noise (outdated information, infrequently relevant facts) and produces more consistent decisions.

We forget things so that the important stuff stays accessible. Sometimes we forget the important stuff and remember something completely useless (I do this constantly... trust me, I'll remember what I had for lunch in 2019 but forget where I put my keys 5 minutes ago). But the pruning mechanism itself is load-bearing.

An ever-growing wiki with no forgetting mechanism is the opposite of how effective memory works. No pruning. No decay. No noise reduction.

Plain .md files handle this naturally. When things change, you update the file. Old stuff gets replaced, not layered on top of. The LLM reads current state. Always.

## What about enterprise?

Companies already have wikis. Confluence, Notion, SharePoint. These have role-based access controls, compliance-grade audit trails, retention policies. RAG taps into those systems with existing permissions. Building a parallel LLM-maintained wiki duplicates what companies already have, minus the security and compliance.

## What it gets right

Don't get me wrong. I'm not trying to rubbish the idea. I'm just asking questions.

The core insight about task allocation is real. LLMs genuinely don't get bored updating cross-references. Humans genuinely do. The "compiled knowledge" framing is useful. And the pattern echoes Vannevar Bush's 1945 Memex concept (a theoretical private knowledge store with associative trails between documents). Bush imagined it 80 years ago. LLMs can now actually maintain it. That's genuinely cool.

For a solo researcher reading 100+ papers over months and wanting an LLM to maintain structured companion notes... yeah, that's elegant. I'll give it that.

## The verdict

By the last drink I'd worn myself out. Here's where I landed.

LLM Wiki is a nice pattern for one specific use case: a solo researcher with a curated collection of sources who wants compiled, cross-referenced notes. For that person, it works.

For everyone else? I wonder if it creates more problems than it solves. The generated layer adds maintenance, introduces hallucination compounding, creates a cache invalidation problem as it grows, and seems to work against the very principle (forgetting, pruning, staying current) that makes knowledge systems actually work.

Sometimes the boring tool that works is the right tool.

Bear sat through the whole rant without saying much. He's probably still giggling inside knowing exactly who wrote the LLM Wiki gist while I was sat there tearing it apart without a clue. We'll probably need another dinner to settle this one.

<!-- iamhoiend -->
