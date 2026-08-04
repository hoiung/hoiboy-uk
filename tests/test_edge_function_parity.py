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
    "replaceLiteral",
    "redactString",
    "redactDeep",
    "redactText",
    "redactLine",
    "createLogger",
    # The bot-defence call. #56 duplicated it into subscribe.js, and Ralph
    # round 21 Tier 3 found it ALREADY drifted at HEAD (a trailing comma in the
    # fetch options) with every delivered test still green -- which is the
    # proof that "both endpoints verify Turnstile the same way" was an
    # assumption, not an invariant. Cosmetic that time; nothing would have
    # caught a changed endpoint, a dropped `remoteip`, or an inverted result.
    "verifyTurnstile",
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
    is at the capture point: every `await resp.text()` is wrapped in the
    logger's redact() -- the by-value pass FIRST, on the pristine text, then the
    shape pass. Bare redactPii() at capture is REJECTED outright: it once
    shipped, and it leaked. On an address with an excluded character
    MID-local-part the shape pass rewrites the suffix to [email-redacted],
    destroying the exact literal the by-value pass was holding, so the prefix
    survived every later pass (Ralph round 14 Tier 3, reproduced end-to-end).

    SCOPE, stated precisely (Ralph round 22 Tier 3 corrected an overclaim here).
    This asserts over every capture BOUND TO A NAME -- `const`/`let NAME = ...`
    draining a response body. Each Function has three body drains; this shape
    catches the one that matters today and any new one written the same way.

    It does NOT cover a drain whose result is returned directly rather than
    bound, which is why `verifyTurnstile`'s `return await resp.json();` is
    outside it. That is safe now (a siteverify verdict carries no submitted
    address), but it is NOT a guarantee that any future upstream call is
    covered. The reviewer demonstrated the gap concretely: a second upstream
    call written in the shape AC 3.7 specifies, truncating before redacting,
    leaked a local part verbatim while this gate still passed 10/10.

    So: if you add an upstream call, bind its body to a name and redact before
    truncating. Do not read this gate as proving you did.
    """
    for path in (SUBSCRIBE, CONTRIBUTE):
        source = path.read_text(encoding="utf-8")

        captures = re.findall(
            r"^\s*(?:const|let)\s+(\w+)\s*=\s*(.+?);$", source, re.M
        )
        # Every way of draining an upstream response body, not just .text().
        # The docstring above claims ALL capture sites are covered, and a filter
        # that only knew about .text() would have made that claim false the first
        # time someone reached for .json() (Ralph Tier 3).
        body_readers = (".text()", ".json()", ".arrayBuffer()", ".blob()", ".formData()")
        text_captures = [(n, c) for n, c in captures if any(r in c for r in body_readers)]

        assert text_captures, (
            f"{path.name} has no upstream body capture at all. If the upstream "
            f"error path was restructured, this gate is now asserting nothing "
            f"and must be rewritten to match the new shape."
        )

        # Every `log(...)` call's arguments, so a raw capture can be checked
        # against them by name.
        log_calls = re.findall(r"\blog\((?:[^()]|\([^()]*\))*\)", source)

        for name, capture in text_captures:
            # The SHAPE-ONLY wrapper is rejected by name, not merely by a later
            # check failing to match: it is the exact form that shipped and
            # leaked, and a future reader reverting to it deserves the reason.
            assert not capture.startswith("redactPii("), (
                f"{path.name} runs the shape redactor ALONE at capture: "
                f"{capture!r}. That order cannibalises the by-value pass: on an "
                f"address with an excluded character mid-local-part, redactPii "
                f"rewrites the suffix and destroys the held literal, so the "
                f"local-part prefix survives every later pass. Use the logger's "
                f"redact() (value first, then shape)."
            )

            if capture.startswith("redact("):
                # Redacted AT capture. Nothing may alter the text between
                # reading it and redacting it: a fixed-offset strip on
                # `redact(await resp.text()).slice(0, 500)` would leave the
                # trailing `.slice(` in the string and fire on the CORRECT form,
                # so scan balanced parens and test only the redactor's argument.
                depth, start = 0, len("redact(") - 1
                inner = capture
                for idx in range(start, len(capture)):
                    if capture[idx] == "(":
                        depth += 1
                    elif capture[idx] == ")":
                        depth -= 1
                        if depth == 0:
                            inner = capture[start + 1:idx]
                            break
                assert not any(
                    op in inner
                    for op in (".slice(", ".substring(", ".substr(", ".split(")
                ), (
                    f"{path.name} transforms the body BEFORE redacting it: "
                    f"{capture!r}. Truncating first lets an address straddling "
                    f"the cut survive as a fragment neither redactor can match. "
                    f"Redact the full text, then bound it."
                )
                continue

            # NOT redacted at capture. That is allowed for exactly one reason:
            # control flow must parse the PRISTINE body, because redaction is a
            # lossy transform over visitor-supplied literals and parsing the
            # redacted copy let a submitted name delete the key a branch reads
            # (Ralph round 15 Tier 3). The price is that the raw binding must
            # never reach a log line, and a redacted copy must exist.
            assert re.search(rf"\bredact\(\s*{re.escape(name)}\s*\)", source), (
                f"{path.name} captures an upstream body into `{name}` and never "
                f"redacts it: {capture!r}. An upstream can echo the submitted "
                f"address back in its error text, and this Function publishes "
                f"that it does not persist the request. Either wrap the capture "
                f"in redact(), or keep the raw binding for control flow ONLY and "
                f"log redact({name}) instead."
            )
            for call in log_calls:
                assert not re.search(rf"\b{re.escape(name)}\b", call), (
                    f"{path.name} logs the PRISTINE upstream body `{name}`: "
                    f"{call!r}. That binding exists so control flow can parse "
                    f"unredacted text; it must never reach a log line. Log the "
                    f"redacted copy instead."
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


def test_the_serialised_line_is_redacted_by_shape_only():
    """`redactLine` must not run a by-value replace over the finished line.

    A held value is arbitrary visitor text and `replaceLiteral` is blind, so
    applying it to the SERIALISED line let a submitted name rewrite the line's
    own structure: a name of `duplicate` renamed that key, and a name carrying a
    double quote terminated a JSON string early and produced an unparseable
    line. Values are already redacted one level down by `redactDeep`, where each
    is still a plain string and cannot collide with structure.

    So the invariant is a level rule, not a call-site list: `redactLine` takes
    the line ALONE, and the only redactor it may apply is the shape pass.
    Behavioural cover is `tests/subscribe.test.js`; this pins the shape in both
    files so the endpoint that has no such suite cannot drift (Ralph round 15).
    """
    for path in (SUBSCRIBE, CONTRIBUTE):
        source = path.read_text(encoding="utf-8")
        body = function_body(path, "redactLine")
        assert body is not None, (
            f"{path.name} has no top-level redactLine declaration. If the log "
            f"write boundary was restructured, this gate is asserting nothing "
            f"and must be rewritten to match the new shape."
        )
        assert "redactString" not in body, (
            f"{path.name}'s redactLine runs a by-value replace over the "
            f"serialised line: {body!r}. That lets a visitor-supplied value "
            f"rewrite the line's own keys. Redact values in redactDeep, before "
            f"serialisation; keep this pass shape-only."
        )
        assert re.search(r"^function redactLine\(line\)", body, re.M), (
            f"{path.name}'s redactLine takes more than the line: {body!r}. It "
            f"must not receive the known-value set at all -- having it in scope "
            f"is what made the by-value replace reachable here."
        )
        assert "redactPii" in body, (
            f"{path.name}'s redactLine no longer applies the shape pass, so an "
            f"address the request never held reaches the log verbatim: {body!r}"
        )


def test_control_flow_reads_the_pristine_upstream_body():
    """`JSON.parse` for control flow must not read the REDACTED copy.

    Redaction is a lossy transform over visitor-supplied literals. Parsing the
    redacted text let a submitted name of `code` delete the very key the
    duplicate branch reads, so a duplicate fell through to 502 while a fresh
    signup returned 303 -- a subscribe-status oracle, defeating the property
    that branch exists to provide (Ralph round 15 Tier 3).

    Only subscribe.js parses an upstream body for control flow; contribute.js
    captures one but never branches on it. The gate is therefore written as
    "no parse of a redacted value ANYWHERE", which holds vacuously for
    contribute.js today and starts biting the moment it grows such a branch.
    """
    for path in (SUBSCRIBE, CONTRIBUTE):
        source = path.read_text(encoding="utf-8")
        parses = re.findall(r"JSON\.parse\(([^)]*)\)", source)
        for target in parses:
            assert target.strip() != "detail", (
                f"{path.name} parses the redacted copy for control flow: "
                f"JSON.parse({target}). Parse the pristine body and redact only "
                f"what is logged, or a visitor-supplied literal can delete the "
                f"key the branch depends on."
            )


# Constants the lock-stepped helpers READ. Enrolling the functions alone is not
# enough: every one of these is a bare `const X = <literal>;` that the functions
# consult, so drifting the VALUE in one file changes that endpoint's behaviour
# while every function body still compares byte-identical.
#
# Ralph round 19 Tier 3 proved it: setting MIN_PROTECTED_LENGTH to 400 in
# contribute.js alone reopens escalation-2 defect 6 on that endpoint -- no
# submitted value is long enough to be registered, so by-value redaction stops
# happening entirely -- and it survived all 8 parity tests and both contribute
# suites.
LOCKSTEP_CONSTANTS = (
    "REDACTED_VALUE",
    "MIN_PROTECTED_LENGTH",
    "MAX_ESCAPE_LEVELS",
    # The address-validation regex, duplicated into subscribe.js by #56. It is
    # the pattern `redactPii`'s character class is deliberately narrower than
    # (see the "alphabet gap" comment in both Functions), so the two are read
    # together as one contract. Widening it on one endpoint alone would admit
    # addresses that endpoint's redactor cannot then match -- the leak class
    # rounds 11-15 kept reopening -- with nothing to show for it.
    "EMAIL_RE",
)


def constant_declaration(path: Path, name: str) -> str | None:
    """The whole `const <name> = <literal>;` line, or None if absent."""
    source = path.read_text(encoding="utf-8")
    match = re.search(rf"^const {re.escape(name)}\s*=\s*(.+);$", source, re.M)
    return match.group(1) if match else None


def test_the_lockstep_constants_are_present_in_both_functions():
    """Guard the guard: a renamed constant must not silently empty the check."""
    for name in LOCKSTEP_CONSTANTS:
        for path in (SUBSCRIBE, CONTRIBUTE):
            assert constant_declaration(path, name) is not None, (
                f"{path.name} no longer declares a top-level `const {name}`. "
                f"Either it was renamed or its shape changed; the value "
                f"comparison below would otherwise pass by comparing nothing."
            )


def test_lockstep_constants_have_not_drifted_between_the_two_functions():
    """Same constant, same VALUE, both files.

    The helpers are byte-identical by the gate above, which is exactly why a
    drifted constant is invisible there: identical code reading a different
    number behaves differently. This is the value half of the same invariant.
    """
    for name in LOCKSTEP_CONSTANTS:
        mine = constant_declaration(SUBSCRIBE, name)
        theirs = constant_declaration(CONTRIBUTE, name)
        assert mine == theirs, (
            f"`{name}` has drifted: subscribe.js has {mine!r}, contribute.js has "
            f"{theirs!r}. The helpers that read it are byte-identical, so this "
            f"changes one endpoint's behaviour with nothing else to show for it. "
            f"Copy the change across, or if they must genuinely differ now, "
            f"remove {name!r} from LOCKSTEP_CONSTANTS and say why in this "
            f"module's docstring."
        )
