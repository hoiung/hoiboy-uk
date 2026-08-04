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

import json
import re
from pathlib import Path

import yaml  # already declared: requirements-dev.txt

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

# Shell operators that end one command and begin another. A single `run:` line
# can chain several, and only the pytest ones run test functions.
SHELL_OPERATORS = ("&&", "||", ";", "|")


def _strip_comment(line: str) -> str:
    """Drop a trailing shell comment, leaving a `#` that sits inside quotes.

    Whole-comment lines were already handled by a `startswith("#")` test, which
    is not the same thing: a comment can follow real code on the same line, and
    that is where ci.yml discusses its own steps. `ci.yml:257` is why this is
    quote-aware rather than a plain `split("#")` -- it runs `grep -v '^#'`, and
    cutting at that `#` would silently truncate a real command.
    """
    quote: str | None = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i]
    return line


def _split_commands(line: str) -> list[str]:
    """Split one shell line into commands, ignoring operators inside quotes.

    Quote-awareness is not decoration. Round 4 made comment-stripping
    quote-aware and left this half naive, so a quoted `;` inside an `echo`
    string split the line and handed the fragment after it a pytest credit it
    had not earned (Ralph round 5).
    """
    parts: list[str] = []
    buf = ""
    quote: str | None = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            buf += ch
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            buf += ch
            i += 1
            continue
        for op in SHELL_OPERATORS:
            if line.startswith(op, i):
                parts.append(buf)
                buf = ""
                i += len(op)
                break
        else:
            buf += ch
            i += 1
    parts.append(buf)
    return parts


def _unquoted(segment: str) -> str:
    """The segment with quoted spans blanked out.

    A filename inside a string literal is text the shell passes to `echo`, not a
    path pytest collects. Blanking the spans means neither the `pytest` token nor
    a test path can be claimed from prose that merely happens to sit on a
    command line.
    """
    out = []
    quote: str | None = None
    for ch in segment:
        if quote:
            if ch == quote:
                quote = None
            out.append(" ")
            continue
        if ch in "'\"":
            quote = ch
            out.append(" ")
            continue
        out.append(ch)
    return "".join(out)


def _pytest_covered(text: str) -> set[str]:
    """Every test file ci.yml actually RUNS UNDER PYTEST, not merely mentions.

    The distinction is the whole point. Several gates in scripts/ are BOTH a CLI
    and a pytest module, and ci.yml invokes some of them both ways -- once as
    `python3 scripts/x.py --flag` and once as `python3 -m pytest scripts/x.py`.
    A CLI run executes no test functions, so counting it as coverage says a file
    is run when nothing runs its tests.

    Three narrowings, each closing a way a filename can appear near a pytest
    command without pytest running it. Ralph round 4 found the first two by
    building them, after round 3's fix caught only the crudest form:

      1. TRAILING COMMENTS. Stripping whole-comment lines is not enough. A step
         rewritten to `run: python3 -m pytest scripts/other.py -q  # test_x.py
         used to run here` deleted the real invocation while leaving the name on
         a pytest line, and scored as covered.
      2. CHAINED COMMANDS. `python3 -m pytest a.py && python3 b.py --flag` is
         one line running one pytest command and one CLI command; crediting the
         whole line credits `b.py` for a run that never collects it.
      3. POSITION. Even inside a pytest segment, only text AFTER the `pytest`
         token is an argument to it.

    Backslash continuations are rejoined after comment-stripping and before
    splitting: ci.yml lists long pytest runs across several lines, and judging
    each physical line alone would class every continuation as non-pytest.
    """
    logical: list[str] = []
    buf = ""
    for raw in text.splitlines():
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        logical.append(buf + line)
        buf = ""
    if buf:
        logical.append(buf)

    covered: set[str] = set()
    for command in logical:
        # 4. SWALLOWED FAILURE. `python3 -m pytest x.py || true` runs the tests
        #    and then throws the verdict away: the step is green whatever they
        #    say, so the file is not GATED by CI even though it is run by it.
        #    An `||` BEFORE the pytest token is the opposite case - pytest is the
        #    fallback and its failure still fails the step - so position decides.
        bare_command = _unquoted(command)
        swallowed = False
        if "pytest" in bare_command and "||" in bare_command:
            swallowed = bare_command.index("||") > bare_command.index("pytest")
        if swallowed:
            continue
        for segment in _split_commands(command):
            bare = _unquoted(segment)
            if "pytest" not in bare:
                continue
            covered.update(TEST_PATH.findall(bare.split("pytest", 1)[1]))
    return covered


