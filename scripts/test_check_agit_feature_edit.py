#!/usr/bin/env python3
"""Unit tests for check-agit-feature-edit.py (hoiboy-uk #48 Phase 2).

Two layers:
  1. Function-level: check_edit() fires exactly the right flag for each tell
     category, stays clean on a form-only tidy, and does NOT false-flag a
     recapitalised sentence start as an added proper noun. extract_proper_nouns()
     (reused by the Phase 3 named-person gate) returns names and drops stop-words.
  2. CLI-level: the script exits 1 when flagged, 0 when clean, 2 on a missing file,
     and stores the ORIGINAL byte-for-byte as the legal evidence record.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
GATE = SCRIPTS / "check-agit-feature-edit.py"

sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("agit_edit_check", GATE)
aec = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = aec  # required before exec for dataclass annotations
_spec.loader.exec_module(aec)

CFG = aec.load_config()
EM_DASH = chr(0x2014)


def _cats(result) -> set[str]:
    return {f.category for f in result.flags}


# ---------------------------------------------------------------- function layer

def test_config_loads_expected_shape():
    assert CFG.hedge_phrases and "I felt" in CFG.hedge_phrases
    assert EM_DASH in CFG.banned_chars
    assert "The" in CFG.proper_noun_stopwords
    assert CFG.length_delta_pct == 40


def test_added_proper_noun_flagged():
    r = aec.check_edit("we shipped the release", "We shipped the release with Priya", CFG)
    assert "added_proper_nouns" in _cats(r)
    assert "Priya" in r.flags[0].items


def test_recapitalised_sentence_start_not_flagged():
    # "The"/"We" appear capitalised in edited only because sentences were split;
    # the words existed in the original, so this must NOT read as an added name.
    r = aec.check_edit("the system worked. we shipped it.",
                       "The system worked. We shipped it.", CFG)
    assert "added_proper_nouns" not in _cats(r)
    assert r.clean


def test_added_number_flagged():
    r = aec.check_edit("we cut the build time a lot",
                       "we cut the build time by 90 percent", CFG)
    assert "added_numbers" in _cats(r)
    assert "90" in r.flags[0].items


def test_added_date_flagged():
    r = aec.check_edit("I joined the team and it grew",
                       "I joined the team in March 2019 and it grew", CFG)
    assert "added_dates" in _cats(r)


def test_removed_hedge_flagged():
    r = aec.check_edit("I think the vendor was careless with the rollout",
                       "The vendor was careless with the rollout", CFG)
    assert "removed_hedges" in _cats(r)
    assert any("I think" in item for item in
               next(f for f in r.flags if f.category == "removed_hedges").items)


def test_banned_punctuation_flagged():
    r = aec.check_edit("a short clean line here",
                       "a short clean line" + EM_DASH + "here", CFG)
    assert "banned_punctuation" in _cats(r)


def test_length_delta_flagged():
    r = aec.check_edit("one two three four five six seven eight nine ten",
                       "one two three", CFG)
    assert "length_delta" in _cats(r)


def test_clean_tidy_no_flags():
    r = aec.check_edit("we did the work and it just worked",
                       "We did the work, and it just worked.", CFG)
    assert r.clean
    assert not r.flags


def test_extract_proper_nouns_lists_names_drops_stopwords():
    names = aec.extract_proper_nouns(
        "The team at Canonical shipped it. Hoi Ung led the build in London.",
        CFG.proper_noun_stopwords)
    assert "Canonical" in names
    assert "Hoi Ung" in names
    assert "London" in names
    assert "The" not in names  # leading stop-word stripped


def test_named_persons_surfaced_on_result():
    r = aec.check_edit("we shipped it", "We shipped it with help from Sarah and Wei", CFG)
    assert "Sarah" in r.named_persons
    assert "Wei" in r.named_persons


def test_name_colliding_with_english_word_is_surfaced():
    # "So", "An", "No" are real given names/surnames -- they must NOT be silently
    # dropped as stop-words (would bypass the named-person clearance gate).
    sw = CFG.proper_noun_stopwords
    assert "So" in aec.extract_proper_nouns("My colleague So helped me debug.", sw)
    assert "No" in aec.extract_proper_nouns("No mentored the whole team well.", sw)
    r = aec.check_edit("My friend helped me that year.",
                       "My friend An helped me that year.", CFG)
    assert "An" in r.named_persons
    assert "added_proper_nouns" in _cats(r)  # the added name is flagged too


def test_diacritic_names_captured_whole():
    names = aec.extract_proper_nouns(
        "Nguyễn Văn An mentored me. Trần Thị Hoa and Björk too.",
        CFG.proper_noun_stopwords)
    assert "Nguyễn Văn An" in names   # not truncated to "Nguy"
    assert "Trần Thị Hoa" in names
    assert "Björk" in names           # not truncated to "Bj"


def test_caseless_script_names_surfaced():
    # CJK / Hangul / Kana have no upper/lower case, so an isupper() gate would make a
    # real name in native script invisible to the named-person clearance gate.
    sw = CFG.proper_noun_stopwords
    assert "陳大文" in aec.extract_proper_nouns("My mentor 陳大文 believed in me.", sw)
    assert "김민준" in aec.extract_proper_nouns("Thanks to 김민준 for the review.", sw)
    # An added CJK name is flagged AND surfaced for clearance.
    r = aec.check_edit("I want to thank my mentor for believing in me.",
                       "I want to thank my mentor 陳大文 for believing in me.", CFG)
    assert "added_proper_nouns" in _cats(r)
    assert "陳大文" in r.named_persons


def test_bare_month_word_is_not_a_date():
    # The modal "may" / verb "march" must not spuriously flag added_dates.
    r = aec.check_edit("It wasn't handled well.",
                       "It may not have been handled well.", CFG)
    assert "added_dates" not in _cats(r)


def test_real_month_year_still_flagged():
    r = aec.check_edit("I joined the team.", "I joined the team in May 2019.", CFG)
    assert "added_dates" in _cats(r)
    dates = next(f for f in r.flags if f.category == "added_dates")
    assert any("May 2019" in item for item in dates.items)  # captured the full year


# --------------------------------------------------------------------- CLI layer

def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def _run(args: list[str]):
    return subprocess.run([sys.executable, str(GATE), *args],
                          capture_output=True, text=True)


def test_cli_exit_1_when_flagged(tmp_path):
    orig = _write(tmp_path, "o.txt", "we shipped the thing")
    edit = _write(tmp_path, "e.txt", "We shipped the thing with Priya in 2021")
    res = _run(["--original", str(orig), "--edited", str(edit),
                "--record-dir", str(tmp_path / "rec")])
    assert res.returncode == 1
    assert "FLAGGED" in res.stdout


def test_cli_exit_0_when_clean(tmp_path):
    orig = _write(tmp_path, "o.txt", "we did the work and it worked well enough")
    edit = _write(tmp_path, "e.txt", "We did the work, and it worked well enough.")
    res = _run(["--original", str(orig), "--edited", str(edit),
                "--record-dir", str(tmp_path / "rec")])
    assert res.returncode == 0
    assert "CLEAN" in res.stdout


def test_cli_exit_2_on_missing_file(tmp_path):
    res = _run(["--original", str(tmp_path / "nope.txt"),
                "--edited", str(tmp_path / "also-nope.txt"), "--no-record"])
    assert res.returncode == 2
    assert "not found" in res.stderr


def test_record_stores_original_verbatim(tmp_path):
    original_text = "I felt it went well.\nWe shipped it.\n"
    orig = _write(tmp_path, "o.txt", original_text)
    edit = _write(tmp_path, "e.txt", "It went well. We shipped it in 2020.")
    rec = tmp_path / "rec"
    _run(["--original", str(orig), "--edited", str(edit),
          "--slug", "sample-1", "--record-dir", str(rec)])
    stored = (rec / "sample-1" / "original.txt").read_text(encoding="utf-8")
    assert stored == original_text  # byte-for-byte legal record
    report = json.loads((rec / "sample-1" / "check.json").read_text(encoding="utf-8"))
    assert report["clean"] is False
    assert report["slug"] == "sample-1"


def test_rewrite_same_original_is_idempotent(tmp_path):
    # The normal "fix the edit and re-check" flow: same original, new edit.
    # original.txt stays byte-for-byte; edited.txt / check.json update.
    rec = tmp_path / "rec"
    original_text = "I felt it went well. We shipped it.\n"
    r1 = aec.check_edit(original_text, "It went well. We shipped it.", aec.load_config())
    aec.write_record(rec, "s", original_text, "It went well. We shipped it.", r1)
    r2 = aec.check_edit(original_text, "It went well; we shipped it cleanly.", aec.load_config())
    aec.write_record(rec, "s", original_text, "It went well; we shipped it cleanly.", r2)
    assert (rec / "s" / "original.txt").read_text(encoding="utf-8") == original_text
    assert (rec / "s" / "edited.txt").read_text(encoding="utf-8") == "It went well; we shipped it cleanly."


def test_rewrite_different_original_raises_and_preserves_record(tmp_path):
    # A slug collision / re-typed original must NOT clobber the legal record.
    rec = tmp_path / "rec"
    first = "First member's true original story."
    r1 = aec.check_edit(first, "First edited.", aec.load_config())
    aec.write_record(rec, "s", first, "First edited.", r1)
    r2 = aec.check_edit("A different second story.", "Second edited.", aec.load_config())
    try:
        aec.write_record(rec, "s", "A different second story.", "Second edited.", r2)
        assert False, "expected RecordIntegrityError on differing original"
    except aec.RecordIntegrityError:
        pass
    assert (rec / "s" / "original.txt").read_text(encoding="utf-8") == first  # preserved


def test_cli_exit_2_on_original_overwrite(tmp_path):
    rec = tmp_path / "rec"
    o1 = _write(tmp_path, "o1.txt", "Original one, verbatim.")
    o2 = _write(tmp_path, "o2.txt", "A wholly different original.")
    edit = _write(tmp_path, "e.txt", "Edited body.")
    _run(["--original", str(o1), "--edited", str(edit), "--slug", "x", "--record-dir", str(rec)])
    res = _run(["--original", str(o2), "--edited", str(edit), "--slug", "x", "--record-dir", str(rec)])
    assert res.returncode == 2
    assert "must never be rewritten" in res.stderr
    assert (rec / "x" / "original.txt").read_text(encoding="utf-8") == "Original one, verbatim."


def test_json_output_is_valid(tmp_path):
    orig = _write(tmp_path, "o.txt", "we shipped it")
    edit = _write(tmp_path, "e.txt", "We shipped it with Ade")
    res = _run(["--original", str(orig), "--edited", str(edit),
                "--no-record", "--json"])
    payload = json.loads(res.stdout)
    assert payload["clean"] is False
    assert "Ade" in payload["named_persons"]


if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
