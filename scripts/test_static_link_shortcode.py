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

# The doc comment mentions errorf in prose, and prose is not a guard, so the
# comment block is stripped before anything is counted. What remains is matched
# on the call site itself rather than on its position in the line.
#
# This was `^\s*\{\{- errorf ` -- line-start, trim-dash mandatory -- until Ralph
# round 2 Tier 3, which pointed out that the coupling check below was written in
# the very idiom this file exists to stop: it asserted a TEXTUAL SHAPE and called
# it a count of guards. Two legal Hugo spellings slipped past it, both proven
# against a real build: `{{ errorf` without the trim dash, and an errorf sitting
# inline on the same line as its `if`. A fourth guard written either way was live
# in the template and invisible here, so the docstring's promise below was false.
# Measured after the change: 3 on the real template (the prose mention still does
# not count), 4 on all three added-guard spellings.
GO_COMMENT = re.compile(r"\{\{-?\s*/\*.*?\*/\s*-?\}\}", re.DOTALL)
ERRORF_CALL_SITE = re.compile(r"\{\{-?\s*errorf\b")

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
        # An absolute URL is not "missing a /" -- it CONTAINS one -- so a guard
        # widened to admit `http` alongside `/` still rejects every other case
        # in this table and survives without this row. Ralph round 2 Tier 2
        # built exactly that mutant and it passed all six tests. The guard's
        # contract is root-relative, and http links belong to markdown plus
        # render-link.html, so this pins the boundary rather than the symptom.
        '{{< static-link path="https://example.com/x.pdf" label="Link" >}}',
        None,
        "root-relative",
        "static-link: needs a root-relative path",
        id="path-is-an-absolute-url",
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
    # These config blocks mirror config/_default/hugo.toml (keepQuotes at :117,
    # unsafe at :127). A fixture that claims to prove what Hugo does in
    # production has to be configured like production, and this one was not.
    #
    # Precisely which part is load-bearing, because Ralph round 5 Tier 3 caught
    # this comment overclaiming: `keepQuotes` IS (drop it and the minifier
    # unquotes every attribute), and `--minify` below IS. `unsafe = true` is NOT
    # -- measured, the suite stays at 9 passed without it, because Hugo
    # substitutes shortcode output after goldmark has run, so the anchor never
    # takes the raw-HTML path. It is kept to mirror production rather than to
    # make anything pass, and this note records that it currently reddens
    # nothing so a future reader does not mistake it for a guard.
    #
    # Measured on the real site, the rendered anchor differs on both live axes:
    #   no --minify                  -> href="...Jolyn-Hoi_CRE&#43;ICT_..."
    #   --minify, keepQuotes unset   -> <a href=/ok.pdf target=_blank rel=noopener>
    #   --minify + keepQuotes = true -> href="...Jolyn-Hoi_CRE+ICT_..." (what ships)
    # Go's html/template escapes `+` in an href to `&#43;`; the minifier is what
    # normalises it back. `+` is the one character the operator pinned in this
    # filename, so the fixture was diverging from production on exactly the
    # character that matters. The happy-path case never caught it because
    # `/ok.pdf` contains nothing the modes disagree about; Ralph round 5 Tier 2's
    # positive control did.
    (site / "hugo.toml").write_text(
        'baseURL = "https://example.test/"\n'
        'title = "static-link contract"\n'
        'disableKinds = ["taxonomy", "term", "RSS", "sitemap", "404"]\n'
        "[markup.goldmark.renderer]\n"
        "  unsafe = true\n"
        "[minify.tdewolff.html]\n"
        "  keepQuotes = true\n",
        encoding="utf-8",
    )
    (site / "content" / "_index.md").write_text(
        f"---\ntitle: contract\n---\n\n{call}\n", encoding="utf-8"
    )

    if static_file:
        target = site / "static" / static_file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"%PDF-1.4 stub for the contract test\n")

    # `--minify` mirrors the real build command (`hugo --gc --minify -e
    # production`, .github/workflows/ci.yml) and is load-bearing for any
    # assertion on rendered HTML. Go's html/template escapes `+` in an href to
    # the entity `&#43;`, and the minifier is what normalises it back to a
    # literal `+`. Measured both ways on the real site: minified ->
    # `Jolyn-Hoi_CRE+ICT_...`, unminified -> `Jolyn-Hoi_CRE&#43;ICT_...`. Without
    # this flag the fixture asserted against a form Cloudflare never serves.
    proc = subprocess.run(
        [hugo_binary(), "--minify", "-s", str(site), "-d", str(site / "public")],
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


# The real published path, so the two withdrawal tests below exercise the actual
# URL the privacy notice is talking about rather than a stand-in.
BROCHURE = "hire-hoi/ict-consultancy/Jolyn-Hoi_CRE+ICT_brochure_v1.0.pdf"
PUBLISHED_CALL = f'{{{{< static-link path="/{BROCHURE}" label="View the brochure" >}}}}'


def test_withdrawal_path_removes_link_and_file_together(tmp_path: Path) -> None:
    """The privacy notice's withdrawal outcome must be one the build can deliver.

    `content/legal/privacy/index.md` tells a named third party that taking the
    brochure down "removes both the link and the file together". That sentence is
    a promise to a data subject about her own withdrawal right, and it is the
    THIRD wording of this bullet: the first invented a timescale the deploy path
    could not keep, and the second ("I remove the file and the site republishes
    without it") described an operation that DEFEATS ITSELF -- removing only the
    file trips the fileExists guard, reddens CI, and `deploy.yml` then never fires
    the Cloudflare hook, so the old deployment keeps serving the brochure. The
    withdrawal, performed exactly as written, would have left her data live.

    Prose was rewritten twice and broke twice because nothing bound it to the
    machinery. This test is that binding:

      1. a POSITIVE CONTROL builds the published state and proves the anchor and
         the file are really there, so step 2 cannot pass for the wrong reason;
      2. link removed AND file removed -> the site builds AND neither the anchor
         nor the file survives, which is the outcome the sentence promises;
      3. file removed while the link remains -> the build FAILS on the
         missing-file guard, which is why the wording says "together" rather
         than naming the file alone.

    Step 1 exists because of Ralph round 5 Tier 2. Until then step 2 built a page
    containing no shortcode call at all and asserted only `exit == 0`, which is
    true of any page whatsoever -- it passed with `static-link.html` deleted
    outright. The docstring claimed it "asserts both halves of the coupling" and
    it asserted neither. That is the same vacuity class this whole file exists to
    kill, reappearing inside the fix for it.

    The coupling the build enforces is ONE-DIRECTIONAL. That blindness is
    disclosed, deliberately, by the test immediately below this one.
    """
    published = build_site(tmp_path / "published", PUBLISHED_CALL, BROCHURE)
    code_pub, log_pub, html_pub = published
    served_pub = tmp_path / "published" / "site" / "public" / BROCHURE
    assert code_pub == 0, (
        f"the published state must build, or nothing below means anything. "
        f"hugo exit {code_pub}:\n{log_pub}"
    )
    assert f'href="/{BROCHURE}"' in html_pub, (
        "POSITIVE CONTROL: the published state must actually emit the brochure "
        "anchor. If it does not, the 'link is gone' assertion below passes on a "
        f"site that never had a link. Rendered:\n{html_pub}"
    )
    assert served_pub.is_file(), (
        "POSITIVE CONTROL: the published state must actually serve the file at "
        "its own URL. If it does not, the 'file is gone' assertion below passes "
        "on a site that never served it."
    )

    both_removed = build_site(
        tmp_path / "both", "The brochure is no longer published here.", None
    )
    code_both, log_both, html_both = both_removed
    served_both = tmp_path / "both" / "site" / "public" / BROCHURE
    assert code_both == 0, (
        "removing the link and the file together must leave a buildable site, "
        "because that is the withdrawal outcome the privacy notice promises "
        f"a data subject. hugo exit {code_both}:\n{log_both}"
    )
    assert BROCHURE not in html_both, (
        "after withdrawal the rendered page must not still link the brochure. "
        f"Rendered:\n{html_both}"
    )
    assert not served_both.exists(), (
        "after withdrawal the brochure must not still be published at its own "
        "URL. This is the half of 'together' that concerns the data subject: a "
        "page that stops linking the file while the file stays served has not "
        "withdrawn anything."
    )

    # The REAL brochure call with the file absent, not a `/gone.pdf` stand-in.
    # Ralph round 5 Tier 3 pointed out that the stand-in made this step a
    # duplicate of the `target-file-does-not-exist` GUARD_CASES row, while the
    # docstring above described it as the withdrawal path for this brochure.
    # Using the published call is what makes step 3 about the thing the privacy
    # notice actually promises.
    code_file_only, log_file_only, _ = build_site(
        tmp_path / "fileonly",
        PUBLISHED_CALL,
        None,
    )
    assert code_file_only != 0, (
        "removing the file while leaving the link must FAIL the build. If this "
        "ever passes, the fileExists guard is gone and a withdrawal that deletes "
        "only the file would ship a dead link instead of failing loudly."
    )
    assert "static-link: no file at" in log_file_only, (
        "the file-only removal must fail on the missing-file guard specifically, "
        f"not incidentally. hugo said:\n{log_file_only}"
    )


def test_withdrawal_coupling_is_one_directional_by_construction(tmp_path: Path) -> None:
    """The build enforces "together" in ONE direction. This asserts the blindness.

    Found by Ralph round 5 Tier 2 and recorded here rather than in prose, per
    `SST3/standards/stage-4/mutation-verification.md` sweep quality gate 5: a
    gate blind BY CONSTRUCTION asserts its blindness, not its safety, with a test
    that FAILS if a future change makes it sensitive -- so the disclosure cannot
    quietly go stale.

    The asymmetry: `fileExists` fires at BUILD time on a call that names a
    missing file, so file-gone-while-link-remains fails loudly (proven by the
    test above). Nothing looks the other way. Hugo copies `static/` verbatim
    whether or not any page references it, so link-gone-while-file-remains
    builds clean and the brochure is STILL published at its own URL, reachable
    by anyone who kept it.

    That state is not hypothetical: this Issue's own documented Rollback
    deliberately produces it, reverting the page commit for diagnosis while the
    PDF stays in place. It is why the privacy notice's Retention bullet is worded
    as a commitment about what taking it down does, and not as a claim that the
    build prevents a half-completed take-down. It cannot.

    If someone later adds an orphan-asset guard, this test fails -- and that is
    the correct moment to revisit both the Rollback procedure and the notice's
    wording, together.
    """
    code, log, html = build_site(
        tmp_path, "The brochure is no longer published here.", BROCHURE
    )
    served = tmp_path / "site" / "public" / BROCHURE
    assert code == 0, (
        "dropping only the link must still build today. If this now fails, an "
        f"orphan-asset guard has landed. hugo exit {code}:\n{log}"
    )
    assert BROCHURE not in html, (
        f"the page must no longer link the brochure in this scenario:\n{html}"
    )
    assert served.is_file(), (
        "DISCLOSED BLINDNESS: an unreferenced brochure is still copied to the "
        "published output and still served at its own URL. No build-time guard "
        "catches this direction. If this assertion ever fails, the build has "
        "become sensitive to orphaned assets and the Retention wording plus the "
        "Issue's Rollback procedure both need revisiting."
    )


def test_guard_table_covers_every_errorf_branch() -> None:
    """GUARD_CASES must exercise every errorf branch the template carries.

    This is the coupling check. Add a fourth guard to static-link.html and this
    fails until GUARD_CASES gains a row for it, so the enumerator above cannot
    silently fall behind the template it is meant to cover.
    """
    src = SHORTCODE.read_text(encoding="utf-8")
    errorf_guards = ERRORF_CALL_SITE.findall(GO_COMMENT.sub("", src))
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
