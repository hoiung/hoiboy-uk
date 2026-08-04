#!/usr/bin/env python3
"""Guard: every content SVG must be house-compliant — root width/height + brand chrome.

Three structural assertions on each SVG under content/ (exit 1 + offender list on any miss):

1. Root width AND height. The zoom-image shortcode opens an SVG in a glightbox lightbox; an
   SVG with a viewBox but no intrinsic width/height has no natural size to scale from, so it
   renders TINY when clicked (the bug fixed 2026-06-04 for the 3-types-of-tests + observability
   posts; harness-layers.svg always worked because it carried width/height). Inline display
   stays responsive via CSS; the attributes only fix the lightbox.

2. Brand watermark present — the `hoiboy.uk` signature in the logo's sky blue `#87ceeb`. Every
   illustration carries it (07_DESIGN_TOKENS.md "Brand watermark"), so a missing one is drift.

3. Canonical class block — when the SVG uses a dual-mode `<style>` block it MUST declare the
   core house classes `.bg` + `.accent` + `.watermark` (07_DESIGN_TOKENS.md "Canonical class
   block"), so a diagram cannot ship with ad-hoc off-brand class names. The fixed-dark inline
   form (no `<style>`, e.g. harness-layers.svg) is exempt from (3) — it carries the watermark
   inline (`fill="#87ceeb"`), which (2) already checks.

This is a STRUCTURAL gate (presence/shape), not a visual one — always also RENDER and eyeball
(overlap, arrow endpoints, watermark corner) per ../dotfiles/docs/guides/diagram-annotation-qa.md.
Wired into scripts/pre-publish.sh; runnable standalone: python3 scripts/check_svg_dimensions.py [path ...]

Exit codes:
  0 = looked, and every SVG is house-compliant
  1 = looked, and one is not
  2 = could NOT look: the gate's own coverage failed (nothing collected, a
      declared input absent, or a surface it could not read). Distinct from 0
      on purpose -- "no violations" and "no evidence" are opposite outcomes an
      exit-code check alone cannot tell apart (#56). Taxonomy: scripts/gate_coverage.py.
"""
import sys
import os
import re
import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_coverage import require_examined  # noqa: E402

ROOT_SVG = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)
HAS_W = re.compile(r"\bwidth\s*=", re.IGNORECASE)
HAS_H = re.compile(r"\bheight\s*=", re.IGNORECASE)

# Brand watermark: the hoiboy.uk text in the signature sky blue. Both must be present.
WATERMARK_TEXT = re.compile(r"hoiboy\.uk", re.IGNORECASE)
SKY_BLUE = re.compile(r"#87ceeb", re.IGNORECASE)

# Canonical class block (only enforced when a <style> block exists — the dual-mode form).
# Each class must be DECLARED as a selector. `(?![\w-])` keeps `.bg` from matching a different
# class (`.bgfoo`, `.bg-x`); `\s*[,{]` accepts BOTH a one-per-line rule (`.bg {`) AND a grouped
# selector (`.bg, .panel {` / `.panel, .bg {`) — the old `\.bg\s*\{` false-rejected grouping.
HAS_STYLE = re.compile(r"<style\b", re.IGNORECASE)
CORE_CLASSES = {
    ".bg": re.compile(r"\.bg(?![\w-])\s*[,{]", re.IGNORECASE),
    ".accent": re.compile(r"\.accent(?![\w-])\s*[,{]", re.IGNORECASE),
    ".watermark": re.compile(r"\.watermark(?![\w-])\s*[,{]", re.IGNORECASE),
}


