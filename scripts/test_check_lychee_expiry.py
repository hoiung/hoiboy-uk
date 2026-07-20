"""Unit tests for check_lychee_expiry.py.

Run: python3 -m pytest scripts/test_check_lychee_expiry.py -q
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import check_lychee_expiry as cle

TODAY = dt.date(2026, 7, 20)

HEADER = "# header\nexclude = [\n"
FOOTER = "]\n"


def _cfg(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "lychee.toml"
    p.write_text(HEADER + body + FOOTER, encoding="utf-8")
    return p


def test_entry_within_window_passes(tmp_path):
    cfg = _cfg(tmp_path, '  # added: 2026-07-01; expires: 2026-10-01 (90 days)\n  "^https?://a\\.com$",\n')
    failures, checked = cle.check(cfg, TODAY)
    assert failures == []
    assert checked == 1


def test_expired_entry_fails(tmp_path):
    cfg = _cfg(tmp_path, '  # added: 2026-04-08; expires: 2026-07-07 (90 days)\n  "^https?://a\\.com$",\n')
    failures, checked = cle.check(cfg, TODAY)
    assert len(failures) == 1
    assert "expired 2026-07-07" in failures[0]
    assert "13 days ago" in failures[0]


def test_expiring_today_is_still_valid(tmp_path):
    # Boundary: the entry is good THROUGH its expiry date, not up to the day
    # before. An off-by-one here would fail a freshly re-confirmed entry.
    cfg = _cfg(tmp_path, '  # added: 2026-04-21; expires: 2026-07-20 (90 days)\n  "^https?://a\\.com$",\n')
    assert cle.check(cfg, TODAY)[0] == []


def test_grouped_entries_share_one_comment(tmp_path):
    # The file's real convention: one rationale + date governing a run of
    # same-class entries. An earlier draft consumed the date after the first
    # entry and reported the other two as undocumented, which was a bug in the
    # checker rather than four defects in the config.
    cfg = _cfg(tmp_path,
               '  # added: 2026-07-10; expires: 2026-10-08 (90 days)\n'
               '  "^https?://meetup\\.com$",\n'
               '  "^https?://facebook\\.com$",\n'
               '  "^https?://instagram\\.com$",\n')
    failures, checked = cle.check(cfg, TODAY)
    assert failures == []
    assert checked == 3


def test_grouped_entries_all_fail_when_their_shared_date_expires(tmp_path):
    cfg = _cfg(tmp_path,
               '  # added: 2026-01-01; expires: 2026-07-07 (90 days)\n'
               '  "^https?://a\\.com$",\n'
               '  "^https?://b\\.com$",\n')
    failures, _ = cle.check(cfg, TODAY)
    assert len(failures) == 2


def test_second_comment_replaces_the_first(tmp_path):
    # The governing date must be REPLACED by a later comment, not merged, or a
    # stale group would be masked by a fresh one above it.
    cfg = _cfg(tmp_path,
               '  # added: 2026-07-01; expires: 2026-10-01 (90 days)\n'
               '  "^https?://fresh\\.com$",\n'
               '  # added: 2026-01-01; expires: 2026-07-07 (90 days)\n'
               '  "^https?://stale\\.com$",\n')
    failures, _ = cle.check(cfg, TODAY)
    assert len(failures) == 1
    assert "stale" in failures[0]


def test_entry_with_no_metadata_fails(tmp_path):
    cfg = _cfg(tmp_path, '  "^https?://undocumented\\.com$",\n')
    failures, _ = cle.check(cfg, TODAY)
    assert len(failures) == 1
    assert "has no" in failures[0]


def test_unparseable_date_fails(tmp_path):
    cfg = _cfg(tmp_path, '  # added: x; expires: 2026-13-45 (90 days)\n  "^https?://a\\.com$",\n')
    failures, _ = cle.check(cfg, TODAY)
    assert len(failures) == 1
    assert "unparseable" in failures[0]


def test_empty_exclude_block_is_a_vacuous_pass_and_is_rejected(tmp_path, capsys):
    # A run that inspects nothing must not report success. Same class as the
    # frontmatter gate's zero-walk guard.
    cfg = _cfg(tmp_path, "")
    rc = cle.main(["--config", str(cfg), "--today", "2026-07-20"])
    assert rc == 1
    assert "0 allowlist entries" in capsys.readouterr().err


def test_missing_config_is_operational_error_not_a_pass(tmp_path, capsys):
    rc = cle.main(["--config", str(tmp_path / "nope.toml")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_real_repo_config_is_clean(capsys):
    # The live config must pass, or the gate is red on main.
    assert cle.main([]) == 0
    assert "none past expiry" in capsys.readouterr().out
