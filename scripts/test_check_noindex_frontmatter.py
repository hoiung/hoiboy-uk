#!/usr/bin/env python3
"""Tests for the noindex sitemap/feed gate (hoiboy-uk#56, Ralph escalation).

The gate shipped with NO test of any kind. It was wired into three surfaces and
reviewed six times, and the escalation class sweep found two defects in it that a
green run could never have surfaced, because nothing was pinning it:

  1. It hand-rolled a SECOND parser for `static/_headers`, which disagreed with
     the canonical one about a BOM and about `X-Robots-Tag: none`.
  2. It had no build-freshness floor, so against a stale tree it reported
     "[OK] ... 4 noindex rule(s) enforced ... no leaks" having examined none of
     the pages it exists to protect.

Both are the same shape and it is this repo's recurring one: a gate reports
success for a surface it did not examine. The assertions below are on the MESSAGE
and not the exit code, because this gate returns 1 for five distinct reasons and
`rc == 1` is compatible with it being red for a reason unrelated to the defect.

Run: python3 -m pytest scripts/test_check_noindex_frontmatter.py -q
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "check_noindex_frontmatter", _HERE / "check_noindex_frontmatter.py"
)
gate = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gate
_spec.loader.exec_module(gate)

REPO = _HERE.parent
PUBLIC = REPO / "public"

# Calls that consume a string as a PATTERN or a needle. A literal reaching one of
# these is the header name being matched; a literal reaching print() is a message
# about it. That difference is the whole point of the one-parser guard below, and
# text-level matching cannot see it.
_MATCHING_CALLS = frozenset({
    "search", "match", "compile", "findall", "finditer", "fullmatch", "sub",
    "startswith", "endswith", "partition", "rpartition", "split", "rsplit",
    "find", "rfind", "index", "count",
})


def _run(built: Path, monkeypatch) -> int:
    monkeypatch.setattr(sys, "argv", ["check_noindex_frontmatter.py", "--built", str(built)])
    return gate.main()


def _tree(root: Path, urls: list[str], sitemap: list[str] | None = None,
          feed: list[str] | None = None) -> Path:
    """A synthetic built tree: pages at `urls`, plus a sitemap and a feed.

    `sitemap`/`feed` default to the non-noindex pages, i.e. a correct build. A
    test that wants a leak passes the leaking URL explicitly.
    """
    root.mkdir(parents=True, exist_ok=True)
    for url in urls:
        page = root / url.strip("/") / "index.html" if url != "/" else root / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("<html></html>", encoding="utf-8")
    listed = urls if sitemap is None else sitemap
    body = "".join(f"<url><loc>https://hoiboy.uk{u}</loc></url>" for u in listed)
    (root / "sitemap.xml").write_text(f"<urlset>{body}</urlset>", encoding="utf-8")
    items = urls if feed is None else feed
    entries = "".join(f"<item><link>https://hoiboy.uk{u}</link></item>" for u in items)
    (root / "index.xml").write_text(f"<rss>{entries}</rss>", encoding="utf-8")
    return root


# The four non-exempt rules in the real static/_headers, and one ordinary page so
# the sitemap is never empty (the gate rejects an empty one outright).
_COVERED = [
    "/private/tools/meet-recorder/",
    "/community/asians-gingers-in-tech/thanks/",
    "/newsletter/",
    "/newsletter/check-inbox/",
    "/newsletter/confirmed/",
]
_ORDINARY = ["/", "/blogs/some-post/"]


@pytest.fixture()
def good(tmp_path) -> Path:
    """A fresh, correct build: every noindex page exists, none is advertised."""
    return _tree(tmp_path / "public", _COVERED + _ORDINARY,
                 sitemap=_ORDINARY, feed=_ORDINARY)


# --------------------------------------------------------------------------
# Positive controls. Without these every red test below could be red for free.
# --------------------------------------------------------------------------

@pytest.mark.skipif(not (PUBLIC / "sitemap.xml").exists(),
                    reason="no built tree; run `hugo --gc --minify -e production`")
def test_the_real_built_tree_passes(monkeypatch, capsys):
    """The live tree must be clean, or every mutation below proves nothing."""
    assert _run(PUBLIC, monkeypatch) == 0
    assert "[OK]" in capsys.readouterr().out


def test_synthetic_good_tree_passes(good, monkeypatch, capsys):
    """Guards the fixture itself: a fixture already red would fake every proof."""
    assert _run(good, monkeypatch) == 0
    assert "[OK]" in capsys.readouterr().out


# --------------------------------------------------------------------------
# A2 -- build-freshness floor.
# --------------------------------------------------------------------------

def test_stale_tree_missing_a_whole_route_is_named(tmp_path, monkeypatch, capsys):
    """A build predating the newsletter route must NOT report the rule enforced.

    This is the exact shape the escalation reproduced: the pages are absent, the
    sitemap and feed are populated and plausible, and every leak assertion holds
    vacuously.
    """
    built = _tree(tmp_path / "public",
                  [u for u in _COVERED if not u.startswith("/newsletter/")] + _ORDINARY,
                  sitemap=_ORDINARY, feed=_ORDINARY)
    assert _run(built, monkeypatch) == 1
    err = capsys.readouterr().err
    assert "[unbuilt-rule]" in err
    assert "/newsletter/*" in err
    assert "STALE" in err


def test_ok_line_reports_per_rule_built_page_counts(good, monkeypatch, capsys):
    """The evidence must be in the message, not just the verdict.

    An "[OK] ... 4 rules enforced" line that cannot say what each rule was
    measured against is indistinguishable from the vacuous pass.
    """
    assert _run(good, monkeypatch) == 0
    out = capsys.readouterr().out
    assert "Rules exercised:" in out
    assert "/newsletter/* -> 3 built page(s)" in out


# --------------------------------------------------------------------------
# A1 -- one file, one parser.
# --------------------------------------------------------------------------

def test_a_bom_does_not_drop_the_first_rule(tmp_path, monkeypatch):
    """Saved from a BOM-emitting editor, the first block must still be read.

    The hand-rolled parser read `utf-8`, so a leading U+FEFF stopped the first
    path line starting with "/" and that rule vanished with the gate still green.
    """
    headers = tmp_path / "_headers"
    headers.write_text(
        "﻿/private/*\n  X-Robots-Tag: noindex, nofollow\n\n"
        "/newsletter/*\n  X-Robots-Tag: noindex, nofollow\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "HEADERS", headers)
    assert gate.noindex_globs() == ["/private/*", "/newsletter/*"]


def test_x_robots_tag_none_counts_as_noindex(tmp_path, monkeypatch):
    """`none` is the documented equivalent of `noindex, nofollow`.

    A literal "noindex" matcher missed it entirely, so a page protected only by
    `none` was invisible to this gate, which then reported OK over it.
    """
    headers = tmp_path / "_headers"
    headers.write_text("/newsletter/*\n  X-Robots-Tag: none\n", encoding="utf-8")
    monkeypatch.setattr(gate, "HEADERS", headers)
    assert gate.noindex_globs() == ["/newsletter/*"]


def test_agent_scoped_directive_is_not_a_blanket_rule(tmp_path, monkeypatch):
    """Inherited from the canonical parser: `googlebot: noindex` binds one crawler.

    Reusing the canonical parser is what buys this, and it is the reason the
    reuse matters beyond deduplication -- the hand-rolled regex would have
    treated this as a site-wide verdict.
    """
    headers = tmp_path / "_headers"
    headers.write_text("/newsletter/*\n  X-Robots-Tag: googlebot: noindex\n", encoding="utf-8")
    monkeypatch.setattr(gate, "HEADERS", headers)
    assert gate.noindex_globs() == []


def test_repo_has_exactly_one_headers_parser():
    """A third parser for static/_headers must not be able to land silently.

    Two parsers for one file drifted in two directions at once and the drift was
    silent in the passing direction. This is the class-level guard: the parse
    lives in check_social_cards.py, and every other consumer reaches it through
    that module rather than re-deriving it.
    """
    # What is banned is the parsing CONSTRUCT, not the mention. A docstring may
    # name the header (this file's do); what may not happen is a non-canonical
    # module deriving a verdict from it by its own text matching.
    #
    # The first version of this guard asked whether the file mentioned
    # X-Robots-Tag while lacking `parse_noindex_globs`. That was too weak in the
    # exact direction that matters: a module which calls the canonical parser AND
    # ALSO hand-rolls a second one satisfied it, and a planted rogue parser was
    # waved straight through. Presence of the right call is not absence of the
    # wrong one.
    # Line-level text matching cannot separate the two, and trying it produced a
    # guard that flagged this very file's docstring for quoting the defect it
    # describes. The AST can: a comment is not in the tree at all, a docstring is
    # a known node, and anything else carrying the literal is the header name
    # being USED as data -- which is what parsing it looks like.
    offenders: list[str] = []
    scanned = 0
    for path in sorted((REPO / "scripts").glob("*.py")):
        if path.name == "check_social_cards.py":
            continue                       # the canonical parser itself
        if path.name.startswith("test_"):
            continue                       # fixtures legitimately contain the literal
        text = path.read_text(encoding="utf-8", errors="replace")
        if "x-robots-tag" not in text.lower():
            continue
        scanned += 1
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(
                    func, "id", "")
                if name not in _MATCHING_CALLS:
                    continue
            elif not isinstance(node, ast.Compare):
                continue
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                        and "x-robots-tag" in sub.value.lower()):
                    offenders.append(f"{path.name}:{sub.lineno}")
    assert scanned, (
        "no non-canonical script mentions X-Robots-Tag at all, so this guard "
        "scanned nothing and would pass no matter what landed. Check the glob."
    )
    assert not offenders, (
        "these lines parse X-Robots-Tag out of static/_headers directly instead "
        "of calling check_social_cards.parse_noindex_globs, so the repo now has "
        f"more than one parser for one file: {offenders}. One file, one parser."
    )


# --------------------------------------------------------------------------
# The gate's original purpose still holds after the fixes.
# --------------------------------------------------------------------------

def test_a_real_sitemap_leak_is_still_caught(tmp_path, monkeypatch, capsys):
    built = _tree(tmp_path / "public", _COVERED + _ORDINARY,
                  sitemap=_ORDINARY + ["/newsletter/confirmed/"], feed=_ORDINARY)
    assert _run(built, monkeypatch) == 1
    assert "[sitemap] /newsletter/confirmed/" in capsys.readouterr().err


def test_a_real_feed_leak_is_still_caught(tmp_path, monkeypatch, capsys):
    built = _tree(tmp_path / "public", _COVERED + _ORDINARY,
                  sitemap=_ORDINARY, feed=_ORDINARY + ["/newsletter/confirmed/"])
    assert _run(built, monkeypatch) == 1
    assert "[feed] /newsletter/confirmed/" in capsys.readouterr().err
