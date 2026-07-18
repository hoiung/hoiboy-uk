---
title: "Market Breadth, Market Condition Signals, and Market Regime"
date: 2026-07-17T00:30:00+01:00
categories: ["trading", "tech-ai"]
tags: ["market-breadth", "t2108", "stockbee", "macd", "price-volume-action", "market-regime", "qqq", "tc2000", "swing-trading", "human-in-the-loop"]
description: "Six months of studying the QQQ turned into three tools: a breadth gauge, a weekly human check, and an automated gate that blocks my trades when the market turns."
---

<!-- iamhoi -->

Before I automated anything, I spent a good 6 months just studying the market. No code, no system yet, just me and the charts.

Everything I came up with came out of watching one thing: the QQQ, my market monitor. It turned into three separate angles, and this post walks through all three. If you want the engineering side of how the platform itself got built, [that story is over here](/posts/building-a-production-grade-trading-system-with-claude-code/). This one is about the studying that came first. And when studying each one, I also studied hundreds of stocks alongside it, to understand their movement over time together with the QQQ's, across multiple timeframes. Hence why the study took 6 months and not 6 days!

## 1) Market Breadth using T2108 % (Daily timeframe)

The original idea came from Stockbee: the T2108, the percentage of stocks trading above their 40-day moving average. Think of it as a headcount. When most stocks are above that line, the market is broadly healthy. When the number falls away, the move is being carried by fewer and fewer names, even while the index itself still looks fine. I still use it today, but on the daily timeframe only.

I ran it against years of QQQ price history to see where it actually mattered. On the screenshot below, the T2108 is the blue area up top. The dashed lines are mine, marking the levels where, again and again, it tends to bounce off support or stall at resistance.

{{< zoom-image src="t2108-breadth-daily.webp" alt="TC2000 daily chart: the T2108 breadth indicator as a blue area on top with dashed support and resistance levels marked, QQQ daily candles with moving average lines in the middle, and dollar volume at the bottom" title="T2108 % market breadth (blue area) with my marked support and resistance levels, above the QQQ daily" >}}

## 2) QQQ Price Volume Action (PVA) + MACD signals (Weekly timeframe)

Next, based on my studies and experiments, I wrote two simple formulas of my own for price volume action (PVA). Really just price measured against the previous bar, and dollar volume ($vol) against the previous bar. Later I laid standard MACD settings on top, to see whether the two lined up. Here is what I landed on:

bullish ⍙ C>H1 and $V>$V1 is true, AND MACD just crossed up ⤯ (early, not late), or curling up ◡ (market reversing). Stronger on a confirmed bullish PVA.

bearish ⍙ C<L1 and $V>$V1 is true, AND (after an extended cross) MACD curling over at the top ⌒, or just crossed down ⤰ (early, not late). Worse on a second confirmed bearish PVA, market breaking down.

I studied the PVA on its own first and mapped out my own reading of it, then added the MACD layer. The thing I kept noticing: you have to read them together, not on their own. Either one on its own throws too many false signals. Together, they filter each other.

{{< zoom-image src="pva-macd-weekly-2023-2026.webp" alt="TC2000 weekly QQQ chart from 2023 to 2026 with the MACD pane on top and my hand-written study notes marking pullback legs, bounces off moving averages, weak re-tests, and fake-out signals" title="The weekly PVA + MACD study on the current period (2023-2026), with my notes on every pullback and re-test" >}}

{{< zoom-image src="pva-macd-weekly-2020-2024.webp" alt="TC2000 weekly QQQ chart from 2020 to 2024 covering the 2022 bear market, annotated with the 57-week pullback of 4 legs, failed bounces, and the double doji re-test that marked the turn back to bullish" title="The same study on the 2022 bear market: 57 weeks, 4 legs of pullback, and the re-test that finally confirmed the bounce" >}}

{{< zoom-image src="pva-macd-weekly-2018-2022.webp" alt="TC2000 weekly QQQ chart from 2018 to 2022 covering the COVID crash, annotated with bear re-tests, MACD crossing signals, and the note that a steep pullback usually means a harder bounce" title="And on the COVID crash era (2018-2022): steep pullback, harder bounce" >}}

