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

WHY THESE TESTS RENDER RATHER THAN GREP. The first version of this file asserted
that certain substrings were PRESENT in the template (`fileExists`, `hasPrefix
$path "/"`, three `errorf` call sites). Ralph Tier 2 showed that whole approach
is vacuous against the defect class that matters here: dropping the `not` from
any of the three guards inverts it -- the guard then rejects correct input and
accepts the broken input it exists to stop -- while every one of those substrings
survives untouched. Three such mutants passed every assertion. A guard's polarity
is not visible in its text, only in its behaviour.

So each guard is exercised by BUILDING a throwaway Hugo site that calls the real
shortcode, and asserting on what Hugo actually does: which build fails, and which
guard's message it fails with. That kills polarity inversion, `or`/`and` swaps,
a mis-paired error message, and a broken `static%s` path join, none of which a
substring check can see. `GUARD_CASES` is the enumerator: one row per way a
caller can be wrong, and `test_guard_table_covers_every_errorf_branch` fails if
a fourth guard is ever added to the template without a row here.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SHORTCODE = REPO_ROOT / "layouts" / "_shortcodes" / "static-link.html"

# Anchored on the call site: `{{- errorf ` at the start of a line, optionally
# indented. The doc comment mentions errorf in prose, and prose is not a guard.
ERRORF_CALL_SITE = re.compile(r"^\s*\{\{- errorf ", re.MULTILINE)

# One row per way a caller can be wrong. `guard` names which of the template's
# errorf branches must fire, and `fragment` is matched against Hugo's log, so a
# case that fails for the WRONG reason is a failure too -- which is what catches
# a guard whose polarity was inverted rather than removed.
GUARD_CASES = [
    pytest.param(
        '{{< static-link path="ok.pdf" label="Link" >}}',
        "ok.pdf",
        "root-relative",
        "static-link: needs a root-relative path",
        id="path-is-not-root-relative",
    ),
    pytest.param(
        '{{< static-link label="Link" >}}',
        None,
        "root-relative",
        "static-link: needs a root-relative path",
        id="path-argument-missing",
    ),
    pytest.param(
        '{{< static-link path="/ok.pdf" >}}',
        "ok.pdf",
        "label",
        "static-link: needs a label",
        id="label-argument-missing",
    ),
    pytest.param(
        '{{< static-link path="/gone.pdf" label="Link" >}}',
        None,
        "file-exists",
        "static-link: no file at static/gone.pdf",
        id="target-file-does-not-exist",
    ),
]

# Every distinct guard GUARD_CASES exercises. Kept beside the table so the
# coupling assertion below reads off one source rather than a hand-typed number.
COVERED_GUARDS = {"root-relative", "label", "file-exists"}


def hugo_binary() -> str:
    """Locate hugo, or fail loudly.

    Deliberately NOT a pytest.skip. A skip here would turn the whole file green
    on a machine with no hugo, which is the vacuous-gate shape these tests were
    rewritten to remove. CI installs the pinned hugo at
    .github/workflows/ci.yml:89-92, long before it runs this file at :251-252.
    """
    found = shutil.which("hugo")
    assert found, (
        "hugo is not on PATH, so the static-link guards cannot be exercised. "
        "This is a hard failure, not a skip: these tests assert build "
        "BEHAVIOUR, and a silent skip would report a passing gate that never "
        "ran. Install the pinned version from .hugo-version (see CLAUDE.md "
        "'Development Setup')."
    )
    return found


