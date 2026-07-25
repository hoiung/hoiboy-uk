#!/usr/bin/env python3
"""Every generated eyebrow fits its card (blog-priv#62 AC 3.4).

AC 3.4 derives a 52-character budget from gen_card.py's eyebrow geometry: font-size
26px, letter-spacing 3px, IBM Plex Mono advance 0.6em => 18.6px per character, over
980px of usable width (1200px card, x=110 inset mirrored on the right).

That derivation is correct for gen_card's cards, but a flat "every trail <= 52 chars"
assertion is NOT the contract, because two things falsify it:

  1. The AGIT feature card has a DIFFERENT geometry — an 18px eyebrow in a 356px
     right-hand panel (gen_agit_feature.py CW - PHOTO_W - 2*PAD), which is ~32
     characters, not 52. A 52-char rule would pass a card that visibly overflows.
  2. The longest real trail on the site is 57 characters, not the 37 the AC records:
     JOIN COMMUNITY > ASIANS & GINGERS IN TECH > AGIT FEATURED, on that same
     356px panel. The AC's enumeration only covered gen_card's sets. A flat 52-char
     rule would fail a card that fits perfectly well once fitted.

So this test asserts the thing the budget was a proxy for: every eyebrow, at the size
its generator actually fits it to, renders inside its own card's usable width. That is
strictly stronger than the character count, and it holds for both geometries.

The 52-character figure is still asserted, as what it really is: the capacity of a
gen_card eyebrow at the full 26px size, i.e. the point beyond which one starts to
shrink. If that derivation ever drifts from the constants, this test says so.

Truncation is never an option here: the operator's decision (A12) is that the eyebrow
shows the full trail however deep. So a trail that will not fit must shrink or wrap,
and this test proves nothing is silently clipped.

Usage:  python3 scripts/test_eyebrow_width.py [--built public]
Exit 0 = every eyebrow fits. Exit 1 = a named page overflows.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "social-cards"))

import card_common  # noqa: E402  (path set above)
import gen_card  # noqa: E402
import gen_agit_feature as agit  # noqa: E402

# gen_agit_feature owns two geometries: the feature card's right-hand panel and the
# section card's text column.
AGIT_FEATURE_W = agit.CW - agit.PHOTO_W - 2 * agit.PAD
AGIT_SECTION_W = agit.CW - agit.SEC_TX - agit.SEC_PAD_R

AGIT_BUNDLE = "community/agit-featured"


def check_budget_derivation(failures: list[str]) -> int:
    """The AC 3.4 arithmetic, re-derived from the constants rather than restated.

    Returns the character capacity at the full size. A change to EB_FS, EB_TRACK or
    EB_USABLE that moves this is a design change, and it should be a visible one.
    """
    per_char = gen_card.EB_FS * 0.6 + gen_card.EB_TRACK
    capacity = int(gen_card.EB_USABLE // per_char)
    if capacity != 52:
        failures.append(
            f"AC 3.4: the gen_card eyebrow budget is now {capacity} characters, not the 52 the "
            f"issue derived (font {gen_card.EB_FS}px, tracking {gen_card.EB_TRACK}px, "
            f"usable {gen_card.EB_USABLE}px). Intended? Update the AC alongside the constants."
        )
    # The fitter must agree with the arithmetic at both ends of the boundary.
    if gen_card.fit_eyebrow("X" * capacity) != gen_card.EB_FS:
        failures.append(f"AC 3.4: fit_eyebrow shrinks a {capacity}-char eyebrow that should fit at full size")
    if gen_card.fit_eyebrow("X" * (capacity + 1)) >= gen_card.EB_FS:
        failures.append(f"AC 3.4: fit_eyebrow does NOT shrink a {capacity + 1}-char eyebrow that overruns")
    return capacity


def check_fail_loud_floor(failures: list[str]) -> None:
    """fit_eyebrow's fail-loud branch fires, and it fires at the DERIVED boundary.

    Ralph Tier 3 (round 4) found that branch had no coverage at all, and Tier 2
    (round 5) confirmed the gap survived the docstring correction: the only other
    assertion on these constants pins the 52/53 full-size capacity, nowhere near the
    min_fs floor. So the number this issue just corrected in prose (78, not 75) had no
    regression backstop, and the exact defect class being fixed -- a stale hand-derived
    constant -- could recur silently on the next tweak.

    Derived here rather than hardcoded, so a deliberate constant change updates the
    expectation while an ACCIDENTAL one still fails: at min_fs the advance is
    min_fs*0.6 + tracking px per character, so floor(usable / advance) characters fit
    and one more must exit.
    """
    advance = gen_card.EB_MIN_FS * 0.6 + gen_card.EB_TRACK
    fits = int(gen_card.EB_USABLE // advance)

    try:
        got = gen_card.fit_eyebrow("X" * fits)
    except SystemExit:
        failures.append(
            f"fit_eyebrow rejected {fits} characters, which the budget says fits at "
            f"{gen_card.EB_MIN_FS}px ({advance}px/char into {gen_card.EB_USABLE}px). "
            f"The floor moved below its derivation."
        )
    else:
        if got != gen_card.EB_MIN_FS:
            failures.append(
                f"fit_eyebrow returned {got}px for {fits} characters, expected the "
                f"{gen_card.EB_MIN_FS}px floor - the shrink ladder stops early."
            )

    try:
        gen_card.fit_eyebrow("X" * (fits + 1))
    except SystemExit:
        pass                                   # correct: overruns even at min_fs
    else:
        failures.append(
            f"fit_eyebrow accepted {fits + 1} characters instead of failing loud. "
            f"That eyebrow runs off the edge of the card, silently, on a generated "
            f"PNG nobody re-reads."
        )


def check_gen_card_pages(trails: dict, failures: list[str]) -> int:
    """Every gen_card-carded page's eyebrow fits 980px at its fitted size."""
    checked = 0
    for bundle in sorted(gen_card_bundles()):
        if bundle not in trails:
            continue                      # coverage is test_trail_manifest.py's job
        eyebrow = card_common.eyebrow_for(trails, bundle)
        if not eyebrow:
            continue                      # no eyebrow line at all
        fs = gen_card.fit_eyebrow(eyebrow)
        width = len(eyebrow) * (fs * 0.6 + gen_card.EB_TRACK)
        if width > gen_card.EB_USABLE:
            failures.append(
                f"AC 3.4: {bundle or '<home>'} eyebrow {eyebrow!r} is {width:.0f}px at {fs}px, "
                f"over the {gen_card.EB_USABLE}px card width"
            )
        checked += 1
    return checked


