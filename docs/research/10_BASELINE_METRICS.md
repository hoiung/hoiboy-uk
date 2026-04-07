# Baseline Metrics

**Date**: 2026-04-07
**Captured at**: end of Phase 0 (foundation, 1 stub post)
**Purpose**: regression detection for Phase 1+. Phase 0 is baseline-only, no hard gates beyond voice and provenance.

## Local Hugo build

| Metric | Value | Method |
|---|---|---|
| Pages built | 21 | `hugo --gc -e production` |
| Build time | ~30 ms | as above |
| Hugo version | 0.160.0 extended | `.hugo-version` |
| Hugo memory (RSS, peak) | TBD post-deploy | not measured locally |

## CI runtime

| Metric | Value |
|---|---|
| Total wall-clock | TBD after first green run |

## Page weight (homepage)

| Metric | Value |
|---|---|
| Total transfer | TBD post-deploy (curl + size) |
| HTML size | TBD |
| CSS size (compressed, fingerprinted) | TBD |
| Render-blocking resources | Inter from Google Fonts (preconnected) |

## Lighthouse (manual, mobile, homepage)

Captured manually post-deploy. Not a hard gate in Phase 0.

| Metric | Value |
|---|---|
| Performance | TBD |
| Accessibility | TBD |
| Best Practices | TBD |
| SEO | TBD |

## Hard gates (Phase 0)

| Gate | Pass/Fail |
|---|---|
| Em dash count in tracked files | 0 (PASS) |
| Voice-banned word count in stubs | 0 (PASS) |
| `.hugo-version` exists and read by CI | (validated by CI) |
| `build-info.json` deployed and fetchable | (validated by Phase 0.8 curl) |
| Atomic rollback smoke-tested | (Phase 0.8 manual) |

## Refresh procedure

After every deploy in Phase 1+, re-run:
```bash
hugo --gc -e production  # capture build time
curl -s -o /tmp/h.html https://hoiboy.uk && wc -c /tmp/h.html
curl -s https://hoiboy.uk/build-info.json
```
Update this doc if any metric drifts >20% from baseline.
