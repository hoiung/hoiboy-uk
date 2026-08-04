---
title: "Thanks for your story"
description: "Your Asians & Gingers in Tech submission is in."
hideDate: true
# The community page is a leaf bundle and cannot hold a child page, so this
# sibling bundle uses a url override to serve at the /thanks/ path the form
# (functions/api/contribute.js) and the CSP/noindex _headers rules expect.
url: "/community/asians-gingers-in-tech/thanks/"
# Sit under the AGIT page in breadcrumbs (its real home), not the bare community
# section, since Hugo files this sibling bundle directly under /community/.
breadcrumbParent: "/community/asians-gingers-in-tech"
sitemap:
  disable: true
# Keep this page OUT of every list page and out of the RSS feed, while still
# rendering it so the form's redirect can land on it. The X-Robots-Tag noindex in
# static/_headers covers neither surface: without this block Hugo publishes the
# full rendered body into public/index.xml, so everyone subscribed to the feed
# receives "Thanks for your story" as a post. Same fix and same reason as
# content/private/tools/meet-recorder/index.md. Missed here when that one was
# fixed, and found by the #56 Ralph review, which is why
# scripts/check_noindex_frontmatter.py now asserts the pairing mechanically
# instead of relying on someone remembering.
build:
  list: never
  render: always
---

Thanks, your story is in.

I read every submission myself, so give me a little time. If it is a good fit for the feature series, I will be in touch by email.

## Join and follow us

Come be part of it. This is where everything happens between features.

- **Real-life meetups (London):** [meetup.com/london-asians-gingers-in-tech](https://www.meetup.com/london-asians-gingers-in-tech)
- **LinkedIn group:** [linkedin.com/groups/26310001](https://www.linkedin.com/groups/26310001/)
- **Facebook page:** [facebook.com/asians.gingers.in.tech](https://www.facebook.com/asians.gingers.in.tech)
- **Facebook group:** [facebook.com/groups/london.asians.gingers.in.tech](https://www.facebook.com/groups/london.asians.gingers.in.tech)
- **Instagram:** [@asians_gingers_in_tech](https://www.instagram.com/asians_gingers_in_tech/)
- **TikTok:** [@asians_gingers_in_tech](https://www.tiktok.com/@asians_gingers_in_tech)
- **X:** [@AsiansGingersIT](https://x.com/AsiansGingersIT)

## While you're here

Have a look around the site and the blog. Since you are into tech, you might like:

- [Tech & AI](/blogs/tech-ai/)
- [Entrepreneurship](/blogs/entrepreneurship/)

And if you want to work with me, here is what I do: [Work with Hoi](/hire-hoi/ai-consultancy/work-with-hoi/) ⭐

Or head back to the [community page](/community/asians-gingers-in-tech/).
