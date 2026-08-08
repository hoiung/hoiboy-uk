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


def _collapse(text: str, which: set[int]) -> str:
    """Collapse the named marker pairs, leaving their copy in the file.

    The copy moves to just after the now-empty pair, so every OTHER rule in the
    gate still finds it. Only the voice guard's reach changes, which is the point:
    an attack that also deleted the copy would be caught by the content rules and
    would prove nothing about the marker rule.
    """
    out, last = [], 0
    for i, m in enumerate(gate._MARKER_PAIR.finditer(text)):
        out.append(text[last : m.start()])
        out.append(
            gate.MARKER_OPEN + gate.MARKER_CLOSE + m.group(1) if i in which else m.group(0)
        )
        last = m.end()
    out.append(text[last:])
    return "".join(out)


def test_markers_that_enclose_nothing_are_caught(clean):
    """Present and balanced was the whole rule, and it protected nothing.

    Collapsing each pair to `<!-- iamhoi --><!-- iamhoiend -->` and leaving the copy
    below it keeps opens/closes at 2/2 and every other rule green. The voice guard is
    marker-driven and default-SKIP, so it then scans nothing and reports OK -- which
    is verbatim the outcome this gate's own error message says the rule prevents.

    The gate was checking that the markers EXIST, not that they DO anything. Ralph
    round 7 tier 3 found it one round after the surrounding rules were hardened.
    """
    collapsed = _collapse(clean, {0, 1})
    assert collapsed != clean
    assert collapsed.count(gate.MARKER_OPEN) == clean.count(gate.MARKER_OPEN), (
        "the fixture must keep the markers balanced, or this passes via the "
        "unbalanced rule and proves nothing about enclosure"
    )
    assert "We do not send anything about" in collapsed, (
        "the copy must still be present, just outside the guarded region"
    )

    problems = gate.failures(collapsed)
    assert any("enclose only 0 characters of prose" in p for p in problems), problems


@pytest.mark.parametrize("index", [0, 1])
def test_collapsing_a_single_marker_pair_is_caught(clean, index):
    """The repair for the above was itself defeated, and BOTH ways round.

    It compared a floor against the SUM across pairs, so either pair could be
    collapsed on its own while the other alone cleared 500. Measured before the
    fix: pair 0 collapsed -> 0 problems, pair 1 collapsed -> 0 problems. Pair 1 is
    the footer, carrying the operator's no-spam promise and the unsubscribe control,
    so the smaller and more dangerous region was the cheaper one to strip.

    Ralph round 7 restart 2 tier 2 reported the pair-1 case; re-deriving it found
    pair 0 open too. Parametrised so neither can regress alone.
    """
    collapsed = _collapse(clean, {index})
    assert collapsed != clean
    assert collapsed.count(gate.MARKER_OPEN) == clean.count(gate.MARKER_OPEN)
    assert "We do not send anything about" in collapsed

    problems = gate.failures(collapsed)
    assert any("OUTSIDE the iamhoi markers" in p for p in problems), (
        f"collapsing pair {index} must be caught on its own, not only when both "
        f"pairs go together: {problems}"
    )


def test_a_marker_pair_full_of_markup_but_no_copy_does_not_satisfy_the_floor(clean):
    """The floor counted RAW CHARACTERS, so table scaffolding answered it.

    Measured on the shipped template: pair 0 encloses 3427 raw characters of which
    148 are prose. A pair wrapped round 600+ characters of `<table>` markup and no
    words at all therefore cleared a 500-character floor while guarding no copy --
    the same "answered by the wrong thing" shape as the gate being satisfied by its
    own comments, and as the 600px rule being satisfied by the hero image.
    """
    scaffold = '<table role="presentation"><tr><td></td></tr></table>' * 12
    assert len(scaffold) > gate.MIN_GUARDED_PROSE, (
        "the scaffold must be longer than the floor, or this proves nothing about "
        "which substance is being counted"
    )
    assert gate._visible_prose(scaffold) == "", "the scaffold must carry no prose"

    attacked = _collapse(clean, {0, 1}).replace(
        "<table", f"{gate.MARKER_OPEN}{scaffold}{gate.MARKER_CLOSE}<table", 1
    )
    problems = gate.failures(attacked)
    assert any("characters of prose" in p for p in problems), problems


