---
title: "You are subscribed"
description: "Confirmed. New posts from hoiboy.uk will land in your inbox."
hideDate: true
sitemap:
  disable: true
# Keep this page OUT of every list page and out of the RSS feed, while still
# rendering it so Brevo's redirectionUrl can land on it. The X-Robots-Tag noindex
# in static/_headers does NOT cover either surface: without this block Hugo puts
# the full rendered body into public/index.xml, which every page advertises via
# <link rel="alternate">, so every subscriber receives "You are subscribed" as a
# post. Same fix and same reason as content/private/tools/meet-recorder/index.md,
# which records it from Ralph round 15 of blog-priv#55. Asserted by
# scripts/check_noindex_frontmatter.py.
build:
  list: never
  render: always
---

That is you confirmed. New posts will land in your inbox.

No spam, and there is an unsubscribe link at the bottom of every email. If you would rather sort it out by hand, email [hello@hoiboy.uk](mailto:hello@hoiboy.uk) and I will take you off the list.

What I do with your name and email is set out in the [Privacy Notice](/legal/privacy/).

## Start here

- [Tech & AI](/blogs/tech-ai/)
- [Food & booze](/blogs/food-booze/)
- [Adventure](/blogs/adventure/)

Or head back to the [blog](/blogs/).
