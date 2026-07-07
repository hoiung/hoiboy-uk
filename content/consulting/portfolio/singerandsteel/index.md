---
title: "Singer & Steel"
date: 2026-07-07T12:00:00+01:00
description: "How HOIBOY AI LTD built a three-day demo for Singer & Steel, advised them not to automate their 3D design, and instead installed and maintains the Claude Code harness setup that lets them build their own workflow."
hideDate: true
---

<!-- iamhoi -->

**Client:** Singer & Steel, an architecture and design practice run by Holly and Derek.
**Base-only harness managed by HOIBOY AI LTD.**

## The problem

Singer & Steel spend real money and real time on every project, working with an interior designer to get each space looking the way they envision it. That is how good design happens, no complaint there. But they had a fair question: could AI take some of that on? Could you automate the 3D modelling of their architectural designs in Blender or SketchUp, turn concepts into visuals faster, and cut the per project cost and the back and forth?

Everyone is asking a version of that right now. So instead of guessing, I built them the answer.

## What I built

A three-day MVP. A real working demo that drove SketchUp and Blender through automation, so we could see the thing with our own eyes rather than argue about it in theory. Three days was enough to build it, run it, and understand exactly where the complexity lived.

## What the demo produced

Here is what those two days actually made. I tried the same room two ways, once in SketchUp and once in Blender, to compare how each one performs, how fiddly each is to set up, and how well each one automates. Same brief, two tools, side by side.

{{< zoom-image src="demo-sketchup-model.jpg" alt="A basic SketchUp free-tier output showing a plain room shell with furniture inside" title="SketchUp, a basic free-tier output (not its best)" >}}

{{< zoom-image src="demo-render-room.jpg" alt="A photoreal 3D render of a living room with a sofa, armchair, coffee table, vase and plant, built in Blender" title="The same room done in Blender" >}}

{{< zoom-image src="demo-render-detail.jpg" alt="A close-up of the Blender version showing the plant, cushions and coffee table" title="A close-up from the Blender version" >}}

A couple of honest caveats. SketchUp ran on its free tier, which lives in the cloud, so its rendering happened on Trimble's servers, not on my machine, and that tier caps how many renders you get. I just took the first output my AI rendering script produced, so the SketchUp shot here is nowhere near what the tool can really do. Fair is fair.

The Blender render is the opposite story. It ran entirely on my own machine, an old laptop, more than twelve years old, with a tiny GPU, part of my home lab test rack. So it is not the sharpest, but for a machine that old, I would say it holds up pretty well. Imagine what it would do on a newer box with a proper GPU.

Two tools, the same job, so I could judge the output, the setup effort, and how automatable each one really is.

My honest take? Blender wins. It has been around for years, free, open source, and insanely powerful, but it was always a beast to learn. Hundreds of parameters and a steep curve, the kind of tool you had to really commit to. SketchUp won on simplicity, it was the easy option. AI is what flips that. The same way AI has made writing code cheaper and faster, it has knocked the barrier right down on Blender too. The complexity is still there, but now AI can drive it for you. So you get all that free, open source power without paying years of your life to learn it.

The trade is hardware, not a subscription. You take the hit once, a decent machine with a good GPU, and then you own it. SketchUp went subscription only a few years back, so it is a bill every year, and that adds up fast. And you do not need the newest kit either. A second hand machine only a few years old, with a proper GPU, could already do something amazing.

Seeing it side by side, instead of guessing, is what let us have the honest conversation next.

## Knowing when not to automate

Here is the honest part. Once I had it working, and actually understood what today's AI tooling can and cannot do, I told them not to take it further.

Not because I could not build it. I can. The questions that matter to a business are different: is it cost effective, and will it genuinely help a practice their size? For Singer & Steel the answer was clearly no. What a bespoke automated 3D tool would cost me to build and keep running, and cost them in time, would far outweigh what they already spend hiring an interior designer per project. One is a big ongoing build I have to maintain. The other is a designer they pay only when they need one.

And here is the bit people skip. Could I have answered that with real confidence without building the mock up first? Probably not, not honestly. Anyone can have an opinion on whether AI can do a job. Building the thing, seeing exactly where it strains, and working out the true cost is what turns an opinion into a decision you can stand behind. The three days bought that.

There is a craft point too. This work is specialist coordination between two experts, the architect and the interior designer, each bringing judgement and taste the other does not have. That back and forth is where the design actually happens. It is not something you hand to a script and walk away from. But even leaving that aside, the economics alone made the call.

Not everything should be automated. Working out what should and what should not, and being able to prove it rather than guess, is the actual work.

## What I do for them now

So we did the more useful thing instead.

This is not my full managed harness service, where I run everything for a client behind the scenes. Singer & Steel wanted to do the building themselves, and that is the right instinct. So I gave them the foundation instead of the finished product. I installed my Claude Code harness setup on their own machine, and I keep it up to date. That is the whole job: the core install, on their device, kept current.

From there they build their own automation, inside the work they already know better than anyone. The design expertise stays where it belongs, with them, and AI takes the parts that genuinely are routine. No waiting on me for the day to day, no black box they cannot steer.

That is a better outcome than a clever 3D script somebody else owns and maintains. They come out of it more capable, not more dependent.

## The outcome

Singer & Steel got a clear, honest answer on their 3D question, backed by a real demo rather than a sales pitch, and they got it in three days. No half-finished automation limping along in the background. They now run my Claude Code harness setup on their own machine, which I keep current, while they build their own automation on top of it.

I did not build their website, that one is all theirs. But if you want to see their architecture and design work, you will find them at [singerandsteel.co.uk](https://www.singerandsteel.co.uk/).

<!-- iamhoiend -->

---

Published with the client's consent. Managed by HOIBOY AI LTD.
