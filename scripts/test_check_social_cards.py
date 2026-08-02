#!/usr/bin/env python3
"""Unit tests for check_social_cards.py (hoiboy-uk #52, blog-priv#61).

Covers all four failure classes (A bundle-form, B singular-card, C section/home
landing card, D auto-section card), every exclusion path, the content-format spread
(.md/.markdown/.html), nested child bundles, SVG share-cards, the section/home
hero-does-not-count rule, the C/D handoff, the rendered-HTML backstop, and CLI exit
codes.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
GUARD = SCRIPTS / "check_social_cards.py"

_spec = importlib.util.spec_from_file_location("check_social_cards", GUARD)
csc = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = csc
_spec.loader.exec_module(csc)

PNG = b"\x89PNG\r\n\x1a\n"


def _seed_sections(root: Path, page_dir: Path):
    """Back every ancestor section of `page_dir` with a carded `_index.md`.

    A real site's sections are branch bundles; a fixture that drops
    content/posts/a/index.md with no content/posts/_index.md is a Hugo AUTO-section,
    which Check D flags on its own (blog-priv#61 2nd increment). Seeding keeps each
    test asserting the ONE class it targets instead of also tripping Check D. Skips
    any ancestor that is itself a leaf bundle (nested child-bundle fixtures), since
    an index.* and an _index.* must never share a directory. Opt out with
    seed_sections=False to build a deliberately uncarded auto-section."""
    d = page_dir.parent
    while d != root and d.parent != d:
        if not any((d / ("index" + e)).exists() for e in (".md", ".markdown", ".html")):
            if not any((d / ("_index" + e)).exists() for e in (".md", ".markdown", ".html")):
                (d / "_index.md").write_text("---\ntitle: S\n---\n", encoding="utf-8")
                (d / "share-card.png").write_bytes(PNG)
        d = d.parent
    # Home too: a real site always has content/_index.md, and Check D flags its
    # absence (Hugo still renders "/", but Check C cannot enumerate it).
    if not any((root / ("_index" + e)).exists() for e in (".md", ".markdown", ".html")):
        root.mkdir(parents=True, exist_ok=True)
        (root / "_index.md").write_text("---\ntitle: Home\n---\n", encoding="utf-8")
        (root / "share-card.png").write_bytes(PNG)


def _bundle(root: Path, rel: str, frontmatter: str = "title: X",
            card: str | None = "share-card.png", ext: str = ".md",
            seed_sections: bool = True):
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / ("index" + ext)).write_text(f"---\n{frontmatter}\n---\nbody\n", encoding="utf-8")
    if card:
        cp = d / card
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_bytes(PNG) if cp.suffix.lower() != ".svg" else cp.write_text("<svg/>")
    if seed_sections:
        _seed_sections(root, d)
    return d


def _flat(root: Path, rel: str, ext: str = ".md", frontmatter: str = "title: X",
          seed_sections: bool = True):
    p = (root / rel).with_suffix(ext)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{frontmatter}\n---\nbody\n", encoding="utf-8")
    if seed_sections:
        _seed_sections(root, p)
    return p


def _landing(root: Path, rel: str, frontmatter: str = "title: X",
             card: str | None = "share-card.png", ext: str = ".md",
             seed_home: bool = True):
    """A section/home landing: an _index.<ext> (rel="" is the home bundle = root itself)
    with an optional root card. Check C class (blog-priv#61).

    `seed_home` gives the tree a carded home landing when this is not itself home, so
    the fixture is a realistic site and Check D's home clause stays quiet."""
    d = root / rel if rel else root
    d.mkdir(parents=True, exist_ok=True)
    (d / ("_index" + ext)).write_text(f"---\n{frontmatter}\n---\nbody\n", encoding="utf-8")
    if card:
        cp = d / card
        cp.write_bytes(PNG) if cp.suffix.lower() != ".svg" else cp.write_text("<svg/>")
    if rel and seed_home and not any(
            (root / ("_index" + e)).exists() for e in (".md", ".markdown", ".html")):
        (root / "_index.md").write_text("---\ntitle: Home\n---\n", encoding="utf-8")
        (root / "share-card.png").write_bytes(PNG)
    return d


def _home(root: Path):
    """A carded home landing - the realistic-site baseline for auto-section fixtures
    built with seed_sections=False."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "_index.md").write_text("---\ntitle: Home\n---\n", encoding="utf-8")
    (root / "share-card.png").write_bytes(PNG)
    return root


def _headers(root: Path, body: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    p = root / "_headers"
    p.write_text(body, encoding="utf-8")
    return p


def _cats(violations, tag):
    return [v for v in violations if v.startswith(f"[{tag}]")]


# ---- clean baseline -----------------------------------------------------------

def test_clean_tree_passes(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/a")
    _landing(content, "posts")          # a section landing owns its own card too (Check C)
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


# ---- Check C: section + home landing card presence (blog-priv#61) -------------

def test_landing_with_card_passes(tmp_path):
    content = tmp_path / "content"
    _landing(content, "food-booze")
    assert csc.check(content, _headers(tmp_path, "")) == []


def test_landing_missing_card_flagged(tmp_path):
    content = tmp_path / "content"
    _landing(content, "food-booze", card=None)
    v = csc.check(content, _headers(tmp_path, ""))
    assert len(_cats(v, "landing-card-missing")) == 1 and "food-booze/_index.md" in v[0]


def test_landing_svg_card_flagged(tmp_path):
    content = tmp_path / "content"
    _landing(content, "legal", card="share-card.svg")
    assert len(_cats(csc.check(content, _headers(tmp_path, "")), "landing-card-svg")) == 1


def test_landing_hero_does_not_satisfy(tmp_path):
    # head.html hero-pick is .IsPage-only: a section hero is NOT the og:image, so a
    # landing with only a hero (no share-card) still falls back to the default card.
    content = tmp_path / "content"
    _landing(content, "adventure", card="hero.jpg")
    assert len(_cats(csc.check(content, _headers(tmp_path, "")), "landing-card-missing")) == 1


def test_home_landing_missing_card_flagged(tmp_path):
    # the home bundle is content/ itself (content/_index.md), served at "/".
    content = tmp_path / "content"
    _landing(content, "", card=None)
    v = csc.check(content, _headers(tmp_path, ""))
    assert len(_cats(v, "landing-card-missing")) == 1 and "_index.md (/)" in v[0]


def test_home_landing_with_card_passes(tmp_path):
    content = tmp_path / "content"
    _landing(content, "", card="share-card.png")
    assert csc.check(content, _headers(tmp_path, "")) == []


def test_landing_noindex_excluded(tmp_path):
    content = tmp_path / "content"
    _landing(content, "private", frontmatter="title: P\nnoindex: true", card=None)
    assert csc.check(content, _headers(tmp_path, "")) == []


def test_landing_render_never_excluded(tmp_path):
    content = tmp_path / "content"
    _landing(content, "private", frontmatter="title: P\nbuild:\n  render: never", card=None)
    assert csc.check(content, _headers(tmp_path, "")) == []


def test_landing_headers_noindex_excluded(tmp_path):
    content = tmp_path / "content"
    _landing(content, "hidden-section", card=None)
    headers = _headers(tmp_path, "/hidden-section/*\n  X-Robots-Tag: noindex\n")
    assert csc.check(content, headers) == []


# ---- Check D: auto-sections (no _index.*) (blog-priv#61 2nd increment) --------

def test_auto_section_uncarded_flagged(tmp_path):
    # content/posts/a/index.md with NO content/posts/_index.md: Hugo still renders
    # /posts/ as a list page, Check C cannot see it, and it serves the default card.
    # This is the /posts/ defect blog-priv#62 fixed by adding content/posts/_index.md.
    content = tmp_path / "content"
    _home(content)
    _bundle(content, "posts/a", seed_sections=False)
    v = csc.check(content, _headers(tmp_path, ""))
    assert len(_cats(v, "auto-section-uncarded")) == 1
    assert "posts (/posts/)" in v[0]


def test_auto_section_with_card_passes(tmp_path):
    # An auto-section CAN own a card: Hugo publishes the directory's files as page
    # resources, so a root share-card.<raster> really does become the og:image
    # (verified against a real hugo build, not inferred). So Check D tests card
    # PRESENCE, exactly like Check C - a carded auto-section is not a violation.
    content = tmp_path / "content"
    _home(content)
    _bundle(content, "posts/a", seed_sections=False)
    (content / "posts" / "share-card.png").write_bytes(PNG)
    assert _cats(csc.check(content, _headers(tmp_path, "")), "auto-section-uncarded") == []


def test_auto_section_svg_card_flagged(tmp_path):
    content = tmp_path / "content"
    _home(content)
    _bundle(content, "posts/a", seed_sections=False)
    (content / "posts" / "share-card.svg").write_text("<svg/>")
    v = csc.check(content, _headers(tmp_path, ""))
    assert len(_cats(v, "auto-section-card-svg")) == 1
    assert _cats(v, "auto-section-uncarded") == []


def test_auto_section_gains_index_handed_to_check_c(tmp_path):
    # Adding the _index.* moves ownership to Check C. Exactly one of the two fires -
    # no double-report for the same directory.
    content = tmp_path / "content"
    _home(content)
    _bundle(content, "posts/a", seed_sections=False)
    _landing(content, "posts", card=None)
    v = csc.check(content, _headers(tmp_path, ""))
    assert len(_cats(v, "landing-card-missing")) == 1
    assert _cats(v, "auto-section-uncarded") == []


def test_auto_section_headers_noindex_excluded(tmp_path):
    # An auto-section has no frontmatter, so static/_headers is the only exclusion
    # signal. This is what keeps the real tree's content/private/tools clean.
    content = tmp_path / "content"
    _home(content)
    _bundle(content, "private/tools/thing", seed_sections=False)
    headers = _headers(tmp_path, "/private/*\n  X-Robots-Tag: noindex, nofollow\n")
    assert _cats(csc.check(content, headers), "auto-section-uncarded") == []


def test_leaf_bundle_and_its_resource_dirs_are_not_auto_sections(tmp_path):
    # A leaf bundle is a PAGE, not a section, and its nested resource dirs are
    # resources - neither may ever be reported as an uncarded auto-section.
    content = tmp_path / "content"
    d = _bundle(content, "posts/gallery")
    (d / "website").mkdir()
    (d / "website" / "shot-01.jpg").write_bytes(PNG)
    assert _cats(csc.check(content, _headers(tmp_path, "")), "auto-section-uncarded") == []


def test_carded_home_is_not_flagged(tmp_path):
    # With content/_index.md present, Check C owns home and Check D stays silent.
    content = tmp_path / "content"
    _bundle(content, "posts/a")
    v = csc.check(content, _headers(tmp_path, ""))
    assert _cats(v, "auto-section-uncarded") == []


def test_nested_dir_without_index_is_not_an_auto_section(tmp_path):
    # Hugo makes a directory a section only if it is TOP-LEVEL or carries an _index.*.
    # Measured on the pinned Hugo 0.160.0: content/toplevel/deeper/pageC/index.md and
    # content/parent/nested/pageB/index.md render /toplevel/ and /parent/ as
    # kind=section, but emit NO page for /toplevel/deeper/ or /parent/nested/. Walking
    # every ancestor would flag directories Hugo never serves.
    content = tmp_path / "content"
    _home(content)
    _landing(content, "parent")
    _bundle(content, "parent/nested/pageB", seed_sections=False)
    _bundle(content, "toplevel/deeper/pageC", seed_sections=False)
    v = _cats(csc.check(content, _headers(tmp_path, "")), "auto-section-uncarded")
    assert len(v) == 1 and "toplevel (/toplevel/)" in v[0], v


def test_home_without_index_flagged(tmp_path):
    # A tree with no content/_index.md is NOT broken: Hugo renders kind=home at "/"
    # serving the default card, and landing_bundles yields nothing for it, so Check C
    # silently stops covering the site's highest-traffic page.
    content = tmp_path / "content"
    _bundle(content, "posts/a", seed_sections=False)
    _landing(content, "posts", seed_home=False)
    v = _cats(csc.check(content, _headers(tmp_path, "")), "auto-section-uncarded")
    assert len(v) == 1 and ". (/)" in v[0], v


def test_home_without_index_but_carded_passes(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "posts/a", seed_sections=False)
    _landing(content, "posts", seed_home=False)
    (content / "share-card.png").write_bytes(PNG)
    assert _cats(csc.check(content, _headers(tmp_path, "")), "auto-section-uncarded") == []


def test_auto_section_url_comes_from_hugo_not_the_content_path(tmp_path):
    # blog-priv#62 maps content/posts -> /blogs/ via [permalinks.section], so a URL
    # derived from the directory name is WRONG and the noindex fnmatch then tests the
    # wrong path - false-positive on a rule written for /blogs/*, silent false-negative
    # on a stale /posts/* rule. Hugo's own trail index must win.
    content = tmp_path / "content"
    _home(content)
    _bundle(content, "posts/a", seed_sections=False)
    url_index = {"posts": "/blogs/"}

    # a noindex rule on the URL Hugo really serves must exclude it...
    headers = _headers(tmp_path, "/blogs/*\n  X-Robots-Tag: noindex\n")
    assert _cats(csc.check(content, headers, url_index), "auto-section-uncarded") == []

    # ...and a stale rule on the retired path must NOT silence it.
    stale = _headers(tmp_path / "s", "/posts/*\n  X-Robots-Tag: noindex\n")
    v = _cats(csc.check(content, stale, url_index), "auto-section-uncarded")
    assert len(v) == 1 and "(/blogs/)" in v[0], v


def test_built_auto_section_rendering_default_flagged(tmp_path):
    # The rendered backstop must cover auto-sections too - they are the page kind
    # Check D exists to protect, and were omitted from check_built's chain at first.
    content = tmp_path / "content"
    _home(content)
    _bundle(content, "notes/a", seed_sections=False)
    (content / "notes" / "share-card.png").write_bytes(PNG)   # source looks fine...
    public = tmp_path / "public"
    _render(public, "/notes/", "https://x/default-card_hu_1.jpg")   # ...render defaulted
    v = _cats(csc.check_built(content, _headers(tmp_path, ""), public), "rendered-default")
    assert len(v) == 1 and "/notes/" in v[0], v


def test_built_landing_default_flagged(tmp_path):
    content = tmp_path / "content"
    _landing(content, "skills", card="share-card.png")   # source is fine...
    public = tmp_path / "public"
    _render(public, "/skills/", "https://x/default-card_hu_1.jpg")   # ...but render defaulted
    assert len(_cats(csc.check_built(content, _headers(tmp_path, ""), public), "rendered-default")) == 1


def test_built_home_landing_own_card_passes(tmp_path):
    content = tmp_path / "content"
    _landing(content, "", card="share-card.png")
    public = tmp_path / "public"
    _render(public, "/", "https://x/share-card_hu_1.jpg")
    assert csc.check_built(content, _headers(tmp_path, ""), public) == []


# ---- remedy wording -----------------------------------------------------------

def test_every_violation_names_the_command_that_works_from_a_cold_tree(tmp_path):
    """Every remedy points at gen-social-cards.sh, never a bare `gen_card.py <set>`.

    The commonest way to reach this guard is to add a page and run the checks before
    any build. In that state gen_card.py exits non-zero from card_common.eyebrow_for,
    because a card's eyebrow comes from public/<url>/trail.json and Hugo has not
    written one yet - so a message naming the bare generator bounces the reader into a
    second, unrelated-looking error. gen-social-cards.sh builds first. Asserted over
    ALL four checks at once so a new violation string cannot regress the wording.

    `[bundle-form]` is deliberately exempt from the "names the command" half: its
    remedy is to restructure the file into a leaf bundle, which no generator can do.
    The "no bare generator" half still covers it.
    """
    REGEN_TAGS = ("card-svg", "card-missing", "auto-section-uncarded",
                  "landing-card-svg", "landing-card-missing", "auto-section-card-svg")
    content = tmp_path / "content"
    _bundle(content, "posts/a", card=None)              # A/B: singular, uncarded
    _flat(content, "hire-hoi/flat")                     # A: flat singular
    _landing(content, "skills", card=None)              # C: landing, uncarded
    _bundle(content, "auto/x", seed_sections=False)     # D: auto-section, uncarded
    (content / "legal").mkdir(parents=True, exist_ok=True)
    (content / "legal" / "_index.md").write_text("---\ntitle: L\n---\n")
    (content / "legal" / "share-card.svg").write_text("<svg/>")   # C: svg card

    v = csc.check(content, _headers(tmp_path, ""))
    assert v, "fixture must produce violations or this test is vacuous"
    regen = [m for m in v if any(m.startswith(f"[{t}]") for t in REGEN_TAGS)]
    # every regen-remedied check must be exercised, else the sweep passes by omission
    assert len(regen) >= 4, f"fixture covered too few regen violations: {regen}"
    for msg in regen:
        assert "gen-social-cards.sh" in msg, f"remedy missing from: {msg}"
    for msg in v:
        assert "run gen_card.py" not in msg, f"bare-generator remedy survived in: {msg}"
        assert "Run gen_card.py" not in msg, f"bare-generator remedy survived in: {msg}"


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


# ---- parse_noindex_globs: which X-Robots-Tag values really mean "noindex" -----
#
# This parser is shared. scripts/test_404.py reuses it as the single authority on
# whether static/_headers keeps the 404 page out of the search index, so a false
# positive here reports an indexable page as protected in a gate whose entire
# purpose is to stop exactly that (blog-priv#64, Ralph round 5).
#
# The defect these pin: the old regex looked for the bare word `none` anywhere in
# the header value, and `max-image-preview:none` is a real, standard robots
# directive that limits preview image SIZE and says nothing about indexing.

def _globs(tmp_path: Path, header: str) -> list[str]:
    return csc.parse_noindex_globs(_headers(tmp_path, f"/x*\n  {header}\n"))


def test_noindex_and_none_are_recognised(tmp_path):
    for value in ("noindex", "noindex, nofollow", "none", "NOINDEX",
                  "nofollow, noindex"):
        assert _globs(tmp_path, f"X-Robots-Tag: {value}") == ["/x*"], value


def test_a_valued_directive_is_a_parameter_not_a_verdict(tmp_path):
    """`max-image-preview:none` limits preview size. It does not deindex.

    A maintainer adding it to a block for that unrelated reason, without keeping
    a real noindex line, used to make every check report the page as protected.
    """
    for value in ("max-image-preview:none", "max-image-preview: none",
                  "max-snippet:-1, max-image-preview:large",
                  "unavailable_after: 2030-01-01"):
        assert _globs(tmp_path, f"X-Robots-Tag: {value}") == [], value


def test_a_valued_directive_beside_a_real_noindex_still_counts(tmp_path):
    assert _globs(tmp_path, "X-Robots-Tag: max-image-preview:none, noindex") == ["/x*"]


def test_a_user_agent_prefix_is_not_mistaken_for_a_valued_directive(tmp_path):
    """`googlebot: noindex` also contains a colon; the KEY is what tells them apart.

    Both forms are colon-bearing and NEITHER grants a blanket noindex, but they
    are rejected for different reasons and the parser must keep telling them
    apart: `max-image-preview:none` is a parameter that says nothing about
    indexing, while `googlebot: noindex` is a real indexing verdict that simply
    binds one crawler.

    Round 5 read the agent-scoped form as a blanket verdict. That is the wrong
    direction for this parser: it is the repo's only EXEMPTION-granting
    derivation, so a page could skip its share-card requirement, and the 404
    could be reported as protected, on one crawler's say-so while every other
    crawler stayed free to index it. Corrected to fail closed.
    """
    assert _globs(tmp_path, "X-Robots-Tag: googlebot: noindex") == []
    assert _globs(tmp_path, "X-Robots-Tag: googlebot: noindex, nosnippet") == []


def test_directives_that_permit_indexing_are_not_matched(tmp_path):
    for value in ("nofollow", "all", "nosnippet", "noarchive"):
        assert _globs(tmp_path, f"X-Robots-Tag: {value}") == [], value


def test_another_header_carrying_the_word_none_is_not_matched(tmp_path):
    """Only X-Robots-Tag decides indexing, whatever other headers happen to say."""
    assert _globs(tmp_path, "X-Frame-Options: none") == []
    assert _globs(tmp_path, "Permissions-Policy: geolocation=none") == []


def test_directive_order_within_a_block_does_not_matter(tmp_path):
    body = ("/x*\n  X-Frame-Options: DENY\n  Referrer-Policy: no-referrer\n"
            "  X-Robots-Tag: noindex, nofollow\n")
    assert csc.parse_noindex_globs(_headers(tmp_path, body)) == ["/x*"]


def test_a_byte_order_mark_does_not_hide_the_first_block(tmp_path):
    """A BOM used to make the first block's path line unrecognisable.

    `'﻿/404*'.startswith('/')` is False, so `current` never got set and the
    rule under it was dropped. Reachable without anyone doing anything odd:
    alphabetise the blocks in static/_headers (`/404*` sorts first) and save
    from a BOM-emitting editor on Windows. The 404 loses its noindex and every
    gate stays green (blog-priv#64, Ralph round 6).
    """
    body = ("/404*\n  X-Robots-Tag: noindex, nofollow\n\n"
            "/private/*\n  X-Robots-Tag: noindex, nofollow\n")
    assert csc.parse_noindex_globs(_headers(tmp_path, body)) == ["/404*", "/private/*"]

    bom = tmp_path / "bom" / "_headers"
    bom.parent.mkdir(parents=True, exist_ok=True)
    bom.write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8"))
    assert csc.parse_noindex_globs(bom) == ["/404*", "/private/*"], (
        "a leading BOM swallowed the first block's rule"
    )


def test_a_user_agent_scoped_directive_is_not_a_blanket_verdict(tmp_path):
    """`X-Robots-Tag: googlebot: noindex` binds googlebot and nobody else.

    Every other crawler stays free to index the page, so it cannot stand in for
    a blanket noindex. This is the repo's only EXEMPTION-granting derivation -
    is_excluded() lets a page skip its share-card requirement entirely, and
    scripts/test_404.py reuses this same parser as its authority on whether the
    404 is kept out of the index. Fail closed: agent-scoped does not count.

    This is Ralph round 5's function, direction and class surviving round 5's
    own fix, which is why it is pinned rather than left to a tenth round.
    """
    for value in ("googlebot: noindex", "googlebot: none", "bingbot: noindex",
                  "GOOGLEBOT: NOINDEX", "googlebot-news: none"):
        assert _globs(tmp_path, f"X-Robots-Tag: {value}") == [], value


def test_a_blanket_directive_alongside_a_scoped_one_still_counts(tmp_path):
    """Do not over-narrow: a real blanket directive in the list still wins."""
    for value in ("googlebot: noindex, noindex", "noindex, googlebot: none",
                  "max-image-preview:none, noindex"):
        assert _globs(tmp_path, f"X-Robots-Tag: {value}") == ["/x*"], value


def test_the_real_headers_file_still_protects_the_404(tmp_path):
    """Regression pin on what actually ships, not on a synthetic fixture."""
    globs = csc.parse_noindex_globs(SCRIPTS.parent / "static" / "_headers")
    assert "/404*" in globs, globs


# ---- walk floor: a guard that examined nothing must not report OK -------------
#
# This guard feeds three of pre-publish.sh's 17 gates and, until #55's post-pass
# re-validation, had NO floor at any layer: with content/posts/ absent it printed
# "OK" and exited 0 having examined zero posts. `--strict` did not cover it --
# strict turns UNRESOLVED PAGE URLS into failures, not EMPTY WALKS, so a walk that
# found nothing has nothing left unresolved and sails through strict too. That
# false premise was the stated reason the Issue deferred this, which is why the
# floor is asserted here by its MESSAGE rather than by exit code alone: exit 1 is
# also what a real violation produces, so an exit-code-only test would not
# distinguish "caught a vacuous walk" from "caught a missing card".

def _floor_run(content, headers, *extra):
    return subprocess.run(
        [sys.executable, str(GUARD), "--content", str(content),
         "--headers", str(headers), *extra],
        capture_output=True, text=True,
    )


def test_walk_floor_fails_when_no_posts_are_walked(tmp_path):
    content = tmp_path / "content"
    _bundle(content, "legal/privacy")          # a compliant page, but no posts/
    r = _floor_run(content, _headers(tmp_path, ""))
    assert r.returncode == 1, f"a walk finding zero posts must fail. stdout={r.stdout} stderr={r.stderr}"
    assert "walked 0 posts" in r.stderr, r.stderr
    assert "vacuous pass" in r.stderr, r.stderr


def test_walk_floor_fails_when_posts_dir_exists_but_is_empty(tmp_path):
    """An existing-but-empty tree is the likelier real failure than a missing one."""
    content = tmp_path / "content"
    _bundle(content, "legal/privacy")
    (content / "posts").mkdir(parents=True, exist_ok=True)
    r = _floor_run(content, _headers(tmp_path, ""))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "walked 0 posts" in r.stderr, r.stderr


@pytest.mark.skipif(not (SCRIPTS.parent / "public").is_dir(), reason="./public not built")
def test_walk_floor_also_fires_under_strict(tmp_path):
    """`--strict` was the reason given for not needing this floor. It is not one.

    Uses the repo's real ./public so the built layer contributes no violations of
    its own -- violations are returned BEFORE the floor, so a synthetic empty
    built tree would fail via that path instead and prove nothing about strict.
    """
    content = tmp_path / "content"
    _bundle(content, "legal/privacy")
    r = _floor_run(content, _headers(tmp_path, ""),
                   "--built", str(SCRIPTS.parent / "public"), "--strict")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "walked 0 posts" in r.stderr, (
        "strict did not reach the walk floor. strict turns UNRESOLVED PAGE URLS "
        f"into failures, not EMPTY WALKS. stderr={r.stderr}"
    )


def test_a_real_violation_is_not_masked_by_the_floor(tmp_path):
    """Ordering: violations must be reported before the floor short-circuits."""
    content = tmp_path / "content"
    _bundle(content, "posts/ok")
    _bundle(content, "posts/bad", card=None)
    r = _floor_run(content, _headers(tmp_path, ""))
    assert r.returncode == 1
    assert "violation" in (r.stdout + r.stderr).lower(), r.stdout + r.stderr
    assert "vacuous pass" not in r.stderr, (
        "the floor swallowed a real violation; violations must return first"
    )


def test_the_guard_reports_what_it_walked(tmp_path):
    """A passing run must be distinguishable from a vacuous one."""
    content = tmp_path / "content"
    _bundle(content, "posts/ok")
    r = _floor_run(content, _headers(tmp_path, ""))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "1 posts" in r.stdout, (
        f"a clean run must state its walk counts, or it is indistinguishable from "
        f"one that examined nothing. stdout={r.stdout}"
    )
