---
title: "Shipping Ralph Review Trio as a Claude Code Plugin"
date: 2026-04-24
draft: true
categories: [tech-ai]
tags: [ai, claude-code, sst3, code-review, plugin-marketplace]
slug: shipping-ralph-review-trio
description: "Three sequential reviewers, restart-on-fail. Battle-tested in my private SST3 harness, now installable by anyone in two lines."
---

<!-- iamhoi -->

There is a moment when you ship a tool and then point the tool at itself.

This afternoon, a few hours after pushing Ralph Review Trio to a public GitHub repo, I installed it into my own Claude Code session and ran it on the branch that contained the ship. Three tiers, Haiku surface, Sonnet logic, Opus deep. Ten and a half minutes, 235,000 tokens, 116 tool uses. All three came back clean. Five non-blocking observations flagged, none about the ship itself.

The tool reviewed its own shipping and said the work was fine. I have been building software a long time and I do not remember the last time I felt that kind of specific quiet satisfaction.

## What Ralph Review Trio actually is

Three sequential code reviewers at increasing depth. Haiku for surface. Sonnet for logic. Opus for architecture. Each reviewer runs its own checklist. If any tier fails, the whole loop restarts from Tier 1 after the fixes are applied. There is no next-tier-with-a-flag shortcut. Pass means all three passed.

The restart rule sounds harsh. It is not harsh. It is the thing that makes the review actually work.

Bugs caught by a deeper tier often invalidate earlier-tier findings. If Sonnet spots a silent fallback that Haiku missed, the fix may touch the same file Haiku already approved. You can pretend the earlier approval is still valid. In practice it is not. The safer move is to re-run the cheap tier and re-verify. A hundred Haiku seconds against five minutes of Sonnet later is a trade you take every single time.

## Why I built this in a harness, not a prompt

<!-- iamhoi-skip -->
I run my solo engineering workflow inside a single-source-of-truth harness I call SST3. Subagent orchestration, structured RESULT blocks, checkpoint MCP, explicit governance signals, voice guards, the whole stack. The harness is its own thing; the review loop is one component of it.
<!-- iamhoi-skipend -->

The review loop used to live inside my private dotfiles repo. Good for me, useless to anyone else. Short of cloning my whole harness, no one could get the benefit of the checklist structure, the restart rule, the subagent discipline, or the two years of tightening that sit behind those checklist bullets.

The Anthropic Agent Skills open standard changed that. Since December 2025, there is a file format for describing a Skill, a package for describing a Plugin, and a marketplace format for listing them. The standard is clean. If I follow it, my private review loop becomes installable by anyone with Claude Code. Two lines:

```
/plugin marketplace add hoiung/sst3-skills
/plugin install ralph-review-trio@sst3-skills
```

That is the ship.

## What makes this pack different from any other 3-tier review

There are already a dozen code-review packs on the marketplaces. Half of them use some variant of Haiku + Sonnet + Opus. The fact that you use three models at different depths is not a differentiator on its own.

Here is what is different in this one.

**Sequential with restart-on-fail, not parallel with aggregation.** Most tools run the three reviewers in parallel and aggregate their outputs. That feels efficient. It is actually the wrong shape for the problem. Failures at deeper tiers often change the correctness of earlier tiers; you need the loop to restart, not just note both findings and keep going.

**Sample Invocation Gate.** For any change that touches a pipeline, a CLI wiring, a cross-module function-argument propagation, or a persistent-state write, Sonnet requires evidence of a real command invocation against a real database. Exit code zero is not enough. I have too many scars from exit-zero runs that wrote zero rows to trust a unit test on its own.

**Proof of Work governance signal.** If you are using a governance MCP server for checkbox tracking (I have one, it is trivial to adapt to any project), Opus checks that every checked box has a matching evidence entry in a canonical `## Proof of Work` section of the issue body. It will not accept narrative progress as evidence. The rule is strict because the consequence of soft governance is a shipped product where nobody can reconstruct what was verified against what.

**MCP availability discriminator.** Every reviewer subagent that touches code-graph queries must state `mcp_graph_available: yes | no` on the first line of its result. If it says yes and then falls back to grep, that is a fail. If it says no and falls back with documented evidence, that is a pass. This one rule kills the entire class of lazy-fallback bugs that would otherwise hide silently in review output.

None of these are new inventions in software engineering. What is new is packaging them as a single, installable Claude Code plugin with an opinionated controller loop that enforces them.

## The dogfood test, in detail

The run I started this post with. My branch on dotfiles had eight commits of mixed content, four Markdown files, 462 insertions, 42 deletions. Not a small review target. Not a large one either. A reasonable branch to test against.

Haiku finished in 101 seconds. Went through the file structure, the commit hygiene, the checkbox evidence, the governance evidence audit, the surface-level common-culprit scan. Passed.

Sonnet took five minutes and fifty-two seconds. Ran 60 tool uses. That is Sonnet actually tracing call sites, reading migrations, opening function bodies, verifying that null-propagation annotations match reality. It did not just skim. Passed.

Opus took two minutes fifty-six seconds. Reviewed the Sonnet result, did the governance drift audit (Tier A vs Tier B classification worked correctly), ran the overengineering check, looked at factual claims in documentation. Passed.

Five non-blocking observations flagged, none of them about the ship. They were about other work on the same branch. The review was honest.

Total ten and a half minutes of wall clock, 235,000 tokens. If you bill that against your Claude Code subscription, it is genuinely cheap for the depth of review. If you compare it to one round of actual human code review, it is an embarrassing saving.

## Where the provenance ends up

The source of these reviewers is scrubbed from my private dotfiles at commit `9249dbf`. That scrub pin goes into the public README so any future drift between the private canonical and the public pack is auditable. Business identifiers, private trading internals, file paths that reference my own machine, all stripped before the first commit to the public repo landed.

What stays is the pattern teeth. The sequential restart rule. The Sample Invocation Gate. The Proof of Work signal. The MCP availability discriminator. Those are the things worth shipping; the rest was scaffolding.

## What this pack does not do

It does not replace human review. It is a pre-human-review verification that every tier's checklist got walked. The human still reads the diff, asks the architectural question, spots the thing nobody thought to put in a checklist. This tool is a floor, not a ceiling.

It does not guarantee your code is bug-free. Three reviewers at three depths will miss bugs. Anyone claiming otherwise is selling snake oil. What it does is remove the class of bugs that a structured checklist would have caught, before the human gets involved.

It does not work well on work-in-progress branches. The checklist assumes the change is code-complete. Running it mid-implementation gives you a hundred false positives because half the features are not wired yet.

## Install

```
/plugin marketplace add hoiung/sst3-skills
/plugin install ralph-review-trio@sst3-skills
/reload-plugins
```

Then, when a branch is code-complete, `/ralph-review-trio`.

MIT licensed. Fork it, adapt it, ship your own flavour. The repository is [github.com/hoiung/sst3-skills](https://github.com/hoiung/sst3-skills). Issues and PRs welcome. If you find a class of bug the checklist misses, tell me and I will fold it in.

## What comes next

Two more packs are drafted in private but not yet public. Solo workflow governance (phase-checkpoint discipline, branch-safety rules, merge gate) and subagent swarm patterns (layered cross-checking, RESULT block schema, frozen scope snippets). Both need their own validation before I put them into the marketplace. If the Ralph Review Trio pack gets any traction, the other two follow.

If none of them ship, none of them ship. I have a kill date on the whole experiment. Ninety days from today. No stars, no installs, no signups, no inbound leads, the project comes home and I redirect the effort to something else. Building the distribution surface is the bet; the packs are the test.

<!-- iamhoiend -->
