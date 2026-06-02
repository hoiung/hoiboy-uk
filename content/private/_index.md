---
title: Private
# Operator-only section (consulting-ops#8 meet-recorder). The section index is
# headless and unrendered so /private/ never appears in the sitemap and returns
# 404 to the public. Child tool pages still render (they are reached by direct
# URL only) but are noindex + nofollow via static/_headers.
build:
  list: never
  render: never
  publishResources: false
---
