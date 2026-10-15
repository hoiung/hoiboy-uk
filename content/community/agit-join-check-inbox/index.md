---
title: "Check your inbox"
description: "Check your inbox to confirm your AGIT signup."
hideDate: true
# Where the AGIT signup form's 303 lands (AGIT_CHECK_INBOX_PATH in
# functions/api/subscribe.js). A sibling bundle with a url override, the
# agit-thanks pattern, under /joined/ so the noindex rule in static/_headers
# cannot also match the signup page itself (#65).
url: "/community/asians-gingers-in-tech/joined/check-inbox/"
breadcrumbParent: "/community/asians-gingers-in-tech"
sitemap:
  disable: true
# Out of every list page and the RSS feed, still rendered so the redirect can land
# here. Same reason as content/newsletter/check-inbox/index.md; asserted by
# scripts/check_noindex_frontmatter.py.
build:
  list: never
  render: always
---

<!-- iamhoi -->
Almost there. We have sent you an email with a confirmation link.

Click that link to confirm your email is correct, and then we send you the welcome email with your WhatsApp invite.

If it has not turned up in a few minutes, have a look in your spam folder.
<!-- iamhoiend -->
