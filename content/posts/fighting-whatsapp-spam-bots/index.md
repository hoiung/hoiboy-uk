---
title: "WhatsApp Spam Bots Bombarded Our Groups. So We Built a Warden."
date: 2026-10-17T23:59:00+01:00
draft: false
slug: fighting-whatsapp-spam-bots
resources:
  - src: "shots/phone/1-chan-test-spam.webp"
    title: "Chan's test spam, flagged in Telegram, banned with one tap, then unbanned"
  - src: "shots/phone/2-banned-numbers-removed.webp"
    title: "The bot clearing out the spammers we banned up front (numbers blurred)"
  - src: "shots/phone/3-undo-reports.webp"
    title: "Every removal is reported in Telegram with an Undo button"
categories: [tech-ai]
tags: [whatsapp, spam-bots, community, open-source, claude-code, AGIT]
description: "Crypto and stock bots kept spamming our WhatsApp groups. A signup funnel now keeps the invite private, and our own warden bot removes any spammer who gets in."
---

<!-- iamhoi -->

Our WhatsApp group link used to be public on Meetup, and we were bombarded by crypto and stock bots spamming our groups constantly. (Sound familiar?)

The community is Asians & Gingers in Tech (AGIT), and we meet up every month in the City of London. Most of the spam is crypto, stocks or some fast money making scheme, but mainly crypto and stocks at the moment.

So we fixed it in two layers. A signup funnel that keeps the invite link private, and our own warden bot for anything that still gets in.

This turned out to be quite the fun project, but also super useful since I am building multiple WhatsApp communities with multiple groups.

## First line of defence: the signup funnel

First we reset our WhatsApp join link, so the old one stopped working. Then we removed every public link to our WhatsApp.

Now the only way in is our [AGIT Events Signup](/community/asians-gingers-in-tech/join/) page. The registration form is a funnel:

1. You fill in your name and email, and tick the membership box.
2. We email you a link to confirm your email is correct (the techy name for this is double opt-in).
3. Once you click it, the welcome email arrives with a big green button to join our WhatsApp community groups.

{{< zoom-image src="signup-page.webp" alt="The AGIT Events Signup page: why the WhatsApp invite comes by email, then a form with name, email, a membership box and a bot check" title="The AGIT Events Signup page" >}}

{{< zoom-image src="welcome-email.webp" alt="The welcome email with a green button to join the AGIT WhatsApp community groups, asking members to keep the link to themselves" title="The welcome email with the WhatsApp invite" >}}

The invite link itself lives in one place only: a locked secret on the server that sends the welcome email. The website's code is public on GitHub, so a test fails the whole build if anyone ever commits a WhatsApp invite link to it (belt and braces!).

The form also doubles up as how you sign up to attend our events. It's FREE, and you only do it once. Members have already started signing up!

## Second line of defence: our own warden bot vs spam bots

A funnel can't stop everything though. People will try to join, and we have no idea whether they are bots or actual users. And anyone who already had the old link could already be inside.

So I built [GroupWarden](https://github.com/hoiung/groupwarden). It sits in every group of our community as a co-admin and reads each new message. When a message matches our spam rules, it deletes the message, removes the sender and bans them from every group of every community it watches. Then it reports what it did in our private Telegram admin chat, with the full message as proof and an Undo button.

A rule is a keyword plus a link or contact detail (a phone number, a contact card, a group invite), or words from two different word lists in the same message. A keyword on its own never gets anyone removed. So chatting about crypto is fine. Crypto plus a phone number? Gone.

And there are no second chances. If they post spamming shit, they are deleted, blocked and removed from the group. Full stop. If they were truly human, or had their account hijacked, that's their problem. They need to reach out to us and fix their account before we even unblock them.

When a new kind of spam turns up, I paste it into Claude Code, and a skill tests every rule against all our saved spam and suggests the smallest rule change. I built the whole thing with Claude Code, using my [SST3-AI-Harness](https://github.com/hoiung/sst3-ai-harness).

## Yes, we're kind of breaking WhatsApp's rules

We're kind of violating the WhatsApp policy.

WhatsApp's official business tools can't delete messages or remove people in groups they didn't create. So GroupWarden logs in the same way WhatsApp Web does, as a linked device, using an unofficial library called whatsmeow. That breaks WhatsApp's Terms of Service, and the real risk is WhatsApp banning the bot's number.

But we're left with no choice. We fight spam bots with our own warden bots.

To keep that risk small, the bot has its own dedicated SIM, and it's a co-admin, never the owner. Every group still has at least 2 human admins, so if WhatsApp bans the bot's number, us humans still run the community.

## How we tested it

My sister Chan helped me test it. She posted a fake crypto spam message in our AGIT London group. The rule was still on report-only at that point, so the bot flagged it in our Telegram admin chat with a Ban button. I tapped Ban, it deleted her message and removed her from all 3 groups, and then I unbanned her with one command. Worked great! (Thanks Chan!)

Then I switched it to delete and ban automatically. I also had a list of spammers' phone numbers, so we banned those up front (23 of them), and the bot cleared them out of the community.

{{< gallery folder="shots/phone" >}}

The old spam already sitting in the groups? I deleted it by hand. No need to build history scanning... let's not overengineer.

It's been live in both my WhatsApp communities since 14 October.

## Want your own warden bot?

If you run a WhatsApp community and want to set up your own bot, I've put it up on my public GitHub repo: [GroupWarden](https://github.com/hoiung/groupwarden). It's free and open source. Read the risks section first, and use a dedicated number!

And if you're in tech in London and fancy coming along, you know where to sign up now: [AGIT Events Signup](/community/asians-gingers-in-tech/join/).

<!-- iamhoiend -->
