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
"""
import sys
import re
import glob

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

    bad = offenders(sorted(set(paths)))
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
