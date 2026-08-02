#!/usr/bin/env python3
"""No `exclude_path` entry may match a path it was not written to match.

This is the root-cause gate for #55. Three separate instances of the same defect
have now shipped, all in this one ungoverned array:

  1. `docs/research` (blog-priv#55)  -- voided every citation in the research corpus
  2. `public/blogs`  (#55 Phase 1)   -- voided the rendered-link gate for EVERY post,
                                        from blog-priv#62 until #55
  3. `.git`          (#55 Phase 3)   -- matched `agit`, voiding all 18 AGIT paths
                                        including both legal-consent surfaces

The array is a list of unanchored REGEXES, not globs, and an over-broad entry
fails silently: lychee reports `0 Total` and the words "No files found for this
input source", which reads like a missing file rather than an exclusion, and it
voids even a path passed to it EXPLICITLY. Nothing failed. Three times.

The contract is defined BEHAVIOURALLY, not by mandating an anchor syntax -- any
entry form is legal so long as it excludes what it is for and leaves near-misses
checkable. Two properties are asserted:

  * everything the entry exists to exclude STAYS excluded (no silent widening of
    link-checking onto the voice-sacred legacy corpus), and
  * a plausible NEAR-MISS stays checkable (the defect above).

`test_every_entry_is_covered_by_the_corpus` is what makes this a gate rather than
a snapshot: a SIXTH entry added later with no corpus fails the suite instead of
sailing through untested. That is the difference between fixing the third
instance and preventing the fourth.

Matching model: Python `re.search` is used to model lychee's Rust `regex`
`is_match`, which is likewise an unanchored search. The model is not taken on
trust -- `test_python_regex_model_matches_real_lychee` runs the real binary and
compares verdicts, and is skipped only where lychee is not installed.

Deliberately NOT asserted: a per-entry justification comment. That would force
`exclude_path` onto multiple lines, and `check_lychee_exclude`
(`scripts/test_permalink_contract.py`) parses only the single line beginning
`exclude_path`, so a multi-line array would silently break AC 5.16 (#55 AC 4.1).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "lychee.toml"


def _entries() -> list[str]:
    return tomllib.loads(CONFIG.read_text(encoding="utf-8"))["exclude_path"]


# Per entry: paths it MUST still exclude, and near-misses it MUST NOT touch.
# The near-miss column is the whole point -- every one of these was a live defect
# before #55 Phase 4, when each entry was a bare substring.
#
# Keyed by the entry string itself, so rewriting an entry forces whoever rewrote
# it to restate what it should and should not match, rather than inheriting a
# corpus written for the old form.
CORPUS: dict[str, dict[str, list[str]]] = {
    r"(^|/)legacy(/|$)": {
        "excluded": ["legacy/export/post.md", "./legacy/export/post.md", "legacy"],
        "checkable": [
            "docs/legacy-migration.md",
            "content/posts/my-legacy-of-zouk/index.md",
            "docs/research/legacy_import_notes.md",
        ],
    },
    r"(^|/)node_modules(/|$)": {
        "excluded": ["node_modules/pkg/README.md", "./node_modules/a/b.md"],
        "checkable": ["docs/node_modules-policy.md", "docs/about-node_modules.md"],
    },
    r"(^|/)\.git(/|$)": {
        "excluded": [".git/hooks/note.md", "./.git/COMMIT_EDITMSG", "a/b/.git/x.md"],
        # The 18 tracked `agit` paths are the worked example. `.gitignore` and
        # prose about git are the same shape and were equally voided.
        "checkable": [
            "content/legal/agit-story-guidelines/index.md",
            "content/community/agit-thanks/index.md",
            "content/community/agit-featured/_index.md",
            "docs/runbooks/agit-erasure.md",
            "./content/legal/agit-story-guidelines/index.md",
            ".gitignore",
            "docs/gitops-runbook.md",
        ],
    },
    r"(^|/)content/posts(/|$)": {
        # Both invocation forms: CI passes `./**/*.md`, pre-publish.sh passes bare.
        "excluded": [
            "content/posts/some-slug/index.md",
            "./content/posts/some-slug/index.md",
        ],
        "checkable": [
            "content/posts-archive/old.md",
            "content/postscript.md",
            "./content/posts-archive/old.md",
            "content/legal/privacy/index.md",
        ],
    },
    r"(^|/)scripts/tests/fixtures(/|$)": {
        "excluded": [
            "scripts/tests/fixtures/blogs_ia/added_since_migration.txt",
            "./scripts/tests/fixtures/validate_internal_links_fixtures/bad.md",
        ],
        "checkable": [
            "scripts/tests/fixtures-readme.md",
            "scripts/tests/test_something.py",
        ],
    },
}


def _matches(entry: str, path: str) -> bool:
    return re.search(entry, path) is not None


def test_every_entry_is_covered_by_the_corpus():
    """A new entry with no corpus must FAIL, not pass untested.

    Without this, the gate degrades into a snapshot of the five entries that
    existed in August 2026 and a sixth over-broad one would ship exactly as the
    first three did.
    """
    live, covered = set(_entries()), set(CORPUS)
    assert live == covered, (
        "lychee.toml exclude_path and this test's CORPUS have diverged. "
        f"entries with no corpus: {sorted(live - covered)}; "
        f"corpus for entries that no longer exist: {sorted(covered - live)}. "
        "Every entry needs a path it must still exclude AND a near-miss it must "
        "leave checkable. Three shipped defects came from an entry nobody tested."
    )


@pytest.mark.parametrize("entry", list(CORPUS))
def test_entry_still_excludes_what_it_is_for(entry: str):
    for path in CORPUS[entry]["excluded"]:
        assert _matches(entry, path), (
            f"exclude_path entry {entry!r} no longer excludes {path!r}. "
            "Loosening an entry re-enables link-checking over paths that are "
            "excluded on purpose (the voice-sacred legacy corpus, vendored "
            "node_modules, test fixtures holding deliberately-broken links)."
        )


@pytest.mark.parametrize("entry", list(CORPUS))
def test_entry_does_not_match_a_near_miss(entry: str):
    """THE defect. Every one of these matched before #55 Phase 4."""
    for path in CORPUS[entry]["checkable"]:
        assert not _matches(entry, path), (
            f"exclude_path entry {entry!r} WRONGLY MATCHES {path!r}, which is not "
            "a path it was written to exclude. That path is now silently "
            "unchecked: lychee reports `0 Total` and 'No files found for this "
            "input source', which reads like a missing file, and the exclusion "
            "voids even an explicitly-passed path. This is the third-time defect "
            "(#55): `docs/research`, then `public/blogs`, then `.git` matching "
            "`agit`."
        )


