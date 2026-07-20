# 16. AI Bot and SEO Crawl Policy (Decision Record)

**Date:** 2026-05-31
**Status:** Decided and implemented (`layouts/robots.txt`).
**Scope:** Should hoiboy.uk allow or block search-engine crawlers and AI bots, and what does that mean for SEO and for being cited in AI chat answers?

This is an infrastructure and SEO decision record, not voice prose. It exists so the crawl-policy decision is durable and reviewable (and, since the repo is portfolio evidence, so the reasoning is visible).

## The question (verbatim)

The owner asked three things:

1. Does allowing search engine crawlers and AI bots help our SEO ranking?
2. Can AI chats find us and use our work, so we become referenced as a subject-matter expert?
3. If we block bots from scanning, do we miss out on being referenced in AI chats, is blocking a missed opportunity?

## TL;DR recommendation

**Allow every bot class, and advertise the sitemap.** That is what was implemented: `layouts/robots.txt` now serves an allow-all policy (`User-agent: *`, empty `Disallow:`) plus a `Sitemap: https://hoiboy.uk/sitemap.xml` line that the previous bare default was missing.

The one mental-model correction that resolves the owner's fear: **training crawls do not produce AI-chat citations; only the search and retrieval bot class does.** Blocking the AI-training bots would cost zero citations. The only block that would actually suppress AI-chat citations is blocking the search and retrieval class, which we are deliberately not doing.

## Bot taxonomy (three classes, not one)

"AI bots" is not a single thing. There are three classes, controlled independently, with very different consequences:

| Class | Example tokens | What it does | Effect of blocking |
|---|---|---|---|
| Search crawlers | `Googlebot`, `bingbot` | Build the search index | Catastrophic: removes you from Search, and from AI Overviews and Copilot (which reuse the search index) |
| AI live-retrieval (cite and refer) | `OAI-SearchBot`, `ChatGPT-User`, `Claude-SearchBot`, `Claude-User`, `PerplexityBot`, `Perplexity-User` | Fetch and cite a page to answer a live user query | Suppresses AI-chat citations: this is the only block that costs you citations |
| AI training (no citation effect) | `GPTBot`, `ClaudeBot`, `Google-Extended`, `CCBot`, `meta-externalagent`, `Bytespider` | Collect content to train model weights | Zero citation cost; only affects whether your text contributes to future model training |

