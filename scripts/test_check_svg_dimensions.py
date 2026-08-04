"""Unit tests for check_svg_dimensions.py (the house SVG structural gate, #534).

Run: python3 -m pytest scripts/test_check_svg_dimensions.py -q

Covers all three assertions (root width/height + #87ceeb watermark + canonical class block)
and the documented exemption for the fixed-dark inline form (no <style>).
"""
from __future__ import annotations
import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_svg_dimensions import offenders, main, scope_problem

# A fully house-compliant dual-mode SVG: root width/height + canonical <style> block + watermark.
COMPLIANT = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200" width="400" height="200">'
    '<defs><style>'
    '.bg { fill: #fafafa; } .card { fill: #ffffff; } .label { fill: #1a1a1a; }'
    '.muted { fill: #6a6a6a; } .accent { fill: #c0533a; } .ok { fill: #7aa869; }'
    '.watermark { fill: #87ceeb; }'
    '</style></defs>'
    '<rect class="bg" width="400" height="200"/>'
    '<text x="385" y="18" text-anchor="end" class="watermark">hoiboy.uk</text>'
    '</svg>'
)

# The documented fixed-dark INLINE form (e.g. harness-layers.svg): NO <style>, inline fills.
INLINE_FIXED_DARK = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1200" width="1600" height="1200">'
    '<rect x="0" y="0" width="1600" height="1200" fill="#1a1a1a"/>'
    '<text x="1573" y="43" text-anchor="end" fill="#87ceeb">hoiboy.uk</text>'
    '</svg>'
)


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_compliant_passes(tmp_path):
    assert offenders([_write(tmp_path, "ok.svg", COMPLIANT)]) == []


def test_inline_fixed_dark_form_passes(tmp_path):
    # No <style> block → exempt from the canonical-class assertion; watermark is inline.
    assert offenders([_write(tmp_path, "inline.svg", INLINE_FIXED_DARK)]) == []


def test_missing_watermark_fails(tmp_path):
    bad = COMPLIANT.replace("#87ceeb", "#cccccc").replace("hoiboy.uk", "nope")
    res = offenders([_write(tmp_path, "no_wm.svg", bad)])
    assert res and any("watermark" in r for r in res[0][1])


def test_adhoc_classes_fail(tmp_path):
    # has a <style> but uses off-brand class names → canonical block assertion fires.
    adhoc = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200" width="400" height="200">'
        '<defs><style>.box { fill: #fafafa; } .line { stroke: #c0533a; }</style></defs>'
        '<text x="385" y="18" text-anchor="end" fill="#87ceeb">hoiboy.uk</text>'
        '<rect class="box" width="400" height="200"/></svg>'
    )
    res = offenders([_write(tmp_path, "adhoc.svg", adhoc)])
    assert res and any("canonical class" in r for r in res[0][1])


def test_missing_dimensions_fail(tmp_path):
    no_dim = COMPLIANT.replace(' width="400" height="200"', "", 1)
    res = offenders([_write(tmp_path, "no_dim.svg", no_dim)])
    assert res and any("width" in r or "height" in r for r in res[0][1])


def test_multiple_violations_collected(tmp_path):
    # missing dims AND missing watermark → both reasons surface for one file.
    both = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">'
            '<rect width="400" height="200"/></svg>')
    res = offenders([_write(tmp_path, "both.svg", both)])
    assert res and len(res[0][1]) >= 2


def test_grouped_selectors_pass(tmp_path):
    # #534 Stage-5: a legitimately house-compliant SVG that GROUPS the canonical selectors
    # (`.bg, .card { }`) must PASS — the old `\.bg\s*\{` regex false-rejected grouping.
    grouped = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200" width="400" height="200">'
        '<defs><style>'
        '.bg, .card { fill: #fafafa; } .label, .muted { fill: #1a1a1a; }'
        '.accent, .ok { fill: #c0533a; } .watermark, .trailstroke { fill: #87ceeb; }'
        '</style></defs>'
        '<rect class="bg" width="400" height="200"/>'
        '<text x="385" y="18" text-anchor="end" class="watermark">hoiboy.uk</text>'
        '</svg>'
    )
    assert offenders([_write(tmp_path, "grouped.svg", grouped)]) == []


def test_near_miss_class_names_still_fail(tmp_path):
    # The grouped-tolerant regex must NOT over-match: `.bgfoo`/`.accentstroke`/`.watermarked`
    # are DIFFERENT classes, so an SVG declaring only those (not the exact core trio) FAILS.
    near = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200" width="400" height="200">'
        '<defs><style>.bgfoo { fill: #fafafa; } .accentstroke { stroke: #c0533a; }'
        '.watermarked { fill: #87ceeb; }</style></defs>'
        '<text x="385" y="18" text-anchor="end" fill="#87ceeb">hoiboy.uk</text>'
        '<rect class="bgfoo" width="400" height="200"/></svg>'
    )
    res = offenders([_write(tmp_path, "near.svg", near)])
    assert res and any("canonical class" in r for r in res[0][1])


# --- Scope floor -----------------------------------------------------------
# The coverage floor is on whether the SCOPE could be OPENED, not on how many
# SVGs it happened to hold. Applied to the count, it made the only live caller
# (scripts/pre-publish.sh, which runs this per page bundle) fail on the ordinary
# case: 78 of 87 post bundles legitimately contain no SVG. run_check exits on
# failure, so that exit-2 stopped the run before six later gates -- including
# subscribe-placement, the 404 gate and the rendered-card check -- ever ran.
#
# These pin all three outcomes so the distinction cannot quietly collapse back
# into "no files means no evidence" (Ralph round 19 Tier 3).

