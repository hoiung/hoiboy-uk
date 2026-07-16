#!/usr/bin/env python3
"""Guard: every singular indexable page must own its social card.

Two failure classes are caught deterministically from the source tree (no Hugo
build needed), matching how ``layouts/_partials/head.html`` resolves ``og:image``:

  Check A - bundle form.  A singular content page must be a leaf bundle
    (``<slug>/index.md``), never a flat ``<slug>.md``.  A flat file cannot hold a
    co-located ``share-card.*``/``hero.*`` resource, so it silently falls back to
    the site default card.  This is the ``.md is not proper`` class (#52).
    Excludes ``_index.md`` (Hugo requires it for sections) and bundle-internal
    resources (a ``<name>.md`` whose directory also has an ``index.md``, e.g.
    ``social.md``).

  Check B - card presence.  A singular indexable page's bundle must contain its
    own card: a ``share-card.*`` OR a non-SVG raster (``hero.*`` or any body
    image head.html/hero-pick would select).  A bundle with only SVGs / no image
    resolves to the shared default card - a violation for a real content page.

Exclusions (a page legitimately using the shared default card is NOT a
violation), all deterministic:
  - Home + taxonomy/term + section list pages (they have no ``index.md`` bundle;
    only ``_index.md`` or nothing).  Check B only walks ``**/index.md``.
  - noindex pages: any path matched by an ``X-Robots-Tag: noindex`` rule in
    ``static/_headers`` (the source of truth), or frontmatter ``noindex: true``
    / ``sitemap.disable: true`` / ``draft: true``.  A page's own ``url:``
    frontmatter override is honoured when matching the _headers globs.

Usage:  python3 scripts/check_social_cards.py [--content DIR] [--headers FILE]
Exit:   0 = clean, 1 = violations, 2 = read/setup error
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RASTER_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def read_frontmatter(md_path: Path) -> str:
    """Return the raw YAML frontmatter block (between the first two --- lines)."""
    text = md_path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    return m.group(1) if m else ""


def parse_noindex_globs(headers_path: Path) -> list[str]:
    """Path prefixes that static/_headers marks noindex (X-Robots-Tag: noindex).

    Cloudflare _headers is `path-glob` lines followed by indented `Header: value`
    lines.  We collect each path glob whose block carries an X-Robots-Tag with
    noindex, and turn `/foo/*` into the prefix `/foo/` for matching.
    """
    if not headers_path.exists():
        return []
    prefixes: list[str] = []
    current: str | None = None
    for raw in headers_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("/"):                      # a path-glob line
            current = raw.strip()
        elif current and re.search(r"X-Robots-Tag:.*\b(noindex|none)\b", raw, re.I):
            prefixes.append(current.rstrip("*"))     # /private/* -> /private/
            current = None                           # one match per block is enough
    return prefixes


def page_url(index_md: Path, content_root: Path) -> str:
    """The page URL: frontmatter `url:` override, else a `slug:` override on the
    last path segment, else derived from the directory path."""
    fm = read_frontmatter(index_md)
    m = re.search(r'^url:\s*["\']?([^"\'\n]+?)["\']?\s*$', fm, re.M)
    if m:
        url = m.group(1).strip()
        return url if url.endswith("/") else url + "/"
    parts = list(index_md.parent.relative_to(content_root).parts)
    sm = re.search(r'^slug:\s*["\']?([^"\'\n]+?)["\']?\s*$', fm, re.M)
    if sm and parts:                                  # slug rewrites the leaf segment
        parts[-1] = sm.group(1).strip()
    rel = "/".join(parts)
    return "/" + rel + "/" if rel else "/"


def is_excluded(index_md: Path, url: str, noindex_prefixes: list[str]) -> bool:
    fm = read_frontmatter(index_md)
    if re.search(r"^draft:\s*true\s*$", fm, re.M):
        return True
    if re.search(r"^noindex:\s*true\s*$", fm, re.M):
        return True
    if re.search(r"sitemap:\s*\n\s+disable:\s*true", fm):
        return True
    return any(url.startswith(p) for p in noindex_prefixes)


def has_own_card(bundle_dir: Path) -> bool:
    """A bundle owns its card if it has any non-SVG raster.

    A share-card.png / hero.* / body photo all qualify; an SVG does NOT, even a
    ``share-card.svg`` - head.html gates og:image emission on
    ``not (strings.HasSuffix .Name ".svg")``, so an SVG-only share-card yields no
    og:image at all (worse than the default card). So this asks the same question
    head.html/hero-pick answer: is there a raster to become the og:image?

    Searches recursively: Hugo page-bundle resources include nested files, so a
    post whose photos live in a subfolder (e.g. ``website/*.jpg``) is picked up
    by hero-pick's ``.Resources.ByType "image"``.  (Limitation: a raster inside a
    nested CHILD leaf bundle is credited to the parent here; no such nesting
    exists in content/ today.)
    """
    for f in bundle_dir.rglob("*"):
        if f.is_file() and f.suffix.lower() in RASTER_EXTS:
            return True
    return False


def check(content_root: Path, headers_path: Path) -> list[str]:
    violations: list[str] = []
    noindex_prefixes = parse_noindex_globs(headers_path)

    for md in sorted(content_root.rglob("*.md")):
        name = md.name
        if name == "_index.md" or name == "index.md":
            continue
        # A non-index .md is a bundle RESOURCE (e.g. social.md) if its directory
        # also holds an index.md; otherwise it is a flat standalone page.
        if (md.parent / "index.md").exists():
            continue
        rel = md.relative_to(content_root).as_posix()
        slug = md.stem
        violations.append(
            f"[bundle-form] {rel}: flat page must be a leaf bundle "
            f"({md.parent.as_posix()}/{slug}/index.md) so it can hold a share-card"
        )

    for index_md in sorted(content_root.rglob("index.md")):
        url = page_url(index_md, content_root)
        if is_excluded(index_md, url, noindex_prefixes):
            continue
        if not has_own_card(index_md.parent):
            rel = index_md.relative_to(content_root).as_posix()
            violations.append(
                f"[card-missing] {rel} ({url}): no share-card.* or raster hero; "
                f"falls back to the default card. Run gen_card.py or add a hero.*"
            )
    return violations


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--content", default="content", help="content root (default: content)")
    ap.add_argument("--headers", default="static/_headers", help="path to static/_headers")
    args = ap.parse_args()

    content_root = Path(args.content)
    if not content_root.is_dir():
        print(f"error: content root not found: {content_root}", file=sys.stderr)
        return 2

    try:
        violations = check(content_root, Path(args.headers))
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if violations:
        print("Social-card guard: violations found\n", file=sys.stderr)
        for v in violations:
            print("  " + v, file=sys.stderr)
        print(f"\n{len(violations)} violation(s).", file=sys.stderr)
        return 1
    print("Social-card guard: OK (every singular indexable page owns its card).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
