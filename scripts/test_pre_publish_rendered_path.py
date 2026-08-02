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
import subprocess
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


@pytest.mark.skipif(not PUBLIC.is_dir(), reason="./public not built")
def test_taxonomy_rejection_fires_behaviourally_not_just_textually():
    """Execute the branch, don't just grep for it (#55, Ralph Tier 3).

    Ralph Tier 3 correctly observed that the taxonomy-rejection loop is never
    REACHED in normal operation: it only runs when the direct
    `public/<section>/<slug>/index.html` path is missing, and for every real
    collision slug that file exists, so the fallback never fires. A source-text
    assertion alone would survive the branch being inverted.

    This drives the real function with a slug that collides with a tag page while
    having NO direct path, which is the only way in. `foundation` is the live
    collision: public/tags/foundation/ and public/blogs/foundation/ both exist.
    """
    tags_page = PUBLIC / "tags" / "foundation" / "index.html"
    if not tags_page.is_file():
        pytest.skip("the tags/foundation collision no longer exists in the build")

    # section `nonexistent` gives expected_prefix=public/nonexistent/, so the
    # direct path is absent and the find-by-slug fallback is forced to run.
    script = f"""
    set -uo pipefail
    REPO_ROOT={ROOT}
    TARGET=content/nonexistent/foundation/index.md
    POST_FILE=/dev/null
    {_function_source()}
    rendered_link_check
    echo "RC=$?"
    """
    r = subprocess.run(["bash", "-c", script], cwd=ROOT, capture_output=True, text=True)
    combined = r.stdout + r.stderr

    assert "refusing taxonomy page" in combined, (
        "the fallback did not refuse public/tags/foundation/index.html. A tag "
        "listing page shares the slug namespace and SORTS FIRST, so without this "
        "the gate checks a term page and reports PASS having never seen the "
        f"target. Output:\n{combined}"
    )
    assert "public/tags/foundation/index.html" in combined, combined


def _function_source() -> str:
    """The real rendered_link_check(), lifted verbatim from the gate script."""
    src = GATE.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(src) if ln.startswith("rendered_link_check()"))
    depth = 0
    for end in range(start, len(src)):
        depth += src[end].count("{") - src[end].count("}")
        if depth == 0 and end > start:
            return "\n".join(src[start:end + 1])
    raise AssertionError("could not delimit rendered_link_check() in the gate script")


@pytest.mark.skipif(not PUBLIC.is_dir(), reason="./public not built")
def test_url_override_resolves_behaviourally_not_just_textually():
    """Drive the real branch; a source-text grep survives it being inverted (#55 Stage 5).

    The three asserts above read pre-publish.sh as TEXT. Stage 5 measured what that
    is worth: rewriting line 302 to `if [[ -n "$fm_url" ]] && false; then` left this
    file at "3 passed, 3 skipped" -- byte-identical to the control. The Ralph Tier 2
    fix was invisible to its own tests, which is the exact shape
    tests/test_gate_mutations.py exists to stop.

    `lychee` is stubbed so this asserts the RESOLUTION CONTRACT only: no network, no
    Hugo build, and the gate's own verdict on link liveness is a different test's job.
    """
    override_page = ROOT / "content" / "community" / "agit-thanks" / "index.md"
    if not override_page.is_file():
        pytest.skip("the agit-thanks url: override page no longer exists")

    script = f"""
    set -uo pipefail
    REPO_ROOT={ROOT}
    TARGET=content/community/agit-thanks/index.md
    POST_FILE={override_page}
    lychee() {{ printf 'stubbed-lychee\\n'; return 0; }}
    {_function_source()}
    rendered_link_check
    echo "RC=$?"
    """
    r = subprocess.run(["bash", "-c", script], cwd=ROOT, capture_output=True, text=True)
    combined = r.stdout + r.stderr

    assert "url: override ->" in combined, (
        "the frontmatter `url:` branch did not fire. This page renders at the path "
        "its override names, not at its slug, so without this branch the gate cannot "
        f"locate it at all and exits 1. Output:\n{combined}"
    )
    assert "public/community/asians-gingers-in-tech/thanks/index.html" in combined, (
        f"the override resolved to the wrong path. Output:\n{combined}"
    )
