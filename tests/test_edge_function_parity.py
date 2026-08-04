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
LOCKSTEP_HELPERS = ("readCapped", "redactPii", "textResponse", "clean")


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
    if match is None:
        return None

    body = match.group(0)
    # The non-greedy match stops at the FIRST `}` in column 0, which is the real
    # end of the declaration only while nothing inside the function closes a
    # brace at column 0. That holds for every helper here today, but a truncated
    # match would silently compare two identical PREFIXES of code that differs
    # later, and the comparison would pass. Braces have to balance, or the span
    # is not a whole function and this must not be used as evidence.
    assert body.count("{") == body.count("}"), (
        f"the extracted `{name}` from {path.name} has unbalanced braces "
        f"({body.count('{')} open, {body.count('}')} close), so the regex matched "
        f"a partial function. Comparing partial spans would pass on drifted code."
    )
    return body


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


def test_the_capped_read_is_unconditional_in_both_functions():
    """The body must ALWAYS be read through the cap, never on a header's say-so.

    This is the structural invariant behind two separate bypasses found in review,
    and it is here because fixing the instances twice did not stop the class.

    Round 1: the ceiling read `Number(header || 0)`, so an ABSENT header became 0
    and passed. The fix branched on `declaredLength === null` to decide whether to
    do a bounded read. Round 2: a header that is PRESENT but unparseable made
    `NaN > cap` false (no fast-reject) while `=== null` was also false (no bounded
    read), so an over-cap body sailed through to a real upstream write.

    Both bugs were the same shape: a branch that asked a client-controlled header
    whether to enforce the bound. The invariant is that no such branch exists. The
    header may only trigger an EARLIER reject; it may never gate the cap.

    Checked by indentation, which is the honest structural signal available to a
    source scan: at two spaces the call sits directly in the handler body, so it
    runs on every request. Wrap it in any `if` and a formatter indents it to four,
    and this fails.
    """
    for path in (SUBSCRIBE, CONTRIBUTE):
        source = path.read_text(encoding="utf-8")

        unconditional = re.findall(
            r"^  const capped = await readCapped\(request, MAX_BODY_BYTES\);$",
            source,
            re.M,
        )
        assert len(unconditional) == 1, (
            f"{path.name} does not call readCapped() unconditionally at handler "
            f"top level (found {len(unconditional)} such calls). If the capped read "
            f"has been moved inside a branch, a client can choose a header value "
            f"that takes the other path and the size ceiling stops applying. That "
            f"exact defect shipped twice on this endpoint pair."
        )

        assert "Number.isFinite(declaredLength)" in source, (
            f"{path.name} no longer guards the declared length with "
            f"Number.isFinite. Without it, a non-numeric header yields NaN and "
            f"every comparison against it is false, so the fast-reject silently "
            f"never fires."
        )


def test_every_upstream_response_body_is_redacted_at_capture():
    """Upstream text must be redacted where it is READ, not where it is logged.

    `content/legal/sub-processors/index.md` publishes, for the Pages Functions
    row of both forms, that the submitted fields are handled in transit only and
    "the request is not persisted". An upstream is free to quote the value it
    rejected, so echoing its raw error body into a structured log put a
    submitter's email address on a persisted log surface and made that published
    claim false.

    Redacting at each log call would leave the claim one forgotten call site away
    from being false again, which is the same shape as the bug. So the invariant
    is at the capture point: every `await resp.text()` is wrapped in redactPii().

    Asserted over ALL capture sites, not a known list, so a newly added upstream
    call cannot quietly introduce an unredacted one.
    """
    for path in (SUBSCRIBE, CONTRIBUTE):
        source = path.read_text(encoding="utf-8")

        captures = re.findall(r"^\s*(?:const|let)\s+\w+\s*=\s*(.+?);$", source, re.M)
        text_captures = [c for c in captures if ".text()" in c]

        assert text_captures, (
            f"{path.name} has no `await resp.text()` capture at all. If the "
            f"upstream error path was restructured, this gate is now asserting "
            f"nothing and must be rewritten to match the new shape."
        )

        for capture in text_captures:
            assert capture.startswith("redactPii("), (
                f"{path.name} captures an upstream response body without "
                f"redacting it: {capture!r}. Wrap it in redactPii() at the "
                f"capture point. An upstream can echo the submitted email back "
                f"in its error text, and this Function publishes that it does "
                f"not persist the request."
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
