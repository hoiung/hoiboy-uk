---
title: "Reverted code review graphs. Going back to basics"
date: 2026-04-25
categories: [tech-ai]
tags: [mcp, claude-code, ast, code-review, sst3]
slug: no-graphs-back-to-basics
description: "We reverted code-review-graph after two same-day bugs and went back to basics. The rule stayed. The replacement is not even a graph."
draft: true
---

<!-- iamhoi -->

Cutting to the chase: this morning we ripped `code-review-graph` MCP out of our SST3 harness. Same day, I filed the upstream bug report. Same day, I filed the internal issue to replace the whole daemon-MCP path with request-scoped Bash scripts. The rule that pointed at the graph survived all of that. This post is about that line, why it matters more than the tool that was sitting underneath it, and why we are choosing to go back to basics on graph tooling for a while.

## What it was, and why we adopted it

For a couple of months we ran `code-review-graph` MCP as part of every review session. It is a local AST knowledge graph: SQLite for the persistent layer, Tree-sitter for parsing across about a dozen languages... Python, TypeScript, Go, Rust, Java, the usual suspects. Five tools sit on top of the graph. `query` for things like "who calls this function" or "what does this symbol resolve to here". `review` for diff-level structural impact analysis. `graph` for index management. `config` for status. `help` because every well-behaved tool deserves one.

We adopted it earlier in the year because subagent-only structural search was, frankly, slow and lossy on wide-diff queries. Ask a swarm of subagents "what is the blast radius of this change to a hub module" and you get back a brave attempt that frequently misses sites an AST graph would surface in a millisecond. The graph made wide-diff reviews cheap. The five tools were small. The on-disk format was just SQLite. This is roughly the right shape of structural-code data for our use cases, and it stayed roughly right for about ten weeks.

We even built a discriminator rule around it. Every reviewer subagent in our harness emits `mcp_graph_available: yes | no` as the first line of its result block (`yes` plus grep-only evidence is a fail; `no` plus a documented grep fallback is a pass). That rule was introduced in [Shipping the Ralph Review Trio](/posts/shipping-ralph-review-trio/), and it exists precisely because the tool was flaky enough to make "did the reviewer actually use the graph" a question worth answering on every output. The rule was the safety net. The tool was the trapeze.

## What broke

Between 07:13 and 07:34 UTC this morning, my session log shows four consecutive `MCP error -32000: Connection closed` events. The cascade kills the CLI. The MCP loses its handshake mid-session, the proxy crashes, the parent agent gets nothing back, the conversation flatlines. Four times in twenty-one minutes.

