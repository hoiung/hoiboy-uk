#!/usr/bin/env python3
"""Unit tests for scripts/check_newsletter_template.py (blog-priv#81 AC 1.8).

These assert the MESSAGE, not just that something failed. A gate whose job is to
explain why the campaign copy is now unguarded is only useful if it says so; an
assertion on "returned a non-empty list" would keep passing if every message
degraded to "invalid".

The load-bearing case is `test_stripped_markers_are_caught`. Everything else here
guards construction details that a browser would forgive; that one guards the
failure the voice guard structurally cannot report, because deleting the markers
makes it scan nothing and print OK.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import check_newsletter_template as gate  # noqa: E402

REAL_TEMPLATE = gate.TEMPLATE


@pytest.fixture(scope="module")
def clean() -> str:
    assert REAL_TEMPLATE.is_file(), f"the template must exist to test against: {REAL_TEMPLATE}"
    return REAL_TEMPLATE.read_text(encoding="utf-8")


def test_the_shipped_template_passes_its_own_gate(clean):
    """If this fails the template is broken, not the test."""
    assert gate.failures(clean) == []


def test_stripped_markers_are_caught(clean):
    """The whole reason this gate exists.

    Removing the markers leaves prose that reads fine and a voice guard that
    reports OK over nothing. Nothing else in the repo turns red.
    """
    stripped = clean.replace(gate.MARKER_OPEN, "").replace(gate.MARKER_CLOSE, "")
    problems = gate.failures(stripped)
    assert problems, "stripping the iamhoi markers must fail the gate"
    assert any("default-SKIP" in p for p in problems), (
        f"the message must explain WHY a missing marker matters, not just that one is "
        f"absent, or the next reader deletes them again: {problems}"
    )


def test_unbalanced_markers_are_caught(clean):
    problems = gate.failures(clean.replace(gate.MARKER_CLOSE, "", 1))
    assert any("unbalanced" in p for p in problems), problems


def test_go_template_action_is_caught(clean):
    """A raw Brevo merge tag here fails the site build, not just the email."""
    broken = clean.replace("%%FIRSTNAME%%", "{" + "{contact.FIRSTNAME}" + "}")
    problems = gate.failures(broken)
    assert any("Go-template action" in p for p in problems), problems


def test_double_quoted_font_name_is_caught(clean):
    """The exact trap AC 1.3's extractor sets.

    A double-quoted face name truncates the declaration before the generic family,
    so the email silently loses its fallback while looking correct in a browser.
    """
    broken = clean.replace("'Source Serif 4'", '"Source Serif 4"', 1)
    problems = gate.failures(broken)
    assert any("generic family" in p for p in problems), problems


@pytest.mark.parametrize(
    "inject,needle",
    [
        ("color:var(--accent);", "custom property"),
        ("display:flex;", "custom property"),
    ],
)
def test_unsupported_css_is_caught(clean, inject, needle):
    problems = gate.failures(clean.replace("padding:24px 12px;", inject, 1))
    assert any(needle in p for p in problems), problems


def test_missing_accent_is_caught(clean):
    problems = gate.failures(clean.replace("#c0533a", "#000000"))
    assert any("terracotta" in p for p in problems), problems


def test_missing_presentation_table_is_caught(clean):
    problems = gate.failures(clean.replace('role="presentation"', 'role="none"'))
    assert any("table-based" in p for p in problems), problems


def test_gate_floors_when_the_template_is_absent(tmp_path):
    """Coverage floor, driven through the real entry point.

    A copy of scripts/ in an empty directory makes the gate resolve that directory
    as the repo, so the template is genuinely missing rather than stubbed out.
    """
    skel = tmp_path / "scripts"
    skel.mkdir()
    for name in ("check_newsletter_template.py", "gate_coverage.py"):
        (skel / name).write_text((SCRIPTS / name).read_text(encoding="utf-8"), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(skel / "check_newsletter_template.py")],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, (
        f"a missing template must not report success: rc={proc.returncode} "
        f"stdout={proc.stdout!r}"
    )
    assert "newsletter email template" in proc.stderr, proc.stderr


def test_a_violating_template_exits_non_zero_through_the_real_entry_point(clean, tmp_path):
    """The exit code is the ONLY thing pre-commit reads. Prove it moves.

    Every other test here calls `failures()` and asserts its message. That proves
    the contract logic and nothing about whether a violation actually stops a
    commit: `.pre-commit-config.yaml:113` runs this file as a command and keys
    solely on the return code, and `ci.yml` runs only the pytest, never the
    binary. So `main()`'s `return 1` is the sole production signal, and the
    sibling floor test above exercises the ABSENT-template branch instead, which
    exits through `require_examined` long before that line.

    Ralph round 3 tier 3 rewrote `return 1` to `return 0` and watched the gate
    print "1 contract violation(s)" while exiting 0, with the suite still green.
    That is round 2's finding on a new module: the guard was tested as a
    function and never through the command that calls it.
    """
    skel = tmp_path / "scripts"
    skel.mkdir()
    for name in ("check_newsletter_template.py", "gate_coverage.py"):
        (skel / name).write_text((SCRIPTS / name).read_text(encoding="utf-8"), encoding="utf-8")

    template = tmp_path / "layouts" / "_partials" / "newsletter" / "email.html"
    template.parent.mkdir(parents=True)
    # Present but non-compliant, so the coverage floor is satisfied and the run
    # reaches the contract check. Stripped markers are the violation this gate
    # was built for.
    template.write_text(
        clean.replace(gate.MARKER_OPEN, "").replace(gate.MARKER_CLOSE, ""),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(skel / "check_newsletter_template.py")],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, (
        f"a template that violates the contract must exit non-zero, or pre-commit "
        f"lets it through: rc={proc.returncode} stderr={proc.stderr!r}"
    )
    assert "contract violation" in proc.stderr, proc.stderr
