#!/usr/bin/env python3
"""Validate internal markdown links against the Hugo permalink contract.

Posts live at ``/blogs/<slug>/`` and category landings at ``/blogs/<category>/``
(blog-priv#62 moved both under ``/blogs/``; the retired root-level URLs are 301'd
in ``static/_redirects``). A landing LISTS the posts in its category, it does not
HOST them, so ``/blogs/dance/some-post/`` is broken even though it looks
plausible.

``<slug>`` is the SERVED slug, which is not always the bundle directory name: a
post's frontmatter ``slug:`` overrides it (``content/posts/2026-04-07-foundation/``
is served at ``/blogs/foundation/``). Resolution goes through that mapping, so a
link to a slug-overridden post is accepted and a link to its directory name is
not — matching what the site actually serves.

Lychee cannot catch this bug class: ``lychee.toml`` excludes
``content/posts`` (raw-markdown false-positive avoidance) and excludes
``hoiboy.uk`` URLs (Cloudflare race protection), so broken in-content
links to nonexistent paths are structurally invisible to the existing
link checker. This validator closes that gap.

Decision matrix (default = PASS):
  link is anchor-only / mailto / external / shortcode internals  -> SKIP
  link path is /blogs/<slug>/ AND that slug is served            -> PASS
  link path is /blogs/<category>/ (a category landing)           -> PASS
  link path is /blogs/ or /blogs/[<category>/]index.xml          -> PASS
  link path matches an allow-list entry                          -> PASS
  link path is a RETIRED /posts/... or /<category>/... URL       -> FAIL
  link path is /blogs/<category>/<slug>/                         -> FAIL
  link path is /blogs/<slug>/ AND no post serves that slug       -> FAIL
  any other / unrecognised internal path                         -> FAIL

Exit codes: 0 = pass, 1 = violations, 2 = read error
"""

from __future__ import annotations

import argparse
import re
import sys
from functools import lru_cache
from pathlib import Path

# The 7 blog categories. They are content sections whose landings are served
# under /blogs/ (config/_default/hugo.toml [permalinks.section], blog-priv#62).
# They are deliberately NOT in _ALLOW_SINGLE: a root-level /tech-ai/ link is a
# retired URL that now only survives via a 301, and an in-repo link should point
# at the live path rather than take a redirect hop.
_SECTIONS = (
    "adventure",
    "dance",
    "entrepreneurship",
    "food-booze",
    "life",
    "tech-ai",
    "trading",
)

# The blog root. Posts, category landings and the hub all live under it.
_BLOG_ROOT = "blogs"

# Single-segment allow-list (paths that are real first-level sections / pages).
_ALLOW_SINGLE = frozenset(
    [
        "",  # bare "/"
        _BLOG_ROOT,  # /blogs/ hub (content/posts/_index.md)
        "hire-hoi",
        "skills",
        "about",
        "legal",  # /legal/ section index (consulting-ops#6 Phase 6)
        "community",  # /community/ section index (#43 Phase 1)
        "index.xml",
        "sitemap.xml",
    ]
)

# Multi-segment prefixes: paths that take one or more segments after the first.
# Both sets used to be one unconditional allow-list (`_ALLOW_TWO_PREFIX`), which
# returned True for anything beneath them without resolving it — so every
# /hire-hoi/, /legal/, /community/, /tags/ and /series/ link in the repo passed
# this tier while being checked by nothing, and the rendered tier does not cover
# them either (lychee rewrites root-relative links to hoiboy.uk, which is
# allowlisted for the CI-vs-deploy race). Both are resolved for real now.
#
# Content sections: page bundles under content/<section>/, so the markdown tree
# decides what is served and the paths are derived from it exactly.
_CONTENT_TWO_PREFIX = frozenset(["hire-hoi", "legal", "community"])
# Taxonomies: term pages Hugo generates from frontmatter rather than from a file
# on disk, so their terms are derived by collecting every `tags:` / `series:`
# value and applying Hugo's urlize. Verified to reproduce the built tree exactly
# (218/218 tag terms, 1/1 series term) by tests/test_taxonomy_terms_match_build.py.
_TAXONOMY_TWO_PREFIX = frozenset(["tags", "series"])
_ALLOW_TWO_PREFIX = _CONTENT_TWO_PREFIX | _TAXONOMY_TWO_PREFIX