# `if:` values that still let the step run AND still let it fail the build.
# `always()` runs the step even after an earlier failure, and it can itself go
# red, so it is real coverage - this file's own `--scope consulting` test exists
# because that guard is load-bearing. Anything outside this set cannot be
# evaluated statically and is refused, which fails LOUD rather than crediting a
# step that may never execute.
_RUNS_AND_CAN_FAIL = frozenset({"true", "always()", "success()"})


def _neutered(node: object) -> str | None:
    """Why this job/step cannot turn CI red, or None if it can.

    A gate that runs but cannot fail the build is not a gate. `if:` accepts
    arbitrary GitHub expressions, which cannot be evaluated here, so anything
    other than a literal true is treated as NOT-credited: fail closed, and say
    so, rather than guess at an expression's runtime value.
    """
    if not isinstance(node, dict):
        return None
    if node.get("continue-on-error") is True:
        return "continue-on-error: true"
    condition = node.get("if")
    if condition is not None and str(condition).strip().lower() not in _RUNS_AND_CAN_FAIL:
        return f"if: {condition}"
    return None


def _workflow_pytest_covered(workflow_text: str) -> set[str]:
    """Every test file the WORKFLOW both runs under pytest AND is gated by.

    `_pytest_covered` above answers a shell question and is deliberately kept
    that way, with its own unit test and three pinned mutations. This answers
    the structural question it cannot see: a step whose job is `if: false`, or
    which carries `continue-on-error: true`, runs pytest and can never turn CI
    red. All three escapes credited before this existed, which made the guard
    fail OPEN in exactly the direction it was written to prevent.

    Rounds 3, 4 and 5 each hardened the LEXING of the command and none asked
    whether the credited command can actually fail the build.
    """
    document = yaml.safe_load(workflow_text)
    if not isinstance(document, dict):
        return set()
    covered: set[str] = set()
    for job in (document.get("jobs") or {}).values():
        if not isinstance(job, dict) or _neutered(job):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict) or _neutered(step):
                continue
            run = step.get("run")
            if isinstance(run, str):
                covered |= _pytest_covered(run)
    return covered


