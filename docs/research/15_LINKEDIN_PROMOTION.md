# 15 — LinkedIn Promotion Posts (Click-Driving Format)

**Last updated**: 2026-04-25
**Applies to**: every LinkedIn post written to drive readers from the LinkedIn feed to a hoiboy.uk blog post.
**Does NOT apply to**: LinkedIn posts written for native engagement only (no external link), thought-leadership essays kept entirely on-platform, or comments.

## TL;DR

| Metric | Target | Hard ceiling |
|---|---|---|
| Word count | 50-90 (sweet spot ~70) | 100 |
| Character count | 350-600 | 700 |
| Hook (line 1) | Under 140 characters | 210 (desktop "see more" cutoff) |
| Hashtags | 3-5 at the end | 5 |
| Links in body | ONE only (the blog URL) | 1 |

A click-driving LinkedIn post is a **tease**, not a mini-blog. If the reader can get the answer from the post, they will not click. The post's job is to land a hook above the "see more" cutoff and open a curiosity loop the blog post closes.

## Why this exists

Drafts kept landing at 150-200+ words because the writing model defaults to "summarise the blog." User feedback 2026-04-25 on the overthink-mode promotion draft: too long, want them to click the link to read more. Research dispatched same day; this doc captures the findings and locks the format.

## The four-line skeleton

```
Line 1 (HOOK, <140 chars, 5-10 words ideal):
  Contrarian claim or specific number that opens a loop.

Line 2 (STAKE, ~1 short sentence):
  Why this matters. The cost of not knowing.

Line 3 (CURIOSITY GAP, ~1 sentence):
  Name the thing you discovered WITHOUT explaining it.

Line 4 (LINK + 1-line CTA):
  "Full breakdown: <https://hoiboy.uk/posts/...>"

Hashtags on the final line: #Tag1 #Tag2 #Tag3 (3-5).
```

Total post: 50-90 words, 350-600 characters.

## What the research found

### LinkedIn truncation cutoff (2026)

- **Mobile**: ~140 characters before "...see more"
- **Desktop**: ~210 characters before "...see more"
- The hook MUST land its curiosity payload inside 140 chars or the reader never sees line 2.

Sources: AuthoredUp 2026, Sendible 2026, Lettercounter 2026.

### Optimal length for click-driving posts

- Botdog 2025: when the post includes an external link, **cap copy ~150 chars** is on the aggressive end; up to ~600 chars works if the hook is tight.
- Postiv AI 2025-2026 (2M-post study): single-sentence hook above the fold, then 2-3 short paragraphs only.
- ConnectSafely 2026 (1,000-post study): **5-10 word hooks** beat longer openings by **40% on "see more" click-through**; curiosity-gap and contrarian hooks lift engagement 2.3x.
- Recurpost / Sprout Social 2026: short formatted posts hold dwell time; "wall of text" loses ~40% dwell.
- 170+ words is "mini-blog-post" territory and over-summarises, which kills the click-through.

### External-link reach (caveat-heavy)

- Multiple 2025-2026 third-party trackers (Botdog, Hashmeta, Pursue Networking) report **25-60% reach reduction** on link posts.
- LinkedIn Senior Director of Product (Aug 2025) **denied an algorithmic penalty**: "no penalty if the post leads with value."
- The "link in first comment" workaround is **also penalised** as of Feb 2026 (Dataslayer analysis).
- **Practical rule**: keep the link in the post body, lead with value in the hook, accept the reach trade-off.

### Hashtag count

- 3-5 hashtags, placed at the bottom.
- Mix of 1-2 broad + 2-3 niche.
- First-comment placement is dead in 2025-2026.

Sources: closelyhq 10K-post study 2025, Hootsuite 2025, ConnectSafely 2026, Wingender Late 2025.

### Curiosity-gap copywriting

- Enchanting Marketing curiosity gap.
- Ship30for30 open loops.
- Tease the discovery, do NOT name the answer in the post body.

## Voice rules still apply

The short format does NOT relax the voice rules. Still:

- Zero em dashes (U+2014).
- Zero banned words (canonical: `dotfiles/SST3/scripts/voice_rules.py`).
- Lumpy fragment rhythm.
- British spelling.
- Concrete numbers, not vague adjectives.
- Plain English (no acronyms without inline expansion on first use, e.g. `KISS (Keep It Simple Stupid)`).
- LinkedIn = professional channel: strip personal/NSFW/juvenile details even if the source blog has them.

## Worked example: too long (170 words) vs target (~70 words)

**Too long** (overthink-mode draft 1, 2026-04-25):

