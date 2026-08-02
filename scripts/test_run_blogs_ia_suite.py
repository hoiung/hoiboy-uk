#!/usr/bin/env python3
"""The Blogs IA pre-push gate runs the same suite CI does, and says why it can't.

Two failure modes this locks down, both of which the gate would otherwise invite.

ONE: the suite drifts between its two callers. The 10 test files are named in
`.pre-commit-config.yaml` (so the hook entry names them, #55 AC 2.1 half (b)) and
again in `ci.yml`'s "Blogs IA tests" step. Two lists means one can gain a file the
other never runs, which reproduces the exact defect `tests/test_gate_wiring.py`
exists to catch, one level up: a test that looks wired because SOME caller runs it.
Asserted as set equality, so a file added to either side alone fails here.

TWO: the gate emits a stack trace instead of an instruction. 8 of the 10 tests
read the BUILT tree, so without `./public` they fail with tracebacks about missing
paths, and the author has to reverse-engineer "run hugo" from them. AC 2.3 requires
an actionable message naming the build command. These tests assert the MESSAGE,
not the exit code -- a gate that fails for the right reason with the wrong words
still costs the author the same debugging time, and exit-code-only assertions are
how a message regression ships unnoticed.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "scripts" / "run-blogs-ia-suite.sh"
PRE_COMMIT = ROOT / ".pre-commit-config.yaml"
CI = ROOT / ".github" / "workflows" / "ci.yml"

BUILD_CMD = "hugo --gc --minify -e production"

# Measured 2026-08-02 by parking ./public and running each file individually.
NEEDS_PUBLIC = {
    "scripts/test_permalink_contract.py",
    "scripts/test_redirects_coverage.py",
    "scripts/test_hub_listing.py",
    "scripts/test_page_url_permalinks.py",
    "scripts/test_section_keyed_regression.py",
    "scripts/test_taxonomy_cleanup.py",
    "scripts/readnext_parse.py",
    "scripts/test_related_ranking.py",
}


def _hook_test_files() -> set[str]:
    """The files listed under the blogs-ia-suite hook's `args:`."""
    text = PRE_COMMIT.read_text(encoding="utf-8")
    block = re.search(
        r"^      - id: blogs-ia-suite$(.*?)(?=^      - id: |^      # >>> SST3)",
        text,
        re.M | re.S,
    )
    assert block, "no `blogs-ia-suite` hook found in .pre-commit-config.yaml"
    return set(re.findall(r"^\s*-\s+(scripts/\S+\.py)\s*$", block.group(1), re.M))


def _ci_test_files() -> set[str]:
    """The files in ci.yml's `Blogs IA tests` step, comments stripped."""
    text = CI.read_text(encoding="utf-8")
    step = re.search(
        r"^      - name: Blogs IA tests.*?\n(.*?)(?=^      - name: |^      # )",
        text,
        re.M | re.S,
    )
    assert step, "no `Blogs IA tests` step found in ci.yml"
    body = "\n".join(
        ln for ln in step.group(1).splitlines() if not ln.strip().startswith("#")
    )
    return set(re.findall(r"(scripts/\S+\.py)", body))


def test_hook_and_ci_run_the_identical_suite():
    hook, ci = _hook_test_files(), _ci_test_files()
    assert hook, "the blogs-ia-suite hook names no test files"
    assert hook == ci, (
        "the Blogs IA suite has drifted between its two callers. "
        f"only in .pre-commit-config.yaml: {sorted(hook - ci)}; "
        f"only in ci.yml: {sorted(ci - hook)}. "
        "Both callers must run the same suite, or a file is enforced in one "
        "place and silently unrun in the other (#55 AC 2.1)."
    )


def test_the_suite_is_the_documented_ten_files():
    assert len(_hook_test_files()) == 10, (
        f"expected the 10-file Blogs IA suite, found {len(_hook_test_files())}. "
        "If the suite legitimately changed size, update #55 AC 2.1 and this test "
        "together."
    )


