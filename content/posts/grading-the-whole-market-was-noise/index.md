---
title: "Maturity Grading Worked on Stocks. The Market? Pure Noise."
date: 2026-06-27T17:00:00+01:00
categories: [trading, tech-ai]
tags: [trading, backtesting, overfitting, market-regime, claude-code]
description: "I wanted to grade the whole market so I could size my risk to it. 30 hours in, the numbers looked great. Then the proof killed it."
---

<!-- iamhoi -->

I spent about 30 hours, pretty much non stop, trying to build one new market signal. Claude Code kept coming back with the same answer: fail, fail, fail. Then one time it thought it had something. So I pushed harder, made it prove the thing against slice after slice of my backtest data, and back it came. Negative again. More fail. Eventually we gave up.

Binned. The only thing I got out of those 30 hours is this blog and one lesson worth keeping.

Quick disclaimer: I am not a data scientist, none of this is trading advice, and all of it comes from a personal backtesting sandbox. Right, let's go.

## Why I wanted it in the first place

Here's the actual goal, because it matters. I don't just want to know which stock to buy. I want to know what the whole market is doing, so I can size my risk to it: when to be aggressive and size up, and when to pull the size back because the move is getting extended. If I could read the market's "state" the way I read a single stock, I'd know when to press and when to ease off. That was the original thought, and everything below was me chasing it.

And I had a head start. A few weeks back I finally cracked [a maturity grade for individual stocks](/posts/maturity-grading-from-backtest-data/): one letter, A to E, that reads where a stock is in its move (early, ripe, or cooked) across three timeframes, plus a cliff symbol for another performance measure. It took 7 days of ripping out a broken first attempt and rebuilding from the data, but it works. I trust it enough to read before I pull the trigger.

So the leap felt obvious. If I can grade a stock, why not grade the whole market the same way? QQQ tracks the Nasdaq-100, the big tech-heavy names, and I use it as my read on the market. Give it an A to E grade each week. Graded A means the market is hot, so size up. A dead E means it's quiet, so trim back. I even had a name for it: QQQM. The M is for maturity.

I was so sure. I'd just made it work on stocks. Same trick, one level up. How hard could it be?

## Mistake one: I built the screen first

Dumb bit first. Before I had a shred of proof the thing predicted anything, I designed the UI. A grade strip on the market page, a panel on my plan-trade screen, the lot. Rendered it, liked it.

Lesson, free of charge: prove the thing before you build the thing. I shouldn't have assumed up front that we'd crack it. That assumption is the only reason this cost me time and not money.

## I pointed the old logic at it. It failed hard

First I did the obvious thing. Took my working stock logic and aimed it at the QQQ index. If it grades a stock, it can grade an index, right? Wrong. It failed hard. Not "needs a tweak" failed. More "there is genuinely nothing here" failed.

So I went into experiment mode, and that's where most of the 30 hours went. Angle after angle. Slice the data one way, then another, bolt a fresh column onto years of weekly market history, check if it lines up with anything my trades actually did. So many ideas looked positive at first glance, and every time I did the same thing: push until it breaks. Most broke fast.

One didn't. Grade each week A to E by how much the market is moving. And I had a lot of history to test it against: every week of QQQ going right back to its launch in 1999, about 27 years of data. Line my trades up under each grade, and that one gave me a result so clean it nearly fooled me.

## The in-sample numbers looked great (and were a lie)

Here it is. Every trade in my history, sorted by the market's grade that week:

| market grade that week | avg reward (R) | win % |
|---|---:|---:|
| A | +1.34R | 64% |
| B | +0.64R | 52% |
| C | +0.28R | 43% |
| D | +0.20R | 41% |
| E | +0.15R | 41% |

(R is reward in units of what I risked, so +1.34R means I made 1.34 times my risk.)

Look at that. A clean drop from +1.34R at A down to +0.15R at E, in order. Nearly nine times the reward in a graded-A week than a graded-E one. I ran the proper maths on it, grouping by week instead of by trade so the numbers couldn't flatter themselves. It held. I re-ran it a thousand ways to check the A-to-E gap wasn't a fluke. Still held. Ran it on just my best trades. Same result, even stronger.

