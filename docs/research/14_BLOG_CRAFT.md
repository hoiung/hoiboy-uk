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

75% of readers prefer posts under 1,000 words, but posts over 2,000 words rank 4x better in search. Resolution: make the first 800 words so good they keep reading. Write long, publish tight (cut 20-30% in editing). Hard stop: drafts crossing 3,000 words get split or cut back, no exceptions. Enforced by `scripts/check_wordcount.py` (pre-commit + CI). Negative example on file: `sst3-ai-harness-reshapeable-knife` (15 Apr 2026, 5,143 words, 2x target).

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

## Headline Craft

Research compiled from BuzzSumo (100M+ articles), Backlinko (912M posts), Upworthy (8,977 A/B experiments), Outbrain, CoSchedule (4M+ headlines), Nature Human Behaviour, and PNAS studies. Updated April 2026.

### The Core Rule

Spend disproportionate time on the title. Upworthy's data showed winning headlines produce 20-500% CTR lifts over losers. The title is the only thing most people will ever read.

### Hoi's Natural Title Style (from corpus analysis)

Before applying any formula, know what Hoi already does well:

- **Average: 7 words.** Sweet spot is 6-8 (53% of his titles).
- **Title Case** (capitalise every word, not strict AP/Chicago). Lowercase only as a deliberate voice signal ("i r back!").
- **Numbered lists are his default** (22% of titles). Numbers 3, 5, 7, 16.
- **Questions are his second mode** (17%). Practical utility questions, not philosophical.
- **Best titles use the double-sentence structure**: "Falling in Zouk Love Again. My Russian Saga." Full stop mid-title creates a two-beat rhythm (headline + subhead collapsed into one).
- **Parenthetical flags**: "(Uncensored)" signals stakes and honesty.
- **CAPS on a single key word**: "DOOMED to Fail" earns emphasis without shouting.
- **Post-mortem framing** works well: "The Idea That Won't Die", "Why it was DOOMED to Fail".
- **Weakest titles are bare labels** with no angle: "Birmingham Bouldering Centre", "Turtle Bay Restaurant". Always add an opinion or hook.

### Optimal Length

| Surface | Optimal length |
|---|---|
| Blog title (H1) | 6-13 words |
| SEO title tag | 50-60 characters (Google truncates at ~600px width) |
| Social sharing (og:title) | Under 70 characters (safe across Twitter, LinkedIn, Facebook) |
| Meta description | 155-160 characters |

Title case gets 2.4% more organic clicks than sentence case (SEMrush, 28-day split test, 96% confidence).

### H1 vs SEO Title

They should be **different but aligned**. The H1 is for the reader on the page (can be longer, more conversational). The SEO title tag is for SERP clicks (50-60 chars, keyword front-loaded). If they match exactly, you lose the chance to optimise for two surfaces. Hugo's `title:` frontmatter becomes the H1. Use `params.seoTitle` or the description field for the SERP version if needed.

### What the Data Says Works

| Finding | Data | Source |
|---|---|---|
| Numbers increase CTR | +36% vs no numbers | ConversionXL / Conductor |
| Questions increase shares | +23.3% | Backlinko, 912M posts |
| Negative framing beats positive | +63% CTR for negative superlatives ("worst", "never") vs positive ("best", "always") | Outbrain |
| Odd numbers beat even (usually) | +20% CTR for odd-numbered lists | CMI. But BuzzSumo shows 10 still wins on raw shares. |
| Digits beat spelled-out numbers | Always use "7" not "Seven" | Nielsen Norman Group eye-tracking |
| Front-load keywords | Keywords in first 3-4 words get stronger SERP weight and survive truncation | Backlinko, Moz |
| Sadness increases clicks | +0.7% per SD | Nature Human Behaviour, 105K headlines |
| Joy decreases clicks | -0.9% per SD | Same study |
| Each negative word | +2.3% CTR per word | Same study |
| Each positive word | -1.0% CTR per word | Same study |

### Formulas That Perform (ranked by data)

1. **Number + noun + value**: "7 Dance Tips from Zero to Hero". BuzzSumo's top 7 performers are all number-led.
2. **How to X (without Y)**: Strongest on LinkedIn (3x nearest rival in B2B). Clear utility promise.
3. **Why X Is Y (opinion/argument)**: Negative framing variant. "Why Being a UK Landlord Is a Mug's Game".
4. **Question headline**: "Do We Actually Need LLM Wiki?" Sustains prefrontal cortex engagement 1.9s longer than declarative. But underperforms with loyal audiences who prefer directness.
5. **[Thing]. [Verdict/Story]**: Hoi's double-sentence format. "ReportaDancer.com. Why it was DOOMED to Fail." Works as a collapsed headline + subhead.
6. **Personal specific**: "What we learned after auditing 117 landing pages". Signals a real human did a real thing.

