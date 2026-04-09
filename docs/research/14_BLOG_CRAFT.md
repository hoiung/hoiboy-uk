# Blog Craft Research

Research on writing engaging personal tech blogs. Informs the /blog skill and all future blog posts on hoiboy.uk.

---

## Optimal Length

| Content type | Word count |
|---|---|
| Personal narrative / opinion | 800-1,200 |
| Tech/personal hybrid ("I built this") | 1,500-2,500 |
| Deep technical breakdown / pillar | 2,500-4,000 |

The engagement peak is ~1,928 words. Tech niche trends slightly shorter because screenshots and code blocks carry informational weight.

75% of readers prefer posts under 1,000 words, but posts over 2,000 words rank 4x better in search. Resolution: make the first 800 words so good they keep reading. Write long, publish tight (cut 20-30% in editing).

---

## Story Spine (Pixar Structure for Tech Blogs)

From Anvil's engineering blog and improv comedy:

```
Once upon a time, [the situation before the problem]...
Every day, [the normal routine / how you worked before]...
One day, [the inciting incident: the bug, the limitation, the idea]...
Because of that, [what you tried]...
Because of that, [what happened next]...
Until finally, [the resolution]...
Ever since, [the new normal / takeaway]...
```

Maps to three-act structure. Emotional involvement drives memory and action. Posts that use this arc are more shared and recalled.

---

## Writing Techniques

### Have a clear, arguable opinion
The recipe for a popular tech post is a genuine conviction, not a comprehensive topic coverage. Write to spread your actual view. Trying to please everyone interests no one.

### Write for one specific person
Pick a specific reader (often yourself at an earlier stage). Trying to reach everybody produces bloated posts or paralysis.

### Lead with a hook, not with context
The intro must: prove you understand the reader's problem, and make it obvious they'll learn something. 2-3 sentences before they close the tab.

### Use conversational register
Imagine explaining to a colleague over coffee, not delivering a formal presentation. Personality is not unprofessional.

### Narrate decisions, not just outcomes
Why did you pick this library? Why did you abandon that approach? The reasoning is more interesting than the final solution.

### Share setbacks, not just wins
"I tried X, it failed for Y, here's what I learned" is shareable. "I did X and it worked" is forgettable.

### Interweave personal and technical
Don't alternate blocks. Weave them: "Here's the line that caused the bug. I found it at midnight after dismissing it three times." The personal beat gives the technical beat weight.

### Use concrete numbers everywhere
"$62K MRR in 90 days" beats "grew quickly." Numbers ground stories in reality and make claims credible.

---

## Building in Public

From Indie Hackers analysis of 500 posts:
- Zero percent of top-50 posts were announcements ("I launched X")
- Most-engaged posts are stories with concrete arc and takeaway
- Transparency attracts feedback, community, and trust
- Authenticity is the differentiator in 2025-2026. AI-generated content floods the web; real imperfection is the moat.

---

## Screenshot Best Practices

### When to use
- Step-by-step processes where UI state matters
- Before/after comparisons
- Dashboard data tedious to describe in prose
- Specific UI features or unexpected behaviour

### When NOT to use
- Code samples (use code blocks: searchable, copyable, scalable)
- Full-screen dumps where only 10% is relevant (crop ruthlessly)
- Decoration without information

### Technical
- Save as PNG (lossless). JPEG degrades text in screenshots.
- Keep file size under 500KB
- Match width to content column (typically 700-900px)
- Zoom before screenshot, crop after
- Annotate: arrows and callout boxes focus the eye
- Blur sensitive data before publishing

### Rule
Each screenshot must earn its place by removing ambiguity. Ask: "If I removed this image, would the reader be confused?" If not, cut it.

---

## Hugo Lightbox: GLightbox Implementation

### How to use (quick reference)

1. Drop images into your page bundle folder alongside `index.md`
2. Add `{{</* gallery */>}}` where you want the gallery to appear
3. Done. Hugo generates thumbnails automatically. GLightbox handles the lightbox.

