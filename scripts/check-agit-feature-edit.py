#!/usr/bin/env python3
"""AGIT feature edit-check: deterministic form-vs-facts guard for member features.

Given a member's ORIGINAL submission and the AI-EDITED version, this FLAGS
candidates for a human editor to clear before publish. It does NOT adjudicate
"meaning changed" (no tool can) -- it surfaces the tells a human must look at:

  * added-fact tell: proper nouns / names / numbers / dates in EDITED not ORIGINAL
  * removed hedge words (I felt, I think, allegedly, in my experience, ...)
  * banned punctuation (em/en dash) still present in EDITED
  * large length delta between ORIGINAL and EDITED

It also stores the ORIGINAL verbatim as a legal evidence record (original +
edited + diff + check report). The Phase 4 email-approval step appends the
member's approval to the same record, and the publish gate reads it.

Honest scope: it FLAGS candidates; a human editor decides. All word lists and
thresholds live in the YAML config (scripts/agit-feature-edit-check.config.yaml),
never hardcoded here (Engineering Requirement: No Hardcoded Settings).

Records hold member PII (name, story) -- the default record dir `.agit-records/`
is gitignored; never commit a record. Point --record-dir outside the repo for
production use.

Issue: hoiung/hoiboy-uk#48 (Phase 2)
Exit codes: 0 = clean (no flags), 1 = flags need a human look, 2 = usage/IO error
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

DEFAULT_CONFIG: Path = Path(__file__).with_name("agit-feature-edit-check.config.yaml")
DEFAULT_RECORD_DIR: Path = Path(".agit-records")

# A capitalised token: starts uppercase, allows internal apostrophes and hyphens
# (O'Brien, Anne-Marie). Curly and straight apostrophes both allowed.
_CAP_TOKEN_RE = re.compile(r"[A-Z][A-Za-z’'\-]*")
# A word, for vocabulary + word-count comparisons.
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z’'\-]*")
# A number: digits with optional thousands separators and decimals.
_NUMBER_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?\b")
# Date-like tokens: month names (with optional day/year), numeric dates, years.
_MONTHS = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)
_DATE_RE = re.compile(
    r"\b(?:%s)\b(?:\s+\d{1,2}(?:st|nd|rd|th)?)?(?:,?\s+\d{4})?"  # month [day] [year]
    r"|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"  # 12/06/2019, 12-06-19
    r"|\b(?:19|20)\d{2}\b" % _MONTHS,  # bare 4-digit year
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Config:
    """Loaded, validated edit-check configuration."""

    hedge_phrases: tuple[str, ...]
    banned_chars: tuple[str, ...]
    proper_noun_stopwords: frozenset[str]
    length_delta_pct: float


@dataclass
class Flag:
    """One category of tell that needs a human look."""

    category: str
    summary: str
    items: list[str] = field(default_factory=list)


@dataclass
class CheckResult:
    """The full outcome of an edit-check."""

    flags: list[Flag]
    original_words: int
    edited_words: int
    length_delta_pct: float
    named_persons: list[str]

    @property
    def clean(self) -> bool:
        return not self.flags


def load_config(path: Path = DEFAULT_CONFIG) -> Config:
    """Load and validate the YAML config. Fails loudly on a missing/broken file."""
    if not path.is_file():
        raise FileNotFoundError(f"config not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"config is not a mapping: {path}")
    try:
        hedges = tuple(str(p) for p in raw["hedge_phrases"])
        codepoints = raw["banned_punctuation_codepoints"]
        stopwords = frozenset(str(w) for w in raw["proper_noun_stopwords"])
        delta = float(raw["thresholds"]["length_delta_pct"])
    except (KeyError, TypeError) as exc:
        raise ValueError(f"config missing required key: {exc}") from exc
    banned = tuple(chr(int(cp)) for cp in codepoints)
    return Config(
        hedge_phrases=hedges,
        banned_chars=banned,
        proper_noun_stopwords=stopwords,
        length_delta_pct=delta,
    )


def word_vocab(text: str) -> set[str]:
    """Lower-cased set of every word in the text (for case-insensitive presence)."""
    return {m.group(0).lower() for m in _WORD_RE.finditer(text)}


def extract_proper_nouns(text: str, stopwords: frozenset[str]) -> list[str]:
    """Every distinct capitalised name candidate in the text (order-preserving).

    Groups consecutive capitalised tokens into one name ("Hoi Ung", "Data
    Centre"), drops leading stop-words, and discards sequences that are entirely
    stop-words. Reused by the Phase 3 named-person clearance checklist, where
    over-inclusion is safe (a human clears each name; nobody is named on a maybe).
    """
    names: list[str] = []
    seen: set[str] = set()
    for run in re.finditer(r"[A-Z][A-Za-z’'\-]*(?:\s+[A-Z][A-Za-z’'\-]*)*", text):
        tokens = run.group(0).split()
        # Strip leading stop-words (e.g. sentence-initial "The System" -> "System").
        while tokens and tokens[0] in stopwords:
            tokens.pop(0)
        if not tokens:
            continue
        name = " ".join(tokens)
        key = name.lower()
        if key not in seen:
            seen.add(key)
            names.append(name)
    return names


def _added_tokens(pattern: re.Pattern[str], original: str, edited: str, normalise=lambda s: s) -> list[str]:
    """Tokens matching `pattern` present in edited but not original (order-preserving)."""
    original_set = {normalise(m.group(0)) for m in pattern.finditer(original)}
    added: list[str] = []
    seen: set[str] = set()
    for m in pattern.finditer(edited):
        norm = normalise(m.group(0))
        if norm not in original_set and norm not in seen:
            seen.add(norm)
            added.append(m.group(0).strip())
    return added


def _count_phrase(phrase: str, text: str) -> int:
    """Case-insensitive, whitespace-tolerant occurrence count of a (multi-word) phrase."""
    pattern = r"\b" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"\b"
    return len(re.findall(pattern, text, re.IGNORECASE))


def check_edit(original: str, edited: str, config: Config) -> CheckResult:
    """Compute every flag comparing the original submission to the edited version."""
    flags: list[Flag] = []

    # 1. Added proper nouns (case-insensitive vs the original's whole vocabulary,
    #    so a recapitalised sentence start is not mistaken for an added name).
    original_words = word_vocab(original)
    added_names = [
        tok
        for tok in dict.fromkeys(m.group(0) for m in _CAP_TOKEN_RE.finditer(edited))
        if tok.lower() not in original_words and tok not in config.proper_noun_stopwords
    ]
    if added_names:
        flags.append(Flag("added_proper_nouns",
                          "Proper nouns / names in EDITED but not ORIGINAL (added-fact tell).",
                          added_names))

    # 2. Added numbers.
    added_numbers = _added_tokens(_NUMBER_RE, original, edited, normalise=lambda s: s.replace(",", ""))
    if added_numbers:
        flags.append(Flag("added_numbers",
                          "Numbers in EDITED but not ORIGINAL (added-fact tell).",
                          added_numbers))

    # 3. Added dates.
    added_dates = _added_tokens(_DATE_RE, original, edited, normalise=lambda s: s.lower().strip())
    if added_dates:
        flags.append(Flag("added_dates",
                          "Dates in EDITED but not ORIGINAL (added-fact tell).",
                          added_dates))

    # 4. Removed hedge words (subjective -> assertion of fact risk).
    removed_hedges: list[str] = []
    for phrase in config.hedge_phrases:
        before = _count_phrase(phrase, original)
        after = _count_phrase(phrase, edited)
        if after < before:
            removed_hedges.append(f'"{phrase}" ({before} -> {after})')
    if removed_hedges:
        flags.append(Flag("removed_hedges",
                          "Hedge words removed in EDITED (may harden opinion into fact).",
                          removed_hedges))

    # 5. Banned punctuation still present in EDITED.
    present_banned = [f"U+{ord(ch):04X}" for ch in config.banned_chars if ch in edited]
    if present_banned:
        flags.append(Flag("banned_punctuation",
                          "Banned punctuation (em/en dash) still present in EDITED.",
                          present_banned))

    # 6. Large length delta.
    n_original = len(_WORD_RE.findall(original))
    n_edited = len(_WORD_RE.findall(edited))
    delta_pct = abs(n_edited - n_original) / max(n_original, 1) * 100.0
    if delta_pct > config.length_delta_pct:
        flags.append(Flag("length_delta",
                          f"Length delta {delta_pct:.0f}% exceeds {config.length_delta_pct:.0f}% "
                          f"({n_original} -> {n_edited} words).",
                          [f"{n_original} -> {n_edited} words ({delta_pct:.0f}%)"]))

    return CheckResult(
        flags=flags,
        original_words=n_original,
        edited_words=n_edited,
        length_delta_pct=round(delta_pct, 1),
        named_persons=extract_proper_nouns(edited, config.proper_noun_stopwords),
    )


def write_record(record_dir: Path, slug: str, original: str, edited: str,
                 result: CheckResult) -> Path:
    """Persist the verbatim original + edited + diff + check report as evidence.

    Returns the per-submission record directory. The ORIGINAL is stored verbatim
    and byte-for-byte -- it is the legal record and must never be rewritten by a
    later edit pass.
    """
    dest = record_dir / slug
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "original.txt").write_text(original, encoding="utf-8")
    (dest / "edited.txt").write_text(edited, encoding="utf-8")
    diff = "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        edited.splitlines(keepends=True),
        fromfile="original", tofile="edited",
    ))
    (dest / "diff.txt").write_text(diff, encoding="utf-8")
    report = {
        "slug": slug,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "clean": result.clean,
        "original_words": result.original_words,
        "edited_words": result.edited_words,
        "length_delta_pct": result.length_delta_pct,
        "named_persons": result.named_persons,
        "flags": [asdict(f) for f in result.flags],
    }
    (dest / "check.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                     encoding="utf-8")
    return dest


def format_report(result: CheckResult, record_path: Path | None) -> str:
    """Human-readable report of the check outcome."""
    lines: list[str] = []
    if result.clean:
        lines.append("CLEAN: no edit-check flags. A human editor should still eyeball it.")
    else:
        lines.append(f"FLAGGED: {len(result.flags)} categor"
                     f"{'y' if len(result.flags) == 1 else 'ies'} need a human look.")
        for flag in result.flags:
            lines.append(f"\n  [{flag.category}] {flag.summary}")
            for item in flag.items:
                lines.append(f"      - {item}")
    if result.named_persons:
        lines.append(f"\nNamed persons detected ({len(result.named_persons)}) "
                     f"-- each needs clearance before publish (Phase 3):")
        for name in result.named_persons:
            lines.append(f"      - {name}")
    if record_path is not None:
        lines.append(f"\nEvidence record written: {record_path}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic form-vs-facts edit-check for AGIT member features.")
    parser.add_argument("--original", required=True, type=Path,
                        help="Path to the member's ORIGINAL submission text.")
    parser.add_argument("--edited", required=True, type=Path,
                        help="Path to the AI-EDITED version.")
    parser.add_argument("--slug", default=None,
                        help="Record identifier (default: derived from --edited filename).")
    parser.add_argument("--record-dir", type=Path, default=DEFAULT_RECORD_DIR,
                        help=f"Where to store the evidence record (default: {DEFAULT_RECORD_DIR}). "
                             "Holds PII -- keep it gitignored / outside the repo.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="Path to the YAML config (word lists + thresholds).")
    parser.add_argument("--no-record", action="store_true",
                        help="Skip writing the evidence record (check only).")
    parser.add_argument("--json", action="store_true",
                        help="Emit the check report as JSON instead of text.")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for label, path in (("original", args.original), ("edited", args.edited)):
        if not path.is_file():
            print(f"error: {label} file not found: {path}", file=sys.stderr)
            return 2

    original = args.original.read_text(encoding="utf-8")
    edited = args.edited.read_text(encoding="utf-8")

    result = check_edit(original, edited, config)

    record_path: Path | None = None
    if not args.no_record:
        slug = args.slug or args.edited.stem
        try:
            record_path = write_record(args.record_dir, slug, original, edited, result)
        except OSError as exc:
            print(f"error: could not write record: {exc}", file=sys.stderr)
            return 2

    if args.json:
        payload = {
            "clean": result.clean,
            "original_words": result.original_words,
            "edited_words": result.edited_words,
            "length_delta_pct": result.length_delta_pct,
            "named_persons": result.named_persons,
            "flags": [asdict(f) for f in result.flags],
            "record": str(record_path) if record_path else None,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(format_report(result, record_path))

    return 1 if result.flags else 0


if __name__ == "__main__":
    sys.exit(main())
