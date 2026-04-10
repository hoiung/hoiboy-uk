---
title: "Is LLM Wiki Pointless?"
date: 2026-04-10
categories: [tech-ai]
tags: [ai, llm, knowledge-management, obsidian, markdown]
slug: llm-wiki-debate
description: "Bear sent me Karpathy's LLM Wiki gist. 17 million views. But what problem does it solve, and does the solution create more engineering problems than what it's trying to fix?"
---

<!-- iamhoi -->

My mate Bear sent me a link the other day. "Have you seen this?"

It was some bloke called Andrej Karpathy's LLM Wiki gist. 17 million views. I had no idea who he was (Bear told me later he's basically AI royalty, founding member of OpenAI, former Director of AI at Tesla, the lot). We were two bottles deep at this point (a Burgundy and a Chablis, pre-dinner) so naturally I had opinions. By the time we'd finished dinner and worked through 4 ports, 4 martinis, 2 negronis, and 2 old fashioneds between us... I had even more opinions.

The pitch: instead of throwing documents into a vector database and hoping retrieval finds the right chunk, let the LLM build and maintain a wiki. Three folders of markdown. Sources go in, the LLM reads them, writes summary pages, cross-links everything, keeps an index. Knowledge compiled once, kept current. Not re-derived every time you ask a question.

Bear was on the fence. I was not.

## What he actually proposes

Three folders. `sources/` for raw documents (immutable, the LLM reads but never modifies). `wiki/` for LLM-generated markdown (summaries, entity pages, concept pages, the works). `schema/` for configuration telling the LLM how to structure everything.

When you drop a new article into sources, the LLM reads it, writes a summary page in the wiki, updates the index, and revises any related pages. A single source might touch 10-15 wiki pages. There's a lint operation for periodic health checks: contradictions, stale claims, orphan pages.

Here's the thing though... it's literally markdown files in folders. The "wiki" is just more .md files that the LLM generates from your original .md files.

So we're adding a layer. What does the layer buy us?

## The overengineering argument

I started ranting at Bear over the Chablis. What's wrong with Obsidian? What's wrong with a folder of .md files with sensible names?

Obsidian already gives you a graph view showing connections between notes, rich markdown rendering, backlinks panel, full-text search, tags, folders, plugins like Dataview for live queries. You can publish it as a website with Obsidian Publish. Humans get a polished UI. The LLM gets the same .md files it can already read and write. No extra layer needed!

Karpathy tested his pattern on roughly 100 articles. At that scale, a well-named folder IS the wiki. You don't need an intermediary.

But forget about specific tools for a second. Think about it logically. What problem does LLM Wiki actually solve? Does the solution create more engineering problems than what it's trying to fix? I just had so many questions.

Most AI coding tools already use a CLAUDE.md or similar file. One markdown file. The LLM reads it at session start, knows the project context, the standards, the constraints. When things change, you edit the file. Next session picks it up immediately. No re-compilation, no re-indexing, no cascade of wiki page updates. Just... edit the file.

## Who watches the wiki?

By this point we were on the martinis and I was properly ranting. Bear was just nodding along while I kept going.

The LLM writes wiki page A from source articles 1, 2, and 3. Six months later, article 3 is outdated. The wiki page still references it as current. The LLM doesn't know the source is stale unless someone tells it. So now you need a process to flag stale sources, a process to re-ingest updated sources, a process to cascade updates through every wiki page that touched the stale source, and a process to verify the cascade didn't introduce new errors. That's a maintenance burden on top of a maintenance burden!

And it gets worse as it grows. One stale wiki page is a bug. A thousand stale pages is a system failure. Every cross-reference between pages is a propagation path for outdated information. The more interconnected the wiki (which is supposed to be the strength, remember), the faster bad data spreads through it.

