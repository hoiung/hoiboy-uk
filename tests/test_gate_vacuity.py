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
GATE_GLOBS = ("check*.py", "validate*.py")
GATE_EXTRA = ("test_404.py",)

# Gates that cannot be driven by "run it against an empty tree", each with the
# reason. An entry here is a claim about the GATE, not a licence to skip: every
# one must still be non-vacuous by its own test, and `test_no_stale_exemptions`
# fails the build when an entry stops naming a real file.
EXEMPT: dict[str, str] = {
    # Takes its surface entirely from argv (pre-commit passes staged files) and
    # has no repo-wide mode to run vacuously. Its zero-surface floor is asserted
    # directly in scripts/test_check_wordcount.py.
    "check_wordcount.py": "argv-only surface; floor asserted in its own suite",
    # Compares this repo against the dotfiles canonical clone, which does not
    # exist inside a tmp skeleton. Absence of the canonical is itself a hard
    # failure in that gate, so the empty-tree run proves nothing new.
    "check-mirror-drift.py": "needs the canonical dotfiles clone, absent by construction",
    # Network gate: resolves live robots.txt over HTTP. Running it in the
    # skeleton would assert the network, not the coverage floor.
    "check-ai-crawler-access.sh": "network gate; empty-tree run asserts DNS, not coverage",
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
    """An empty repo that every gate will resolve as its own root.

    `scripts/` is copied whole so intra-package imports (voice_rules,
    gate_coverage, the social-cards helpers) resolve exactly as they do in
    production. Everything a gate scans -- content/, layouts/, public/,
    config/ -- is deliberately absent or empty. That is the point: this is the
    tree in which every one of the eleven defects printed OK.
    """
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copytree(SCRIPTS, root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    # A git repo with no tracked files: `git ls-files` based gates enumerate
    # nothing, which is the empty-surface case rather than a git error.
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def run_gate(root: Path, name: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "scripts" / name)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
    )


def assert_refuses_to_clear(name: str, result: subprocess.CompletedProcess) -> None:
    """The invariant itself, factored so the positive control asserts the SAME code.

    Written once and called twice on purpose. A control that re-implements the
    assertion it is controlling drifts away from it silently, and then proves
    only that the copy still works.
    """
    output = result.stdout + result.stderr

    # Distinguish "the gate declined to clear an empty tree" (the property) from
    # "the skeleton was broken" (a harness artifact that would score every gate
    # as compliant for free). Without this, a typo in `skeleton()` turns the
    # whole suite green while proving nothing -- the same fail-open shape the
    # suite exists to catch, one level up.
    assert "ModuleNotFoundError" not in output, (
        f"{name} failed on a missing import, so the skeleton is broken and this "
        f"assertion proved nothing about the gate:\n{output}"
    )

    assert result.returncode != 0, (
        f"{name} exited 0 against a tree containing none of the surfaces it "
        f"checks. Its assertions held vacuously and it reported that as a pass. "
        f"Give it a coverage floor from scripts/gate_coverage.py -- "
        f"require_examined() on whatever it enumerates, require_input() on "
        f"whatever it declares.\n--- gate output ---\n{output}"
    )


@pytest.mark.parametrize("name", [n for n in gate_inventory() if n not in EXEMPT])
def test_gate_refuses_to_clear_an_empty_tree(tmp_path, name):
    """The invariant. A gate with nothing to examine must not report success."""
    root = skeleton(tmp_path)
    assert_refuses_to_clear(name, run_gate(root, name))


def test_harness_catches_a_vacuous_gate(tmp_path):
    """Positive control: the assertion above must be able to FAIL.

    Every check in this file is an absence, which is precisely the shape that
    passes for free once it stops discriminating. Three tests written during
    this Issue passed with their own subject disabled and were caught only by
    mutating it, so the mutant lives in the suite permanently rather than in a
    session someone has to repeat.

    A gate that prints a confident OK and exits 0 over the empty skeleton is
    the defect in one file. If the harness ever stops failing it, the harness
    has stopped testing.
    """
    root = skeleton(tmp_path)
    (root / "scripts" / "check_synthetic_vacuous.py").write_text(
        "#!/usr/bin/env python3\n"
        "print('OK: 0 files scanned, no problems found.')\n"
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    result = run_gate(root, "check_synthetic_vacuous.py")

    assert result.returncode == 0, "fixture must model the defect: exit 0 on an empty tree"
    with pytest.raises(AssertionError, match="exited 0 against a tree"):
        assert_refuses_to_clear("check_synthetic_vacuous.py", result)


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
