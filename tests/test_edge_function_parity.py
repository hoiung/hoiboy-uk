"""Lock-step guard for helpers duplicated across the two Pages Functions (#56).

`functions/api/subscribe.js` and `functions/api/contribute.js` are deliberately
self-contained edge modules. There is no shared module under `functions/`, and
there deliberately is not one: an `import` would break the real-source loading in
`tests/subscribe.test.js`, which evaluates the module body directly rather than
mirroring its helpers by hand the way `tests/contribute.test.js` has to.

The cost of that choice is duplicated helpers, and duplication drifts. It already
would have: the `#56` Ralph review found that BOTH files trusted a client-supplied
`content-length` as a size bound, and fixing only the endpoint under review would
have left the identical hole in its sibling, on the endpoint that accepts photo
uploads and therefore has the larger ceiling.

So the duplication is allowed, and this gate is the price of allowing it. A change
to any helper below must be made in both files or this fails.

`log` is excluded ON PURPOSE. It is duplicated too, but the two copies legitimately
differ: each stamps its own function name into the structured line (`"fn":
"subscribe"` vs `"fn": "contribute"`), which is the whole point of the field. It is
asserted to differ, so this exclusion cannot silently widen into "log drifted and
nobody noticed".
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

SUBSCRIBE = REPO / "functions" / "api" / "subscribe.js"
CONTRIBUTE = REPO / "functions" / "api" / "contribute.js"

# Helpers that MUST be byte-identical in both Functions.
LOCKSTEP_HELPERS = ("readCapped", "textResponse", "clean")


def function_body(path: Path, name: str) -> str | None:
    """The whole `function <name>(...) { ... }` declaration, brace to brace.

    Anchored on a top-level declaration (column 0) and terminated by a closing
    brace in column 0, which is the shape both files are written in. A helper
    that gets indented into a nested scope stops matching and fails loud here
    rather than silently comparing nothing.
    """
    source = path.read_text(encoding="utf-8")
    match = re.search(
        rf"^(?:async )?function {re.escape(name)}\(.*?^\}}",
        source,
        re.S | re.M,
    )
    return match.group(0) if match else None


def test_the_lockstep_helpers_are_present_in_both_functions():
    """Guard the guard: a renamed helper must not silently empty this gate."""
    for name in LOCKSTEP_HELPERS:
        for path in (SUBSCRIBE, CONTRIBUTE):
            assert function_body(path, name) is not None, (
                f"{path.name} no longer declares a top-level `{name}`. Either the "
                f"helper was renamed or its shape changed; every assertion below "
                f"about {name} would otherwise pass by comparing nothing."
            )


def test_duplicated_helpers_have_not_drifted_between_the_two_functions():
    """The actual invariant: same helper, same bytes, both files."""
    for name in LOCKSTEP_HELPERS:
        mine = function_body(SUBSCRIBE, name)
        theirs = function_body(CONTRIBUTE, name)
        assert mine == theirs, (
            f"`{name}` has drifted between functions/api/subscribe.js and "
            f"functions/api/contribute.js. These are duplicated on purpose "
            f"(self-contained edge modules, no shared import), so a fix to one "
            f"has to land in the other. Copy the change across, or if they must "
            f"genuinely differ now, remove {name!r} from LOCKSTEP_HELPERS and say "
            f"why in this module's docstring."
        )


def test_log_is_excluded_because_it_genuinely_differs():
    """The exclusion is asserted, not assumed.

    If someone later makes the two `log` helpers identical, that is fine, but it
    means this exclusion is stale and `log` should join LOCKSTEP_HELPERS. Failing
    here is how that gets noticed instead of quietly leaving a helper ungated.
    """
    mine = function_body(SUBSCRIBE, "log")
    theirs = function_body(CONTRIBUTE, "log")
    assert mine is not None and theirs is not None
    assert mine != theirs, (
        "the two `log` helpers are now identical, so the documented reason for "
        "excluding `log` from LOCKSTEP_HELPERS no longer holds. Add it to the "
        "tuple and delete this test."
    )
    assert '"fn": "subscribe"' in mine or '"subscribe"' in mine
    assert '"contribute"' in theirs
