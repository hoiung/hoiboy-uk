#!/usr/bin/env python3
"""
Word-count ceiling guard for hoiboy.uk new posts.

Blocks commit / fails CI if a new post (date >= HOIBOY_CUTOFF_DATE) exceeds
WORDCOUNT_CEILING words after markup stripping. Legacy posts
(date < HOIBOY_CUTOFF_DATE) are silently skipped (voice-sacred corpus,
e.g. woodsmoke-bushcraft-course at 11,858 words).

Ceiling set from 14_BLOG_CRAFT.md line 17 rule: drafts >3000 words must be
split or cut back. Negative example on file: sst3-ai-harness-reshapeable-knife
(5,143 words, 15 Apr 2026). Exactly 3000 passes; strictly greater fails.

Strip sequence is deliberate: Hugo shortcodes, iamhoi markers, code blocks,
and URLs inflate naive wc counts on long technical posts. Counting only the
prose readers actually read is the point of the ceiling.

Issue: hoiung/hoiboy-uk#10
Exit codes: 0 = pass (silent), 1 = fail (block commit / fail CI)
"""

from __future__ import annotations

import re
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

from voice_rules import HOIBOY_CUTOFF_DATE

WORDCOUNT_CEILING: int = 3000

# Long-form exemption list. These are deliberate long-form flagship
# posts: intentional editorial exemptions from WORDCOUNT_CEILING, not a
# mechanical bypass. Intentionally NOT a frontmatter opt-out — adding a slug
# is an editorial decision and requires a code review. The live negative
# example referenced in docs/research/14_BLOG_CRAFT.md line 17 is
# sst3-ai-harness-reshapeable-knife. Future drafts (date >= 2026-04-07) without
# a slug here must stay <= WORDCOUNT_CEILING.
GRANDFATHERED_SLUGS: frozenset[str] = frozenset({
    "sst3-ai-harness-reshapeable-knife",
    "every-book-ive-read-in-20-years",
    "scaling-without-quality",
    "maturity-grading-from-backtest-data",
    "how-to-actually-build-communities",  # flagship community manifesto, operator-approved 2026-07-13
})

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
# A comment body may not itself contain `<!--`. Without that guard an
# unterminated `<!--` paired with the NEXT `-->` however far away - typically
# the closing `<!-- iamhoiend -->` marker - and every word between them was
# deleted before counting. That is fail-OPEN on a word-count ceiling: the post
# is measured as shorter than it is, so an over-3000-word post passes.
_HTML_COMMENT_RE = re.compile(r"<!--(?:(?!<!--)[\s\S])*?-->")
# Same fail-OPEN class as _HTML_COMMENT_RE above, and the asymmetry with the
# correctly-anchored _FRONTMATTER_RE was the tell. The old pattern was
# ```` ```.*?``` ```` with re.DOTALL: no line anchor and no fence-length rule, so
# it paired ANY two backtick runs. One stray ``` mentioned in prose (`type ``` to
# open a block`) shifts the pairing by one, and every word between that mention
# and the next real fence is deleted before counting. Measured on a 400-word
# fixture with one stray fence: 400 words counted as 10. The post is measured as
# shorter than it is, so one over the ceiling passes the gate.
# Now: a fence must START a line, be 3+ backticks or tildes, and be closed by a
# run of the same character at line start. An UNTERMINATED fence deliberately
# matches nothing, leaving its text counted as prose -- over-counting is the safe
# direction for a ceiling.
_FENCED_CODE_RE = re.compile(
    r"^(?P<fence>`{3,}|~{3,})[^\n]*\n"
    r"[\s\S]*?"
    r"^(?P=fence)`*~*[ \t]*$",
    re.MULTILINE,
)
_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_SHORTCODE_ANGLE_RE = re.compile(r"\{\{<.*?>\}\}", re.DOTALL)
_SHORTCODE_PERCENT_RE = re.compile(r"\{\{%.*?%\}\}", re.DOTALL)
_REF_LINK_DEF_RE = re.compile(r"^\s*\[[^\]]+\]:\s+\S+\s*$", re.MULTILINE)
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WORD_RE = re.compile(r"\w+")


