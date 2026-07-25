#!/usr/bin/env python3
"""Card-eyebrow contract (blog-priv#62 AC 3.2, AC 3.3, AC 3.4b, AC 3.6).

The eyebrow is the one thing the operator asked for by name — "their card should be
BLOGS instead of HOIBOY.UK at the top" — so this test asserts what the eyebrow
actually SAYS, per named page. The other Phase-3 checks are absence-of-old-string,
presence-of-import and width; none of them would notice a card that rendered the
wrong trail.

Four assertions:

  AC 3.4b  Exact eyebrow text for each page the operator named, resolved the way the
           generators resolve it: through the page's own trail.json sidecar.
  AC 3.2   The lookup joins on the CONTENT path, not the served url. Proven by
           rewriting every url in a copy of the sidecar set (simulating the Phase-5
           permalink change) and asserting every eyebrow is unchanged. A url-keyed
           generator would break at Phase 5 and nothing else here would catch it.
  AC 3.3   The 6 top-level cards (Hire Hoi, Legal, Skills, Community, the Blogs hub,
           Home) render with NO eyebrow text node at all.
  AC 3.6   The site-wide default card carries no eyebrow either.

AC 3.3/3.6 are asserted on the markup the SVG builders RETURN, not on a file: the
generators unlink the intermediate .svg immediately after rsvg-convert
(gen_card.py render_card), so no SVG ever persists on disk to grep.

Usage:  python3 scripts/test_eyebrow_render.py [--built public]
Exit 0 = contract holds. Exit 1 = a named failure.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
sys.path.insert(0, str(ROOT / "scripts" / "social-cards"))

import card_common  # noqa: E402  (path set above)
import gen_card  # noqa: E402
import gen_agit_feature  # noqa: E402

# Every page the operator named, plus the deep example he gave. Keys are content
# bundle dirs; values are the exact eyebrow the card must carry.
#
# The three Hire Hoi pages are all listed because he enumerated all three by name
# ("AI Consultancy / ICT Consultancy / Permanent Roles"). An expectation set naming
# only AI Consultancy would narrow his enumerated set.
NAMED_EYEBROWS = {
    # the 7 blog categories -> BLOGS
    "tech-ai": "BLOGS",
    "entrepreneurship": "BLOGS",
    "trading": "BLOGS",
    "food-booze": "BLOGS",
    "adventure": "BLOGS",
    "dance": "BLOGS",
    "life": "BLOGS",
    # the three Hire Hoi pages he named
    "hire-hoi/ai-consultancy": "HIRE HOI",
    "hire-hoi/ict-consultancy": "HIRE HOI",
    "hire-hoi/permanent-roles": "HIRE HOI",
    # his deep example, and one level deeper again
    "hire-hoi/ai-consultancy/claude-code-harness-architect": "HIRE HOI > AI CONSULTANCY",
    "hire-hoi/ai-consultancy/portfolio/chung-ying": "HIRE HOI > AI CONSULTANCY > PORTFOLIO",
}

# Cards with no parent trail: they sit at the top level, so there is nothing above
# them to name. AC 3.3 — "" is the home bundle (content/_index.md).
NO_EYEBROW_BUNDLES = ["hire-hoi", "legal", "skills", "community", "posts", ""]

EYEBROW_CLASS = 'class="eyebrow"'


def _fake_logo() -> str:
    """A 1x1 data URI. The builders only ever interpolate it into an <image href>,
    so a real logo would slow the test down without changing what is asserted."""
    return "data:image/png;base64,iVBORw0KGgo="


def _rewrite_urls(built: Path) -> Path:
    """A copy of the built tree's sidecars with every `url` replaced by a Phase-5-shaped
    one. The files stay where they are: only the url FIELD changes, which is exactly
    the failure a url-keyed join would hit."""
    tmp = Path(tempfile.mkdtemp(prefix="eyebrow-url-move-"))
    for src in built.rglob("trail.json"):
        rec = json.loads(src.read_text(encoding="utf-8"))
        rec["url"] = "/moved" + rec["url"]
        dst = tmp / src.relative_to(built)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(rec), encoding="utf-8")
    return tmp


def check_named(trails: dict, failures: list[str]) -> int:
    """AC 3.4b — exact eyebrow text, per named page."""
    for bundle, expected in sorted(NAMED_EYEBROWS.items()):
        if bundle not in trails:
            failures.append(f"AC 3.4b: named page {bundle!r} has no trail.json (did it render?)")
            continue
        got = card_common.eyebrow_for(trails, bundle)
        if got != expected:
            failures.append(f"AC 3.4b: {bundle} eyebrow is {got!r}, expected {expected!r}")
    return len(NAMED_EYEBROWS)


def check_join_key(built: Path, trails: dict, failures: list[str]) -> None:
    """AC 3.2 — the join survives a permalink change, because it keys on content path."""
    moved_root = _rewrite_urls(built)
    try:
        moved = card_common.load_trails(moved_root)
        for bundle in sorted(NAMED_EYEBROWS):
            if bundle not in trails:
                continue
            before, after = card_common.eyebrow_for(trails, bundle), card_common.eyebrow_for(moved, bundle)
            if before != after:
                failures.append(
                    f"AC 3.2: {bundle} eyebrow changed from {before!r} to {after!r} when only the "
                    f"served urls moved — the lookup is keyed on url, not on the content path"
                )
    finally:
        shutil.rmtree(moved_root, ignore_errors=True)


def check_no_eyebrow(trails: dict, failures: list[str]) -> None:
    """AC 3.3 — the 6 top-level cards emit no eyebrow text node."""
    logo = _fake_logo()
    for bundle in NO_EYEBROW_BUNDLES:
        label = bundle or "<home>"
        if bundle not in trails:
            failures.append(f"AC 3.3: top-level page {label} has no trail.json (did it render?)")
            continue
        eyebrow = card_common.eyebrow_for(trails, bundle)
        if eyebrow:
            failures.append(f"AC 3.3: {label} should have an empty trail but resolved {eyebrow!r}")
            continue
        if bundle == "":
            markup = gen_card.make_home_svg("data:image/jpeg;base64,x", logo, eyebrow=eyebrow)
        else:
            markup = gen_card.make_landing_svg("Title", "Tagline", logo, eyebrow=eyebrow)
        if EYEBROW_CLASS in markup:
            failures.append(f"AC 3.3: {label} card markup still contains an eyebrow text node")


def check_default_card(failures: list[str]) -> None:
    """AC 3.6 — the site-wide fallback card has no eyebrow.

    gen_default() stands for no single page, so it passes an empty eyebrow through
    the same make_svg the real cards use. Asserted on the returned markup because the
    intermediate .svg is unlinked at generation time.
    """
    markup = gen_card.make_svg("", "hoiboy.uk", "Food, booze, adventure, dance, tech and AI.",
                               _fake_logo(), gen_card.HOIBOY_PAL)
    if EYEBROW_CLASS in markup:
        failures.append("AC 3.6: the default card markup still contains an eyebrow text node")
    # And the inverse, so the assertion above cannot pass vacuously on a builder that
    # dropped the eyebrow node entirely.
    with_eyebrow = gen_card.make_svg("BLOGS > TECH & AI", "t", "g", _fake_logo(), gen_card.HOIBOY_PAL)
    if EYEBROW_CLASS not in with_eyebrow or "BLOGS &gt; TECH &amp; AI" not in with_eyebrow:
        failures.append("AC 3.6: make_svg no longer renders an eyebrow when given one — "
                        "the empty-eyebrow assertion above would pass vacuously")


def check_agit(trails: dict, failures: list[str]) -> None:
    """AC 3.4b — the AGIT feature card carries its own rendered breadcrumb trail."""
    bundle = "community/agit-featured"
    if bundle not in trails:
        failures.append(f"AC 3.4b: {bundle} has no trail.json (did it render?)")
        return
    section = card_common.eyebrow_for(trails, bundle)
    expected_section = "JOIN COMMUNITY > ASIANS & GINGERS IN TECH"
    if section != expected_section:
        failures.append(f"AC 3.4b: {bundle} eyebrow is {section!r}, expected {expected_section!r}")
    features = sorted(k for k in trails if k.startswith(bundle + "/"))
    if not features:
        failures.append("AC 3.4b: no AGIT feature page found under community/agit-featured/")
    for feat in features:
        eyebrow = card_common.eyebrow_for(trails, feat)
        if not eyebrow.startswith(expected_section + " > "):
            failures.append(
                f"AC 3.4b: {feat} eyebrow {eyebrow!r} is not its rendered trail "
                f"(expected it to extend {expected_section!r})"
            )
        # The deep AGIT trail is the one that forced the wrapping fitter; assert the
        # markup actually carries every line of it rather than a silently clipped one.
        fs, ls, lines = gen_agit_feature._fit_eyebrow(eyebrow, gen_agit_feature.CW
                                                      - gen_agit_feature.PHOTO_W
                                                      - 2 * gen_agit_feature.PAD,
                                                      gen_agit_feature.EB_FS)
        if "".join(lines).replace(" ", "") != eyebrow.replace(" ", ""):
            failures.append(
                f"AC 3.4b: {feat} eyebrow was clipped when fitted: {eyebrow!r} -> {lines!r}"
            )


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

    named = check_named(trails, failures)
    check_join_key(built, trails, failures)
    check_no_eyebrow(trails, failures)
    check_default_card(failures)
    check_agit(trails, failures)

    if failures:
        print(f"FAIL: {len(failures)} eyebrow violation(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"OK: {named} named eyebrows exact, {len(NO_EYEBROW_BUNDLES)} top-level cards "
          f"eyebrow-free, default card eyebrow-free, join survives a permalink change "
          f"({len(trails)} sidecars)")
    return 0


def test_eyebrow_render() -> None:
    """pytest entry point (CI runs pytest through explicit file lists)."""
    assert main([]) == 0


if __name__ == "__main__":
    sys.exit(main())
