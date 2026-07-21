#!/usr/bin/env python3
"""Fail CI if the ai_training migration decision is still open near its deadline.

Cloudflare changes what `ai_training: block` MEANS on 2026-09-15. Verbatim from
the announcement: "Since the defaults will be enforced by the most restrictive
applicable rules, multi-purpose crawlers such as Googlebot, Applebot, and BingBot
will be blocked by customers who have selected to block Training".

These zones HAVE selected to block Training, so they are in scope. That is the
whole exposure: it follows from a setting this repo's own workstream applied, not
from any plan tier or default. (An earlier version of this docstring claimed the
new defaults "apply to all existing free customers" and that Free plan was the
reason. That sentence is not in Cloudflare's post; it was a fabricated quote and
is retracted. The separate ads-page default genuinely does apply only to newly
onboarding domains, and is irrelevant here.)

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
from datetime import date, datetime, timezone
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
FENCE_OPEN = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
# Closing fence: same bound as the opener (CommonMark 0.31 s4.5 allows up to
# three leading spaces), the delimiter run, then only trailing whitespace.
FENCE_CLOSE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")


def _strip_fences(text: str) -> str:
    """Blank out fenced code blocks, preserving line count.

    An illustrative `resolved` example inside a fence would otherwise be found
    and satisfy the gate while the real marker still says pending.

    Scanned line by line rather than with one regex, because the regex version
    was defeated three ways, each verified to produce a false PASS: a delimiter
    indented by a space (still valid CommonMark), a tilde `~~~` fence, and a
    fence opened but never closed. The last is the nastiest, since an unclosed
    fence swallows the rest of the file and a regex requiring a closing delimiter
    matches nothing at all, leaving the whole block live.

    An unclosed fence therefore runs to end of file, which is what CommonMark
    says it does. Line count is preserved so any future line-number reporting
    stays honest.
    """
    out, fence = [], None
    for line in text.splitlines():
        if fence is None:
            m = FENCE_OPEN.match(line)
            if m:
                # Keep the OPENER'S OWN LENGTH, not a hardcoded 3. CommonMark
                # requires the closing run to be at least as long as the opener,
                # so a ```` block is NOT closed by an inner ``` run. Hardcoding 3
                # let that inner run close the fence early and expose everything
                # after it, including a marker that was supposed to stay hidden.
                fence = m.group(1)
                out.append("")
                continue
            out.append(line)
        else:
            out.append("")
            # A closing fence is the same character, alone, at least as long as
            # the opener, and indented by AT MOST THREE SPACES.
            #
            # The indentation bound is not cosmetic. `line.strip()` was used
            # here, which accepts a closer at any indentation, while the opener
            # was correctly bounded to `[ \t]{0,3}`. CommonMark 0.31 s4.5 caps
            # the closing fence at three spaces, so a four-space-indented ```
            # is CONTENT, not a delimiter. Treating it as a closer flipped
            # inside/outside parity for the rest of the file and could leave an
            # illustrative `resolved` example as the only live marker, at which
            # point the gate printed "decision recorded" and exited 0 with the
            # real decision still pending. Verified against markdown-it-py's
            # commonmark preset, which puts both markers inside the code block.
            m = FENCE_CLOSE.match(line)
            if m and set(m.group(1)) == {fence[0]} and len(m.group(1)) >= len(fence):
                fence = None
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _today() -> date:
    override = os.environ.get("AI_TRAINING_DEADLINE_TODAY")
    if not override:
        # UTC explicitly: CI runs in UTC and the operator is in the UK, so
        # date.today() would mean different things in the two places for one
        # hour a day during BST. A date-based gate must not depend on where it
        # runs. The two-week lead makes the hour immaterial either way.
        return datetime.now(timezone.utc).date()
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

    matches = MARKER.findall(_strip_fences(DOC.read_text(encoding="utf-8")))
    if not matches:
        print(
            "ERR: no `ai-training-migration-decision:` marker in "
            f"{DOC.relative_to(ROOT)}.\n"
            "     The marker IS the gate's input. Removing it disables the gate, "
            "so its absence is an error, not a pass.",
            file=sys.stderr,
        )
        return 2

    # More than one marker is ambiguous, and first-match-wins would let a stale
    # `resolved` line above the real `pending` one silently disarm the gate.
    if len(matches) > 1:
        print(
            f"ERR: {len(matches)} `ai-training-migration-decision:` markers in "
            f"{DOC.relative_to(ROOT)}; expected exactly 1.\n"
            "     Ambiguous input is not a pass. Delete the duplicates.",
            file=sys.stderr,
        )
        return 2

    state, note = matches[0][0], matches[0][1].strip()
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
