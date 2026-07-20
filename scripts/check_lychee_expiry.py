#!/usr/bin/env python3
"""Fail when a lychee allowlist entry is past its stated expiry date.

`lychee.toml` requires every `exclude` entry to carry an
`added: YYYY-MM-DD; expires: YYYY-MM-DD` comment, and its header claimed CI
enforced that. Nothing did. An entry added 2026-04-08 sat 13 days past expiry
with no signal, found by the blog-priv#55 Stage 5 audit.

The expiry exists because an allowlist entry suppresses link-checking for a
URL pattern. The reason for suppressing it (anti-bot 403, rate limit, deploy
race) can stop being true, and then the entry is silently hiding a genuinely
broken link. The date forces someone to re-confirm the reason still holds.

This FAILS rather than warns. A warning is what the previous state effectively
was: the information sat in the file and nobody read it. Re-confirming an entry
is a one-line edit, so a hard failure costs little, and it is the only kind of
signal this class of staleness has been shown to respond to.

Exit codes:
  0 = every entry is within its expiry window
  1 = at least one entry is past expiry, or is missing/has malformed metadata
  2 = operational error (config missing or unreadable)

Usage:
  python3 scripts/check_lychee_expiry.py [--config lychee.toml] [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# `expires:` inside a `#` comment. Anchored to the comment so a date appearing
# inside a regex pattern cannot be mistaken for metadata.
EXPIRES_RE = re.compile(r"#.*?\bexpires:\s*(\d{4}-\d{2}-\d{2})")
# A quoted string on its own line inside the exclude list is an entry.
ENTRY_RE = re.compile(r'^\s*"')


def check(config: Path, today: dt.date) -> tuple[list[str], int]:
    """Return (failures, entries_checked)."""
    failures: list[str] = []
    lines = config.read_text(encoding="utf-8").splitlines()

    in_exclude = False
    pending_expiry: dt.date | None = None
    pending_line = 0
    malformed: str | None = None
    checked = 0

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("exclude"):
            in_exclude = True
            continue
        if in_exclude and stripped.startswith("]"):
            in_exclude = False
            continue
        if not in_exclude:
            continue

        m = EXPIRES_RE.search(line)
        if m:
            try:
                pending_expiry = dt.date.fromisoformat(m.group(1))
                pending_line = i
                malformed = None
            except ValueError:
                pending_expiry = None
                malformed = f"{config.name}:{i}: unparseable expires date {m.group(1)!r}"
            continue

        if ENTRY_RE.match(line):
            checked += 1
            entry = stripped.rstrip(",")
            if malformed:
                failures.append(malformed)
            elif pending_expiry is None:
                failures.append(
                    f"{config.name}:{i}: entry {entry} has no "
                    f"'added: ...; expires: ...' comment; the header requires one"
                )
            elif pending_expiry < today:
                days = (today - pending_expiry).days
                failures.append(
                    f"{config.name}:{pending_line}: entry {entry} expired "
                    f"{pending_expiry} ({days} days ago). Re-confirm the reason for the "
                    f"exclusion still holds and extend the date, or drop the entry if "
                    f"the URL is checkable again."
                )
            # NOT consumed. The file's actual convention is one comment
            # governing the run of same-class entries beneath it (meetup +
            # facebook + instagram share one rationale and one date, as do
            # tiktok + x + twitter). An earlier draft of this checker cleared
            # the date after the first entry and reported four "missing
            # metadata" failures against entries that are correctly documented.
            # The date stays in force until the next expires comment replaces it.

    return failures, checked


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=str(ROOT / "lychee.toml"))
    ap.add_argument("--today", default=None,
                    help="Override today's date (YYYY-MM-DD) for testing.")
    args = ap.parse_args(argv)

    config = Path(args.config)
    if not config.is_file():
        print(f"ERR: config not found: {config}", file=sys.stderr)
        return 2

    try:
        today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    except ValueError:
        print(f"ERR: --today must be YYYY-MM-DD, got {args.today!r}", file=sys.stderr)
        return 2

    try:
        failures, checked = check(config, today)
    except OSError as exc:
        print(f"ERR: cannot read {config}: {exc}", file=sys.stderr)
        return 2

    # A run that inspects nothing is a broken run, not a clean one: the same
    # vacuous-pass class the frontmatter gate in this repo had to defend against.
    if checked == 0:
        print(f"ERR: found 0 allowlist entries in {config}; the exclude block or "
              f"the parser is broken (vacuous pass)", file=sys.stderr)
        return 1

    if failures:
        print("LYCHEE ALLOWLIST EXPIRY CHECK FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1

    print(f"Lychee allowlist OK ({checked} entries, none past expiry)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
