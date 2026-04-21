#!/usr/bin/env python3
"""
Regression tests for check_wordcount.py (issue hoiung/hoiboy-uk#10).

Run: pytest scripts/test_check_wordcount.py -q

Covers the 5 synthetic scenarios from Phase 1 validation plus the
Stage-5 edge cases that surfaced real bugs: ISO-timestamp frontmatter
crash, quoted date strings, CRLF line endings, BOM handling.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

_spec = importlib.util.spec_from_file_location("cwc", HERE / "check_wordcount.py")
cwc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cwc)


def _run(path: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(HERE / "check_wordcount.py"), str(path)],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _write(path: Path, frontmatter: str, body_words: int) -> None:
    body = " ".join(["lorem"] * body_words) if body_words else ""
    path.write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")


class TestCountWords:
    def test_strip_frontmatter_excluded(self):
        text = "---\ntitle: Big Title Here\ndate: 2026-04-21\n---\n\nhello world"
        assert cwc.count_words(text) == 2

    def test_strip_fenced_code(self):
        text = "---\ndate: 2026-04-21\n---\n\nhello\n```python\nignored ignored ignored\n```\nworld"
        assert cwc.count_words(text) == 2

    def test_strip_html_comment_iamhoi(self):
        text = "---\ndate: 2026-04-21\n---\n\n<!-- iamhoi -->\nhello world\n<!-- iamhoiend -->"
        assert cwc.count_words(text) == 2

    def test_strip_hugo_shortcode(self):
        text = "---\ndate: 2026-04-21\n---\n\n{{< figure src=\"a.jpg\" >}}\nhello"
        assert cwc.count_words(text) == 1

    def test_markdown_link_keeps_text(self):
        text = "---\ndate: 2026-04-21\n---\n\nSee [the guide](https://example.com) here"
        assert cwc.count_words(text) == 4

    def test_image_keeps_alt_only(self):
        text = "---\ndate: 2026-04-21\n---\n\n![alt text here](img.jpg) extra"
        assert cwc.count_words(text) == 4


class TestParsePostDate:
    def test_iso_date_string(self, tmp_path):
        p = tmp_path / "a.md"
        p.write_text("---\ndate: 2026-04-21\n---\n\nx\n", encoding="utf-8")
        assert cwc.parse_post_date(p.read_text(), p) == date(2026, 4, 21)

    def test_iso_timestamp_coerced_to_date(self, tmp_path):
        p = tmp_path / "a.md"
        p.write_text("---\ndate: 2026-04-21T09:00:00Z\n---\n\nx\n", encoding="utf-8")
        assert cwc.parse_post_date(p.read_text(), p) == date(2026, 4, 21)

    def test_quoted_date_string(self, tmp_path):
        p = tmp_path / "a.md"
        p.write_text('---\ndate: "2026-04-21"\n---\n\nx\n', encoding="utf-8")
        assert cwc.parse_post_date(p.read_text(), p) == date(2026, 4, 21)

    def test_missing_date_raises(self, tmp_path):
        p = tmp_path / "a.md"
        p.write_text("---\ntitle: x\n---\n\nx\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Missing 'date' field"):
            cwc.parse_post_date(p.read_text(), p)

    def test_no_frontmatter_raises(self, tmp_path):
        p = tmp_path / "a.md"
        p.write_text("just body, no frontmatter\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid frontmatter"):
            cwc.parse_post_date(p.read_text(), p)

    def test_empty_date_string_raises(self, tmp_path):
        p = tmp_path / "a.md"
        p.write_text('---\ndate: ""\n---\n\nx\n', encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid 'date' value"):
            cwc.parse_post_date(p.read_text(), p)


class TestCheckFile:
    def test_over_ceiling_fails(self, tmp_path):
        p = tmp_path / "a.md"
        _write(p, "title: t\ndate: 2026-04-21", 3100)
        rc, _, err = _run(p)
        assert rc == 1
        assert "exceeds word-count ceiling" in err
        assert "Current: 3100 words" in err
        assert "Excess: 100 words" in err

    def test_boundary_at_ceiling_passes(self, tmp_path):
        p = tmp_path / "a.md"
        _write(p, "title: t\ndate: 2026-04-21", 3000)
        rc, _, _ = _run(p)
        assert rc == 0

    def test_legacy_date_silently_skipped(self, tmp_path):
        p = tmp_path / "a.md"
        _write(p, "title: t\ndate: 2024-01-01", 11000)
        rc, _, err = _run(p)
        assert rc == 0
        assert err == ""

    def test_iso_timestamp_does_not_crash(self, tmp_path):
        p = tmp_path / "a.md"
        _write(p, "title: t\ndate: 2026-04-21T09:00:00Z", 100)
        rc, _, err = _run(p)
        assert rc == 0
        assert "Traceback" not in err

    def test_missing_file_fails_loud(self, tmp_path):
        rc, _, err = _run(tmp_path / "does-not-exist.md")
        assert rc == 1
        assert "File not found" in err

    def test_crlf_line_endings(self, tmp_path):
        p = tmp_path / "a.md"
        p.write_bytes(b"---\r\ntitle: t\r\ndate: 2026-04-21\r\n---\r\n\r\nhello world\r\n")
        rc, _, _ = _run(p)
        assert rc == 0

    def test_bom_prefix(self, tmp_path):
        p = tmp_path / "a.md"
        p.write_bytes("\ufeff---\ntitle: t\ndate: 2026-04-21\n---\n\nhello\n".encode("utf-8"))
        rc, _, _ = _run(p)
        assert rc == 0


class TestGrandfather:
    def test_grandfathered_slug_skipped_even_if_oversize(self, tmp_path):
        slug_dir = tmp_path / "sst3-ai-harness-reshapeable-knife"
        slug_dir.mkdir()
        p = slug_dir / "index.md"
        _write(p, "title: t\ndate: 2026-04-21", 5000)
        rc, _, err = _run(p)
        assert rc == 0
        assert err == ""


class TestMain:
    def test_empty_argv_returns_zero(self):
        proc = subprocess.run(
            [sys.executable, str(HERE / "check_wordcount.py")],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0


class TestConstants:
    def test_ceiling_is_3000(self):
        assert cwc.WORDCOUNT_CEILING == 3000

    def test_cutoff_shared_with_voice_rules(self):
        import voice_rules
        assert cwc.HOIBOY_CUTOFF_DATE == voice_rules.HOIBOY_CUTOFF_DATE

    def test_grandfather_list_entries_exist(self):
        posts = Path(__file__).resolve().parents[1] / "content" / "posts"
        for slug in cwc.GRANDFATHERED_SLUGS:
            assert (posts / slug / "index.md").exists(), f"grandfathered slug {slug!r} missing on disk"
