# Social posts - Stephen the Real Diehl

Paste-ready social copy for AGIT feature #2, one labelled block per channel. This
file does not publish (it is a Hugo bundle resource, not a page); it is the
cheat-sheet for posting.

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

A cap is a CEILING for one bucket, never a TARGET for all of them. Each copy fence
below is labelled with its type and its exact length, and `agit_social_post.py`
refuses to post on any mismatch.

**The first comment is not optional.** The copy ends "See comment for full story.",
which is a promise only the Source comment keeps. On the three automated channels
Postiz posts it for you, on the same call, as the child of the post. The MANUAL
group channels below get the Source inline instead, because group posts do not get
the same first-comment treatment.

Every string below sits in a fenced block, so the markdownlint pre-commit hook
cannot reword post copy. All copy is derived from the approved wording of the
feature page and adds no claim that is not already on it. It is written in the
third person because AGIT is introducing him: the first person on the page is his,
and what he approved was that page, not this copy.

## Images: which file goes on which channel

Both images sit in this folder beside this file. They are different shapes on
purpose (see the design spec in `agit-featured/SKILL.md`), so they are not
interchangeable:

| File | Size | Shape | Use it on |
|---|---|---|---|
| `share-card.png` | 1200x630 | landscape | Facebook Page, Bluesky, X, LinkedIn Group, Facebook Group, Substack |
| `hero.jpg` | 1080x1350 | portrait | Instagram ONLY |

**Every post gets an image.** A feed post with no image gets a fraction of the
reach, and the landscape card is what the link-preview slot expects. Instagram is
the only channel that takes the portrait crop, and the only one that will REJECT a
text-only post outright.

The raw submission photo is never used anywhere. These two files are generated
artwork.

Feature link (the Source, used in the first comment on every post):

```text
https://hoiboy.uk/community/agit-featured/2-stephen-the-real-diehl-software-engineer-and-sometimes-more/
```

Hashtag core set:

```text
#AsiansInTech #GingersInTech #AGIT #FunctionalProgramming #Compilers
```

## Automated (Postiz)

Facebook Page, Instagram and Bluesky are fanned out by the Postiz deployment in the
agit-social repo. That repo's deploy/CHANNELS.md is the canonical channel split.

### Facebook Page

**Image:** `share-card.png` (1200x630 landscape).

Post (summary, 1523 chars):

```text
Meet Stephen!

A software nerd in London. By day he works in financial markets, doing the mathy, formal methods things at the frontiers of electronic markets.

In his spare time he builds programming languages. Not for a company, not for a deadline, just because he cannot leave certain problems alone. His current one is called Prism, a small functional language with algebraic effects, which he admits is the sort of sentence that clears a dinner party in seconds.

The short version is this. Most languages let side effects roam free, printing and mutating and throwing wherever they like, and then act surprised when the program misbehaves. Prism writes it all down. It tracks what a function actually does, not what it claims to do.

The part he is quietly proud of is subtle enough that almost nobody notices it, which is exactly why he loves it. If a function throws an error internally and catches it before anyone sees, Prism treats that function as pure. The mess is real, but it is private, so the type system forgives it. Effects that never escape simply vanish from the signature. It took an embarrassing number of evenings to make that work, and the reward is a compiler that stays silent.

Away from the compiler he reads novels, and then he reviews them. A good novel and a good type system have more in common than people expect. Both are built from constraints. Both fall apart the moment an author cheats.

See comment for full story.

#AsiansInTech #GingersInTech #AGIT #FunctionalProgramming #Compilers
```

First comment:

```text
Source: https://hoiboy.uk/community/agit-featured/2-stephen-the-real-diehl-software-engineer-and-sometimes-more/
```

### Instagram

**Image:** `hero.jpg` (1080x1350 portrait). REQUIRED. Instagram rejects a text-only
post. It is the only channel taking the portrait crop; the landscape card is wrong
here.