def build_site(
    tmp_path: Path,
    call: str,
    static_file: str | None,
    shortcode_src: str | None = None,
) -> tuple[int, str, str]:
    """Build a throwaway one-page Hugo site that calls the shortcode.

    Returns (exit code, combined log, rendered index.html or "").
    `shortcode_src` overrides the template text, which is how the mutation
    harness feeds this a deliberately broken guard.
    """
    site = tmp_path / "site"
    (site / "layouts" / "_shortcodes").mkdir(parents=True)
    (site / "content").mkdir(parents=True)
    (site / "static").mkdir(parents=True)

    src = SHORTCODE.read_text(encoding="utf-8") if shortcode_src is None else shortcode_src
    (site / "layouts" / "_shortcodes" / "static-link.html").write_text(src, encoding="utf-8")
    # The whole layout: render the page body and nothing else. disableKinds
    # keeps hugo from warning about taxonomy templates this site has no use for.
    (site / "layouts" / "index.html").write_text("{{ .Content }}", encoding="utf-8")
    (site / "hugo.toml").write_text(
        'baseURL = "https://example.test/"\n'
        'title = "static-link contract"\n'
        'disableKinds = ["taxonomy", "term", "RSS", "sitemap", "404"]\n',
        encoding="utf-8",
    )
    (site / "content" / "_index.md").write_text(
        f"---\ntitle: contract\n---\n\n{call}\n", encoding="utf-8"
    )

    if static_file:
        target = site / "static" / static_file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"%PDF-1.4 stub for the contract test\n")

    proc = subprocess.run(
        [hugo_binary(), "-s", str(site), "-d", str(site / "public")],
        capture_output=True,
        text=True,
        timeout=180,
    )
    rendered = ""
    index = site / "public" / "index.html"
    if index.is_file():
        rendered = index.read_text(encoding="utf-8")
    return proc.returncode, proc.stdout + proc.stderr, rendered


def test_happy_path_emits_the_new_tab_anchor(tmp_path: Path) -> None:
    """A correct call builds, and the anchor carries BOTH new-tab attributes."""
    code, log, rendered = build_site(
        tmp_path, '{{< static-link path="/ok.pdf" label="View it" >}}', "ok.pdf"
    )
    assert code == 0, f"a valid static-link call must build. hugo exit {code}:\n{log}"
    assert '<a href="/ok.pdf" target="_blank" rel="noopener">View it</a>' in rendered, (
        "static-link must emit the href plus the exact pair `target=\"_blank\" "
        'rel="noopener"`. target="_blank" is the operator\'s new-tab '
        'requirement; rel="noopener" is what stops the opened document holding '
        "a live window.opener handle back to this page. render-link.html "
        f"cannot supply either for a root-relative path. Rendered:\n{rendered}"
    )


@pytest.mark.parametrize(("call", "static_file", "guard", "fragment"), GUARD_CASES)
def test_guard_rejects_bad_input(
    tmp_path: Path, call: str, static_file: str | None, guard: str, fragment: str
) -> None:
    """Each guard fails the build, and fails it with its OWN message.

    Asserting the message, not just a non-zero exit, is what makes an inverted
    guard visible: invert the root-relative check and this call still fails, but
    it fails later on `no file at staticok.pdf` instead, and that mismatch is
    the failure.
    """
    code, log, _ = build_site(tmp_path, call, static_file)
    assert code != 0, (
        f"the {guard} guard must fail the build for `{call}`, but hugo exited 0. "
        f"A guard that does not stop bad input is not a guard.\n{log}"
    )
    assert fragment in log, (
        f"the {guard} guard must fail with its own message. Expected "
        f"{fragment!r} in hugo's log for `{call}`, got:\n{log}"
    )


def test_guard_table_covers_every_errorf_branch() -> None:
    """GUARD_CASES must exercise every errorf branch the template carries.

    This is the coupling check. Add a fourth guard to static-link.html and this
    fails until GUARD_CASES gains a row for it, so the enumerator above cannot
    silently fall behind the template it is meant to cover.
    """
    src = SHORTCODE.read_text(encoding="utf-8")
    errorf_guards = ERRORF_CALL_SITE.findall(src)
    exercised = {case.values[2] for case in GUARD_CASES}
    assert exercised == COVERED_GUARDS, (
        f"GUARD_CASES exercises {sorted(exercised)} but COVERED_GUARDS names "
        f"{sorted(COVERED_GUARDS)}. Keep the two in step."
    )
    assert len(errorf_guards) == len(COVERED_GUARDS), (
        f"static-link.html has {len(errorf_guards)} errorf call sites but "
        f"GUARD_CASES covers {len(COVERED_GUARDS)} guards "
        f"({sorted(COVERED_GUARDS)}). Every guard needs a row in GUARD_CASES "
        f"naming the input that trips it and the message it must emit, or a "
        f"guard ships with nothing exercising it. Count the CALL SITES, not "
        f"the word: the doc comment names errorf in prose too."
    )
