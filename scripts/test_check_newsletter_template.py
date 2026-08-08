#!/usr/bin/env python3
"""Unit tests for scripts/check_newsletter_template.py (blog-priv#81 AC 1.8).

These assert the MESSAGE, not just that something failed. A gate whose job is to
explain why the campaign copy is now unguarded is only useful if it says so; an
assertion on "returned a non-empty list" would keep passing if every message
degraded to "invalid".

The load-bearing case is `test_stripped_markers_are_caught`. Everything else here
guards construction details that a browser would forgive; that one guards the
failure the voice guard structurally cannot report, because deleting the markers
makes it scan nothing and print OK.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import check_newsletter_template as gate  # noqa: E402

REAL_TEMPLATE = gate.TEMPLATE


@pytest.fixture(scope="module")
def clean() -> str:
    assert REAL_TEMPLATE.is_file(), f"the template must exist to test against: {REAL_TEMPLATE}"
    return REAL_TEMPLATE.read_text(encoding="utf-8")


def test_the_shipped_template_passes_its_own_gate(clean):
    """If this fails the template is broken, not the test."""
    assert gate.failures(clean) == []


def test_stripped_markers_are_caught(clean):
    """The whole reason this gate exists.

    Removing the markers leaves prose that reads fine and a voice guard that
    reports OK over nothing. Nothing else in the repo turns red.
    """
    stripped = clean.replace(gate.MARKER_OPEN, "").replace(gate.MARKER_CLOSE, "")
    problems = gate.failures(stripped)
    assert problems, "stripping the iamhoi markers must fail the gate"
    assert any("default-SKIP" in p for p in problems), (
        f"the message must explain WHY a missing marker matters, not just that one is "
        f"absent, or the next reader deletes them again: {problems}"
    )


def test_unbalanced_markers_are_caught(clean):
    problems = gate.failures(clean.replace(gate.MARKER_CLOSE, "", 1))
    assert any("unbalanced" in p for p in problems), problems


def test_go_template_action_is_caught(clean):
    """A raw Brevo merge tag here fails the site build, not just the email."""
    broken = clean.replace("%%FIRSTNAME%%", "{" + "{contact.FIRSTNAME}" + "}")
    problems = gate.failures(broken)
    assert any("Go-template action" in p for p in problems), problems


def test_double_quoted_font_name_is_caught(clean):
    """The exact trap AC 1.3's extractor sets.

    A double-quoted face name truncates the declaration before the generic family,
    so the email silently loses its fallback while looking correct in a browser.
    """
    broken = clean.replace("'Source Serif 4'", '"Source Serif 4"', 1)
    problems = gate.failures(broken)
    assert any("generic family" in p for p in problems), problems


@pytest.mark.parametrize(
    "inject,needle",
    [
        ("color:var(--accent);", "custom property"),
        ("display:flex;", "custom property"),
    ],
)
def test_unsupported_css_is_caught(clean, inject, needle):
    problems = gate.failures(clean.replace("padding:24px 12px;", inject, 1))
    assert any(needle in p for p in problems), problems


def test_too_few_font_declarations_are_caught(clean):
    """The one contract rule with no test at all until round 4.

    Ralph round 4 tier 2 relaxed the threshold from `< 3` to `< 0`, which disables
    the rule outright, and the whole suite stayed green at 89 passed. Every other
    rule in this gate had a killing test; this one was enforced by nothing.

    It matters because the ladder is the point (D-1): the email mirrors the site's
    font stack and ends in a generic family, so a template that lost most of its
    declarations would still render, just not as the design.
    """
    stripped = gate._FONT_DECL.sub("color:#111", clean)
    assert len(gate._FONT_DECL.findall(stripped)) == 0, "fixture must remove them all"
    problems = gate.failures(stripped)
    assert any("font-family declaration" in p for p in problems), problems
    assert any("at least 3" in p for p in problems), problems


def test_inverting_the_consent_promise_is_caught(clean):
    """The most serious thing the class sweep found, and it is not a construction bug.

    The footer promises: "That is the only thing this list is used for. We do not
    send anything about our services, our consultancy or our products." A workflow
    sweep of the template AS DATA rewrote that into "We may also send occasional news
    about our services, our consultancy and our products" and it SURVIVED the whole
    suite, including the consent-version harness from #56.

    This is the operator's requirement in his own words: "you're making it sound like
    I will spam them with HOIBOY AI LTD services. it needs to be more about blog
    posts." The list was collected on a posts-only promise, so widening it is a
    consent question, not an editorial one (content/legal/privacy/index.md:77).

    Both directions are checked, because deleting the promise and contradicting it
    are different edits with the same effect on the reader.
    """
    dropped = clean.replace(
        "We do not send anything about\n            our services, our consultancy or our products.",
        "",
    )
    assert dropped != clean, "fixture must actually remove the promise"
    assert any("used ONLY for new posts" in p for p in gate.failures(dropped))

    inverted = clean.replace(
        "We do not send anything about",
        "We may also send occasional news about",
    )
    problems = gate.failures(inverted)
    assert any("admits sending non-post mail" in p for p in problems), problems


def test_an_invisible_unsubscribe_link_is_caught(clean):
    """Keeping the href while hiding the control passes every href assertion.

    The sweep coloured the anchor white and shrank it to 1px. %%UNSUBSCRIBE_URL%% was
    still present, so the merge-tag test stayed green, and the reader had no visible
    way out. That is a dark pattern and a PECR problem rather than a styling choice.
    """
    hidden = clean.replace(
        '<a href="%%UNSUBSCRIBE_URL%%" style="color:#c0533a;">',
        '<a href="%%UNSUBSCRIBE_URL%%" style="color:#ffffff;font-size:1px;">',
    )
    assert hidden != clean, "fixture must actually restyle the anchor"
    problems = gate.failures(hidden)
    assert any("invisible" in p or "visible" in p for p in problems), problems


def test_repointing_the_call_to_action_is_caught(clean):
    """%%POST_URL%% appears three times, so two of them survive a broken button.

    That is why a presence check is not enough and this test targets the BUTTON.
    Writing it the lazy way (replace the first occurrence) hits the hero image
    instead and trips a different rule, which is how the too-weak version of this
    gate rule was caught: the test failed for the right reason before the rule did.
    """
    button = re.search(r'<a href="%%POST_URL%%"[^>]*>Read the full post</a>', clean)
    assert button is not None, "the CTA button is not in the shipped template"
    broken = clean.replace(
        button.group(0),
        button.group(0).replace('href="%%POST_URL%%"', 'href="https://hoiboy.uk/"'),
    )
    assert broken != clean, "fixture must actually repoint the button"

    problems = gate.failures(broken)
    assert any("call to action points at" in p for p in problems), problems


def test_repointing_any_one_of_the_three_post_links_is_caught(clean):
    """The hero and the plain-text fallback matter too, not just the button."""
    hero = clean.replace(
        '<a href="%%POST_URL%%" style="display:block;',
        '<a href="https://hoiboy.uk/" style="display:block;',
        1,
    )
    assert hero != clean, "fixture must actually repoint the hero link"
    problems = gate.failures(hero)
    assert any("of the 3 post links" in p for p in problems), problems


def test_a_privacy_link_that_404s_is_caught(clean):
    """Nothing else reads layouts/.

    lychee.toml is scoped to './**/*.md' and scripts/validate_internal_links.py to
    content/, so a dead link in the email template is checked by no other gate in
    this repo. The sweep repointed it at /legal/privacy-notice/ and nothing noticed.
    """
    broken = clean.replace(
        "https://hoiboy.uk/legal/privacy/", "https://hoiboy.uk/legal/privacy-notice/"
    )
    assert broken != clean
    problems = gate.failures(broken)
    assert any("privacy-notice link" in p or "privacy" in p for p in problems), problems


def test_missing_content_column_is_caught(clean):
    """The last rule in this gate with no killing test.

    Ralph round 6 tier 3 disabled it and the suite stayed green. That is the same
    class round 4 found in the font-count rule one line above: this gate was tested
    rule by rule, and the sweep that followed covered send_newsletter.py only, so its
    siblings here went unexamined. Worth naming because it is exactly how a "class
    exhausted" claim goes stale.

    The 600px column is not decoration. It is the width every mail client's preview
    pane is built around; without it the email renders full-bleed in Outlook.
    """
    problems = gate.failures(clean.replace("max-width:600px", "max-width:100%"))
    assert any("600px content column" in p for p in problems), problems


def test_missing_accent_is_caught(clean):
    problems = gate.failures(clean.replace("#c0533a", "#000000"))
    assert any("terracotta" in p for p in problems), problems


def test_missing_presentation_table_is_caught(clean):
    problems = gate.failures(clean.replace('role="presentation"', 'role="none"'))
    assert any("table-based" in p for p in problems), problems


def test_gate_floors_when_the_template_is_absent(tmp_path):
    """Coverage floor, driven through the real entry point.

    A copy of scripts/ in an empty directory makes the gate resolve that directory
    as the repo, so the template is genuinely missing rather than stubbed out.
    """
    skel = tmp_path / "scripts"
    skel.mkdir()
    for name in ("check_newsletter_template.py", "gate_coverage.py"):
        (skel / name).write_text((SCRIPTS / name).read_text(encoding="utf-8"), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(skel / "check_newsletter_template.py")],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, (
        f"a missing template must not report success: rc={proc.returncode} "
        f"stdout={proc.stdout!r}"
    )
    assert "newsletter email template" in proc.stderr, proc.stderr


def test_a_violating_template_exits_non_zero_through_the_real_entry_point(clean, tmp_path):
    """The exit code is the ONLY thing pre-commit reads. Prove it moves.

    Every other test here calls `failures()` and asserts its message. That proves
    the contract logic and nothing about whether a violation actually stops a
    commit: `.pre-commit-config.yaml:113` runs this file as a command and keys
    solely on the return code, and `ci.yml` runs only the pytest, never the
    binary. So `main()`'s `return 1` is the sole production signal, and the
    sibling floor test above exercises the ABSENT-template branch instead, which
    exits through `require_examined` long before that line.

    Ralph round 3 tier 3 rewrote `return 1` to `return 0` and watched the gate
    print "1 contract violation(s)" while exiting 0, with the suite still green.
    That is round 2's finding on a new module: the guard was tested as a
    function and never through the command that calls it.
    """
    skel = tmp_path / "scripts"
    skel.mkdir()
    for name in ("check_newsletter_template.py", "gate_coverage.py"):
        (skel / name).write_text((SCRIPTS / name).read_text(encoding="utf-8"), encoding="utf-8")

    template = tmp_path / "layouts" / "_partials" / "newsletter" / "email.html"
    template.parent.mkdir(parents=True)
    # Present but non-compliant, so the coverage floor is satisfied and the run
    # reaches the contract check. Stripped markers are the violation this gate
    # was built for.
    template.write_text(
        clean.replace(gate.MARKER_OPEN, "").replace(gate.MARKER_CLOSE, ""),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(skel / "check_newsletter_template.py")],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, (
        f"a template that violates the contract must exit non-zero, or pre-commit "
        f"lets it through: rc={proc.returncode} stderr={proc.stderr!r}"
    )
    assert "contract violation" in proc.stderr, proc.stderr
