---
title: "I Built an eBay Harness in 15 Days. Here's What 17 Tools Look Like."
date: 2026-04-25
draft: true
slug: my-ebay-harness
categories: [tech-ai]
tags: [ai, harness, mcp, ebay, sst3, claude-code, tools]
description: "Production proof for the harness thesis. 15 days, 159 commits, 17 MCP tools, four phases. What it looks like when an operator builds for their own trade."
---

<!-- iamhoi -->

## The problem I gave myself a window to fix

I run an eBay reseller business on the side. Listing creation. Photos. Item specifics. Condition descriptions. Pricing checks. Inventory monitoring. Repricing when the market shifts. Watching feedback. Watching returns. Watching the active listings panel for the ones that have gone quiet.

It is manual. It is serial. It is error-prone. Multiple live listings. More in the queue. Do the maths.

I gave myself a window. Two weeks. Make it go away.

## The setup (and what I will not tell you)

I will not tell you what I sell. None of your business. That's my edge. (You can call it an online store. You can call it a side project. You can call it the small businesses I run on the side. Pick whichever makes you comfortable.) The platform is eBay. That's the only specific you get.

eBay's seller side has a particular shape. The Seller Hub web UI scatters things across six or seven surfaces. The mobile app shows you a different subset. Half the data you actually want, the qty sold per listing, the watcher counts, the offer counts, the buyer questions, lives in the Trading API (the legacy XML one, the one that has been "deprecated" for years and yet still runs the lights). The newer REST APIs, Inventory and Analytics, hold the modern signals (impressions, click-through rate, conversion). They live behind a separate OAuth (open-authorisation) flow. Two-headed authentication for the same account.

Nothing ties them together. No single eBay surface gives you the picture. Either you spend half an hour every week clicking through Seller Hub spotting which listings have stalled, or you build the harness that knows which API verb to call in what order.

I built the harness.

## Why a harness, not a script

I have done this dance before. Built a [trading harness](/posts/why-do-we-need-an-ai-harness/) for swing trades. Built a [blogging harness](/posts/your-voice-is-a-brand/) for this site. Same shape, different trade. Get burned by the same problem in three different domains, and you stop writing scripts. You write a harness.

A script does one thing. A harness does many things, and refuses to do them when you ask wrong. A script reads from one API. A harness knows about three APIs and which one to ask first. A script crashes on a malformed input. A harness gives a refusal you can read in plain English and act on. A script is a tool. A harness is a workshop.

Same blade metal as the trading harness and the blog harness. [Reshaped](/posts/sst3-ai-harness-reshapeable-knife/) for reselling. Built on top of [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) (the underlying methodology I run for everything: my trading bot, my blog, my CV, this post you are reading right now). Same workflow. Same Ralph Review tiers. Just pointed at the eBay platform instead of IBKR or Hugo.

The thesis I have been writing for a month, [every domain expert needs their own harness](/posts/every-sme-needs-their-own-harness/), needed proof. Not metaphor. Not philosophy. A real one. Public. Operating. Mine.

## The 15-day arc

