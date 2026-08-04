"""Unit tests for check_svg_dimensions.py (the house SVG structural gate, #534).

Run: python3 -m pytest scripts/test_check_svg_dimensions.py -q

Covers all three assertions (root width/height + #87ceeb watermark + canonical class block)
and the documented exemption for the fixed-dark inline form (no <style>).
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_svg_dimensions import offenders

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
