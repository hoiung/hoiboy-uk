#!/usr/bin/env python3
"""Unit tests for the section-landing + home card logic in social-cards/gen_card.py
(blog-priv#61): the tagline fitter (must never overflow max_lines), the _index.md
frontmatter reader, and the title-only vs title+tagline render path."""
from __future__ import annotations

import importlib.util
import re
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
    assert len(lines) <= gc._tag_max_lines(128, fs)     # fits the default vertical budget
    assert not lines[-1].endswith("...")
    assert "".join(lines).replace(" ", "") == AI_CONSULTANCY_DESC.replace(" ", "")


def test_pathological_text_bounded_and_ellipsised():
    # Text too long to fit even at min_fs must be truncated to the vertical budget, not
    # overflow. At the default 128px budget the smallest font (15) fits 5 lines.
    fs, lines = gc.fit_tagline("word " * 400)
    assert fs == 15
    assert len(lines) == gc._tag_max_lines(128, 15)
    assert lines[-1].endswith("...")


def test_never_exceeds_vertical_budget_for_any_length():
    for n in (5, 30, 80, 160, 400, 1000):
        fs, lines = gc.fit_tagline("word " * n)
        assert len(lines) <= gc._tag_max_lines(128, fs), f"{n} words -> {len(lines)} lines @ {fs}px"


def test_small_vertical_budget_bounds_lines():
    # A cramped budget (e.g. a 2-line title left little room) shrinks the tagline instead
    # of overflowing: only what fits, truncated with an ellipsis.
    fs, lines = gc.fit_tagline("word " * 400, avail_px=60)
    assert len(lines) <= gc._tag_max_lines(60, fs)
    assert lines[-1].endswith("...")


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


def _tag_baselines(svg):
    return [float(y) for y in re.findall(r'y="([\d.]+)" class="tag"', svg)]


def test_tagline_never_overlaps_signature_for_any_title_length():
    # No matter how far a wrapped title pushes the rule down, a tagline is never placed
    # below the signature-clearance line: it shrinks (2-line title) or is dropped entirely
    # (3+-line title -> title-only). Closes the tagline-vs-signature class (Ralph Sonnet).
    titles = {
        "Legal": 1,                                                 # 1 line (real)
        "AI Product Engineering Consultancy Roles": 2,              # 2 lines
        "Owner Operator Led AI Adoption Strategy And Automation Roadmap": 3,  # 3 lines
        "Owner Operator Led AI Adoption Strategy Automation Roadmap And Delivery Playbook": 4,  # 4 lines
    }
    for title, want_lines in titles.items():
        assert len(gc.wrap_title(title)) == want_lines, title
        svg = gc.make_landing_svg(title, AI_CONSULTANCY_DESC, "data:image/png;base64,AAAA")
        ys = _tag_baselines(svg)
        assert all(y <= gc.SIG_CLEAR_Y for y in ys), f"{title}: tagline y {ys} past SIG_CLEAR_Y"


def test_long_title_drops_tagline_rather_than_overlap():
    # A 3-line title leaves no vertical room, so the card is title-only (no tagline text).
    title = "Owner Operator Led AI Adoption Strategy And Automation Roadmap"
    assert len(gc.wrap_title(title)) >= 3
    svg = gc.make_landing_svg(title, AI_CONSULTANCY_DESC, "data:image/png;base64,AAAA")
    assert 'class="tag">' not in svg              # tagline dropped
    assert ">Automation Roadmap<" in svg          # title still rendered in full