def test_no_entry_matches_a_tracked_path_that_must_stay_checkable():
    """Whole-tree scan, so a future over-broad entry is caught against reality.

    The per-entry corpus above is hand-written and therefore only as imaginative
    as its author. This asserts against every file actually in the repo: nothing
    outside the four directories that are excluded ON PURPOSE may be matched.
    `.git` matching `agit` would have been caught here by 18 real paths.
    """
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    assert tracked, "git ls-files returned nothing; refusing to pass vacuously"

    intentional = ("legacy/", "node_modules/", "content/posts/", "scripts/tests/fixtures/")
    entries = _entries()
    wrong: list[str] = []
    for path in tracked:
        if path.startswith(intentional):
            continue
        for entry in entries:
            if _matches(entry, path):
                wrong.append(f"{entry!r} matches {path!r}")

    assert not wrong, (
        "exclude_path entries silently void tracked files that must stay "
        "link-checked:\n  " + "\n  ".join(wrong[:20])
    )


def test_content_posts_is_excluded_in_both_invocation_forms():
    """CI passes `./**/*.md`; pre-publish.sh passes bare paths.

    An entry that works for only one form is the trap #55 AC 3.1 documents: a
    plain `^` anchor looks tighter and silently disables the exclusion for the
    other caller.
    """
    entry = next(e for e in _entries() if "content/posts" in e)
    for path in ("content/posts/x/index.md", "./content/posts/x/index.md"):
        assert _matches(entry, path), f"{entry!r} misses {path!r}"


def test_the_array_is_a_single_line():
    """`check_lychee_exclude` parses only the line starting `exclude_path`.

    A multi-line array silently breaks that parser and with it AC 5.16, which is
    why this suite asserts no per-entry justification comment (#55 AC 4.1).
    """
    line = next(
        (ln for ln in CONFIG.read_text(encoding="utf-8").splitlines()
         if ln.startswith("exclude_path")),
        None,
    )
    assert line is not None, "lychee.toml has no line starting `exclude_path`"
    assert line.rstrip().endswith("]"), (
        "exclude_path spans multiple lines. scripts/test_permalink_contract.py "
        "reads only the first line, so a multi-line array makes AC 5.16 assert "
        "against a fragment."
    )


@pytest.mark.skipif(shutil.which("lychee") is None, reason="lychee not installed")
def test_python_regex_model_matches_real_lychee(tmp_path: Path):
    """Validate the model instead of assuming it.

    Everything above models lychee's Rust `regex` crate with Python `re.search`.
    If that model is wrong, every assertion here is theatre. This runs the real
    binary over a file whose path should be excluded and one that should not, and
    checks the verdicts agree with the model.
    """
    cfg = tmp_path / "lychee.toml"
    cfg.write_text('exclude_path = ["(^|/)\\\\.git(/|$)"]\n', encoding="utf-8")

    (tmp_path / ".git").mkdir()
    (tmp_path / "agit-notes").mkdir()
    excluded = tmp_path / ".git" / "note.md"
    checkable = tmp_path / "agit-notes" / "note.md"
    for f in (excluded, checkable):
        f.write_text("[x](https://example.com/a)\n", encoding="utf-8")

    def total(target: Path) -> int:
        out = subprocess.run(
            ["lychee", "--config", str(cfg), "--no-progress", "--offline", str(target)],
            capture_output=True, text=True, cwd=tmp_path,
        )
        m = re.search(r"(\d+) Total", out.stdout + out.stderr)
        assert m, f"could not parse a Total from lychee output:\n{out.stdout}{out.stderr}"
        return int(m.group(1))

    entry = r"(^|/)\.git(/|$)"
    assert total(excluded) == 0, "real lychee did NOT exclude a .git path"
    assert _matches(entry, str(excluded)), "model disagrees: it should match"
    assert total(checkable) > 0, "real lychee excluded an agit path (the #55 defect)"
    assert not _matches(entry, str(checkable)), "model disagrees: it should not match"