# Pre-compiled patterns.
# Frontmatter block — everything between the first two `---` lines. Used to read
# a post's `slug:` override without pulling in a YAML dependency (this script is
# a `language: system` pre-commit hook, so it stays stdlib-only).
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.S)
_FM_SLUG_RE = re.compile(r"^slug:\s*(.+?)\s*$", re.M)
# A frontmatter `url:` overrides the WHOLE served path, not merely the last
# segment (content/community/agit-thanks/ sets url: /community/asians-gingers-in-tech/
# thanks/ and renders two levels deeper under a DIFFERENT parent).
_FM_URL_RE = re.compile(r"^url:\s*(.+?)\s*$", re.M)
# Frontmatter list fields, in both the inline (`tags: [a, b]`) and block
# (`tags:` then `- a`) forms Hugo accepts, plus the scalar form (`series: name`)
# that content/posts/ uses. All three appear in this repo, so a parser that
# knows only one of them under-collects and would reject a live term page.
_FM_INLINE_LIST_RE = r"^{key}:[ \t]*\[(.*?)\]"
_FM_SCALAR_RE = r"^{key}:[ \t]*(\S.*)$"
_FM_BLOCK_HEAD_RE = r"^{key}:[ \t]*$"
_FM_BLOCK_ITEM_RE = re.compile(r"^\s*-\s+(.*)$")
# Shortcode strip — Hugo shortcodes look like `{{< name args >}}` or `{{% ... %}}`.
_SHORTCODE_RE = re.compile(r"\{\{[<%].*?[>%]\}\}", re.DOTALL)
# HTML comment strip.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# Code fence strip — triple-backtick blocks (with or without language hint).
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
# Inline code strip — single-backtick spans on a line.
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
# Self-reference normalisation — strip absolute hoiboy.uk prefix to leave a
# relative path. Catches absolute-style cross-references that would otherwise
# be skipped by the external-URL filter.
_SELF_REF_RE = re.compile(r"^https?://(www\.)?hoiboy\.uk", re.IGNORECASE)
# Inline link extractor — `[text](/path)` or `[text](/path "title")`.
# `(?<!!)` negative lookbehind excludes images `![alt](path)` (image existence
# is a different bug class — sibling-file in page bundle — out of scope).
_INLINE_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(\s*(\S+?)(?:\s+\"[^\"]*\")?\s*\)")
# Reference-style link definition — `[ref]: /path` (standalone line; URL up to
# whitespace; optional title ignored).
_REF_DEF_RE = re.compile(r"^\s*\[([^\]]+)\]:\s*(\S+)", re.MULTILINE)
# Reference-style link usage — `[text][ref]` (collapsed `[text][]` also matches
# with ref==text).
_REF_USE_RE = re.compile(r"(?<!!)\[([^\]]+)\]\[([^\]]*)\]")
# Reference-style IMAGE usage — `![alt][ref]` (collapsed `![ref][]` also
# matches with ref==alt). Image existence is a different bug class
# (sibling-file in page bundle, out of scope), so refs used ONLY as images
# must be excluded from URL classification — the same out-of-scope decision
# the inline `(?<!!)` lookbehind makes for `![alt](path)`.
_REF_IMG_USE_RE = re.compile(r"!\[([^\]]*)\]\[([^\]]*)\]")


def _strip_non_link_regions(text: str) -> str:
    """Remove regions that should never contribute links: shortcodes,
    HTML comments, code fences, inline code. Order matters — fences first so
    inline-code stripping doesn't mangle fence interiors."""
    text = _CODE_FENCE_RE.sub("", text)
    text = _HTML_COMMENT_RE.sub("", text)
    text = _SHORTCODE_RE.sub("", text)
    text = _INLINE_CODE_RE.sub("", text)
    return text


def _line_of(text: str, offset: int) -> int:
    """1-based line number of the character at ``offset``."""
    return text.count("\n", 0, offset) + 1


def _normalise_target(raw: str) -> str | None:
    """Resolve a raw href into a normalised internal path, or None if the
    href is external / anchor-only / unsupported (skip)."""
    target = raw.strip()
    if not target:
        return None
    # Strip trailing fragment (anchor) — fragment irrelevant to path resolution.
    if "#" in target:
        target = target.split("#", 1)[0]
        if not target:
            return None  # pure anchor ](#section)
    # Strip trailing query string.
    if "?" in target:
        target = target.split("?", 1)[0]
        if not target:
            return None
    # Self-reference normalisation — absolute hoiboy.uk URL becomes relative.
    target = _SELF_REF_RE.sub("", target)
    # mailto / external — skip.
    if target.startswith(("mailto:", "tel:", "http://", "https://")):
        return None
    # Internal links MUST start with / (relative-path links to siblings are
    # not used in this codebase; if they appear, treat as out-of-scope skip
    # rather than false positive).
    if not target.startswith("/"):
        return None
    return target


@lru_cache(maxsize=None)
def _served_post_slugs(repo_root: Path) -> frozenset[str]:
    """Every slug the posts section actually SERVES, i.e. the ``<slug>`` in
    ``/blogs/<slug>/``.

    Hugo resolves it with ``:slugorcontentbasename`` (``config/_default/hugo.toml``
    ``[permalinks.page]``): a frontmatter ``slug:`` wins, else the bundle
    directory name. 2 of the 79 posts override it
    (``2026-04-07-foundation`` -> ``foundation``, ``ai-jargon-for-noobs`` ->
    ``ai-jargon-for-newbies``), so resolving on the directory name alone would
    reject a correct link to either AND accept a dead one — in both directions,
    the opposite of what the page serves.

    Read from the frontmatter block only (between the first two ``---`` lines),
    so a ``slug:`` mentioned in body prose cannot hijack it.
    """
    slugs: set[str] = set()
    for index in sorted((repo_root / "content" / "posts").glob("*/index.md")):
        slug = ""
        fm = _FRONTMATTER_RE.match(index.read_text(encoding="utf-8", errors="replace"))
        if fm:
            m = _FM_SLUG_RE.search(fm.group(1))
            if m:
                slug = m.group(1).strip().strip("\"'")
        slugs.add(slug or index.parent.name)
    return frozenset(slugs)


def _fm_block(md_path: Path) -> str:
    """The frontmatter block of ``md_path``, or ``""`` when it has none."""
    fm = _FRONTMATTER_RE.match(md_path.read_text(encoding="utf-8", errors="replace"))
    return fm.group(1) if fm else ""


def _fm_list(block: str, key: str) -> list[str]:
    """Every value of frontmatter list field ``key``, across the inline, scalar
    and block YAML forms. Quotes are stripped; ordering is not significant."""
    m = re.search(_FM_INLINE_LIST_RE.format(key=key), block, re.M | re.S)
    if m:
        return [v.strip().strip("\"'") for v in m.group(1).split(",") if v.strip(" \"'")]
    m = re.search(_FM_SCALAR_RE.format(key=key), block, re.M)
    if m:
        value = m.group(1).strip().strip("\"'")
        return [value] if value else []
    m = re.search(_FM_BLOCK_HEAD_RE.format(key=key), block, re.M)
    if not m:
        return []
    values: list[str] = []
    for line in block[m.end():].splitlines():
        if not line.strip():
            continue
        item = _FM_BLOCK_ITEM_RE.match(line)
        if not item:
            break  # dedented out of the list — the next frontmatter field.
        value = item.group(1).strip().strip("\"'")
        if value:
            values.append(value)
    return values


def _urlize(term: str) -> str:
    """Hugo's taxonomy-term URL segment for ``term``.

    Lowercase, whitespace to hyphens, then drop anything outside ``[a-z0-9_-]``.
    The underscore is KEPT, not folded to a hyphen: Hugo serves the `auto_pb`
    tag at /tags/auto_pb/, so folding it would reject a live link. Verified
    against the built tree rather than against Hugo's source, because the
    pinned version is what this repo actually serves.
    """
    slug = re.sub(r"\s+", "-", term.lower().strip())
    slug = re.sub(r"[^a-z0-9_/-]", "", slug)
    return re.sub(r"-+", "-", slug).strip("-")


@lru_cache(maxsize=None)
def _taxonomy_terms(repo_root: Path, taxonomy: str) -> frozenset[str]:
    """Every term ``taxonomy`` actually serves, derived from the frontmatter of
    every page that assigns one.

    Hugo generates a term page for each distinct value, so the content tree DOES
    determine the term set — the old allow-list's claim that it "cannot be
    checked from the markdown tree alone" was wrong, and it cost the repo any
    check at all on /tags/ and /series/ links.
    """
    key = taxonomy if taxonomy == "tags" else "series"
    terms: set[str] = set()
    for md in sorted((repo_root / "content").rglob("*.md")):
        for value in _fm_list(_fm_block(md), key):
            slug = _urlize(value)
            if slug:
                terms.add(slug)
    return frozenset(terms)


@lru_cache(maxsize=None)
def _served_section_paths(repo_root: Path) -> frozenset[str]:
    """Every path the non-post content sections serve, as ``/a/b/`` strings,
    plus every file under ``static/`` as its served ``/a/b.ext`` path.

    Resolution mirrors Hugo: ``index.md`` / ``_index.md`` are served at their
    directory, a flat ``<name>.md`` at ``<dir>/<name>/``, a frontmatter ``slug:``
    replaces the last segment and a ``url:`` replaces the whole path. A sibling
    ``.md`` inside a leaf bundle is a page RESOURCE, not a page, so it is not
    served and is skipped (``content/community/agit-featured/1-.../social.md``).

    ``aliases:`` targets are deliberately EXCLUDED. Hugo emits a redirect stub at
    each one, so they resolve for a visitor — but an in-repo link should point at
    the live path rather than take the hop, which is the same rule the retired
    /posts/ and /<category>/ URLs are rejected under.
    """
    content_root = repo_root / "content"
    paths: set[str] = set()
    for section in sorted(_CONTENT_TWO_PREFIX):
        base = content_root / section
        if not base.is_dir():
            continue
        for md in sorted(base.rglob("*.md")):
            if md.name not in ("index.md", "_index.md") and (md.parent / "index.md").is_file():
                continue
            block = _fm_block(md)
            override = _FM_URL_RE.search(block)
            if override:
                paths.add("/" + override.group(1).strip().strip("\"'").strip("/") + "/")
                continue
            if md.name in ("index.md", "_index.md"):
                rel = md.parent.relative_to(content_root)
                slug = _FM_SLUG_RE.search(block) if md.name == "index.md" else None
                if slug:
                    rel = rel.parent / slug.group(1).strip().strip("\"'").strip("/")
            else:
                rel = md.relative_to(content_root).with_suffix("")
            paths.add("/" + str(rel).strip("/") + "/")
    static_root = repo_root / "static"
    if static_root.is_dir():
        for asset in sorted(static_root.rglob("*")):
            if not asset.is_file():
                continue
            served = "/" + str(asset.relative_to(static_root))
            if served.endswith(".html"):
                # Cloudflare Pages serves a static .html at its EXTENSIONLESS
                # path and 308s the .html form to it (probed live: /...-social-cards
                # -> 200, /...-social-cards.html -> 308). The extensionless form is
                # therefore the canonical one, and registering only it keeps the
                # .html form rejected under the same no-redirect-hop rule the
                # retired /posts/ and /<category>/ URLs are rejected under.
                served = served[: -len(".html")]
            paths.add(served)
    return frozenset(paths)


@lru_cache(maxsize=None)
def _retired_tag_terms(repo_root: Path) -> frozenset[str]:
    """Tag terms that now exist only as a 301, read from ``static/_redirects``.

    Derived rather than hard-coded so that retiring another tag extends the check
    with no edit here. The redirect file is the single place that decides a term
    is retired, so reading it is what keeps this rule and the redirect set from
    drifting apart - the drift that let blog-priv#66 retire seven terms while
    every internal-link rule still knew only about blog-priv#62's categories.

    Matches the bare source form (``/tags/congress /tags/congresses/ 301``) and
    ignores the ``/*`` wildcard twin, which carries the same term.
    """
    redirects = repo_root / "static" / "_redirects"
    if not redirects.is_file():
        return frozenset()
    terms: set[str] = set()
    for line in redirects.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("/tags/"):
            term = parts[0][len("/tags/"):].strip("/")
            if term and not term.endswith("*"):
                terms.add(term)
    return frozenset(terms)


def _classify(target: str, repo_root: Path) -> tuple[bool, str]:
    """Return (ok, message). ``ok=True`` means the link passes; message is the
    error text when ``ok=False``."""
    # Trailing-slash normalisation: /blogs/foo and /blogs/foo/ are equivalent
    # (Hugo serves both — the path resolves to the same page bundle).
    stripped = target.strip("/")
    if stripped == "":
        return True, ""  # bare "/" — homepage.
    parts = stripped.split("/")
    first = parts[0]

    # --- the live blog tree -------------------------------------------------
    if first == _BLOG_ROOT:
        if len(parts) == 1:
            return True, ""  # the /blogs/ hub
        second = parts[1]
        if len(parts) == 2:
            if second == "index.xml" or second in _SECTIONS:
                return True, ""  # section feed, or a category landing
            if not second:
                return False, f"empty post slug in '{target}'"
            if second in _served_post_slugs(repo_root):
                return True, ""
            return False, (
                f"broken internal link: /{_BLOG_ROOT}/{second}/ is neither one of "
                f"the 7 category landings nor a post served at that slug "
                f"(a post's frontmatter `slug:` overrides its directory name)"
            )
        # /blogs/<category>/index.xml — per-category RSS feed.
        if len(parts) == 3 and second in _SECTIONS and parts[2] == "index.xml":
            return True, ""
        if second in _SECTIONS:
            slug = parts[2] if len(parts) > 2 and parts[2] else "<slug>"
            return False, (
                f"section-prefix link '{target}' — "
                f"category landings list posts, they don't host them. "
                f"Did you mean /{_BLOG_ROOT}/{slug}/?"
            )
        return False, f"unknown internal path '{target}'"

    # --- retired URL shapes (blog-priv#62) ----------------------------------
    # These still resolve for external visitors via the 301s in static/_redirects,
    # but an in-repo link should point at the live path rather than take the hop
    # (a redirected internal link is what AC 5.15 forbids).
    if first == "posts":
        rest = "/".join(parts[1:]).strip("/")
        suggestion = f"/{_BLOG_ROOT}/{rest}/" if rest else f"/{_BLOG_ROOT}/"
        return False, (
            f"retired URL '{target}' — posts moved to /{_BLOG_ROOT}/<slug>/. "
            f"Did you mean {suggestion}?"
        )
    if first in _SECTIONS:
        return False, (
            f"retired URL '{target}' — the 7 category landings moved under "
            f"/{_BLOG_ROOT}/. Did you mean /{_BLOG_ROOT}/{stripped}/?"
        )

    # --- everything else ----------------------------------------------------
    if len(parts) == 1:
        if first in _ALLOW_SINGLE:
            return True, ""
        return False, (
            f"unknown single-segment path '{target}' "
            f"(not blogs / hire-hoi / skills / about / legal / community / "
            f"index.xml / sitemap.xml)"
        )
    # A retired /tags/<term>/ (blog-priv#66). Checked BEFORE the allow-list below,
    # which accepts any /tags/<slug>/ because taxonomy term pages are generated
    # from frontmatter and cannot be enumerated from the markdown tree. The seven
    # terms the mechanical tag merges retired are the exception: they are the one
    # part of the taxonomy this repo CAN enumerate, because each one has a 301 in
    # static/_redirects. Without this, an author writes
    # `[congresses](/tags/congress/)`, pre-commit and CI pass, and every reader
    # takes a needless redirect hop - exactly what the /posts/ and /<category>/
    # rules above exist to prevent, applied to a class blog-priv#66 created and
    # did not sweep.
    if first == "tags" and len(parts) > 1 and parts[1] in _retired_tag_terms(repo_root):
        return False, (
            f"retired URL '{target}' - the tag '{parts[1]}' was merged away and now "
            f"only survives as a 301 in static/_redirects. Link the live term instead."
        )
    # --- /tags/<term>/ and /series/<term>/ — taxonomy term pages -------------
    if first in _TAXONOMY_TWO_PREFIX:
        rest = parts[1:]
        if rest and rest[-1] == "index.xml":
            rest = rest[:-1]  # the per-term RSS feed.
        if not rest:
            return True, ""  # the taxonomy list page itself.
        if len(rest) > 1:
            return False, (
                f"unknown internal path '{target}' — a {first} term page is "
                f"/{first}/<term>/, one segment deep"
            )
        served = _taxonomy_terms(repo_root, first)
        if rest[0] in served:
            return True, ""
        return False, (
            f"broken internal link: no page assigns the {first[:-1] if first == 'tags' else first} "
            f"'{rest[0]}', so Hugo generates no /{first}/{rest[0]}/ term page "
            f"(terms come from frontmatter, so add the term to a page or fix the link)"
        )

    # --- /hire-hoi/, /legal/, /community/ — real content sections ------------
    if first in _CONTENT_TWO_PREFIX:
        served = _served_section_paths(repo_root)
        if "/" + stripped in served:  # a static asset, e.g. a PDF.
            return True, ""
        if "/" + stripped + "/" in served:
            return True, ""
        # /<section>/.../index.xml — the RSS feed Hugo emits for each _index.md.
        if parts[-1] == "index.xml":
            parent = "/" + "/".join(parts[:-1]).strip("/") + "/"
            if parent in served:
                return True, ""
        return False, (
            f"broken internal link: '{target}' is not served by the {first} "
            f"section — no content page resolves to it and no file in static/ "
            f"matches (a frontmatter `url:`/`slug:` override decides the path, "
            f"and an `aliases:` entry is a redirect, not a live path)"
        )
    return False, f"unknown internal path '{target}'"


def scan_file(md_path: Path, repo_root: Path) -> list[tuple[int, str, str]]:
    """Return a list of (line_number, target_link, error_message) for every
    invalid internal link in ``md_path``. Read errors raise; the caller
    catches and returns exit 2."""
    raw = md_path.read_text(encoding="utf-8")
    body = _strip_non_link_regions(raw)
    # Reference-style link definitions (parsed from the stripped body so we
    # don't pick up code-fenced examples).
    refs: dict[str, tuple[int, str]] = {}
    for m in _REF_DEF_RE.finditer(body):
        ref_id = m.group(1).strip().lower()
        url = m.group(2).strip()
        line = _line_of(body, m.start())
        refs[ref_id] = (line, url)
    # Track which refs are consumed by image syntax `![alt][ref]` vs link
    # syntax `[text][ref]`. Image-only refs are skipped from URL classification
    # because image existence is out of scope (parity with the inline `(?<!!)`
    # lookbehind that already excludes `![alt](path)`).
    image_refs: set[str] = set()
    for m in _REF_IMG_USE_RE.finditer(body):
        alt = m.group(1).strip().lower()
        ref_id = m.group(2).strip().lower() or alt  # collapsed `![ref][]`
        image_refs.add(ref_id)
    link_refs: set[str] = set()
    for m in _REF_USE_RE.finditer(body):
        text = m.group(1).strip().lower()
        ref_id = m.group(2).strip().lower() or text  # collapsed `[text][]`
        link_refs.add(ref_id)
    findings: list[tuple[int, str, str]] = []
    seen: set[tuple[int, str]] = set()
    # Inline `[text](/path)` links.
    for m in _INLINE_LINK_RE.finditer(body):
        raw_target = m.group(1)
        line = _line_of(body, m.start())
        target = _normalise_target(raw_target)
        if target is None:
            continue
        ok, msg = _classify(target, repo_root)
        if not ok and (line, target) not in seen:
            seen.add((line, target))
            findings.append((line, target, msg))
    # Reference-style link usages — resolve ref → URL via the definitions
    # table, then classify. Skip refs consumed only as images (see image_refs
    # above).
    for ref_id in link_refs:
        if ref_id not in refs:
            continue  # unknown ref — markdown renders it as literal text, not a link
        ref_line, ref_url = refs[ref_id]
        target = _normalise_target(ref_url)
        if target is None:
            continue
        ok, msg = _classify(target, repo_root)
        if not ok and (ref_line, target) not in seen:
            seen.add((ref_line, target))
            findings.append((ref_line, target, msg))
    # Reference-style definitions whose URL is itself broken AND the ref is
    # used as a link (or unused — defensive: an unused link-shaped def is a
    # latent bug). Skip image-only refs (out of scope, parity with inline
    # image lookbehind).
    for ref_id, (line, url) in refs.items():
        if ref_id in image_refs and ref_id not in link_refs:
            continue
        target = _normalise_target(url)
        if target is None:
            continue
        ok, msg = _classify(target, repo_root)
        if not ok and (line, target) not in seen:
            seen.add((line, target))
            findings.append((line, target, msg))
    findings.sort(key=lambda t: (t[0], t[1]))
    return findings


def _walk_content(repo_root: Path) -> list[Path]:
    """Walk ``content/**/*.md`` returning a sorted list of paths."""
    content = repo_root / "content"
    if not content.is_dir():
        raise FileNotFoundError(f"content/ not found at {content}")
    return sorted(content.rglob("*.md"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate internal markdown links for hoiboy.uk."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Specific markdown files to scan. Omit to scan content/**/*.md.",
    )
    parser.add_argument(
        "--check-only-new",
        action="store_true",
        help=(
            "Accepted for parity with sibling validators. Internal-link rules "
            "do not depend on the HOIBOY_CUTOFF_DATE so this flag is a no-op."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repo root (default: parent of scripts/).",
    )
    args = parser.parse_args()
    _ = args.check_only_new  # acknowledge — no behavioural difference.
    repo_root = args.repo_root.resolve()
    try:
        files = list(args.paths) if args.paths else _walk_content(repo_root)
    except FileNotFoundError as exc:
        print(f"validate_internal_links: {exc}", file=sys.stderr)
        return 2

    # Zero-walk floor (#55 Stage 5). This gate used to exit 0 with ZERO stdout, so a
    # run that walked nothing was byte-identical in the CI log to a real 122-file run.
    # That matters more here than for most gates: docs/AUTHORING.md nominates this
    # tier as the compensating control for keeping content/posts in lychee's
    # exclude_path, so if it silently walks nothing, posts have no internal-link
    # coverage at ALL and the log still looks clean.
    # Scoped to the WALK: an explicit --paths of zero files is the caller's business
    # (pre-commit passes the staged set, which is legitimately empty for a non-md commit).
    if not args.paths and not files:
        print(
            "error: walked 0 markdown files under content/ - that tree is never "
            "empty, so the root or the filename filter is broken (vacuous pass).",
            file=sys.stderr,
        )
        return 1

    total = 0
    for md in files:
        try:
            findings = scan_file(md, repo_root)
        except OSError as exc:
            print(f"validate_internal_links: read error: {md}: {exc}", file=sys.stderr)
            return 2
        for line, target, msg in findings:
            try:
                rel = md.resolve().relative_to(repo_root)
            except ValueError:
                rel = md
            print(f"{rel}:{line}: {msg}", file=sys.stderr)
            total += 1
    if total:
        print(
            f"validate_internal_links: {total} broken internal link(s) found.",
            file=sys.stderr,
        )
        return 1
    # State the walk size, so a clean run is distinguishable from a vacuous one in a
    # CI log (#55 Stage 5 — the whole class this Issue exists to close).
    print(f"validate_internal_links: OK ({len(files)} file(s) scanned, 0 broken).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