def gen_card_bundles() -> list[str]:
    """The bundles gen_card cards, read from its own TSV inputs."""
    cards = ROOT / "scripts" / "social-cards"
    out: list[str] = [""]                                   # home
    for tsv, root in (("cards.tsv", "hire-hoi/ai-consultancy"),
                      ("legal-cards.tsv", "legal"),
                      ("hire-hoi-cards.tsv", "hire-hoi"),
                      ("landing-cards.tsv", "")):
        path = cards / tsv
        if not path.exists():
            sys.exit(f"FAIL: missing card input {path}")
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            slug = line.split("\t")[0].strip()
            out.append(f"{root}/{slug}" if root else slug)
    return out


def check_agit_pages(trails: dict, failures: list[str]) -> int:
    """Every AGIT eyebrow fits its own panel, wrapped and fitted, with nothing clipped."""
    checked = 0
    targets = [(AGIT_BUNDLE, AGIT_SECTION_W, agit.SEC_EB_FS)]
    targets += [(k, AGIT_FEATURE_W, agit.EB_FS) for k in sorted(trails) if k.startswith(AGIT_BUNDLE + "/")]
    for bundle, maxw, max_fs in targets:
        if bundle not in trails:
            continue
        eyebrow = card_common.eyebrow_for(trails, bundle)
        if not eyebrow:
            continue
        fs, _ls, lines = agit._fit_eyebrow(eyebrow, maxw, max_fs)
        if not lines:
            failures.append(f"AC 3.4: {bundle} eyebrow {eyebrow!r} fitted to no lines")
            continue
        if len(lines) > agit.EB_LINES:
            failures.append(f"AC 3.4: {bundle} eyebrow wrapped to {len(lines)} lines, over the {agit.EB_LINES} allowed")
        if "".join(lines).replace(" ", "") != eyebrow.replace(" ", ""):
            failures.append(
                f"AC 3.4: {bundle} eyebrow was CLIPPED to fit: {eyebrow!r} -> {lines!r}. The full "
                f"trail must always show (operator decision A12); shrink or wrap, never truncate."
            )
        for line in lines:
            w = agit._measure(line, agit.PLEX_B, fs)
            if w > maxw:
                failures.append(f"AC 3.4: {bundle} eyebrow line {line!r} is {w:.0f}px at {fs}px, over {maxw}px")
        checked += 1
    return checked


def main(argv: list[str] | None = None) -> int:
    """`argv=None` reads sys.argv, which under pytest is the pytest command line
    (file paths + flags), so argparse exits 2 before a single assertion runs. CI
    invokes these through pytest, so the entry point below passes an explicit []
    and this signature is what makes that possible."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--built", default="public", help="built site root (default: public)")
    args = ap.parse_args(argv)

    built = Path(args.built)
    if not built.is_absolute():
        built = ROOT / built
    if not built.is_dir():
        print(f"FAIL: built site not found at {built} (run `hugo` first)", file=sys.stderr)
        return 1

    trails = card_common.load_trails(built)
    failures: list[str] = []

    capacity = check_budget_derivation(failures)
    check_fail_loud_floor(failures)
    n_card = check_gen_card_pages(trails, failures)
    n_agit = check_agit_pages(trails, failures)

    if failures:
        print(f"FAIL: {len(failures)} eyebrow-width violation(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"OK: {n_card} gen_card eyebrows fit {gen_card.EB_USABLE}px "
          f"(full-size capacity {capacity} chars); {n_agit} AGIT eyebrows fit their panels, "
          f"nothing clipped; the fail-loud floor fires at its derived boundary")
    return 0


def test_eyebrow_width() -> None:
    """pytest entry point (CI runs pytest through explicit file lists)."""
    assert main([]) == 0


if __name__ == "__main__":
    sys.exit(main())