def test_pytest_covered_credits_only_real_pytest_arguments():
    """Unit-test the guard's own helper, because the guard is the last line.

    Every case below is a way a filename appears without pytest running it, and
    each one scored as covered at some point in this issue's Ralph rounds. A
    guard whose own parser is untested is exactly the shape this file exists to
    stop, one level further down.
    """
    real = "        run: python3 -m pytest scripts/test_a.py scripts/test_b.py -q"
    assert _pytest_covered(real) == {"scripts/test_a.py", "scripts/test_b.py"}

    # A bare CLI run is not a pytest run, however the file is named.
    assert _pytest_covered("        run: python3 scripts/test_a.py --built public") == set()

    # A whole-line comment is prose.
    assert _pytest_covered("        # python3 -m pytest scripts/test_a.py -q") == set()

    # A TRAILING comment after real code is also prose (round 4, finding 1).
    trailing = ("        run: python3 -m pytest scripts/test_b.py -q  "
                "# scripts/test_a.py used to run here")
    assert _pytest_covered(trailing) == {"scripts/test_b.py"}

    # Chaining does not launder a CLI invocation into a pytest one.
    for joiner in ("&&", ";", "|"):
        chained = (f"        run: python3 -m pytest scripts/test_b.py -q {joiner} "
                   f"python3 scripts/test_a.py --flag")
        assert _pytest_covered(chained) == {"scripts/test_b.py"}, joiner

    # A name BEFORE the pytest token is not an argument to it.
    assert _pytest_covered(
        "        run: python3 scripts/test_a.py && python3 -m pytest scripts/test_b.py"
    ) == {"scripts/test_b.py"}

    # Continuations still rejoin, so a multi-line pytest list is credited whole.
    multi = ("        run: python3 -m pytest scripts/test_a.py \\\n"
             "            scripts/test_b.py -q")
    assert _pytest_covered(multi) == {"scripts/test_a.py", "scripts/test_b.py"}

    # A quoted '#' is not a comment; cutting there would truncate a real command
    # (ci.yml:257 runs `grep -v '^#'`).
    quoted = "        run: grep -v '^#' f && python3 -m pytest scripts/test_a.py -q"
    assert _pytest_covered(quoted) == {"scripts/test_a.py"}

    # A filename inside a STRING is prose the shell hands to echo, and a quoted
    # operator must not split the line (round 5, finding 2). Both halves of this
    # one case: the echo mentions pytest AND a filename AND carries a ';'.
    laundered = ('        run: echo "reminder: pytest scripts/test_a.py -q covers '
                 'this; keep it wired"; python3 scripts/test_a.py --built public')
    assert _pytest_covered(laundered) == set()

    # The same shape must not suppress a REAL invocation elsewhere on the line.
    mixed = ('        run: echo "see scripts/test_a.py; note" && '
             'python3 -m pytest scripts/test_b.py -q')
    assert _pytest_covered(mixed) == {"scripts/test_b.py"}


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
    covered = _workflow_pytest_covered(CI.read_text(encoding="utf-8"))
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


def test_a_step_that_cannot_fail_the_build_is_not_coverage():
    """A gate that runs but can never turn CI red is not a gate.

    All four of these credited before `_workflow_pytest_covered` existed, so the
    guard failed OPEN in the exact direction it was written to prevent: a test
    file could be neutered in ci.yml and the wiring test stayed green. Rounds 3,
    4 and 5 each hardened the LEXING of the command; none asked whether the
    credited command can actually fail the build.
    """
    def wf(job_extra="", step_extra="", command="python3 -m pytest scripts/test_a.py -q"):
        return (f"jobs:\n  ci:\n{job_extra}    steps:\n      - name: run\n"
                f"{step_extra}        run: {command}\n")

    # Control: an ordinary step is credited.
    assert _workflow_pytest_covered(wf()) == {"scripts/test_a.py"}

    # A job or step that never runs is not coverage.
    assert _workflow_pytest_covered(wf(job_extra="    if: false\n")) == set()
    assert _workflow_pytest_covered(wf(step_extra="        if: false\n")) == set()
    assert _workflow_pytest_covered(
        wf(step_extra="        if: github.event_name == 'schedule'\n")) == set()

    # A step whose failure is ignored runs the tests and discards the verdict.
    assert _workflow_pytest_covered(wf(job_extra="    continue-on-error: true\n")) == set()
    assert _workflow_pytest_covered(wf(step_extra="        continue-on-error: true\n")) == set()

    # ...as does swallowing the exit code in the shell.
    assert _workflow_pytest_covered(
        wf(command="python3 -m pytest scripts/test_a.py -q || true")) == set()

    # But `||` BEFORE pytest is the opposite case: pytest is the fallback and
    # its failure still fails the step, so it stays credited.
    assert _workflow_pytest_covered(
        wf(command="test -f x || python3 -m pytest scripts/test_a.py -q")
    ) == {"scripts/test_a.py"}

    # `if: always()` runs the step MORE, and it can still go red. Real coverage.
    assert _workflow_pytest_covered(
        wf(step_extra="        if: always()\n")) == {"scripts/test_a.py"}