@pytest.mark.parametrize(
    "channel,fragment",
    [
        ("alt", '<img src="x.png" alt="{copy}">'),
        ("title", '<a href="https://hoiboy.uk/" title="{copy}">x</a>'),
        ("aria-label", '<span aria-label="{copy}">x</span>'),
        ("single-quoted alt", "<img src='x.png' alt='{copy}'>"),
    ],
)
def test_copy_smuggled_through_a_readable_attribute_is_caught(clean, channel, fragment):
    """Deleting a tag deletes its attributes, and two of them carry copy.

    `alt` is not decorative in email: most clients block images by default, so
    alt text is what the reader actually reads -- and this template already puts
    real copy there (`alt="%%HERO_ALT%%"`, substituted at send time from the
    post's og:image:alt). `title` is a tooltip, `aria-label` is what a screen
    reader announces.

    Measured before the fix: 100 characters appended outside the markers through
    any of these left the unguarded count at 16 and the gate green. Ralph round 7
    restart 3 tier 2 reported `alt`; sweeping the class found `title` and the
    single-quoted form open too, and found that `aria-label` only LOOKED closed
    because the probe's fixture tripped an unrelated table rule. Hence the
    assertion below names the marker message specifically -- passing because some
    other rule fired is how that near-miss happened.
    """
    copy = (
        "This sentence is well over forty characters of ordinary prose and a "
        "reader can see every word of it."
    )
    assert len(copy) > gate.MAX_UNGUARDED_PROSE
    attacked = clean.rstrip() + "\n" + fragment.format(copy=copy) + "\n"
    assert attacked != clean, f"the {channel} fixture changed nothing"

    problems = gate.failures(attacked)
    assert any("OUTSIDE the iamhoi markers" in p for p in problems), (
        f"copy carried in {channel} outside the markers must be caught by the "
        f"MARKER rule, not incidentally by another one: {problems}"
    )


@pytest.mark.parametrize("attr", ["data-alt", "data-title", "x-aria-label"])
def test_a_hyphen_prefixed_attribute_is_not_mistaken_for_copy(attr):
    """`\\b` sits between a hyphen and a letter, so `data-alt` matched `alt`.

    Ralph round 7 restart 4 tier 1 found the over-match and read it as a
    smuggling hole. It is the opposite: an over-matched attribute is COUNTED, so
    the value is detected, not hidden. The real damage is that invisible text
    then ANSWERS the rule -- see the floor test below. Pinned in both directions
    because a future "simplification" back to `\\b` looks harmless.
    """
    payload = "sixty characters of prose that a cap of forty must not permit!"
    assert payload not in gate._visible_prose(f'<div {attr}="{payload}"></div>')


@pytest.mark.parametrize("attr", ["salt", "xtitle", "subtitle"])
def test_an_attribute_merely_ending_in_a_readable_name_is_not_counted(attr):
    """The opposite over-reach, pinned so the lookbehind is not widened.

    `salt` ends in `alt` and is not copy. These never matched, and the fix for
    the hyphen case must not make them match.
    """
    payload = "sixty characters of prose that a cap of forty must not permit!"
    assert payload not in gate._visible_prose(f'<div {attr}="{payload}"></div>')


def test_invisible_attribute_text_cannot_answer_the_guarded_prose_floor(clean):
    """The false-PASS direction, which is the one that actually ships copy.

    Over-counting is not merely untidy here. Gut a marker pair of its real copy,
    pad it with `data-alt` text no reader can see, and the floor is satisfied by
    the padding: measured before the fix, 400 characters of padding put guarded
    prose at 562 against a floor of 300 with the gate green.
    """
    pairs = list(gate._MARKER_PAIR.finditer(clean))
    assert len(pairs) == 2, f"the template should carry two marker pairs, found {len(pairs)}"
    footer = pairs[1]
    padding = "x" * 400
    assert len(padding) > gate.MIN_GUARDED_PROSE

    attacked = (
        clean[: footer.start()]
        + gate.MARKER_OPEN
        + f'<div data-alt="{padding}"></div>'
        + gate.MARKER_CLOSE
        + clean[footer.end() :]
    )
    assert attacked != clean
    assert attacked.count(gate.MARKER_OPEN) == clean.count(gate.MARKER_OPEN)

    problems = gate.failures(attacked)
    assert any("enclose only" in p for p in problems), (
        f"invisible padding must not satisfy the guarded-prose floor: {problems}"
    )


