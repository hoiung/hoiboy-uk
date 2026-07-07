---
title: "Singer & Steel"
date: 2026-07-07T12:00:00+01:00
description: "How HOIBOY AI LTD built a two-day demo for Singer & Steel, advised them not to automate their 3D design, and instead installed and maintains the Claude Code harness setup that lets them build their own workflow."
hideDate: true
---

<!-- iamhoi -->

**Client:** Singer & Steel, an architecture and design practice run by Holly and Derek.
**Base-only harness managed by HOIBOY AI LTD.**

## The problem

Singer & Steel spend real money and real time on every project, working with an interior designer to get each space looking the way they envision it. That is how good design happens, no complaint there. But they had a fair question: could AI take some of that on? Could you automate the 3D modelling of their architectural designs in Blender or SketchUp, turn concepts into visuals faster, and cut the per project cost and the back and forth?

Everyone is asking a version of that right now. So instead of guessing, I built them the answer.

## What I built

A two-day MVP. A real working demo that drove SketchUp and Blender through automation, so we could see the thing with our own eyes rather than argue about it in theory. Two days was enough to build it, run it, and understand exactly where the complexity lived.

## What the demo produced

Here is what those two days actually made. I tried the same room two ways, once in SketchUp and once in Blender, to compare how each one performs, how fiddly each is to set up, and how well each one automates. Same brief, two tools, side by side.

{{< zoom-image src="demo-sketchup-model.jpg" alt="A plain grey room shell built in SketchUp with furniture placed inside" title="The room built in SketchUp" >}}

{{< zoom-image src="demo-render-room.jpg" alt="A photoreal 3D render of a living room with a sofa, armchair, coffee table, vase and plant, built in Blender" title="The same room done in Blender" >}}

{{< zoom-image src="demo-render-detail.jpg" alt="A close-up of the Blender version showing the plant, cushions and coffee table" title="A close-up from the Blender version" >}}

A quick note on these. They were rendered on an HP ZBook 15 from 2013, more than twelve years old now, an old i7 laptop with a tiny Quadro GPU that sits in my home lab test rack. So the Blender output is not the sharpest, but for a machine that old, I would say it holds up pretty well. Imagine what it would do on a newer box with a proper GPU.

Two tools, the same job, so I could judge the output, the setup effort, and how automatable each one really is.

My honest take? Blender wins. It is insanely powerful, it is free and open source, and if I was building this properly with AI automation, that is where I would go. You take the hardware hit once, a decent machine with a good GPU, and then you own it. SketchUp went subscription only a few years back, so it is a bill every year, and that adds up fast. And you do not need the newest kit either. A second hand machine only a few years old, with a proper GPU, could already do something amazing.

Seeing it side by side, instead of guessing, is what let us have the honest conversation next.

## Knowing when not to automate

Here is the honest part. Once I had it working, and actually understood what today's AI tooling can and cannot do, I told them not to take it further.

Not because I could not build it. I can. The questions that matter to a business are different: is it cost effective, and will it genuinely help a practice their size? For Singer & Steel the answer was clearly no. What a bespoke automated 3D tool would cost me to build and keep running, and cost them in time, would far outweigh what they already spend hiring an interior designer per project. One is a big ongoing build I have to maintain. The other is a designer they pay only when they need one.

And here is the bit people skip. Could I have answered that with real confidence without building the mock up first? Probably not, not honestly. Anyone can have an opinion on whether AI can do a job. Building the thing, seeing exactly where it strains, and working out the true cost is what turns an opinion into a decision you can stand behind. The two days bought that.

There is a craft point too. This work is specialist coordination between two experts, the architect and the interior designer, each bringing judgement and taste the other does not have. That back and forth is where the design actually happens. It is not something you hand to a script and walk away from. But even leaving that aside, the economics alone made the call.

Not everything should be automated. Working out what should and what should not, and being able to prove it rather than guess, is the actual work.

## What I do for them now

So we did the more useful thing instead.

This is not my full managed harness service, where I run everything for a client behind the scenes. Singer & Steel wanted to do the building themselves, and that is the right instinct. So I gave them the foundation instead of the finished product. I installed my Claude Code harness setup on their own machine, and I keep it up to date. That is the whole job: the core install, on their device, kept current.

From there they build their own automation, inside the work they already know better than anyone. The design expertise stays where it belongs, with them, and AI takes the parts that genuinely are routine. No waiting on me for the day to day, no black box they cannot steer.

That is a better outcome than a clever 3D script somebody else owns and maintains. They come out of it more capable, not more dependent.

## The outcome

Singer & Steel got a clear, honest answer on their 3D question, backed by a real demo rather than a sales pitch, and they got it in two days. No half-finished automation limping along in the background. Their site is live at [singerandsteel.co.uk](https://www.singerandsteel.co.uk/), and they now run my Claude Code harness setup on their own machine, which I keep current, while they build their own automation on top of it.

<!-- iamhoiend -->

---

Published with the client's consent. Managed by HOIBOY AI LTD.
