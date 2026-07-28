# Social posts - Hoi aka Hoiboy

Paste-ready social copy for this feature, one labelled block per channel. This file
does not publish (it is a Hugo bundle resource, not a page); it is the cheat-sheet
for posting.

Post native. Social platforms downrank posts with a link in the body, and for the
community, shares matter more than clicks to hoiboy.uk (that traffic comes on its
own). So the Source link goes in the first comment, never in the post body.

Every string below sits in a fenced block, so the markdownlint pre-commit hook cannot
reword post copy. All copy is derived from the approved wording of the feature page
and adds no claim that is not already on it.

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

Post the full feature story natively. Facebook has room for the whole thing, so paste
the story from the feature page rather than a cut of it, then append the hashtag set
above. This file deliberately does not reproduce the story: the feature page is the
single source, so the two cannot drift.

First comment:

```text
Source: https://hoiboy.uk/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/
```

### Instagram

REQUIRES media. Attach `hero.jpg` from this bundle (portrait 1080x1350, the Instagram
shape). Instagram will not accept a text-only post.

Caption (233 chars):

```text
First feature on Asians & Gingers in Tech, so I went first. 8 years quietly building Canonical's cloud data centres, and a Malta sprint where our kit ended up in Kabul. Full story below. #AsiansInTech #GingersInTech #AGIT #DataCentre
```

First comment:

```text
Source: https://hoiboy.uk/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/
```

### Bluesky

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

MANUAL. Groups have no API, and there is no AGIT Page. Group posts do not get the same
first-comment treatment, so the Source goes inline:

```text
First feature on Asians & Gingers in Tech, so I went first. 8 years quietly building Canonical's cloud data centres, and a Malta sprint where our kit ended up in Kabul. Full story: https://hoiboy.uk/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/
```

### Meetup

MANUAL. No posting API. Post as a group announcement using the inline-Source block
above.

### Facebook Group

MANUAL. No posting API, and distinct from the automated Facebook Page. Same
inline-Source block.

### Substack

MANUAL. No posting API. Runs as a Note rather than an issue of the newsletter, using
the inline-Source block.
