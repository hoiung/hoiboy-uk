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

## Cloudflare operator checklist (network-level enforcement)

robots.txt is advisory; Cloudflare is the only layer that hard-enforces at the network edge. Because the dashboard state cannot be read from this repo, the owner should confirm these four settings once in the Cloudflare dashboard for the hoiboy.uk zone:

1. **Block AI bots**: confirm this managed toggle is OFF (if ON, it blocks AI crawlers at the edge regardless of robots.txt). https://developers.cloudflare.com/bots/additional-configurations/block-ai-bots/
2. **AI Crawl Control**: confirm the AI crawlers are set to Allow (this feature offers per-crawler Allow or Block on all plans, including Free). https://developers.cloudflare.com/ai-crawl-control/features/manage-ai-crawlers/
3. **managed-robots.txt**: confirm Cloudflare's managed-robots.txt feature is OFF, so it does not inject its own block rules over the repo-served file.
4. **Bot Fight Mode**: confirm Bot Fight Mode (or Super Bot Fight Mode) is either off or configured to skip verified bots, so legitimate search and citation crawlers are not challenged.

Then verify the served file directly from a terminal:

```
curl https://hoiboy.uk/robots.txt
curl -A "GPTBot" https://hoiboy.uk/robots.txt
```

Both should return the allow-all file with the Sitemap line, and the second confirms Cloudflare is not serving a different (blocked) file to an AI user-agent. Note: the "Content Independence Day" AI-block default that Cloudflare announced in 2025 applied only to newly-onboarded domains as a prompted choice at sign-up; pre-existing zones were not auto-flipped, so for an established zone the risk is low, but the one-time check is still worth doing.

## Deferred variant: block training only (NOT built now)

If the owner later wants to protect content from model training while keeping every citation path open, the policy below is the "best of both" alternative. It is **deferred and not built now** because there is no current need (the goal is exposure, not protection) and it carries zero citation benefit either way. Trigger to revisit: **if the owner later wants to protect content from model training.**

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

**Unsourced.** Visible author and credential signals, and freshness. Both were asserted here with no source, and the superseding brief does not address either one, so both remain unsourced on this record. The brief's silence on a tactic is not a positive finding about it in either direction.

A note for completeness: `llms.txt` was considered and deliberately not built, because no major AI vendor honors it as of 2026, so it would be effort with no consumer.

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
