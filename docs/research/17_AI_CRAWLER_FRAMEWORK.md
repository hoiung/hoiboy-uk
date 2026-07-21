# 17. AI Crawler Framework (standing policy, all domains)

**Status**: adopted 2026-07-20. Applies to every domain the operator controls, present and future.

This is the reusable procedure. `16_AI_BOT_AND_SEO_POLICY.md` holds the research, the bot taxonomy
and the decision record for hoiboy.uk; read this one when standing up or auditing a domain.

## The policy, in one line

**Citation crawlers ALLOWED. Named training crawlers BLOCKED. On every domain.**

**Read the word "named". This document used to say "Training crawlers BLOCKED... without
exception", and that was false.** Measured 2026-07-21 against the live `hoiboy.uk/robots.txt` with
CPython's `urllib.robotparser`: the nine tokens the managed block names return `can_fetch=False`,
and **sixteen of sixteen other real training and scraping agents returned `can_fetch=True`** -
`anthropic-ai`, `FacebookBot`, `cohere-ai`, `omgilibot`, `Diffbot`, `AI2Bot`, `Webzio-Extended`,
`ImagesiftBot`, `PanguBot`, `Timpibot`, `YouBot`, `TikTokSpider`, `img2dataset`, `Kangaroo Bot`,
`Scrapy`, `python-requests`.

The managed block is an **allowlist of nine named tokens, not a block on the training class**. Any
agent outside that list is permitted to crawl.

What those sixteen DO get is the `*` group's `Content-Signal: search=yes,ai-train=no,use=reference`,
served with `Allow: /`. That is a stated licence condition covering every crawler, and the served
file's own preamble spells out the terms: *"If a Content-Signal = no, you may not collect content for
the corresponding use."* So the training opt-out IS expressed to them. It is expressed by a signal
rather than by a `Disallow`, and a signal is neither a robots directive nor enforcement.

The honest three-tier summary, which the rest of this document should be read against:

| Tier | Who | Mechanism | Strength |
|---|---|---|---|
| Enforced | 7 of the 9 named, where a WAF rule can match the user-agent | WAF custom rule, `block` | **Hard. A 403 at the edge.** |
| Asked | `Google-Extended`, `Applebot-Extended` (no user-agent exists to match) | `Disallow: /` in robots.txt | Honour-system |
| Signalled | Everyone else, including the sixteen above | `Content-Signal: ai-train=no` on the `*` group | Honour-system, and less widely implemented |

Do not collapse those three tiers back into the word "blocked".

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
   `User-agent: *`. **Honour-system: a request, not enforcement.** Bytespider has been widely
   reported ignoring robots.txt, though this repo has not verified that first-hand; treat it as
   reputation, not measurement.
3. **Granular presets (`ai_training` / `ai_search` / `ai_user`)**: set `ai_training: block`, leave
   the other two `disabled`. Partly enforced today (see below). At Cloudflare's **2026-09-15**
   migration this becomes the native mechanism, **and also reclassifies Googlebot, Applebot and
   BingBot as blocked on any zone set to block Training**. Read "MANDATORY REVISIT BEFORE
   2026-09-15" before relying on this layer.
4. **WAF custom rule**: the only layer that *hard-enforces* a training block before 2026-09-15, and
   it reaches **seven of the nine** tokens. `Google-Extended` and `Applebot-Extended` send no
   user-agent of their own, so no edge rule can match them and robots.txt is their only control.
   Blocks the training user-agents at the edge; leaves the citation user-agents untouched.
   Available on the Free plan. **APPLIED on all three zones on 2026-07-21** and verified by probe;
   rule IDs are in the WAF section below.

### The granular presets are PARTLY enforced, not unenforced

Do not record these as inert. Measured 2026-07-20:

The strongest evidence is a before/after on one zone, not a comparison between two. cuarchitects.co.uk
was measured with `ai_training: disabled` (all six training tokens **200**), then the preset was set
to `block`, and CCBot and Bytespider flipped to **403** while the other four stayed 200. hoiboy.uk,
already at `block`, showed the same two at 403 throughout. Both zones now read identically.

The flip is user-agent-signature specific, which rules out generic bot mitigation: the full
`CCBot/2.0 (https://commoncrawl.org/faq/)` string gets 403, a bare `CCBot` gets 200, and an invented
crawler with the same shape gets 200.

**That same fact is also an evasion surface, and this paragraph used to present only the flattering
half of it.** The measurement authenticates the mechanism, yes. It also means the preset's block was
defeated by deleting one token from a user-agent string, with no other change. A reader finished this
section more confident in the preset than the evidence warrants.

