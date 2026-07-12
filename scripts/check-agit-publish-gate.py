#!/usr/bin/env python3
"""AGIT publish gate: no member feature goes live until it is cleared.

Reads a per-submission evidence record (produced by check-agit-feature-edit.py)
and HARD-FAILS publish unless every gate is satisfied:

  1. Edit-check flags reviewed. If the edit-check flagged anything, a human must
     have set `flags_cleared: true` in the clearance file after looking at them.
  2. Named-person clearance. Every person named in the edited feature is either
     `permissioned` (with the author's warranty recorded as a note) OR
     `anonymised` to a role. A `pending` or missing name blocks publish.
  3. (Phase 4) Emailed approval. The member's approval of the exact final wording
     is on file (approval.json, approved: true). Added by the Phase 4 step.

On first run, if no clearance file exists, this WRITES a `clearance.json`
template listing every named person as `pending` and exits non-zero, so the
operator fills it in. It never auto-clears anyone.

Honest scope: this gate enforces the recorded decisions; a human makes them.

Issue: hoiung/hoiboy-uk#48 (Phase 3; Phase 4 extends the approval leg)
Exit codes: 0 = cleared to publish, 1 = blocked (fill clearance / not approved),
            2 = usage/IO error
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

CLEARANCE_FILE = "clearance.json"
CHECK_FILE = "check.json"
APPROVAL_FILE = "approval.json"
VALID_STATUSES = ("permissioned", "anonymised")


@dataclass
class GateResult:
    ok: bool
    blockers: list[str] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)
    wrote_template: bool = False


def load_check(record: Path) -> dict:
    """Read the edit-check report from the record. Fails loudly if absent."""
    path = record / CHECK_FILE
    if not path.is_file():
        raise FileNotFoundError(
            f"no {CHECK_FILE} in {record}: run check-agit-feature-edit.py first")
    return json.loads(path.read_text(encoding="utf-8"))


def build_clearance_template(named_persons: list[str], flags_clean: bool) -> dict:
    """A fresh clearance file: every name pending, flags uncleared if any exist."""
    return {
        "flags_cleared": bool(flags_clean),  # True only when the edit-check was clean
        "named_persons": {
            name: {"status": "pending", "note": ""} for name in named_persons
        },
    }


def evaluate_gate(check: dict, clearance: dict, approval: dict | None) -> GateResult:
    """Evaluate every publish precondition against the recorded decisions."""
    blockers: list[str] = []
    checklist: list[str] = []

    # 1. Edit-check flags reviewed.
    if not check.get("clean", False) and not clearance.get("flags_cleared", False):
        n = len(check.get("flags", []))
        blockers.append(
            f"edit-check raised {n} flag categor{'y' if n == 1 else 'ies'}; "
            "review them and set flags_cleared: true in clearance.json")

    # 2. Named-person clearance.
    named_persons = check.get("named_persons", [])
    entries = clearance.get("named_persons", {})
    for name in named_persons:
        entry = entries.get(name)
        if entry is None:
            blockers.append(f"named person not in clearance file: {name}")
            checklist.append(f"[ ] {name}: MISSING from clearance.json")
            continue
        status = entry.get("status", "pending")
        note = (entry.get("note") or "").strip()
        if status not in VALID_STATUSES:
            blockers.append(f"named person not cleared ({status}): {name}")
            checklist.append(f"[ ] {name}: {status}")
        elif status == "permissioned" and not note:
            blockers.append(
                f"permissioned without an author-warranty note: {name}")
            checklist.append(f"[ ] {name}: permissioned (note required)")
        else:
            checklist.append(f"[x] {name}: {status}"
                             + (f" ({note})" if note else ""))

    # 3. Emailed approval (Phase 4). Enforced only once the approval leg is wired:
    #    an approval.json present but not approved always blocks; its absence is a
    #    Phase-4 boundary, surfaced (not silently passed).
    if approval is not None:
        if not approval.get("approved", False):
            blockers.append("member emailed approval on file but not approved")
        else:
            checklist.append("[x] member emailed approval on file")
    else:
        checklist.append("[ ] member emailed approval: not on file "
                         "(Phase 4 email-approval step)")

    return GateResult(ok=not blockers, blockers=blockers, checklist=checklist)


def run_gate(record: Path) -> GateResult:
    """Load the record, initialise a clearance template if needed, evaluate."""
    check = load_check(record)
    named_persons = check.get("named_persons", [])
    clearance_path = record / CLEARANCE_FILE

    if not clearance_path.is_file():
        template = build_clearance_template(named_persons, check.get("clean", False))
        clearance_path.write_text(
            json.dumps(template, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        result = evaluate_gate(check, template, None)
        result.wrote_template = True
        result.ok = False  # a freshly-written template is never pre-cleared
        result.blockers.insert(
            0, f"wrote {clearance_path} template; fill in each named person "
               "(permissioned + note, or anonymised) then re-run")
        return result

    clearance = json.loads(clearance_path.read_text(encoding="utf-8"))
    approval_path = record / APPROVAL_FILE
    approval = (json.loads(approval_path.read_text(encoding="utf-8"))
                if approval_path.is_file() else None)
    return evaluate_gate(check, clearance, approval)


def format_report(record: Path, result: GateResult) -> str:
    lines: list[str] = [f"Publish gate for {record}:"]
    if result.checklist:
        lines.append("")
        lines.extend(f"  {item}" for item in result.checklist)
    lines.append("")
    if result.ok:
        lines.append("CLEARED: every named person is permissioned or anonymised "
                     "and edit-check flags are reviewed. Safe to publish.")
    else:
        lines.append("BLOCKED: do NOT publish. Resolve:")
        lines.extend(f"  - {b}" for b in result.blockers)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hard publish gate for AGIT member features.")
    parser.add_argument("--record", required=True, type=Path,
                        help="Per-submission evidence record dir (from the edit-check).")
    parser.add_argument("--json", action="store_true",
                        help="Emit the gate result as JSON.")
    args = parser.parse_args(argv)

    if not args.record.is_dir():
        print(f"error: record dir not found: {args.record}", file=sys.stderr)
        return 2

    try:
        result = run_gate(args.record)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "ok": result.ok,
            "blockers": result.blockers,
            "checklist": result.checklist,
            "wrote_template": result.wrote_template,
        }, indent=2, ensure_ascii=False))
    else:
        print(format_report(args.record, result))

    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