### The Curiosity Gap (Use With Care)

Partial information drives clicks. Nature Scientific Reports (2024, 8,977 Upworthy experiments): 50.9% of headlines would see CTR DECREASE if made more concrete. Only 8.7% benefit from more concreteness. The sweet spot is partial information. But Penn State/ACM CHI (2021) found clickbait triggers source derogation (distrust) rather than engagement. The line: **the content must deliver on the headline's implied promise**.

### Emotional Triggers

- **Sadness** increases click odds. Fear and joy both decrease them.
- Power words cluster into: urgency (alert, critical, pending), exclusivity (accepted, eligible, limited), emotion (dream, epic, warning), value (deal, bargain, sale).
- Personal pronouns increase CTR by 14-33 percentage points (Tandfonline, 1,828 headline pairs). "You/your" outperforms "I/my" in marketing contexts.
- EMV (Emotional Marketing Value) benchmark: average English text ~20% EMV words. Professional copywriters hit 30-40%. Elite hit 50-75%.

### BuzzSumo Shifts (2017 vs 2020)

The landscape changed. "Will make you" collapsed from 1.7M shares to 143K. Emotional clickbait died.

| Era | Top Facebook phrases |
|---|---|
| 2017 | "will make you", "this is why", "can we guess" |
| 2020 | "of the year", "in X years", "for the first time", "you need to" |

Optimal headline length shifted from 15 words / 95 chars (2017) to 11 words / 65 chars (2020). Audiences want faster consumption.

### Personal Blog Titles (Not Corporate Content)

Lessons from Seth Godin, Paul Graham, Derek Sivers:

- **Godin**: 2-5 word noun phrases, no verbs, mild provocation. "Plumbed." "Kinder than necessary."
- **Graham**: Either "How to X" (direct utility) or a single provocative noun ("Heresy", "Founder Mode").
- **Sivers**: Short imperative or present-tense observation. Never a listicle. "Offline 23 hours a day."
- **Pattern across all three**: no numbers, no brackets, no "ultimate guide." Confidence by omission.
- **Hacker News sweet spot**: specific verb + concrete result. "Fingerprinting is worse than I thought."
- **Anti-clickbait that works**: honest specificity. "We've fabricated steel for 30 years. Here's what most people get wrong."

### 10 Headline Mistakes

1. **Overpromising**: 63% of UK news audiences say clickbait reduces trust (Reuters Institute).
2. **Vague/generic**: a headline that could be about anything signals low value before the click.
3. **Too clever**: puns that sacrifice clarity. If the reader has to decode the joke, they scroll.
4. **Keyword stuffing**: Google penalises it. Readers bounce.
5. **Curse of knowledge**: assuming the reader already cares. The headline must earn their interest.
6. **Giving away the conclusion**: no reason to click if the verdict is already in the title.
7. **Too long**: optimal is 60-100 chars. Google truncates at ~63 chars on desktop.
8. **Passive voice**: "Profits Were Increased" vs "New Strategy Triples Profits". Active wins.
9. **Jargon/acronyms**: excludes the majority of potential readers.
10. **Bare label with no angle**: "Birmingham Bouldering Centre" could be anything. Always add a hook.

### The Writing Process

