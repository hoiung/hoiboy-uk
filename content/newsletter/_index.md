---
title: "Newsletter"
description: "Internal section holder for the newsletter confirmation pages."
sitemap:
  disable: true
# There is no /newsletter/ landing page and there should not be one. This file
# exists ONLY to stop Hugo auto-generating a section index for the two pages
# below it: without it, /newsletter/ was emitted into public/sitemap.xml as a
# listing of the confirmation pages, which is not a page anyone should reach and
# not something a search engine should be offered.
#
# It still RENDERS, deliberately. `render: never` was tried first and
# tests/test_taxonomy_terms_match_build.py caught it: the internal-link resolver
# derives /newsletter/ as a valid section path, so an unserved section is a link
# target that passes the link gate and then 404s for a reader. Keeping the page
# served costs nothing (it is noindex via static/_headers, out of the sitemap by
# the line above, and out of the feed by list: never, and both children are
# themselves list: never so it renders an empty list) and it keeps the resolver
# honest rather than weakening it to match.
build:
  list: never
  render: always
---