def test_neutering_a_real_ci_step_is_caught_by_the_wiring_guard():
    """Mutation, against the REAL ci.yml rather than a synthetic fixture.

    The guard's value is entirely in what it does to the file that ships. Adding
    `continue-on-error: true` to a real pytest step must drop that file's
    coverage, which is what makes the guard's own assertion fail.
    """
    real = CI.read_text(encoding="utf-8")
    baseline = _workflow_pytest_covered(real)
    assert "scripts/test_404.py" in baseline

    marker = "python3 -m pytest scripts/test_404.py -q"
    assert marker in real, "ci.yml no longer runs test_404.py the expected way"
    line_start = real.rfind("\n", 0, real.index(marker)) + 1
    indent = " " * (len(real[line_start:]) - len(real[line_start:].lstrip()))
    mutated = real.replace(
        real[line_start:real.index(marker) + len(marker)],
        f"{indent}continue-on-error: true\n{indent}run: {marker}", 1)

    assert "scripts/test_404.py" not in _workflow_pytest_covered(mutated), (
        "neutering a real pytest step with continue-on-error still credited it. "
        "The guard is measuring the text and not the wiring."
    )

    # And drive the GUARD, not just the helper. Asserting on the helper proves
    # the helper works and says nothing about whether the guard calls it: the
    # first version of this test did exactly that, and swapping the guard back
    # to the shell-only credit left all eight tests green. Point the module's CI
    # at the neutered workflow and require the guard itself to go red.
    import sys as _sys
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        neutered = Path(tmp) / "ci.yml"
        neutered.write_text(mutated, encoding="utf-8")
        module = _sys.modules[__name__]
        original = module.CI
        module.CI = neutered
        try:
            with pytest.raises(AssertionError):
                test_every_test_file_is_actually_run_by_pytest_in_ci()
        finally:
            module.CI = original


# ---------------------------------------------------------------------------
# The same invariant, for the JS half of the suite (#56 AC 4.2).
#
# `test_every_test_file_is_actually_run_by_pytest_in_ci` above closes the hole
# for Python only. The JS suite has the identical hole and no guard at all:
# `package.json` names its test files EXPLICITLY, exactly the way ci.yml names
# its pytest files, so a `*.test.js` omitted from that line never runs while the
# suite reports green. That is the same defect one runtime over, and #56 would
# have walked straight into it -- `tests/subscribe.test.js` is the third JS test
# file in the repo and the first added since the script was written.
#
# Two assertions, because either alone fails open:
#   1. every JS test file on disk is named by `npm test`, and
#   2. ci.yml actually RUNS `npm test` in a step that can turn the build red.
# Without (2), (1) proves only that a file is listed in a script nobody invokes.
# ---------------------------------------------------------------------------

PACKAGE_JSON = ROOT / "package.json"

# Where JS test files live. Both directories are already in use.
JS_TEST_DIRS = ("tests", "static/js")

JS_TEST_PATH = re.compile(r"(?:tests|static/js)/[a-z0-9_.-]+\.test\.js")


def _node_run_files(command: str) -> set[str]:
    """Every *.test.js the node runner is actually handed by this command.

    Mirrors `_pytest_covered`'s three narrowings rather than matching the
    filename anywhere: quoted spans are blanked so a name inside an `echo`
    string is not credited, chained commands are split so a sibling command
    cannot lend its credit, and only text AFTER the `node` token counts as an
    argument to it.
    """
    bare_command = _unquoted(command)
    # A swallowed failure runs the tests and discards the verdict. An `||` BEFORE
    # the node token is the opposite case, so position decides -- same rule, and
    # same rationale, as the pytest half.
    if "node" in bare_command and "||" in bare_command:
        if bare_command.index("||") > bare_command.index("node"):
            return set()

    covered: set[str] = set()
    for segment in _split_commands(command):
        bare = _unquoted(segment)
        if not re.search(r"(?:^|\s|/)node(?:\s|$)", bare):
            continue
        covered.update(JS_TEST_PATH.findall(bare.split("node", 1)[1]))
    return covered


