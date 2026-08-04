---
title: "Check your inbox"
description: "One more click and you are subscribed to new posts from hoiboy.uk."
hideDate: true
sitemap:
  disable: true
# Keep this page OUT of every list page and out of the RSS feed, while still
# rendering it so the endpoint's 303 can land on it. The X-Robots-Tag noindex in
# static/_headers does NOT cover either surface: without this block Hugo puts the
# full rendered body into public/index.xml, which every page advertises via
# <link rel="alternate">, so every subscriber receives "Check your inbox" as a
# post. Same fix and same reason as content/private/tools/meet-recorder/index.md,
# which records it from Ralph round 15 of blog-priv#55. Asserted by
# scripts/check_noindex_frontmatter.py.
build:
  list: never
  render: always
---

<!-- iamhoi -->
Almost there. I have sent you an email with a confirmation link.

Click that link and you are on the list. If it has not turned up in a few minutes, have a look in your spam folder.

Nothing gets sent until you confirm, and every email after that has an unsubscribe link in it.

## While you are waiting

- [Tech & AI](/blogs/tech-ai/)
- [Food & booze](/blogs/food-booze/)
- [Adventure](/blogs/adventure/)

Or head back to the [blog](/blogs/).
<!-- iamhoiend -->
