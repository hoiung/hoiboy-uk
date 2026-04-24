---
title: "Three Reviewers, Restart on Fail. Why I Shipped It."
date: 2026-04-24
draft: true
categories: [tech-ai]
tags: [ai, claude-code, sst3, code-review, plugin-marketplace]
slug: shipping-ralph-review-trio
description: "Three sequential Claude reviewers, any fail restarts from tier one. Lived in my private harness for months. Today I shipped it as a Claude Code plugin and watched it review its own ship."
---

<!-- iamhoi -->

There is a moment when you ship a tool and then point the tool at itself.

This afternoon, a few hours after pushing Ralph Review Trio to a public GitHub repo, I installed it into my own Claude Code session and ran it on the branch that contained the ship. Three tiers. Haiku surface. Sonnet logic. Opus deep. Ten and a half minutes, 235,000 tokens, 116 tool uses. All three came back clean. Five non-blocking observations flagged, none of them about the ship itself.

The tool reviewed its own shipping.

I have been building software for a long time and I do not remember the last time I felt that kind of specific quiet satisfaction.

## What it actually is

Three Claude models reading the same diff at increasing depth. Haiku runs first and does the cheap surface checks (file structure, commit hygiene, debug code, visible magic numbers). If it passes, Sonnet runs next and does logic tracing (cross-boundary contracts, null propagation, config wiring, real call-site inspection). If that passes, Opus runs last and does architectural review plus a factual-claims audit on anything the diff writes into documentation.

If any of the three tiers fails, the whole loop restarts from Tier 1.

Not continue-with-a-flag. Not "note the finding and keep going". Restart.

That one rule is the thing that makes the review actually work, and it is the rule I kept getting wrong for about four months before it clicked.

## Why restart-on-fail sounds harsh (and isn't)

Here is the scenario I kept running into. Haiku would pass a file. Sonnet would find a silent exception handler in that same file and I would fix it. The file changed. Haiku's pass was now against a stale version of the file.

The pragmatic move is to pretend the stale approval still holds. After all, it was only a small change. You fix. You mark Sonnet PASS. You move on.

The problem is that "only a small change" is exactly the class of thing Haiku was supposed to catch. Maybe the fix introduced a debug print. Maybe it changed a magic number. Maybe it added a commented-out `# TODO`. Surface-level mistakes that Haiku would have caught the first time... but Haiku already ran. You cannot go back.

Unless you can. And the fix is trivial. Any tier failure restarts the whole loop from Tier 1. Pass means all three tiers passed in a row, against the same final state of the code.

Yes, it costs more tokens. A hundred Haiku seconds instead of zero. In exchange, every file in the final diff has actually been surface-reviewed in its final form, not in some intermediate state nobody remembers.

It feels harsh on day one. After a month, you stop noticing the extra Haiku cycles and you start trusting the reviews in a way you did not before.

## Why I built it in a harness, not a prompt

