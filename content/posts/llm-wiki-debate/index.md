---
title: "Is LLM Wiki Pointless?"
date: 2026-04-10
categories: [tech-ai]
tags: [ai, llm, knowledge-management, obsidian, markdown]
slug: llm-wiki-debate
description: "Bear sent me Karpathy's LLM Wiki gist. 17 million views. I think it's overengineering. Here's why plain markdown files still win."
---

<!-- iamhoi -->

My mate Bear sent me a link the other day. "Have you seen this?"

It was Andrej Karpathy's LLM Wiki gist. 17 million views. We were two bottles deep at this point (a Burgundy and a Chablis, pre-dinner) so naturally I had opinions. By the time we'd finished dinner and worked through 4 ports, 4 martinis, 2 negronis, and 2 old fashioneds between us... I had even more opinions.

The pitch: instead of throwing documents into a vector database and hoping retrieval finds the right chunk, let the LLM build and maintain a wiki. Three folders of markdown. Sources go in, the LLM reads them, writes summary pages, cross-links everything, keeps an index. Knowledge compiled once, kept current. Not re-derived every time you ask a question.

Bear was excited. I was not.

## The debate

Look, I get the appeal (and it wasn't just the Burgundy talking). Karpathy is a brilliant bloke and the framing is genuinely clever. The idea that an LLM never gets bored updating cross-references (true), that humans are rubbish at maintaining wiki links (also true), and that you can cut token usage by 95% if you pre-compile your knowledge into readable pages... all fair points.

But I've spent the last year building production systems with AI. Not prototypes, not demos. A swing trading platform with 10,000+ commits and 1,860+ issues. A five-stage solo agent workflow called SST3 that manages everything from research through implementation through review. All of it built and documented using plain .md files. CLAUDE.md. STANDARDS.md. Issue bodies. Research docs. Markdown in folders.

It works. It scales. And it does not need a generated wiki layer sitting between me and my source of truth.

## What Karpathy actually proposes

Three folders. `sources/` for raw documents (immutable, the LLM reads but never modifies). `wiki/` for LLM-generated markdown (summaries, entity pages, concept pages, the works). `schema/` for configuration telling the LLM how to structure everything.

When you drop a new article into sources, the LLM reads it, writes a summary page in the wiki, updates the index, and revises any related pages. A single source might touch 10-15 wiki pages. There is a lint operation for periodic health checks (contradictions, stale claims, orphan pages).

Here's the thing though... it is literally markdown files in folders. The "wiki" is just more .md files that the LLM generates from your original .md files.

So we're adding a layer. What does the layer buy us?

## The overengineering argument

I asked Bear this directly. What's wrong with Obsidian? What's wrong with a folder of .md files with sensible names?

Obsidian already gives you a graph view showing connections between notes, rich markdown rendering, backlinks panel, full-text search, tags, folders, plugins like Dataview for live queries. You can publish it as a website with Obsidian Publish. Humans get a polished UI. The LLM gets the same .md files it can already read and write.

Karpathy tested his pattern on roughly 100 articles. At that scale, a well-named folder is the wiki. You don't need an intermediary.

My SST3 workflow manages context for an AI agent across sessions using... a CLAUDE.md file. That's it. The LLM reads it at session start, knows the project structure, the standards, the anti-patterns, the quality gates. When things change, I update the file. The LLM reads the updated file next time. No generated layer. No compilation step. No index to maintain.

## Who watches the wiki?

This is where it gets properly concerning.

The LLM writes wiki page A from source articles 1, 2, and 3. Six months later, article 3 is outdated. The wiki page still references it as current. The LLM does not know the source is stale unless someone tells it. So now you need a process to flag stale sources, a process to re-ingest updated sources, a process to cascade updates through every wiki page that touched the stale source, and a process to verify the cascade didn't introduce new errors.

That is a maintenance burden on top of a maintenance burden.

And it gets worse as it grows. One stale wiki page is a bug. A thousand stale pages is a system failure. Every cross-reference between pages is a propagation path for outdated information. The more interconnected the wiki (which is supposed to be the strength), the faster bad data spreads through it.

The maintenance maths is brutal. A thousand wiki pages, each referencing roughly 3 sources. One source updates per week. Each update touches 10-15 wiki pages (Karpathy's own estimate). Each re-synthesis might affect downstream pages that reference those pages. Within months you are running full re-ingests just to keep up.

You have basically built a cache invalidation problem. And as the old joke goes, the two hardest problems in computer science are cache invalidation, naming things, and off-by-one errors.

## The telephone game

There is a scarier problem underneath the staleness one. Compounding hallucination.

The LLM summarises source article 1 into a wiki page. Gets 95% right, 5% slightly off. Later it synthesises that wiki page with pages B and C into a comparison. The 5% error from page A is now baked into the comparison. The next synthesis layer compounds it again. You are playing the telephone game with no correction mechanism.

With plain .md files, you are always reading the source. No intermediary. No accumulated drift. The "cost" is re-reading source every time you query. The benefit is the answer is always grounded in current reality, not a six-month-old synthesis that might be quietly wrong.

## Forgetting is a feature

This is the bit that really landed for me during the debate with Bear.

Cognitive science research actually supports the idea that forgetting is not a flaw. It is a feature. A 2022 paper in Frontiers in Computational Neuroscience found that agents with structured memory can forget a large percentage of older memories without any performance loss. And here is the kicker... some forgetting actually improved performance compared to agents with unbounded memory.

The brain does this deliberately. Princeton research shows it actively prunes inaccurate memories to keep the system tidy. During sleep, microglia prune unnecessary synaptic connections. The mechanism removes noise (outdated information, infrequently relevant facts) and produces more consistent decisions.

We forget things so that the important stuff stays accessible. Sometimes we forget the important stuff and remember something completely useless (I do this constantly, trust me). But the pruning mechanism itself is load-bearing. It is what keeps the whole system from collapsing under its own weight.

An ever-growing wiki with no forgetting mechanism is the opposite of how effective memory works. Every page it has ever generated sits there forever, confidently presenting information that might be months out of date. No pruning. No decay. No noise reduction.

My CLAUDE.md approach handles this naturally. When things change, I update the file. Old instructions get replaced, not layered on top of. The LLM reads current state. Always. There is no generated intermediary accumulating quiet drift.

## The enterprise angle

Bear pushed back. "What about companies? Teams?"

Companies already have wikis. Confluence, Notion, SharePoint. They have access controls, audit trails, compliance logging. RAG can tap into those systems and pull information with proper permissions.

Karpathy's LLM Wiki has no role-based access control (how do you do RBAC on a file system?), no compliance-grade audit trail (git log is a developer tool, not a compliance log), no scalability beyond roughly 100 articles, and anyone can zip the entire knowledge base and walk out the door.

For enterprise, it is a non-starter. For personal use... well, Obsidian exists.

## What it gets right

I'm not going to pretend the whole thing is rubbish. That would be dishonest.

The core insight about task allocation is real. LLMs genuinely do not get bored updating cross-references. Humans genuinely do. The "compiled knowledge" framing is useful. And the pattern echoes Vannevar Bush's 1945 Memex concept (a private knowledge store with associative trails between documents). Bush imagined it. LLMs can now actually maintain it. That is cool.

For a solo researcher reading 100+ papers over months and wanting an LLM to maintain structured companion notes... yeah, that is genuinely elegant. I will give it that.

## So where does that leave us?

Bear and I ended up roughly here. LLM Wiki is a nice pattern for one specific use case: a solo researcher with a curated collection of sources who wants compiled, cross-referenced notes maintained by an AI. For that person, it is elegant.

For everyone else, it is a solution looking for a problem that .md files, Obsidian, or existing enterprise wikis already solve. The generated layer adds maintenance burden, introduces hallucination compounding, creates a cache invalidation nightmare as it grows, and fights against the very principle (forgetting, pruning, staying current) that makes knowledge systems actually work.

Sometimes the boring tool that works is the right tool. I will take my folder of markdown files over a generated wiki any day.

<!-- iamhoiend -->
