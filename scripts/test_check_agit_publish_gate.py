#!/usr/bin/env python3
"""Unit tests for check-agit-publish-gate.py (hoiboy-uk #48 Phase 3).

Covers the hard-gate logic: a fresh record writes a clearance template and
blocks; a pending / note-less / missing name blocks; permissioned-with-note and
anonymised clear; unreviewed edit-check flags block; a clean edit-check needs no
flag review; and (Phase 4 leg) an unapproved approval.json blocks. Plus CLI exit
codes 0 cleared / 1 blocked / 2 missing record.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
GATE = SCRIPTS / "check-agit-publish-gate.py"

sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("agit_publish_gate", GATE)
apg = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = apg
_spec.loader.exec_module(apg)


def _record(tmp_path: Path, named_persons, clean, flags=None) -> Path:
    rec = tmp_path / "sample"
    rec.mkdir()
    (rec / "check.json").write_text(json.dumps({
        "slug": "sample",
        "clean": clean,
        "named_persons": named_persons,
        "flags": flags or [],
    }), encoding="utf-8")
    return rec


def _clearance(rec: Path, flags_cleared, persons: dict) -> None:
    (rec / "clearance.json").write_text(json.dumps({
        "flags_cleared": flags_cleared,
        "named_persons": persons,
    }), encoding="utf-8")


def _approval(rec: Path, approved: bool) -> None:
    (rec / "approval.json").write_text(json.dumps({"approved": approved}),
                                       encoding="utf-8")


# --------------------------------------------------------------- function layer

def test_fresh_record_writes_template_and_blocks(tmp_path):
    rec = _record(tmp_path, ["Sarah", "Wei"], clean=True)
    result = apg.run_gate(rec)
    assert result.ok is False
    assert result.wrote_template is True
    tmpl = json.loads((rec / "clearance.json").read_text(encoding="utf-8"))
    assert tmpl["named_persons"]["Sarah"]["status"] == "pending"
    assert tmpl["named_persons"]["Wei"]["status"] == "pending"


def test_all_permissioned_with_notes_clears(tmp_path):
    # Name/flag logic in isolation (approval leg tested separately below).
    rec = _record(tmp_path, ["Sarah"], clean=True)
    _clearance(rec, flags_cleared=True,
               persons={"Sarah": {"status": "permissioned", "note": "author has her OK"}})
    result = apg.run_gate(rec, require_approval=False)
    assert result.ok is True


def test_anonymised_clears(tmp_path):
    rec = _record(tmp_path, ["Sarah"], clean=True)
    _clearance(rec, flags_cleared=True,
               persons={"Sarah": {"status": "anonymised", "note": ""}})
    assert apg.run_gate(rec, require_approval=False).ok is True


def test_pending_name_blocks(tmp_path):
    rec = _record(tmp_path, ["Sarah"], clean=True)
    _clearance(rec, flags_cleared=True,
               persons={"Sarah": {"status": "pending", "note": ""}})
    result = apg.run_gate(rec)
    assert result.ok is False
    assert any("Sarah" in b for b in result.blockers)


def test_permissioned_without_note_blocks(tmp_path):
    rec = _record(tmp_path, ["Sarah"], clean=True)
    _clearance(rec, flags_cleared=True,
               persons={"Sarah": {"status": "permissioned", "note": ""}})
    result = apg.run_gate(rec)
    assert result.ok is False
    assert any("note" in b for b in result.blockers)


def test_missing_name_in_clearance_blocks(tmp_path):
    rec = _record(tmp_path, ["Sarah", "Wei"], clean=True)
    _clearance(rec, flags_cleared=True,
               persons={"Sarah": {"status": "anonymised", "note": ""}})  # Wei absent
    result = apg.run_gate(rec)
    assert result.ok is False
    assert any("Wei" in b for b in result.blockers)


def test_unreviewed_flags_block(tmp_path):
    rec = _record(tmp_path, [], clean=False, flags=[{"category": "added_numbers"}])
    _clearance(rec, flags_cleared=False, persons={})
    result = apg.run_gate(rec)
    assert result.ok is False
    assert any("flags_cleared" in b for b in result.blockers)


def test_clean_editcheck_needs_no_flag_review(tmp_path):
    rec = _record(tmp_path, [], clean=True)
    _clearance(rec, flags_cleared=False, persons={})  # clean -> flags_cleared irrelevant
    assert apg.run_gate(rec, require_approval=False).ok is True


def test_no_approval_blocks_full_gate(tmp_path):
    # Names cleared and flags clean, but no approval on file -> hard gate blocks.
    rec = _record(tmp_path, ["Sarah"], clean=True)
    _clearance(rec, flags_cleared=True,
               persons={"Sarah": {"status": "anonymised", "note": ""}})
    result = apg.run_gate(rec)  # require_approval defaults True
    assert result.ok is False
    assert any("approval not on file" in b for b in result.blockers)


def test_allow_unapproved_bypasses_approval(tmp_path):
    rec = _record(tmp_path, ["Sarah"], clean=True)
    _clearance(rec, flags_cleared=True,
               persons={"Sarah": {"status": "anonymised", "note": ""}})
    assert apg.run_gate(rec, require_approval=False).ok is True


def test_unapproved_approval_blocks(tmp_path):
    rec = _record(tmp_path, ["Sarah"], clean=True)
    _clearance(rec, flags_cleared=True,
               persons={"Sarah": {"status": "anonymised", "note": ""}})
    _approval(rec, approved=False)
    result = apg.run_gate(rec)
    assert result.ok is False
    assert any("approv" in b.lower() for b in result.blockers)


def test_approved_approval_clears(tmp_path):
    rec = _record(tmp_path, ["Sarah"], clean=True)
    _clearance(rec, flags_cleared=True,
               persons={"Sarah": {"status": "anonymised", "note": ""}})
    _approval(rec, approved=True)
    assert apg.run_gate(rec).ok is True


# -------------------------------------------------- wording-binding (re-edit guard)
# check.json carries edited_sha256; clearance.json + approval.json are bound to it.
# A same-slug re-edit that changed the wording must invalidate a stale clearance /
# an approval that was for the earlier wording.

def _sha_record(tmp_path, edited_sha) -> Path:
    rec = tmp_path / "s"
    rec.mkdir()
    (rec / "check.json").write_text(json.dumps({
        "slug": "s", "clean": True, "named_persons": [], "flags": [],
        "edited_sha256": edited_sha,
    }), encoding="utf-8")
    return rec


def test_stale_clearance_wording_blocks(tmp_path):
    rec = _sha_record(tmp_path, "NEWHASH")
    (rec / "clearance.json").write_text(json.dumps(
        {"edited_sha256": "OLDHASH", "flags_cleared": True, "named_persons": {}}),
        encoding="utf-8")
    (rec / "approval.json").write_text(json.dumps(
        {"approved": True, "wording_sha256": "NEWHASH"}), encoding="utf-8")
    result = apg.run_gate(rec)
    assert result.ok is False
    assert any("stale" in b.lower() for b in result.blockers)


def test_stale_approval_wording_blocks(tmp_path):
    rec = _sha_record(tmp_path, "NEWHASH")
    (rec / "clearance.json").write_text(json.dumps(
        {"edited_sha256": "NEWHASH", "flags_cleared": True, "named_persons": {}}),
        encoding="utf-8")
    (rec / "approval.json").write_text(json.dumps(
        {"approved": True, "wording_sha256": "OLDHASH"}), encoding="utf-8")
    result = apg.run_gate(rec)
    assert result.ok is False
    assert any("different wording" in b.lower() for b in result.blockers)


def test_matching_wording_clears(tmp_path):
    rec = _sha_record(tmp_path, "HASH")
    (rec / "clearance.json").write_text(json.dumps(
        {"edited_sha256": "HASH", "flags_cleared": True, "named_persons": {}}),
        encoding="utf-8")
    (rec / "approval.json").write_text(json.dumps(
        {"approved": True, "wording_sha256": "HASH"}), encoding="utf-8")
    assert apg.run_gate(rec).ok is True


def test_later_replies_surfaced_in_checklist(tmp_path):
    # A member follow-up after approval is surfaced prominently for the operator.
    rec = _sha_record(tmp_path, "HASH")
    (rec / "clearance.json").write_text(json.dumps(
        {"edited_sha256": "HASH", "flags_cleared": True, "named_persons": {}}),
        encoding="utf-8")
    (rec / "approval.json").write_text(json.dumps(
        {"approved": True, "wording_sha256": "HASH",
         "later_replies": ["Oh wait, can we swap the photo?"]}), encoding="utf-8")
    result = apg.run_gate(rec)
    assert result.ok is True  # surfaced, not hard-blocked
    assert any("AFTER the recorded decision" in c for c in result.checklist)
    assert any("swap the photo" in c for c in result.checklist)


def test_approval_reply_text_surfaced_in_checklist(tmp_path):
    # The gate echoes the decisive reply verbatim so the operator sees the exact
    # wording that produced approved:true -- the human backstop for a nuanced reply.
    rec = _sha_record(tmp_path, "HASH")
    (rec / "clearance.json").write_text(json.dumps(
        {"edited_sha256": "HASH", "flags_cleared": True, "named_persons": {}}),
        encoding="utf-8")
    (rec / "approval.json").write_text(json.dumps(
        {"approved": True, "wording_sha256": "HASH",
         "reply_text": "Approved, please publish it."}), encoding="utf-8")
    result = apg.run_gate(rec)
    assert result.ok is True
    assert any("approval reply" in c.lower() and "publish it" in c.lower()
               for c in result.checklist)


# -------------------------------------------------------------------- CLI layer

def _run(rec: Path, *extra):
    return subprocess.run([sys.executable, str(GATE), "--record", str(rec), *extra],
                          capture_output=True, text=True)


def test_cli_exit_1_when_blocked(tmp_path):
    rec = _record(tmp_path, ["Sarah"], clean=True)  # no clearance yet -> template + block
    res = _run(rec)
    assert res.returncode == 1
    assert "BLOCKED" in res.stdout


def test_cli_exit_0_when_cleared(tmp_path):
    rec = _record(tmp_path, ["Sarah"], clean=True)
    _clearance(rec, flags_cleared=True,
               persons={"Sarah": {"status": "permissioned", "note": "have her OK"}})
    res = _run(rec, "--allow-unapproved")
    assert res.returncode == 0
    assert "CLEARED" in res.stdout


def test_cli_exit_2_on_missing_record(tmp_path):
    res = _run(tmp_path / "nope")
    assert res.returncode == 2


def test_cli_exit_2_on_unwritable_record(tmp_path):
    # A first-run clearance-template write that fails (PermissionError) is a usage/IO
    # error (exit 2), NOT a normal BLOCKED result (exit 1) -- an operator or script
    # relying on the exit code must be able to tell a broken record store apart.
    import os
    import pytest
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root ignores chmod write bits")
    rec = _record(tmp_path, ["Sarah"], clean=True)  # no clearance -> tries to write template
    os.chmod(rec, 0o500)  # read + execute, no write
    try:
        res = _run(rec)
        assert res.returncode == 2
        assert "error" in res.stderr.lower()
    finally:
        os.chmod(rec, 0o700)


def test_allow_unapproved_writes_bypass_receipt_and_warns(tmp_path):
    # --allow-unapproved is never silent: it warns on stderr, marks the checklist,
    # and writes an audit receipt when it actually bypassed the approval requirement.
    rec = _record(tmp_path, ["Sarah"], clean=True)
    _clearance(rec, flags_cleared=True,
               persons={"Sarah": {"status": "anonymised", "note": ""}})
    res = _run(rec, "--allow-unapproved")
    assert res.returncode == 0
    assert "CLEARED" in res.stdout
    assert "BYPASS" in res.stdout.upper()          # loud checklist marker
    assert "warning" in res.stderr.lower()          # loud stderr warning
    assert (rec / "approval_bypass.json").is_file()  # audit receipt
    receipt = json.loads((rec / "approval_bypass.json").read_text(encoding="utf-8"))
    assert receipt["approval_bypassed"] is True


def test_allow_unapproved_no_receipt_when_approval_present(tmp_path):
    # If a member approval IS on file, --allow-unapproved changed nothing: no receipt.
    rec = _record(tmp_path, ["Sarah"], clean=True)
    _clearance(rec, flags_cleared=True,
               persons={"Sarah": {"status": "anonymised", "note": ""}})
    _approval(rec, approved=True)
    res = _run(rec, "--allow-unapproved")
    assert res.returncode == 0
    assert not (rec / "approval_bypass.json").is_file()


def test_cli_json_output(tmp_path):
    rec = _record(tmp_path, ["Sarah"], clean=True)
    _clearance(rec, flags_cleared=True,
               persons={"Sarah": {"status": "anonymised", "note": ""}})
    res = _run(rec, "--json", "--allow-unapproved")
    payload = json.loads(res.stdout)
    assert payload["ok"] is True


if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
