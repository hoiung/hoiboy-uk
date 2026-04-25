#!/usr/bin/env python3
"""Enforce iamhoi-marker wrapping on new Hoi-voice posts.

Complements `check-ai-writing-tells.py` (which scans INSIDE iamhoi regions)
by ENFORCING that posts containing first-person Hoi-voice prose actually
HAVE the wrapping markers in the first place. Without this gate, an author
can write a full Hoi-voice post and the voice guard silently skips it
(default = SKIP for unmarked content).

Decision matrix (default = PASS):
  --check-only-new and date < HOIBOY_CUTOFF_DATE  -> PASS (legacy corpus)
  first non-blank line is `<!-- iamhoi-exempt -->` -> PASS (whole-file bypass)
  body contains `<!-- iamhoi -->`                  -> PASS (wrapped)
  body has first-person prose AND no marker        -> FAIL exit 1

First-person detection:
  - regex `\\b(I|I'm|I've|my|me|Hoi)\\b` (case-sensitive on `I`/`I'm`/`I've`/`Hoi`;
    case-insensitive on `my`/`me` via separate pattern, but kept simple for
    false-positive economy)
  - KEEP_LIST vocabulary from voice_rules.py (passion, journey, back to basics,
    align, leverage, robust, coach, enable, etc) — only triggers if 3+ KEEP_LIST
    terms appear, to suppress one-off generic-word noise.

Issue: hoiung/bakeoff-priv#3 (Phase 1 infra)
Exit codes: 0 = pass, 1 = wrapping missing, 2 = config / read error
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from voice_rules import HOIBOY_CUTOFF_DATE, KEEP_LIST

# Pre-compiled patterns (compile once, reuse per file)
_FIRST_PERSON_RE = re.compile(r"\b(I|I'm|I've|Hoi)\b")
_FIRST_PERSON_LOWER_RE = re.compile(r"\b(my|me)\b", re.IGNORECASE)
_KEEP_LIST_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in KEEP_LIST) + r")\b",
    re.IGNORECASE,
)
_FRONTMATTER_DATE_RE = re.compile(r"^date:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
_MARKER_OPEN = "<!-- iamhoi -->"
_MARKER_EXEMPT = "<!-- iamhoi-exempt -->"
_KEEP_LIST_THRESHOLD = 3  # require >= N KEEP_LIST hits to count as Hoi-voice


def parse_post_date(text: str) -> date | None:
    """Return frontmatter date or None if no frontmatter / no date."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    front = text[3:end]
    m = _FRONTMATTER_DATE_RE.search(front)
    if not m:
        return None
    return date.fromisoformat(m.group(1))


def strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter block. Returns body or original text on no frontmatter."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4:]


def is_exempt(body: str) -> bool:
    """First non-blank line is `<!-- iamhoi-exempt -->`."""
    for line in body.split("\n"):
        if line.strip():
            return line.strip() == _MARKER_EXEMPT
    return False


def has_voice_prose(body: str) -> bool:
    """Return True if body contains first-person prose or a strong KEEP_LIST signal."""
    if _FIRST_PERSON_RE.search(body):
        return True
    if _FIRST_PERSON_LOWER_RE.search(body):
        return True
    keep_hits = len(_KEEP_LIST_RE.findall(body))
    return keep_hits >= _KEEP_LIST_THRESHOLD


def check_file(path: Path, check_only_new: bool) -> tuple[bool, str]:
    """Return (ok, message). ok=True means PASS."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        return False, f"READ_ERROR {path}: {exc}"

    if check_only_new:
        post_date = parse_post_date(text)
        if post_date is not None and post_date < HOIBOY_CUTOFF_DATE:
            return True, ""

    body = strip_frontmatter(text)

    if is_exempt(body):
        return True, ""

    if _MARKER_OPEN in body:
        return True, ""

    if has_voice_prose(body):
        return False, (
            f"ERR: {path}: post contains Hoi-voice prose but no iamhoi wrapping. "
            f"Wrap each section in `<!-- iamhoi --> ... <!-- iamhoiend -->`, OR "
            f"add `<!-- iamhoi-exempt -->` as the first non-blank line for "
            f"whole-file bypass."
        )

    return True, ""


def gather_files(args: list[str], check_only_new: bool) -> list[Path]:
    """Resolve CLI args to a list of .md files. Default: content/posts/**/*.md."""
    repo_root = Path(__file__).resolve().parents[1]
    files: list[Path] = []
    if args:
        for arg in args:
            p = Path(arg).resolve()
            if p.is_dir():
                files.extend(sorted(p.rglob("*.md")))
            elif p.exists() and p.suffix == ".md":
                files.append(p)
    else:
        posts = repo_root / "content" / "posts"
        if posts.exists():
            files.extend(sorted(posts.rglob("*.md")))
    return files


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Enforce iamhoi-marker wrapping on new Hoi-voice posts. "
            "Default scope: content/posts/**/*.md."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Files or directories to check. Default: content/posts/.",
    )
    parser.add_argument(
        "--check-only-new",
        dest="check_only_new",
        action="store_true",
        default=True,
        help="Skip posts dated < HOIBOY_CUTOFF_DATE (default ON).",
    )
    parser.add_argument(
        "--no-check-only-new",
        dest="check_only_new",
        action="store_false",
        help="Check every file regardless of frontmatter date.",
    )
    args = parser.parse_args()

    files = gather_files(args.paths, args.check_only_new)
    if not files:
        return 0

    failures: list[str] = []
    for f in files:
        ok, msg = check_file(f, args.check_only_new)
        if not ok:
            failures.append(msg)

    if failures:
        for msg in failures:
            print(msg, file=sys.stderr)
        print(
            f"\n{len(failures)} file(s) missing iamhoi wrapping. "
            f"See dotfiles/cv-linkedin/VOICE_PROFILE.md Section 8 + AP #15.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