Started 10 April 2026. Latest commit 25 April 2026. Fifteen days. 159 commits. 134 of them Claude-attributed (about 84%). Ten Ralph-reviewed merges. One GitHub issue (multi-phase, four checkpoints). Public on GitHub, MIT licensed, [hoiung/ebay-seller-tool](https://github.com/hoiung/ebay-seller-tool).

Four phases. Each one bolted on to the previous. None of them rewrote the previous one.

**Phase 1, listing CRUD (create, read, update, delete).** Five tools. `get_active_listings` to enumerate the live ones with title, price, qty, views, watchers. `get_listing_details` to pull the full per-listing detail with HTML, item specifics, photos. `update_listing` to revise title, description, price, condition. `upload_photos` to batch-push local photos through resize and EXIF-strip preprocessing. `create_listing` to stand up a fresh fixed-price listing end to end. Five tools. The boring foundation. You cannot do anything fancy if create-read-update-delete does not work.

**Phase 2, OAuth and REST analytics.** Three tools. `get_traffic_report` for impressions, click-through rate (CTR), views, conversion. `get_listing_returns` for the post-order return search. `compute_return_rate` for the per-stock-keeping-unit (per-SKU) rate that floor pricing later depends on. Phase 2 did not rewrite Phase 1. It bolted on. New auth flow, same pattern.

**Phase 3, competitive intelligence.** One tool. `find_competitor_prices`, a Browse-API market scan that excludes my own seller account. Small surface. Big payoff on pricing decisions. Same pattern again. No rewrite of Phase 1 or Phase 2.

**Phase 4, pricing guardrails and listing diagnostics.** Two tools. `floor_price`, which computes the break-even floor under measured return-risk scenarios. `analyse_listing`, which is the one I am proudest of. More on that in a minute.

Plus six supporting read-only tools strung across the phases: `get_sold_listings`, `get_unsold_listings`, `get_seller_transactions`, `get_listing_feedback`, `get_listing_cases`, `get_store_info`. Boring on their own. Critical to feed the diagnostic side of the harness.

Five plus three plus one plus two plus six. Seventeen tools. Four phases. Reshapeable knife playing out in code. [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) ran the cadence (Implement, then Haiku review, then Sonnet review, then Opus review, then merge). Ralph caught the bugs that pytest never would have. Three Sonnet-tier flags on logic. Seven Opus-tier flags on architecture and edge cases. Restart from Tier 1 each time. Boring discipline. Boring discipline is the only kind that ships.

## The guardrail moves (the bit that makes it more than CRUD)

Anyone can wire CRUD to an API in a weekend. The reason this took fifteen days, and 159 commits, and ten Ralph reviews, is the four moves that turn it from a script into a harness.

**Move one, floor-price refusal.** Phase 4. If you ask the harness to revise a listing below the computed floor, it refuses. Loud refusal, not silent clamp. The floor comes from a public `config/fees.yaml` (final-value fee schedule, payment fee, ad fee if Promoted) plus the measured per-SKU return rate. The verdict is a number you can explain to someone. The refusal is a sentence you can copy into a note. The harness saying no on my behalf when the AI gets enthusiastic.

**Move two, dry-run by default.** Every create and revise call defaults to the eBay Verify API. You see exactly what the platform would do, with the warnings and errors the platform would raise, before anything mutates. I pick when to apply. Apply is one explicit flag. Forgetting the flag does nothing. I cannot accidentally update 30 listings because Claude got chatty.

**Move three, audit trail.** Every mutation appends a structured line to `~/.local/share/ebay-seller-tool/audit.log`. Timestamp. Operator (me). Tool name. Inputs (redacted of long fields). Result. If something looks weird in Seller Hub later, I do not have to remember what I did. I just `tail` the log.

**Move four, snapshot-based elasticity.** Listing state appends to `~/.local/share/ebay-seller-tool/price_snapshots.jsonl`. JSON Lines. User-owned. Outside the repo. `jq` it. `pandas` it. Stream it into anything. Months from now I will have time-series data on every listing's price, watcher count, and conversion, ready for elasticity work that does not exist yet.

The synthesis tool, `analyse_listing`, ties them together. One operator turn ("analyse my worst-performing listing this month") fans out to six API calls (sold, unsold, transactions, feedback, traffic, returns), runs the funnel synthesis (impressions, click-through rate, views, watchers, conversion, days-to-sell), checks the floor, and returns one diagnosis with one recommended action. Not a dashboard. A verdict.

Most listing-diagnostic tools you can buy give you a dashboard. Six panels. Forty numbers. Pick a hypothesis. Run with it. Wrong half the time. The verdict version is harder to build (you have to encode the funnel logic, the priority of which break to fix first, the floor-price check, the return-rate weighting) but cheaper to use. Read sentence. Take action. Done.

Model Context Protocol (MCP, the standard Claude Code uses to call external tools) makes the synthesis possible because every signal is already a tool the agent can ask for. The harness is the thing that decides which tools to ask for, in what order, with what fallback when a call fails. The agent sees seventeen tools. It does not see seventeen REST endpoints. The mapping from "what the operator wants" to "what the API actually serves" lives in the harness, not in the prompt.

## The Cassini context (why automation matters here)

eBay's search ranking algorithm is called Cassini. It is real-time. Not nightly batch. A listing rises or falls within hours of the signal moving. The official documentation talks about three signal clusters: relevance (about 40 to 50 percent), seller performance (30 to 40 percent), listing quality and engagement (the remaining 20 to 30 percent). Sixty days with no sales and visibility quietly suppresses. Nobody emails you. The traffic just goes.

The mechanism that matters for any seller running multiple listings: the signal loop is faster than your manual review loop. Three-day-old data is stale. Even one-day-old data on the wrong listing means three days of muted impressions before you notice. Manual review at "once a week" cadence loses every week against any seller who closes the loop in 24 hours.

Promoted Listings has its own twist. The attribution rule changed in January 2026. Old rule, the same person who clicked the promoted listing had to buy. New rule, any person clicks, any other person buys within thirty days, and the platform attributes the sale to the campaign and bills the ad fee. European sellers reported attribution rates climbing from about 35 percent to 80 percent or higher with no measurable lift in actual orders. A disguised fee increase, not a sales-velocity increase.

You cannot fix algorithms by talking to algorithms. You fix them by working the funnel, fast, every day, and refusing to pay for attribution that you would have got for free. That is what the harness does on my behalf.

## What is mine, what is yours

Two layers. The harness, the public layer, [hoiung/ebay-seller-tool](https://github.com/hoiung/ebay-seller-tool), is open. MIT licensed. Take it. Fork it. Run it against your own eBay account. The seventeen tools work for any reseller on the platform. The guardrails work for anyone.

The skill on top, the private layer, is mine. The category-specific title rules. The condition-description templates. The price-warning thresholds. The vocabulary I use in returns conversations. The watch-list of patterns that mean a listing is about to lose its rank. None of that is in the public repo. It lives in my SST3 skill folder and stays there. That is the trade craft. That is twenty years of pattern matching. It is not for sale.

A harness is the place where the public tool meets the private rules. The tool is what anyone can run. The rules are what I have learned from running the trade. Both go in the workshop. Only one goes on GitHub.

This is the model I keep recommending to other operators. Build (or borrow) the harness. Keep the rules. Both bits matter. Either one alone is half the answer.

## So

Same blade metal as trading and blogging. Reshaped for reselling. The repo is public if you want to see what fifteen days of focused work looks like. The philosophy lives over [here](/posts/every-sme-needs-their-own-harness/) if you want the why first.

Build your own. Then come back and tell me what your knife looks like.

<!-- iamhoiend -->