Caption (summary, 1523 chars):

```text
Meet Stephen!

A software nerd in London. By day he works in financial markets, doing the mathy, formal methods things at the frontiers of electronic markets.

In his spare time he builds programming languages. Not for a company, not for a deadline, just because he cannot leave certain problems alone. His current one is called Prism, a small functional language with algebraic effects, which he admits is the sort of sentence that clears a dinner party in seconds.

The short version is this. Most languages let side effects roam free, printing and mutating and throwing wherever they like, and then act surprised when the program misbehaves. Prism writes it all down. It tracks what a function actually does, not what it claims to do.

The part he is quietly proud of is subtle enough that almost nobody notices it, which is exactly why he loves it. If a function throws an error internally and catches it before anyone sees, Prism treats that function as pure. The mess is real, but it is private, so the type system forgives it. Effects that never escape simply vanish from the signature. It took an embarrassing number of evenings to make that work, and the reward is a compiler that stays silent.

Away from the compiler he reads novels, and then he reviews them. A good novel and a good type system have more in common than people expect. Both are built from constraints. Both fall apart the moment an author cheats.

See comment for full story.

#AsiansInTech #GingersInTech #AGIT #FunctionalProgramming #Compilers
```

First comment:

```text
Source: https://hoiboy.uk/community/agit-featured/2-stephen-the-real-diehl-software-engineer-and-sometimes-more/
```

### Bluesky

**Image:** `share-card.png` (1200x630 landscape).

The super short summary, inside Bluesky's 300-character cap.

Post (super short, 274 chars):

```text
Meet Stephen!

A London software nerd who builds programming languages in his spare time. His own, Prism, tracks what a function does, not what it claims to. Effects that never escape vanish from the signature.

See comment for full story. #AsiansInTech #GingersInTech #AGIT
```

First comment:

```text
Source: https://hoiboy.uk/community/agit-featured/2-stephen-the-real-diehl-software-engineer-and-sometimes-more/
```

## MANUAL (operator posts these by hand)

X and TikTok are deferred to manual by operator decision 2026-07-24. Facebook Group,
LinkedIn Group and Substack have no posting API at all. Nothing here automates any
of them. Meetup is not a feature channel: it is the events surface.

### X

**Image:** `share-card.png` (1200x630 landscape).

MANUAL. The super short summary: 280 characters including the hashtags.

Post (super short, 274 chars):

```text
Meet Stephen!

A London software nerd who builds programming languages in his spare time. His own, Prism, tracks what a function does, not what it claims to. Effects that never escape vanish from the signature.

See comment for full story. #AsiansInTech #GingersInTech #AGIT
```

First comment:

```text
Source: https://hoiboy.uk/community/agit-featured/2-stephen-the-real-diehl-software-engineer-and-sometimes-more/
```

### TikTok

MANUAL. Video-first, so this feature runs only if a clip exists. There is no
still-image path worth using here, and public posting would need the
Content-Posting audit anyway.

### LinkedIn Group

**Image:** `share-card.png` (1200x630 landscape).

MANUAL. The summary, inside LinkedIn's 3000-character cap. Groups have no API, and
there is no AGIT Page. Group posts do not get the same first-comment treatment, so
the Source goes inline instead:

Post (summary, 1612 chars):

