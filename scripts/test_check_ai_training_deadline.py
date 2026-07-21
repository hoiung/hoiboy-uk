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
import yaml

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


@pytest.mark.parametrize(
    "opener,closer,label",
    [
        ("```", "```", "plain backtick fence"),
        (" ```", " ```", "delimiter indented one space (valid CommonMark)"),
        ("~~~", "~~~", "tilde fence"),
        ("````", "````", "four-backtick fence"),
    ],
)
def test_fenced_resolved_example_never_satisfies_the_gate(tmp_path, monkeypatch, opener, closer, label):
    # Each of these defeated the original single-regex fence stripper and
    # produced a false PASS. The gate's entire job is to be red here.
    body = (
        "Record it like this:\n"
        f"{opener}\n"
        "ai-training-migration-decision: resolved (2026-09-01, opted out)\n"
        f"{closer}\n"
        "ai-training-migration-decision: pending\n"
    )
    assert _run(tmp_path, body, PAST_TRIGGER, monkeypatch) == 1, label


def test_shorter_inner_run_does_not_close_a_longer_fence(tmp_path, monkeypatch):
    # CommonMark: the closing run must be at least as long as the opener. With
    # the opener length hardcoded to 3, an inner ``` run closed a ```` block
    # early and exposed the marker after it. The marker here must stay hidden,
    # so the doc has no live marker at all -> operational error, not a pass.
    body = (
        "Example:\n"
        "````\n"
        "```\n"
        "ai-training-migration-decision: resolved (must stay hidden)\n"
        "```\n"
        "````\n"
    )
    assert _run(tmp_path, body, PAST_TRIGGER, monkeypatch) == 2


def test_longer_closer_still_closes_a_shorter_fence(tmp_path, monkeypatch):
    # The other direction: a closing run LONGER than the opener is valid, so the
    # pending marker after it is live and the gate must go red.
    body = (
        "Example:\n"
        "```\n"
        "ai-training-migration-decision: resolved (hidden)\n"
        "`````\n"
        "ai-training-migration-decision: pending\n"
    )
    assert _run(tmp_path, body, PAST_TRIGGER, monkeypatch) == 1


def test_mismatched_fence_type_does_not_close(tmp_path, monkeypatch):
    # A ~~~ line does not close a ``` fence. Everything after stays hidden.
    body = (
        "Example:\n"
        "```\n"
        "ai-training-migration-decision: resolved (hidden)\n"
        "~~~\n"
        "ai-training-migration-decision: resolved (also hidden)\n"
    )
    assert _run(tmp_path, body, PAST_TRIGGER, monkeypatch) == 2


def test_unclosed_fence_swallows_to_end_of_file(tmp_path, monkeypatch):
    # The worst of the three bypasses: an unclosed fence made a regex requiring
    # a closing delimiter match nothing, leaving the example live as the ONLY
    # marker, so the gate passed. CommonMark says an unclosed fence runs to EOF;
    # with the whole block blanked there is no marker left, which is an error.
    body = (
        "Record it like this:\n"
        "```\n"
        "ai-training-migration-decision: resolved (2026-09-01, opted out)\n"
    )
    assert _run(tmp_path, body, PAST_TRIGGER, monkeypatch) == 2


def test_strip_fences_preserves_line_count(tmp_path):
    mod = _load(tmp_path / "unused.md")
    for body in (
        "a\n```\nb\nc\n```\nd\n",
        "a\n~~~\nb\n~~~\nd\n",
        "a\n```\nb\n",
        "no fences at all\n",
    ):
        assert mod._strip_fences(body).count("\n") == body.count("\n"), body


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
    # Parsed as YAML, NOT grepped as text. A line-regex cannot tell a live step
    # from a dead one, and two mutations that fully disable the gate in GitHub
    # Actions both left the regex version green:
    #   (a) commenting the step out  -> `# run: python3 scripts/...` still matched
    #   (b) adding `if: false`       -> the run line is untouched, step never runs
    # Both were verified to pass against the old assertion. Loading the YAML
    # makes a commented step vanish from the document entirely and exposes the
    # `if:` key, so neither mutation survives.
    ci_path = SCRIPT.parent.parent / ".github" / "workflows" / "ci.yml"
    doc = yaml.safe_load(ci_path.read_text(encoding="utf-8"))

    live = []
    for job in (doc.get("jobs") or {}).values():
        for step in (job.get("steps") or []):
            run = str(step.get("run") or "")
            if not re.search(
                r"(^|\s)python3\s+scripts/check_ai_training_deadline\.py(\s|$)", run
            ):
                continue
            # An `if:` that is literally false (or the string "false") disables
            # the step. Any other condition is a real expression and is treated
            # as live, since evaluating GitHub's expression language here would
            # be guesswork.
            cond = step.get("if", None)
            if cond is None or str(cond).strip().lower() not in ("false", "${{ false }}"):
                live.append(step)

    assert live, (
        "ci.yml has no LIVE step running `python3 scripts/check_ai_training_deadline.py`; "
        "the gate cannot fire. A commented-out step, an `if: false` step, or a "
        "unit-test step alone does not run the gate."
    )


def test_four_space_indented_closer_is_content_not_a_delimiter(tmp_path, monkeypatch):
    # CommonMark 0.31 section 4.5 caps a CLOSING fence at three spaces, the same
    # bound the opener already had. The stripper used line.strip() for the
    # closer, accepting any indentation, so a four-space ``` ended the block
    # early, flipped inside/outside parity for the rest of the file, and could
    # leave an illustrative `resolved` example as the only live marker. The gate
    # then printed "decision recorded" and exited 0 with the decision pending.
    #
    # This is the reproducer from the fix commit, promoted to a test. Ralph
    # round 4 observed that widening FENCE_CLOSE's indent bound left all 21
    # deadline-gate tests green: the fix shipped with nothing pinning it. A fix
    # without a regression test is one careless edit from being undone.
    body = (
        "# doc\n\n"
        "```\n"
        "ai-training-migration-decision: pending\n"
        "    ```\n"                       # 4 spaces: CONTENT, not a closer
        "ai-training-migration-decision: resolved (illustrative example)\n"
    )
    # Both markers sit inside the still-open fence, so ZERO live markers remain.
    # That is an operational error (exit 2), never a satisfied gate (exit 0).
    assert _run(tmp_path, body, "2026-07-21", monkeypatch) == 2


def test_three_space_indented_closer_does_close_the_fence(tmp_path, monkeypatch):
    # The other side of the boundary: three spaces is a VALID closer, so the
    # marker after it is live. Without this, tightening the bound too far (to
    # zero, say) would satisfy the test above while breaking real documents.
    body = (
        "# doc\n\n"
        "```\n"
        "ai-training-migration-decision: resolved (inside the fence, ignored)\n"
        "   ```\n"                        # 3 spaces: a valid closing fence
        "ai-training-migration-decision: pending\n"
    )
    # The live marker is `pending`, and this date is before the trigger.
    assert _run(tmp_path, body, "2026-07-21", monkeypatch) == 0
