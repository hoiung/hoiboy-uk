#!/usr/bin/env python3
"""The `static-link` shortcode opens a new tab and fails the build on a missing file.

hoiboy-uk#59.

WHY THIS FILE EXISTS. Two site gates that look like they cover a link to a PDF
under `static/` do not cover this one.

`layouts/_markup/render-link.html:3` gives `target="_blank"` to `http*` links
only, so a plain markdown link to a root-relative PDF opens in the SAME tab.
The operator's requirement is a new tab, so the shortcode has to emit the
attributes itself.

`scripts/validate_internal_links.py:132,167` strips every `{{< ... >}}` call
before it scans, and parses markdown links only. So it can see neither this
shortcode's invocation nor a raw `<a href>`. Renaming or deleting the PDF would
ship a dead link with every gate green. The `fileExists` + `errorf` branch is
the only thing that actually holds the path, and it holds it at build time, in
CI and on Cloudflare alike.

WHAT IS ASSERTED. The three `errorf` guards are counted at their CALL SITES
using an anchored pattern. Unanchored, `errorf` matches 4 and `fileExists`
matches 2, because the doc comment at the top of the shortcode names both --
so an unanchored `== 3` would fail correct work. The precedent
(`scripts/test_cta_button.py`) asserts exact counts for the same reason: a
guard silently dropped is the defect, and a count is what catches it.

`rel="noopener"` is asserted alongside `target="_blank"` rather than separately:
a new-tab link without it hands the opened document a live `window.opener`
handle back to this page.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHORTCODE = REPO_ROOT / "layouts" / "_shortcodes" / "static-link.html"

# Anchored on the call site: `{{- errorf ` at the start of a line, optionally
# indented. The doc comment mentions errorf in prose, and prose is not a guard.
ERRORF_CALL_SITE = re.compile(r"^\s*\{\{- errorf ", re.MULTILINE)


def source() -> str:
    """The shortcode's text, read fresh so a mutation to the file is seen."""
    assert SHORTCODE.is_file(), (
        f"{SHORTCODE} does not exist. The brochure link in "
        f"content/hire-hoi/ict-consultancy/_index.md calls this shortcode; "
        f"without the file the Hugo build fails outright."
    )
    return SHORTCODE.read_text(encoding="utf-8")


def test_opens_in_a_new_tab_safely() -> None:
    """The emitted anchor carries BOTH new-tab attributes, adjacent."""
    src = source()
    assert 'target="_blank" rel="noopener"' in src, (
        'static-link.html must emit the exact pair `target="_blank" '
        'rel="noopener"` on its anchor. target="_blank" is the operator\'s '
        "new-tab requirement; rel=\"noopener\" is what stops the opened "
        "document holding a live window.opener handle back to this page. "
        "render-link.html cannot supply either for a root-relative path."
    )


def test_missing_file_fails_the_build() -> None:
    """`fileExists` is what makes a renamed or deleted PDF a build failure."""
    src = source()
    assert "fileExists" in src, (
        "static-link.html must call fileExists. validate_internal_links.py "
        "strips shortcode calls before scanning and lychee skips "
        "root-relative paths, so this is the ONLY gate that notices the "
        "target file has gone. Without it a rename ships a dead link "
        "silently."
    )
    assert "$file := printf" in src, (
        "the fileExists check must test the path under static/, built from "
        "the caller's root-relative path. Checking the bare path would look "
        "for the file at the repo root and error on every correct call."
    )


def test_three_guard_branches_are_present() -> None:
    """Each `errorf` stops a distinct named failure; none may be dropped."""
    src = source()
    errorf_guards = ERRORF_CALL_SITE.findall(src)
    assert len(errorf_guards) == 3, (
        f"expected exactly 3 errorf call sites in static-link.html, found "
        f"{len(errorf_guards)}. The three guards are: a path that is not "
        f"root-relative (it would silently resolve against the page URL), a "
        f"missing label (an invisible link), and a missing file (a 404). "
        f"Count the CALL SITES, not the word: the doc comment names errorf "
        f"in prose too."
    )


def test_path_must_be_root_relative() -> None:
    """A relative path resolves against the page URL and breaks quietly."""
    src = source()
    assert 'hasPrefix $path "/"' in src, (
        "static-link.html must reject a path that does not start with /. A "
        "relative path resolves against the calling page's URL, so the link "
        "would 404 from every page except by accident, and fileExists would "
        "be checking a different file than the browser requests."
    )
