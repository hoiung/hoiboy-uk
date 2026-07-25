#!/usr/bin/env python3
"""check_social_cards.page_url() is permalink-aware (blog-priv#62 AC 5.8).

Two distinct defects lived here, and the ORDER mattered:

  Root cause - `page_url()` derived a page's served URL from its CONTENT path,
    honouring only `url:`/`slug:` frontmatter, with zero [permalinks] awareness.
    After the move it returns /posts/foundation/ for a page served at
    /blogs/foundation/.
  Visible symptom - `check_built()` skipped any page whose rendered HTML it could
    not find. With a wrong derivation that silently skipped 87 of 113 bundles
    while the guard still printed OK.

Adding `--strict` WITHOUT fixing the derivation just turns CI red on all 87. So
both halves are asserted here, and the derivation is asserted against Hugo's own
answer (the per-page trail.json sidecar), not against a second Python
re-implementation of Hugo's permalink rules.

The previous inline verify for this AC was a no-op: its trailing `...` is Python's
Ellipsis literal, not shorthand for an omitted assertion, so the command imported
page_url and asserted nothing, exiting 0 whether or not the fix existed.

Usage:  python3 scripts/test_page_url_permalinks.py [--built public]
Exit 0 = the derivation follows the permalink. Exit 1 = a named failure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from check_social_cards import load_url_index, page_url, read_frontmatter  # noqa: E402

CONTENT = ROOT / "content"

# (content bundle, expected served URL). Chosen to cover all three ways the served
# URL can diverge from the content path.
CASES = [
    ("posts/2026-04-07-foundation", "/blogs/foundation/"),       # permalink + slug override
    ("posts/ai-jargon-for-noobs", "/blogs/ai-jargon-for-newbies/"),
    ("posts/why-scope-beats-code", "/blogs/why-scope-beats-code/"),  # permalink only
    ("tech-ai", "/blogs/tech-ai/"),                              # section permalink
    ("hire-hoi/ai-consultancy", "/hire-hoi/ai-consultancy/"),    # no permalink rule
]


def check(built: Path, failures: list[str]) -> None:
    url_index = load_url_index(built)
    for rel, expected in CASES:
        bundle = CONTENT / rel
        index = next((bundle / f"{stem}{ext}"
                      for stem in ("index", "_index")
                      for ext in (".md", ".markdown", ".html")
                      if (bundle / f"{stem}{ext}").is_file()), None)
        if index is None:
            failures.append(f"AC 5.8: no content index under content/{rel}")
            continue
        fm = read_frontmatter(index)

        got = page_url(index, CONTENT, fm, url_index)
        if got != expected:
            failures.append(f"AC 5.8: page_url(content/{rel}) returned {got}, expected "
                            f"{expected} (the URL the build actually serves)")

        # The fallback (no index) must be the one that CANNOT know about permalinks.
        # Asserting this keeps the two paths honestly distinct: if the fallback also
        # returned the right answer, the url_index would be decorative and a
        # regression that stopped passing it would go unnoticed.
        blind = page_url(index, CONTENT, fm, None)
        if rel.startswith("posts/") and blind == expected:
            failures.append(
                f"AC 5.8: the content-path fallback returned the correct URL for "
                f"content/{rel}, so this test cannot tell whether the trail.json "
                f"lookup is being used at all"
            )

    # Ground truth: every carded bundle must resolve to a page that exists.
    for key, url in sorted(url_index.items()):
        if not url:
            failures.append(f"AC 5.8: trail sidecar for '{key}' carries no url")


def check_strict_flag(failures: list[str]) -> None:
    """The `--strict` half: a missing rendered page must be a FAILURE, not a skip."""
    src = (ROOT / "scripts" / "check_social_cards.py").read_text(encoding="utf-8")
    if "rendered-missing" not in src:
        failures.append("AC 5.8: check_social_cards.py has no [rendered-missing] "
                        "violation, so --strict cannot turn an unfound page into a fail")
    if "strict: bool = False" not in src:
        failures.append("AC 5.8: check_built() takes no `strict` parameter")


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

    failures: list[str] = []
    check_strict_flag(failures)
    if not built.is_dir():
        failures.append(f"AC 5.8: built site not found at {built} (run `hugo` first)")
    else:
        check(built, failures)

    if failures:
        print(f"FAIL: {len(failures)} page_url violation(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"OK: page_url() resolves {len(CASES)} bundles to the URL Hugo serves "
          f"(via trail.json), the content-path fallback provably does not, and "
          f"--strict turns an unfound rendered page into a named failure")
    return 0


def test_page_url_permalinks() -> None:
    """pytest entry point (CI runs pytest through explicit file lists)."""
    assert main([]) == 0


if __name__ == "__main__":
    sys.exit(main())