def _npm_test_files(package_json_text: str) -> set[str]:
    """Every JS test file `npm test` runs, parsed from the script it shells."""
    document = json.loads(package_json_text)
    script = (document.get("scripts") or {}).get("test")
    if not isinstance(script, str):
        return set()
    return _node_run_files(_strip_comment(script))


def _npm_test_is_gated_in_ci(workflow_text: str) -> bool:
    """True when ci.yml runs `npm test` somewhere it can fail the build.

    Reuses `_neutered` so a step parked behind `if: false` or waved through with
    `continue-on-error: true` is not counted, which is the same fail-open shape
    `test_a_step_that_cannot_fail_the_build_is_not_coverage` pins for pytest.
    """
    document = yaml.safe_load(workflow_text)
    if not isinstance(document, dict):
        return False
    for job in (document.get("jobs") or {}).values():
        if not isinstance(job, dict) or _neutered(job):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict) or _neutered(step):
                continue
            run = step.get("run")
            if not isinstance(run, str):
                continue
            for line in run.splitlines():
                stripped = _strip_comment(line)
                bare_line = _unquoted(stripped)
                if "npm" in bare_line and "||" in bare_line:
                    if bare_line.index("||") > bare_line.index("npm"):
                        continue
                for segment in _split_commands(stripped):
                    tokens = _unquoted(segment).split()
                    if len(tokens) >= 2 and tokens[0] == "npm" and tokens[1] == "test":
                        return True
    return False


def test_every_js_test_file_is_actually_run_by_npm_test():
    """No JS test file can exist without `npm test` RUNNING it (#56 AC 4.2).

    `package.json`'s test script names its files explicitly, so this is the same
    failure mode the pytest guard above exists to stop: a file that passes
    locally when someone runs it by hand, and that CI never executes. It is
    worse than having no test, because the file count implies coverage the
    pipeline does not enforce.
    """
    on_disk = {
        f"{directory}/{path.name}"
        for directory in JS_TEST_DIRS
        for path in sorted((ROOT / directory).glob("*.test.js"))
    }
    # A glob that matched nothing would make the subtraction below empty and this
    # assertion vacuous, which is the silent pass being guarded against.
    assert on_disk, "found no *.test.js under tests/ or static/js/ - the glob is wrong"

    covered = _npm_test_files(PACKAGE_JSON.read_text(encoding="utf-8"))
    assert covered, (
        "package.json's test script runs no JS test file at all - the script was "
        "emptied or rewritten, not merely missing one entry."
    )

    unlisted = sorted(on_disk - covered)
    assert not unlisted, (
        f"{len(unlisted)} JS test file(s) exist but are named by no `npm test` "
        f"invocation, so neither CI nor a local `npm test` runs them: {unlisted}. "
        f"Add each to the `test` script in package.json."
    )


def test_ci_runs_the_js_suite_at_all():
    """Wiring a file into `npm test` is worthless if CI never runs `npm test`.

    This is the level-up check the pytest guard learned the hard way: asking
    whether a file is NAMED, without asking how the naming is invoked, credits a
    gate that cannot fail. Here the whole JS suite is one step, so deleting it
    would silently drop all three files at once.
    """
    assert _npm_test_is_gated_in_ci(CI.read_text(encoding="utf-8")), (
        "ci.yml has no `npm test` step that can fail the build, so every JS test "
        "file is unrun in CI however faithfully package.json lists it."
    )


