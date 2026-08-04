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
  a standalone line is exactly `<!-- iamhoi -->`    -> PASS (wrapped; a mere
                                                      mention of the token in
                                                      prose does NOT count)
  body has first-person prose AND no marker        -> FAIL exit 1

`--require-all` replaces that last row with "body has ANY prose AND no marker
-> FAIL", dropping the pronoun heuristic entirely. See `needs_markers` for
which consumers want which mode and why.

First-person detection:
  - regex `\\b(I|I'm|I've|Hoi)\\b` (case-sensitive) plus `\\b(my|me)\\b`
    (case-insensitive). Any single hit triggers detection.
  - KEEP_LIST vocabulary signal removed after Issue #3 Sonnet review surfaced
    false-positive risk: a non-Hoi technical post quoting methodology terms
    (`leverage`, `robust`, `coach`, `back to basics`, etc) would FAIL despite
    not being Hoi-voice. Hoi's prose is reliably first-person; KEEP_LIST
    without first-person is generic professional vocabulary.

Tracker: private bake-off teaser issue (Phase 1 infra)
Exit codes:
  0 = looked, and every prose file is wrapped
  1 = looked, and wrapping is missing
  2 = could NOT look: the gate's own coverage failed (no files collected, a
      declared input absent, or a surface it could not read). Distinct from 0
      on purpose -- "no violations" and "no evidence" are opposite outcomes
      an exit-code check alone cannot tell apart (hoiboy-uk#56).
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from voice_rules import HOIBOY_CUTOFF_DATE

# Pre-compiled patterns (compile once, reuse per file)
_FIRST_PERSON_RE = re.compile(r"\b(I|I'm|I've|Hoi)\b")
_FIRST_PERSON_LOWER_RE = re.compile(r"\b(my|me)\b", re.IGNORECASE)
_FRONTMATTER_DATE_RE = re.compile(r"^date:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
_MARKER_OPEN = "<!-- iamhoi -->"
_MARKER_CLOSE = "<!-- iamhoiend -->"
_MARKER_EXEMPT = "<!-- iamhoi-exempt -->"


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


def has_marker(body: str) -> bool:
    """True if any STANDALONE line is exactly `<!-- iamhoi -->` (a real region open).

    Mirrors the region-open detection in check-ai-writing-tells.py
    (`line.strip() == OPEN`) and is_exempt above. A plain `in body` substring
    test would let a file that merely *mentions* the marker token (e.g.
    backtick-wrapped in documentation prose, as the voice/tones/*.md specs do)
    bypass the gate without ever wrapping its first-person prose — defeating
    the gate's entire purpose. The marker must open a region on its own line.
    """
    return any(line.strip() == _MARKER_OPEN for line in body.split("\n"))


def has_voice_prose(body: str) -> bool:
    """Return True if body contains first-person SINGULAR prose (I, I'm, I've, Hoi, my, me).

    First-person pronouns are the only detection signal. The KEEP_LIST
    vocabulary path was removed after Issue #3 Sonnet review surfaced false-
    positive risk: a non-Hoi technical post quoting methodology terms
    (`leverage`, `robust`, `coach`, `back to basics`, etc) would FAIL despite
    not being Hoi-voice. Hoi's prose is reliably first-person; KEEP_LIST
    without first-person is generic professional vocabulary.

    COVERAGE BOUNDARY OF THIS PREDICATE — it is first-person SINGULAR only.
    First-person PLURAL ("we", "our", "us") and THIRD-PERSON copy ("The
    charity delivers…") raise no signal here, so on the default path this
    checker never demands markers around them. Frontmatter is stripped before
    the check, so `title:` and `description:` are likewise never seen.

    That is correct for the blog/CV surfaces this predicate was built for
    (Hoi writes those in the first person singular) and WRONG for a website,
    whose dominant register is exactly the uncovered one. Do not widen this
    regex to fix that: `--require-all` (see `needs_markers`) is the mode a
    website consumer wires, and it makes the pronoun question moot instead of
    trading one blind spot for a false-positive class.
    """
    return bool(
        _FIRST_PERSON_RE.search(body) or _FIRST_PERSON_LOWER_RE.search(body)
    )


def has_prose(body: str) -> bool:
    """True if the body carries any content line that is not a marker.

    Marker lines and blank lines do not count, so a frontmatter-only stub
    (a Hugo `_index.md` that sets `title:` and nothing else) is NOT treated
    as prose and never fails `--require-all`. Without this a site's section
    landings would all go red on day one with nothing to guard.
    """
    markers = {_MARKER_OPEN, _MARKER_EXEMPT, "<!-- iamhoiend -->",
               "<!-- iamhoi-skip -->", "<!-- iamhoi-skipend -->"}
    return any(
        line.strip() and line.strip() not in markers
        for line in body.split("\n")
    )


def unwrapped_prose(body: str) -> list[int]:
    """Body-relative line numbers of prose sitting OUTSIDE every iamhoi region.

    `has_marker` is satisfied by a single region anywhere in the file, so on its
    own it cannot tell "this page is covered" from "this page has one covered
    paragraph". Measured on a file with one wrapped sentence and an unwrapped one
    carrying a banned word and an em dash: the wrapping check and the tells
    scanner BOTH exit 0. That is the same composed hole `--require-all` closes at
    the file level, one level down, so `--require-all` closes it here too.

    Markers, blank lines, whole-line Hugo shortcodes and whole-line HTML comments
    are not prose. Shortcodes are template calls rather than copy, and demanding
    an author wrap `{{< figure … >}}` would be the kind of false positive that
    gets a hook switched off.
    """
    stray: list[int] = []
    in_region = False
    for n, raw in enumerate(body.split("\n"), 1):
        line = raw.strip()
        if line == _MARKER_OPEN:
            in_region = True
            continue
        if line == _MARKER_CLOSE:
            in_region = False
            continue
        if in_region or not line:
            continue
        if line.startswith("{{") and line.endswith("}}"):
            continue
        if line.startswith("<!--") and line.endswith("-->"):
            continue
        stray.append(n)
    return stray


def needs_markers(body: str, require_all: bool) -> bool:
    """Does this body have to be wrapped? The one place the two modes differ.

    DEFAULT (`require_all=False`) — pronoun-triggered. A file is only forced
    to carry markers when it contains first-person singular prose. Built for
    blog/CV repos, where the corpus is mixed: legacy imports, third-party
    quotes and generated boilerplate sit beside Hoi-voice prose, and a blanket
    demand would fail on all of it.

    `--require-all` — every file with prose must be marked or exempted, with
    no pronoun test at all. This is the mode a WEBSITE consumer wires, and it
    exists because the default composes into a hole there rather than a
    narrow one:

      `check-ai-writing-tells.py --mode blog` reads ONLY inside
      `<!-- iamhoi --> … <!-- iamhoiend -->` regions. So on unmarked prose the
      tells scanner is silent BY DESIGN and this checker is what is supposed
      to force the wrapping. When the pronoun trigger misses — "We run classes
      for beginners", "The charity delivers…" — nothing demands markers, so
      nothing is ever scanned. Measured on a fixture carrying six banned words
      and an em dash in first-person-plural prose: both hooks exit 0 on the
      default path, both fail under `--require-all`.

    Widening the pronoun regex to `we|our|us` was considered and rejected as
    the remedy. It re-introduces the false-positive class the KEEP_LIST removal
    eliminated (codes of conduct, job descriptions and quoted policy are
    written in exactly that register), it still leaves third-person copy
    uncovered, and it would change behaviour in every repo this file is
    vendored to. `--require-all` is opt-in per repo, covers every register,
    and routes the false-positive case through the carve-outs that already
    exist for it: `<!-- iamhoi-skip -->` around a quoted block, or
    `<!-- iamhoi-exempt -->` as the first non-blank line of a wholly
    third-party file.
    """
    return has_prose(body) if require_all else has_voice_prose(body)


def check_file(
    path: Path, check_only_new: bool, require_all: bool = False
) -> tuple[bool, str]:
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
    offset = text[: len(text) - len(body)].count("\n")  # body line -> file line

    if is_exempt(body):
        return True, ""

    if has_marker(body):
        stray = unwrapped_prose(body) if require_all else []
        if stray:
            shown = ", ".join(str(n + offset) for n in stray[:10])
            more = f" (+{len(stray) - 10} more)" if len(stray) > 10 else ""
            return False, (
                f"ERR: {path}: prose outside the iamhoi markers at line(s) "
                f"{shown}{more}. One marked region does not cover the file — "
                f"extend the region, or wrap the block and carve it out with "
                f"`<!-- iamhoi-skip --> ... <!-- iamhoi-skipend -->` inside."
            )
        return True, ""

    if needs_markers(body, require_all):
        what = "prose" if require_all else "Hoi-voice prose"
        return False, (
            f"ERR: {path}: file contains {what} but no iamhoi wrapping. "
            f"Wrap each section in `<!-- iamhoi --> ... <!-- iamhoiend -->`, OR "
            f"add `<!-- iamhoi-exempt -->` as the first non-blank line for "
            f"whole-file bypass."
        )

    return True, ""


def gather_files(args: list[str], check_only_new: bool) -> list[Path]:
    """Resolve CLI args to a list of .md files. Default: content/**/*.md.

    The default used to be `content/posts` alone, while the pre-commit hook
    that runs this same script selects files with `pass_filenames` over a
    WIDER pattern. So the CI step calling itself the "CI mirror of pre-commit
    hook" scanned a strictly smaller set: `content/hire-hoi/**/*.md` is
    covered by pre-commit and was examined by NO CI step. A green CI run
    therefore asserted a property of pages nothing had opened.

    `content/` is the honest default: it is the whole voice surface, and it
    matches the sibling `check-ai-writing-tells.py` CI step, which already
    scans `content/ docs/ layouts/` explicitly. Legacy pages stay exempt via
    the date filter, and a non-voice page opts out with `<!-- iamhoi-exempt -->`.
    """
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
                # A named path that does not exist, or is not .md, matched
                # neither branch above and left no trace: the caller asked
                # "is this file wrapped?" and got exit 0 without an answer.
                # Refusing to judge is a different outcome from judging clean,
                # and only one of them may exit 0.
                raise SystemExit(
                    f"[FAIL] [vacuous-gate] check-iamhoi-wrapping: cannot scan "
                    f"{arg} ({'not a .md file' if p.exists() else 'does not exist'}). "
                    f"Passing it silently would report OK for a file that was "
                    f"never opened."
                )
    else:
        content = repo_root / "content"
        if not content.exists():
            # `if content.exists()` used to fall through to `return []`, and the
            # caller's `if not files: return 0` turned a missing content tree
            # into a clean bill of health for the whole voice surface.
            raise SystemExit(
                f"[FAIL] [vacuous-gate] check-iamhoi-wrapping: {content} does not "
                f"exist, so the default scan collected nothing. Either this is not "
                f"a checkout of the repo, or the content root moved and this "
                f"default is stale."
            )
        files.extend(sorted(content.rglob("*.md")))
    return files


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Enforce iamhoi-marker wrapping on new Hoi-voice posts. "
            "Default scope: content/**/*.md."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Files or directories to check. Default: content/.",
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
    parser.add_argument(
        "--require-all",
        dest="require_all",
        action="store_true",
        default=False,
        help=(
            "Demand markers on EVERY file carrying prose, not only files with "
            "first-person singular pronouns. Website mode: covers we/our/us "
            "and third-person copy, which the default trigger misses."
        ),
    )
    args = parser.parse_args()

    files = gather_files(args.paths, args.check_only_new)
    if not files:
        # gather_files now fails loudly on a missing root or an unresolvable
        # argument, so reaching here means the roots existed and held no .md at
        # all. That is still a scan of nothing, and still may not exit 0.
        print(
            "[FAIL] [vacuous-gate] check-iamhoi-wrapping: collected 0 markdown "
            "files, so every wrapping assertion held vacuously.",
            file=sys.stderr,
        )
        return 2

    failures: list[str] = []
    for f in files:
        ok, msg = check_file(f, args.check_only_new, args.require_all)
        if not ok:
            failures.append(msg)

    if failures:
        for msg in failures:
            print(msg, file=sys.stderr)
        print(
            f"\n{len(failures)} file(s) missing iamhoi wrapping. "
            f"See dotfiles/voice/base/VOICE_PROFILE.md Section 8 + AP #15.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