```
content/posts/my-post/
  index.md          <- add {{</* gallery */>}} in the markdown
  screenshot-1.png  <- images go here
  screenshot-2.png
  screenshot-3.png
```

Optional: use `name` param for multiple galleries per post:
```markdown
{{</* gallery name="before" */>}}
... some text ...
{{</* gallery name="after" */>}}
```

### What the reader sees

- Responsive thumbnail grid (3 columns desktop, 1 column mobile)
- Click any thumbnail: full-screen lightbox overlay
- Left/right arrows or swipe to navigate between images
- Keyboard: arrow keys to navigate, Escape to close
- If JS fails: thumbnails link directly to full images (graceful degradation)

### How it works (architecture)

GLightbox v3.3.0 is vendored locally at `static/vendor/glightbox/` (no CDN, no CSP issues).

| File | Location | Loaded when |
|------|----------|-------------|
| GLightbox CSS | `layouts/_partials/head.html` | Page uses `{{</* gallery */>}}` shortcode |
| GLightbox JS | `layouts/_partials/glightbox.html` | Page uses `{{</* gallery */>}}` shortcode |
| Init script | `static/vendor/glightbox/glightbox-init.js` | Page uses `{{</* gallery */>}}` shortcode |
| Gallery shortcode | `layouts/_shortcodes/gallery.html` | Author adds `{{</* gallery */>}}` to markdown |
| Gallery CSS | `assets/css/main.css` (.photo-gallery) | Always (site-wide CSS, lightweight) |

Conditional loading via `.HasShortcode "gallery"`: pages without the gallery shortcode load zero JS.

The `single.html` template has a `HasShortcode` guard: posts using `{{</* gallery */>}}` skip the auto-gallery (prevents double-rendering). Legacy posts without the shortcode keep their existing image grid.

### Notes for future posts

- All images in the page bundle are included in the gallery (Hugo picks them up via `.Page.Resources.ByType "image"`)
- The hero image (picked by `hero-pick.html`) will also appear in the gallery. If you want a specific hero, add a file named `hero.png` or `hero.jpg` to the bundle.
- Thumbnails are 400x300 (3:2 ratio), generated by Hugo at build time and cached
- Keep source images under 500KB each (PNG for screenshots, JPEG for photos)
- First build with new images is slower (~1s extra). Subsequent builds use cache.

---

## Sources

- [Writing a tech blog people want to read: Sean Goedecke](https://www.seangoedecke.com/on-writing/)
- [Story spine for tech blogs: Anvil](https://www.useanvil.com/blog/engineering/writing-technical-blog-posts-with-the-story-spine/)
- [How to write a great tech blog post: freeCodeCamp](https://www.freecodecamp.org/news/how-to-write-a-great-technical-blog-post-414c414b67f6/)
- [10 Tips for Developer Blogs: MoldStud](https://moldstud.com/articles/p-10-tips-for-writing-an-engaging-developer-blog-to-showcase-your-work)
- [Optimal blog length 2025: Automateed](https://www.automateed.com/how-long-should-blog-posts-be-in-2025)
- [Screenshots in technical docs: Archbee](https://www.archbee.com/blog/screenshots-in-technical-documentation)
- [500 Indie Hackers posts analysis: scottPlusPlus](https://medium.com/@scottplusplus/how-to-go-viral-on-indiehackers-a-study-of-500-posts-c467e567f1ed)
- [Details/summary lightboxes: Dan Q](https://danq.me/2025/08/15/details-summary-lightboxes-in-pure-html-css/)
- [GLightbox GitHub](https://github.com/biati-digital/glightbox)
- [PhotoSwipe 5 with Hugo: 42point](https://42point.com/en/posts/2024-04-28-photoswipe-with-hugo/)

---

*Research compiled: 2026-04-09*
