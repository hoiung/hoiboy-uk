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