**The WAF rule closes this specific hole**: `http.user_agent contains "CCBot"` matches the bare token
too, so since 2026-07-21 a bare `CCBot` returns **403** where it returned 200 the day before.
Verified live. The general lesson stands though - preset enforcement keys on a signature, so treat
any preset-only block as defeatable by a crawler that wants to defeat it.

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
and it follows from a setting applied in this workstream.

The opt-out sentence must be quoted WHOLE, because its second half is what makes the opt-out safe
and an earlier version of this document cut it off exactly there:

> *"if a website owner wants to opt out of these new default configurations, they can easily mark
> this in their Security settings any time leading up to September 15, **which will confirm that they
> want no changes on Training crawlers that also crawl for Search purposes**."*

Truncating at "September 15" turned a targeted carve-out into a bare deadline and made the decision
below look like a straight trade of training protection against search visibility. It is not: opting
out preserves the multi-purpose crawlers (Googlebot, Applebot, BingBot) specifically. This is the
same undisclosed-elision defect already corrected once in this file for the Apple quote; do not
reintroduce it.

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
Training and Agent will be blocked by default on the pages that display ads, while Search will remain
allowed by default"*) applies only to newly
onboarding domains and does **not** narrow this hazard. Do not let the word "ads" suggest these sites
are safe because they carry none.

An earlier version of this document said to set the preset everywhere so the migration would activate
"with no revisit". That was unsupported and actively hazardous: followed literally on a portfolio blog
and a client practice whose whole purpose is being found, it would take out organic search on both.

**The trade-off, and why applying the WAF rule changed it.** Keeping `ai_training: block` used to be
the only thing buying real edge blocking of CCBot and Bytespider, which made opting out a genuine
sacrifice. **That is no longer true.** Since 2026-07-21 the WAF custom rule blocks those two, and
five more, on all three zones, independently of the preset.

So the WAF rule and the migration decision are **coupled, and this document previously presented
them as independent.** The practical consequence:

- **With the WAF rule applied (the current state): opting out costs nothing in enforcement.** The
  seven hard-blocked tokens stay hard-blocked, because the WAF rule does that work, not the preset.
- **Without it, opting out would drop edge enforcement to zero** and leave the entire training
  position resting on robots.txt, which is a request.

Search visibility outranks training protection for these domains, and the opt-out is specifically
scoped to preserve crawlers that also serve Search. So **the recommendation is to OPT OUT**, and it
is now a cheap decision rather than a painful one. Verify the WAF rules are still present first: if
they have been removed, the calculation reverts.

`scripts/check_ai_training_deadline.py` fails CI from 2026-09-01 so this cannot be forgotten. It is
not advice in a document; it is a gate. The line below is that gate's input: flip it to
`resolved (<date>, <what was done>)` once the call is made and the zones are set accordingly.

ai-training-migration-decision: pending

## The WAF custom rule (APPLIED on all three zones, 2026-07-21)

**Status: done and probe-verified.**

| Zone | Rule ID | Verified |
|---|---|---|
| hoiboy.uk | `88eed3b5dce1471e99025336d0a71dac` | 7/7 training UAs 403, citation 6/6 200, probe exit 0 |
| cuarchitects.co.uk | `de90c6505a1e440ba40870fda4ce2abb` | training 403, citation 6/6 200, probe exit 0 |
| speak2lola.com | `12c8a4d6bc624dd5ab189eccf7ce3d6f` | stored only; no DNS, so unverifiable by probe |

**The permission. This section named the wrong one and cost a round-trip.** It said
**Zone > Firewall Services > Edit**. That is wrong: `Firewall Services Write` grants the *legacy*
Filters and Firewall Rules API, NOT the Rulesets API that WAF custom rules live in. Adding it changed
nothing, because
`GET /zones/{id}/rulesets/phases/http_request_firewall_custom/entrypoint` kept returning
`request is not authorized` while `firewall/rules` and `filters` started returning `OK` - which is
how the mis-scope was diagnosed. What actually works is **`Account WAF Write`** (used here) or
**Zone > WAF > Edit**. Treat a documented permission name as an executable instruction: an operator
will act on it.

**Do not reach for the legacy API just because a token already grants it.** Writes there still
succeed - a probe filter was created and deleted to confirm - but Cloudflare states the Firewall
Rules API and Filters API *"are no longer supported since 2025-06-15"*. A rule that stores cleanly
while never being evaluated at the edge is this document's own failure mode wearing a different hat.

