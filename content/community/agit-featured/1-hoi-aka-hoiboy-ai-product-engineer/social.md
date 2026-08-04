
<!-- iamhoi -->
# Social posts - Hoi aka Hoiboy

Paste-ready social copy for this feature, one labelled block per channel. This file
does not publish (it is a Hugo bundle resource, not a page); it is the cheat-sheet
for posting.

Post native. Social platforms downrank posts with a link in the body, and for the
community, shares matter more than clicks to hoiboy.uk (that traffic comes on its
own). So the Source link goes in the first comment, never in the post body.

**TWO copy types, never the full story.** The full story lives on the feature page
and the link to it goes in the first comment. What goes out is one of two types,
and a channel's own character cap decides which one it takes:

| Type | Channels | Cap |
|---|---|---|
| **summary** | Facebook Page, Instagram, LinkedIn Group, Facebook Group, Substack | 63206 / 2200 / 3000 |
| **super short summary** | Bluesky, X | 300 / 280 |

A cap is a CEILING for one bucket, never a TARGET for all of them. One string sized
to Bluesky pasted everywhere throws away ~1950 characters of an Instagram caption:
that reads as consistency but is the smallest-common-denominator failure. Each copy
fence below is labelled with its type and its exact length, and
`agit_social_post.py` refuses to post on any mismatch.

**The first comment is not optional.** The copy ends "See comment for full story.", which
is a promise only the Source comment keeps. On the three automated channels Postiz posts
it for you: it goes out on the same call as the post, as the child of it. On the MANUAL
channels below, post the copy first, then immediately post the Source line yourself.

Every string below sits in a fenced block, so the markdownlint pre-commit hook cannot
reword post copy. All copy is derived from the approved wording of the feature page
and adds no claim that is not already on it.

## Images: which file goes on which channel

Both images sit in this folder beside this file. They are different shapes on purpose
(see the design spec in `agit-featured/SKILL.md`), so they are not interchangeable:

| File | Size | Shape | Use it on |
|---|---|---|---|
| `share-card.png` | 1200x630 | landscape | Facebook Page, Bluesky, X, LinkedIn Group, Facebook Group, Substack |
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

Post (summary, 1007 chars):

```text
Meet Hoi!

First feature on Asians & Gingers in Tech, so I went first.

Eight years at Canonical, the company behind Ubuntu. My title said Data Centre Engineer the whole time, but the role outgrew the title almost straight away: infrastructure architect, procurement lead, project manager and data centre manager, running the sites largely on my own for years. I designed and rolled out Canonical's cloud data centres across London, Boston and Taipei.

One year we had a two week sprint in Malta and the entire equipment shipment got sent to the US by mistake, then ended up in Kabul. We only found out on the setup weekend, two days before 500+ engineers started landing. Armed with two credit cards, me and Gareth bootstrapped the whole setup by hand out of a hotel room.

Nobody threw a party for any of it. The work just spoke for itself, even when the title didn't. That is usually how it goes for the quiet ones.

See comment for full story.

#AsiansInTech #GingersInTech #AGIT #DataCentre #Automation
```

First comment:

```text
Source: https://hoiboy.uk/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/
```

### Instagram

**Image:** `hero.jpg` (1080x1350 portrait). REQUIRED. Instagram rejects a text-only post.
It is the only channel taking the portrait crop; the landscape card is wrong here.

Caption (summary, 1007 chars):

```text
Meet Hoi!

First feature on Asians & Gingers in Tech, so I went first.

Eight years at Canonical, the company behind Ubuntu. My title said Data Centre Engineer the whole time, but the role outgrew the title almost straight away: infrastructure architect, procurement lead, project manager and data centre manager, running the sites largely on my own for years. I designed and rolled out Canonical's cloud data centres across London, Boston and Taipei.

One year we had a two week sprint in Malta and the entire equipment shipment got sent to the US by mistake, then ended up in Kabul. We only found out on the setup weekend, two days before 500+ engineers started landing. Armed with two credit cards, me and Gareth bootstrapped the whole setup by hand out of a hotel room.

Nobody threw a party for any of it. The work just spoke for itself, even when the title didn't. That is usually how it goes for the quiet ones.

See comment for full story.

#AsiansInTech #GingersInTech #AGIT #DataCentre #Automation
```

First comment:

```text
Source: https://hoiboy.uk/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/
```

### Bluesky

**Image:** `share-card.png` (1200x630 landscape).

The super short summary, inside Bluesky's 300-character cap.

Post (super short, 254 chars):

