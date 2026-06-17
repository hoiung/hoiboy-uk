---
title: "The Tech Stack I Use to Build an Automated Trading System"
date: 2026-06-17T12:25:00+01:00
draft: false
categories: [tech-ai, trading]
tags: [automated-trading, python, rust, system-architecture, interactive-brokers]
description: "A plain-English tour of the data providers, languages, libraries and tools behind my automated swing-trading system, and why the dependable option usually won."
---

<!-- iamhoi -->

I recently gave a talk to the London Investments and Traders Group. Afterwards I ended up in a few smaller chats with other techies, and the same question kept coming back: what did you actually use to build the thing? What data providers, what languages, what libraries, what tools?

So here it is. The parts list.

If you want the story of how it all came together (the crashes, the rebuilds, the things I broke and then had to fix), that one already exists: [building a production-grade trading system](/posts/building-a-production-grade-trading-system-with-claude-code/). This post is just the breakdown. What each piece is, and what it's there for.

## AI tooling

[Claude Code](https://www.anthropic.com/claude-code) by Anthropic, on the Max 20x subscription (it gets difficult with anything less than the 20x usage limit).

One thing up front. I don't hand-write the code, but I can read it well enough since it's not new to me. I am the technical architect. I created the design intent for every component and module, made the calls on what goes where and how the internal parts of the system work together, and directed Claude Code to build it under my own [SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness). I'm the product owner and the engineering lead. The AI is the one typing, the one I'm swearing at and fighting most of the time to keep it focused on the goal at hand.

## The shape of it

Here's the whole thing on one page. Don't worry about the detail yet, we'll walk each block in turn. The gist: market data comes in on one side, gets cleaned up and cached in the middle, and the trading logic sits on the other side talking to the broker.

{{< zoom-image src="system-overview.svg" alt="System overview: market data providers and the broker feed into a Rust data service, which caches prices and streams them to a Python dashboard and paper and live controllers, all backed by a PostgreSQL database; only the controllers place orders with the broker." title="The whole system on one page" >}}

Two languages do the work. [Python](https://www.python.org) for crunching the numbers and most of the heavy lifting, [Rust](https://www.rust-lang.org) for the always-on data plumbing. Everything else is a library or a service hanging off those two.

{{< zoom-image src="language-split.svg" alt="The stack split by language: Python owns the dashboard, backtester and controllers; Rust owns the data services and redundancy managers; PostgreSQL and Redis are the shared storage and messaging layer." title="Who's written in what" >}}

Truth be told, I'd have happily built the whole thing in Rust, or in Go (it was close to a coin flip between the two), if the libraries had been there. What kept the rest on Python was exactly that: the serious data-science tools just aren't mature in Rust or Go yet. So the number-crunching stays where the libraries already live.

## PostgreSQL: the memory

Everything the system knows lives in [PostgreSQL](https://www.postgresql.org). Price history, every backtest I've ever run, the trades, the metrics, the live state of the running system. It's a plain relational database (rows and tables, like a very serious spreadsheet) and it's the single source of truth. If it isn't in the database, it didn't happen.

## Redis: fast cache on RAM

If PostgreSQL is the long memory, [Redis](https://redis.io) is the short one. It's an in-memory store (everything sits in RAM instead of on disk, so a read comes back in a fraction of a millisecond) that the programs use to pass data to each other, which is great for streaming the same data out to several apps at once. The Rust side writes the latest prices into it, the Python side reads them straight back, and nobody has to go round-tripping to the database for a number they need many times a second. It's also where the parts of the system leave each other quick messages. Everything in here is disposable and most of it expires on a timer, so a stale price can't sit there pretending to be live. Wipe it and the system just rebuilds it from the database. The real record is never in Redis. It's the standard, proven tool for this job, so it was an easy call.

## Python: the muscle

Most of the day-to-day work is Python. Four bits matter here.

**Talking to the database.** Python reaches PostgreSQL through [psycopg3](https://www.psycopg.org) (the Postgres driver for Python). Nothing fancy, it's just the wire between the code and the data.

**The dashboard.** The screen I actually look at is a [React](https://react.dev) app, built with [Vite](https://vite.dev), with the charts drawn by [lightweight-charts](https://github.com/tradingview/lightweight-charts) (TradingView's free charting library). The back end serving it is [FastAPI](https://fastapi.tiangolo.com). It's look-and-command only: it shows me what's going on and lets me fire off actions, but it never touches the broker itself. More on why in a minute.

**The backtester.** Before any strategy goes near real money, it gets tested against years of history. That runs on [vectorbt](https://github.com/polakowo/vectorbt) (a fast backtesting library) with [ta-lib](https://github.com/TA-Lib/ta-lib-python) for the standard indicators. A few "smart layers" sit in front of it to work out sensible settings for each stock, then vectorbt simulates the trades and the result gets a score. There are more than a thousand stocks to test, so the runs don't all fire at once. They get queued and worked through in batches, several at a time across multiple CPU cores, with the price data loaded once and shared across each batch. It's the difference between a run that finishes in good time and one that falls over halfway through because it tried to do everything at once and ran out of memory.

{{< zoom-image src="backtest-pipeline.svg" alt="The backtest pipeline: historical price data feeds smart layers that tune settings per stock, which feed the vectorbt engine that simulates trades, which produces a graded result stored in the database." title="How a backtest runs" >}}

**The controllers.** Two near-identical programs do the live work: a paper one (fake money, for testing) and a live one (real money). They watch my open positions, follow each position's plan (nudge the stop, take some profit, get out when it's time), and place the orders. The live one runs at a higher priority than everything else because, well... real money.

## Rust: the always-on plumbing

The market-data side runs on Rust, because it has to be fast and it cannot fall over while the market's open. I didn't just take that on faith. I built both the data services and the redundancy managers in Python and in Rust, ran the two side by side as a hot-standby pair, and swapped which one was live every day so the test was fair. Rust won, and not by a little. It ran for weeks without falling over, and when it did need restarting it was back in under a tenth of a second, where the Python apps have to reload their whole data-science toolbox first and take several times longer. For services that have to stay up while the market is open, that is the difference between a blink and a real outage. So I deleted the Python side, around seven thousand lines of it, and went Rust-only (the Rust that replaced it came out about twice the size, funnily enough, because Rust makes you spell everything out). Two kinds of program live here.

**Data Services.** These own every connection to the outside world: the price feeds and the broker's live quote stream. They pull prices in, sanity-check them (one bad tick can do real damage), cache them, and push them out to everything else as a live stream. Two copies run at all times, one active and one warm spare.

**Redundancy Managers.** These are the babysitters. Their whole job is to make sure exactly one Data Service is live at any moment, keep checking it's healthy, and if it stumbles, flip over to the spare without me lifting a finger. Belt and braces. They come as a pair too, so even the babysitter is babysat by its counterpart, and the two swap the leader and warm-standby roles between them if they need to.

{{< zoom-image src="redundancy.svg" alt="The redundancy setup: a pair of redundancy managers watch a pair of data services, keep exactly one active and one on warm standby, and automatically fail over to the spare if the active one becomes unhealthy." title="Staying up when things break" >}}

## The broker: Interactive Brokers

The orders go to a real broker, [Interactive Brokers](https://www.interactivebrokers.com), through their gateway software. The split here is the important bit, and it's on purpose:

- Prices come **in** through the Rust Data Service.
- Orders go **out** only through the controllers.

The dashboard has zero connection to the broker. It can ask the controllers to do something, but it cannot place a trade on its own. One door in, one door out, and the screen a human pokes at is neither of them. The thing you click should never be the thing that can fire a live order.

{{< zoom-image src="broker-split.svg" alt="The broker split: market data flows in from Interactive Brokers to the Rust data service, while orders flow out only from the controllers to Interactive Brokers; the dashboard has no broker connection at all." title="One door in, one door out" >}}

The hardest part was making the connection reliable and stable without breaking. The Interactive Brokers API is shit. It hangs, it drops the connection, and it throws back errors so cryptic you need a translation layer just to work out what went wrong. We tried the official Python client and the most popular one on GitHub, and they both fell over, something we needed always broke. So a big chunk of the work was the scaffolding around it: reconnection logic, a map of every error code and what to do about each one, an order-safety gate, and a reconciliation pass that checks the broker's reality against my own records every time it reconnects. On the Rust side, the obvious library deadlocked, so I swapped it for a sturdier one. Unglamorous work, all of it. It's also the difference between a system you can trust with real money and one you can't.

A couple of practical notes. The automation runs on IB Gateway, the headless version of their software, with a tool called [IBC](https://github.com/IbcAlpha/IBC) handling the logins so it can let itself back in after IBKR's nightly restarts (that part I'm still wiring up...). I keep the full Trader Workstation app around too, but only as a window to watch with my own eyes, its trading connection switched off so it can't get in the way. And the only things actually resting at the broker are the entry and one full-size stop. The profit-taking isn't parked there waiting to fire, the controller watches the price and banks it in real time, so the logic for when to take a win lives in my code, not theirs.

## The data feeds

Three providers, used in a set order.

For the live system, prices come from [Finnhub](https://finnhub.io) first. If Finnhub has a wobble, [Alpha Vantage](https://www.alphavantage.co) picks up the slack. Both of them down? [yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance's data) catches the fall. Three tiers, so one feed going dark doesn't leave the system blind.

For backtesting it's simpler: yfinance only. It's free, it's good enough for years of history, and I checked it against well over a hundred stocks from TC2000 before I trusted it with anything.

{{< zoom-image src="data-tiering.svg" alt="Data provider tiering: the live system tries Finnhub first, falls back to Alpha Vantage, then to yfinance; backtests use yfinance only, cached temporarily for performance." title="Three feeds for the live system, one for backtests" >}}

## The machine it all runs on

All of this sits on a single mini PC, a Minisforum NAD9: an Intel i9 with 14 cores, 64GB of memory and a 2TB NVMe drive. It runs Windows 11, with the real system living inside [WSL](https://learn.microsoft.com/en-us/windows/wsl/) (Windows Subsystem for Linux, which is a proper Linux running right alongside Windows). Linux runs the database and the services, Windows runs the broker software, and a small bridge lets the two talk. No server rack, no cloud bill. The whole thing, backtesting a thousand-plus stocks and trading live, runs off one little box on a desk.

It barely breaks a sweat most of the time. The live trading side is tiny, the Rust data service sits on about 22MB of memory. The database is the greedy one, and only because I told it to be: it reserves 16GB, a quarter of the box, as cache so queries stay quick. The hungry job is backtesting, and that one I keep on a leash. Each test holds about half a gig while it runs, so the system works out how many it can run at once inside a memory budget and throttles itself, only ever taking a slice of the cores rather than choking the whole machine. Worker counts, cache size, the memory budget, it's all config I can dial up or down. The trading data itself is small. It's the backtest results that pile up, and those I can always regenerate.

## The safety nets

A couple of things that never show up on screen but matter more than the flashy parts.

**Logging.** Both sides keep detailed logs ([loguru](https://github.com/Delgan/loguru) on the Python side, [tracing](https://github.com/tokio-rs/tracing) on the Rust side), so when something misbehaves I can see exactly what happened and when, instead of guessing. If you want the longer version of why I care about this, there's a whole post on it: [Observability, You Can't Fix What You Can't See](/posts/observability-and-logging-for-production-systems/).

**A watchdog.** Every process has to check in on a timer. If one goes quiet, the operating system restarts it on its own. Between that and the redundancy managers, the system is built to pick itself back up without me sitting there watching it.

## That's the kit

That's the lot. PostgreSQL holding everything, Redis keeping it fast, Python doing the heavy lifting, Rust keeping the data flowing, Interactive Brokers taking the orders, three data feeds for backup, all on one box.

I didn't pick any of this to look clever. Each piece is there because it does a job the others couldn't, and the boring, dependable option usually won. The interesting part was never the tools anyway. It was deciding what talks to what, and what is allowed to touch real money.

If you want the how-it-got-built story instead of the parts list, [it's over here](/posts/building-a-production-grade-trading-system-with-claude-code/). And if you're wondering about the harness I used to direct all of this, that's the [SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness).

<!-- iamhoiend -->
