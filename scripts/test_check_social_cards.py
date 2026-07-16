#!/usr/bin/env python3
"""Unit tests for check_social_cards.py (hoiboy-uk #52).

Covers both failure classes, every exclusion path, the content-format spread
(.md/.markdown/.html), nested child bundles, SVG share-cards, the rendered-HTML
backstop, and CLI exit codes.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
GUARD = SCRIPTS / "check_social_cards.py"

_spec = importlib.util.spec_from_file_location("check_social_cards", GUARD)
csc = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = csc
_spec.loader.exec_module(csc)

PNG = b"\x89PNG\r\n\x1a\n"


def _bundle(root: Path, rel: str, frontmatter: str = "title: X",
            card: str | None = "share-card.png", ext: str = ".md"):
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / ("index" + ext)).write_text(f"---\n{frontmatter}\n---\nbody\n", encoding="utf-8")
    if card:
        cp = d / card
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_bytes(PNG) if cp.suffix.lower() != ".svg" else cp.write_text("<svg/>")
    return d


def _flat(root: Path, rel: str, ext: str = ".md", frontmatter: str = "title: X"):
    p = (root / rel).with_suffix(ext)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{frontmatter}\n---\nbody\n", encoding="utf-8")
    return p


def _headers(root: Path, body: str) -> Path:
    p = root / "_headers"
    p.write_text(body, encoding="utf-8")
    return p


def _cats(violations, tag):
    return [v for v in violations if v.startswith(f"[{tag}]")]


# ---- clean baseline -----------------------------------------------------------

def test_clean_tree_passes(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/a")
    (content / "posts" / "_index.md").write_text("---\ntitle: Posts\n---\n")
    assert csc.check(content, _headers(tmp_path, "")) == []


# ---- Check A: flat pages must be bundles (all content formats) ----------------

def test_flat_md_flagged(tmp_path):
    content = tmp_path / "content"
    (content / "legal").mkdir(parents=True)
    (content / "legal" / "_index.md").write_text("---\ntitle: Legal\n---\n")
    _flat(content, "legal/privacy", ".md")
    v = csc.check(content, _headers(tmp_path, ""))
    assert len(_cats(v, "bundle-form")) == 1 and "legal/privacy.md" in v[0]


def test_flat_markdown_flagged(tmp_path):
    content = tmp_path / "content"
    _flat(content, "legal/cookies", ".markdown")
    assert len(_cats(csc.check(content, _headers(tmp_path, "")), "bundle-form")) == 1


def test_flat_html_flagged(tmp_path):
    content = tmp_path / "content"
    _flat(content, "legal/terms", ".html")
    assert len(_cats(csc.check(content, _headers(tmp_path, "")), "bundle-form")) == 1


def test_bundle_resource_md_not_flagged(tmp_path):
    content = tmp_path / "content"
    d = _bundle(content, "community/feature")
    (d / "social.md").write_text("---\ntitle: social\n---\nsnippet\n")
    assert _cats(csc.check(content, _headers(tmp_path, "")), "bundle-form") == []


def test_nested_md_resource_not_flagged(tmp_path):
    # a .md in a SUBFOLDER of a leaf bundle is a resource, not a flat page (ancestor-walk)
    content = tmp_path / "content"
    d = _bundle(content, "posts/deep")
    (d / "notes").mkdir()
    (d / "notes" / "extra.md").write_text("---\ntitle: n\n---\nx\n")
    assert _cats(csc.check(content, _headers(tmp_path, "")), "bundle-form") == []


# ---- Check B: card presence ---------------------------------------------------

def test_missing_card_flagged(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/nocard", card=None)
    assert len(_cats(csc.check(content, _headers(tmp_path, "")), "card-missing")) == 1


def test_svg_only_bundle_flagged(tmp_path):
    content = tmp_path / "content"
    d = _bundle(content, "posts/svgonly", card=None)
    (d / "diagram.svg").write_text("<svg/>")
    assert len(_cats(csc.check(content, _headers(tmp_path, "")), "card-missing")) == 1


def test_share_card_svg_only_flagged(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/svgcard", card="share-card.svg")
    assert len(_cats(csc.check(content, _headers(tmp_path, "")), "card-svg")) == 1


def test_share_card_svg_beside_raster_flagged(tmp_path):
    # head.html picks share-card.* first; an SVG share-card wins over a raster hero
    # and emits NO og:image, so the raster does not save it.
    content = tmp_path / "content"
    d = _bundle(content, "posts/svgplus", card="share-card.svg")
    (d / "hero.webp").write_bytes(PNG)
    assert len(_cats(csc.check(content, _headers(tmp_path, "")), "card-svg")) == 1


def test_share_card_png_passes(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/ok", card="share-card.png")
    assert csc.check(content, _headers(tmp_path, "")) == []


def test_top_level_raster_passes(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/photo", card="hero.webp")
    assert csc.check(content, _headers(tmp_path, "")) == []


def test_nested_raster_passes(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/gallery", card="website/shot-01.jpg")
    assert csc.check(content, _headers(tmp_path, "")) == []


def test_html_bundle_no_card_flagged(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "consulting/newsvc", card=None, ext=".html")
    assert len(_cats(csc.check(content, _headers(tmp_path, "")), "card-missing")) == 1


def test_html_bundle_with_card_passes(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "consulting/newsvc", card="share-card.png", ext=".html")
    assert csc.check(content, _headers(tmp_path, "")) == []


def test_nested_child_bundle_parent_flagged(tmp_path):
    # parent has NO card; the child's card must NOT be credited to the parent.
    content = tmp_path / "content"
    _bundle(content, "consulting/parent", card=None)
    _bundle(content, "consulting/parent/child", card="share-card.png")
    v = csc.check(content, _headers(tmp_path, ""))
    miss = _cats(v, "card-missing")
    assert len(miss) == 1 and "consulting/parent/index.md" in miss[0]


# ---- Exclusions ---------------------------------------------------------------

def test_frontmatter_noindex_excluded(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "private/tool", frontmatter="title: T\nnoindex: true", card=None)
    assert csc.check(content, _headers(tmp_path, "")) == []


def test_frontmatter_draft_excluded(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/wip", frontmatter="title: T\ndraft: true", card=None)
    assert csc.check(content, _headers(tmp_path, "")) == []


def test_sitemap_disable_excluded(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/hidden", frontmatter="title: T\nsitemap:\n  disable: true", card=None)
    assert csc.check(content, _headers(tmp_path, "")) == []


def test_headless_excluded(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/headless", frontmatter="title: T\nheadless: true", card=None)
    assert csc.check(content, _headers(tmp_path, "")) == []


def test_build_render_never_excluded(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/norender", frontmatter="title: T\nbuild:\n  render: never", card=None)
    assert csc.check(content, _headers(tmp_path, "")) == []


def test_headers_noindex_glob_excluded(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "private/tools/rec", card=None)
    headers = _headers(tmp_path, "/private/*\n  X-Robots-Tag: noindex, nofollow\n")
    assert csc.check(content, headers) == []


def test_url_override_honoured_for_headers_match(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "foo/thanks", frontmatter='title: T\nurl: "/section/thanks/"', card=None)
    headers = _headers(tmp_path, "/section/thanks/*\n  X-Robots-Tag: noindex\n")
    assert csc.check(content, headers) == []


def test_slug_override_honoured_for_headers_match(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/oldname", frontmatter="title: T\nslug: newname", card=None)
    headers = _headers(tmp_path, "/posts/newname/*\n  X-Robots-Tag: noindex\n")
    assert csc.check(content, headers) == []


def test_headers_xrobots_none_excluded(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "hidden/page", card=None)
    headers = _headers(tmp_path, "/hidden/*\n  X-Robots-Tag: none\n")
    assert csc.check(content, headers) == []


def test_headers_non_trailing_wildcard_glob(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "a/mid/b", card=None)
    headers = _headers(tmp_path, "/a/*/b/\n  X-Robots-Tag: noindex\n")
    assert csc.check(content, headers) == []


# ---- Rendered-HTML backstop (--built) -----------------------------------------

def _render(public: Path, url: str, og: str):
    d = public / url.strip("/")
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(
        f'<html><head><meta property="og:image" content="{og}"></head></html>',
        encoding="utf-8")


def test_built_default_ogimage_flagged(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "legal/privacy", card="share-card.png")   # source is fine...
    public = tmp_path / "public"
    _render(public, "/legal/privacy/", "https://x/default-card_hu_1.jpg")   # ...but render defaulted
    v = csc.check_built(content, _headers(tmp_path, ""), public)
    assert len(_cats(v, "rendered-default")) == 1


def test_built_own_card_passes(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "legal/privacy", card="share-card.png")
    public = tmp_path / "public"
    _render(public, "/legal/privacy/", "https://x/legal/privacy/share-card_hu_1.jpg")
    assert csc.check_built(content, _headers(tmp_path, ""), public) == []


def test_built_excluded_page_not_checked(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "private/tool", frontmatter="title: T\nnoindex: true", card=None)
    public = tmp_path / "public"
    _render(public, "/private/tool/", "https://x/hoi-mug_hu_1.jpg")
    assert csc.check_built(content, _headers(tmp_path, ""), public) == []


# ---- CLI ----------------------------------------------------------------------

def test_cli_exit_codes(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/ok")
    headers = _headers(tmp_path, "")
    ok = subprocess.run([sys.executable, str(GUARD), "--content", str(content),
                         "--headers", str(headers)], capture_output=True)
    assert ok.returncode == 0

    _bundle(content, "posts/bad", card=None)
    bad = subprocess.run([sys.executable, str(GUARD), "--content", str(content),
                          "--headers", str(headers)], capture_output=True)
    assert bad.returncode == 1

    missing = subprocess.run([sys.executable, str(GUARD), "--content",
                              str(tmp_path / "nope")], capture_output=True)
    assert missing.returncode == 2
