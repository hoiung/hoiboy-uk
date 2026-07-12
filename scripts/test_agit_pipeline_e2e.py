#!/usr/bin/env python3
"""End-to-end pipeline harness for the AGIT member-feature legal-safety flow.

hoiboy-uk #48 Phase 5. Drives the REAL pipeline scripts end to end (subprocess,
real record dirs under a tmp path) over a matrix of sample submissions, proving
the four Phase-5 assertions:

  * an UNAPPROVED sample is BLOCKED from publish,
  * an APPROVED sample publishes (gate cleared),
  * a sample with an added fact / a named person / an em-dash is FLAGGED,
  * the ORIGINAL submission is retained verbatim as the legal record.

Tiers: this file is the Workflow + E2E tier of the Three-Tier test gate. Each
test is a full sample-invocation of the real CLIs (check-agit-feature-edit.py and
check-agit-publish-gate.py run as subprocesses against a real record directory) --
NOT mocks swallowing kwargs. The only simulated element is the Gmail transport:
the member's reply is delivered through a fake service (the live OAuth grant is an
operator-runtime boundary), and the REAL agit_approval detection logic writes the
real approval.json that the gate reads. Everything else is a real subprocess call.

Em-dash discipline: the em-dash sample is built with chr(0x2014) at runtime, so no
literal em-dash byte ever lands in this tracked file (matches the config's
codepoint convention; the whole-tree em-dash rule is respected by construction).

Run: python3 -m pytest scripts/test_agit_pipeline_e2e.py -q
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import agit_approval as aa  # noqa: E402  (real approval-detection logic under test)
from test_agit_approval import FakeService, _gmail_message  # noqa: E402  (shared Gmail fake)

EDIT_CHECK = SCRIPTS / "check-agit-feature-edit.py"
PUBLISH_GATE = SCRIPTS / "check-agit-publish-gate.py"

EM_DASH = chr(0x2014)  # built at runtime; never a literal dash byte in this file
MEMBER_EMAIL = "member@example.com"
FROM_ADDR = "hoiboyuk@gmail.com"


# --------------------------------------------------------------------- helpers

def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    """Invoke a pipeline CLI as a real subprocess (no import shortcut)."""
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True)


def _edit_check(tmp: Path, slug: str, original: str, edited: str,
                record_dir: Path) -> subprocess.CompletedProcess:
    """Write the sample pair to disk and run the real edit-check CLI over it."""
    od = tmp / f"{slug}-original.txt"
    od.write_text(original, encoding="utf-8")
    ed = tmp / f"{slug}-edited.txt"
    ed.write_text(edited, encoding="utf-8")
    return _run(EDIT_CHECK, "--original", str(od), "--edited", str(ed),
                "--slug", slug, "--record-dir", str(record_dir))


def _gate(record: Path) -> subprocess.CompletedProcess:
    """Run the real publish-gate CLI against a per-submission record dir."""
    return _run(PUBLISH_GATE, "--record", str(record))


def _load_check(record: Path) -> dict:
    return json.loads((record / "check.json").read_text(encoding="utf-8"))


def _flag_categories(record: Path) -> set[str]:
    return {f["category"] for f in _load_check(record)["flags"]}


def _clear_names_and_flags(record: Path) -> None:
    """Simulate the human editor clearing every surfaced name + reviewing flags.

    Reads the REAL named_persons the edit-check surfaced (never guessed), clears
    the first as permissioned-with-note and the rest as anonymised so both valid
    statuses are exercised, and marks flags reviewed.
    """
    check = _load_check(record)
    entries: dict[str, dict] = {}
    for i, name in enumerate(check["named_persons"]):
        if i == 0:
            entries[name] = {"status": "permissioned",
                             "note": "author warrants they have this person's permission"}
        else:
            entries[name] = {"status": "anonymised", "note": ""}
    # Preserve the wording fingerprint the gate wrote into the template, so the
    # clearance stays bound to this exact edit (a human keeps this field).
    (record / "clearance.json").write_text(
        json.dumps({"edited_sha256": check.get("edited_sha256"),
                    "flags_cleared": True, "named_persons": entries}, indent=2),
        encoding="utf-8")


def _deliver_reply(record: Path, *reply_texts: str) -> dict:
    """Simulate the member replying (once or several times), then run the REAL
    approval detection.

    The fake Gmail thread carries our outgoing wording plus every member reply, in
    order; agit_approval.poll_for_approval reads it and writes the real
    approval.json the gate consumes (recording the member's LATEST decision). Only
    the transport is faked (operator-runtime OAuth boundary).
    """
    messages = [_gmail_message("out-1", FROM_ADDR,
                               "Here is the exact wording, please reply to approve.")]
    for i, text in enumerate(reply_texts):
        messages.append(_gmail_message(f"reply-{i}", MEMBER_EMAIL, text))
    thread = {"messages": messages}
    svc = FakeService(send_result={"id": "out-1", "threadId": "thread-1"}, thread=thread)
    # Send the EXACT edited wording (what the gate binds the approval to), not a
    # placeholder -- so approval.json's wording_sha256 == check.json's edited_sha256.
    wording = (record / "edited.txt").read_text(encoding="utf-8")
    aa.send_approval_request(svc, record, to_addr=MEMBER_EMAIL, from_addr=FROM_ADDR,
                             feature_title="AGIT feature", final_wording=wording,
                             slug=record.name)
    payload = aa.poll_for_approval(svc, record, thread_id="thread-1",
                                   member_email=MEMBER_EMAIL)
    assert payload is not None  # the member replied on the thread
    return payload


# --------------------------------------------------------------- sample corpus
# Form-only edits (light clarity + punctuation), every fact/hedge/name preserved.
CLEAN_ORIGINAL = (
    "My first year in tech was rough. I felt out of place in every meeting, and "
    "I think I nearly quit twice. Priya, my manager, kept telling me to slow down "
    "and ask questions. In my experience that one habit changed everything for me."
)
CLEAN_EDITED = (
    "My first year in tech was rough. I felt out of place in every meeting, and "
    "I think I nearly quit twice. Priya, my manager, kept telling me to slow down "
    "and to ask questions. In my experience, that one habit changed everything for me."
)

ADDED_FACT_ORIGINAL = "I worked at a small startup for a couple of years before moving on."
ADDED_FACT_EDITED = "I worked at Nexora for 3 years, joining in 2019, before moving on."

EMDASH_ORIGINAL = "My mentor gave me advice I still use. It was simple but it stuck."
EMDASH_EDITED = (
    "My mentor Sarah Chen gave me advice I still use" + EM_DASH
    + "it was simple, but it stuck."
)


# ---------------------------------------------------------------------- tests

def test_sample_clean_approved_publishes(tmp_path):
    """Clean form-only edit + named person cleared + member approves -> CLEARED."""
    record_dir = tmp_path / "records"
    slug = "clean-approved"
    res = _edit_check(tmp_path, slug, CLEAN_ORIGINAL, CLEAN_EDITED, record_dir)
    assert res.returncode == 0, res.stdout + res.stderr  # clean edit, no flags
    record = record_dir / slug

    # First gate run surfaces the named persons as a clearance template and blocks.
    first = _gate(record)
    assert first.returncode == 1
    assert (record / "clearance.json").is_file()
    assert "BLOCKED" in first.stdout

    # Human clears the names + reviews flags; member approves by email.
    _clear_names_and_flags(record)
    approval = _deliver_reply(record, "This is perfect. Approved, please publish it.")
    assert approval["approved"] is True

    # Second gate run: everything satisfied -> cleared to publish.
    final = _gate(record)
    assert final.returncode == 0, final.stdout + final.stderr
    assert "CLEARED" in final.stdout

    # The original is retained verbatim as the legal record.
    assert (record / "original.txt").read_text(encoding="utf-8") == CLEAN_ORIGINAL


def test_sample_hedge_then_approved_publishes(tmp_path):
    """Member hedges first, then approves on the same thread -> still publishes.

    Full-pipeline coverage of the multi-reply approval path: the latest decisive
    reply wins, so a stale first hedge must not block a feature the member did
    approve.
    """
    record_dir = tmp_path / "records"
    slug = "hedge-then-approved"
    res = _edit_check(tmp_path, slug, CLEAN_ORIGINAL, CLEAN_EDITED, record_dir)
    assert res.returncode == 0, res.stdout + res.stderr
    record = record_dir / slug

    _gate(record)  # writes the clearance template
    _clear_names_and_flags(record)
    approval = _deliver_reply(
        record,
        "Hold off for a sec, let me reread this properly.",
        "OK I've reread it. Approved, please publish it.")
    assert approval["approved"] is True

    final = _gate(record)
    assert final.returncode == 0, final.stdout + final.stderr
    assert "CLEARED" in final.stdout


def test_reedit_after_approval_is_blocked(tmp_path):
    """A same-slug re-edit that changed the wording voids a prior approval+clearance.

    Guards the "approval of the EXACT final wording" rule: an operator who tweaks a
    feature after approval was granted cannot publish the new wording on the old OK.
    """
    record_dir = tmp_path / "records"
    slug = "reedit"
    _edit_check(tmp_path, slug, CLEAN_ORIGINAL, CLEAN_EDITED, record_dir)
    record = record_dir / slug
    _gate(record)
    _clear_names_and_flags(record)
    approval = _deliver_reply(record, "Approved, please publish it.")
    assert approval["approved"] is True
    assert _gate(record).returncode == 0  # cleared for the approved wording

    # Re-edit the SAME slug with a different wording (adds a fabricated year).
    _edit_check(tmp_path, slug, CLEAN_ORIGINAL, CLEAN_EDITED + " We shipped in May 2019.",
                record_dir)
    blocked = _gate(record)
    assert blocked.returncode == 1  # stale clearance + approval for the old wording
    assert "BLOCKED" in blocked.stdout


def test_sample_clean_declined_blocked(tmp_path):
    """Names cleared + flags clean, but the member declines -> HARD-BLOCKED."""
    record_dir = tmp_path / "records"
    slug = "clean-declined"
    res = _edit_check(tmp_path, slug, CLEAN_ORIGINAL, CLEAN_EDITED, record_dir)
    assert res.returncode == 0, res.stdout + res.stderr
    record = record_dir / slug

    _gate(record)  # writes the clearance template
    _clear_names_and_flags(record)
    approval = _deliver_reply(
        record, "Thanks, but hold off. I'd like some changes before you publish.")
    assert approval["approved"] is False

    final = _gate(record)
    assert final.returncode == 1  # no approval on file -> no publish
    assert "BLOCKED" in final.stdout
    assert any("approv" in line.lower() for line in final.stdout.splitlines())


def test_no_approval_at_all_blocks(tmp_path):
    """Absent approval (member never replied) also hard-blocks -- fail-safe."""
    record_dir = tmp_path / "records"
    slug = "no-approval"
    _edit_check(tmp_path, slug, CLEAN_ORIGINAL, CLEAN_EDITED, record_dir)
    record = record_dir / slug
    _gate(record)  # template
    _clear_names_and_flags(record)  # names cleared, but NO approval.json written
    assert not (record / "approval.json").is_file()
    final = _gate(record)
    assert final.returncode == 1
    assert "BLOCKED" in final.stdout


def test_sample_added_fact_flagged(tmp_path):
    """An added company / number / year in the edit is FLAGGED (added-fact tell)."""
    record_dir = tmp_path / "records"
    slug = "added-fact"
    res = _edit_check(tmp_path, slug, ADDED_FACT_ORIGINAL, ADDED_FACT_EDITED, record_dir)
    assert res.returncode == 1  # flags need a human look
    record = record_dir / slug
    categories = _flag_categories(record)
    assert "added_proper_nouns" in categories  # "Nexora"
    assert "added_numbers" in categories        # "3"
    assert "added_dates" in categories          # "2019"
    assert any("Nexora" in name for name in _load_check(record)["named_persons"])
    # Original retained verbatim even for a flagged submission.
    assert (record / "original.txt").read_text(encoding="utf-8") == ADDED_FACT_ORIGINAL


def test_sample_emdash_and_named_person_flagged(tmp_path):
    """An em-dash and a newly named person are both FLAGGED / surfaced."""
    record_dir = tmp_path / "records"
    slug = "emdash-named"
    res = _edit_check(tmp_path, slug, EMDASH_ORIGINAL, EMDASH_EDITED, record_dir)
    assert res.returncode == 1
    record = record_dir / slug
    categories = _flag_categories(record)
    assert "banned_punctuation" in categories
    named = _load_check(record)["named_persons"]
    assert any("Sarah" in name for name in named)  # "Sarah Chen" surfaced for clearance


def test_original_retained_across_samples(tmp_path):
    """Every processed submission keeps its original verbatim + a diff record."""
    record_dir = tmp_path / "records"
    for slug, original, edited in (
        ("ret-clean", CLEAN_ORIGINAL, CLEAN_EDITED),
        ("ret-fact", ADDED_FACT_ORIGINAL, ADDED_FACT_EDITED),
    ):
        _edit_check(tmp_path, slug, original, edited, record_dir)
        record = record_dir / slug
        assert (record / "original.txt").read_text(encoding="utf-8") == original
        assert (record / "edited.txt").read_text(encoding="utf-8") == edited
        assert (record / "diff.txt").is_file()
        assert (record / "check.json").is_file()


if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
