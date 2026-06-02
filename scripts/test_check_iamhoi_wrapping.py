#!/usr/bin/env python3
"""Discriminating tests for check-iamhoi-wrapping.py (hoiboy-uk #33 AC 4.1).

Two layers:
  1. has_marker() unit tests — a STANDALONE `<!-- iamhoi -->` line opens a region,
     but a backtick *mention* of the token (as the tone-spec docs carry) must NOT
     satisfy has_marker (the #513 substring-bypass class).
  2. Gate-level subprocess tests — a NEW post with first-person prose and no real
     marker FAILs (exit 1); a correctly-wrapped region PASSes (exit 0); a
     backtick-mention bypass attempt still FAILs.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
GATE = SCRIPTS / "check-iamhoi-wrapping.py"

# Import the hyphen-named module so has_marker can be tested directly.
sys.path.insert(0, str(SCRIPTS))  # for `from voice_rules import ...`
_spec = importlib.util.spec_from_file_location("ciw", GATE)
ciw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ciw)

NEW = "---\ndate: 2026-05-01\n---\n"


def _run(path: Path) -> int:
    return subprocess.run(
        [sys.executable, str(GATE), "--check-only-new", str(path)],
        capture_output=True,
        text=True,
    ).returncode


def _write(tmp_path, name, body) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# --- has_marker unit layer ---

def test_standalone_marker_is_a_marker():
    assert ciw.has_marker("<!-- iamhoi -->\nI built this.\n<!-- iamhoiend -->") is True


def test_backtick_mention_is_not_a_marker():
    # A doc that merely mentions the token in backticks must NOT satisfy has_marker.
    body = "Wrap prose in the `<!-- iamhoi -->` token to opt in.\nI did this once.\n"
    assert ciw.has_marker(body) is False


# --- gate-level subprocess layer ---

def test_gate_fails_unwrapped_voice(tmp_path):
    p = _write(tmp_path, "a.md", NEW + "\nI built my own trading system and I love it.\n")
    assert _run(p) == 1


def test_gate_passes_wrapped_region(tmp_path):
    p = _write(
        tmp_path,
        "b.md",
        NEW + "\n<!-- iamhoi -->\nI built my own trading system.\n<!-- iamhoiend -->\n",
    )
    assert _run(p) == 0


def test_gate_fails_backtick_bypass(tmp_path):
    # First-person prose + the marker only mentioned in backticks -> still FAIL.
    p = _write(
        tmp_path,
        "c.md",
        NEW + "\nI opt in with the `<!-- iamhoi -->` token, honest.\n",
    )
    assert _run(p) == 1
