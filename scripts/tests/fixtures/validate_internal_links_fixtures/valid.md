---
title: "Fixture - valid links only"
date: 2026-05-01
draft: true
---

Inline link to a real post:
[same dancers](/posts/same-dancers-on-the-sidelines/) is the home of the post.

Trailing-slash agnostic — both forms resolve to the same bundle:
[no slash](/posts/same-dancers-on-the-sidelines).

Section landings (single segment) are valid:
[dance section](/dance/) lists posts.

Tags taxonomy term page:
[zouk tag](/tags/zouk/).

Per-section RSS feed:
[dance rss](/dance/index.xml).

Anchor-only link, skipped:
[jump to closing](#closing-thoughts).

External skipped:
[github](https://github.com/hoiung) is fine.

Self-reference normalised then validated:
[absolute self](https://hoiboy.uk/posts/same-dancers-on-the-sidelines/).

Reference-style link:
[ref-style usage][same].

[same]: /posts/same-dancers-on-the-sidelines/

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
