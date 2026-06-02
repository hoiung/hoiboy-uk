#!/usr/bin/env python3
"""Date-gated em-dash guard for NEW posts (hoiboy-uk #33 AC 2.5).

The blanket CI em-dash grep excludes `content/posts` entirely because legacy
posts (date < HOIBOY_CUTOFF_DATE) are voice-sacred and legitimately contain
em-dashes. That blanket exclusion also un-gated NEW posts, whose unmarked prose
must stay em-dash-free (the no-em-dash voice rule).

This check closes that hole: it scans NEW posts only (date >= cutoff) for a bare
U+2014, exempting `<!-- iamhoi-skip --> ... <!-- iamhoi-skipend -->` blocks where
banned punctuation may be quoted as an example (e.g. your-voice-is-a-brand
explaining what an em dash *is*). Legacy posts are skipped; the meet-recorder
consent page (content/private/, not content/posts) is out of scope here and is
handled by the existing grep guard's `--exclude-dir=meet-recorder`.

Usage:
  python3 scripts/check_emdash_newposts.py                 # scan all new posts
  python3 scripts/check_emdash_newposts.py <file> [file…]  # scan explicit files

Exit codes: 0 = clean, 1 = a new post has a bare em-dash in unmarked prose.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from voice_rules import HOIBOY_CUTOFF_DATE  # single source of the voice cutoff

EM_DASH = "—"
SKIP_OPEN = "<!-- iamhoi-skip -->"
SKIP_CLOSE = "<!-- iamhoi-skipend -->"
_DATE_RE = re.compile(r"^date:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
_REPO_ROOT = Path(__file__).resolve().parent.parent


def post_date(text: str) -> date | None:
    """Parse the frontmatter `date:` (first YAML block only); None if absent."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    front = text[3:end] if end != -1 else text
    m = _DATE_RE.search(front)
    return date.fromisoformat(m.group(1)) if m else None


def emdash_lines_outside_skip(text: str) -> list[int]:
    """1-based line numbers carrying a U+2014 outside iamhoi-skip blocks."""
    offenders: list[int] = []
    in_skip = False
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped == SKIP_OPEN:
            in_skip = True
            continue
        if stripped == SKIP_CLOSE:
            in_skip = False
            continue
        if not in_skip and EM_DASH in line:
            offenders.append(n)
    return offenders


def new_post_files() -> list[Path]:
    posts = _REPO_ROOT / "content" / "posts"
    return sorted(posts.rglob("index.md")) if posts.is_dir() else []


def main(argv: list[str]) -> int:
    targets = [Path(a) for a in argv] if argv else new_post_files()
    failed = False
    scanned = 0
    for path in targets:
        try:
            text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write(f"ERR: cannot read {path}: {e}\n")
            return 1
        d = post_date(text)
        if d is None or d < HOIBOY_CUTOFF_DATE:
            continue  # legacy / dateless → out of scope
        scanned += 1
        offenders = emdash_lines_outside_skip(text)
        if offenders:
            failed = True
            sys.stderr.write(
                f"ERR: em dash (U+2014) in new-post prose {path} "
                f"line(s) {', '.join(map(str, offenders))} "
                f"(wrap quoted examples in <!-- iamhoi-skip -->)\n"
            )
    if failed:
        return 1
    print(f"OK: no em dashes in {scanned} new-post file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
