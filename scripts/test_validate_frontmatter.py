"""Unit tests for validate_frontmatter.py parser.

Run: python3 -m pytest scripts/test_validate_frontmatter.py -q
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validate_frontmatter import parse_frontmatter, REQUIRED


def test_basic_frontmatter():
    text = '---\ntitle: "Hello"\ndate: 2026-04-07\ncategories: [tech]\ntags: [a, b]\n---\nbody'
    fm = parse_frontmatter(text)
    assert fm is not None
    assert fm["title"] == "Hello"
    assert fm["date"] == "2026-04-07"
    assert fm["categories"] == ["tech"]
    assert fm["tags"] == ["a", "b"]


def test_colon_in_title():
    text = '---\ntitle: "Why: a manifesto"\ndate: 2026-04-07\ncategories: [tech]\ntags: [test]\n---\nbody'
    fm = parse_frontmatter(text)
    assert fm is not None
    assert fm["title"] == "Why: a manifesto"


def test_unquoted_value():
    text = '---\ntitle: bare title\ndate: 2026-04-07\ncategories: [tech]\ntags: [foo]\n---\n'
    fm = parse_frontmatter(text)
    assert fm["title"] == "bare title"


def test_multiple_tags():
    text = '---\ntitle: "x"\ndate: 2026-04-07\ncategories: [adventure]\ntags: [hike, mountains, "new zealand"]\n---\n'
    fm = parse_frontmatter(text)
    assert fm["tags"] == ["hike", "mountains", "new zealand"]


def test_no_frontmatter():
    assert parse_frontmatter("just body, no fence") is None


def test_unclosed_frontmatter():
    assert parse_frontmatter("---\ntitle: x\nno closing") is None


def test_required_fields_match_contract():
    assert REQUIRED == {"title", "date", "categories", "tags"}


def test_draft_flag_optional():
    text = '---\ntitle: "x"\ndate: 2026-04-07\ncategories: [tech]\ntags: [a]\ndraft: true\n---\n'
    fm = parse_frontmatter(text)
    assert fm["draft"] == "true"
    missing = REQUIRED - set(fm.keys())
    assert not missing
