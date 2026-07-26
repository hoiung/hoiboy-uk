#!/usr/bin/env python3
"""Every retired URL resolves, through the rules, to a page that exists.

blog-priv#62 AC 5.6 (posts, categories, bare paths, the 8 feeds) and AC 6.3
(the `/categories/*` taxonomy switched off in Phase 6).

Two halves, and BOTH are needed. A rule can exist and still be useless:

  1. Coverage - every URL in the checked-in retired baseline matches some rule.
  2. Liveness - the target that rule produces is a page the new build actually
     serves, checked against the built tree on disk rather than the sitemap.
     Hugo keeps `.xml` outputs out of sitemap.xml entirely, so a sitemap-only
     check could never see the 8 RSS feeds it claims to cover.

The bare slash-less variant of every retired path is asserted separately, because
a Cloudflare `/x/*` rule does not match `/x`. Since blog-priv#64 an uncaught `/x`
returns a real 404 instead of soft-404ing to the homepage, so the failure is at
least visible now, but the bare rules still matter: a 301 to the page the reader
wanted beats a correct 404, and it preserves the ranking the old URL carries.
`static/_redirects` documents that gotcha for /consulting; this test is what
stops it being documented but unenforced.

Usage:  python3 scripts/test_redirects_coverage.py [--built public]
Exit 0 = every retired URL lands somewhere real. Exit 1 = a named failure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from redirects_rules import parse, resolve  # noqa: E402

REDIRECTS = ROOT / "static" / "_redirects"
BASELINE = ROOT / "scripts" / "tests" / "fixtures" / "blogs_ia" / "retired_urls.txt"


def read_baseline() -> list[str]:
    if not BASELINE.exists():
        sys.exit(f"AC 5.6: baseline not found at {BASELINE}; a redirect set can only "
                 f"be proven complete against the URLs that used to exist")
    urls = [ln.strip() for ln in BASELINE.read_text(encoding="utf-8").splitlines()]
    return [u for u in urls if u.startswith("/")]


def serves(built: Path, url: str) -> bool:
    """True iff the built tree actually has something at `url`.

    Filesystem ground truth, not the sitemap: `.xml` outputs never appear in
    sitemap.xml, and a redirect pointing at a feed that does not exist is exactly
    the failure this is here to catch.
    """
    rel = url.lstrip("/")
    if not rel:
        return (built / "index.html").is_file()
    if rel.endswith(".xml") or rel.endswith(".html"):
        return (built / rel).is_file()
    return (built / rel.rstrip("/") / "index.html").is_file()


def check(built: Path, failures: list[str]) -> int:
    rules = parse(REDIRECTS)
    retired = read_baseline()
    if not retired:
        failures.append("AC 5.6: the retired-URL baseline is empty (vacuous pass)")
        return 0

    checked = 0
    for url in retired:
        # Both the canonical form and its slash-less variant. The second is not a
        # nicety: /x/* does not match /x under Cloudflare.
        variants = [url]
        if url.endswith("/") and url != "/":
            variants.append(url.rstrip("/"))
        for variant in variants:
            checked += 1
            hit = resolve(rules, variant)
            if hit is None:
                failures.append(
                    f"AC 5.6: retired URL {variant} matches NO rule in "
                    f"{REDIRECTS.name}, so it 404s"
                )
                continue
            rule, target = hit
            if not serves(built, target):
                failures.append(
                    f"AC 5.6: {variant} redirects (line {rule.line_no}) to {target}, "
                    f"which the build does not serve. The link is dead on the far side."
                )
    return checked


def check_taxonomy_gone(built: Path, failures: list[str]) -> None:
    """AC 6.3 - the /categories/ URLs must be redirected AND no longer built, or the
    old page would still answer directly and compete with its landing."""
    if (built / "categories").exists():
        failures.append(
            "AC 6.3: public/categories/ still exists in the build. The `categories` "
            "taxonomy must be off (hugo.toml [taxonomies]) so the only thing serving "
            "those URLs is the 301."
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

    failures: list[str] = []
    if not REDIRECTS.is_file():
        print(f"FAIL: {REDIRECTS} does not exist", file=sys.stderr)
        return 1
    if not built.is_dir():
        print(f"FAIL: built site not found at {built} (run `hugo` first)", file=sys.stderr)
        return 1

    checked = check(built, failures)
    check_taxonomy_gone(built, failures)

    if failures:
        print(f"FAIL: {len(failures)} redirect-coverage violation(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"OK: {checked} retired URL forms (canonical + slash-less) all resolve "
          f"through static/_redirects to a page the build serves")
    return 0


def test_redirects_coverage() -> None:
    """pytest entry point (CI runs pytest through explicit file lists)."""
    assert main([]) == 0


if __name__ == "__main__":
    sys.exit(main())