**A token cannot widen or revoke itself**, so this step always needs a human. Measured:
`GET /user/tokens` returns *"Valid user-level authentication not found"* and
`GET /accounts/{id}/tokens` returns *"Unauthorized to access requested resource"*. Granting
`User > API Tokens > Edit` would remove that limit and is root-equivalent - anything holding it can
mint itself any permission on the account. It was offered during this work and declined.

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
WAF rule can never cover them.** Both are robots.txt *control tokens* rather than crawlers that fetch
under their own name, so `http.user_agent contains` has nothing to match and a rule listing them
would look correct while enforcing nothing.

The two are sourced differently and should not be stated with equal confidence. **Google says it
outright**; the Apple half is our inference from what Apple describes, not an Apple statement:

- Google: *"Google-Extended doesn't have a separate HTTP request user agent string"* - explicit.
- Apple calls Applebot-Extended *"a secondary user agent"* and says it *"does not crawl webpages"*,
  which leaves nothing to match at the edge, but Apple never makes Google's explicit no-UA-string
  claim. **Verified operationally instead**: with the WAF rule live, `Applebot-Extended` is served
  **200** while every token the rule can match returns 403. That is the measurement the conclusion
  actually rests on.

> Google: *"Google-Extended doesn't have a separate HTTP request user agent string. Crawling is done
> with existing Google user agent strings; the robots.txt user-agent token is used in a control
> capacity."*
>
> Apple: *"Applebot-Extended does not crawl webpages. Webpages that disallow Applebot-Extended can
> still be included in search results. Applebot-Extended is only used to determine how to use the
> data crawled by the Applebot user agent."*

Apple's middle sentence is worth keeping rather than eliding: it confirms that opting out of
Applebot-Extended does not remove a page from search results, which is the same shape as the argument for
this whole policy.

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
2. Set, only where the read shows it is wrong (**read "MANDATORY REVISIT BEFORE 2026-09-15" first**;
   `ai_training: block` arms a dated hazard, and the CI gate that catches it lives in THIS repo only,
   so a domain in another repo inherits no reminder):
   - `ai_bots_protection: disabled`
   - `is_robots_txt_managed: true`
   - `ai_training: block`, `ai_search: disabled`, `ai_user: disabled`
3. Add the WAF custom rule blocking the training user-agents (see layer 4).
4. Verify by probe, not by read-back:
   `bash scripts/check-ai-crawler-access.sh https://<domain>/`
   Exit 0 means no citation crawler was status-blocked AND no training token was proven to lack
   an opt-out (a CONFLICT is reported, not failed; an unfetchable robots.txt skips the training
   half entirely, so read the PASS line rather than inferring from the code). It does NOT mean
   the citation crawlers were served real
   content: the script classifies on HTTP status, so a challenge page returning 200 reads as ok.
   The TRAINING rows report the robots.txt directive each training crawler is given.
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
  the user-agent, the matching groups' rules MUST be combined into one group and parsed according to
  Section 2.2.2."*
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
  §2.2.2 specificity at all: it is first-matching-group-wins. **Version-bound, and it will go stale:**
  measured on CPython **3.12.3**. CPython added RFC 9309 support in `bc285e583286` (2026-05-04) and
  backported it, so this ordering behaviour changes on newer interpreters. **No version floor is
  quoted here on purpose:** an earlier draft named a single release, which would read as clearance
  to trust the table on any interpreter below it, including maintenance branches that already
  carry the backport. Treat ANY interpreter other than the measured 3.12.3 as unverified. The live outcome stays "blocked"; only the reason
  does. Re-measure before citing this table on a newer interpreter. Measured, same file, order flipped:

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
- **Nothing will tell you when that drift gets worse, and that is a deliberate gap.** A CONFLICT
  token is counted out of the opt-out total but never fails the gate, so the count on
  cuarchitects.co.uk could rise from four to nine and the weekly job would still exit 0 and stay
  green. The only signal is the count in a PASS line inside a job nobody opens when it is green.
  Failing on it was considered and rejected: the live outcome is blocked, and a standing red on a
  client zone the operator cannot unilaterally fix is the alarm-fatigue trap this workflow already
  avoids by excluding speak2lola.com. But by this document's own standard, that a gate which never
  asks about a token cannot fail on it, a gate that asks and never fails is only half a gate. **If
  the CONFLICT count on a zone changes, that is a human noticing, not the gate telling you.** Re-read
  the count when this document is next reviewed rather than assuming four is still four.

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
`layouts/robots.txt` reached the right ANSWER (blocked) before either version of this file did,
though by the specificity-only route this section warns against: it says *"the records merge and the
most specific rule wins"*, which is the argument corrected above. Right conclusion, incomplete
reasoning. Kept because the first version was briefly the basis
for calling the client site's policy defeated, which it never was.

Always fetch the live `https://<domain>/robots.txt` before reasoning about what a crawler sees. The
repo file is not the served file.