Sources for the per-class split: OpenAI (https://developers.openai.com/api/docs/bots), Anthropic (https://support.claude.com/en/articles/8896518), Perplexity (https://docs.perplexity.ai/docs/resources/perplexity-crawlers).

## Per-class verdict

| Bot class | Verdict | Why |
|---|---|---|
| Search crawlers (Googlebot, bingbot) | ALLOW (non-negotiable) | Crawl access is a prerequisite for ranking, and the search index is reused by Google AI Overviews and Microsoft Copilot |
| AI live-retrieval (OAI-SearchBot, Claude-SearchBot, PerplexityBot, and the user-fetch siblings) | ALLOW (this is the GEO money class) | These produce the cited, clickable links and referral traffic the owner wants |
| AI training (GPTBot, ClaudeBot, Google-Extended, CCBot, and others) | ALLOW (owner's call, no citation cost either way) | Training feeds model weights, not citations; the goal here is exposure, not content protection, so the simplest stance is allow-all |

## Answering the three questions

### 1. Does allowing crawlers help SEO ranking?

It helps SEO **access**, not **rank**. Crawling is a prerequisite for appearing in search results, but Google is explicit that crawling itself is not a ranking signal (https://developers.google.com/crawling/docs/myths-about-crawling). For a small site, crawl policy is not a meaningful ranking lever at all (https://developers.google.com/crawling/docs/crawl-budget). What the change does add is a `Sitemap:` line, which speeds discovery of every page (https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap). So: allowing crawlers and advertising the sitemap cannot hurt ranking and removes a discovery obstacle, but it is not a ranking boost on its own. Ranking is earned by content quality and links.

### 2. Can AI chats find us and cite our work?

Yes, and the mechanism is the search and retrieval bot class, not training. When you allow `OAI-SearchBot`, `Claude-SearchBot`, `PerplexityBot` and their live-fetch siblings, your pages become eligible to be cited in ChatGPT, Claude, and Perplexity answers. Two of the biggest surfaces need no AI-specific opt-in at all: Google AI Overviews reuses the ordinary Googlebot index (https://developers.google.com/search/docs/appearance/ai-features), and Microsoft Copilot Search is built into Bing and answers with citations to web pages, so it reuses Bing's existing web index rather than needing an AI-specific opt-in (https://blogs.bing.com/search/April-2025/Introducing-Copilot-Search-in-Bing). The caveat is that index-reuse surfaces only cite a page that is actually indexed and snippet-eligible, so for a new site the real work is getting genuinely indexed and ranked.

### 3. Is blocking a missed opportunity?

For hoiboy.uk specifically, yes, blocking the retrieval class would be a real missed opportunity. There is a widely-quoted study showing that sites which block AI bots still get cited (BuzzStream: https://www.buzzstream.com/blog/news-block-ai-bots-citations/), and it is tempting to read that as "blocking is free." It is not. That stat is correlation, not causation: the sites in it are large, already-indexed, high-authority domains whose citations come from pre-block crawls, Common Crawl reuse, and search-result extraction. That mechanism does not transfer to a small, new, low-authority personal blog. For a site like this one, with no existing authority to coast on, allowing the live-retrieval class is materially important to being cited at all. So we allow it.

The flip side: blocking the **training** class would not be a missed citation opportunity, because training does not drive citations. That is purely a content-protection choice with no citation downside, which is why it is offered below as an optional, deferred variant.

## What was implemented

`layouts/robots.txt` (a Hugo template, since `enableRobotsTXT = true` in `config/_default/hugo.toml`):

```
User-agent: *
Disallow:

Sitemap: {{ "sitemap.xml" | absURL }}
```

A production build (`hugo --gc --minify -e production`) resolves this to a `public/robots.txt` whose Sitemap line reads `Sitemap: https://hoiboy.uk/sitemap.xml`. The per-route `noindex` on `/private/tools/meet-recorder/*` in `static/_headers` is left untouched: that is correct as-is, because it is a `noindex` on a crawlable route (a page must stay crawlable for the crawler to see its `noindex`, and a `Disallow` would defeat that). See https://developers.google.com/search/docs/crawling-indexing/block-indexing.

Note that robots.txt is advisory (honor-system) only. Some user-triggered fetchers state plainly that robots.txt rules may not apply to them, and at least one crawler has been accused of ignoring directives entirely. The repo file records intent and is honored by the well-behaved search and citation bots; it is not a hard enforcement layer.

## Cloudflare edge state (MEASURED 2026-07-20: FAILED, then FIXED the same day)

robots.txt is advisory; Cloudflare is the only layer that hard-enforces at the network edge. This section previously held a four-point checklist for the owner to confirm "once". That checklist was written 2026-05-31 and never performed. It is replaced here with an actual measurement, plus a standing gate so the state cannot go unverified again.

**Result** (blog-priv#55 Phase 10, via `scripts/check-ai-crawler-access.sh`, 2026-07-20):

| Class | Bot | Status |
|---|---|---|
| CITATION | OAI-SearchBot | 403 blocked |
| CITATION | ChatGPT-User | 403 blocked |
| CITATION | Claude-SearchBot | 403 blocked |
| CITATION | Claude-User | 403 blocked |
| CITATION | PerplexityBot | 403 blocked |
| CITATION | Perplexity-User | 403 blocked |
| TRAINING | GPTBot | 403 blocked |
| TRAINING | ClaudeBot | 403 blocked |
| TRAINING | CCBot | 403 blocked |
| TRAINING | Google-Extended | 200 ok |
| TRAINING | meta-externalagent | 403 blocked |
| TRAINING | Bytespider | 403 blocked |

**All six citation-class crawlers are blocked.** The same URL returns 200 to a plain browser user-agent and to an empty user-agent, so this is user-agent-based blocking at the edge, not an outage. The Google crawler family is the sole exception, with `Google-Extended` and a `Googlebot` control both returning 200, so it is allow-listed as a verified bot.

Three of those four controls (browser user-agent, empty user-agent, `Googlebot`) are implemented in `scripts/check-ai-crawler-access.sh` and print under a `CONTROLS` heading on every run, so the standing gate reproduces its own evidence rather than citing a measurement nobody can re-run. They are reported only and do not touch the exit code, which the citation class alone gates. The fourth control, ruling out rate limiting by re-probing in isolation with three-second gaps and by repeating runs, was a manual one-off during Phase 10; the 403s were deterministic across those runs. It is not in the script, because a gate that sleeps between every probe is too slow to run weekly.

**This value moved between two probes on the same day.** An earlier probe during Stage 3 of blog-priv#55 recorded OAI-SearchBot at 200 and four of the five training crawlers it covered at 200. The measurement above, taken a few hours later, found six of six citation crawlers blocked and five of six training crawlers blocked. Both readings are kept on purpose: the state is not stable, and no single reading should be treated as the settled value. Any figure here is valid only for its timestamp, which is the argument for the scheduled gate rather than another one-time check.

The two readings cover different bot sets and the counts are NOT directly comparable. The Stage 3 probe covered five training tokens; `Bytespider` was in the class table above but was never probed, so the table under-covered its own taxonomy. That gap was found in Ralph round 10 and closed here: `Bytespider` was added to `TRAINING_BOTS`, probed twice with three-second spacing (403 both times, deterministic), and added to the table. The training class is now six tokens in the taxonomy, six in the script, and six in the measured table.

**The previous low-risk reasoning was wrong.** This section used to argue that Cloudflare's 2025 "Content Independence Day" AI-block default applied only to newly-onboarded domains, so an established zone was low risk and the check was merely "worth doing". The zone is in fact blocking. Reasoning about a vendor default is not a substitute for measuring the live state.

### Operator ruling: training vs citation (2026-07-20, SUPERSEDED same day)

The owner's first position, verbatim: *"I dont mind training with our site as long as our sites are cited for it."*

**That condition is not expressible as configuration.** Training and citation are separate bot classes (see the crawler-class table earlier in this document, sourced to the OpenAI, Anthropic and Perplexity crawler docs). A training crawl never emits a citation, and no vendor offers a cite-for-training contract. The ruling was therefore recorded as an aspiration, not as a control.

### Operator ruling: SUPERSEDING (2026-07-20)

Told that no vendor offers a cite-for-training contract, the owner reversed the position. Verbatim:

> *"i dont want to give bots free training if i am not cited. i want to block that"*
>
> *"all 3 domains and future should always follow this same framework"*

**This is now the standing framework: citation ALLOWED, training BLOCKED, on hoiboy.uk, cuarchitects.co.uk, speak2lola.com, and every future domain.** It is not a per-site judgement call. The reasoning is that the conditional in the first ruling can never be satisfied, so an unconditional give is the only thing "allow training" can actually mean, and the owner declined it.

The framework is written up once, for reuse, in `docs/research/17_AI_CRAWLER_FRAMEWORK.md`. That document is the thing to read when standing up a new domain; this section records only the decision and the date.

### Fixed 2026-07-20. The cause, as this section asked to be recorded

The four candidates above were checked by READING the zone config through the API before writing anything. **Exactly one was the cause: `ai_bots_protection` was set to `block`.** The other three were already correct: `fight_mode` was `false`, `crawler_protection` was `disabled`, and `is_robots_txt_managed` was `false`. Flipping all four blind would have changed three settings for nothing and left no way to attribute the fix.

`ai_bots_protection` is the coarse legacy switch. It takes the citation class down with the training class, which is exactly what this issue found and why it must not be re-enabled.

Item 3 above is now **inverted on purpose**. Managed robots.txt was turned ON, not confirmed off, because it is the mechanism that expresses the training block: it serves a `Content-Signal: search=yes,ai-train=no,use=reference` line plus `Disallow: /` for nine training crawlers, and leaves the citation class to fall under `User-agent: *`. The original instruction assumed the repo-served file was the only one that mattered. It is not: **Cloudflare PREPENDS the managed block ahead of the origin's file rather than replacing it**, so both records are served and a repo edit cannot remove the managed one.

Verified after the change: `bash scripts/check-ai-crawler-access.sh https://hoiboy.uk/` exits 0, all six citation crawlers reachable, all six training crawlers carrying `Disallow: /`.

### Correction: the granular presets are partly enforced, not unenforced

An earlier note in this workstream recorded that the granular presets (`ai_training` / `ai_search` / `ai_user`) are "accepted by the API but not enforced" before Cloudflare's 2026-09-15 migration. That was over-generalised from probing GPTBot alone. Measured across the full class:

- hoiboy.uk with `ai_training: block` → CCBot **403**, Bytespider **403**, the other four training tokens 200
- cuarchitects.co.uk with `ai_training: disabled` → all six training tokens **200**

So the preset does real work today, on a subset of crawlers. It is set on all three zones so the 2026-09-15 migration activates the full framework natively without a revisit. Until then robots.txt carries the rest, and robots.txt is honour-system: an edge rule is the only hard enforcement. See `docs/research/17_AI_CRAWLER_FRAMEWORK.md`.

### Standing gate

`scripts/check-ai-crawler-access.sh` exits non-zero while any citation-class crawler is blocked. `.github/workflows/ai-crawler-access.yml` runs it weekly and on demand, non-blocking, because an edge setting can regress with no repo change and nothing in the repo would show it.

**Honesty bound.** Unblocking is necessary, not sufficient. An access denial guarantees zero citation from that engine; removing it guarantees nothing in return. No reliable method for measuring AI citation currently exists, so success here is "the crawlers are no longer blocked", never "we are now cited".

## Block training only: ADOPTED 2026-07-20 (was "deferred, not built")

This section used to describe blocking training while keeping every citation path open as a "best of both" alternative that was **deferred and not built**, on the reasoning that there was no current need because the goal is exposure rather than protection. The stated trigger to revisit was "if the owner later wants to protect content from model training".

**That trigger fired the same day.** The owner's superseding ruling above is exactly it, so this is no longer a deferred variant: it is the implemented policy on all three zones and the standing default for future ones. The mechanism and the reusable procedure are in `docs/research/17_AI_CRAWLER_FRAMEWORK.md`. The description below is kept because it is still an accurate account of what the policy does and why it costs nothing in citation terms.

The variant `layouts/robots.txt` would keep all search and retrieval bots on an empty `Disallow:` (allowed) and add explicit block blocks for the training class, for example:

```
User-agent: GPTBot
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: *
Disallow:

Sitemap: {{ "sitemap.xml" | absURL }}
```

This blocks the training bots (`GPTBot` and siblings via `Disallow: /`) while every search and live-retrieval bot stays allowed, so citations are unaffected. Because robots.txt is advisory, a hard training block would also need a Cloudflare edge rule to be enforced against non-compliant crawlers.

## In-content factors (out of scope here, and largely retracted)

robots.txt is not the thing to obsess over. This section previously presented the in-content work as the higher-leverage half of the job. A 2026-07-19 evidence review has since withdrawn most of that framing. The section is corrected in place rather than deleted, so the retraction stays auditable.

**Survives.** Clean, extractable HTML. The superseding brief retains it as checklist item 6, but explicitly on general crawlability grounds, that is, as hygiene rather than as a citation lever.

**Retracted.** An earlier revision of this section attributed materially more AI citations to writing in roughly 120-to-180-word sections under clear headings, on the authority of a study that appears nowhere in the Sources list below. That citation claim is withdrawn. Section length may still be a sound writing-craft preference; it is simply not evidence-backed as a GEO lever. Withdrawing the claim is a statement about the evidence, not a finding that the practice fails to help.

**Unsourced.** Visible author and credential signals, and freshness. Both were asserted here with no source, and the superseding brief never evaluates either as a citation factor, so both remain unsourced on this record. (The brief does mention freshness once, in its own summary of this retraction. That is a description of the claim being withdrawn here, not independent support for it, and neither signal is enumerated anywhere in the brief's own list of known evidence limits.) The brief's silence on a tactic is not a positive finding about it in either direction.

A note for completeness: `llms.txt` was considered and deliberately not built. No vendor has demonstrated a measurable effect, Google has called it purely speculative, and no controlled public test exists, so the expected return does not justify the effort. Note the honest shape of that: it is absence of demonstrated benefit, not proof that nothing consumes it.

**Superseding evidence:** `docs/research/2026-07-19-geo-aeo-generative-search-optimisation.md` in the dotfiles repo. Corrected 2026-07-20 under blog-priv#55 Phase 3.

## Sources

- Google Search Central, crawling myths: https://developers.google.com/crawling/docs/myths-about-crawling
- Google Search Central, crawl budget: https://developers.google.com/crawling/docs/crawl-budget
- Google Search Central, build and submit a sitemap: https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap
- Google Search Central, block indexing with noindex: https://developers.google.com/search/docs/crawling-indexing/block-indexing
- Google Search Central, AI features and your site: https://developers.google.com/search/docs/appearance/ai-features
- OpenAI, bots and crawlers: https://developers.openai.com/api/docs/bots
- Anthropic, does Claude access the web and crawler details: https://support.claude.com/en/articles/8896518
- Perplexity, crawler documentation: https://docs.perplexity.ai/docs/resources/perplexity-crawlers
- Microsoft Bing, Copilot Search grounding on the Bing index: https://blogs.bing.com/search/April-2025/Introducing-Copilot-Search-in-Bing
- Cloudflare, block AI bots: https://developers.cloudflare.com/bots/additional-configurations/block-ai-bots/
- Cloudflare, manage AI crawlers (AI Crawl Control): https://developers.cloudflare.com/ai-crawl-control/features/manage-ai-crawlers/
- Hugo, robots.txt template: https://gohugo.io/templates/robots/
- BuzzStream, do sites that block AI bots still get cited (correlation caveat): https://www.buzzstream.com/blog/news-block-ai-bots-citations/