def strip_markup(text: str) -> str:
    """Apply the 9-step strip sequence before tokenisation."""
    text = _FRONTMATTER_RE.sub("", text, count=1)
    text = _HTML_COMMENT_RE.sub("", text)
    text = _FENCED_CODE_RE.sub("", text)
    text = _INLINE_CODE_RE.sub("", text)
    text = _SHORTCODE_ANGLE_RE.sub("", text)
    text = _SHORTCODE_PERCENT_RE.sub("", text)
    text = _REF_LINK_DEF_RE.sub("", text)
    text = _IMAGE_RE.sub(r"\1", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _HTML_TAG_RE.sub("", text)
    return text


def count_words(markdown: str) -> int:
    stripped = strip_markup(markdown)
    return len(_WORD_RE.findall(stripped))


def parse_post_date(text: str, path: Path) -> date:
    """
    Parse the frontmatter `date:` field via PyYAML.
    Fails loudly on malformed frontmatter, missing date, or bad date type.
    """
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        raise ValueError(f"Invalid frontmatter in {path}: no YAML block found")
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid frontmatter in {path}: {exc}") from exc
    if not isinstance(data, dict) or "date" not in data:
        raise ValueError(f"Missing 'date' field in frontmatter: {path}")
    raw = data["date"]
    # datetime is a subclass of date; coerce first so timestamp strings
    # like `date: 2026-04-21T09:00:00Z` do not crash the later cmp.
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(
                f"Invalid 'date' value in frontmatter ({path}): {raw!r}: {exc}"
            ) from exc
    raise ValueError(
        f"Invalid 'date' type in frontmatter ({path}): expected date or YYYY-MM-DD string, got {type(raw).__name__}"
    )


def check_file(path: Path) -> int:
    if not path.exists():
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        return 1
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        print(f"ERROR: Encoding error in {path}: {exc}", file=sys.stderr)
        return 1

    try:
        post_date = parse_post_date(text, path)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if post_date < HOIBOY_CUTOFF_DATE:
        return 0

    if path.parent.name in GRANDFATHERED_SLUGS:
        return 0

    words = count_words(text)
    if words <= WORDCOUNT_CEILING:
        return 0

    excess = words - WORDCOUNT_CEILING
    print(
        f"ERROR: {path} exceeds word-count ceiling\n"
        f"  Current: {words} words\n"
        f"  Ceiling: {WORDCOUNT_CEILING} words\n"
        f"  Excess: {excess} words\n"
        f"  Remediation: trim the draft or split into two posts. "
        f"See docs/research/14_BLOG_CRAFT.md line 17.",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str]) -> int:
    if not argv:
        # Finding N7. The CI step is
        #   python3 scripts/check_wordcount.py $(git ls-files 'content/posts/*/index.md')
        # so if that glob ever stops matching -- a renamed directory, a changed
        # bundle layout -- argv arrives empty, this returned 0, and the word-count
        # ceiling silently stopped being enforced with CI green. An empty argument
        # list is a fact about the CALLER, not a clean result.
        #
        # The pre-commit hook cannot reach this: it is `pass_filenames: true` with
        # a `files:` filter and `always_run: false`, so pre-commit SKIPS it when
        # nothing matches rather than invoking it with no arguments. Verified in
        # .pre-commit-config.yaml before changing this.
        print(
            "[FAIL] [vacuous-gate] check_wordcount: no files given, so the ceiling "
            "was enforced against nothing. The caller's glob matched no post; "
            "check it before trusting this gate's silence.",
            file=sys.stderr,
        )
        return 2
    rc = 0
    for arg in argv:
        rc |= check_file(Path(arg))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