def test_every_public_dependent_file_is_named_in_the_runner():
    """The runner's NEEDS_PUBLIC list is what the author is shown. Keep it true."""
    listed = set(
        re.findall(
            r"^\s*(scripts/\S+\.py)\s*$",
            re.search(
                r"NEEDS_PUBLIC=\((.*?)\)", RUNNER.read_text(encoding="utf-8"), re.S
            ).group(1),
            re.M,
        )
    )
    assert listed == NEEDS_PUBLIC, (
        "run-blogs-ia-suite.sh's NEEDS_PUBLIC no longer matches the measured set. "
        f"only in the script: {sorted(listed - NEEDS_PUBLIC)}; "
        f"only in this test: {sorted(NEEDS_PUBLIC - listed)}. "
        "Re-measure by parking ./public and running each file, then update both."
    )


def _run(cwd: Path) -> subprocess.CompletedProcess:
    """Run the COPY inside the fixture, never the real script.

    The runner derives its repo root from `${BASH_SOURCE[0]}/..` and cd's there,
    so invoking the real path would make it operate on the real repo and ignore
    the fixture entirely -- the first draft of this file did exactly that, and
    every precondition test passed against the live tree instead of the tmp one.
    """
    return subprocess.run(
        ["bash", str(cwd / "scripts" / "run-blogs-ia-suite.sh"),
         "scripts/test_redirects_order.py"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo_without_public(tmp_path: Path) -> Path:
    """A minimal tree shaped like the repo but with no ./public."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run-blogs-ia-suite.sh").write_bytes(
        RUNNER.read_bytes()
    )
    return tmp_path


def test_missing_public_names_the_build_command(repo_without_public: Path):
    r = _run(repo_without_public)
    assert r.returncode == 1, f"expected exit 1, got {r.returncode}"
    assert BUILD_CMD in r.stderr, (
        "the missing-./public message must name the build command verbatim so the "
        f"author can copy it. stderr was:\n{r.stderr}"
    )
    assert "isn't one" in r.stderr or "there isn't one" in r.stderr


def test_missing_public_lists_which_tests_need_it(repo_without_public: Path):
    """AC 2.3: the gate must STATE WHICH tests need the tree."""
    r = _run(repo_without_public)
    for f in NEEDS_PUBLIC:
        assert f in r.stderr, (
            f"{f} needs ./public but the message does not name it. An author told "
            f"only that 'some tests' need a build cannot tell which. stderr:\n{r.stderr}"
        )


def test_missing_public_does_not_emit_a_stack_trace(repo_without_public: Path):
    r = _run(repo_without_public)
    combined = r.stdout + r.stderr
    assert "Traceback" not in combined, (
        "AC 2.3 requires an actionable message, not a stack trace. The precondition "
        f"check must run BEFORE pytest. Output:\n{combined}"
    )


def test_empty_public_dir_is_caught_not_treated_as_built(tmp_path: Path):
    """A `public/` that exists but holds no index.html is not a build."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run-blogs-ia-suite.sh").write_bytes(RUNNER.read_bytes())
    (tmp_path / "public").mkdir()
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "no index.html" in r.stderr, r.stderr
    assert BUILD_CMD in r.stderr


def test_stale_public_is_rejected(tmp_path: Path):
    """A tree built before the newest source edit proves nothing about this push."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run-blogs-ia-suite.sh").write_bytes(RUNNER.read_bytes())
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "index.html").write_text("<html></html>")
    (tmp_path / "content").mkdir()
    src = tmp_path / "content" / "post.md"
    src.write_text("# newer than the build")
    import os

    st = (tmp_path / "public" / "index.html").stat()
    os.utime(src, (st.st_atime + 10, st.st_mtime + 10))

    r = _run(tmp_path)
    assert r.returncode == 1, f"stale tree must fail. stderr:\n{r.stderr}"
    assert "STALE" in r.stderr, r.stderr
    assert BUILD_CMD in r.stderr


def test_no_test_files_is_a_usage_error(tmp_path: Path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run-blogs-ia-suite.sh").write_bytes(RUNNER.read_bytes())
    r = subprocess.run(
        ["bash", str(tmp_path / "scripts" / "run-blogs-ia-suite.sh")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2, (
        "a runner invoked with no test files must be a usage error, not a silent "
        "zero-test PASS -- that is the vacuous-gate class this whole issue is about."
    )


def _tree(tmp_path: Path) -> Path:
    """A minimal repo-shaped tree with a built ./public and all six source roots."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run-blogs-ia-suite.sh").write_bytes(RUNNER.read_bytes())
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "index.html").write_text("<html></html>")
    for root in ("content", "layouts", "config", "assets", "data", "static"):
        (tmp_path / root).mkdir()
    (tmp_path / "content" / "post.md").write_text("# a post")
    (tmp_path / "data" / "consulting.yaml").write_text("offer: {}\n")
    (tmp_path / "static" / "_redirects").write_text("/old /new 301\n")
    # The build must be the NEWEST thing in the tree, or `find -newer ... -quit`
    # returns whichever source file happened to be written last and the test proves
    # nothing about the root it names. Stamp it after the sources exist.
    (tmp_path / "public" / "index.html").touch()
    return tmp_path


