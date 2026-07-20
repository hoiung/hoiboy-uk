#!/usr/bin/env python3
"""Fail CI if the ai_training migration decision is still open near its deadline.

Cloudflare changes what `ai_training: block` MEANS on 2026-09-15: from that date
multi-purpose crawlers (Googlebot, Applebot, BingBot) are blocked for any zone
that has selected to block Training, and the new defaults apply to all existing
free customers. Both live zones are Free plan.

So a setting that is correct today silently becomes an SEO outage on a fixed
future date unless somebody decides before then. That is exactly the class of
thing a document cannot hold: docs/research/17_AI_CRAWLER_FRAMEWORK.md can state
the deadline, but nothing makes anyone read it in September.

This is the gate. It goes red from TRIGGER onward while the decision marker in
doc 17 still reads `pending`, and it goes green the moment the marker records a
real decision. It does NOT check the live Cloudflare state: CI has no zone token,
and a gate that silently skips when a credential is absent is worse than no gate.
It checks that a human made a call and wrote it down.

Exit codes (tri-state, matching scripts/check-ai-crawler-access.sh):
  0 = decision recorded, or the trigger date has not arrived yet
  1 = decision still pending and the trigger date has passed (the defect)
  2 = operational error (doc missing, marker missing or unparseable)

Override today's date for testing with AI_TRAINING_DEADLINE_TODAY=YYYY-MM-DD.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "research" / "17_AI_CRAWLER_FRAMEWORK.md"

# Cloudflare's migration date. The trigger deliberately leads it by two weeks so
# the decision is made with room to act, not on the morning it lands.
DEADLINE = date(2026, 9, 15)
TRIGGER = date(2026, 9, 1)

MARKER = re.compile(
    r"^ai-training-migration-decision:\s*(pending|resolved)\b(.*)$",
    re.MULTILINE,
)


def _today() -> date:
    override = os.environ.get("AI_TRAINING_DEADLINE_TODAY")
    if not override:
        return date.today()
    try:
        return date.fromisoformat(override)
    except ValueError:
        print(
            f"ERR: AI_TRAINING_DEADLINE_TODAY={override!r} is not YYYY-MM-DD.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def main() -> int:
    if not DOC.exists():
        print(f"ERR: {DOC} not found; cannot read the decision marker.", file=sys.stderr)
        return 2

    m = MARKER.search(DOC.read_text(encoding="utf-8"))
    if m is None:
        print(
            "ERR: no `ai-training-migration-decision:` marker in "
            f"{DOC.relative_to(ROOT)}.\n"
            "     The marker IS the gate's input. Removing it disables the gate, "
            "so its absence is an error, not a pass.",
            file=sys.stderr,
        )
        return 2

    state, note = m.group(1), m.group(2).strip()
    today = _today()

    if state == "resolved":
        print(f"OK: ai_training migration decision recorded. {note}".rstrip())
        return 0

    if today < TRIGGER:
        days = (TRIGGER - today).days
        print(
            f"OK: decision still pending, {days} day(s) before this gate turns red "
            f"({TRIGGER.isoformat()}); Cloudflare migrates {DEADLINE.isoformat()}."
        )
        return 0

    print(
        f"FAIL: the ai_training migration decision is still `pending` and "
        f"{TRIGGER.isoformat()} has passed.\n"
        f"\n"
        f"  Cloudflare migrates on {DEADLINE.isoformat()}. From that date "
        f"`ai_training: block` also blocks\n"
        f"  Googlebot, Applebot and BingBot on these zones, which would remove them "
        f"from organic search.\n"
        f"\n"
        f"  Decide, act on the zones, then record it in "
        f"{DOC.relative_to(ROOT)} as:\n"
        f"      ai-training-migration-decision: resolved (<date>, <what was done>)\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
