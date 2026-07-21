# 17. AI Crawler Framework (standing policy, all domains)

**Status**: adopted 2026-07-20. Applies to every domain the operator controls, present and future.

This is the reusable procedure. `16_AI_BOT_AND_SEO_POLICY.md` holds the research, the bot taxonomy
and the decision record for hoiboy.uk; read this one when standing up or auditing a domain.

## The policy, in one line

**Citation crawlers ALLOWED. Training crawlers BLOCKED. On every domain, without exception.**

Operator ruling, verbatim (2026-07-20):

> *"i dont want to give bots free training if i am not cited. i want to block that"*
>
> *"all 3 domains and future should always follow this same framework"*

## Why, and what was ruled out

The earlier position was *"I dont mind training with our site as long as our sites are cited for it."*
It was reversed once it was established that **no vendor offers a cite-for-training contract**.
Training and citation are separate crawler classes with separate user-agents; a training crawl never
emits a citation. So "allow training if cited" has no configuration that expresses it, and the only
thing "allow training" can mean in practice is an unconditional give. The operator declined it.

Ruled out, with reasons, so they are not re-litigated:

| Option | Why not |
|---|---|
| Block everything (`ai_bots_protection: block`) | The coarse legacy switch. Takes the citation class down with the training class. **This was the original defect on hoiboy.uk.** Never re-enable it. |
| Allow everything | The superseded ruling. Gives training away for a citation that is not contractually owed and cannot be measured. |
| Allow training on some domains only | The operator explicitly made this uniform. Not a per-site judgement call. |

**Honesty bound.** Allowing the citation class is necessary, not sufficient. A denial guarantees zero
citation from that engine; removing it guarantees nothing in return. No reliable method for measuring
AI citation currently exists. Success here is "the citation crawlers are not blocked", never "we are
cited".

## The four layers, and what each one actually does

Order matters: they are listed weakest-to-strongest in enforcement terms.

1. **`ai_bots_protection`**: coarse on/off. Must be `disabled`. Setting it to `block` is the thing
   that broke hoiboy.uk: it blocks the citation class too.
2. **Managed robots.txt (`is_robots_txt_managed: true`)**: the mechanism that *expresses* the
   training block. Serves a `Content-Signal: search=yes,ai-train=no,use=reference` line plus
   `Disallow: /` for nine training crawlers, and leaves the citation class to fall under
   `User-agent: *`. **Honour-system: a request, not enforcement.** Bytespider in particular has been
   reported ignoring robots.txt.
3. **Granular presets (`ai_training` / `ai_search` / `ai_user`)**: set `ai_training: block`, leave
   the other two `disabled`. Partly enforced today (see below). At Cloudflare's **2026-09-15**
   migration this becomes the native mechanism, **and also reclassifies Googlebot, Applebot and
   BingBot as blocked on any zone set to block Training**. Read "MANDATORY REVISIT BEFORE
   2026-09-15" before relying on this layer.
4. **WAF custom rule**: the only layer that *hard-enforces* a training block before 2026-09-15, and
   it reaches **seven of the nine** tokens. `Google-Extended` and `Applebot-Extended` send no
   user-agent of their own, so no edge rule can match them and robots.txt is their only control.
   Blocks the training user-agents at the edge; leaves the citation user-agents untouched.
   Available on the Free plan. **Not applied on any zone yet.**

### The granular presets are PARTLY enforced, not unenforced

Do not record these as inert. Measured 2026-07-20:

The strongest evidence is a before/after on one zone, not a comparison between two. cuarchitects.co.uk
was measured with `ai_training: disabled` (all six training tokens **200**), then the preset was set
to `block`, and CCBot and Bytespider flipped to **403** while the other four stayed 200. hoiboy.uk,
already at `block`, showed the same two at 403 throughout. Both zones now read identically.

The flip is user-agent-signature specific, which rules out generic bot mitigation: the full
`CCBot/2.0 (https://commoncrawl.org/faq/)` string gets 403, a bare `CCBot` gets 200, and an invented
crawler with the same shape gets 200.

