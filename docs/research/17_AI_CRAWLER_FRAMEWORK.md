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
   the other two `disabled`. Partly enforced today (see below) and scheduled to become the native
   mechanism at Cloudflare's **2026-09-15** migration, at which point this layer does the whole job.
4. **WAF custom rule**: the only layer that *hard-enforces* a training block before 2026-09-15.
   Blocks the training user-agents at the edge; leaves the citation user-agents untouched.
   Available on the Free plan.

### The granular presets are PARTLY enforced, not unenforced

Do not record these as inert. Measured 2026-07-20:

- hoiboy.uk with `ai_training: block` → CCBot **403**, Bytespider **403**, other four training
  tokens 200
- cuarchitects.co.uk with `ai_training: disabled` → all six training tokens **200**

So the preset does real work now, on a subset of crawlers. An earlier note in this workstream said
"accepted by the API but not enforced"; that was over-generalised from probing GPTBot alone. Set it
on every zone regardless, so the September migration activates the full framework with no revisit.

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
  contradictory groups for one token**. RFC 9309 merges duplicate groups, and permissive parsers
  resolve an allow/disallow tie toward **allow**, so the training block silently stops applying.
- cuarchitects.co.uk was serving exactly this for GPTBot, ClaudeBot, Google-Extended and CCBot: its
  repo file explicitly allowed them (written before managed robots.txt was on) while the managed
  block disallowed them.
- `scripts/check-ai-crawler-access.sh` now detects this and reports `CONFLICT` on the affected rows.
  Run it against any domain whose repo serves its own robots.txt.

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

| Domain | Zone ID | State |
|---|---|---|
| hoiboy.uk | `8f3025b71cd0661773746a18a3be2495` | citation PASS 6/6, training `Disallow: /` |
| cuarchitects.co.uk | `f2526587d4edffaeaeb1a0d47f1c2b71` | citation PASS 6/6, **robots.txt CONFLICT on 4 tokens** |
| speak2lola.com | `ff7099adcd722ed0b39580768678c847` | configured; no DNS, unverifiable until a site exists |

Account `9bb03980d84fd2fdea6dea8b3ea2e1dd`. Target zones **by ID**; never iterate "all zones".

Both live zones are **Free plan**: `sbfm_*` fields are Pro+ and will reject. That is a plan limit,
not a token-scope problem.

## Sources

- Cloudflare, "Block AI bots": https://developers.cloudflare.com/bots/additional-configurations/block-ai-bots/
- Cloudflare, "Manage AI crawlers": https://developers.cloudflare.com/ai-crawl-control/features/manage-ai-crawlers/
- Cloudflare, "Managed robots.txt": https://developers.cloudflare.com/ai-crawl-control/features/managed-robots-txt/
- RFC 9309, Robots Exclusion Protocol: https://www.rfc-editor.org/rfc/rfc9309.html
- Content Signals Policy: https://contentsignals.org/
