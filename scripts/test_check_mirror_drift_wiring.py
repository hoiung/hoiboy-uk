"""Tests that the two vendored drift-check files stay a matched pair.

`check-mirror-drift.py` and `sst3_mirror_utils.py` are BOTH vendored copies of
canonical files in dotfiles/SST3. They are propagated independently, one file at
a time, which means it is entirely possible to sync one and not the other.

That is not hypothetical. It shipped. Commit a26e9f4 synced
`check-mirror-drift.py` to a canonical revision that had grown a call to
`smu.propagate_tool_path()`, while this repo's `sst3_mirror_utils.py` stayed
116 lines behind and did not define it. The result was an unhandled
AttributeError on the unstaged-drift branch: the exact path whose documented
contract is "surfaced as warnings, commit allowed". A warning-and-proceed path
became a hard crash, on a hook that runs with `always_run: true` on every
commit, for commits having nothing to do with the drifted file.

Nothing caught it, because there was no test for this script at all. Ralph
round 9 Tier 2 found it by reading the diff.

The failure is invisible to the drift checker itself: each file is individually
in sync with its own canonical, so a per-file drift check passes while the pair
is internally inconsistent. Only a cross-file check sees it.

These tests are deliberately about WIRING, not behaviour. They ask one question:
does every module attribute the script reaches for actually exist on the copy of
the module this repo ships? That question is cheap, has no fixtures, and would
have turned red the moment the half-sync landed.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
DRIFT_SCRIPT = SCRIPTS / "check-mirror-drift.py"
UTILS_MODULE = SCRIPTS / "sst3_mirror_utils.py"

# `smu.<name>` as written in the script. Attribute access only: this is not
# trying to parse Python, it is asking which names the script expects to find.
SMU_ATTR = re.compile(r"\bsmu\.([A-Za-z_][A-Za-z0-9_]*)")


def _load_vendored_utils():
    """Import THIS repo's vendored copy, not whatever is on sys.path.

    Importing by name would happily pick up a different copy (the canonical one
    in dotfiles, say) and the test would then verify a file this repo does not
    ship, passing while the shipped pair is broken.
    """
    spec = importlib.util.spec_from_file_location(
        "_vendored_sst3_mirror_utils", UTILS_MODULE
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_both_halves_of_the_vendored_pair_are_present():
    assert DRIFT_SCRIPT.is_file(), f"{DRIFT_SCRIPT} is missing"
    assert UTILS_MODULE.is_file(), f"{UTILS_MODULE} is missing"


def test_the_script_actually_references_the_utils_module():
    """Guard against this file quietly becoming vacuous.

    If the script is ever refactored to stop using the `smu.` alias, the
    attribute sweep below would find zero names and pass while checking
    nothing. That is the shape of test this repo has already shipped four
    times, so it gets an explicit assertion rather than a comment.
    """
    source = DRIFT_SCRIPT.read_text(encoding="utf-8")
    found = set(SMU_ATTR.findall(source))
    assert found, (
        "no `smu.<attr>` references found in check-mirror-drift.py. Either the "
        "import alias changed or this test has gone vacuous; update SMU_ATTR."
    )


def test_every_smu_attribute_the_script_uses_exists_on_the_vendored_module():
    """The regression that shipped in a26e9f4.

    A missing name here means the two vendored files were propagated out of
    step. The fix is to sync the lagging one, not to delete the call.
    """
    source = DRIFT_SCRIPT.read_text(encoding="utf-8")
    referenced = sorted(set(SMU_ATTR.findall(source)))
    module = _load_vendored_utils()

    missing = [name for name in referenced if not hasattr(module, name)]

    assert not missing, (
        f"check-mirror-drift.py calls {missing} but this repo's vendored "
        f"sst3_mirror_utils.py does not define them. The two files are a "
        f"matched pair and have drifted apart. Sync the lagging half:\n"
        f"  python3 ../dotfiles/SST3/scripts/propagate-mirrors.py --apply "
        f"--repo hoiboy-uk --file SST3/scripts/sst3_mirror_utils.py\n"
        f"NOTE: that tool writes to the MAIN CLONE, not to a linked worktree."
    )


@pytest.mark.parametrize(
    "name",
    [
        # The specific casualty of the half-sync. Pinned by name so a future
        # re-introduction of the same partial propagation names itself in the
        # failure output instead of hiding inside the generic sweep above.
        "propagate_tool_path",
        # The drift-check entrypoints. If any of these vanish the hooks break
        # outright rather than on one branch.
        "check_mirror_drift",
        "iter_mirror_entries",
        "find_manifest",
    ],
)
def test_load_bearing_utils_functions_are_callable(name):
    module = _load_vendored_utils()
    assert hasattr(module, name), (
        f"vendored sst3_mirror_utils.py is missing {name}(); the vendored pair "
        f"is out of step with canonical"
    )
    assert callable(getattr(module, name)), f"{name} exists but is not callable"
