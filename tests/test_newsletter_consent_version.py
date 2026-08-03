"""Consent-label version traceability for the newsletter form (#56 AC 4.3).

The sibling of tests/test_agit_consent_version.py, for the second consent
surface in this repo. Recording THAT someone consented is not enough under
Article 7(1); the record has to show WHICH wording they agreed to, or a later
export cannot tell a pre-amendment subscriber from a post-amendment one.

Three surfaces have to agree and nothing at runtime couples them:

  1. the hidden input in layouts/_partials/subscribe-form.html
     (the version actually rendered to the reader),
  2. KNOWN_CONSENT_VERSIONS in functions/api/subscribe.js
     (the endpoint that accepts or rejects it),
  3. KNOWN_CONSENT_VERSIONS_MIRROR in tests/subscribe.test.js
     (a literal the JS suite declares so this gate has something to read;
     that suite asserts its own mirror against the loaded endpoint value, so
     the mirror cannot drift silently in the other direction either).

A wording change that bumps one and not the others fails silently in the worst
way: the form would post a version the endpoint rejects, and every submission
would 400 while the page still looked fine.

Why this is a sibling rather than a generalisation of the AGIT test: the two
surfaces share their PARSING (extracted to tests/consent_version_surfaces.py)
but not their ASSERTIONS. AGIT is an Article 9(2)(a) special-category surface
whose evidence is a line in an emailed record; this is an Article 6(1)(a)
marketing surface whose evidence is a CONSENT_VERSION attribute on the Brevo
contact. The last test below is where they genuinely differ.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from consent_version_surfaces import (  # noqa: E402
    REPO,
    assignment_expression,
    hidden_input_version,
    js_string_list,
)

FORM = REPO / "layouts" / "_partials" / "subscribe-form.html"
ENDPOINT = REPO / "functions" / "api" / "subscribe.js"
JS_TEST = REPO / "tests" / "subscribe.test.js"

JS_MIRROR_SYMBOL = "KNOWN_CONSENT_VERSIONS_MIRROR"


def test_form_hidden_version_is_accepted_by_the_endpoint():
    """The version the form renders must be one the endpoint accepts."""
    rendered = hidden_input_version(FORM)
    accepted = js_string_list(ENDPOINT)
    assert rendered in accepted, (
        f"subscribe-form.html posts consent_version={rendered!r} but subscribe.js "
        f"accepts {accepted!r}; every submission would be rejected with a 400"
    )


def test_js_test_mirror_matches_the_endpoint_list():
    """The JS suite declares the list by hand; this is the anti-drift assertion."""
    assert js_string_list(JS_TEST, JS_MIRROR_SYMBOL) == js_string_list(ENDPOINT), (
        "tests/subscribe.test.js declares KNOWN_CONSENT_VERSIONS_MIRROR by hand so "
        "this gate has a literal to read. It has drifted from "
        "functions/api/subscribe.js, so this gate is asserting against a list the "
        "endpoint does not use."
    )


def test_endpoint_rejects_an_absent_or_unknown_version():
    """An unrecognised version must fail loud, never fall through to a default.

    Source-scanned rather than executed HERE: tests/subscribe.test.js already
    executes the endpoint against every one of these cases. What this adds is
    the structural property that suite cannot state -- that the guard sits
    BEFORE the write and carries no default -- so a refactor that reorders the
    steps is caught even if the behavioural assertions were also weakened.
    """
    source = ENDPOINT.read_text(encoding="utf-8")

    guard = source.find("KNOWN_CONSENT_VERSIONS.includes(")
    assert guard != -1, "subscribe.js never tests the posted version for membership"

    tail = source[guard : guard + 500]
    assert "return textResponse(400" in tail, (
        "the consent-version check does not return a 400; an unknown version "
        "would fall through and be treated as consent to the current wording"
    )

    expression = assignment_expression(source, "consentVersion")
    assert not re.search(r"\|\||\?\?", expression), (
        f"subscribe.js defaults consent_version when absent ({expression.strip()!r}); "
        "that silently attributes the current label to a reader who never saw it"
    )


def test_the_accepted_version_reaches_the_stored_consent_record():
    """The version has to arrive at Brevo, or no export can evidence consent.

    This is where the newsletter surface differs from AGIT. AGIT writes a
    "Consent label version:" line into an emailed record; here the evidence is a
    CONSENT_VERSION contact attribute on the double-opt-in payload, alongside the
    submission timestamp. The Privacy Notice states that this pair is stored, so
    an endpoint that validated the version and then dropped it would make a
    published claim untrue while every other assertion above still passed.
    """
    source = ENDPOINT.read_text(encoding="utf-8")

    guard = source.find("KNOWN_CONSENT_VERSIONS.includes(")
    assert guard != -1

    # Anchored on the object-key form, NOT the bare name: `CONSENT_VERSION` is a
    # prefix of `KNOWN_CONSENT_VERSIONS`, so a bare find() matches the allowlist
    # constant (and its comment) hundreds of bytes earlier and the ordering
    # assertion below then compares the wrong two offsets.
    attribute = source.find("CONSENT_VERSION:")
    assert attribute != -1, (
        "the accepted consent version is never written into the Brevo contact "
        "attributes, so no later export can tell which label the reader agreed to"
    )
    assert attribute > guard, (
        "the consent attribute is built before the guard runs, so an unknown "
        "version would reach the record"
    )

    # And it must carry the VALIDATED value, not re-read the raw form field.
    payload = source[attribute : attribute + 120]
    assert "consentVersion" in payload, (
        "CONSENT_VERSION is not set from the validated `consentVersion` binding; "
        "re-reading the raw form value here would bypass the allowlist entirely"
    )

    assert "CONSENT_TIMESTAMP" in source, (
        "no submission timestamp is stored; the Privacy Notice states that the "
        "consent record carries both the wording and when it was accepted"
    )
