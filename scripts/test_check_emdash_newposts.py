#!/usr/bin/env python3
"""Discriminating tests for scripts/check_emdash_newposts.py (hoiboy-uk #33 AC 2.5).

Invokes the guard as a subprocess on fixture posts and asserts exit codes:
a NEW post with a bare em dash in unmarked prose FAILs (exit 1); a legacy post,
a NEW post whose em dash sits inside an iamhoi-skip block, and a clean NEW post
all PASS (exit 0).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

GUARD = Path(__file__).resolve().parent / "check_emdash_newposts.py"

NEW = "---\ndate: 2026-05-01\n---\n"
LEGACY = "---\ndate: 2014-01-01\n---\n"


def _run(path: Path) -> int:
    return subprocess.run(
        [sys.executable, str(GUARD), str(path)], capture_output=True, text=True
    ).returncode


def _write(tmp_path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_new_post_bare_emdash_fails(tmp_path):
    p = _write(tmp_path, "a.md", NEW + "\nProse with a bare em dash — here.\n")
    assert _run(p) == 1


def test_legacy_post_emdash_passes(tmp_path):
    p = _write(tmp_path, "b.md", LEGACY + "\nLegacy prose — em dash allowed.\n")
    assert _run(p) == 0


def test_new_post_emdash_in_skip_passes(tmp_path):
    p = _write(
        tmp_path,
        "c.md",
        NEW + "\n<!-- iamhoi-skip -->\nExample: em dash —\n<!-- iamhoi-skipend -->\n",
    )
    assert _run(p) == 0


def test_clean_new_post_passes(tmp_path):
    p = _write(tmp_path, "d.md", NEW + "\nClean prose, only hyphens - like this.\n")
    assert _run(p) == 0
