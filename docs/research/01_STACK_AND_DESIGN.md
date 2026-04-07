# Stack and Design Research

**Date**: 2026-04-07
**Decision**: Hugo + Cloudflare Pages, design referenced from stephendiehl.com.

## Static Site Generator Comparison

Researched 7 candidates against constraints: markdown-first, Claude-friendly, minimal maintenance, ~hundreds of legacy posts to import, Cloudflare Pages compatible.

### Hugo (Go) — **CHOSEN**
- ~75k stars, since 2013
- Build speed: fastest. 1000 posts in ~1 second.
- Single binary (`apt install hugo`), no Ruby/Node/Python dep hell on WSL
- Page bundles: each post is a folder with `index.md` + co-located images. Perfect for 22 years of mixed content.
- YAML frontmatter, conventional layout
- Massive training data — Claude Code knows it cold
- Cloudflare Pages has native Hugo support
- Mature minimal themes: `risotto`, `archie`, `hugo-paper`, `hugo-theme-console`
- Trade-off: Go template syntax is unusual if you customise heavily, but you rarely touch templates with a good theme

### Zola (Rust) — runner-up
- ~14k stars, since 2017
- Single Rust binary, very fast, no template quirks
- Tera templates (Jinja-like)
- Smaller theme pool — more upfront CSS work
- Pick this only if you want even less surface area than Hugo

### Astro (JS/TS)
- Modern, component-based, typed frontmatter via Zod
- npm dependency churn — overkill for a pure blog
- Skip

### Eleventy (11ty)
- Flexible, "no opinions" — which is a liability for an LLM agent (many ways to do things)
- Skip

### Jekyll (Ruby)
- GitHub Pages native, but Ruby/bundler pain on WSL, slow builds
- Skip

### Next.js static export
- React overhead, multiple competing markdown patterns (MDX, contentlayer)
- Wrong tool. Skip.

### Pelican (Python) — Stephen Diehl uses this
- Quirky non-YAML metadata format (`Title:`, `Date:` as colon lines)
- Small theme pool
- The Diehl association is the only draw, and his minimal aesthetic is replicable on any SSG. Skip.

## Diehl's Site as Design Reference

stephendiehl.com structurally:

- **Stack**: Pelican + Pandoc, Tailwind compiled CSS, Apache static serve, no JS framework
- **Layout**: Fixed left sidebar (256px) + main column (`max-w-4xl`, ~896px) centred on light grey background
- **Sidebar contents**: name, Index, Blog, flat tag shortcuts, social links, RSS, novelty "LCARS Mode" easter egg
- **Homepage**: 4 sentences. That's it. Zero hero, zero CTAs.
- **Post page**: H1 title, prose, optional metadata pill bar (date + tags) injected via JS in "reading mode"
- **Typography**: IBM Plex Sans (body), Cormorant Garamond (serif accent), Source Code Pro (code) — all from Google Fonts
- **Colour**: pure greyscale. Light grey bg, white cards, grey-600 → grey-900 link hover. No brand colour anywhere.
- **Taxonomy**: tags only. No categories, no year archives, no related-posts widget.
- **Code/math/diagrams**: Prism.js + MathJax 3 + Mermaid 10, all CDN scripts, no build plugins
- **Images**: plain `<img>` in `/images/`, no srcset gymnastics
- **Footer**: one line, copyright "2009 — 2026"

## Why this works as a reference

1. Effectively Markdown → Pandoc → HTML template. One file per post. Claude Code thrives on this.
2. One template, one stylesheet, zero JS framework. 22 years rebuilds in seconds.
3. **Restraint as branding** — greyscale + IBM Plex + max-w-4xl is the entire design system. Nothing to maintain.
4. Tags-only taxonomy. Doesn't collapse under its own weight at scale.
5. Content-first chrome. The homepage is 4 sentences. Every saved pixel is a pixel he doesn't maintain in 2036.
6. MathJax + Prism + Mermaid as drop-in CDN scripts. No build-time plugins, no MDX.

## Recipe for hoiboy.uk (SUPERSEDED 2026-04-07: see updated recipe below)

Original draft (kept for trail). Replaced after voice-profile audit pivoted theme + design tokens.
