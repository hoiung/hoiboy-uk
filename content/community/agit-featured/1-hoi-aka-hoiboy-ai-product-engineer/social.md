# Social posts - Hoi aka Hoiboy

Paste-ready social copy for this feature, one labelled block per channel. This file
does not publish (it is a Hugo bundle resource, not a page); it is the cheat-sheet
for posting.

Post native. Social platforms downrank posts with a link in the body, and for the
community, shares matter more than clicks to hoiboy.uk (that traffic comes on its
own). So the Source link goes in the first comment, never in the post body.

**The first comment is not optional.** The short-form copy ends "Full story below.",
which is a promise the Source comment keeps. Post the copy, then immediately post the
Source line as the first comment. Postiz cannot do this step (see
`POSTIZ-FIRST-COMMENT: UNRESOLVED` in SKILL.md): it is by hand on every channel,
including the automated three.

Every string below sits in a fenced block, so the markdownlint pre-commit hook cannot
reword post copy. All copy is derived from the approved wording of the feature page
and adds no claim that is not already on it.

## Images: which file goes on which channel

Both images sit in this folder beside this file. They are different shapes on purpose
(see the design spec in `agit-featured/SKILL.md`), so they are not interchangeable:

| File | Size | Shape | Use it on |
|---|---|---|---|
| `share-card.png` | 1200x630 | landscape | Facebook Page, Bluesky, X, LinkedIn Group, Meetup, Facebook Group, Substack |
| `hero.jpg` | 1080x1350 | portrait | Instagram ONLY |

**Every post gets an image.** A feed post with no image gets a fraction of the reach, and
the landscape card is what the link-preview slot expects. Instagram is the only channel
that takes the portrait crop, and the only one that will REJECT a text-only post outright.

The raw submission photo is never used anywhere. These two files are generated artwork.

Feature link (the Source, used in the first comment on every post):

```text
https://hoiboy.uk/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/
```

Hashtag core set:

```text
#AsiansInTech #GingersInTech #AGIT #DataCentre #Automation
```

## Automated (Postiz)

Facebook Page, Instagram and Bluesky are fanned out by the Postiz deployment in the
agit-social repo. That repo's deploy/CHANNELS.md is the canonical channel split.

### Facebook Page

**Image:** `share-card.png` (1200x630 landscape).

Post the full feature story natively. Facebook has room for the whole thing, so paste
the story from the feature page rather than a cut of it, then append the hashtag set
above. This file deliberately does not reproduce the story: the feature page is the
single source, so the two cannot drift.

First comment:

```text
Source: https://hoiboy.uk/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/
```

### Instagram

**Image:** `hero.jpg` (1080x1350 portrait). REQUIRED. Instagram rejects a text-only post.
It is the only channel taking the portrait crop; the landscape card is wrong here.

Caption (233 chars):

```text
First feature on Asians & Gingers in Tech, so I went first. 8 years quietly building Canonical's cloud data centres, and a Malta sprint where our kit ended up in Kabul. Full story below. #AsiansInTech #GingersInTech #AGIT #DataCentre
```

First comment:

```text
Source: https://hoiboy.uk/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/
```

### Bluesky

**Image:** `share-card.png` (1200x630 landscape).

Fits inside Bluesky's 300-character cap.

Post (233 chars):

```text
First feature on Asians & Gingers in Tech, so I went first. 8 years quietly building Canonical's cloud data centres, and a Malta sprint where our kit ended up in Kabul. Full story below. #AsiansInTech #GingersInTech #AGIT #DataCentre
```

First comment:

```text
Source: https://hoiboy.uk/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/
```

## MANUAL (operator posts these by hand)

X and TikTok are deferred to manual by operator decision 2026-07-24. Meetup, Facebook
Group, LinkedIn Group and Substack have no posting API at all. Nothing here automates
any of them.

### X

**Image:** `share-card.png` (1200x630 landscape).

MANUAL. 280 characters including the hashtags.

Post (233 chars):

```text
First feature on Asians & Gingers in Tech, so I went first. 8 years quietly building Canonical's cloud data centres, and a Malta sprint where our kit ended up in Kabul. Full story below. #AsiansInTech #GingersInTech #AGIT #DataCentre
```

First comment:

```text
Source: https://hoiboy.uk/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/
```

### TikTok

MANUAL. Video-first, so this feature runs only if a clip exists. There is no
still-image path worth using here, and public posting would need the Content-Posting
audit anyway.

### LinkedIn Group

**Image:** `share-card.png` (1200x630 landscape).

MANUAL. Groups have no API, and there is no AGIT Page. Group posts do not get the same
first-comment treatment, so the Source goes inline:

```text
First feature on Asians & Gingers in Tech, so I went first. 8 years quietly building Canonical's cloud data centres, and a Malta sprint where our kit ended up in Kabul. Full story: https://hoiboy.uk/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/
```

### Meetup

**Image:** `share-card.png` (1200x630 landscape).

MANUAL. No posting API. Post as a group announcement using the inline-Source block
above.

### Facebook Group

**Image:** `share-card.png` (1200x630 landscape).

MANUAL. No posting API, and distinct from the automated Facebook Page. Same
inline-Source block.

### Substack

**Image:** `share-card.png` (1200x630 landscape).

MANUAL. No posting API. Runs as a Note rather than an issue of the newsletter, using
the inline-Source block.
