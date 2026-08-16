---
title: "#2 Stephen the Real Diehl"
date: 2026-08-04T10:00:00+01:00
description: "A London software engineer who builds programming languages in his spare time, including a functional language called Prism that tracks what code really does."
role: "Software Engineer (and sometimes more!)"
breadcrumbParent: "/community/agit-featured"
hideDate: true
---

Hi I'm Stephen. 👋 I'm a software nerd in London. By day I work in financial markets, doing lots of fun mathy and formal methods things at the frontiers of electronic markets.

**Superpowers:** formal methods, compilers, functional programming.

**Current role:** Software Engineer (and sometimes more!).

**What I quietly did:** I also build programming languages. Not for a company, not for a deadline, just because I cannot leave certain problems alone. My current one is called Prism. It is a small functional language with algebraic effects, which is the sort of sentence that clears a dinner party in seconds. The short version is this. Most languages let side effects roam free, printing and mutating and throwing wherever they like, and then act surprised when the program misbehaves. Prism writes it all down. It tracks what a function actually does, not what it claims to do, using a thing called row polymorphism that I promise is more fun than it sounds.

The part I am quietly proud of is subtle enough that almost nobody notices it, which is exactly why I love it. If a function throws an error internally and catches it before anyone sees, Prism treats that function as pure. The mess is real, but it is private, so the type system forgives it. Effects that never escape simply vanish from the signature. It took me an embarrassing number of evenings to make that work, and the reward is a compiler that stays silent. This is a very cool idea at the frontiers of computer science.

**The flex, nothing to do with tech:** when I am not arguing with continuations I read novels, and then I review them. A good novel and a good type system have more in common than people expect. Both are built from constraints. Both fall apart the moment an author cheats. I have learned to spot a plot hole and a leaky abstraction with the same instinct, and I distrust anything, book or language, that asks me to just trust it.

**The identity bit:** the truest thing about me is not on any repository. I am married to my wonderful wife, and soon have a daughter, and she will have no idea that her father spends his spare hours teaching a machine the difference between what it does and what it says. But one day I will teach her Lean 4 and algebraic effects so she can speak to our Machine Overminds directly instead of going through the inefficiencies of language.

So that is me. I'm completely normal obviously.

**Follow me**

- Website: [stephendiehl.com](https://www.stephendiehl.com)
- GitHub: [github.com/sdiehl](https://github.com/sdiehl)
