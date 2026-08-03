"""Consent-label version traceability (agit-ops#3 AC 1.9).

The community form is an Article 9(2)(a) explicit-consent surface. Recording
THAT consent was given is not enough; the record has to show WHICH wording was
agreed to, or a later export cannot tell a pre-amendment submission from a
post-amendment one.

Three surfaces have to agree and none of them imports the others:

  1. the hidden input in content/community/asians-gingers-in-tech/index.md
     (raw HTML inside Hugo markdown -- the version actually rendered),
  2. KNOWN_CONSENT_VERSIONS in functions/api/contribute.js
     (the Pages Function that accepts or rejects it),
  3. the lock-step mirror of that list in tests/contribute.test.js
     (contribute.js is ESM in a CJS package, so the JS suite mirrors pure
     helpers rather than importing them -- see that file's header).

Nothing at runtime couples them, so a wording change that bumps one and not the
others fails silently: the form would post a version the endpoint rejects, and
every submission would 400. These assertions are that coupling.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Parsing shared with the newsletter surface (#56 AC 4.3). Extracted so a fix to
# the hidden-input pattern lands in both gates rather than one, which is the same
# silent-drift failure these gates exist to catch, one level up.
from consent_version_surfaces import (  # noqa: E402
    REPO,
    assignment_expression,
    hidden_input_version,
    js_string_list as _versions_from,
)

FORM = REPO / "content" / "community" / "asians-gingers-in-tech" / "index.md"
ENDPOINT = REPO / "functions" / "api" / "contribute.js"
JS_TEST = REPO / "tests" / "contribute.test.js"


def test_form_hidden_version_is_accepted_by_the_endpoint():
    """The version the form renders must be one the endpoint accepts."""
    rendered = hidden_input_version(FORM)
    accepted = _versions_from(ENDPOINT)
    assert rendered in accepted, (
        f"the form posts consent_version={rendered!r} but contribute.js accepts "
        f"{accepted!r}; every submission would be rejected with a 400"
    )


def test_js_test_mirror_matches_the_endpoint_list():
    """The JS suite mirrors the list by hand; this is the anti-drift assertion."""
    assert _versions_from(JS_TEST) == _versions_from(ENDPOINT), (
        "tests/contribute.test.js mirrors KNOWN_CONSENT_VERSIONS from "
        "functions/api/contribute.js by hand (ESM/CJS boundary). They have drifted, "
        "so the JS tests are asserting against a list the endpoint does not use."
    )


def test_endpoint_rejects_an_absent_or_unknown_version():
    """An unrecognised version must fail loud, never fall through to a default.

    Source-scanned rather than executed: contribute.js is a Cloudflare Pages
    Function (ESM, needs a Request/FormData/env runtime), so pytest cannot
    invoke it. What is checkable here is that the guard exists, rejects, and
    sits BEFORE the send -- the properties a silent default would break.
    """
    source = ENDPOINT.read_text(encoding="utf-8")

    guard = source.find("KNOWN_CONSENT_VERSIONS.includes(")
    assert guard != -1, "contribute.js never tests the posted version for membership"

    # The guard is a rejection, not a warning: a 400 return inside the block.
    tail = source[guard : guard + 500]
    assert "return textResponse(400" in tail, (
        "the consent-version check does not return a 400; an unknown version "
        "would fall through and be treated as consent to the current wording"
    )

    # The assignment itself must not carry a fallback. Scan the whole statement,
    # not a keyword-adjacent window: the value is wrapped (`clean(form.get(...), 32)`),
    # so a pattern anchored near "consent_version" sits on the wrong side of the
    # closing parens and matches nothing however the default is written. That exact
    # hole let a `|| "2026-07-28"` default pass this gate when it was first written.
    expression = assignment_expression(source, "consentVersion")
    assert not re.search(r"\|\||\?\?", expression), (
        "contribute.js defaults consent_version when absent "
        f"({expression.strip()!r}); that silently attributes the current "
        "label to a member who never saw it"
    )

    # And the accepted version reaches the record, or nothing downstream can read it.
    assert "Consent label version:" in source, (
        "the accepted consent version is never written into the emailed record, "
        "so no later export can tell which label the member agreed to"
    )
    assert source.find("Consent label version:") > guard, (
        "the record line is emitted before the guard runs"
    )
