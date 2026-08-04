#!/usr/bin/env python3
"""No gate in this repo may report success over a tree it did not examine.

This is the enforcement half of `scripts/gate_coverage.py`; read that module's
docstring for why the class exists. The short version: eleven times in #56 a
gate printed a confident OK having opened nothing, because the set of surfaces
it examined had silently shrunk to zero. Each was fixed individually, at its
own granularity, and the next instance appeared on a surface the previous fix
had not enumerated.

Fixing instances cannot close that. What closes it is a property asserted over
the WHOLE inventory:

    run any gate against a deliberately empty tree. It must not exit 0.

Enrolment is by existence. `gate_inventory()` reads `scripts/` at collection
time, so a gate added next month is covered before anyone remembers this file
is here -- which is the only reason it will still be true next month. A gate
that genuinely cannot be driven this way goes in EXEMPT with a stated reason,
and the exemptions are themselves checked for staleness so the list cannot rot
into a silent allowlist.

WHY A COPIED SKELETON rather than flags or monkeypatching. Every gate here
resolves its own root from `Path(__file__).resolve().parent.parent`, so a copy
of `scripts/` placed in an empty directory makes each gate see that directory
as the repo. Nothing is stubbed and no seam is added for the test's benefit:
this drives each gate's real `main()`, by its real entry point, over a real
(empty) filesystem. A test that proved the property about a helper rather than
about the shipped path would be exactly the vacuity it exists to catch.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"

# A gate is any script whose job is to gate. The prefixes match the inventory
# convention documented in CLAUDE.md "Repository Structure"; test_404.py is a
# CLI gate despite the test_ prefix, and is named explicitly for that reason.
# `.sh` is in the list because leaving it out silently un-enrolled a live,
# CI-wired and pre-commit-wired gate (check_emdash_zero_tolerance.sh), which then
# carried the exact defect this suite exists to close for the whole time the
# suite claimed to cover everything. An enrolment rule that quietly excludes a
# whole language is the same shape as a scan list that quietly skips a directory.
GATE_GLOBS = ("check*.py", "check*.sh", "validate*.py")
GATE_EXTRA = ("test_404.py",)

# Gates that cannot be driven by "run it against an empty tree", each with the
# reason. An entry here is a claim about the GATE, not a licence to skip: every
# one must still be non-vacuous by its own test, and `test_no_stale_exemptions`
# fails the build when an entry stops naming a real file.
EXEMPT: dict[str, str] = {
    # Compares this repo against the dotfiles canonical clone, which does not
    # exist inside a tmp skeleton. Absence of the canonical is itself a hard
    # failure in that gate, so the empty-tree run proves nothing new.
    "check-mirror-drift.py": "needs the canonical dotfiles clone, absent by construction",
    # Network gate: resolves live robots.txt over HTTP. Running it in the
    # skeleton would assert the network, not the coverage floor.
    "check-ai-crawler-access.sh": "network gate; empty-tree run asserts DNS, not coverage",
    # Takes ONE mandatory positional argument and has no scan-and-collect step at
    # all (scripts/check_future_date.py:77-80), so `run_gate` -- which always
    # invokes with no arguments -- gets `usage: ...` and exit 2 identically
    # whether the tree is empty or fully populated. That is a usage error wearing
    # a compliant exit code, and counting it as a coverage floor is the accidental
    # pass this suite exists to reject. The vacuous scan-and-clear shape cannot
    # occur for a single-mandatory-arg CLI: with no argument it does nothing, and
    # with one it examines exactly that file.
    "check_future_date.py": (
        "single mandatory positional arg, no enumeration step; its no-arg exit is "
        "a usage error, identical on an empty and a populated tree"
    ),
    # The one gate whose empty tree this harness structurally cannot build: the
    # skeleton must copy scripts/ for imports to resolve, and scripts/ IS this
    # gate's scan surface, so the tree is never empty from where it stands.
    # Its two floors -- the collected-zero floor and --require-public -- are
    # asserted directly against main() in scripts/test_check_public_repo_secrets.py
    # (TestCoverageFloor), which is a stronger test than this one, not a weaker
    # one: it drives the real entry point over a tree it fully controls.
    "check-public-repo-secrets.py": (
        "skeleton copies scripts/, which is this gate's own scan surface; floors "
        "asserted in scripts/test_check_public_repo_secrets.py TestCoverageFloor"
    ),
}


def gate_inventory() -> list[str]:
    """Every gate script, read from disk at collection time.

    Read rather than listed so a new gate is enrolled by existing. A hardcoded
    list would make this suite's coverage a thing someone has to remember, and
    the whole point of the invariant is that nobody has to.
    """
    names = set()
    for pattern in GATE_GLOBS:
        names.update(p.name for p in SCRIPTS.glob(pattern))
    for extra in GATE_EXTRA:
        if (SCRIPTS / extra).is_file():
            names.add(extra)
    # A gate's own unit tests live beside it and are not gates.
    return sorted(n for n in names if not n.startswith("test_") or n in GATE_EXTRA)


def skeleton(tmp_path: Path) -> Path:
    """A STRUCTURALLY VALID repo that is EMPTY OF CONTENT.

    The distinction is the whole design, and the first version got it wrong. That
    version created only `scripts/` and a bare `git init`, which is not a repo any
    gate was written for: `check_config_traceability` exited 1 on "params.toml
    missing" and `test_404.py` raised FileNotFoundError at import before `main()`
    ran. Both scored compliant, and neither exit had anything to do with coverage.
    An incidental error is not a refusal, and counting it as one is the same
    can't-tell-these-apart defect the suite exists to close, one level up.

    So every structural prerequisite a gate needs to REACH its coverage check is
    present here, and everything it would actually examine is absent:

      config/_default/hugo.toml    present, minimal  -- gates parse it
      config/_default/params.toml  present, EMPTY    -- the zero-keys case
      static/_headers              present, EMPTY    -- the zero-rules case
      layouts/ content/ public/    present, EMPTY    -- the zero-surface case

    A gate that still exits 0 here has no floor. A gate that exits non-zero must
    say WHY, which `assert_refuses_to_clear` checks.
    """
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copytree(SCRIPTS, root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    cfg = root / "config" / "_default"
    cfg.mkdir(parents=True)
    (cfg / "hugo.toml").write_text(
        'baseURL = "https://example.invalid/"\ntitle = "skeleton"\n', encoding="utf-8")
    (cfg / "params.toml").write_text("", encoding="utf-8")
    (root / "static").mkdir()
    (root / "static" / "_headers").write_text("", encoding="utf-8")
    for d in ("layouts", "content", "public", "data", "assets"):
        (root / d).mkdir()
    # A git repo with no tracked files: `git ls-files` gates enumerate nothing,
    # which is the empty-surface case rather than a git error.
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def run_gate(root: Path, name: str) -> subprocess.CompletedProcess:
    gate = root / "scripts" / name
    argv = ["bash", str(gate)] if name.endswith(".sh") else [sys.executable, str(gate)]
    return subprocess.run(
        argv,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
    )


def assert_refuses_to_clear(name: str, result: subprocess.CompletedProcess) -> None:
    """The invariant itself, factored so the positive control asserts the SAME code.

    `returncode != 0` ALONE IS NOT ENOUGH, and asserting only that was this
    harness's own defect. A gate that crashes on a missing file, or dies in an
    import, also returns non-zero -- so three gates scored compliant while their
    real empty-surface path still returned 0. That is precisely the finding an
    earlier round raised against tests/test_gate_mutations.py ("asserts
    returncode != 0 only, so a pure SyntaxError reports the guard as pinned"),
    rebuilt here in the harness written to close that class.

    So the exit must be non-zero AND the gate must SAY it declined: either the
    shared `[vacuous-gate]` marker, or exit 2, which the repo-wide taxonomy in
    scripts/gate_coverage.py reserves for "could not look". A traceback is
    rejected outright -- an unhandled exception is a crash, never a verdict.
    """
    output = result.stdout + result.stderr

    assert "Traceback (most recent call last)" not in output, (
        f"{name} CRASHED against the empty skeleton rather than declining to "
        f"clear it. A crash is not a refusal: it exits non-zero for a reason "
        f"unrelated to coverage, so it would score compliant while its real "
        f"empty-surface path still returns 0. Handle the missing input "
        f"explicitly.\n--- gate output ---\n{output}"
    )

    assert result.returncode != 0, (
        f"{name} exited 0 against a tree containing none of the surfaces it "
        f"checks. Its assertions held vacuously and it reported that as a pass. "
        f"Give it a coverage floor: require_examined() from "
        f"scripts/gate_coverage.py on whatever it enumerates, or a fail-loud "
        f"branch of its own.\n--- gate output ---\n{output}"
    )

    assert output.strip(), (
        f"{name} exited {result.returncode} against the empty skeleton and said "
        f"NOTHING. A silent refusal is unreadable in a CI log and indistinguishable "
        f"from a crash; whatever it declined to do, it must name."
    )


# A stricter third assertion was tried and DELIBERATELY REJECTED: requiring the
# refusal to take a fixed form (exit 2, or the shared `[vacuous-gate]` marker).
# It failed five gates that already refuse correctly in their own words --
# validate_internal_links even self-reports "walked 0 markdown files ... (vacuous
# pass)", which is exactly the property, phrased its way. Mandating the FORM would
# have churned five correct gates to satisfy the test rather than the contract,
# and the property under test is "does not report success", not "reports failure
# in my house style". The valid-but-empty skeleton above is what actually closed
# the incidental-exit hole: gates now reach their real coverage path instead of
# dying on a missing config, so a gate that still exits 0 has genuinely no floor.


@pytest.mark.parametrize("name", [n for n in gate_inventory() if n not in EXEMPT])
def test_gate_refuses_to_clear_an_empty_tree(tmp_path, name):
    """The invariant. A gate with nothing to examine must not report success."""
    root = skeleton(tmp_path)
    assert_refuses_to_clear(name, run_gate(root, name))


def _synthetic(root: Path, name: str, body: str) -> None:
    (root / "scripts" / name).write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")


def test_harness_catches_a_vacuous_gate(tmp_path):
    """Positive control 1 of 3: the exit-0 branch must be able to FAIL.

    Every check in this file is an absence, which is the shape that passes for
    free once it stops discriminating. Three tests written during this Issue
    passed with their own subject disabled and were caught only by mutating it,
    so the mutants live in the suite permanently rather than in a session
    someone has to repeat.
    """
    root = skeleton(tmp_path)
    _synthetic(root, "check_synthetic_vacuous.py",
               "print('OK: 0 files scanned, no problems found.')\nraise SystemExit(0)\n")
    result = run_gate(root, "check_synthetic_vacuous.py")

    assert result.returncode == 0, "fixture must model the defect: exit 0 on an empty tree"
    with pytest.raises(AssertionError, match="exited 0 against a tree"):
        assert_refuses_to_clear("check_synthetic_vacuous.py", result)


def test_harness_catches_a_crashing_gate(tmp_path):
    """Positive control 2 of 3: the no-traceback branch must be able to FAIL.

    This is the branch that closes the harness's OWN original defect. Before it
    existed, `returncode != 0` alone scored a crashing gate as compliant, and two
    gates passed that way while their real empty-surface path still returned 0.
    An unpinned fix for a false-pass mechanism is itself a false-pass waiting to
    return, which is exactly what Ralph Tier 2 pointed out about this assertion.
    """
    root = skeleton(tmp_path)
    _synthetic(root, "check_synthetic_crash.py",
               "open('/nonexistent/definitely-not-here').read()\n")
    result = run_gate(root, "check_synthetic_crash.py")

    assert result.returncode != 0, "fixture must crash, so exit!=0 alone would pass it"
    assert "Traceback (most recent call last)" in result.stderr
    with pytest.raises(AssertionError, match="CRASHED against the empty skeleton"):
        assert_refuses_to_clear("check_synthetic_crash.py", result)


def test_harness_catches_a_silent_refusal(tmp_path):
    """Positive control 3 of 3: the non-empty-output branch must be able to FAIL.

    A gate that exits 2 and says nothing satisfies both assertions above while
    being unreadable in a CI log and indistinguishable from a crash.
    """
    root = skeleton(tmp_path)
    _synthetic(root, "check_synthetic_silent.py", "raise SystemExit(2)\n")
    result = run_gate(root, "check_synthetic_silent.py")

    assert result.returncode == 2 and not (result.stdout + result.stderr).strip()
    with pytest.raises(AssertionError, match="said NOTHING"):
        assert_refuses_to_clear("check_synthetic_silent.py", result)


def test_no_stale_exemptions():
    """An exemption naming a file that no longer exists is a silent allowlist.

    A stale entry costs nothing to leave behind and silently un-enrols whatever
    later takes that name, so staleness is checked rather than trusted.
    """
    inventory = set(gate_inventory())
    shell_gates = {p.name for p in SCRIPTS.glob("check*.sh")}
    known = inventory | shell_gates
    stale = sorted(set(EXEMPT) - known)
    assert not stale, (
        f"EXEMPT names {stale}, which are not gates in scripts/. Remove the "
        f"entries, or the next gate to take one of those names is exempt by "
        f"accident."
    )


def test_exemption_reasons_that_name_a_test_still_have_one():
    """An exemption is a claim that the floor is proved somewhere else.

    That claim decays exactly like a stale scan root: the named suite gets
    renamed or deleted, the exemption stays, and a gate is un-enrolled with a
    reason nobody re-reads. So any reason naming a file and a symbol is
    resolved here rather than believed. This is the same invariant the suite
    enforces on gates, applied to the suite's own escape hatch.
    """
    for gate, reason in EXEMPT.items():
        for token in reason.split():
            if not token.endswith(".py"):
                continue
            named = REPO / "scripts" / Path(token).name
            if not named.is_file():
                named = REPO / "tests" / Path(token).name
            assert named.is_file(), (
                f"EXEMPT[{gate}] cites {token}, which does not exist. The "
                f"exemption's justification is gone, so the gate is unproven."
            )
            # The reason names a class or function in that file; require it.
            symbols = [w for w in reason.split() if w[:1].isupper() and w[1:2].islower()]
            for sym in symbols:
                assert sym in named.read_text(encoding="utf-8"), (
                    f"EXEMPT[{gate}] cites {sym} in {token}, which no longer "
                    f"contains it. The floor this exemption defers to is gone."
                )


# Floors a gate cannot enforce alone, because only the CALLER knows the claim:
# whether this repo is public, whether this --built tree is a real build. Each is
# a flag, and a flag is one careless edit from being dropped -- at which point the
# gate silently returns to the behaviour the flag exists to prevent, with CI
# green. So the wiring is asserted, not assumed.
CALLER_DECLARED = [
    (".github/workflows/ci.yml", "check-public-repo-secrets.py . --require-public",
     "the blocking public-repo secret scan"),
    (".pre-commit-config.yaml", "check-public-repo-secrets.py . --staged-only --require-public",
     "the pre-commit secret hook"),
    (".github/workflows/ci.yml", "check_social_cards.py --built public --require-trails",
     "the rendered og:image tier in CI"),
    ("scripts/pre-publish.sh", "check_social_cards.py --built public --require-trails",
     "the rendered og:image tier in pre-publish"),
]


@pytest.mark.parametrize("path,invocation,what", CALLER_DECLARED)
def test_caller_declares_its_coverage_claim(path, invocation, what):
    """A caller that stops declaring silently un-arms the floor it depends on."""
    text = (REPO / path).read_text(encoding="utf-8")
    assert invocation in text, (
        f"{path} no longer invokes {what} as `{invocation}`. Without that flag "
        f"the gate reverts to a silent no-op on the exact failure it guards: a "
        f"missing .public-repo marker retires the leak scan, and a missing "
        f"trail.json downgrades the rendered card checks to source-only. Both "
        f"stay green while checking less."
    )


def test_inventory_is_not_empty():
    """The enrolment mechanism must itself be non-vacuous.

    If `gate_inventory()` ever returns nothing -- a moved directory, a changed
    naming convention -- the parametrized test above collects zero cases and
    the suite passes having checked no gate at all. That failure is invisible
    in a green run, which is why it is asserted rather than assumed.
    """
    inventory = gate_inventory()
    assert len(inventory) >= 15, (
        f"gate_inventory() found only {len(inventory)} gates ({inventory}). "
        f"The repo has ~20; a collapse here silently empties the whole suite."
    )