def test_node_run_files_credits_only_real_runner_arguments():
    """Unit-test the JS guard's own parser, for the reason the pytest one is.

    Each case is a way a filename appears without the runner collecting it.
    """
    real = "node --test static/js/a.test.js tests/b.test.js"
    assert _node_run_files(real) == {"static/js/a.test.js", "tests/b.test.js"}

    # A name inside a string is prose, not an argument.
    assert _node_run_files('echo "node tests/b.test.js"') == set()

    # A sibling command cannot lend its credit across a chain.
    assert _node_run_files("node --test tests/b.test.js && echo tests/c.test.js") == {
        "tests/b.test.js"
    }

    # A name BEFORE the node token is not an argument to it.
    assert _node_run_files("ls tests/a.test.js && node --test tests/b.test.js") == {
        "tests/b.test.js"
    }

    # Swallowing the exit code runs the tests and discards the verdict.
    assert _node_run_files("node --test tests/b.test.js || true") == set()

    # ...but `||` BEFORE node keeps node as the fallback whose failure still fails.
    assert _node_run_files("test -f x || node --test tests/b.test.js") == {
        "tests/b.test.js"
    }


def test_dropping_a_js_test_file_from_package_json_is_caught():
    """Mutation, driving the GUARD rather than only its helper.

    Asserting on `_npm_test_files` alone would prove the parser works and say
    nothing about whether the guard calls it. The pytest half of this file was
    written that way first and stayed green when the guard was swapped back to a
    weaker check, so this points the module's PACKAGE_JSON at a mutated copy and
    requires the guard itself to go red.
    """
    import sys as _sys
    import tempfile

    real = PACKAGE_JSON.read_text(encoding="utf-8")
    document = json.loads(real)
    script = document["scripts"]["test"]

    victim = "tests/subscribe.test.js"
    assert victim in script, "package.json no longer runs the file this mutation drops"
    document["scripts"]["test"] = script.replace(f" {victim}", "")

    module = _sys.modules[__name__]
    with tempfile.TemporaryDirectory() as tmp:
        mutated = Path(tmp) / "package.json"
        mutated.write_text(json.dumps(document, indent=2), encoding="utf-8")
        original = module.PACKAGE_JSON
        module.PACKAGE_JSON = mutated
        try:
            with pytest.raises(AssertionError):
                test_every_js_test_file_is_actually_run_by_npm_test()
        finally:
            module.PACKAGE_JSON = original


def test_neutering_the_npm_test_step_is_caught_by_the_js_wiring_guard():
    """The same mutation one level up: a step that cannot fail is not coverage."""
    import sys as _sys
    import tempfile

    real = CI.read_text(encoding="utf-8")
    assert _npm_test_is_gated_in_ci(real), "ci.yml does not run npm test as expected"

    marker = "run: npm test"
    assert marker in real, "ci.yml no longer runs the JS suite the expected way"
    line_start = real.rfind("\n", 0, real.index(marker)) + 1
    indent = " " * (len(real[line_start:]) - len(real[line_start:].lstrip()))
    mutated = real.replace(
        real[line_start:real.index(marker) + len(marker)],
        f"{indent}continue-on-error: true\n{indent}{marker}", 1)

    assert not _npm_test_is_gated_in_ci(mutated), (
        "a neutered npm test step still counted as coverage; the guard is "
        "measuring the text and not the wiring."
    )

    module = _sys.modules[__name__]
    with tempfile.TemporaryDirectory() as tmp:
        neutered = Path(tmp) / "ci.yml"
        neutered.write_text(mutated, encoding="utf-8")
        original = module.CI
        module.CI = neutered
        try:
            with pytest.raises(AssertionError):
                test_ci_runs_the_js_suite_at_all()
        finally:
            module.CI = original


