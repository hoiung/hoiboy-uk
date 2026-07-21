"""Tests for the ai_training migration deadline gate.

The gate's whole value is that it turns red on a date nobody will remember. So
the cases that matter are the ones where it could be red and silently is not:
a marker deleted, duplicated, or shadowed by an illustrative example. Every one
of those must be an ERROR, never a pass.

Exit contract:
  0 = decision recorded, or the trigger date has not arrived
  1 = still pending and the trigger has passed
  2 = operational error
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "check_ai_training_deadline.py"

PAST_TRIGGER = "2026-09-02"
PRE_TRIGGER = "2026-08-31"


def _load(doc_path: Path):
    """Import the script with DOC pointed at a fixture."""
    spec = importlib.util.spec_from_file_location("deadline_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DOC = doc_path
    mod.ROOT = doc_path.parent
    return mod


def _run(tmp_path: Path, body: str, today: str, monkeypatch) -> int:
    doc = tmp_path / "17_AI_CRAWLER_FRAMEWORK.md"
    doc.write_text(body, encoding="utf-8")
    monkeypatch.setenv("AI_TRAINING_DEADLINE_TODAY", today)
    return _load(doc).main()


def test_real_doc_passes_today():
    # The shipped doc must satisfy its own gate, or every CI run is red.
    p = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr


def test_pending_before_trigger_passes(tmp_path, monkeypatch):
    body = "text\nai-training-migration-decision: pending\n"
    assert _run(tmp_path, body, PRE_TRIGGER, monkeypatch) == 0


def test_pending_after_trigger_fails(tmp_path, monkeypatch):
    body = "text\nai-training-migration-decision: pending\n"
    assert _run(tmp_path, body, PAST_TRIGGER, monkeypatch) == 1


def test_resolved_passes_after_trigger(tmp_path, monkeypatch):
    body = "ai-training-migration-decision: resolved (2026-08-20, opted out)\n"
    assert _run(tmp_path, body, PAST_TRIGGER, monkeypatch) == 0


def test_missing_marker_is_an_error_not_a_pass(tmp_path, monkeypatch):
    # Deleting the marker must not be a way to make the gate green.
    body = "a doc with no marker at all\n"
    assert _run(tmp_path, body, PAST_TRIGGER, monkeypatch) == 2


def test_missing_doc_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_TRAINING_DEADLINE_TODAY", PAST_TRIGGER)
    mod = _load(tmp_path / "does_not_exist.md")
    assert mod.main() == 2


def test_resolved_example_in_a_code_fence_does_not_satisfy_the_gate(tmp_path, monkeypatch):
    # The doc explains the marker by example. If a fenced `resolved` sample were
    # matched, the gate would read as decided while the real marker says pending
    # -- the exact vacuous pass this gate exists to prevent.
    body = (
        "Record it like this:\n"
        "```\n"
        "ai-training-migration-decision: resolved (2026-09-01, opted out)\n"
        "```\n"
        "ai-training-migration-decision: pending\n"
    )
    assert _run(tmp_path, body, PAST_TRIGGER, monkeypatch) == 1


def test_duplicate_markers_are_an_error(tmp_path, monkeypatch):
    # First-match-wins would let a stale `resolved` above the live `pending`
    # silently disarm the gate. Ambiguity is an error, not a pass.
    body = (
        "ai-training-migration-decision: resolved (old, superseded)\n"
        "ai-training-migration-decision: pending\n"
    )
    assert _run(tmp_path, body, PAST_TRIGGER, monkeypatch) == 2


def test_marker_quoted_mid_sentence_does_not_count(tmp_path, monkeypatch):
    # Only a line-initial marker is input. Prose mentioning it must not arm or
    # disarm anything, so this reads as "no marker" -> error.
    body = "the line `ai-training-migration-decision: resolved` is the input\n"
    assert _run(tmp_path, body, PAST_TRIGGER, monkeypatch) == 2


def test_garbage_date_override_is_an_error(tmp_path, monkeypatch):
    doc = tmp_path / "17_AI_CRAWLER_FRAMEWORK.md"
    doc.write_text("ai-training-migration-decision: pending\n", encoding="utf-8")
    monkeypatch.setenv("AI_TRAINING_DEADLINE_TODAY", "not-a-date")
    with pytest.raises(SystemExit) as e:
        _load(doc).main()
    assert e.value.code == 2


def test_trigger_boundary_is_inclusive(tmp_path, monkeypatch):
    # On the trigger date itself the gate must already be red; an off-by-one
    # here costs a day at exactly the moment the gate matters.
    body = "ai-training-migration-decision: pending\n"
    assert _run(tmp_path, body, "2026-09-01", monkeypatch) == 1
    assert _run(tmp_path, body, "2026-08-31", monkeypatch) == 0


def test_gate_is_wired_into_ci():
    # The defect that made this gate worthless on its first commit: it existed,
    # was documented as "not advice in a document; it is a gate", and no
    # workflow invoked it. A guard nothing runs guards nothing.
    #
    # Matched as a whole invocation line, NOT as a substring. A bare
    # `"check_ai_training_deadline.py" in ci` also matches the unit-test step
    # (`test_check_ai_training_deadline.py` contains the name), so deleting the
    # gate step while keeping the tests would still have passed. Mutation
    # testing caught exactly that.
    ci = (SCRIPT.parent.parent / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    invocations = [
        line.strip()
        for line in ci.splitlines()
        if re.search(r"run:\s*python3\s+scripts/check_ai_training_deadline\.py\s*$", line)
    ]
    assert invocations, (
        "ci.yml has no `run: python3 scripts/check_ai_training_deadline.py` step; "
        "the gate cannot fire. A unit-test step alone does not run the gate."
    )
