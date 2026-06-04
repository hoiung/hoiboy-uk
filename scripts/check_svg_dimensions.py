#!/usr/bin/env python3
"""Guard: every content SVG must declare root width AND height attributes.

Why: the zoom-image shortcode opens an SVG in a glightbox lightbox. An SVG with
a viewBox but no intrinsic width/height has no natural size for the lightbox to
scale from, so it renders TINY when clicked (the bug fixed on 2026-06-04 for the
3-types-of-tests + observability posts; the consulting harness-layers.svg always
worked because it carried width/height). The inline display stays responsive via
CSS (.zoom-image img { width:100% }); the attributes only fix the lightbox.

Checks the ROOT <svg> opening tag of each SVG under content/. Fails (exit 1) and
lists offenders if width or height is missing. Wired into scripts/pre-publish.sh
and runnable standalone:  python3 scripts/check_svg_dimensions.py [path ...]
"""
import sys
import re
import glob

ROOT_SVG = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)
HAS_W = re.compile(r"\bwidth\s*=", re.IGNORECASE)
HAS_H = re.compile(r"\bheight\s*=", re.IGNORECASE)


def offenders(paths):
    bad = []
    for p in paths:
        try:
            text = open(p, encoding="utf-8").read()
        except OSError as e:
            bad.append((p, f"unreadable: {e}"))
            continue
        m = ROOT_SVG.search(text)
        if not m:
            bad.append((p, "no <svg> root element found"))
            continue
        tag = m.group(0)
        missing = []
        if not HAS_W.search(tag):
            missing.append("width")
        if not HAS_H.search(tag):
            missing.append("height")
        if missing:
            bad.append((p, f"root <svg> missing {', '.join(missing)} (glightbox renders it tiny)"))
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
        print("FAIL: SVG(s) missing root width/height (will render tiny in the lightbox):")
        for p, why in bad:
            print(f"  - {p}: {why}")
        print("Fix: add width/height to the root <svg> matching the viewBox, e.g. "
              'viewBox="0 0 880 360" width="880" height="360".')
        return 1
    print(f"PASS: all {len(paths)} content SVG(s) declare root width + height")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
