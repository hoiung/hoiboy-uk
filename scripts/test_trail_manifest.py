#!/usr/bin/env python3
"""Per-page trail sidecar contract (blog-priv#62 AC 1.4 + AC 1.5).

Two assertions, both against a real build:

  AC 1.4  Every carded page has its own public/<url>/trail.json.
          The set of carded pages is read from the four scripts/social-cards/*.tsv
          inputs plus the home card and the AGIT feature cards, so it is the same
          enumeration the generators use, not a second hand-kept list.

          `/hire-hoi/permanent-roles/` is asserted BY NAME as well as by set
          membership. That page sets `build.list: never`, so it belongs to no
          Hugo page collection: it is absent from the sitemap and from any
          collection-driven manifest, yet it renders and it is carded from
          hire-hoi-cards.tsv. A regression that swapped the per-page output
          format back for a collection walk would still pass a set check built
          from a collection, so the named check is the one that bites.

  AC 1.5  Each trail.json equals the crumb sequence parsed from that page's OWN
          rendered breadcrumb <nav>, minus Home and minus the page's own title.
          This is what proves the JSON and the HTML come from one implementation
          rather than two that happen to agree today.

          /tags/* is excluded from the nav comparison: Hugo derives a tag term
          title from whichever spelling it parses first, and the `ai` tag is
          written "AI" in one post and "ai" in 28, so /tags/ai/ renders as "AI"
          or "Ai" non-deterministically between builds. No tag ever appears in a
          trail, so excluding them costs nothing and not excluding them makes
          this test flake.

Usage:  python3 scripts/test_trail_manifest.py [--built public]
Exit 0 = contract holds. Exit 1 = a named failure, printed with its page.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
CARDS_DIR = ROOT / "scripts" / "social-cards"

REQUIRED_KEYS = {"path", "title", "trail", "url"}

# Named by the operator and carded from hire-hoi-cards.tsv, but in no Hugo page
# collection. See the AC 1.4 note above.
NAMED_COLLECTION_ORPHAN = "hire-hoi/permanent-roles"

NAV_RE = re.compile(r'<nav class="breadcrumbs".*?</nav>', re.S)
CRUMB_RE = re.compile(r"<(a|span)\b[^>]*>(.*?)</\1>", re.S)


def tsv_rows(name: str) -> list[str]:
    """First tab-separated field of each non-comment, non-blank line."""
    path = CARDS_DIR / name
    if not path.exists():
        sys.exit(f"FAIL: missing card input {path}")
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(line.split("\t")[0].strip())
    return rows


def carded_bundles() -> dict[str, str]:
    """Content-relative bundle dir -> the card input that names it.

    Mirrors gen_card.py's four set roots and gen_agit_feature.py's OUTDIR. The
    home card lives in the content root itself (bundle "").
    """
    bundles: dict[str, str] = {}
    for slug in tsv_rows("cards.tsv"):
        bundles[f"hire-hoi/ai-consultancy/{slug}"] = "cards.tsv"
    for slug in tsv_rows("legal-cards.tsv"):
        bundles[f"legal/{slug}"] = "legal-cards.tsv"
    for slug in tsv_rows("hire-hoi-cards.tsv"):
        bundles[f"hire-hoi/{slug}"] = "hire-hoi-cards.tsv"
    for path in tsv_rows("landing-cards.tsv"):
        bundles[path] = "landing-cards.tsv"
    for slug in tsv_rows("agit-features.tsv"):
        bundles[f"community/agit-featured/{slug}"] = "agit-features.tsv"
    bundles["community/agit-featured"] = "gen_agit_feature.py (section card)"
    bundles[""] = "gen_card.py gen_home()"
    return bundles


def content_path_for(bundle: str) -> str:
    """The content path Hugo reports for a bundle dir, e.g. `legal/privacy/index.md`.

    A bundle is a leaf (index.md) or a branch (_index.md); which one is a fact on
    disk, so read it rather than guess. Fail loud if neither exists: a carded
    bundle with no content file is a card pointing at nothing.
    """
    base = CONTENT / bundle if bundle else CONTENT
    for leaf in ("index.md", "_index.md"):
        if (base / leaf).exists():
            return f"{bundle}/{leaf}" if bundle else leaf
    sys.exit(f"FAIL: carded bundle {bundle or '<content root>'!r} has no index.md or _index.md")


def load_trails(built: Path) -> dict[str, dict]:
    """content path -> trail record, for every trail.json in the built tree."""
    by_path: dict[str, dict] = {}
    for f in built.rglob("trail.json"):
        rec = json.loads(f.read_text(encoding="utf-8"))
        missing = REQUIRED_KEYS - set(rec)
        if missing:
            sys.exit(f"FAIL: {f} is missing key(s) {sorted(missing)}")
        if not isinstance(rec["trail"], list) or not all(isinstance(t, str) for t in rec["trail"]):
            sys.exit(f"FAIL: {f} has a non-list-of-strings `trail`: {rec['trail']!r}")
        rec["_file"] = f
        # An auto-generated section page has no source file and reports path "".
        # Key those by URL so they are still reachable, but never by "" (which
        # would collide with the home bundle).
        by_path[rec["path"] or f"<generated>{rec['url']}"] = rec
    return by_path


def nav_crumbs(page_html: Path) -> list[str] | None:
    """Crumb texts from the rendered breadcrumb nav, minus Home and minus the page title.

    The nav shape (Home first, own title last) is ASSERTED, not assumed. Blindly
    dropping texts[0] and texts[-1] makes the parser fail open: a crumb rendered
    before Home is silently swallowed by the slice, so a template that leaked one
    onto every page would still read as clean. Caught by mutation-testing this
    parser during Phase 1, which is exactly the class of hole this issue keeps
    finding in guards that were never made to fail.
    """
    m = NAV_RE.search(page_html.read_text(encoding="utf-8", errors="replace"))
    if not m:
        return None
    texts = [html.unescape(re.sub(r"<[^>]*>", "", t)).strip() for _, t in CRUMB_RE.findall(m.group(0))]
    texts = [t for t in texts if t and t != ">"]
    if not texts or texts[0] != "Home":
        sys.exit(f"FAIL: {page_html} breadcrumb nav does not start with Home: {texts!r}")
    if len(texts) < 2:
        sys.exit(f"FAIL: {page_html} breadcrumb nav has no page-title crumb: {texts!r}")
    return texts[1:-1]


def main(argv: list[str] | None = None) -> int:
    """`argv=None` reads sys.argv, which under pytest is the pytest command line
    (file paths + flags), so argparse exits 2 before a single assertion runs. CI
    invokes these through pytest, so the entry point below passes an explicit []
    and this signature is what makes that possible."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--built", default="public", help="built site root (default: public)")
    args = ap.parse_args(argv)

    built = (ROOT / args.built) if not Path(args.built).is_absolute() else Path(args.built)
    if not built.is_dir():
        print(f"FAIL: built site not found at {built} (run `hugo` first)", file=sys.stderr)
        return 1

    trails = load_trails(built)
    if not trails:
        print(f"FAIL: no trail.json found under {built}", file=sys.stderr)
        return 1

    failures: list[str] = []

    # --- AC 1.4: every carded page has a sidecar -----------------------------
    bundles = carded_bundles()
    if NAMED_COLLECTION_ORPHAN not in bundles:
        failures.append(
            f"{NAMED_COLLECTION_ORPHAN} is no longer named by any card input; it is the "
            "page that falsified the collection-driven manifest, so its coverage must stay asserted"
        )
    for bundle, source in sorted(bundles.items()):
        cpath = content_path_for(bundle)
        if cpath not in trails:
            failures.append(f"carded page {bundle or '<home>'!r} (from {source}) has no trail.json for content path {cpath!r}")

    # --- AC 1.5: sidecar == the page's own rendered nav -----------------------
    compared = 0
    for key, rec in sorted(trails.items()):
        url = rec["url"]
        if url.startswith("/tags/"):
            continue
        page = built / url.strip("/") / "index.html"
        if not page.exists():
            failures.append(f"trail.json at {rec['_file']} points at {url} but {page} does not exist")
            continue
        rendered = nav_crumbs(page)
        if rendered is None:
            # Home renders no breadcrumb by design; its trail must be empty.
            if url == "/":
                if rec["trail"]:
                    failures.append(f"home renders no breadcrumb but its trail is {rec['trail']!r}")
                continue
            failures.append(f"{url} has a trail.json but no rendered breadcrumb nav")
            continue
        if rendered != rec["trail"]:
            failures.append(f"{url}: trail.json {rec['trail']!r} != rendered nav {rendered!r}")
        compared += 1

    if failures:
        print(f"FAIL: {len(failures)} trail-manifest violation(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"OK: {len(bundles)} carded pages have sidecars; {compared} sidecars match their rendered nav ({len(trails)} total)")
    return 0


def test_trail_manifest() -> None:
    """pytest entry point (CI runs pytest through explicit file lists)."""
    assert main([]) == 0


if __name__ == "__main__":
    sys.exit(main())