def offenders(paths):
    """Return [(path, [reason, ...]), ...] for every SVG that fails any house assertion."""
    bad = []
    for p in paths:
        try:
            text = open(p, encoding="utf-8").read()
        except OSError as e:
            bad.append((p, [f"unreadable: {e}"]))
            continue
        reasons = []
        m = ROOT_SVG.search(text)
        if not m:
            bad.append((p, ["no <svg> root element found"]))
            continue
        tag = m.group(0)
        # (1) root width/height
        missing = [d for d, rx in (("width", HAS_W), ("height", HAS_H)) if not rx.search(tag)]
        if missing:
            reasons.append(f"root <svg> missing {', '.join(missing)} (glightbox renders it tiny)")
        # (2) brand watermark
        if not (WATERMARK_TEXT.search(text) and SKY_BLUE.search(text)):
            reasons.append("missing brand watermark (hoiboy.uk text in #87ceeb, top-right)")
        # (3) canonical class block — only for the dual-mode <style> form
        if HAS_STYLE.search(text):
            absent = [name for name, rx in CORE_CLASSES.items() if not rx.search(text)]
            if absent:
                reasons.append(
                    f"<style> block missing canonical class(es) {', '.join(absent)} "
                    "(use the 07_DESIGN_TOKENS.md canonical class block, not ad-hoc names)")
        if reasons:
            bad.append((p, reasons))
    return bad


def main(argv):
    args = argv[1:]
    if args:
        paths = []
        for a in args:
            paths.extend(glob.glob(a, recursive=True) if any(c in a for c in "*?[") else [a])
        paths = [p for p in paths if p.endswith(".svg")]
        if not paths:
            # a page-bundle dir was passed: scan it
            paths = []
            for a in args:
                paths.extend(glob.glob(f"{a.rstrip('/')}/**/*.svg", recursive=True))
    else:
        paths = glob.glob("content/**/*.svg", recursive=True)

    # A glob that matches nothing used to print "PASS: all 0 content SVG(s)
    # house-compliant" and exit 0. Every compliance claim in that sentence is
    # true of the empty set, which is why it reads as a healthy run of a small
    # tree rather than as a gate that never opened a file. See
    # scripts/gate_coverage.py for the class and tests/test_gate_vacuity.py for
    # the enforcement.
    # The floor is on the SCOPE, not on the SVG COUNT, and the difference is
    # load-bearing. Applied to the count, it made the only live caller fail on
    # the ordinary case: pre-publish.sh runs this per page bundle, and 78 of 87
    # post bundles legitimately contain no SVG. Because run_check exits on
    # failure, that exit-2 stopped the run before six later checks -- including
    # the subscribe-placement, 404 and rendered-card gates -- ever ran. A floor
    # that turns a correct clean result into a hard stop protects nothing and
    # costs every check behind it (Ralph round 19 Tier 3).
    #
    # "Examined nothing" therefore means the scope could not be OPENED, which is
    # the case that genuinely proves nothing. A scope that exists and holds no
    # SVG is a real and complete answer, and says so rather than claiming
    # compliance for files it never saw.
    paths = sorted(set(paths))
    if args:
        missing = [a for a in args if not any(c in a for c in "*?[") and not os.path.exists(a)]
        if missing:
            print(
                f"[vacuous-gate] check_svg_dimensions: scope not found: "
                f"{', '.join(missing)}. Nothing was opened, so no compliance claim "
                f"can be made. Check the path.",
                file=sys.stderr,
            )
            return 2
        if not paths:
            print(f"PASS: no SVG in {', '.join(args)} (scope opened, nothing to check)")
            return 0
    else:
        require_examined(
            "check_svg_dimensions",
            "SVG file",
            paths,
            hint="content/ has no SVG at all. Either the tree genuinely has none "
                 "(remove this gate from the caller rather than run it blind), or "
                 "the glob is wrong.",
        )

    bad = offenders(paths)
    if bad:
        print("FAIL: SVG(s) not house-compliant (dimensions / watermark / canonical class block):")
        for p, reasons in bad:
            for why in reasons:
                print(f"  - {p}: {why}")
        print("Fix: see ../dotfiles/docs/guides/diagram-annotation-qa.md (reproduce-list) + "
              "07_DESIGN_TOKENS.md. Root e.g. viewBox=\"0 0 880 360\" width=\"880\" height=\"360\"; "
              "watermark <text class=\"watermark\" ...>hoiboy.uk</text> (#87ceeb); copy the "
              "canonical <style> class block into <defs>.")
        return 1
    print(f"PASS: all {len(paths)} content SVG(s) house-compliant "
          "(root width/height + #87ceeb watermark + canonical class block)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
