#!/usr/bin/env python3
"""Shared helpers for the social-card generators (gen_card.py, gen_agit_feature.py).

Both render an SVG through rsvg-convert with the type faces embedded as base64
@font-face rules, so the cards render identically anywhere with no system-font
dependency, and both derive their eyebrow line from the same per-page trail
sidecar Hugo emits. Everything else differs (text-only consulting cards vs
photo-driven AGIT feature cards), so only these pieces live here.
"""
import base64
import json
import pathlib
import posixpath
import sys


def b64(path):
    """Base64-encode a file's bytes (for data: URIs)."""
    return base64.b64encode(pathlib.Path(path).read_bytes()).decode()


def font_face(family, ttf, weight):
    """An @font-face rule embedding `ttf` as a base64 data URI."""
    return (f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"src:url(data:font/ttf;base64,{b64(ttf)}) format('truetype');}}")


# --- Card eyebrow: the page's parent trail, from Hugo's per-page sidecar ------
# blog-priv#62. The eyebrow used to be a hardcoded brand string per card set
# ("HOIBOY AI LTD", "HOIBOY.UK", "PERSONAL BLOG", ...). It is now the page's own
# parent trail, derived from exactly the rule that renders the on-page breadcrumb:
# layouts/_partials/breadcrumb-trail.html feeds BOTH the rendered <nav> and the
# trail.json sidecar, so the card and the breadcrumb cannot drift apart.

def load_trails(public):
    """Index every per-page trail.json sidecar by the CONTENT BUNDLE it describes.

    Hugo writes one sidecar per rendered page at public/<url>/trail.json (see
    config/_default/hugo.toml [outputFormats.trails] + [outputs]). Each carries that
    page's content `path`, `title`, parent `trail` and served `url`.

    The index is keyed by the DIRECTORY of the content path, NEVER by `url`. The join
    key is load-bearing: blog-priv#62 Phase 5 rewrites every URL, while both
    generators are keyed by content path (they write share-card.png into
    content/<...>/ page bundles), so a url-keyed join would break silently at the
    permalink change and nothing else in the pipeline would notice.

      content/hire-hoi/ai-consultancy/pricing-billing/index.md -> "hire-hoi/ai-consultancy/pricing-billing"
      content/tech-ai/_index.md                                -> "tech-ai"
      content/_index.md (home)                                 -> ""

    A page with an empty `path` is one of Hugo's auto-generated section pages (no
    _index.md on disk, so `.File` is nil). It owns no content bundle and is never
    carded, so it is skipped rather than collapsed onto a shared "" key where it
    would collide with home.
    """
    public = pathlib.Path(public)
    if not public.is_dir():
        sys.exit(f"trail sidecars not found: {public} is not a directory. Build the site "
                 f"first - scripts/gen-social-cards.sh runs hugo before the generators.")
    trails = {}
    for sidecar in sorted(public.rglob("trail.json")):
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            sys.exit(f"unreadable trail sidecar {sidecar}: {e}")
        path = (data.get("path") or "").strip()
        if not path:
            continue
        key = posixpath.dirname(path)
        if key in trails and trails[key] != data:
            sys.exit(f"two different trail sidecars claim content bundle '{key}': "
                     f"{trails[key]} vs {data} (second from {sidecar})")
        trails[key] = data
    if not trails:
        sys.exit(f"no trail.json sidecar under {public} carries a content path - the trails "
                 f"output format is not building (config/_default/hugo.toml [outputs]).")
    return trails


def bundle_key(bundle_dir, content_root):
    """The load_trails() key for a content page-bundle directory ("" for home)."""
    rel = pathlib.Path(bundle_dir).resolve().relative_to(pathlib.Path(content_root).resolve())
    return "" if str(rel) == "." else rel.as_posix()


def eyebrow_for(trails, key):
    """The card eyebrow for a content bundle: that page's parent trail, uppercased and
    joined with ' > '. Returns "" when the page has no parent - a top-level landing or
    home - and those cards then carry no eyebrow line at all.

    Fails loud and names the bundle when it has no sidecar. There is deliberately no
    default: a card silently falling back to a hardcoded brand string is the exact
    drift this mechanism exists to remove.
    """
    entry = trails.get(key)
    if entry is None:
        sys.exit(f"no trail.json for content bundle '{key or '(home)'}', so its card eyebrow "
                 f"cannot be derived. The page must render before its card is generated - "
                 f"run scripts/gen-social-cards.sh, which builds the site first.")
    return " > ".join(t.upper() for t in entry.get("trail", []))