So the preset does real work now, on a subset of crawlers. An earlier note in this workstream said
"accepted by the API but not enforced"; that was over-generalised from probing GPTBot alone.

## MANDATORY REVISIT BEFORE 2026-09-15

**`ai_training: block` will block Googlebot, Applebot and BingBot on 2026-09-15 unless the zone opts
out first.** This is not a hypothetical. Cloudflare's announcement, verbatim:

> *"Since the defaults will be enforced by the most restrictive applicable rules, multi-purpose
> crawlers such as Googlebot, Applebot, and BingBot will be blocked by customers who have selected to
> block Training (either through the new options to manage AI traffic, or through the legacy Block AI
> bots service)."*

**These zones have selected to block Training, so they are in scope.** That is the whole exposure,
and it follows from a setting applied in this workstream. Opt-out can be marked in Security settings
*"any time leading up to September 15"*.

Two things this section previously got wrong, corrected rather than deleted because the wrong version
was quoted into a GitHub comment:

- It attributed to Cloudflare the sentence *"apply to new Cloudflare customers, new sites set up by
  existing customers, and all existing free customers"*, and rested the whole "both zones are in
  scope" conclusion on it. **That sentence is not in Cloudflare's post.** It came from a
  search-result summary and was presented as a verbatim quote. Retracted.
- It therefore gave Free plan as the reason these zones are affected. Wrong reason, right conclusion:
  they are affected because they have selected to block Training, which is what the announcement
  actually conditions on.

