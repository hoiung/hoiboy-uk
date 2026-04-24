---
title: "Three Reviewers, Restart on Fail. Why I Shipped It."
date: 2026-04-24
draft: true
categories: [tech-ai]
tags: [ai, claude-code, sst3, code-review, plugin-marketplace]
slug: shipping-ralph-review-trio
description: "Three-tier Ralph Review with restart-on-fail. Borrowed the loop pattern from Geoffrey Huntley, layered three SST3 checklists on top, shipped as a Claude Code plugin today."
---

<!-- iamhoi -->

There is a moment when you ship a tool and then point the tool at itself.

This afternoon, a few hours after pushing Ralph Review Trio to a public GitHub repo, I installed it into my own Claude Code session and ran it on the branch that contained the ship. Three tiers. Haiku surface. Sonnet logic. Opus deep. Ten and a half minutes, 235,000 tokens, 116 tool uses. All three came back clean. Five non-blocking observations flagged, none of them about the ship itself.

The tool reviewed its own shipping.

## What it actually is

Three Claude models reading the same diff at increasing depth. Haiku runs first and does the cheap surface checks (file structure, commit hygiene, debug code, visible magic numbers). If it passes, Sonnet runs next and does logic tracing (cross-boundary contracts, null propagation, config wiring, real call-site inspection). If that passes, Opus runs last and does architectural review plus a factual-claims audit on anything the diff writes into documentation.

If any of the three tiers fails, the whole loop restarts from Tier 1.

Not continue-with-a-flag. Not "note the finding and keep going". Restart.

That one rule is what makes the review actually work.

## Why restart-on-fail sounds harsh (and isn't)

Here is why the rule matters. Haiku passes a file. Sonnet, tracing deeper, finds a silent exception handler in that same file. The fix touches the file. Haiku's earlier pass is now against a stale version.

The pragmatic move is to pretend the stale approval still holds. After all, it was only a small change. You fix. You mark Sonnet PASS. You move on.

The problem is that "only a small change" is exactly the class of thing Haiku was supposed to catch. Maybe the fix introduced a debug print. Maybe it changed a magic number. Maybe it added a commented-out `# TODO`. Surface-level mistakes that Haiku would have caught the first time... but Haiku already ran. You cannot go back.

Unless you can. The fix is trivial: any tier failure restarts the whole loop from Tier 1. Pass means all three tiers passed in a row against the same final state.

Yes, it costs more tokens. A hundred Haiku seconds instead of zero. In exchange, every file in the final diff has actually been surface-reviewed in its final form.

It feels harsh on day one. After a month, you stop noticing the extra Haiku cycles and you start trusting the reviews in a way you did not before.

## Where the pattern comes from

