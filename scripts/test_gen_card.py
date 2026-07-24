#!/usr/bin/env python3
"""Unit tests for the section-landing + home card logic in social-cards/gen_card.py
(blog-priv#61): the tagline fitter (must never overflow max_lines), the _index.md
frontmatter reader, and the title-only vs title+tagline render path."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SC = Path(__file__).resolve().parent / "social-cards"
sys.path.insert(0, str(SC))                       # so gen_card's `import card_common` resolves
_spec = importlib.util.spec_from_file_location("gen_card", SC / "gen_card.py")
gc = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gc
_spec.loader.exec_module(gc)

# The real longest landing description (content/hire-hoi/ai-consultancy/_index.md).
AI_CONSULTANCY_DESC = (
    "AI consulting for owner-operator-led teams: AI Managed Harness Services, "
    "Business Automation Services, AI Adoption Training, and the AI Product "
    "Demo/MVP/Prototype Builder, plus a portfolio of client work. Audit-first "
    "builds, deliverable-anchored automation, done-with-you training, ongoing "
    "Monthly Maintenance Package."
)


# ---- fit_tagline --------------------------------------------------------------

def test_short_tagline_one_line_full_size_no_ellipsis():
    fs, lines = gc.fit_tagline("A short, clean tagline.")
    assert fs == gc.TAG_FS and lines == ["A short, clean tagline."]
    assert not lines[-1].endswith("...")


def test_real_long_description_fits_in_full():
    # The real ai-consultancy description must render in full (no truncation). Compare
    # non-space content: textwrap may break at an existing hyphen (deliverable-anchored)
    # or a space, but must never add/drop a character.
    fs, lines = gc.fit_tagline(AI_CONSULTANCY_DESC)
    assert len(lines) <= 4
    assert not lines[-1].endswith("...")
    assert "".join(lines).replace(" ", "") == AI_CONSULTANCY_DESC.replace(" ", "")


def test_pathological_text_bounded_to_max_lines_with_ellipsis():
    # Text too long to fit even at min_fs in 4 lines must be truncated, not overflow.
    fs, lines = gc.fit_tagline("word " * 400)
    assert fs == 15
    assert len(lines) == 4
    assert lines[-1].endswith("...")


def test_never_exceeds_max_lines_for_any_length():
    for n in (5, 30, 80, 160, 400, 1000):
        _, lines = gc.fit_tagline("word " * n)
        assert len(lines) <= 4, f"{n} words -> {len(lines)} lines"


def test_custom_max_lines_respected():
    _, lines = gc.fit_tagline("word " * 400, max_lines=2)
    assert len(lines) == 2 and lines[-1].endswith("...")


# ---- read_landing_meta --------------------------------------------------------

def test_read_meta_quoted_title_and_description(tmp_path):
    p = tmp_path / "_index.md"
    p.write_text('---\ntitle: "Food & Booze"\ndescription: "Good eats and honest drinks."\n---\nbody\n',
                 encoding="utf-8")
    assert gc.read_landing_meta(p) == ("Food & Booze", "Good eats and honest drinks.")


def test_read_meta_unquoted_title_no_description(tmp_path):
    p = tmp_path / "_index.md"
    p.write_text("---\ntitle: Legal\n---\nbody\n", encoding="utf-8")
    assert gc.read_landing_meta(p) == ("Legal", None)


# ---- make_landing_svg (title-only vs title+tagline) ---------------------------

def test_title_only_svg_has_no_tagline_text():
    svg = gc.make_landing_svg("Dance", None, "data:image/png;base64,AAAA")
    assert ">Dance<" in svg
    assert 'class="tag">' not in svg                   # no tagline <text> element in title-only


def test_title_tagline_svg_has_tagline_text():
    svg = gc.make_landing_svg("Legal", "Privacy notice and sub-processors.",
                              "data:image/png;base64,AAAA")
    assert ">Legal<" in svg
    assert "Privacy notice and sub-processors." in svg
    assert 'class="tag">' in svg