def _run(monkeypatch, tmp_path, *args):
    """Invoke main() with argv, from tmp_path, returning its exit code."""
    monkeypatch.chdir(tmp_path)
    return main(["check_svg_dimensions.py", *args])


def test_an_existing_scope_with_no_svg_is_a_clean_pass(monkeypatch, tmp_path, capsys):
    bundle = tmp_path / "content" / "posts" / "no-diagrams"
    bundle.mkdir(parents=True)
    (bundle / "index.md").write_text("# no diagrams here\n", encoding="utf-8")

    rc = _run(monkeypatch, tmp_path, "content/posts/no-diagrams")
    out = capsys.readouterr().out

    assert rc == 0, (
        "a page bundle that legitimately contains no SVG must PASS. Failing it "
        "stops pre-publish.sh before every gate that runs after this one."
    )
    assert "no SVG" in out and "scope enumerated" in out, (
        f"the clean pass must say the scope was enumerated and held nothing, "
        f"not claim compliance for files it never saw: {out!r}"
    )


def test_a_scope_that_does_not_exist_is_vacuous(monkeypatch, tmp_path, capsys):
    (tmp_path / "content").mkdir()
    rc = _run(monkeypatch, tmp_path, "content/typo-in-this-path")
    err = capsys.readouterr().err

    assert rc == 2, (
        "a path that does not exist means nothing was opened, so no compliance "
        "claim can be made. That must be exit 2 (could not look), never 0."
    )
    assert "vacuous-gate" in err and "scope not found" in err, (
        f"the refusal must name why it could not look: {err!r}"
    )


def test_a_whole_tree_run_with_no_svg_anywhere_is_still_vacuous(
    monkeypatch, tmp_path, capsys
):
    # This path floors via gate_coverage.require_examined, which RAISES
    # SystemExit rather than returning, so the code is read off the exception.
    # The exit code alone is not enough -- an unrelated crash also raises -- so
    # the refusal message is asserted as well.
    (tmp_path / "content").mkdir()
    with pytest.raises(SystemExit) as excinfo:
        _run(monkeypatch, tmp_path)
    captured = capsys.readouterr()

    assert excinfo.value.code == 2, (
        "with NO argument the gate claims to cover all of content/, so finding "
        "zero SVGs there means the glob is wrong or the tree has none -- the "
        "original vacuity case, which must stay floored."
    )
    assert "vacuous-gate" in (captured.err + captured.out), (
        f"the whole-tree floor must announce itself as a coverage refusal, not "
        f"merely exit non-zero: {captured.err + captured.out!r}"
    )


# The floor's predicate is ENUMERABILITY, not existence. `os.path.exists` proves
# a path resolves; it says nothing about whether the contents can be listed, and
# glob.glob swallows a PermissionError and returns []. Both gaps below were
# false PASSES in the first version of this floor -- the very shape it exists to
# stop, reintroduced by the fix (Ralph round 20 Tier 2).


def test_an_unreadable_directory_is_vacuous_not_clean(monkeypatch, tmp_path, capsys):
    if os.geteuid() == 0:
        pytest.skip("running as root: mode 000 does not deny access")
    hidden = tmp_path / "content" / "locked" / "sub"
    hidden.mkdir(parents=True)
    (hidden / "hidden.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "content" / "locked").chmod(0o000)
    try:
        rc = _run(monkeypatch, tmp_path, "content/locked")
        err = capsys.readouterr().err
    finally:
        (tmp_path / "content" / "locked").chmod(0o755)

    assert rc == 2, (
        "a directory that exists but cannot be listed hides every file inside "
        "it. glob returns [] silently, so reporting PASS claims compliance for "
        "an SVG that was never opened."
    )
    assert "not readable" in err, (
        f"the refusal must say the scope could not be listed, not that it was "
        f"absent: {err!r}"
    )


def test_a_glob_under_a_missing_directory_is_vacuous(monkeypatch, tmp_path, capsys):
    (tmp_path / "content").mkdir()
    rc = _run(monkeypatch, tmp_path, "content/typo-dir/**/*.svg")
    err = capsys.readouterr().err

    assert rc == 2, (
        "a glob was exempted from the scope check entirely, so a pattern under "
        "a directory that does not exist matched nothing and reported clean."
    )
    assert "scope not found" in err, f"the refusal must name the cause: {err!r}"


def test_a_glob_under_a_real_directory_matching_nothing_still_passes(
    monkeypatch, tmp_path, capsys
):
    # The contrast case that keeps the fix honest: enumerability is about the
    # directory being walked, not about the pattern matching something. A real
    # directory with no SVG is a complete answer, glob or not.
    (tmp_path / "content" / "posts").mkdir(parents=True)
    rc = _run(monkeypatch, tmp_path, "content/posts/**/*.svg")
    out = capsys.readouterr().out

    assert rc == 0, (
        "a readable directory that genuinely holds no SVG must PASS whether it "
        "was named directly or by pattern; failing it would stop pre-publish.sh "
        "for no reason."
    )
    assert "nothing to check" in out, f"the clean pass must say why: {out!r}"


def test_scope_problem_names_the_two_causes_apart():
    # The messages are the diagnostic; a single generic string would make an
    # unreadable scope indistinguishable from a typo at the call site.
    assert scope_problem("definitely/not/here") is not None
    assert "not found" in scope_problem("definitely/not/here")
    assert scope_problem(".") is None, "the repo root must be enumerable"
