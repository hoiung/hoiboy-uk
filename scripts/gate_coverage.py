#!/usr/bin/env python3
"""The one invariant behind eleven separate defects in this Issue.

Every gate in `scripts/` asserts an ABSENCE: no em dash here, no secret there,
no noindex page in the feed, no identifying EXIF in the images. An absence is
only evidence when something was actually opened. When the set of surfaces a
gate examines silently shrinks to zero, every assertion over it holds
vacuously, the gate prints a confident OK, and the shrinkage is reported as
success.

That is one defect, and #56 shipped eleven instances of it before this file
existed. The instances differ only in HOW the set shrank:

  enumeration returned nothing   `if not argv: return 0` (check_wordcount)
                                 `git ls-files` in a tree with no images (check-exif)
                                 an empty params.toml (check_config_traceability)
  a declared input was absent    a missing SCAN_PATHS directory swallowed by
                                 `2>/dev/null || true` (check_emdash_zero_tolerance)
                                 a nonexistent path matching no if/elif branch
                                 (check-ai-writing-tells)
  a surface was never opened     1 of 18 RSS feeds (check_noindex_frontmatter)
  a precondition disarmed a tier absent trail.json (check_social_cards)
  an error path returned clean   an unparseable image (check-exif)

Each was fixed on its own terms, at its own granularity -- per rule, per class,
per tree, per format. None of those floors is the surface that matters, which
is the individual page, feed, or file, so the next instance appeared on a
surface the previous fix had not enumerated. Three consecutive fixes for this
class reproduced the class.

So the floor belongs HERE, once, in the vocabulary every gate shares:

    a gate that examined nothing must FAIL, never pass.

`tests/test_gate_vacuity.py` is the half that makes this structural rather than
advisory. It runs EVERY gate in `scripts/` against a deliberately empty tree
and fails the build on any that exits 0. A gate is enrolled by existing, not by
remembering to call something here, so the next gate anyone writes is covered
before it is written.

Exit codes, repo-wide:

    0  the gate looked, and found nothing wrong
    1  the gate looked, and found a violation
    2  the gate could not look -- its own coverage failed

2 is deliberately distinct from 1. "No violations" and "no evidence" are
opposite outcomes that an exit-code check alone cannot tell apart, and reading
the second as the first is this whole class in one sentence.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Sized

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_VACUOUS = 2


class VacuousGate(SystemExit):
    """Raised when a gate cannot substantiate its own claim.

    Subclasses SystemExit so an uncaught instance terminates with EXIT_VACUOUS
    without every call site needing a handler, while still being catchable by
    name in tests. A gate that wants to report several coverage failures at
    once collects them itself and calls `fail` last.
    """

    def __init__(self, message: str) -> None:
        super().__init__(EXIT_VACUOUS)
        self.message = message


def fail(gate: str, message: str) -> "VacuousGate":
    """Emit a coverage failure on stderr and raise.

    Returned as well as raised so a caller can write `raise fail(...)` and keep
    the control flow legible to a reader and to a type checker.
    """
    text = f"[FAIL] [vacuous-gate] {gate}: {message}"
    print(text, file=sys.stderr)
    raise VacuousGate(text)


def require_examined(
    gate: str,
    kind: str,
    items: Sized | int,
    *,
    hint: str,
) -> int:
    """Assert a gate examined at least one surface. Returns the count.

    `kind` names the surface in the plural as the gate's own message would
    ("built page", "tracked image", "noindex rule"), because the count alone is
    what made these failures survive review: "0 scanned image(s)" printed
    beside "OK" reads as a healthy run of a small tree.

    `hint` states what the operator should DO. A coverage failure is nearly
    always one of two things, a stale build or a rule naming a surface the site
    no longer serves, and the two have opposite fixes.
    """
    count = items if isinstance(items, int) else len(items)
    if count <= 0:
        raise fail(
            gate,
            f"examined 0 {kind}, so every assertion it makes held vacuously. "
            f"An absence proves nothing about a surface that was never opened. "
            f"{hint}",
        )
    return count


def require_input(gate: str, path: Path | str, *, why: str) -> Path:
    """Assert a declared input exists. A missing one is a FAIL, not a skip.

    The silent-skip shape this replaces: a gate iterates a hardcoded list of
    scan roots, one is renamed or removed, the iteration quietly covers fewer
    surfaces than the list claims, and the gate still exits 0. Absence of a
    declared input is a fact about the GATE, not about the tree.
    """
    resolved = Path(path)
    if not resolved.exists():
        raise fail(
            gate,
            f"declared input {resolved} does not exist ({why}). Either the path "
            f"moved and this gate's list is stale, or the tree is incomplete. "
            f"Skipping it would clear a surface that was never opened.",
        )
    return resolved


def require_readable(gate: str, path: Path | str, exc: Exception, *, remedy: str) -> "VacuousGate":
    """Convert an unreadable surface into a coverage failure.

    A parse error inside a gate is the same defect wearing a different coat:
    `except Exception: return []` hands the caller an empty result that is
    indistinguishable from a clean one, and the gate then clears a file it
    could not read. Callers use this in the except branch instead of returning
    an empty collection.
    """
    raise fail(
        gate,
        f"cannot read {path}: {exc}. This gate cannot assert an absence in a "
        f"surface it failed to parse, and an empty result here is "
        f"indistinguishable from a clean one. {remedy}",
    )


def coverage(gate: str, **counts: int) -> str:
    """The evidence line a passing gate prints.

    The counts ARE the proof that each absence was measured against something,
    which is why they belong in the success message and not only in the failure
    path. A reader who cannot see WHAT was examined cannot tell a real pass
    from a vacuous one, and neither could this repo for eleven rounds.
    """
    detail = ", ".join(f"{n} {kind.replace('_', ' ')}" for kind, n in sorted(counts.items()))
    return f"[OK] {gate}: examined {detail}."


def declared_paths(gate: str, paths: Iterable[Path | str], *, why: str) -> list[Path]:
    """`require_input` over a list, reporting EVERY missing entry at once.

    Reporting only the first turns one stale scan root into as many edit-run
    cycles as there are stale roots, which is how a partially-correct list
    survives: each run fixes one and still passes the rest by never reaching
    them.
    """
    resolved = [Path(p) for p in paths]
    missing = [p for p in resolved if not p.exists()]
    if missing:
        listed = ", ".join(str(p) for p in missing)
        raise fail(
            gate,
            f"{len(missing)} declared input(s) do not exist: {listed} ({why}). "
            f"A scan list naming a path the tree does not have covers fewer "
            f"surfaces than it claims.",
        )
    return resolved
