---
title: "The Market Wouldn't Tell Me When to Size Up. The Setup Did."
date: 2026-07-03T10:20:00+01:00
draft: false
categories: [trading, tech-ai]
tags: [position-sizing, risk-management, backtesting, maturity-grading, automated-trading, auto_pb]
description: "Grading the whole market to size my risk was noise. So I built a toggle that presses harder on the rare strong setups, with the brakes wired in first."
resources:
  - src: "shots/close/on.webp"
    title: "RISK-ADJUST ON: the toggle is lit (R2 1.25x band), so account risk goes 0.5% to 0.625% and the size steps up to 13 shares (base would be 10)."
  - src: "shots/close/off.webp"
    title: "RISK-ADJUST OFF: same setup, toggle off, back to base 0.5% and 10 shares. It still shows what it would size to."
  - src: "shots/close/not-met.webp"
    title: "Condition not met: the toggle is disabled and tells me why. Above the cliff, but stop-out 13.4% is over the 13% size-up band, so it stays at base (6 shares)."
  - src: "shots/full/on.webp"
    title: "Plan-trade page view with RISK-ADJUST ON."
  - src: "shots/full/off.webp"
    title: "Plan-trade page view with RISK-ADJUST OFF."
  - src: "shots/full/not-met.webp"
    title: "Plan-trade page view, condition not met."
---

<!-- iamhoi -->

The last post ended on an open question. I wanted to size my risk to the market. Press harder when the whole thing was strong, pull back when it was getting stretched. So I graded the whole market to find that signal. It was noise. (Binned. You can read the wreckage in [the market-grading post](/posts/grading-the-whole-market-was-noise/).)

But the question never went away. When do I press, and when do I ease off?

So I dropped down a level.

The market's mood was noise. The individual setup wasn't. Back in [the grading post](/posts/maturity-grading-from-backtest-data/) I built a grade for each stock's setup, A to E, off 938,680 backtested trades. The rare strong shapes held up on the held-out data (trades I kept aside to test on, never to build on). Above the cliff, which is just a gap in the numbers where the good setups have both higher reward and a lower stop-out rate. Top of the ranking. Those ones have real edge.

So instead of sizing to the market, size to the setup.

## The idea

Here is how I put it when I first asked for the feature:

> We need combinations of the highest ranking and above cliff because it gives us more edge and more risk control, therefore we should be more aggressive by increasing our position sizing.

More edge AND more risk control. That is the whole thing right there. The rare strong setups don't just win bigger. They stop out less often too. So sizing up on those isn't reckless. Done right, it's safer than a normal trade.

It's a toggle on my plan-trade page. A setup qualifies, the button lights up, I click it, and my position size goes up by a tier. Click again, back to base. Nothing auto-places. It's just the maths, sitting there, waiting for me to say yes.

I could work this out by hand on every trade. But I wanted it automated and consistent, human-in-the-loop, not me eyeballing the sizing differently depending on my mood. Same rules, every time.

> yes, I bless it because it is still manual, this is just a calculation as a toggle option if I choose to or not scale the size up.

Here is what that looks like on the actual page. The toggle on, the toggle off, and one that won't let me size up and tells me why. The blue box is the risk it works out, the coloured box is the toggle itself. Click any to zoom in.

{{< gallery folder="shots/close" >}}

And the same three states, the wider page view:

{{< gallery folder="shots/full" >}}

## What gets sized up

My base account risk is 0.5% per trade (max 10 positions, so my total account risk sits around 5%, give or take, because gap-downs may bypass the stop-loss order). The ladder picks the multiplier off the setup's historical stop-out rate (how often that shape hit its stop in the backtest). Lower stop-out, more size.

| Setup | Historical stop-out | Size |
|---|---|---|
| Above the cliff, elite band | up to 7% | 2.0x |
| Above the cliff | 7 to 13% | 1.25x |
| Top-ten ranked, no cliff | up to 7% | 1.5x |
| Top-ten ranked, no cliff | 7 to 13% | 1.25x |
| Everything else | over 13% | base, no toggle |

Two lanes. Above the cliff is the strong one, and it earns the full 2x on the elite band. Not above the cliff but still top-ten ranked gets a smaller bump. Everything else stays at base risk, no toggle.

## What stops it

This is the bit that matters. Because what hurts most is sizing up and then getting stopped out. It's painful and it's damaging to the account. So the brakes went in first, before anything else.

| The brake | What it does |
|---|---|
| Stop-out over 20% | never sizes up, full stop |
| Fewer than 30 trades | no size-up, not enough evidence to trust |
| Rank-only lane | needs at least 50 trades |
| Thin sample, under 100 trades | multiplier capped at 1.5x |
| Absolute ceiling | never more than 2% of the account, whatever the maths says |
| Timeframe | weekly and daily setups only |

## Why 2x is still safe

This is the table that makes the whole case. The elite weekly setups stopped out around 5.6 to 6.9% of the time on the held-out data. A normal trade stops out around 22.8%.

| | Normal trade | Elite setup, sized 2x |
|---|---|---|
| Account risk | 0.5% | 1.0% |
| Historical stop-out | ~22.8% | ~5.6 to 6.9% |
| Expected loss to stops | ~0.114% per trade | ~0.085% per trade |

Read the bottom row. Double the size on the elite setup and I still bleed less per trade to stops than I do on a normal trade, because the setup stops out about a third as often. That is what "more edge and more risk control" actually looks like once you put numbers on it.

(These are held-out backtest figures, not live money. Fingers crossed on the real trades. I've learned to say that part out loud.)

## After so many refactors

It didn't land clean. Two rebuilds got it there.

First one: the sizing multiplier was reading a frozen snapshot of the validation data. Pinned to an old picture. I didn't like it.

> we created current so that it adapts to the changing stock market which no one really knows other than the data driven. Using fixed, means it will be wrong in the future.

The whole reason I built the adaptive version was to keep up with a market nobody can predict. Freezing the sizing to an old snapshot throws that away. So now it reads the live numbers when there are enough of them, and only falls back to the frozen ones when the live sample is too thin to trust. Keep it real, don't overfit.

Second one: I found a dead toggle. Live, on a real stock. The button lit up ON, and my size went from 0.5% to 0.5%. Nothing happened. A one-times multiplier is not a size-up.

> having 1x behavior is weird. so why would we still have a toggle? it doesn't make sense.

Killed it. If it can't size up, no toggle. Then I pushed it further. Don't just hide the toggle, tell me why. Otherwise I stare at a setup that's above the cliff, ranked, everything looking green, and I sit there wondering why it isn't sizing up. Now it spells it out:

> ★9 above the cliff, but stop-out 13.4% is above the 13% size-up band, no size-up.

Strong setup. It just stops out a touch too often to earn the extra size. I know that at a glance now, instead of guessing.

(All of this, on live-trading code, without breaking the running system, went through my [SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness). Built, reviewed, regression-gated before a single line shipped.)

## Where it leaves me

The market wouldn't tell me when to press. That was noise. The setup does, and I proved that part before I built anything on top of it. The sizer doesn't trade for me. It does the maths when one of the rare strong ones shows up, lights the button, and waits for me to click.

Done. For now lol...

<!-- iamhoiend -->
