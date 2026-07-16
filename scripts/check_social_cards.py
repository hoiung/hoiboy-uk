#!/usr/bin/env python3
"""Guard: every singular indexable page must own its social card.

Two failure classes are caught deterministically from the source tree (no Hugo
build needed), matching how ``layouts/_partials/head.html`` resolves ``og:image``:

  Check A - bundle form.  A singular content page must be a leaf bundle
    (``<slug>/index.<ext>``), never a flat ``<slug>.<ext>``.  A flat file cannot
    hold a co-located ``share-card.*``/``hero.*`` resource, so it silently falls
    back to the site default card.  This is the ``.md is not proper`` class (#52).
    Excludes ``_index.*`` (Hugo requires it for sections) and bundle-internal
    resources (a content file anywhere under a leaf-bundle dir tree).

  Check B - card presence.  A singular indexable page's bundle must contain its
    own card, mirroring head.html exactly: a root ``share-card.<raster>`` wins; a
    root ``share-card.svg`` is a VIOLATION (head.html suppresses og:image for an
    SVG); otherwise a non-SVG raster hero anywhere in the bundle (but NOT inside a
    nested child bundle) qualifies; nothing => falls back to the default card.

``ext`` spans the content formats Hugo renders natively on this site: ``.md``,
``.markdown``, ``.html`` (CONTENT_EXTS).

Exclusions (a page legitimately using the shared default card is NOT a
violation), all deterministic:
  - Home + taxonomy/term + section list pages (they have no ``index.*`` bundle;
    only ``_index.*`` or nothing).  Check B only walks leaf bundles.
  - noindex pages: any path matched by an ``X-Robots-Tag: noindex|none`` rule in
    ``static/_headers`` (the source of truth, fnmatch against the page's served
    URL honouring a ``url:`` / ``slug:`` frontmatter override), or frontmatter
    ``noindex`` / ``sitemap.disable`` / ``draft`` / ``headless`` / build render
    ``never``.

Optional ground-truth backstop (``--built <public-dir>``): after a Hugo build,
re-checks each singular indexable page's RENDERED ``og:image`` and fails if it is
the site default / mug.  This catches a head.html/hero-pick TEMPLATE regression
that the source heuristic (which re-implements that logic in Python) cannot see.

Usage:  python3 scripts/check_social_cards.py [--content DIR] [--headers FILE]
        python3 scripts/check_social_cards.py --built public [--content DIR]
Exit:   0 = clean, 1 = violations, 2 = read/setup error
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from pathlib import Path

CONTENT_EXTS = (".md", ".markdown", ".html")   # Hugo natively-rendered content files
RASTER_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
DEFAULT_CARD_MARKERS = ("default-card", "hoi-mug")   # og:image URLs that ARE the site default


def read_frontmatter(path: Path) -> str:
    """Return the raw YAML frontmatter block (between the first two --- lines)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    return m.group(1) if m else ""


def index_file(dirpath: Path) -> Path | None:
    """The leaf-bundle index (index.md/index.markdown/index.html) in dirpath, or None."""
    for ext in CONTENT_EXTS:
        p = dirpath / ("index" + ext)
        if p.exists():
            return p
    return None


def _under_a_bundle(path: Path, content_root: Path) -> bool:
    """True if any ancestor dir (below content_root) is a leaf bundle => path is a resource."""
    d = path.parent
    while True:
        if index_file(d):
            return True
        if d == content_root or d.parent == d:
            return False
        d = d.parent


def _in_child_bundle(bundle_dir: Path, f: Path) -> bool:
    """True if f lives inside a NESTED child leaf bundle under bundle_dir (Hugo scopes
    a child bundle's resources to the child page, not the parent's og:image)."""
    d = f.parent
    while d != bundle_dir:
        if index_file(d):
            return True
        d = d.parent
    return False


def parse_noindex_globs(headers_path: Path) -> list[str]:
    """Path globs that static/_headers marks noindex (X-Robots-Tag: noindex|none)."""
    if not headers_path.exists():
        return []
    globs: list[str] = []
    current: str | None = None
    for raw in headers_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("/"):                      # a path-glob line
            current = raw.strip()
        elif current and re.search(r"X-Robots-Tag:.*\b(noindex|none)\b", raw, re.I):
            globs.append(current)
            current = None                           # one match per block is enough
    return globs


def _url_matches(url: str, glob: str) -> bool:
    """fnmatch a served URL against a Cloudflare _headers glob (handles /foo/*, /a/*/b)."""
    return fnmatch.fnmatch(url, glob) or fnmatch.fnmatch(url.rstrip("/"), glob.rstrip("/*"))


def page_url(index_path: Path, content_root: Path, fm: str) -> str:
    """Served URL: frontmatter `url:` override, else a `slug:` override on the leaf
    segment, else the directory path."""
    m = re.search(r'^url:\s*["\']?([^"\'\n]+?)["\']?\s*$', fm, re.M)
    if m:
        url = m.group(1).strip()
        return url if url.endswith("/") else url + "/"
    parts = list(index_path.parent.relative_to(content_root).parts)
    sm = re.search(r'^slug:\s*["\']?([^"\'\n]+?)["\']?\s*$', fm, re.M)
    if sm and parts:
        parts[-1] = sm.group(1).strip()
    rel = "/".join(parts)
    return "/" + rel + "/" if rel else "/"