def _age(tmp_path: Path, rel: str, seconds: int = 10) -> None:
    """Make `rel` look `seconds` newer than the build, without changing its bytes."""
    import os

    st = (tmp_path / "public" / "index.html").stat()
    os.utime(tmp_path / rel, (st.st_atime + seconds, st.st_mtime + seconds))


@pytest.mark.parametrize("root,rel", [
    ("data", "data/consulting.yaml"),
    ("static", "static/_redirects"),
])
def test_every_hugo_source_root_is_scanned(tmp_path: Path, root: str, rel: str):
    """Hugo reads SIX roots; the scan named four, so two were invisible (#55 Stage 5).

    data/ is live via layouts/_shortcodes/consulting-cta.html (`hugo.Data.consulting`)
    and static/_redirects is exactly what scripts/test_redirects_coverage.py asserts
    against the BUILT tree -- so editing either and pushing without a rebuild ran the
    suite against output that no longer corresponded to the sources being pushed.
    """
    t = _tree(tmp_path)
    (t / rel).write_text("# a real edit\n")     # content CHANGE, not just a touch
    _age(t, rel)

    r = _run(t)
    assert r.returncode == 1, (
        f"an unbuilt edit under {root}/ must be STALE, but the scan did not see it. "
        f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    )
    assert rel in r.stderr, (
        f"the gate must NAME {rel}; naming some other file means it tripped for an "
        f"unrelated reason and this test proves nothing. stderr:\n{r.stderr}"
    )


def test_a_touched_but_unchanged_file_is_not_stale(tmp_path: Path):
    """mtime is not a proxy for 'edited' (#55 Stage 5).

    Running this hook through pre-commit rewrites unrelated working-tree files,
    bumping mtimes with byte-identical content. That made a PASS invalidate its own
    precondition: the next run reported STALE on an unchanged tree and demanded a
    rebuild that changed nothing. Because pre-publish.sh always leaves a regenerated
    share-card.png unstaged, the documented author workflow produced it reliably --
    and the workaround is the SKIP= bypass the script's own comment calls worse than
    having no gate at all.
    """
    t = _tree(tmp_path)
    _run(t)                                     # first pass writes the content stamp
    assert (t / "public" / ".blogs-ia-srchash").is_file(), (
        "a passing run must record the stamp, or the next run cannot tell a touch "
        "from an edit"
    )

    _age(t, "content/post.md")                  # mtime moves, bytes do not

    r = _run(t)
    assert "STALE" not in r.stderr, (
        "a file whose mtime moved but whose CONTENT is identical to the last verified "
        f"build is not stale. stderr:\n{r.stderr}"
    )
    assert "stamp match" in r.stdout, (
        f"the gate must say WHY it allowed a newer mtime. stdout:\n{r.stdout}"
    )


def test_a_real_edit_after_a_stamp_is_still_rejected(tmp_path: Path):
    """The stamp must not become a blanket exemption.

    This is the direction that matters: the fix above is only safe if a genuine
    content change still fails AFTER a stamp exists. Without this test the stamp
    could silently turn the staleness gate into a no-op.
    """
    t = _tree(tmp_path)
    _run(t)                                     # stamp now records the current bytes

    (t / "content" / "post.md").write_text("# genuinely different bytes\n")
    _age(t, "content/post.md")

    r = _run(t)
    assert r.returncode == 1, (
        f"a real edit must still be STALE once a stamp exists. stderr:\n{r.stderr}"
    )
    assert "STALE" in r.stderr, r.stderr