### Edge changes propagate unevenly

The first probe after a change showed 2 of 6 citation crawlers flipped and the rest still 403. That
was mid-rollout, not a failure. Poll until it settles; never conclude from a single reading. Doc 16
records the value moving between two probes on the same day.

## Verification

`scripts/check-ai-crawler-access.sh [URL]` takes any domain, so one script covers the estate.
Tri-state exit: `0` citation reachable and no training token PROVEN to lack an opt-out (a CONFLICT
token is reported and not failed; an unfetchable robots.txt skips the training gate, so read the PASS
line for the actual count rather than inferring nine-of-nine from a zero exit), `1` a policy failure
of EITHER kind (citation blocked, or a training token with no opt-out; they need opposite fixes, so
read the output), `2` inconclusive (DNS failure, 5xx,
429). The tri-state matters: speak2lola.com has no DNS and returns 2, where a binary pass/fail would
have reported "6 of 6 blocked" and sent someone hunting a crawler policy on a domain with no site.

`.github/workflows/ai-crawler-access.yml` runs it weekly as a matrix over both reachable zones
(hoiboy.uk and cuarchitects.co.uk; speak2lola.com is excluded while it has no DNS, because it could
only ever return the inconclusive exit 2 and a permanent warning trains the reader to ignore the
job). Non-blocking, because an
edge setting can regress with no repo change and nothing in the repo would show it.

## Zone inventory (2026-07-20)

Zone settings read back from the API on 2026-07-21 (`GET /zones/{id}/bot_management`), so every row
below is measured rather than asserted. An earlier version of this table claimed "all three zones"
for `ai_training` while carrying no evidence at all for speak2lola.com; that gap is now closed by
reading it.

| Domain | `ai_bots_protection` | `is_robots_txt_managed` | `ai_training` | Citation | Training probed | WAF rule |
|---|---|---|---|---|---|---|
| hoiboy.uk | disabled | true | block | PASS 6/6 | **9 of 9** | **applied**, probe-verified |
| cuarchitects.co.uk | disabled | true | block | PASS 6/6 | **9 of 9** | **applied**, probe-verified |
| speak2lola.com | disabled | true | block | no DNS, unverifiable | no DNS | **applied**, stored only |

**The "training probed" column is not decoration, and an earlier version of this table dropped it.**
The row used to read `Disallow: / on all nine (gate re-checks 6 of them)`, which was an honest
disclosure that the probe covered six of the nine named tokens. That caveat was deleted in the same
Stage 5 commit that gave the training class authority to fail CI, replacing a true qualified claim
with an unqualified one at the exact moment the claim started gating a build. Ralph Tier 2 caught it.

The underlying gap is now closed rather than re-worded: `TRAINING_BOTS` in
`scripts/check-ai-crawler-access.sh` covers all nine (Amazonbot, Applebot-Extended and
CloudflareBrowserRenderingCrawler were the three missing), and a test pins the list against the nine
named here so it cannot silently drift again. A gate that never asks about a token cannot fail on
it, so probe coverage is part of the claim, not a footnote to it.

Two caveats that the table cannot carry:

- **cuarchitects.co.uk still reports CONFLICT on four tokens** (its repo file allows what the managed
  block disallows). Drift, not an outage: the live file measures as blocked in every parser tried.
- **speak2lola.com has no DNS**, so its rule is stored and unverifiable. A stored rule is not a
  verified rule. Re-probe it when the domain resolves.

And the estate is wider than this table. **id8u.com is live, serves an allow-all `robots.txt`
(HTTP 200, body `User-agent: *` with an empty `Disallow:`, verified 3/3 on 2026-07-21), and is
not behind Cloudflare**, so it follows none of this. It is out of scope for this issue and named here
so the inventory does not read as complete when it is not.

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
- Cloudflare, "Managed robots.txt": https://developers.cloudflare.com/bots/additional-configurations/managed-robots-txt/
  (the previously cited `ai-crawl-control/features/managed-robots-txt/` path is a stable 404,
  verified 3/3 attempts with no redirect. It went unnoticed because `lychee.toml` excluded
  `docs/research` from the CI link check, so no citation in this corpus was ever verified.)
- Google, "Google crawlers and fetchers" (source for Google-Extended having no user-agent):
  https://developers.google.com/search/docs/crawling-indexing/google-common-crawlers
- Apple, "About Applebot" (source for Applebot-Extended not crawling):
  https://support.apple.com/en-us/119829
- RFC 9309, Robots Exclusion Protocol: https://www.rfc-editor.org/rfc/rfc9309.html
- Content Signals Policy: https://contentsignals.org/
