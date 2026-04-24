---
title: "Skills"
description: "SST3-AI-Harness skills, packaged up as installable Claude Code plugins. Free, MIT-licensed, dogfooded."
---

A small, growing collection of the workflows that run inside [SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness), packaged as installable Claude Code plugins. Free. MIT-licensed. Dogfooded on the same code that produced them.

One pack ships live today. The rest follow if this one finds an audience.

## Ralph Review Trio

Three Claude models reading the same diff at increasing depth. Haiku runs surface checks first. If it passes, Sonnet runs logic checks. If that passes, Opus runs architectural review. Any tier fails, the whole loop restarts from Tier 1.

The rule that makes it work: restart-on-fail. Pass means all three tiers passed in a row against the same final code.

### Install

```
/plugin marketplace add hoiung/sst3-skills
/plugin install ralph-review-trio@sst3-skills
/reload-plugins
```

Then, when a branch is code-complete, run `/ralph-review-trio`.

### Links

- **Deep dive**: [Three Reviewers, Restart on Fail. Why I Shipped It.]({{< ref "/posts/shipping-ralph-review-trio" >}})
- **Source**: [github.com/hoiung/sst3-skills](https://github.com/hoiung/sst3-skills)
- **Scrubbed from private dotfiles @ commit `9249dbf`**. Public pack drift against that pin is auditable.

### What it is not

Not a human-review replacement. Not a bug-free guarantee. Not a fit for work-in-progress branches. See the blog post for the full boundary.

## What is coming

Two more packs sit drafted privately.

- **Solo Workflow Governance**: phase-checkpoint discipline, branch safety, merge gates.
- **Subagent Swarm Patterns**: layered cross-checking, RESULT schema, frozen scope snippets.

Both ship if Ralph Review Trio gets traction. Ninety-day kill date. No stars, no installs, no signups, no inbound leads at the end of that window and the project comes home. No ego in the kill.
