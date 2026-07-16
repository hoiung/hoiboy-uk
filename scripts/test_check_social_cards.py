#!/usr/bin/env python3
"""Unit tests for check_social_cards.py (hoiboy-uk #52).

Covers both failure classes and every exclusion path, plus CLI exit codes:
  Check A  - a flat <slug>.md page is flagged; a bundle-internal resource
             (social.md next to index.md) and _index.md are not.
  Check B  - a leaf bundle with no card is flagged; one with a share-card,
             a top-level raster, or a nested raster passes.
  Exclusions - _headers noindex glob (with url: override), frontmatter
             noindex/draft/sitemap.disable.
  CLI      - 0 clean, 1 violations, 2 missing content root.
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

PNG_BYTES = b"\x89PNG\r\n\x1a\n"  # enough for a raster file to exist


def _bundle(root: Path, rel: str, frontmatter: str = "title: X", card: str | None = "share-card.png"):
    """Create content/<rel>/index.md, optionally with a card file (path may nest)."""
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.md").write_text(f"---\n{frontmatter}\n---\nbody\n", encoding="utf-8")
    if card:
        cp = d / card
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_bytes(PNG_BYTES)
    return d


def _headers(root: Path, body: str) -> Path:
    p = root / "_headers"
    p.write_text(body, encoding="utf-8")
    return p


def _cats(violations, tag):
    return [v for v in violations if v.startswith(f"[{tag}]")]


def test_clean_tree_passes(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/a")                       # own share-card
    (content / "posts" / "_index.md").write_text("---\ntitle: Posts\n---\n")
    headers = _headers(tmp_path, "")
    assert csc.check(content, headers) == []


def test_flat_md_page_flagged(tmp_path):
    content = tmp_path / "content"
    (content / "legal").mkdir(parents=True)
    (content / "legal" / "_index.md").write_text("---\ntitle: Legal\n---\n")
    (content / "legal" / "privacy.md").write_text("---\ntitle: Privacy\n---\nbody\n")
    v = csc.check(content, _headers(tmp_path, ""))
    assert len(_cats(v, "bundle-form")) == 1
    assert "legal/privacy.md" in v[0]


def test_bundle_resource_md_not_flagged(tmp_path):
    content = tmp_path / "content"
    d = _bundle(content, "community/feature")         # has index.md + share-card
    (d / "social.md").write_text("---\ntitle: social\n---\nsnippet\n")   # a resource
    v = csc.check(content, _headers(tmp_path, ""))
    assert _cats(v, "bundle-form") == []


def test_missing_card_flagged(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/nocard", card=None)
    v = csc.check(content, _headers(tmp_path, ""))
    assert len(_cats(v, "card-missing")) == 1


def test_svg_only_bundle_flagged(tmp_path):
    content = tmp_path / "content"
    d = _bundle(content, "posts/svgonly", card=None)
    (d / "diagram.svg").write_text("<svg/>")
    v = csc.check(content, _headers(tmp_path, ""))
    assert len(_cats(v, "card-missing")) == 1


def test_share_card_svg_not_counted(tmp_path):
    # head.html emits NO og:image for an SVG share-card, so it is not a real card.
    content = tmp_path / "content"
    _bundle(content, "posts/svgcard", card="share-card.svg")
    v = csc.check(content, _headers(tmp_path, ""))
    assert len(_cats(v, "card-missing")) == 1


def test_slug_override_url_for_headers_match(tmp_path):
    # bundle dir is posts/oldname but slug: makes it serve at /posts/newname/
    content = tmp_path / "content"
    _bundle(content, "posts/oldname", frontmatter="title: T\nslug: newname", card=None)
    headers = _headers(tmp_path, "/posts/newname/*\n  X-Robots-Tag: noindex\n")
    assert csc.check(content, headers) == []


def test_headers_xrobots_none_excluded(tmp_path):
    # X-Robots-Tag: none is spec-equivalent to noindex, nofollow.
    content = tmp_path / "content"
    _bundle(content, "hidden/page", card=None)
    headers = _headers(tmp_path, "/hidden/*\n  X-Robots-Tag: none\n")
    assert csc.check(content, headers) == []


def test_top_level_raster_passes(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/photo", card="hero.webp")
    assert csc.check(content, _headers(tmp_path, "")) == []


def test_nested_raster_passes(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/gallery", card="website/shot-01.jpg")
    assert csc.check(content, _headers(tmp_path, "")) == []


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


def test_headers_noindex_glob_excluded(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "private/tools/rec", card=None)
    headers = _headers(tmp_path, "/private/*\n  X-Robots-Tag: noindex, nofollow\n")
    assert csc.check(content, headers) == []


def test_url_override_honoured_for_headers_match(tmp_path):
    # bundle lives at content/foo/thanks but serves at /section/thanks/ via url:
    content = tmp_path / "content"
    _bundle(content, "foo/thanks",
            frontmatter='title: Thanks\nurl: "/section/thanks/"', card=None)
    headers = _headers(tmp_path, "/section/thanks/*\n  X-Robots-Tag: noindex, nofollow\n")
    assert csc.check(content, headers) == []


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
