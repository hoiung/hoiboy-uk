"""The taxonomy and section resolvers must reproduce the tree Hugo builds.

``validate_internal_links.py`` decides whether ``/tags/<term>/``,
``/series/<term>/`` and ``/hire-hoi|legal|community/...`` links are real by
deriving the served paths from the markdown tree. That derivation is a MODEL of
Hugo, and a model can drift from the thing it models: Hugo's urlize keeps an
underscore (``/tags/auto_pb/``), a frontmatter ``url:`` moves a page under a
different parent, and a sibling ``.md`` inside a leaf bundle is a resource
rather than a page. Each of those got the derivation wrong on the first attempt.

So this test compares the derived sets against ``public/`` — the real answer —
rather than against hand-written expectations, which would only re-assert the
model's own assumptions. It is the reason the resolver is allowed to REJECT an
unknown term at all: without this parity check, a derivation that under-collects
would turn a pre-commit hook into a blocker on valid links.

Runs inside the Blogs IA suite (``scripts/run-blogs-ia-suite.sh``, wired to
pre-push and to ci.yml), which is where this repo keeps its built-tree tests and
which refuses to run against a STALE ``public/``. That gating is not optional
here: on a tree built before the newest source edit, a post that exists in
``content/`` but not yet in the build makes the derivation a strict superset,
and this test's own message would read as a resolver defect rather than as
"rebuild first". Measured live, on an unbuilt post: ``derives tags terms Hugo
does not serve: ['addiction', 'fishing', 'gaming', 'obsession']``.

``_require_build`` below is the floor beneath that gate, not a substitute for
it: it catches a MISSING build, the suite runner catches a stale one. It fails
rather than skips, because a parity test that silently passes on a missing build
is the same vacuous shape this Issue exists to remove.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_internal_links import (  # noqa: E402
    _CONTENT_TWO_PREFIX,
    _served_section_paths,
    _taxonomy_terms,
)

PUBLIC = REPO_ROOT / "public"


def _require_build() -> None:
    if not any(PUBLIC.rglob("index.html")):
        pytest.fail(
            f"{PUBLIC} holds no rendered index.html, so this parity test would "
            f"compare the derivation against an empty set and pass without "
            f"checking anything. Build first: hugo --gc --minify -e production"
        )


def _built_dirs(rel: str) -> set[str]:
    root = PUBLIC / rel
    return {d.name for d in root.iterdir() if d.is_dir()} if root.is_dir() else set()


@pytest.mark.parametrize("taxonomy", ["tags", "series"])
def test_derived_taxonomy_terms_match_the_built_tree(taxonomy: str) -> None:
    _require_build()
    built = _built_dirs(taxonomy)
    assert built, f"public/{taxonomy}/ has no term pages; the build is not what CI produces"
    derived = _taxonomy_terms(REPO_ROOT, taxonomy)

    missing = built - derived
    assert not missing, (
        f"Hugo serves /{taxonomy}/<term>/ pages the resolver does not derive: "
        f"{sorted(missing)}. Every one of these is a live URL that the validator "
        f"would now reject, blocking a correct link at pre-commit."
    )
    extra = derived - built
    assert not extra, (
        f"the resolver derives {taxonomy} terms Hugo does not serve: "
        f"{sorted(extra)}. These would be accepted as links to pages that 404."
    )


def test_derived_section_paths_are_all_really_served() -> None:
    """Every derived content path must exist in the build.

    Asserted one-directionally on purpose. The reverse (every built path is
    derived) is deliberately FALSE: Hugo also emits a redirect stub for each
    ``aliases:`` entry, and this repo rejects linking a redirect hop, so those
    built paths must NOT be in the derived set.
    """
    _require_build()
    derived = _served_section_paths(REPO_ROOT)
    section_pages = {
        path
        for path in derived
        if path.endswith("/") and path.strip("/").split("/")[0] in _CONTENT_TWO_PREFIX
    }
    assert section_pages, "no section paths derived at all — the resolver walked nothing"
    unserved = [
        path for path in sorted(section_pages) if not (PUBLIC / path.strip("/") / "index.html").is_file()
    ]
    assert not unserved, (
        f"the resolver accepts paths the build does not serve: {unserved}. "
        f"A link to one of these would pass the gate and 404 for a reader."
    )


def test_alias_targets_are_not_accepted_as_live_paths() -> None:
    """The discriminator for the one-directional assertion above.

    ``content/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/``
    carries an ``aliases:`` entry, so the build contains BOTH the canonical path
    and a redirect stub at the alias. Only the canonical one may be linkable —
    the same no-redirect-hop rule that rejects the retired /posts/ URLs. Without
    this test, a resolver that simply enumerated ``public/`` would look correct.
    """
    _require_build()
    canonical = "/community/agit-featured/1-hoi-aka-hoiboy-ai-product-engineer/"
    alias = "/community/agit-featured/hoi-aka-hoiboy-ai-product-engineer/"
    assert (PUBLIC / alias.strip("/") / "index.html").is_file(), (
        f"{alias} is no longer built, so this test no longer discriminates; "
        f"re-point it at a current aliases: entry or drop it"
    )
    derived = _served_section_paths(REPO_ROOT)
    assert canonical in derived, f"{canonical} is the live path and must be linkable"
    assert alias not in derived, (
        f"{alias} is an aliases: redirect stub, not a live path; accepting it "
        f"lets an in-repo link take a needless redirect hop"
    )


def test_every_single_segment_allow_list_entry_is_really_served() -> None:
    """The hand-maintained list must not accept a path the build does not serve.

    It had drifted: ``about`` was listed with no ``content/about`` and a live
    404 behind it, so the validator would have accepted a link to a dead page
    without complaint. Nothing linked it, which is exactly why a hand-maintained
    list rots unnoticed -- the wrong answer is only observable when someone
    finally writes the link.
    """
    _require_build()
    from validate_internal_links import _ALLOW_SINGLE  # noqa: PLC0415

    unserved = sorted(
        entry
        for entry in _ALLOW_SINGLE
        if entry
        and not entry.endswith(".xml")
        and not (PUBLIC / entry / "index.html").is_file()
    )
    assert not unserved, (
        f"_ALLOW_SINGLE accepts single-segment paths the build does not serve: "
        f"{unserved}. Either the page was removed and the entry is stale, or the "
        f"build is missing it."
    )


def test_no_served_top_level_path_is_wrongly_rejected() -> None:
    """The other direction: a live page the validator refuses to accept.

    This is the failure mode that costs an author time rather than a reader a
    404 -- a correct link blocked at pre-commit with no way to satisfy the hook.
    It had drifted too: /tags/ and /series/ both serve a list page and both were
    rejected, because a single-segment path is answered by _ALLOW_SINGLE before
    it ever reaches the taxonomy branch that handles the bare list case.

    Aliases are the documented exception. Hugo emits a redirect stub for each
    ``aliases:`` entry, and this repo rejects linking a redirect hop on purpose,
    so a served path whose HTML is a redirect stub is skipped here rather than
    treated as a miss.
    """
    _require_build()
    from validate_internal_links import _classify  # noqa: PLC0415

    wrongly_rejected = []
    for index in PUBLIC.rglob("index.html"):
        rel = index.parent.relative_to(PUBLIC)
        if str(rel) == "." or len(rel.parts) > 2:
            continue
        target = "/" + str(rel) + "/"
        ok, _ = _classify(target, REPO_ROOT)
        if ok:
            continue
        html = index.read_text(encoding="utf-8", errors="replace")
        if 'http-equiv="refresh"' in html.lower():
            continue  # an aliases: redirect stub, rejected by design.
        if target.strip("/").split("/")[0] == "private":
            continue  # unlisted operator-only tree, rejected by design.
        wrongly_rejected.append(target)

    assert not wrongly_rejected, (
        f"the validator rejects live pages: {sorted(wrongly_rejected)}. Each one "
        f"is a correct link an author cannot get past the pre-commit hook."
    )