# --- Built-output secret scan (hoiboy-uk#56, escalation 2 defect 7) ----------
#
# The source scan cannot see the rendered tree. That was measured, not assumed:
# planting an address in `public/` and re-running the source scan prints
# "PASS: No secrets detected". So a leak reachable only through a template, a
# data file, a shortcode or a partial had no gate anywhere between a clean
# source file and the HTML actually served.
#
# Two properties are pinned here, because either one alone is satisfiable by a
# step that protects nothing: the scan must run against the BUILT path, and it
# must carry --include-ignored. Without the flag `public/` (gitignored, being a
# build artefact) is filtered to zero files, and the scanner's coverage floor
# exits 2 -- loud, but it means the tree is never actually scanned.

BUILD_SCAN_PATH = "public"
BUILD_SCAN_FLAG = "--include-ignored"
SECRET_SCANNER = "scripts/check-public-repo-secrets.py"


def _build_output_scan_is_gated_in_ci(workflow_text: str) -> bool:
    """True when ci.yml scans the BUILT tree somewhere it can fail the build.

    Reuses `_neutered` so a step parked behind `if: false` or waved through
    with `continue-on-error: true` does not count as coverage -- the same
    fail-open shape the npm-test guard above pins.
    """
    document = yaml.safe_load(workflow_text)
    if not isinstance(document, dict):
        return False
    for job in (document.get("jobs") or {}).values():
        if not isinstance(job, dict) or _neutered(job):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict) or _neutered(step):
                continue
            run = step.get("run")
            if not isinstance(run, str):
                continue
            for line in run.splitlines():
                bare = _unquoted(_strip_comment(line))
                if SECRET_SCANNER not in bare:
                    continue
                fields = bare.split()
                # The path argument, not a substring: `--allowlist public.txt`
                # must not be mistaken for scanning `public`.
                if BUILD_SCAN_PATH in fields and BUILD_SCAN_FLAG in fields:
                    return True
    return False


def test_ci_scans_the_built_output_for_secrets():
    assert _build_output_scan_is_gated_in_ci(CI.read_text(encoding="utf-8")), (
        f"ci.yml no longer runs {SECRET_SCANNER} against `{BUILD_SCAN_PATH}` "
        f"with {BUILD_SCAN_FLAG} in a step that can fail the build. The source "
        f"scan does NOT cover the rendered tree -- a planted address in "
        f"public/ leaves the source scan reporting PASS -- so dropping this "
        f"step reopens the gap with CI still green."
    )


def test_the_built_output_scan_must_carry_include_ignored():
    """Without the flag the step scans nothing, so its presence is not coverage.

    `public/` is gitignored. The scanner drops git-ignored files by default, so
    the step would collect zero files. Pinning only "the step exists" would
    accept exactly that.
    """
    real = CI.read_text(encoding="utf-8")
    assert _build_output_scan_is_gated_in_ci(real)

    mutated = real.replace(f" {BUILD_SCAN_PATH} {BUILD_SCAN_FLAG}", f" {BUILD_SCAN_PATH}")
    assert mutated != real, "the expected invocation shape was not found to mutate"
    assert not _build_output_scan_is_gated_in_ci(mutated), (
        "a built-output scan WITHOUT --include-ignored still counted as "
        "coverage; the guard is matching the path and ignoring whether the "
        "scan can see any file at all."
    )


def test_a_neutered_built_output_scan_is_not_coverage():
    """Prove the guard measures wiring, not text (mirrors the npm-test guard)."""
    real = CI.read_text(encoding="utf-8")
    marker = f"run: python3 {SECRET_SCANNER} {BUILD_SCAN_PATH} {BUILD_SCAN_FLAG}"
    assert marker in real, "ci.yml no longer runs the built-output scan as expected"

    line_start = real.rfind("\n", 0, real.index(marker)) + 1
    indent = " " * (len(real[line_start:]) - len(real[line_start:].lstrip()))
    mutated = real.replace(
        real[line_start:real.index(marker) + len(marker)],
        f"{indent}continue-on-error: true\n{indent}{marker}", 1)

    assert not _build_output_scan_is_gated_in_ci(mutated), (
        "a step that cannot fail the build still counted as coverage."
    )