```text
Meet Stephen!

A software nerd in London. By day he works in financial markets, doing the mathy, formal methods things at the frontiers of electronic markets.

In his spare time he builds programming languages. Not for a company, not for a deadline, just because he cannot leave certain problems alone. His current one is called Prism, a small functional language with algebraic effects, which he admits is the sort of sentence that clears a dinner party in seconds.

The short version is this. Most languages let side effects roam free, printing and mutating and throwing wherever they like, and then act surprised when the program misbehaves. Prism writes it all down. It tracks what a function actually does, not what it claims to do.

The part he is quietly proud of is subtle enough that almost nobody notices it, which is exactly why he loves it. If a function throws an error internally and catches it before anyone sees, Prism treats that function as pure. The mess is real, but it is private, so the type system forgives it. Effects that never escape simply vanish from the signature. It took an embarrassing number of evenings to make that work, and the reward is a compiler that stays silent.

Away from the compiler he reads novels, and then he reviews them. A good novel and a good type system have more in common than people expect. Both are built from constraints. Both fall apart the moment an author cheats.

Full story: https://hoiboy.uk/community/agit-featured/2-stephen-the-real-diehl-software-engineer-and-sometimes-more/

#AsiansInTech #GingersInTech #AGIT #FunctionalProgramming #Compilers
```

### Facebook Group

**Image:** `share-card.png` (1200x630 landscape).

MANUAL. The summary, well inside Facebook's 63206-character cap. No posting API,
and distinct from the automated Facebook Page. Groups get no first comment, so the
Source goes inline:

Post (summary, 1612 chars):

```text
Meet Stephen!

A software nerd in London. By day he works in financial markets, doing the mathy, formal methods things at the frontiers of electronic markets.

In his spare time he builds programming languages. Not for a company, not for a deadline, just because he cannot leave certain problems alone. His current one is called Prism, a small functional language with algebraic effects, which he admits is the sort of sentence that clears a dinner party in seconds.

The short version is this. Most languages let side effects roam free, printing and mutating and throwing wherever they like, and then act surprised when the program misbehaves. Prism writes it all down. It tracks what a function actually does, not what it claims to do.

The part he is quietly proud of is subtle enough that almost nobody notices it, which is exactly why he loves it. If a function throws an error internally and catches it before anyone sees, Prism treats that function as pure. The mess is real, but it is private, so the type system forgives it. Effects that never escape simply vanish from the signature. It took an embarrassing number of evenings to make that work, and the reward is a compiler that stays silent.

Away from the compiler he reads novels, and then he reviews them. A good novel and a good type system have more in common than people expect. Both are built from constraints. Both fall apart the moment an author cheats.

Full story: https://hoiboy.uk/community/agit-featured/2-stephen-the-real-diehl-software-engineer-and-sometimes-more/

#AsiansInTech #GingersInTech #AGIT #FunctionalProgramming #Compilers
```

### Substack

**Image:** `share-card.png` (1200x630 landscape).

MANUAL. The summary. No posting API, and Substack publishes no Note character
limit, so the length gate does not apply. Runs as a Note rather than an issue of
the newsletter, with the Source inline:

Post (summary, 1612 chars):

```text
Meet Stephen!

A software nerd in London. By day he works in financial markets, doing the mathy, formal methods things at the frontiers of electronic markets.

In his spare time he builds programming languages. Not for a company, not for a deadline, just because he cannot leave certain problems alone. His current one is called Prism, a small functional language with algebraic effects, which he admits is the sort of sentence that clears a dinner party in seconds.

The short version is this. Most languages let side effects roam free, printing and mutating and throwing wherever they like, and then act surprised when the program misbehaves. Prism writes it all down. It tracks what a function actually does, not what it claims to do.

The part he is quietly proud of is subtle enough that almost nobody notices it, which is exactly why he loves it. If a function throws an error internally and catches it before anyone sees, Prism treats that function as pure. The mess is real, but it is private, so the type system forgives it. Effects that never escape simply vanish from the signature. It took an embarrassing number of evenings to make that work, and the reward is a compiler that stays silent.

Away from the compiler he reads novels, and then he reviews them. A good novel and a good type system have more in common than people expect. Both are built from constraints. Both fall apart the moment an author cheats.

Full story: https://hoiboy.uk/community/agit-featured/2-stephen-the-real-diehl-software-engineer-and-sometimes-more/

#AsiansInTech #GingersInTech #AGIT #FunctionalProgramming #Compilers
```
