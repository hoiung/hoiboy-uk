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


# ---- fit_title (LEAF cards) ---------------------------------------------------
# The landing path above has been guarded against the tagline-vs-signature collision
# since blog-priv#61. make_svg, the LEAF/service path, had no equivalent, so a title
# long enough for a third line pushed its tagline onto the signature and shipped that
# way: the operator caught it on the real ai-product-builder card at AC 3.7 review.
# These are the leaf twins of the two landing tests above.

LEAF_TITLE_37 = "AI Product Demo/MVP/Prototype Builder"   # the real title that broke


def test_leaf_title_never_exceeds_two_lines():
    # make_svg's geometry defines a one-line and a two-line case only; a third line is
    # what moves tag_y past SIG_CLEAR_Y. The 37-char real title is the discriminating
    # case: the conservative 22-char wrap gives it 3 lines, the card's real width gives 2.
    assert len(gc.wrap_title(LEAF_TITLE_37)) == 3        # pre-fix behaviour, still true
    fs, lines = gc.fit_title(LEAF_TITLE_37)
    assert len(lines) <= gc.TITLE_MAX_LINES, lines
    assert "".join(lines).replace(" ", "") == LEAF_TITLE_37.replace(" ", "")  # nothing lost


def test_leaf_tagline_never_overlaps_signature_for_any_title_length():
    # Same assertion the landing path makes, applied to make_svg. Every title here is a
    # real or realistic leaf title; none may place its tagline past the clearance line.
    for title in ("Portfolio",                                   # 1 line
                  "Business Automation Services",                # 2 lines
                  LEAF_TITLE_37,                                 # 3 lines pre-fix
                  "AI Product Demo And MVP And Prototype Builder Service"):
        svg = gc.make_svg("HIRE HOI > AI CONSULTANCY", title, "A tagline.",
                          "data:image/png;base64,AAAA", gc.HOIBOY_PAL)
        ys = [float(y) for y in re.findall(r'y="([\d.]+)" class="tag"', svg)]
        assert ys, f"{title}: no tagline rendered"
        assert all(y <= gc.SIG_CLEAR_Y for y in ys), f"{title}: tagline y {ys} past SIG_CLEAR_Y"


def test_leaf_title_that_cannot_fit_fails_loud():
    # Fail loud beats rendering a broken card, because a 3-line title still renders.
    import pytest
    with pytest.raises(SystemExit):
        gc.fit_title("Supercalifragilistic " * 12)


def test_short_leaf_titles_keep_their_original_size_and_wrap():
    # The fix must not touch any card that already fitted: <=2 lines at width 22 returns
    # exactly what the pre-fix inline expression returned. This is what kept the other 32
    # cards byte-identical through the AC 3.7 re-approval.
    assert gc.fit_title("Portfolio") == (gc.TITLE_FS_1L, ["Portfolio"])
    assert gc.fit_title("Business Automation Services") == (
        gc.TITLE_FS_2L, ["Business Automation", "Services"])


def test_read_meta_reads_a_folded_block_scalar_description(tmp_path):
    """`description: >` is ordinary YAML, and the regex reader returned ">".

    That single character rendered straight into the committed 1200x630
    share-card.png that is served as og:image for the landing. Nothing caught
    it: check_social_cards.py asserts a card EXISTS, never what it says. The
    only fail-open in this repo's card lane that reaches a reader.
    """
    md = tmp_path / "_index.md"
    md.write_text(
        "---\ntitle: Hire Hoi\ndescription: >\n"
        "  AI systems built and shipped\n  by one practitioner.\n---\n",
        encoding="utf-8",
    )
    title, desc = gc.read_landing_meta(md)
    assert title == "Hire Hoi"
    assert desc == "AI systems built and shipped by one practitioner."


def test_read_meta_reads_a_literal_block_scalar_description(tmp_path):
    """The `|` form folds newlines differently but must not degrade either."""
    md = tmp_path / "_index.md"
    md.write_text(
        "---\ntitle: Hire Hoi\ndescription: |\n  AI systems built and shipped.\n---\n",
        encoding="utf-8",
    )
    assert gc.read_landing_meta(md) == ("Hire Hoi", "AI systems built and shipped.")


def test_read_meta_dies_rather_than_rendering_a_non_string(tmp_path):
    """An unquoted date-like description parses as a date, not text.

    Rendering its Python repr onto a card would ship "datetime.date(2026, 7, 27)"
    as the tagline, and a generated PNG is not something anyone re-reads before
    publishing. Fail loud instead.
    """
    import pytest

    md = tmp_path / "_index.md"
    md.write_text("---\ntitle: Hire Hoi\ndescription:\n  - a\n  - b\n---\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        gc.read_landing_meta(md)


def test_read_meta_matches_every_real_landing_in_the_tsv():
    """Regression pin: the real landings must parse, and parse as text.

    This is the check that would have caught the block-scalar defect without
    anyone thinking to test block scalars, because it reads what actually ships.
    """
    tsv = SC / "landing-cards.tsv"
    seen = 0
    for line in tsv.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        path = Path(__file__).resolve().parent.parent / "content" / line.split("\t")[0]
        if path.is_dir():
            path = path / "_index.md"
        assert path.exists(), f"landing-cards.tsv names a missing landing: {path}"
        title, desc = gc.read_landing_meta(path)
        assert title and isinstance(title, str)
        assert desc is None or (isinstance(desc, str) and desc.strip() not in (">", "|"))
        seen += 1
    assert seen >= 14, f"expected the full landing set, parsed only {seen}"
