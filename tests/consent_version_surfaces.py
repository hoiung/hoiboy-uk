"""Shared extraction for the consent-version traceability gates.

Two consent surfaces now exist in this repo and both need the same three reads:
the version a form renders in its hidden input, the list an endpoint accepts,
and the list a JS test mirrors by hand. They are:

  1. the AGIT community form (agit-ops#3) -- an Article 9(2)(a) explicit-consent
     surface, whose evidence is an emailed record, and
  2. the newsletter subscribe form (#56) -- an Article 6(1)(a) surface, whose
     evidence is a CONSENT_VERSION attribute on the Brevo contact.

Their ASSERTIONS differ, because what "the version reached the record" means
differs. Their PARSING does not, so it lives here once. Copying it would mean a
fix to the hidden-input pattern landing in one gate and not the other, which is
the same silent-drift failure these gates exist to catch, one level up.

Not named test_*.py on purpose: it holds no tests, so pytest does not collect it
and `test_every_test_file_is_actually_run_by_pytest_in_ci` does not require it
to appear in a ci.yml pytest invocation.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The hidden input a consent form renders. Order-sensitive by design: it matches
# the shape both forms actually ship, and a rewrite that reorders the attributes
# should fail loud here rather than silently stop finding the version.
_HIDDEN_RE = re.compile(
    r"""<input\s+type=["']hidden["']\s+name=["']consent_version["']\s+value=["']([^"']+)["']"""
)


def js_string_list(path: Path, symbol: str = "KNOWN_CONSENT_VERSIONS") -> list[str]:
    """Extract the JS array-literal of strings assigned to ``symbol``.

    ``symbol`` is a parameter because the JS-side mirror in a test file is named
    for what it is (``KNOWN_CONSENT_VERSIONS_MIRROR``) rather than sharing the
    endpoint's name. The negative lookahead stops a search for the endpoint's
    symbol from matching a longer identifier that merely starts with it, so
    passing the wrong name fails loud instead of asserting against the mirror.
    """
    pattern = re.compile(
        rf"{re.escape(symbol)}(?![A-Za-z0-9_])\s*=\s*\[([^\]]*)\]"
    )
    match = pattern.search(path.read_text(encoding="utf-8"))
    assert match, f"no {symbol} array literal found in {path.name}"
    return re.findall(r"""["']([^"']+)["']""", match.group(1))


def hidden_input_version(path: Path) -> str:
    """The consent_version a form renders, from its hidden input."""
    match = _HIDDEN_RE.search(path.read_text(encoding="utf-8"))
    assert match, f"{path.name} has no hidden consent_version input"
    return match.group(1)


def assignment_expression(source: str, name: str) -> str:
    """The right-hand side of ``const <name> = ...;``, whole statement.

    Scanning the whole statement rather than a keyword-adjacent window is
    load-bearing: the value is wrapped (``clean(form.get(...), 32)``), so a
    pattern anchored near "consent_version" sits on the wrong side of the
    closing parens and matches nothing however the default is written. That
    exact hole let a ``|| "<version>"`` default pass this gate when it was
    first written for the AGIT surface.
    """
    match = re.search(rf"const\s+{re.escape(name)}\s*=\s*(.+?);", source, re.DOTALL)
    assert match, f"no `const {name} = ...;` assignment found"
    return match.group(1)