def test_entity_padding_cannot_answer_the_guarded_prose_floor(clean):
    """The same padding attack as `data-*`, in a different substance.

    An undecoded entity is measured as its SOURCE characters, so `&nbsp;` scored
    6 apiece against a floor meant to count copy. Measured before entities were
    decoded: 80 non-breaking spaces (480 characters that render as whitespace)
    replacing the footer's real copy put guarded prose at 642 against a floor of
    300, gate green.

    Found by sweeping the class rather than waiting for it to be reported --
    five instances of "this rule is answered by the wrong substance" had already
    been fixed one at a time, which is how a class gets serialised across
    restarts instead of closed.
    """
    pairs = list(gate._MARKER_PAIR.finditer(clean))
    assert len(pairs) == 2
    footer = pairs[1]
    padding = "&nbsp;" * 80
    assert len(padding) > gate.MIN_GUARDED_PROSE, "the padding must out-bulk the floor"

    attacked = (
        clean[: footer.start()]
        + gate.MARKER_OPEN
        + f"<p>{padding}</p>"
        + gate.MARKER_CLOSE
        + clean[footer.end() :]
    )
    assert attacked != clean
    problems = gate.failures(attacked)
    assert any("enclose only" in p for p in problems), (
        f"whitespace entities must not satisfy the prose floor: {problems}"
    )


def test_entity_encoded_copy_is_measured_as_the_words_it_renders_as(clean):
    """Decoding cuts both ways, and the other way matters too.

    Copy written as numeric references must be measured as the copy it renders
    as -- not as inflated source text, and not missed. This is the readable
    half of the same decode.
    """
    copy = "This is plainly readable copy and it is far longer than the cap allows."
    encoded = "".join(f"&#{ord(c)};" for c in copy)
    assert copy not in encoded, "the fixture must actually be encoded"
    assert gate._visible_prose(f"<p>{encoded}</p>") == copy

    attacked = clean.rstrip() + f"\n<p>{encoded}</p>\n"
    assert attacked != clean
    problems = gate.failures(attacked)
    assert any("OUTSIDE the iamhoi markers" in p for p in problems), problems


def test_stylesheet_text_is_not_counted_as_copy(clean):
    """The inverse error: a rule that over-counts fails on ordinary edits.

    Tag-stripping removes `<style>` but leaves the CSS between the tags, which
    would land in the unguarded bucket and fail the gate on a stylesheet nobody
    reads. The shipped template has no real <style> block, so this guards a
    future edit rather than a present one.
    """
    css = "<style>.wrap{padding:24px}.btn{background:#c0533a;border-radius:2px}</style>"
    assert len(gate._visible_prose(css)) == 0, gate._visible_prose(css)

    attacked = clean.rstrip() + "\n" + css + "\n"
    assert attacked != clean
    assert gate.failures(attacked) == [], (
        "adding a stylesheet must not fail the marker rule; CSS is not copy"
    )


def test_copy_added_outside_the_markers_is_caught(clean):
    """The case the old rule could not see AT ALL.

    Every previous version asked only how much sat inside the markers, so new copy
    appended outside them left the answer unchanged and shipped unscanned. This is
    the realistic regression: nobody collapses a marker pair on purpose, but adding
    a line to the footer without noticing the markers end above it is one careless
    edit away.
    """
    added = "<p>PS. we also run paid workshops, and will mail you when booking opens.</p>"
    attacked = clean + "\n" + added
    problems = gate.failures(attacked)
    assert any("OUTSIDE the iamhoi markers" in p for p in problems), problems
    assert any("paid workshops" in p for p in problems), (
        f"the message must quote the offending copy so the fix is obvious: {problems}"
    )


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
    assert any("content column" in p for p in problems), problems


def test_missing_accent_is_caught(clean):
    problems = gate.failures(clean.replace("#c0533a", "#000000"))
    assert any("terracotta" in p for p in problems), problems


def test_missing_presentation_table_is_caught(clean):
    problems = gate.failures(clean.replace('role="presentation"', 'role="none"'))
    assert any("role=" in p for p in problems), problems


# --------------------------------------------------------------------------
# The gate was reading its own documentation (blog-priv#81 class sweep)
#
# The template opens with ~50 lines of engineering notes that necessarily QUOTE
# the literals these rules search for. Measured on the shipped file:
# `role="presentation"` appears 5 times in the raw text and 4 in the markup;
# `#c0533a` 10 times and 9. So every whole-file substring rule was satisfied by
# the prose before a single real element was read, and the sweep proved the
# consequence: all four tables could become role="none" and all nine accent
# colours could go black, with this gate green.
#
# The rules now read the markup body. These tests mutate the MARKUP ONLY and
# leave the comments intact, which is the shape the old gate could not see.
# --------------------------------------------------------------------------