By every test I'd normally trust, "size up at A" looked proven. Claude said as much. But I didn't write it down as a win. Something felt off, and I couldn't tell you what.

That is the trap. An [AI hallucination](/posts/why-ai-hallucination-keeps-happening/) trap, that is!

## "Show me the proof"

That gut feeling is the only reason I didn't just take the win and move on. Human instinct saved me here. I'd been burned too many times by exactly this on the stock version: a great-looking in-sample result that turned out to be a coin flip. So I had a rule drilled in. A result this clean has to survive out-of-sample, tested on recent data that looks like now, not the long flattering history.

So I kept pushing. My words to Claude, more than once: prove it, show me the proof, build me an artifact with every metric and how you got there. I need to see it, not just hear it. Every positive number, we pushed on it until it held or it broke.

And it broke.

## Out of sample, it inverts or vanishes

First problem: in the recent window, the number of grade-A weeks that produced any trades was zero. Grade A is rare and clumps into a few scary years (2008, 2022), so the recent test simply had none of them. The whole "size up at A" pitch wasn't proven, it was untestable. Those are very different things.

Worse, the rest of it flipped. The low grades started beating the high ones, the exact opposite of the in-sample numbers. On the long history the top grade still came out ahead, but the clean order from A down to E was gone.

Then the money question: does sizing by grade beat just sizing flat? Head to head, across every slice of data I had. The result sat right across zero (anything that spans zero means "could be nothing"), and the entire so-called edge lived in one lucky stretch. Rejected.

Somewhere around here I typed: "it adds no fucking value."

## What survived was useless anyway

Two things did hold up. The grade is sticky (graded A this week, very likely A next). And it is direction-blind: a high grade reliably means a bigger move is coming, but it is a coin flip whether that move is up or down.

Sounds useful until you say it out loud. "The market is in a persistent, volatile state." I already know that. My market read is a dead-simple moving-average check, and it already tells me whether the gates are open or closed for trading entries. Knowing a storm is coming, with no idea which way and no repeatable edge on top, isn't a decision. It just repeats what I've got.

This is just noise. No consistent, predictable, repeatable pattern. It still felt random. Nothing here gives me a single thing the simple check doesn't already give me. So what's the point? There wasn't one. Predicting that the market will move is not the same as predicting you'll make money.

## The bit that actually matters

Notice what caught this. Not a unit test, every automated check went green. Not the AI, it had called it proven. It was me, refusing to take "proven" on the AI's word, or even my own, until it survived a fair out-of-sample fight.

That refusal is the whole job. Build with AI and it will hand you clean, confident results all day long. It is very good at producing something that looks right. It is much worse at doubting it. I run all this through my own [SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness), but even with all that in place, the AI is never the one that stops and says prove it. That has to come from me.

## What I kept

Nothing was wired into the live system, so there was nothing to unwind. I deleted the grade, scrapped the mockups, and went back to my boring moving-average regime. Open or closed. That's the whole market read I have actual evidence for, and after 30 hours trying to beat it with something cleverer, I trust the boring version more than ever.

If you want the longer version of how I learned to test like this, it's in [my overfitting tests](/posts/overfitting-tests-for-my-trading-system/). The [trading system itself](/posts/building-a-production-grade-trading-system-with-claude-code/) is what all of this protects.

## Was it a waste?

30 hours, half a week of my AI budget, and nothing to show for it. Waste?

Honestly, no. It re-proved on my own data that you can't predict where the market goes next. It caught a premature "it's proven" before it ever touched real money. And it talked me out of swapping a simple thing that works for a clever thing that doesn't. A clever signal you can't trust is worse than a dumb one you can.

The best looking numbers were the wrong ones. That is the whole lesson. If a result looks too good, make it prove itself before you believe a word of it.

Funny, not funny. On to the next one.

<!-- iamhoiend -->