<!-- iamhoi-skip -->
I run my solo engineering workflow inside a [SST3-AI-Harness](https://github.com/hoiung/SST3-AI-Harness) (single source of truth version 3), a governance harness I evolved out of the wreckage of my earlier multi-agent experiments. Subagent orchestration, structured RESULT blocks, checkpoint MCP servers, voice guards, the whole stack. The harness is its own thing; the review loop is one component.
<!-- iamhoi-skipend -->

The review loop used to live inside my private dotfiles. Good for me. Useless to anyone else. Short of cloning my whole harness, no one could get the benefit of the checklist structure, the restart rule, the subagent discipline, or the months of tightening that sit behind those checklist bullets.

The Anthropic Agent Skills open standard changed the calculation. There is now a file format for describing a Skill, a package for describing a Plugin, and a marketplace format for listing them. If I follow the spec, my private review loop becomes installable by anyone with Claude Code. Two lines:

```
/plugin marketplace add hoiung/sst3-skills
/plugin install ralph-review-trio@sst3-skills
```

That was the plan.

## The two things that broke on ship day

The plan did not survive first contact. It rarely does.

**First break**: I packaged the plugin, pushed it to GitHub, ran the marketplace add from Claude Code. Succeeded. Ran the install. Failed.

```
Failed to install: invalid manifest file
Validation errors: repository: Invalid input: expected string, received object
```

My `plugin.json` had `repository` as an npm-style `{type, url}` object. Claude Code expected a plain URL string. JSON syntax was valid. Schema validation passed. The real install loader rejected it on a structural mismatch that no offline check would have caught.

Fix was one character pair of braces. The lesson was not. A structural JSON-is-valid check is not a schema-conformance check. The only way to know your plugin spec is right is to run the install loader against it. (This is the pattern AP #18 exists for in my harness. The scar tissue is real.)

**Second break**: install succeeded after the fix. `/reload-plugins` showed the skill registered. I ran the trio on a test branch. The controller dispatched a subagent named `haiku-reviewer` and got:

```
Agent type 'haiku-reviewer' not found.
Available agents: ralph-review-trio:haiku-reviewer, ralph-review-trio:sonnet-reviewer, ralph-review-trio:opus-reviewer
```

Claude Code namespaces plugin-bundled agents as `<plugin-name>:<agent-name>`. My command file said "dispatch `haiku-reviewer`". Wrong. Needed to say "dispatch `ralph-review-trio:haiku-reviewer`".

Another one-line fix. Pushed as v0.2 an hour later. But that is what the dogfood test is for... it is not the review that finds these. It is the real user session, the real controller, the real dispatch. No amount of unit testing against a mock plugin loader would have shown me either of those two bugs.

I shipped v0.2 before the dogfood run even started.

## What the dogfood run actually found

After both fixes, the trio ran cleanly. On a non-trivial target: 4 Markdown files, 462 insertions, 42 deletions, 8 commits ahead of master. Not a toy review target.

Haiku finished in 101 seconds. Walked the file structure, commit hygiene, checkbox evidence, governance evidence audit, surface-level common-culprit scan. Passed.

Sonnet took five minutes and fifty-two seconds. Ran 60 tool uses. That is Sonnet actually tracing call sites, reading migrations, opening function bodies, verifying null-propagation annotations match reality. Not skimming. 60 tool uses is real work. Passed.

Opus took two minutes fifty-six seconds. Reviewed the Sonnet result, ran the governance drift audit (Tier A vs Tier B cadence classification worked correctly), did the overengineering check, ran the factual claims audit. Passed.

Five non-blocking observations flagged, all about other work on the same branch, none about the ship. The review was honest.

Ten and a half minutes of wall clock. 235,000 tokens. 116 tool uses total. If you bill that against your Claude Code subscription, it is genuinely cheap for the depth of review. If you compare it to one round of human code review... it is an embarrassing saving.

## What makes this pack different from a generic 3-tier

There are already several 3-tier review packs on the marketplaces. Using three models at three depths is not a differentiator on its own.

Four hooks kept from the harness that I think earn their keep. Sequential restart-on-fail is the big one (covered above). The other three:

Sample Invocation Gate: for any change that touches a pipeline, CLI wiring, cross-module function-argument propagation, or a persistent-state write, Sonnet will not pass without evidence of a real command invocation against a real database. Exit code zero is not enough. AP #18 in the harness exists because exit-zero runs that wrote zero rows are a silent-failure class I have fixed too many times.

Proof of Work governance signal: if you use a governance MCP server for checkbox tracking (I have one), Opus checks that every checked box has a matching evidence entry in a canonical `## Proof of Work` section of the issue body. It refuses narrative-only progress. The rule is strict because soft governance produces shipped products where nobody can reconstruct what was verified against what.

MCP availability discriminator: every reviewer subagent that touches code-graph queries must state `mcp_graph_available: yes | no` on the first line of its result block. `yes` plus grep-only evidence is a fail; `no` plus documented grep fallback is a pass. This one line kills the class of lazy-fallback bugs that would otherwise hide silently in review output.

None of these are new inventions. What is new is packaging them as one installable plugin with an opinionated controller loop.

## Where the provenance ends up

The reviewers are scrubbed from my private dotfiles at commit `9249dbf`. That scrub pin goes into the public README so any future drift between the private canonical and the public pack is auditable. Business identifiers, private trading internals, machine-specific paths... all stripped before the first commit landed in the public repo.

What stays is the pattern teeth. The sequential restart rule. The Sample Invocation Gate. The Proof of Work signal. The MCP availability discriminator. Those are the things worth shipping; the rest was scaffolding.

## What this pack does NOT do

It does not replace human review. It is the pre-human-review floor. Every tier's checklist got walked, evidence was captured, structured findings were produced. The human still reads the diff, asks the architectural question, spots the thing nobody put in a checklist.

Bug-free code is not a thing it guarantees. Three reviewers at three depths will miss bugs. Anyone claiming otherwise is selling snake oil.

Work-in-progress branches are not its problem space either. The checklist assumes the change is code-complete. Run it mid-implementation and you will get a hundred false positives because half the features are not wired yet.

## Install

```
/plugin marketplace add hoiung/sst3-skills
/plugin install ralph-review-trio@sst3-skills
/reload-plugins
```

Then, when a branch is code-complete, `/ralph-review-trio`.

MIT licensed. Fork it, adapt it, ship your own flavour. Repository: [github.com/hoiung/sst3-skills](https://github.com/hoiung/sst3-skills). Issues and PRs welcome. If you find a class of bug the checklist misses, tell me and I will fold it in.

## What comes next

Two more packs drafted privately but not public yet. Solo workflow governance (phase-checkpoint discipline, branch safety, merge gates) and subagent swarm patterns (layered cross-checking, RESULT schema, frozen scope snippets). Both need their own validation before they land in the marketplace.

If the Ralph Review Trio pack gets any traction, the other two follow. If it does not... neither do they.

Ninety-day kill date on the whole experiment. No stars, no installs, no signups, no inbound leads at the end of that window? Project comes home. Effort redirects to something winning. No ego in the kill decision.

The bet is the distribution surface. The packs are the test.

<!-- iamhoiend -->