The maintenance maths is brutal. A thousand wiki pages, each referencing roughly 3 sources. One source updates per week. Each update touches 10-15 wiki pages (Karpathy's own estimate). Each re-synthesis might affect downstream pages that reference those pages. Within months you're running full re-ingests just to keep up. You've basically built a cache invalidation problem. And as the old joke goes, the two hardest problems in computer science are cache invalidation, naming things, and off-by-one errors.

There's a scarier problem underneath all that, too. Compounding hallucination. The LLM summarises source article 1 into a wiki page. Gets 95% right, 5% slightly off. Later it synthesises that wiki page with pages B and C into a comparison. The 5% error is now baked in. Next synthesis layer compounds it again. You're playing the telephone game with no correction mechanism. With plain .md files, you're always reading the source. No intermediary. No accumulated drift.

## Forgetting is a feature

I was on the old fashioneds by now (don't judge, it was a long dinner) and this is where the rant got philosophical.

Cognitive science research actually supports the idea that forgetting isn't a flaw. It's a feature! A 2022 study published in Frontiers in Computational Neuroscience found that agents with structured memory can forget a large percentage of older memories without any performance loss. And here's the kicker... some forgetting actually improved performance compared to agents with unbounded memory. Let that sink in. Remembering LESS made them BETTER.

The brain does this deliberately. Neuroscience research shows it actively prunes inaccurate memories to keep the system tidy. During sleep, microglia prune unnecessary synaptic connections. The mechanism removes noise (outdated information, infrequently relevant facts) and produces more consistent decisions.

We forget things so that the important stuff stays accessible. Sometimes we forget the important stuff and remember something completely useless (I do this constantly... trust me, I'll remember what I had for lunch in 2019 but forget where I put my keys 5 minutes ago). But the pruning mechanism itself is load-bearing. It's what keeps the whole system from collapsing under its own weight.

An ever-growing wiki with no forgetting mechanism is the opposite of how effective memory works. Every page it's ever generated sits there forever, confidently presenting information that might be months out of date. No pruning. No decay. No noise reduction.

Plain .md files handle this naturally. When things change, you update the file. Old instructions get replaced, not layered on top of. The LLM reads current state. Always. No generated intermediary accumulating quiet drift.

And then I moved on to companies, because why stop when you're on a roll.

## The enterprise angle

Companies already have wikis. Confluence, Notion, SharePoint. These aren't just document stores. They have role-based access controls, compliance-grade audit trails, proper retention policies. When someone leaves the company, their access gets revoked. When regulators come knocking, there's an immutable log of who changed what and when.

Karpathy's wiki? It's a folder on a file system. Anyone with access can zip the whole thing and walk out. There's no RBAC, no audit trail beyond git log (which is a developer tool, not a compliance record), and it was tested on roughly 100 articles. Try that with the 50,000 documents a mid-sized company generates in a year.

RAG isn't perfect, but it taps into existing enterprise systems with existing permissions. Building a parallel LLM-maintained wiki duplicates what companies already have, minus everything that makes it safe for a team to use.

For enterprise, it's a non-starter. For personal use... well, Obsidian exists.

## What it gets right

Don't get me wrong. I'm not going to pretend the whole thing is rubbish. That would be dishonest.

The core insight about task allocation is real. LLMs genuinely don't get bored updating cross-references. Humans genuinely do. The "compiled knowledge" framing is useful. And the pattern echoes Vannevar Bush's 1945 Memex concept (a theoretical private knowledge store with associative trails between documents). Bush imagined it 80 years ago. LLMs can now actually maintain it. That's genuinely cool.

For a solo researcher reading 100+ papers over months and wanting an LLM to maintain structured companion notes... yeah, that's elegant. I'll give it that.

## The verdict

By the second negroni I'd worn myself out. Here's where I landed.

LLM Wiki is a nice pattern for one specific use case: a solo researcher with a curated collection of sources who wants compiled, cross-referenced notes maintained by an AI. For that person, it's elegant.

For everyone else? It's a solution looking for a problem that .md files, Obsidian, or existing enterprise wikis already solve. The generated layer adds maintenance burden, introduces hallucination compounding, creates a cache invalidation nightmare as it grows, and fights against the very principle (forgetting, pruning, staying current) that makes knowledge systems actually work.

Sometimes the boring tool that works is the right tool. I'll take my folder of markdown files over a generated wiki any day.

Bear sat through the whole rant without saying much. He's still on the fence. We'll probably need another dinner to settle this one.

<!-- iamhoiend -->