## 3) Market Regime: QQQ MA lines (Weekly + Daily timeframe combined)

This is the one I actually wired into the automated system, as a simple ON/OFF gate that either lets me trade or blocks me.

It all came out of manual studying on TC2000. If you look back at the earlier charts you will spot a lot of different moving average lines. I added and removed those constantly, going right back through the whole of QQQ's history, just to see where price tends to bounce and where it runs into resistance. This is the final set I settled on:

- MA200, MA150, MA100 (MA = simple moving average)
- ema50, ema20, ema10 (ema = exponential moving average)
- FWMA50, FWMA20, FWMA10 (FWMA = forward weighted moving average)

Then I tested it across the daily and the weekly, looking at the two side by side. The monthly I dropped, because over the bigger periods it barely ever bounces, so it added nothing. Daily and weekly together told me what I needed, and that was good enough to turn into a rule.

Here is the actual algorithm for the OPEN and CLOSED regime. On the plan-trade page, my system blocks any new trade while the regime is CLOSED, though I have left myself a manual override for when I'm feeling risky on a bounce.

```text
daily:   Price > EMA50 = OPEN | Price <= EMA50 = CLOSED
weekly:  EMA20 > EMA50 = OPEN | EMA20 <= EMA50 = CLOSED
monthly: (inherits weekly)
```

{{< zoom-image src="market-regime-qqq-dashboard.png" alt="My trading dashboard's QQQ market chart page: weekly, monthly and daily candle panes with the SMA, EMA and FWMA line toggles, and the QQQ OPEN Only panel on the right spelling out the daily and weekly regime rules" title="The regime live on my dashboard: the QQQ page, with the OPEN/CLOSED rules spelled out on the right" >}}

The best part of doing it this way: those white and red regime candles show up on every chart in my system, not just the QQQ. TC2000 can't do that. It is not timeframe agnostic, so it can't combine a daily and a weekly formula into one signal. Sucks, but that's just how it is.

{{< zoom-image src="market-regime-tsla-overlay.png" alt="The same dashboard on a TSLA ticker page: the QQQ regime candle colouring overlaid on TSLA's weekly, monthly and daily charts, so the market state is visible on any ticker" title="The same regime colouring carried onto any ticker's chart, TSLA here, not just the QQQ" >}}

## Final words

Just remember, there is no golden signal. Nobody actually knows what the market will do next. What we can do is take everything we understand and make a decent guess at where it might head, for the next bet. That is what all those months of studying are really for. It is never a guarantee.

I fine-tuned some of this through study, yes. But honestly, most of what I learned came from losing money when a bet went wrong, then going back over the market conditions afterwards to work out what I missed. That is what builds the intuition, the feel you get from staring at all this information that no algorithm could easily calculate. And I'm deliberately trying not to overengineer it.

That is exactly why angle number 2, the PVA + MACD read, is built as a human in the loop check (HITL, a step the system will not let me skip). There are too many nuances in it to hand cleanly to an algorithm, so I keep myself in the loop. (If you want the longer story of how I got into any of this, it is in [my baby steps to becoming a professional trader](/posts/my-baby-steps-to-becoming-a-professional-trader/).)

And here is that latest human in the loop design, live on my plan-trade page (built with Claude Code under my [SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness) workflow, same as the rest of the platform). It reminds me what I am looking for, tells me to go and review my study notes, and makes me tick the box before it will let me place an order. I've forgotten this step too many times and paid for it lol. So dumb right? Hence why I built it into the workflow, permanently.

{{< zoom-image src="plan-trade-hitl-gate.png" alt="The plan-trade page with the market regime showing CLOSED, a red banner saying new positions are blocked, the TC2000 QQQ Weekly PVA + MACD human check panel with the bullish and bearish rules, and the unticked attestation checkbox next to a disabled Place Order button" title="The HITL gate on plan-trade: regime CLOSED, the PVA + MACD reminder, and the checkbox I have to tick before Place Order unlocks" >}}

<!-- iamhoiend -->
