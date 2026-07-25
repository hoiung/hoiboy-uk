---
title: "Fixture - valid links only"
date: 2026-05-01
draft: true
---

Inline link to a real post:
[same dancers](/blogs/same-dancers-on-the-sidelines/) is the home of the post.

Trailing-slash agnostic — both forms resolve to the same bundle:
[no slash](/blogs/same-dancers-on-the-sidelines).

The /blogs/ hub and the 7 category landings are valid:
[blogs hub](/blogs/) is the hub.

[dance section](/blogs/dance/) lists posts.

Tags taxonomy term page:
[zouk tag](/tags/zouk/).

Per-category RSS feed:
[dance rss](/blogs/dance/index.xml).

Anchor-only link, skipped:
[jump to closing](#closing-thoughts).

External skipped:
[github](https://github.com/hoiung) is fine.

Self-reference normalised then validated:
[absolute self](https://hoiboy.uk/blogs/same-dancers-on-the-sidelines/).

Reference-style link:
[ref-style usage][same].

[same]: /blogs/same-dancers-on-the-sidelines/

Image is NOT a link, image existence is a different bug class:
![alt text](/dance/should-be-skipped-because-image.png).

Reference-style IMAGE definition is also not a link, even when the URL would
look like a section-prefix link in isolation:

![alt][refimg]

[refimg]: /dance/should-be-skipped-because-ref-image.jpg

Hugo shortcode — interior is not link-extractable:
{{< figure src="/dance/example.jpg" alt="example" >}}

Code fence — interior never scanned:

```
[fenced bad link](/dance/never-checked-because-fenced/)
```

Inline code — interior never scanned: `[inline](/dance/never-checked/)`.

HTML comment — interior never scanned:

<!-- [commented bad](/dance/never-checked/) -->

A post whose frontmatter `slug:` overrides its bundle directory name resolves on
the SERVED slug, which is what the site actually publishes:
[slug override](/blogs/foundation/) and [alias slug](/blogs/ai-jargon-for-newbies/).
