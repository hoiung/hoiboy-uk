#!/usr/bin/env python3
"""The /blogs/ hub is inside the em-dash guard's scope (blog-priv#62).

`scripts/check_emdash_zero_tolerance.sh` excludes `content/posts` wholesale,
because those 79 posts are the voice-sacred pre-AI corpus where em dashes are
genuine authorship. Hugo then forces the NEW hub landing to live at
`content/posts/_index.md`, so it inherited that exemption purely by where the
framework requires a section index to sit.

Measured on 2026-07-25, before the carve-out was added: an em dash injected into
that file passed this guard AND `check_emdash_newposts.py` (date-gated, and a
section landing carries no date) AND the marker-driven
`check-ai-writing-tells.py`. Nothing in the repo covered it.

This test asserts the fix the only way that means anything: by MUTATION, in both
directions. Injecting an em dash into the hub must fail the guard, and injecting
one into a legacy post must still pass it. Half of that pair alone is satisfiable
by a guard that always fails, or by one that never does.

Usage:  python3 scripts/test_emdash_hub_coverage.py
Exit 0 = the hub is covered and the legacy exemption is intact.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "scripts" / "check_emdash_zero_tolerance.sh"
HUB = ROOT / "content" / "posts" / "_index.md"
EMDASH = "—"


def run_guard() -> int:
    return subprocess.run(["bash", str(GUARD)], cwd=ROOT,
                          capture_output=True, text=True, check=False).returncode


def _legacy_post() -> Path:
    """A post that is NOT the hub, read from disk rather than hardcoded so a
    renamed or deleted post surfaces as a failure instead of a silent skip."""
    for p in sorted((ROOT / "content" / "posts").glob("*/index.md")):
        return p
    sys.exit("no legacy post found under content/posts/")


def mutate_and_check(target: Path, expect_fail: bool, label: str,
                     failures: list[str]) -> None:
    """Append an em dash to `target`, run the guard, restore. Byte-for-byte
    restore is asserted, so a crashed run cannot leave the tree dirty unnoticed."""
    original = target.read_bytes()
    try:
        target.write_bytes(original + f"\n\ninjected {EMDASH} dash\n".encode())
        rc = run_guard()
    finally:
        target.write_bytes(original)
    if target.read_bytes() != original:
        failures.append(f"{label}: the test failed to restore {target}")
    failed = rc != 0
    if failed != expect_fail:
        verb = "should have failed" if expect_fail else "should have passed"
        failures.append(
            f"{label}: with an em dash in {target.relative_to(ROOT)} the guard {verb} "
            f"but exited {rc}"
        )


def main() -> int:
    failures: list[str] = []
    if not GUARD.is_file():
        print(f"FAIL: {GUARD} does not exist", file=sys.stderr)
        return 1
    if not HUB.is_file():
        print(f"FAIL: {HUB} does not exist", file=sys.stderr)
        return 1

    if run_guard() != 0:
        print("FAIL: the em-dash guard is already failing on the clean tree, so this "
              "test cannot distinguish its own mutations", file=sys.stderr)
        return 1

    mutate_and_check(HUB, expect_fail=True,
                     label="hub coverage", failures=failures)
    mutate_and_check(_legacy_post(), expect_fail=False,
                     label="legacy exemption", failures=failures)

    if failures:
        print(f"FAIL: {len(failures)} em-dash scope violation(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("OK: an em dash in content/posts/_index.md fails the zero-tolerance guard, "
          "and one in a legacy post still does not")
    return 0


def test_emdash_hub_coverage() -> None:
    """pytest entry point (CI runs pytest through explicit file lists)."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