def is_excluded(fm: str, url: str, noindex_globs: list[str]) -> bool:
    """A page legitimately using the default card (or not rendered) is not a violation."""
    if re.search(r"^draft:\s*true\s*$", fm, re.M):
        return True
    if re.search(r"^noindex:\s*true\s*$", fm, re.M):
        return True
    if re.search(r"^headless:\s*true\s*$", fm, re.M):
        return True
    if re.search(r"sitemap:\s*\n\s+disable:\s*true", fm):
        return True
    if re.search(r"render:\s*['\"]?never", fm):       # _build.render / build.render: never
        return True
    return any(_url_matches(url, g) for g in noindex_globs)


def card_status(bundle_dir: Path) -> str:
    """Mirror head.html's og:image resolution for a leaf bundle.

    Returns 'ok' (a real card renders), 'svg-sharecard' (a root share-card.svg wins
    and head.html emits NOTHING), or 'none' (falls back to the default card)."""
    share_svg = False
    for f in bundle_dir.iterdir():                    # root-level share-card.* only (GetMatch pattern)
        if f.is_file() and f.name.startswith("share-card."):
            if f.suffix.lower() in RASTER_EXTS:
                return "ok"
            if f.suffix.lower() == ".svg":
                share_svg = True
    if share_svg:
        return "svg-sharecard"
    for f in bundle_dir.rglob("*"):                   # hero: any non-SVG raster, excl. child bundles
        if f.is_file() and f.suffix.lower() in RASTER_EXTS and not _in_child_bundle(bundle_dir, f):
            return "ok"
    return "none"


def leaf_bundles(content_root: Path):
    """Yield (bundle_dir, index_path) for every leaf-bundle page under content_root."""
    seen = set()
    for f in sorted(content_root.rglob("*")):
        if f.is_dir():
            idx = index_file(f)
            if idx and f not in seen:
                seen.add(f)
                yield f, idx


def flat_pages(content_root: Path):
    """Yield every flat singular content page (Check A violation candidate)."""
    for f in sorted(content_root.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in CONTENT_EXTS:
            continue
        if f.stem in ("index", "_index"):
            continue
        if _under_a_bundle(f, content_root):          # a bundle resource, not a page
            continue
        yield f


def check(content_root: Path, headers_path: Path) -> list[str]:
    violations: list[str] = []
    noindex_globs = parse_noindex_globs(headers_path)

    for f in flat_pages(content_root):
        rel = f.relative_to(content_root).as_posix()
        stem = f.parent / f.stem
        violations.append(
            f"[bundle-form] {rel}: flat page must be a leaf bundle "
            f"({stem.relative_to(content_root).as_posix()}/index{f.suffix}) so it can hold a share-card"
        )

    for bundle_dir, index_path in leaf_bundles(content_root):
        fm = read_frontmatter(index_path)
        url = page_url(index_path, content_root, fm)
        if is_excluded(fm, url, noindex_globs):
            continue
        rel = index_path.relative_to(content_root).as_posix()
        status = card_status(bundle_dir)
        if status == "svg-sharecard":
            violations.append(
                f"[card-svg] {rel} ({url}): share-card is an SVG; head.html emits NO "
                f"og:image for an SVG. Use a raster share-card.png (run gen_card.py)."
            )
        elif status == "none":
            violations.append(
                f"[card-missing] {rel} ({url}): no share-card.* or raster hero; "
                f"falls back to the default card. Run gen_card.py or add a hero.*"
            )
    return violations


def check_built(content_root: Path, headers_path: Path, public: Path) -> list[str]:
    """Ground-truth backstop: assert each singular indexable page's RENDERED og:image
    is not the site default. Catches head.html/hero-pick template regressions."""
    violations: list[str] = []
    noindex_globs = parse_noindex_globs(headers_path)
    og_re = re.compile(r'<meta property="og:image" content="([^"]+)"')
    for bundle_dir, index_path in leaf_bundles(content_root):
        fm = read_frontmatter(index_path)
        url = page_url(index_path, content_root, fm)
        if is_excluded(fm, url, noindex_globs):
            continue
        rendered = public / url.strip("/") / "index.html"
        if not rendered.exists():
            continue                                  # alias/permalink edge — source check owns it
        html = rendered.read_text(encoding="utf-8", errors="replace")
        m = og_re.search(html)
        og = m.group(1) if m else ""
        if not og or any(mk in og for mk in DEFAULT_CARD_MARKERS):
            violations.append(
                f"[rendered-default] {url}: rendered og:image is the site default "
                f"({og or 'MISSING'}); a real page must render its own card "
                f"(template regression or missing card)."
            )
    return violations


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--content", default="content", help="content root (default: content)")
    ap.add_argument("--headers", default="static/_headers", help="path to static/_headers")
    ap.add_argument("--built", metavar="PUBLIC_DIR",
                    help="also verify rendered og:image in this Hugo build output dir")
    args = ap.parse_args()

    content_root = Path(args.content)
    if not content_root.is_dir():
        print(f"error: content root not found: {content_root}", file=sys.stderr)
        return 2
    headers_path = Path(args.headers)

    try:
        violations = check(content_root, headers_path)
        if args.built:
            public = Path(args.built)
            if not public.is_dir():
                print(f"error: --built dir not found: {public}", file=sys.stderr)
                return 2
            violations += check_built(content_root, headers_path, public)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if violations:
        print("Social-card guard: violations found\n", file=sys.stderr)
        for v in violations:
            print("  " + v, file=sys.stderr)
        print(f"\n{len(violations)} violation(s).", file=sys.stderr)
        return 1
    scope = "source + rendered" if args.built else "source"
    print(f"Social-card guard: OK ({scope}; every singular indexable page owns its card).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
