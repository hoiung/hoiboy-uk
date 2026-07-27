"""Wiring regression guard for the frontmatter gates in pre-publish.sh and ci.yml.

This wiring broke twice in blog-priv#55 and neither break was catchable by the
test suite, because every existing test exercises the Python validator and
nothing reads the shell script or the workflow that CALL it.

What broke, both times the same shape: `pre-publish.sh` gate 4 ran the validator
bare (whole tree) and gate 4a then re-ran `--scope consulting`, a strict subset.
That made gate 4a unable to fail when gate 4 passed, and `run_check` exits on the
first failure, so when a project page WAS broken gate 4 failed and gate 4a never
printed at all. The one case it existed for was the one case it could not reach.
`ci.yml` carried the identical nesting. The fix made the two scopes DISJOINT.

`scripts/test_validate_frontmatter.py` already proves the scopes are disjoint at
the module level. It cannot see how they are wired, so a revert to nested
scoping would leave the whole suite green. These tests close that gap.

They are deliberately source-scans rather than executions: running pre-publish.sh
means a full Hugo build plus live external-URL probing, which does not belong in
the unit tier. Same trade-off, and same rationale, as
tests/test_meet_recorder_content.py.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PRE_PUBLISH = ROOT / "scripts" / "pre-publish.sh"
CI = ROOT / ".github" / "workflows" / "ci.yml"
VALIDATOR = "scripts/validate_frontmatter.py"


def _invocations(text: str) -> list[str]:
    """Every validate_frontmatter.py invocation, normalised to its scope.

    Returns e.g. ["posts", "consulting"]. A bare invocation (no --scope) is
    reported as "all", which is what the validator itself defaults to.
    """
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        # Ignore comment lines: they mention the validator constantly and are
        # not wiring. A test that counted them would fail on a doc edit.
        if stripped.startswith("#") or VALIDATOR not in stripped:
            continue
        m = re.search(r"--scope\s+(\w+)", stripped)
        out.append(m.group(1) if m else "all")
    return out


def test_pre_publish_frontmatter_gates_are_disjoint():
    scopes = _invocations(PRE_PUBLISH.read_text(encoding="utf-8"))
    assert scopes == ["posts", "consulting"], (
        f"pre-publish.sh must invoke the validator exactly twice, as disjoint "
        f"scopes, got {scopes!r}. A bare 'all' invocation alongside a scoped one "
        f"re-creates the nested-subset bug: the narrower gate becomes unable to "
        f"fail, and fail-fast means it never even runs when the wider one fails."
    )


def test_ci_frontmatter_steps_are_disjoint():
    scopes = _invocations(CI.read_text(encoding="utf-8"))
    assert scopes == ["posts", "consulting"], (
        f"ci.yml must invoke the validator exactly twice, as disjoint scopes, "
        f"got {scopes!r}. Same nested-subset bug as pre-publish.sh; the two files "
        f"drifted apart once already, when one was fixed and its twin was not."
    )


def test_ci_project_page_step_runs_even_when_the_posts_step_fails():
    """`if: always()` is load-bearing once the scopes are disjoint.

    While the steps were nested, dropping it only lost an attribution label.
    Now that they cover different trees, dropping it loses real coverage: a
    posts failure would skip the project-page check entirely.
    """
    text = CI.read_text(encoding="utf-8")
    idx = text.find("--scope consulting")
    assert idx != -1, "ci.yml no longer runs the validator with --scope consulting"
    # Look back to the start of this step and assert the guard is inside it.
    step_start = text.rfind("- name:", 0, idx)
    assert step_start != -1
    assert "if: always()" in text[step_start:idx], (
        "the --scope consulting step lost `if: always()`. With disjoint scopes "
        "GHA would skip it whenever the posts step failed, silently dropping "
        "project-page coverage on exactly the runs that need it."
    )


def test_the_two_scopes_together_cover_every_tree_the_validator_knows_about():
    """Disjoint is only safe if the union is still total.

    If someone adds a third content root to the validator, the two wired scopes
    stop covering the tree and this test says so, rather than the gap being
    found by a page shipping without a description.
    """
    import argparse
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import validate_frontmatter as vf

    # Read the declared --scope choices from the parser itself rather than
    # restating them here, so this tracks the real CLI instead of a copy that
    # can drift away from it.
    seen: set[str] = set()
    original = argparse.ArgumentParser.add_argument

    def spy(self, *args, **kwargs):
        if args and args[0] == "--scope":
            seen.update(kwargs.get("choices", ()))
        return original(self, *args, **kwargs)

    argparse.ArgumentParser.add_argument = spy
    try:
        with pytest.raises(SystemExit):
            vf.main(["--scope", "__not_a_scope__"])
    finally:
        argparse.ArgumentParser.add_argument = original

    assert seen == {"all", "posts", "consulting"}, (
        f"validate_frontmatter.py's --scope choices are now {sorted(seen)!r}. "
        f"pre-publish.sh and ci.yml wire 'posts' + 'consulting' as a total cover "
        f"of the tree; a new scope means that union is no longer total, and the "
        f"wiring has to be updated alongside it."
    )

    # The choices assertion above tracks what the CLI DECLARES. On its own that
    # is not enough: a third content root walked under `--scope all` without a
    # new CLI choice would leave it green while the wired posts+consulting pair
    # silently stopped covering the tree (Ralph round 16 seeded exactly that and
    # the test still passed). So assert on the roots main() passes to check_tree.
    #
    # KNOWN BOUNDARY (Ralph round 17): this spies on check_tree, so it sees a
    # root added the way roots are actually added - another check_tree call -
    # and NOT one walked by an inline loop that bypasses check_tree entirely.
    # A mutant of that shape passes all four wiring tests. Closing that would
    # need a filesystem-level spy (rglob/os.walk), which buys little: every
    # root in this validator goes through check_tree, and an inline-walk root
    # would be a deliberate rewrite rather than the incremental addition this
    # guards. The limit is recorded here so a future reader does not read this
    # test as broader than it is.
    walked: list = []
    original_check_tree = vf.check_tree

    def spy_check_tree(root, *args, **kwargs):
        walked.append(root)
        return [], 1  # no failures, non-zero count (the vacuous-walk guard)

    vf.check_tree = spy_check_tree
    try:
        vf.main(["--scope", "all"])
    finally:
        vf.check_tree = original_check_tree

    assert set(walked) == {vf.POSTS, vf.CONSULTING}, (
        f"`--scope all` now walks {sorted(str(p) for p in walked)!r}, not just "
        f"the posts and consulting trees. pre-publish.sh and ci.yml wire exactly "
        f"'posts' + 'consulting'; any other root is gated by nothing, and every "
        f"page under it passes by omission rather than by compliance."
    )


TEST_PATH = re.compile(r"(?:scripts|tests)/test_[a-z0-9_]+\.py")


def _pytest_covered(text: str) -> set[str]:
    """Every test file ci.yml actually RUNS UNDER PYTEST, not merely mentions.

    The distinction is the whole point. Several gates in scripts/ are BOTH a CLI
    and a pytest module, and ci.yml invokes some of them both ways -- once as
    `python3 scripts/x.py --flag` and once as `python3 -m pytest scripts/x.py`.
    A CLI run executes no test functions, so counting it as coverage says a file
    is run when nothing runs its tests.

    Backslash continuations are rejoined first: ci.yml lists long pytest runs
    across several lines, and judging each physical line on its own would class
    every continuation line as a non-pytest invocation.
    """
    lines = [l for l in text.splitlines() if not l.strip().startswith("#")]
    logical: list[str] = []
    buf = ""
    for line in lines:
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
            continue
        logical.append(buf + stripped)
        buf = ""
    if buf:
        logical.append(buf)
    covered: set[str] = set()
    for command in logical:
        if "pytest" in command:
            covered.update(TEST_PATH.findall(command))
    return covered


def test_every_test_file_is_actually_run_by_pytest_in_ci():
    """No test file can exist without CI RUNNING it (blog-priv#62, Ralph Tier 3).

    CI invokes pytest through EXPLICIT FILE LISTS -- there is no `testpaths` config
    and no directory-wide collection -- so a test file nobody lists never runs. It
    still passes locally, which is worse than having no test at all: the local suite
    count reports coverage that CI does not enforce.

    This repo has now been bitten by that three times. `tests/test_gate_wiring.py`
    itself shipped unlisted in blog-priv#55 (see the comment above the frontmatter
    step in ci.yml), and blog-priv#62 found `scripts/test_gen_card.py` unlisted while
    that same issue was rewriting its subject under test. Both were caught by an
    audit rather than by the suite, because no assertion existed to catch them.

    The third was this guard's own blind spot, and it is why the check now asks
    HOW a file is invoked rather than only WHETHER it is named. It used to match
    the filename anywhere in a non-comment line. `scripts/test_404.py` is a CLI
    gate wearing a `test_` prefix that ci.yml already ran as
    `python3 scripts/test_404.py --built public`, so when blog-priv#64 added 12
    pytest tests to it plus a `python3 -m pytest scripts/test_404.py -q` step, the
    CLI line alone satisfied this assertion. Deleting the pytest step left the
    guard green and the 12 tests silently unrun -- the very defect the guard
    exists to prevent, one level up the wiring stack, in the one file whose name
    collides with itself. Proven by mutation, both directions: deleting that step
    used to give `5 passed` and now fails, while deleting a step for a file with
    no CLI sibling always failed correctly.

    COMMENT LINES ARE STRIPPED FIRST, for the same reason `_invocations()` above
    strips them: ci.yml discusses its own test files constantly, and a file named
    only in prose is not wired. Counting a comment as wiring would let a file whose
    real invocation was deleted -- but whose explanatory comment survived -- pass
    this check, which is precisely the failure mode the test exists to catch. Three
    of the current matches for this very file are comment-only.
    """
    covered = _pytest_covered(CI.read_text(encoding="utf-8"))
    on_disk = {
        f"{d}/{p.name}"
        for d in ("scripts", "tests")
        for p in sorted((ROOT / d).glob("test_*.py"))
    }
    # A glob that returned nothing would make the subtraction below empty and the
    # assertion vacuous, which is the same class of silent pass being guarded against.
    assert on_disk, "found no test_*.py under scripts/ or tests/ - the glob is wrong"
    # Likewise, a rejoining bug that produced no pytest commands at all would make
    # every file look unlisted rather than silently pass, but assert it explicitly
    # so the failure names the real cause instead of listing all 33 files.
    assert covered, (
        "no pytest invocation found in ci.yml at all - _pytest_covered is broken, "
        "not the workflow."
    )
    unlisted = sorted(on_disk - covered)
    assert not unlisted, (
        f"{len(unlisted)} test file(s) exist but are run by no ci.yml PYTEST "
        f"invocation, so CI never runs their tests: {unlisted}. Add each to a "
        f"pytest step (built-tree tests belong after the Hugo build step, "
        f"source-only tests before it). Being named on a bare `python3 <file>` "
        f"CLI line does NOT count: that runs the file, not its test functions."
    )