```text
Meet Hoi!

First feature on Asians & Gingers in Tech, so I went first. 8 years quietly building Canonical's cloud data centres, and a Malta sprint where our kit ended up in Kabul. See comment for full story. #AsiansInTech #GingersInTech #AGIT #DataCentre
```

First comment:

```text
Source: https://hoiboy.uk/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/
```

## MANUAL (operator posts these by hand)

X and TikTok are deferred to manual by operator decision 2026-07-24. Facebook Group,
LinkedIn Group and Substack have no posting API at all. Nothing here automates any of
them. Meetup is not a feature channel: it is the events surface.

### X

**Image:** `share-card.png` (1200x630 landscape).

MANUAL. The super short summary: 280 characters including the hashtags.

Post (super short, 254 chars):

```text
Meet Hoi!

First feature on Asians & Gingers in Tech, so I went first. 8 years quietly building Canonical's cloud data centres, and a Malta sprint where our kit ended up in Kabul. See comment for full story. #AsiansInTech #GingersInTech #AGIT #DataCentre
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

MANUAL. The summary, inside LinkedIn's 3000-character cap. Groups have no API, and
there is no AGIT Page. Group posts do not get the same first-comment treatment, so
the Source goes inline instead:

Post (summary, 1071 chars):

```text
Meet Hoi!

First feature on Asians & Gingers in Tech, so I went first.

Eight years at Canonical, the company behind Ubuntu. My title said Data Centre Engineer the whole time, but the role outgrew the title almost straight away: infrastructure architect, procurement lead, project manager and data centre manager, running the sites largely on my own for years. I designed and rolled out Canonical's cloud data centres across London, Boston and Taipei.

One year we had a two week sprint in Malta and the entire equipment shipment got sent to the US by mistake, then ended up in Kabul. We only found out on the setup weekend, two days before 500+ engineers started landing. Armed with two credit cards, me and Gareth bootstrapped the whole setup by hand out of a hotel room.

Nobody threw a party for any of it. The work just spoke for itself, even when the title didn't. That is usually how it goes for the quiet ones.

Full story: https://hoiboy.uk/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/

#AsiansInTech #GingersInTech #AGIT #DataCentre #Automation
```

### Facebook Group

**Image:** `share-card.png` (1200x630 landscape).

MANUAL. The summary, well inside Facebook's 63206-character cap. No posting API, and
distinct from the automated Facebook Page. Groups get no first comment, so the Source
goes inline:

Post (summary, 1071 chars):

```text
Meet Hoi!

First feature on Asians & Gingers in Tech, so I went first.

Eight years at Canonical, the company behind Ubuntu. My title said Data Centre Engineer the whole time, but the role outgrew the title almost straight away: infrastructure architect, procurement lead, project manager and data centre manager, running the sites largely on my own for years. I designed and rolled out Canonical's cloud data centres across London, Boston and Taipei.

One year we had a two week sprint in Malta and the entire equipment shipment got sent to the US by mistake, then ended up in Kabul. We only found out on the setup weekend, two days before 500+ engineers started landing. Armed with two credit cards, me and Gareth bootstrapped the whole setup by hand out of a hotel room.

Nobody threw a party for any of it. The work just spoke for itself, even when the title didn't. That is usually how it goes for the quiet ones.

Full story: https://hoiboy.uk/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/

#AsiansInTech #GingersInTech #AGIT #DataCentre #Automation
```

### Substack

**Image:** `share-card.png` (1200x630 landscape).

MANUAL. The summary. No posting API, and Substack publishes no Note character limit,
so the length gate does not apply. Runs as a Note rather than an issue of the
newsletter, with the Source inline:

Post (summary, 1071 chars):

```text
Meet Hoi!

First feature on Asians & Gingers in Tech, so I went first.

Eight years at Canonical, the company behind Ubuntu. My title said Data Centre Engineer the whole time, but the role outgrew the title almost straight away: infrastructure architect, procurement lead, project manager and data centre manager, running the sites largely on my own for years. I designed and rolled out Canonical's cloud data centres across London, Boston and Taipei.

One year we had a two week sprint in Malta and the entire equipment shipment got sent to the US by mistake, then ended up in Kabul. We only found out on the setup weekend, two days before 500+ engineers started landing. Armed with two credit cards, me and Gareth bootstrapped the whole setup by hand out of a hotel room.

Nobody threw a party for any of it. The work just spoke for itself, even when the title didn't. That is usually how it goes for the quiet ones.

Full story: https://hoiboy.uk/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/

#AsiansInTech #GingersInTech #AGIT #DataCentre #Automation
```
<!-- iamhoiend -->
