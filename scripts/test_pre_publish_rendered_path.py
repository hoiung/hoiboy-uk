#!/usr/bin/env python3
"""`rendered-link-liveness` must resolve the page it was asked about.

The gate reads a page's RENDERED html. Getting that path wrong has failed in
three distinct ways, and each one passed something rather than erroring:

  1. A taxonomy page sorting first. `find public -path "*/<slug>/index.html"`
     returns public/tags/foundation/ before public/blogs/foundation/, so the gate
     checked a tag listing and reported PASS having never seen the post
     (#55 AC 1.7).
  2. A section that is not its own url prefix. Posts render to /blogs/, not
     /posts/, per [permalinks.page] in config/_default/hugo.toml.
  3. A frontmatter `url:` override, which replaces the WHOLE path -- neither the
     section prefix nor the slug describes where the page lands. Found by Ralph
     Tier 2 on #55: content/community/agit-thanks/ renders at
     /community/asians-gingers-in-tech/thanks/, so the gate could not publish it
     at all (exit 1, "cannot locate rendered HTML for slug agit-thanks"). That
     page is one of the 18 AGIT paths AC 3.2 requires be link-checked.

These assert the resolution CONTRACT rather than re-running the whole gate, which
would need a Hugo build per case. The build-dependent test skips when ./public is
absent rather than passing vacuously.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "scripts" / "pre-publish.sh"
PUBLIC = ROOT / "public"


def _url_override_pages() -> list[tuple[Path, str]]:
    """Every content page carrying a frontmatter `url:`, with its override."""
    found = []
    for md in ROOT.joinpath("content").rglob("*.md"):
        text = md.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        fm = text[:end] if end != -1 else text
        m = re.search(r"^url:\s*(.+)$", fm, re.M)
        if m:
            found.append((md, m.group(1).strip().strip("\"'")))
    return found


def test_the_gate_reads_a_url_override_at_all():
    """Guards the fix itself. Without this the gate silently regresses to slug-only."""
    src = GATE.read_text(encoding="utf-8")
    assert re.search(r"fm_url=\$\(awk", src), (
        "scripts/pre-publish.sh no longer parses a frontmatter `url:`. A page "
        "carrying one renders at that exact path, so slug-based resolution looks "
        "in the wrong place and the gate cannot locate it (#55, Ralph Tier 2)."
    )
    assert 'rendered="public/${fm_url#/}"' in src, (
        "the `url:` override is parsed but no longer used to build the rendered path"
    )


def test_url_override_is_authoritative_over_the_slug_search():
    """An override must NOT fall through to the find-by-slug fallback.

    Falling through would search under the wrong parent, and if any unrelated
    page happened to share the slug it could check the wrong file and PASS.
    """
    src = GATE.read_text(encoding="utf-8")
    # the override branch must return/resolve before the WARN-and-search branch
    override_at = src.index('rendered="public/${fm_url#/}"')
    search_at = src.index("looking for any matching slug")
    assert override_at < search_at, (
        "the `url:` override branch must come before the slug search, and the "
        "search must be in its `else`"
    )


@pytest.mark.skipif(not PUBLIC.is_dir(), reason="./public not built")
def test_every_url_override_page_resolves_to_a_built_file():
    """The mapping the gate now relies on must actually hold in the built tree."""
    pages = _url_override_pages()
    assert pages, (
        "no `url:` override page found in content/. If the last one was removed, "
        "delete this test with it; if the parser broke, fix it -- an empty corpus "
        "must not pass silently."
    )
    missing = []
    for md, url in pages:
        rendered = PUBLIC / url.strip("/") / "index.html"
        if not rendered.is_file():
            missing.append(f"{md.relative_to(ROOT)} declares url: {url} -> {rendered} MISSING")
    assert not missing, (
        "a `url:` override points at a path Hugo does not build, so "
        "rendered-link-liveness will fail on it:\n  " + "\n  ".join(missing)
    )


@pytest.mark.skipif(not PUBLIC.is_dir(), reason="./public not built")
def test_the_known_override_page_does_not_resolve_by_slug():
    """Pins WHY the override branch is needed, not merely that it exists.

    If this ever starts resolving by slug, the override handling is no longer
    load-bearing and someone should re-derive the contract rather than assume it.
    """
    by_slug = PUBLIC / "community" / "agit-thanks" / "index.html"
    by_url = PUBLIC / "community" / "asians-gingers-in-tech" / "thanks" / "index.html"
    if not by_url.is_file():
        pytest.skip("the agit-thanks override page is no longer built at that url")
    assert not by_slug.is_file(), (
        "public/community/agit-thanks/index.html now exists, so the slug path "
        "resolves after all. Re-derive whether the `url:` branch is still needed."
    )


def test_taxonomy_pages_are_still_refused():
    """AC 1.7's other half must survive this change."""
    src = GATE.read_text(encoding="utf-8")
    assert "public/tags/*|public/series/*" in src, (
        "the taxonomy-rejection case is gone. A tag listing page shares the slug "
        "namespace and sorts first, so the gate would check it and report PASS "
        "having never seen the target page (#55 AC 1.7)."
    )