The separate ads-page default (*"For all new domains onboarding to Cloudflare, the categories of
Training and Agent will be blocked by default on the pages that display ads"*) applies only to newly
onboarding domains and does **not** narrow this hazard. Do not let the word "ads" suggest these sites
are safe because they carry none.

An earlier version of this document said to set the preset everywhere so the migration would activate
"with no revisit". That was unsupported and actively hazardous: followed literally on a portfolio blog
and a client practice whose whole purpose is being found, it would take out organic search on both.

**The trade-off, stated so it gets decided rather than drifted into.** Keeping `ai_training: block`
today buys real blocking of CCBot and Bytespider, and Bytespider is the crawler most often reported
ignoring robots.txt, so it is not nothing. The cost is that the same switch is what Cloudflare reads
on 2026-09-15 to decide whether Googlebot counts as a training crawler. Search visibility outranks
training protection for these domains, so **if the migration arrives undecided, opt out**.

`scripts/check_ai_training_deadline.py` fails CI from 2026-09-01 so this cannot be forgotten. It is
not advice in a document; it is a gate. The line below is that gate's input: flip it to
`resolved (<date>, <what was done>)` once the call is made and the zones are set accordingly.

ai-training-migration-decision: pending

## The WAF custom rule (NOT YET APPLIED on any zone)

**Status: blocked, not done.** The API token available to this workstream carries Bot Management
Write only; `GET /zones/{id}/rulesets/phases/http_request_firewall_custom/entrypoint` returns
`request is not authorized`. Applying it needs **Zone > Firewall Services > Edit**, or the dashboard.
Until it exists, the training block is robots.txt only, which is honour-system.

Action `block`, phase `http_request_firewall_custom`:

```
(http.user_agent contains "GPTBot")
or (http.user_agent contains "ClaudeBot")
or (http.user_agent contains "CCBot")
or (http.user_agent contains "meta-externalagent")
or (http.user_agent contains "Bytespider")
or (http.user_agent contains "Amazonbot")
or (http.user_agent contains "CloudflareBrowserRenderingCrawler")
```

**Seven clauses, not nine. `Google-Extended` and `Applebot-Extended` are deliberately absent, and a
WAF rule can never cover them.** Both are robots.txt *control tokens*, not crawlers: they have no
user-agent string, so `http.user_agent contains` can never match and a rule listing them would look
correct while enforcing nothing.

> Google: *"Google-Extended doesn't have a separate HTTP request user agent string. Crawling is done
> with existing Google user agent strings; the robots.txt user-agent token is used in a control
> capacity."*
>
> Apple: *"Applebot-Extended does not crawl webpages. Instead, Applebot-Extended is only used to
> determine how to use the data crawled by the Applebot user agent."*

The only user-agents that WOULD match are `Googlebot` and `Applebot`, which are the search crawlers
you must never block. **So for Google and Apple, robots.txt is the only available training control,
full stop.** This is a real limit on the claim that the WAF layer "hard-enforces": it hard-enforces
seven of nine, and the two it cannot reach are the two whose opt-out is honour-system by design.

**The substring trap for the seven that do work.** Cloudflare's `contains` is a substring match, so a
carelessly shortened token blocks a crawler you want. `ClaudeBot` is safe as written: the citation
tokens are `Claude-SearchBot` and `Claude-User`, and neither contains the substring `ClaudeBot`.
Verified literally, not assumed. Never shorten a token toward a vendor name.

After applying, verify with the probe rather than the dashboard, and confirm the CITATION rows are
still 200. A rule that takes citation down with training is the original defect in a new place.

## Standing up a new domain

1. Read the zone's current `bot_management` config **before writing anything**.
   `GET /zones/{id}/bot_management`. Partial `PUT`s merge, and a read-back is not proof of
   enforcement.
2. Set, only where the read shows it is wrong:
   - `ai_bots_protection: disabled`
   - `is_robots_txt_managed: true`
   - `ai_training: block`, `ai_search: disabled`, `ai_user: disabled`
3. Add the WAF custom rule blocking the training user-agents (see layer 4).
4. Verify by probe, not by read-back:
   `bash scripts/check-ai-crawler-access.sh https://<domain>/`
   Exit 0 means every citation crawler is reachable. The TRAINING rows report the robots.txt
   directive each training crawler is given.
5. If the origin repo serves its own robots.txt, check it does not contradict the managed block
   (see below).

**Change one variable at a time.** Reading first collapsed a four-setting guess into one measured
cause on hoiboy.uk, and revealed that two of the three zones were already partly correct. Flipping
everything blind would have left no way to attribute the fix.

## Two traps that have already bitten

### Cloudflare PREPENDS the managed robots.txt; it does not replace

The managed block is served *ahead of* the origin's file, so both records are served. A repo edit
cannot remove the managed one. Consequences:

- A repo-served `robots.txt` that allows a bot the managed block disallows produces **two
  contradictory groups for one token**. RFC 9309 §2.2.1: *"If there is more than one group matching
  the user-agent, the matching groups' rules MUST be combined into one group."*
- cuarchitects.co.uk serves exactly this for GPTBot, ClaudeBot, Google-Extended and CCBot: its repo
  file allows them with an empty `Disallow:` (written before managed robots.txt was on) while the
  managed block disallows them.
- **An empty `Disallow:` means allow, in practice, but the RFC and real parsers disagree about why.**
  Real parsers treat it as the traditional allow-everything special case: CPython's
  `urllib.robotparser` says so in its own source, *"an empty value means allow all"*, and this repo's
  parser scores it the same way. **RFC 9309 has no such special case**: its ABNF puts
  `empty-pattern = *WS` under `("allow" / "disallow")`, so read strictly it is a zero-octet
  *disallow*. Both readings reach "blocked" here, for different reasons, which is why the outcome is
  stable but the reasoning must not be stated as if the two agree.
- **The block still applies on the live file, but for a narrower reason than a specificity argument.**
  Under a strict RFC reading §2.2.2 gives it to `Disallow: /` (*"the most specific match... the match
  that has the most octets"*, one octet against the empty pattern's zero, and the allow-beats-disallow
  tie-break needs *equivalent* rules). But `urllib.robotparser` does not implement §2.2.1 merging or
  §2.2.2 specificity at all: it is first-matching-group-wins. Measured, same file, order flipped:

  | group order | `can_fetch('/')` for GPTBot |
  |---|---|
  | Cloudflare block first (the live layout) | `False` |
  | site block first (reversed) | `True` |

  **So the live outcome is blocked partly because Cloudflare prepends.** Do not restate this as
  "specificity guarantees it"; a widely-used parser gets there by ordering, and would flip if the
  ordering did.
- `scripts/check-ai-crawler-access.sh` reports `CONFLICT` on the affected rows. Treat it as **drift
  worth fixing**: not an outage today, but the effective stance depends on parser behaviour that
  varies between implementations and on a serving order the origin does not control.

**This paragraph has now been wrong twice, in opposite directions. Do not restate it from memory.**

Version 1 said "permissive parsers resolve the tie toward allow, so the training block silently stops
applying" and concluded the client site's policy was defeated. False: the live file measures as
blocked in every parser tried.

Version 2 over-corrected. It said there was no allow/disallow tie "because both records are
`disallow`", and cited `urllib.robotparser` as confirmation of a specificity argument. Both halves
were wrong: an empty `Disallow:` is an allow (CPython says so in its own source, and this repo's awk
parser already scored it that way, so the document contradicted its own implementation), and urllib
demonstrates ordering rather than specificity.

What is actually true: it is a real conflict, the live outcome is blocked, and that outcome rests on
a mix of strict-RFC specificity and the fact that Cloudflare prepends. cuarchitects' own
`layouts/robots.txt` had the right reading before either version of this file did. Kept because the
first version was briefly the basis
for calling the client site's policy defeated, which it never was.

Always fetch the live `https://<domain>/robots.txt` before reasoning about what a crawler sees. The
repo file is not the served file.

### Edge changes propagate unevenly

The first probe after a change showed 2 of 6 citation crawlers flipped and the rest still 403. That
was mid-rollout, not a failure. Poll until it settles; never conclude from a single reading. Doc 16
records the value moving between two probes on the same day.

## Verification

`scripts/check-ai-crawler-access.sh [URL]` takes any domain, so one script covers the estate.
Tri-state exit: `0` citation reachable, `1` citation blocked, `2` inconclusive (DNS failure, 5xx,
429). The tri-state matters: speak2lola.com has no DNS and returns 2, where a binary pass/fail would
have reported "6 of 6 blocked" and sent someone hunting a crawler policy on a domain with no site.

`.github/workflows/ai-crawler-access.yml` runs it weekly against hoiboy.uk, non-blocking, because an
edge setting can regress with no repo change and nothing in the repo would show it.

## Zone inventory (2026-07-20)

| Domain | Citation | Training (robots.txt) | WAF rule |
|---|---|---|---|
| hoiboy.uk | PASS 6/6 | `Disallow: /` on all nine (gate re-checks 6 of them) | **not applied** |
| cuarchitects.co.uk | PASS 6/6 | **CONFLICT on 4 tokens** (drift; live stance still blocked) | **not applied** |
| speak2lola.com | no DNS, unverifiable | configured | **not applied** |

No zone has the WAF rule. Every "training blocked" above means robots.txt only.

**Zone and account IDs are deliberately not recorded here.** This repository is public. The IDs are
not credentials, but publishing the account's zone inventory is free reconnaissance for no benefit.
Read them from the Cloudflare dashboard or `GET /zones`. Target zones **by ID** when scripting;
never iterate "all zones".

Both live zones are **Free plan**: `sbfm_*` fields are Pro+ and will reject. That is a plan limit,
not a token-scope problem. Plan tier is NOT why the 2026-09-15 change reaches these zones; that
follows from having selected to block Training. See the retraction above and do not reintroduce
a Free-plan rationale here.

## Sources

- Cloudflare blog, "Your site, your rules: new AI traffic options for all customers" (the source for
  the 2026-09-15 date and the multi-purpose-crawler reclassification):
  https://blog.cloudflare.com/content-independence-day-ai-options/
- Cloudflare, "Block AI bots": https://developers.cloudflare.com/bots/additional-configurations/block-ai-bots/
- Cloudflare, "Manage AI crawlers": https://developers.cloudflare.com/ai-crawl-control/features/manage-ai-crawlers/
- Cloudflare, "Managed robots.txt": https://developers.cloudflare.com/ai-crawl-control/features/managed-robots-txt/
- RFC 9309, Robots Exclusion Protocol: https://www.rfc-editor.org/rfc/rfc9309.html
- Content Signals Policy: https://contentsignals.org/