def markup_only(text: str, old: str, new: str) -> str:
    """Rewrite `old` everywhere EXCEPT inside html comments.

    A plain `.replace` hits the engineering notes too, which is precisely what
    made the old rules look tested: the fixture destroyed the evidence and the
    prose at the same time, so the gate turned red for the wrong reason.
    """
    parts = re.split(r"(<!--.*?-->)", text, flags=re.S)
    return "".join(
        part if part.startswith("<!--") else part.replace(old, new)
        for part in parts
    )


def test_the_fixture_really_does_leave_the_comments_alone(clean):
    """Guard the guard: if markup_only stopped working, every test below would
    pass for the wrong reason."""
    mutated = markup_only(clean, 'role="presentation"', 'role="none"')
    assert mutated != clean
    assert '<!-- iamhoi -->' in mutated
    assert mutated.count('role="presentation"') == 1, (
        "exactly the one occurrence inside the explanatory comment must survive"
    )


def test_a_single_table_losing_its_role_is_caught(clean):
    """The old rule was `'role="presentation"' not in text`, a whole-file
    membership test over four tables plus one comment, so it passed while any one
    of them still carried it. The outer table is the one that matters most: without
    it a screen reader announces the entire email as a data table."""
    # Searched in the MARKUP, not in `clean`. The comment at email.html:6 explains
    # the technique by quoting `<table role="presentation">`, so a regex over the
    # raw file finds the prose first and the "mutation" edits the documentation --
    # which is the same confusion between the file and the email that this whole
    # section exists to fix, reproduced one level up in the test.
    outer = re.search(r'<table[^>]*role="presentation"[^>]*>', gate.strip_comments(clean))
    assert outer is not None, "no real table carries the role in the shipped markup"
    broken = clean.replace(outer.group(0), outer.group(0).replace(' role="presentation"', ""), 1)
    assert broken != clean

    problems = gate.failures(broken)
    assert any("of 4 <table> elements" in p for p in problems), problems


def test_the_accent_going_black_in_the_markup_is_caught(clean):
    """Nine real accent occurrences (the border, the button, six link colours) could
    all go black, because one mention of the hex in a prose comment satisfied the
    rule. The rule's own message says the accent "must be a literal hex, not a
    token" -- it could not tell a literal hex in a sentence from one in a style."""
    problems = gate.failures(markup_only(clean, "#c0533a", "#000000"))
    assert any("terracotta" in p for p in problems), problems


def test_the_content_column_losing_its_width_is_caught(clean):
    """`max-width:600px` occurs TWICE: on the content column and on the hero <img>.

    So a membership test over the markup was answered by the image while the column
    itself went full-bleed -- the same vacuity as reading the comments, one level
    in. The existing sibling test replaces every occurrence at once and cannot see
    it. Matched on a <table> carrying the width instead.
    """
    broken = clean.replace(
        'align="center" style="max-width:600px;width:100%;',
        'align="center" style="max-width:100%;width:100%;',
        1,
    )
    assert broken != clean
    assert "max-width:600px" in broken, (
        "the hero image still carries it, which is exactly why the old rule passed"
    )
    problems = gate.failures(broken)
    assert any("content column" in p for p in problems), problems


def test_a_go_template_action_hidden_in_a_comment_is_caught(clean):
    """This rule is the one place that MUST read the comments.

    Hugo parses every file under layouts/ as a Go template, html comments included,
    so a double-curly tag written into a comment fails the whole site build. The
    existing test puts the tag in the markup, where any comment-blind version of
    the rule still catches it, so the rule's entire stated rationale was untested.
    """
    broken = clean.replace(
        "<!-- iamhoi -->",
        "<!-- iamhoi. Brevo writes it as {" + "{contact.FIRSTNAME}" + "} -->",
        1,
    )
    assert broken != clean
    problems = gate.failures(broken)
    assert any("Go-template action" in p for p in problems), problems


def test_a_call_to_action_that_is_not_the_accent_colour_is_caught(clean):
    """The button is the one element where losing the accent is most visible, and
    the whole-file colour rule could never have seen it on its own."""
    cell = re.search(r'<td[^>]*bgcolor="#c0533a"', clean)
    assert cell is not None, "the CTA button cell is not in the shipped template"
    broken = clean.replace(cell.group(0), cell.group(0).replace("#c0533a", "#333333"), 1)

    problems = gate.failures(broken)
    assert any("call-to-action button is" in p for p in problems), problems