Ralph is not mine. It comes from [Geoffrey Huntley](https://ghuntley.com/ralph): a while-true loop that re-feeds the same prompt to an agent until it emits a completion promise. Anthropic published an official `ralph-loop` plugin implementing the mechanic as a slash command, and that plugin is what powers each tier inside mine.

What I layered on top is the three-tier cost-stratified orchestration. One Ralph loop per tier, not one long loop for the whole review. Haiku runs its own ralph-loop against the surface checklist until it emits `<promise>HAIKU_PASS</promise>`. Sonnet runs its own loop against the logic checklist. Opus runs its own loop against the architectural checklist. The controller dispatches them in order, and any deep-tier failure restarts the whole stack from Tier 1.

The 3-tier stack entered [SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness) on 8 January 2026. The initial scaffolding (three tier checklists, a dispatch controller, a restart rule, ~142 combined lines) was all in place within a single evening, committed against `dotfiles#391`.

Three and a half months later, the same three files add up to 416 lines and the checklists have been pulled into more than 430 issues across my two main repos, with ~155 of those closing with all three tier-pass tokens emitted. Over 250 commits across the two repos reference Ralph activity directly. Every new line in a checklist traces back to a class of bug that slipped through an earlier review. The evolution has been bursty-reactive, not gradual: a long quiet middle, then 21 tier-checklist upgrades in 19 days after a cross-boundary contract post-mortem (`auto_pb#1407`) triggered a cascade of governance integrations (Sample Invocation Gate, MCP availability discriminator, Checkbox-MCP audit, Proof of Work canonical signal).

A few catches worth naming, so you do not have to take the shape on faith. Ralph flagged its own hardcoded repository-path assumption hiding in the Haiku tier (`dotfiles#399`). It caught a database helper returning dict-row cursors while callers still indexed by `[0]` tuple style: eight latent bugs across hot paths, one of which was silently writing NULL foreign keys for roughly three out of four audit rows (`auto_pb#1415`). It caught a cache helper quietly substituting a default argument whenever callers forgot to pass one, pretending the code was fine; the fix made the argument required and raised loudly on omission (`auto_pb#1442`). The pattern earns its keep by catching things I was sure were fine.

This is the kind of thing I think of as elegant engineering. Small idea on top of someone else's small idea, neither complicated on its own, both tightening each other. Since it went live in January Ralph has been a reliable bug-catching machine. It just works.

The reviewers lived inside my private dotfiles. Good for me. Useless to anyone else. The Anthropic Agent Skills open standard (December 2025) gave a clean format to publish in: a Skill file, a Plugin package, a marketplace manifest. Two lines to install:

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

Fix was one character pair of braces. The lesson was not. A structural JSON-is-valid check is not a schema-conformance check. The only way to know your plugin spec is right is to run the install loader against it. (AP #18 in my harness exists for exactly this reason.)

**Second break**: install succeeded after the fix. `/reload-plugins` showed the skill registered. I ran the trio on a test branch. The controller dispatched a subagent named `haiku-reviewer` and got:

```
Agent type 'haiku-reviewer' not found.
Available agents: ralph-review-trio:haiku-reviewer, ralph-review-trio:sonnet-reviewer, ralph-review-trio:opus-reviewer
```

Claude Code namespaces plugin-bundled agents as `<plugin-name>:<agent-name>`. My command file said "dispatch `haiku-reviewer`". Wrong. Needed to say "dispatch `ralph-review-trio:haiku-reviewer`".

Another one-line fix. Pushed as v0.2 an hour later. But that is what the dogfood test is for: the real user session, the real controller, the real dispatch. No unit test against a mock loader would have shown me either bug.

I shipped v0.2 before the dogfood run even started.

## What the dogfood run actually found

After both fixes, the trio ran cleanly. On a non-trivial target: 4 Markdown files, 462 insertions, 42 deletions, 8 commits ahead of master. Not a toy review target.

Haiku finished in 101 seconds. Walked the file structure, commit hygiene, checkbox evidence, governance evidence audit, surface-level common-culprit scan. Passed.

Sonnet took five minutes and fifty-two seconds. Ran 60 tool uses, tracing call sites, reading migrations, opening function bodies, verifying null-propagation. Not skimming. Passed.

Opus took two minutes fifty-six seconds. Reviewed the Sonnet result, ran the governance drift audit, overengineering check, factual claims audit. Passed.

Five non-blocking observations flagged, all about other work on the same branch, none about the ship. The review was honest.

Ten and a half minutes of wall clock. 235,000 tokens. 116 tool uses. Against your Claude Code subscription, cheap for the depth. Against one human review... an embarrassing saving.

## What makes this pack different from a generic 3-tier

There are already several 3-tier review packs on the marketplaces. Using three models at three depths is not a differentiator on its own.

The three-tier Ralph orchestration itself is the first differentiator (covered above). The other three hooks are the SST3-specific layers that earn their keep:

Sample Invocation Gate: for any change that touches a pipeline, CLI wiring, cross-module function-argument propagation, or a persistent-state write, Sonnet will not pass without evidence of a real command invocation against a real database. Exit code zero is not enough. AP #18 in the harness exists because exit-zero runs that wrote zero rows are a silent-failure class the harness was built to catch.

Proof of Work governance signal: if you use a governance MCP server for checkbox tracking (I have one), Opus checks that every checked box has a matching evidence entry in a canonical `## Proof of Work` section of the issue body. It refuses narrative-only progress. The rule is strict because soft governance produces shipped products where nobody can reconstruct what was verified against what.

MCP availability discriminator: every reviewer subagent that touches code-graph queries must state `mcp_graph_available: yes | no` on the first line of its result block. `yes` plus grep-only evidence is a fail; `no` plus documented grep fallback is a pass. This one line kills the class of lazy-fallback bugs that would otherwise hide silently in review output.

None of these are new inventions. What is new is packaging them as one installable plugin with an opinionated controller loop.

## Where the provenance ends up

The reviewers are scrubbed from my private dotfiles at commit `9249dbf`. That scrub pin goes into the public README so any future drift between the private canonical and the public pack is auditable. Business identifiers, private trading internals, machine-specific paths... all stripped before the first commit landed in the public repo.

What stays is the pattern teeth. The sequential restart rule. The Sample Invocation Gate. The Proof of Work signal. The MCP availability discriminator. Those are the things worth shipping; the rest was scaffolding.

## What this pack does NOT do

It does not replace human review. It is the pre-human-review floor where every tier's checklist got walked and structured findings are ready for the human. It does not guarantee bug-free code. Three reviewers at three depths will miss things. It does not work on work-in-progress branches; the checklist assumes the change is code-complete, and running it mid-implementation floods you with false positives.

It also works alone, but it works better inside a harness. The same three tier checklists ship as part of [SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness). The standalone plugin exists for people who want to dissect the pattern, or wire the same loop into a review for an LLM other than Claude.

## Install

```
/plugin marketplace add hoiung/sst3-skills
/plugin install ralph-review-trio@sst3-skills
/reload-plugins
```

Then, when a branch is code-complete, `/ralph-review-trio`.

MIT licensed. Fork it, adapt it, ship your own flavour. Repository: [github.com/hoiung/sst3-skills](https://github.com/hoiung/sst3-skills). Issues and PRs welcome. If you find a class of bug the checklist misses, tell me and I will fold it in.

## What comes next

Two more packs drafted privately. Solo workflow governance (phase-checkpoint discipline, branch safety, merge gates) and subagent swarm patterns (layered cross-checking, RESULT schema, frozen scope snippets). Both need their own validation.

If the Ralph Review Trio pack gets traction, the other two follow. If it does not, neither do they.

Ninety-day kill date. No stars, no installs, no signups, no inbound leads at the end of that window and the project comes home. No ego in the kill.

The bet is the distribution surface. The packs are the test.

<!-- iamhoiend -->