1. **Write 25 headlines** (Upworthy's technique). The first 5 are obvious. The good ones come from 15-25. The discipline forces you past cliches.
2. **Title first OR last, but never as an afterthought.** Copyblogger: write it first because it determines your angle. Many writers: write last because the body dictates the summary. The non-negotiable: spend real time on it.
3. **Title + description as a one-two punch.** The title hooks. The description (Hugo's `description:` frontmatter) qualifies. Write them as a pair. The description should expand the promise, not repeat the title. 155-160 characters max.
4. **The dinner party test.** Does your headline contain something worth breaking out at a dinner party? If it's too dry to repeat in conversation, it lacks a genuine hook.
5. **Run it through CoSchedule Headline Analyzer** (free, scores 0-100 on word balance, sentiment, readability). Not authoritative, but catches obvious weakness.

### Year Numbers in Titles

Ahrefs data: users skip stale-titled results. "Best CRM Tools 2023" at position 3 loses clicks to "Best CRM Tools 2026" at position 5. But year in the URL slug ages badly. **Put the year in the title tag only, not the slug.** Update the title annually for evergreen content.

### Platform-Specific Notes

| Platform | Headline preference |
|---|---|
| Facebook | Instructional and emotional. "of the year", "you need to know" |
| Twitter/X | Curiosity-gap and trend-focused. "the future of" |
| LinkedIn/B2B | "How to" dominates (3x nearest rival). Practical, data-led, aspirational |
| Hacker News | Specific + concrete. "I built [thing] to solve [specific problem]" |

### Tools

- **CoSchedule Headline Analyzer** (coschedule.com/headline-analyzer): Most comprehensive free option. Scores word balance, sentiment, readability.
- **Sharethrough Headline Analyzer** (headlines.sharethrough.com): AI-powered. Best for social/ad formats.
- **AMI EMV Analyzer** (aminstitute.com/headline): 30-second emotional punch sanity check.
- **None replace real click data.** A/B test via email subject lines first (fastest signal), then apply winners to article titles.

### Sources

- [BuzzSumo 100M Headlines Study](https://buzzsumo.com/blog/most-shared-headlines-study/)
- [BuzzSumo 10M LinkedIn Headlines](https://buzzsumo.com/blog/write-engaging-b2b-headlines-analysis-10-million-articles-shared-linkedin/)
- [Backlinko Blogging Stats 2026](https://backlinko.com/blogging-stats)
- [Backlinko 4M Google Search Results](https://backlinko.com/google-ctr-stats)
- [Nature Human Behaviour: Negativity Drives Online News](https://www.nature.com/articles/s41562-023-01538-4)
- [Nature Scientific Reports: Curiosity Gaps (2024)](https://www.nature.com/articles/s41598-024-81575-9)
- [Banerjee & Urminsky: Upworthy Headline Experiments (UChicago)](https://home.uchicago.edu/ourminsky/Banerjee_Urminsky_Headlines.pdf)
- [Outbrain: Negative Superlatives Study (via Poynter)](https://www.poynter.org/reporting-editing/2014/the-worst-news-ever-negative-headlines-outperform-positive-ones/)
- [SEMrush: Title Case vs Sentence Case Split Test](https://www.semrush.com/blog/seo-split-test-result-should-you-sentence-case-or-title-sase-your-title-tags-/)
- [Nielsen Norman Group: Show Numbers as Numerals](https://www.nngroup.com/articles/web-writing-show-numbers-as-numerals/)
- [Tandfonline: Effective Headlines in Digital Environment](https://www.tandfonline.com/doi/full/10.1080/21670811.2017.1279978)
- [Penn State/ACM CHI: Does Clickbait Actually Attract More Clicks (2021)](https://dl.acm.org/doi/fullHtml/10.1145/3411764.3445753)
- [CoSchedule Headline Analyzer](https://coschedule.com/headline-analyzer)
- [Noah Kagan: Why Content Goes Viral (1M articles)](https://noahkagan.com/why-content-goes-viral-what-analyzing-100-millions-articles-taught-us/)
- [Copyblogger: How to Write Headlines That Work](https://copyblogger.com/how-to-write-headlines-that-work/)

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

## Post Format Selection (MANDATORY before writing)

Decide the post FORMAT before writing a single word. Different post types need different content structures. Getting this wrong means a full rewrite (see Issue #8: 127-book list rendered as 6-column tables, had to be rewritten as a list).

### Post Type Taxonomy

| Type | Primary format | When to use |
|---|---|---|
| Narrative / Opinion | Flowing prose paragraphs | Argument, story, editorial. Lists fragment the reasoning. |
| How-to / Tutorial | Numbered steps + H2 per step + images | Sequential instructions. Reader must follow order. |
| Listicle | Numbered H2 per item + bullet pros/cons | 5-20 ranked or curated items. Each item is self-contained. |
| Catalogue / Collection | Bold-title list entries + inline metadata | 20-200+ items. Reference browsing, not deep reading. |
| Comparison | Side-by-side tables + pros/cons + verdict | Reader needs to evaluate attributes across options simultaneously. |
| Review | H2 per criterion + star/score + CTA | Single product evaluation. Conversion-oriented. |
| Roundup | Card-style or mini-list with link + summary | Curating other people's content with brief commentary. |
| Pillar / Guide | TOC + H2/H3 hierarchy + mixed prose, lists, tables | Breadth requires navigation scaffolding. 3,000+ words. |

### When to Use Tables

Tables are for **genuinely relational, two-dimensional data** where the row/column intersection carries meaning. The W3C test: "if removing the table structure would lose meaning, it's tabular."

**Tables ARE correct for:**
- Comparison grids (features across products)
- Stats/metrics tables (category counts, percentages)
- Pricing tiers, spec sheets
- Schedules and timetables

**Tables are WRONG for:**
- Book/resource lists (not comparing attributes across items)
- Step-by-step instructions (use numbered lists)
- Narrative content with metadata (use bold-title list entries)
- Any list where each item has a variable-length description

**Mobile rule:** More than 3 columns requires a responsive strategy. More than 5 columns will break on phones (375px viewport fits 2-3 narrow columns max). 6-column tables with long text cells are unreadable on mobile.

### Catalogue / Collection Posts (20+ items)

This is the format for reading lists, tool stacks, resource directories. Research from Derek Sivers (473 books), Patrick Collison (1,000+ books), Ryan Holiday, Austin Kleon, Jason Kottke.

**Entry format (bold-title list):**
```markdown
**127. The Art of War** by Sun Tzu · T · Physical
Why this book matters in one sentence from personal experience.
```

**Key principles:**
- Bold title is the primary visual anchor. The eye scans for bold on the left edge.
- Metadata (author, category, format) inline after title, lighter weight.
- Description is one line about WHY the book is useful, not a textbook summary.
- Consistent entry structure throughout. Reader learns the pattern after 3-4 entries.
- White space between entries. The margin tells the eye "this is one unit."

**For 50+ items:**
- Group by section (year, category, theme). Cognitive limit is ~7 items per group.
- Jump links / anchor TOC at the top. Each section heading gets an `id`.
- "Back to top" links at each section end for mobile.
- Never paginate a list that should be scannable (breaks Ctrl+F).

**One-liner quality rule:**
The description must answer "why should I read this?" not "what is this about?" Wrong: "Ancient strategy on conflict and warfare." Right: "Every chapter applies to business, negotiation, and knowing when NOT to act." The reader already knows what the book is from the title. They want to know what they'll GET from it.

**What the best reading lists do:**
- Derek Sivers: cover + title + author + numeric rating + personal notes
- Patrick Collison: title only + colour-coding for quality tier (radical minimalism)
- Ryan Holiday: deep categorical sections, 50-200 word editorial per book
- Austin Kleon: thematic sections, conversational subheadings, 1-3 sentences personal reaction
- None of them use HTML tables for the book list

### Format Decision Checklist (ask before writing)

1. **What type of post is this?** (narrative, listicle, catalogue, tutorial, comparison, review)
2. **How many items?** (<10 = listicle with H2 per item. 10-50 = grouped list. 50+ = catalogue with TOC and sections)
3. **Is the data genuinely tabular?** (comparing attributes across items = table. Sequential list with metadata = not a table)
4. **Will this render on mobile?** (>3 columns = needs responsive strategy. Long descriptions in table cells = will break)
5. **What does the reader need to DO with this?** (scan and pick = bold-title list. Compare options = table. Follow steps = numbered list. Read an argument = prose)

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
- [Derek Sivers book notes](https://sive.rs/book) (473 books, single-page catalogue)
- [Patrick Collison bookshelf](https://patrickcollison.com/bookshelf) (1,000+ books, colour-coded)
- [Ryan Holiday reading list](https://ryanholiday.net/the-reading-list/) (deep categorical sections)
- [Austin Kleon reading year](https://austinkleon.com/2022/12/28/my-reading-year-2022/) (thematic prose)
- [Jason Kottke media diet](https://kottke.org/23/12/my-recent-media-diet-the-end-of-2023-edition) (bold title + letter grade)
- [W3C WAI Tables Tutorial](https://www.w3.org/WAI/tutorials/tables/) (when tables are appropriate)
- [CSS-Tricks: Responsive Data Tables](https://css-tricks.com/responsive-data-tables/)
- [CSS-Tricks: Definition Lists](https://css-tricks.com/utilizing-the-underused-but-semantically-awesome-definition-list/)
- [WebAIM: Creating Accessible Tables](https://webaim.org/techniques/tables/)
- [Semrush: How to Format a Blog Post](https://www.semrush.com/blog/how-to-format-a-blog-post/)
- [HubSpot: How to Choose Blog Post Format](https://blog.hubspot.com/marketing/how-to-choose-blogging-post-format-ht)
- [NN/G: In-Page Links and Content Navigation](https://www.nngroup.com/articles/in-page-links-content-navigation/)

---

*Research compiled: 2026-04-09, updated: 2026-04-12 (Post Format Selection added after Issue #8 lesson)*