@pytest.mark.parametrize("threshold_probe", [1, 2])
def test_the_font_declaration_floor_is_a_real_floor(clean, threshold_probe):
    """Round 4 closed this rule only at ZERO.

    Its test strips EVERY declaration and asserts the count is 0, so it pins "at
    least one" and says nothing about the threshold: `< 3` could be lowered to
    `< 1` or `< 2` with the suite green. Reduced to a real count here instead, so
    the boundary itself is exercised.
    """
    stripped = gate._FONT_DECL.sub("color:#111", clean, count=len(gate._FONT_DECL.findall(clean)) - threshold_probe)
    assert len(gate._FONT_DECL.findall(stripped)) == threshold_probe
    problems = gate.failures(stripped)
    assert any(f"only {threshold_probe} font-family" in p for p in problems), problems


def test_a_generic_family_that_is_not_at_the_end_is_caught(clean):
    """The `$` anchor IS the rule. The message promises the declarations "end in a
    generic family"; unanchored, a generic appearing anywhere in the stack
    satisfies it, so `font-family:sans-serif,Arial` would pass a check that claims
    to have verified a fallback."""
    decl = gate._FONT_DECL.findall(clean)[0]
    broken = clean.replace(decl, "font-family:serif,'Some Face',Arial", 1)
    problems = gate.failures(broken)
    assert any("generic family" in p for p in problems), problems


@pytest.mark.parametrize("css", ["display:grid;", "display: flex;", "display:  grid;"])
def test_the_other_unsupported_layouts_are_caught(clean, css):
    """Two untested halves of one rule. `grid` was exercised by nothing, and the
    `\\s*` whitespace tolerance by nothing either -- every test injected the
    no-space `display:flex;`, while `display: flex` with a space is how CSS is
    ordinarily written and what every formatter emits."""
    problems = gate.failures(clean.replace("padding:24px 12px;", css, 1))
    assert any("flex/grid" in p for p in problems), problems


def test_a_compliant_template_exits_zero_through_the_real_entry_point(tmp_path):
    """main()'s SUCCESS path was driven by nothing.

    Both entry-point tests exercise failures and assert `rc != 0`, so `return 0`
    could become `return 1` and the gate would reject a perfectly valid template
    while printing "OK". That blocks every commit touching the template, which is
    loud -- but it is loud in a way that teaches the next person to bypass the hook.
    """
    skel = tmp_path / "scripts"
    skel.mkdir()
    for name in ("check_newsletter_template.py", "gate_coverage.py", "newsletter_render.py"):
        (skel / name).write_text((SCRIPTS / name).read_text(encoding="utf-8"), encoding="utf-8")
    template = tmp_path / "layouts" / "_partials" / "newsletter" / "email.html"
    template.parent.mkdir(parents=True)
    template.write_text(REAL_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(skel / "check_newsletter_template.py")],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"the shipped template must pass: {proc.stderr}"
    assert "OK:" in proc.stdout


def test_a_template_that_cannot_be_decoded_is_a_coverage_failure(tmp_path):
    """An unreadable surface is the vacuity problem wearing a different coat.

    Invalid UTF-8 in the template used to kill this gate with a raw
    UnicodeDecodeError traceback. gate_coverage ships require_readable for exactly
    that, and its docstring states the rule this gate was breaking: a gate cannot
    assert an absence in a surface it failed to parse.
    """
    skel = tmp_path / "scripts"
    skel.mkdir()
    for name in ("check_newsletter_template.py", "gate_coverage.py", "newsletter_render.py"):
        (skel / name).write_text((SCRIPTS / name).read_text(encoding="utf-8"), encoding="utf-8")
    template = tmp_path / "layouts" / "_partials" / "newsletter" / "email.html"
    template.parent.mkdir(parents=True)
    template.write_bytes(b'\xff\xfe<table role="presentation">\x80\x81')

    proc = subprocess.run(
        [sys.executable, str(skel / "check_newsletter_template.py")],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "cannot read" in proc.stderr, proc.stderr
    assert "Traceback" not in proc.stderr, (
        "a coverage failure must be a diagnostic, not a stack trace:\n" + proc.stderr
    )


def test_gate_floors_when_the_template_is_absent(tmp_path):
    """Coverage floor, driven through the real entry point.

    A copy of scripts/ in an empty directory makes the gate resolve that directory
    as the repo, so the template is genuinely missing rather than stubbed out.
    """
    skel = tmp_path / "scripts"
    skel.mkdir()
    # newsletter_render is copied too: the gate imports strip_comments from it,
    # so a skeleton without it fails on the import rather than on the contract.
    for name in ("check_newsletter_template.py", "gate_coverage.py", "newsletter_render.py"):
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
    # newsletter_render is copied too: the gate imports strip_comments from it,
    # so a skeleton without it fails on the import rather than on the contract.
    for name in ("check_newsletter_template.py", "gate_coverage.py", "newsletter_render.py"):
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
