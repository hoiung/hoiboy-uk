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

### Why GLightbox
- 17 KB JS + 9 KB CSS (CDN, no build step)
- Swipe, keyboard nav, touch support
- `data-gallery` attribute groups images automatically
- One init call wires everything up

### Shortcode: `layouts/_shortcodes/gallery.html`

```html
{{- $images := .Page.Resources.ByType "image" -}}
{{- $folder := .Get "folder" -}}
{{- if $folder -}}
  {{- $images = .Page.Resources.Match (printf "%s/*.{jpg,jpeg,png,webp,gif}" $folder) -}}
{{- end -}}
{{- $gallery := .Get "name" | default "gallery" -}}

<div class="photo-gallery">
  {{- range $images }}
    {{- $thumb := .Fill "400x400 Lanczos" -}}
    <a href="{{ .RelPermalink }}"
       class="glightbox"
       data-gallery="{{ $gallery }}"
       data-title="{{ .Title | default .Name }}">
      <img src="{{ $thumb.RelPermalink }}"
           alt="{{ .Title | default .Name }}"
           width="{{ $thumb.Width }}"
           height="{{ $thumb.Height }}"
           loading="lazy">
    </a>
  {{- end }}
</div>
```

### CSS: gallery grid

```css
.photo-gallery {
  columns: 3 200px;
  gap: 0.75rem;
}
.photo-gallery a {
  display: block;
  break-inside: avoid;
  margin-bottom: 0.75rem;
}
.photo-gallery img {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 4px;
  transition: opacity 0.2s ease;
}
.photo-gallery a:hover img { opacity: 0.85; }
@media (max-width: 600px) { .photo-gallery { columns: 1; } }
```

### Load GLightbox in baseof.html

In `<head>`:
```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/glightbox@3.3.0/dist/css/glightbox.min.css">
```

Before `</body>`:
```html
<script src="https://cdn.jsdelivr.net/npm/glightbox@3.3.0/dist/js/glightbox.min.js"></script>
<script>
  document.addEventListener("DOMContentLoaded", function () {
    GLightbox({ selector: ".glightbox", touchNavigation: true, loop: true, zoomable: true, draggable: true });
  });
</script>
```

### Usage in markdown
```markdown
{{</* gallery */>}}
{{</* gallery folder="photos" name="trip-2024" */>}}
```

### Alternative: Pure CSS (no JS, single-image only)

Uses `<details>`/`<summary>` native HTML. No gallery navigation between images. Good for click-to-enlarge on individual images. See lightbox research for full implementation.

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
