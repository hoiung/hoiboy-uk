# Baseline Metrics

**Date captured**: 2026-04-07
**Captured at**: end of Phase 0 (foundation, 1 stub post)
**Purpose**: regression detection for Phase 1+. Phase 0 is baseline-only.

## Local Hugo build (Phase 0 baseline)

| Metric | Value | Method |
|---|---|---|
| Pages built | 21 | `hugo --gc -e production` |
| Build time | ~30 ms | wall clock from build log |
| Hugo version | 0.160.0 extended | `.hugo-version` |

## Local Hugo build (Phase 1 outcome, 2026-04-08)

| Metric | Value | Method |
|---|---|---|
| Pages built | 136 | `hugo --gc --minify -e production` after 33-post import |
| Non-page files | 277 | bundle images |
| Processed images | 4 | hero/og processing |
| Build time | ~130 ms | wall clock from build log |
| Hugo version | 0.160.0 extended | unchanged |
| Posts in `content/posts/` | 34 (33 imports + foundation) | `ls content/posts/` count |
| Hunt logs in `docs/import-logs/` | 33 | 1:1 with imported posts |
| Posts per category | adv 5, dance 22, food 3, tech 2, relationship 2 | grep `categories:` |

## CI runtime (GHA)

| Metric | Value |
|---|---|
| Total wall-clock | ~30 seconds (from green ci.yml runs on main) |
| Cache state | cold first run, warm thereafter via `actions/cache@v4` |

## Live site weight (homepage)

Captured from `https://hoiboy.uk/` via curl on 2026-04-07.

| Metric | Value |
|---|---|
| HTML transfer (uncompressed) | 1850 bytes |
| CSS transfer (compressed, fingerprinted) | 4065 bytes |
| Time to first byte | ~120 ms |
| Render-blocking resources | none (Inter loaded async via media=print swap) |

## Lighthouse (manual)

PageSpeed Insights API hit a daily quota limit during automated capture. Manual capture deferred to user.

To capture: open https://pagespeed.web.dev/?url=https%3A%2F%2Fhoiboy.uk and run for mobile + desktop. Record:
- Performance score
- Accessibility score
- Best Practices score
- SEO score

Update this doc with the values once captured. Phase 1 will set hard regression gates against these baselines.

## Hard gates passing (Phase 0)

| Gate | Pass/Fail |
|---|---|
| Em dash count in tracked files | 0 PASS |
| Voice-banned word count in stubs | 0 PASS |
| `.hugo-version` exists, single source of truth | PASS |
| `build-info.json` deployed and matches commit | PASS (verified `de8cd4d4` and `0.160.0`) |
| Atomic deploy + recovery smoke-tested | PASS (broken commit deployed, restoration deployed, both verified) |
| Section vs taxonomy URL collision | PASS (sections removed, taxonomy terms own /food/, /tech/ etc) |

## Refresh procedure

After every deploy in Phase 1+:
```bash
hugo --gc -e production    # capture build time
curl -s -o /tmp/h.html https://hoiboy.uk && wc -c /tmp/h.html
curl -s https://hoiboy.uk/build-info.json
```
Update this doc if any metric drifts >20% from baseline.
