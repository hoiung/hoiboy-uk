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

`log` USED to be excluded, because each copy stamped its own function name into
the structured line (`"fn": "subscribe"` vs `"fn": "contribute"`) and so the two
bodies legitimately differed. That exclusion is gone: the logger is now built by
`createLogger(fn)`, which takes the name as a parameter, so the body is identical
in both files and only the call site differs. `createLogger` is therefore in
LOCKSTEP_HELPERS below and the stale "log genuinely differs" test is deleted --
which is precisely the migration that test's own docstring asked for when it
fired.

That change is load-bearing, not cosmetic. The redaction it carries (`redactLine`
+ `literalForms`) is what closes the alphabet gap between `EMAIL_RE` and
`redactPii`, and it is exactly the kind of security helper that must not be
allowed to drift between a newsletter endpoint and a photo-upload endpoint.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

SUBSCRIBE = REPO / "functions" / "api" / "subscribe.js"
CONTRIBUTE = REPO / "functions" / "api" / "contribute.js"

# Helpers that MUST be byte-identical in both Functions.
LOCKSTEP_HELPERS = (
    "readCapped",
    "redactPii",
    "textResponse",
    "clean",
    # The value-redaction path. `createLogger` takes the function name as a
    # parameter precisely so these can be lock-stepped rather than excluded.
    # Every function in the chain is enrolled: Ralph round 13 proved that with
    # `redactString` and `redactDeep` missing, deleting `redactDeep`'s
    # array-handling branch in one file (reopening the exact leak class the
    # chain exists to close, on one endpoint only) drifted the files while
    # every enrolled helper still compared equal.
    "literalForms",
    "redactString",
    "redactDeep",
    "redactLine",
    "createLogger",
)


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

        # Calling readCapped is not the invariant; ACTING on its refusal is.
        # Ralph Tier 3 showed this gate was ceremonial without the next
        # assertion: `if (capped === null && declaredLength > 0)` still calls
        # readCapped at the right indent, so the check above passes, while a
        # chunked request (declaredLength 0) skips the 413 entirely. That is the
        # round-1 bypass reopened, and it survived every other delivered gate.
        #
        # Be clear about what this can and cannot do. It is a cheap TRIPWIRE for
        # the exact one-token shape that shipped, not a proof of control flow: a
        # regex cannot establish that a line executes. Ralph Tier 2 duly defeated
        # it twice, with a nested `if` and by moving the pair into a dead helper.
        # Both of those are caught by the BEHAVIOURAL suites
        # (tests/contribute-handler.test.js, tests/subscribe.test.js), which
        # execute the handler and are the real guarantee here. This assertion
        # earns its place by failing fast and naming the defect, not by being
        # exhaustive. Do not add shapes to it and call the class closed; add a
        # behavioural test instead.
        acted_on = re.findall(r"^  if \(capped === null\) \{$", source, re.M)
        assert len(acted_on) == 1, (
            f"{path.name} does not reject unconditionally on readCapped()'s null "
            f"return (found {len(acted_on)} bare `if (capped === null) {{` at "
            f"handler top level). Adding a condition to that branch is how the "
            f"round-1 bypass was reopened."
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
        # Every way of draining an upstream response body, not just .text().
        # The docstring above claims ALL capture sites are covered, and a filter
        # that only knew about .text() would have made that claim false the first
        # time someone reached for .json() (Ralph Tier 3).
        body_readers = (".text()", ".json()", ".arrayBuffer()", ".blob()", ".formData()")
        text_captures = [c for c in captures if any(r in c for r in body_readers)]

        assert text_captures, (
            f"{path.name} has no `await resp.text()` capture at all. If the "
            f"upstream error path was restructured, this gate is now asserting "
            f"nothing and must be rewritten to match the new shape."
        )

        for capture in text_captures:
            # `.startswith("redactPii(")` alone was satisfied by
            # `redactPii((await resp.text()).slice(0, 500))` -- redaction wrapping
            # a value that had ALREADY been truncated. The gate certified
            # redaction-at-capture while blind to a lossy transform inside the
            # call, and 8 of 31 padding offsets leaked the local part because the
            # cut landed mid-address and the regex no longer matched (Ralph Tier 3).
            # So the body read must be the DIRECT argument: nothing may alter the
            # text between reading it and redacting it.
            inner = capture
            if capture.startswith("redactPii("):
                # Balanced-paren scan, not a naive strip: the capture INCLUDES
                # everything chained after the call, so `capture[10:-1]` on
                # `redactPii(await resp.text()).slice(0, 500)` leaves the trailing
                # `.slice(` in the string and the check fires on the CORRECT form.
                # Only the redactor's own argument is under test here.
                depth, start = 0, len("redactPii(") - 1
                for idx in range(start, len(capture)):
                    if capture[idx] == "(":
                        depth += 1
                    elif capture[idx] == ")":
                        depth -= 1
                        if depth == 0:
                            inner = capture[start + 1:idx]
                            break
            assert not any(
                op in inner for op in (".slice(", ".substring(", ".substr(", ".split(")
            ), (
                f"{path.name} transforms the body BEFORE redacting it: "
                f"{capture!r}. Truncating first lets an address straddling the cut "
                f"survive as a fragment the redactor cannot match. Redact the full "
                f"text, then bound it: redactPii(await resp.text()).slice(0, N)."
            )
            assert capture.startswith("redactPii("), (
                f"{path.name} captures a response body without redacting it: "
                f"{capture!r}. An upstream can echo the submitted email back in "
                f"its error text, and this Function publishes that it does not "
                f"persist the request, so wrap it in redactPii() at the capture "
                f"point. This gate is deliberately fail-closed on EVERY body "
                f"read: if the value is binary or never reaches a log (an image "
                f"buffer, say), that is fine, but say so by excluding it here "
                f"with a reason rather than by letting the check quietly not "
                f"apply."
            )


def test_the_redacted_value_set_is_per_request_not_module_level():
    """The set of values to redact must live INSIDE `createLogger`.

    A Workers isolate serves concurrent requests off one module instance. A
    module-level mutable set would therefore be shared across visitors, and one
    subscriber's address registered mid-flight would be stripped out of a
    DIFFERENT visitor's log line -- or, far worse, retained after their request
    ended and matched against someone else's. That is a cross-request PII leak,
    strictly worse than the single-request leak this redactor was added to fix.

    So the declaration is asserted to be nested, not top-level. This is the one
    property of the design that cannot be checked by reading either function
    body in isolation.
    """
    for path in (SUBSCRIBE, CONTRIBUTE):
        source = path.read_text(encoding="utf-8")

        body = function_body(path, "createLogger")
        assert body is not None, f"{path.name} no longer declares `createLogger`"
        assert "const known = new Set()" in body, (
            f"{path.name}'s createLogger no longer creates its own known-value "
            f"set. Every value registered by protect() would then have nowhere "
            f"request-scoped to live."
        )

        # Nothing may construct a Set at column 0: that is what "module-level"
        # looks like in these files, and it is the shape being forbidden.
        top_level_sets = re.findall(r"^(?:const|let|var)\s+\w+\s*=\s*new Set\(", source, re.M)
        assert not top_level_sets, (
            f"{path.name} declares a module-level Set ({top_level_sets}). In a "
            f"Workers isolate that is shared across concurrent requests, so a "
            f"value registered for redaction by one visitor outlives their "
            f"request and applies to another's."
        )


def test_the_logger_is_built_per_request_in_both_handlers():
    """`createLogger` must actually be CALLED, once, inside each handler.

    The helper being present and lock-stepped proves nothing on its own: if a
    handler never builds a logger, `protect` is never wired and every log line
    falls back to shape-only redaction -- the exact gap that let
    `"patriley"@example.net` through verbatim.
    """
    for path, expected_name in ((SUBSCRIBE, "subscribe"), (CONTRIBUTE, "contribute")):
        source = path.read_text(encoding="utf-8")
        calls = re.findall(r'createLogger\("([^"]+)"\)', source)
        assert calls == [expected_name], (
            f"{path.name} should build exactly one logger stamped "
            f'"{expected_name}"; found {calls}. A handler with no createLogger '
            f"call has no per-request redaction at all."
        )
        assert "protect(email)" in source, (
            f"{path.name} never registers the submitted email for redaction, so "
            f"an address whose shape redactPii cannot match reaches the log "
            f"verbatim."
        )