> Claude has an effort setting that, cranked to max, burns five times the tokens for a one-line change. Every new release resets it on me. Every release I turn it back down.
>
> The pitch is simple. Crank effort up, model thinks harder, you get better answers. Reality is different. Max effort second-guesses your instructions, comes back with a three-file refactor when you asked for one line, and a paragraph explaining why your original request wasn't quite right.
>
> Low effort isn't the answer either. The model stops checking itself, misreads the file, ships code that compiles but doesn't do the thing. Different failure mode, same net result.
>
> The middle is where the work gets done. Used to be middle of three (medium). Now middle of five (high). Across every Claude release, across ChatGPT's reasoning knob when OpenAI added one, same answer. Different names, different tier counts. Same dial underneath.
>
> Nine or ten months of experiments. Release-day reset ritual. Why max effort overrides the harness's no-overengineering rule. And why KISS still applies, because humans overthink the same way.
>
> https://hoiboy.uk/posts/overthink-mode/
>
> #ClaudeCode #AIEngineering #LLMs

That answers the question. Reader has no reason to click.

**Target** (overthink-mode draft 2, ~70 words, ~440 chars):

> Claude's max effort setting burns 5x the tokens to deliver a one-line change.
>
> Every new release resets it on me. Every release I turn it back down.
>
> Nine months of experiments across Claude and ChatGPT. Same dial. Same answer. The label changes. The setting doesn't.
>
> Where the dial actually wins: https://hoiboy.uk/posts/overthink-mode/
>
> #ClaudeCode #AIEngineering #LLMs

Hook lands in 78 chars (well under the 140-char mobile cutoff). Curiosity gap: "the setting doesn't" (which one?). Link closes the loop.

## Caveats (what this does NOT prove)

- No randomised controlled trial; all evidence is observational on aggregated LinkedIn posts.
- Click-rate-vs-length specifically (not engagement-vs-length) has thinner data than dwell-time studies.
- LinkedIn officially contradicts the link-penalty claim. The 25-60% figures are third-party-measured, not LinkedIn-disclosed.
- The 5-10 word hook claim is one study (ConnectSafely, 1,000 posts). Directional, not gospel.

## Sources

Top three:

1. ConnectSafely 2026, "LinkedIn Hooks 2026" (1,000-post analysis): <https://connectsafely.ai/articles/linkedin-hooks-engagement-guide-2026>
2. Postiv AI 2025-2026, 2M-post LinkedIn content study: <https://postiv.ai/blog/linkedin-content-strategy-2025>
3. Botdog 2025, "LinkedIn Algorithm 2025" (link-penalty + 150-char rule): <https://www.botdog.co/blog-posts/linkedin-algorithm-2025>

Supporting:

- AuthoredUp 2026 character-limit guide: <https://authoredup.com/blog/linkedin-character-limit>
- AuthoredUp 2026 algorithm guide: <https://authoredup.com/blog/linkedin-algorithm>
- Sendible 2026 LinkedIn post size: <https://www.sendible.com/insights/linkedin-post-size>
- Sprout Social 2026 algorithm: <https://sproutsocial.com/insights/linkedin-algorithm/>
- Dataslayer Feb 2026 algorithm update: <https://www.dataslayer.ai/blog/linkedin-algorithm-february-2026-whats-working-now>
- closelyhq 10K-post hashtag study 2025: <https://blog.closelyhq.com/linkedin-hashtag-strategy-data-from-10000-posts-analysis/>
- Enchanting Marketing curiosity gap: <https://www.enchantingmarketing.com/curiosity-gap/>
- Ship30for30 open loops: <https://www.ship30for30.com/post/85-open-loop-methods-to-hook-your-reader-and-keep-their-attention>
- Matt Navarra / LinkedIn Sr Director "no link penalty" rebuttal Aug 2025: <https://www.threads.com/@mattnavarra/post/DOWa_61Cown/>

## How to apply

When `/blog write <slug>` is followed by a LinkedIn post draft:

1. Compose the body in the four-line skeleton above.
2. Verify total word count is 50-90 (target ~70).
3. Verify total character count is 350-600 (hard ceiling 700).
4. Verify line 1 (the hook) is under 140 characters.
5. Run the voice guard against the LinkedIn post even though it lives on Drive — same banned-word rules apply.
6. ONE link only. NEVER add a repo link.
7. 3-5 hashtags at the end.
8. Append to `linkedin_Posts.md` newest-at-top with `## YYYY-MM-DD — <Title> (DRAFT, not published)`.

When in doubt: if removing 30% of the words would still leave a coherent tease, the draft is too long.
