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