By 08:14 UTC I had `dotfiles#444` open, scoped originally as a wrapper-script reliability fix plus an unrelated eBay bug (the kind of bundled-issue you sometimes get when two things break in the same hour and you do not want to lose either context). By 09:09 UTC I had filed [`n24q02m/better-code-review-graph#365`](https://github.com/n24q02m/better-code-review-graph/issues/365) upstream with a full evidence pack: orphan-daemon mechanism (`smart_stdio.py:83-132` plus `local_server.py:71-98`), timestamps for all four disconnect events, the smoking-gun lock file, the healthy lock file from a different session, the eight-day-old orphan, the two coexisting `mcp_core` wheels with incompatible lock formats, the 401 response from `BearerMCPApp.__call__()`, three proposed upstream fixes. About one hour and fifty-six minutes from first observed disconnect to upstream report. Not exactly leisurely, but accurate.

The mechanism is the kind of bug you cannot fix at the application layer. An old `mcp_core` wheel had spawned a detached daemon that survived a previous Claude Code session. The daemon reparents to init via `start_new_session=True`, so it lives forever once the parent exits. Forever! When `uvx` later resolved a NEW `mcp_core` with an incompatible three-line lock format (PID, port, JWT), the new proxy walked into a directory still holding a two-line lock from the old daemon (PID, port, no token). It read line three, got an empty string, sent that empty string as a Bearer token, the daemon returned 401, the proxy dropped stdio. Connection closed. CLI dies. There is no clean way to make a proxy recover from "the daemon I am talking to was started by a different version of me and we now disagree on how to authenticate". You either kill the daemon (sledgehammer) or get the daemon to upgrade itself (architectural daydream). Neither lives at our layer.

Removing the MCP entry from `~/.claude.json` is necessary but not sufficient on its own. The canonical SST3 docs in our harness reference the MCP tool names everywhere... playbook recipes, anti-patterns, workflow gates, the standards file itself, the per-stage prompts in our reviewer flow. If those docs still call `mcp__code-review-graph__query` and friends after the API entry is gone, a future agent reads those docs, tries to invoke a tool with no entry, and the failure mode becomes "tool not found" instead of "tool not used". So the removal has to happen in two places: at the API surface (`~/.claude.json`) and across every canonical doc that names it. That second piece is what `dotfiles#445` is about. (Worth a sibling-note: the MCP framework has multiple architectural rough edges right now beyond ours. The cloud-scope cousin of this story lives at [`anthropics/claude-code#48275`](https://github.com/anthropics/claude-code/issues/48275). Disconnected cloud connectors persist in `claude mcp list` after session resume, cannot be removed via `claude mcp remove`, and silently inject their tool registrations into every system prompt. Token drain, not a crash. Different mechanism from ours, same family. State-cache inspection on my side pins the cloud-scope cause on a `tengu_claudeai_mcp_connectors` flag that re-enumerates connectors from a backend the local config never touches. Different bug, related neighbourhood, mention it and move on.)

## What we tried first

Before I ripped it out, I tried to make it work. The first attempt was a wrapper script around `uvx better-code-review-graph --stdio`: clean stale lock files before each exec, kill orphan daemons whose lock-file format we no longer agree with, log diagnostics to a per-session directory. About ninety lines of Bash, gated by a smoke test, embedded in the MCP startup hook in `~/.claude.json`. The wrapper reduced the failure rate. It did not get it to zero.

The second attempt was the playbook. A 310-line operational guide with an explicitly named section on recovering from a "Connection Closed" disconnect, three numbered steps, and footnotes explaining why each step was needed. Run this command to kill orphans. Run this command to remove stale locks. Run `/mcp` to reconnect. Lovely documentation. Solid recovery procedure. Worked every time.

When your operations doc has a "three-step manual recovery from Connection closed" section, that section IS the architectural smell. Not the recovery itself... the recovery worked, the steps are correct, the playbook is good documentation. The smell is that the recovery is recurring. A tool that needs periodic manual intervention to keep working is a tool that has decided your time is one of its operands. Once you notice the shape it becomes obvious. Architectural costs you measure in seconds-per-incident pile up faster than you think when the incidents are weekly. So the third attempt was the architectural call: get the daemon out of the editor session lifecycle entirely.

## Going back to basics

Before the architectural call, we ran a same-day alternatives evaluation across two categories: daemon-MCP servers, and CLI-first tools that exit per query.

The daemon-MCP category includes some serious projects. Serena (`oraios/serena`) is the obvious next-most-popular option in this niche. It exhibits the exact same `MCP error -32000` symptom in [`#898`](https://github.com/oraios/serena/issues/898), plus a 30GB memory leak in [`#944`](https://github.com/oraios/serena/issues/944), plus init hangs the maintainers have not yet closed out. `isaacphi/mcp-language-server` last shipped a release nearly a year ago. `sdsrss/code-graph-mcp`, `bug-ops/mcpls`, `JudiniLabs/mcp-code-graph`, `chroma-core/chroma-mcp`... all daemon-class. The architectural failure mode is the daemon coupling itself, not the implementation specifics. They all inherit the bug shape that bit us. Different bugs, same shape. Heavyweight platforms are out for orthogonal reasons (Sourcegraph paywalls private code at enterprise tier, Glean has zero published releases, Kythe covers languages I do not write, GitHub's `stack-graphs` was archived in September 2025).

The CLI-first category is the boring choice. `ast-grep` for structural patterns. `tree-sitter` CLI as fallback. `ripgrep` because of course `ripgrep`. `semgrep` for some classes of static analysis. `coverage.py` and `cargo llvm-cov` and `c8` for untested-function detection per language. The native Claude Code LSP tool for per-symbol queries that benefit from a real language server. None of these are exotic. None are new. All exit per query, exit code zero or non-zero, no daemon, no `~/.claude.json` MCP entry, no transport handshake, no resume-replay surface area. They are reliable.

Our position going in: the alternatives all looked reasonable. The off-the-shelf MCP variants are mostly fine in normal use. We chose to go back to basics anyway. Not "everything else is broken so we have to". Not "no off-the-shelf MCP works for our needs". The CLI-first stack is just plainly reliable, and we want OFF the daemon class entirely... not on a different daemon. Going back to basics is the deliberate call.

## The pivot

What replaces it is the wrapper-lane at `dotfiles/SST3/scripts/sst3-graph-*`, scoped as Phase A of a four-phase plan in `dotfiles#445` (the four phases compose: code wrappers, doc-tooling wrappers, cross-class drift detection, harness integration). Eight scripts, one per query type. None of them are a graph any more... no SQLite persistent layer, no Tree-sitter index, no embeddings. They are stateless Bash wrappers that reproduce the old query interface using `ast-grep` for structural patterns, `ripgrep` for literal search, `git` for diff and log, `find` for file enumeration, and `coverage.py` for untested-function detection per language. You invoke a script from the Bash tool inside an agent (main or subagent), it runs, it prints NDJSON, it exits. There is no `~/.claude.json` entry. There is no long-running daemon. Each query starts from nothing and finishes returning nothing in memory. When the next session resumes, there is zero stdio state to replay. Zero!

The contract surface is preserved by JSON-shape match. Scripts emit the same shape of output the MCP would have, so callers in our canonical docs stay textually correct against the new lane. Five tool names map to five script names. Same names, same arguments, same shape. The wiring underneath is different. The wiring above does not need to know.

The architecture has three layers. The CLI scripts are Layer 1. A thin orchestrator (`sst3-check.sh`) is Layer 2. Skill-and-hook integration into the harness is Layer 3. Layered failure isolation is the point. Kill the skill (Layer 3) and the orchestrator and CLIs still run from any shell. Kill the orchestrator (Layer 2) and the CLIs still run from any shell. The bottom layer is always usable for ground-truth debugging. That is what you cannot get from a daemon-MCP coupling: when the daemon is down, the daemon is down, and you find yourself debugging the transport, not the question.

## Why the rule survives

The rule we adopted alongside the original tool is unchanged. AP #19 in our anti-patterns doc enumerates twelve subagent-only moments (voice content protection, intentional-vs-accidental architecture, cross-document semantic audits, opposite-scoping checks, factual-claim provenance...) where graphs of any kind are the wrong tool. Those twelve moments still belong to the subagent swarm. The five-gate pre-query check (existence, freshness, language support, embeddings status, source verification) still gates structural-code queries. The supported-language profile still says exactly which file types are graph-eligible.

The implementation route swapped. The rule did not. That is what good rules look like: they live above the implementation that serves them. When an implementation breaks, the rule survives. The next implementation slots in underneath. Same shape on the surface, different mechanism beneath. Most rules in our harness are written this way on purpose, because the SST3 standards are designed as plain-text contracts that survive tool churn... which is exactly why the rule survived the tool here too. Single mention of the harness, done.

## "For now"

I have not declared graphs dead as a category. The AST data model is still the right shape for structural questions in supported languages. The wrapper-lane scripts are not a deeper insight than a real graph. They are a less ambitious one. We just stopped trusting daemons in our editor session lifecycle for a while.

Vectors are also on the list to explore. Embeddings-based search over the codebase is a different shape of structural-data tooling than an AST graph, and we have not run that experiment yet. It is an obvious next angle to test once the wrapper-lane has bedded in. Whether it enhances the SST3 harness or just adds another rough edge is a question the experiment answers, not the architectural call to make now.

If `n24q02m/better-code-review-graph#365` ships a fix and the resume-replay class in `claude-code#48275` gets closed, we may pull a graph MCP back in the future. The decision rule it would slot under is the same one that sits there now. The tool will be different. The line between the two is what matters.

<!-- iamhoiend -->
