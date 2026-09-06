#!/usr/bin/env python3
"""Keep the newsletter email template's construction contract enforced (blog-priv#81 AC 1.8).

WHY THIS GATE EXISTS AT ALL, given the voice guard already reads the file.

`.pre-commit-config.yaml` already selects `layouts/.*\\.html` for `check-voice-tells`,
so the tells guard CAN open the template. Measured by mutation, both directions: a
banned word placed INSIDE an `<!-- iamhoi -->` region is caught and exits 1, and the
same word placed OUTSIDE one is not caught and exits 0. That second half is the
problem. The guard is marker-driven and default-SKIP, so deleting the markers does
not make it complain that the copy is now unprotected: it makes it scan nothing and
report OK. The gate is vacuous rather than absent, which is the harder failure to
notice, because the green tick still appears.

So this gate asserts the one thing the voice guard structurally cannot: that the
markers are still there. It also floors the rest of the Phase-1 construction
contract, because every one of those properties is invisible until an email lands
in somebody's inbox looking wrong, and by then it has been sent.

WHY NO ARGUMENTS. `tests/test_gate_vacuity.py` enrols every `scripts/check*.py` by
existence and runs it with no arguments against an empty-but-structurally-valid
skeleton, demanding a non-zero exit. A gate reading a fixed known path satisfies
that honestly: on an empty tree the template is missing and the coverage floor
fires, which is a real answer rather than a usage error wearing a compliant code.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_coverage import require_examined, require_readable
from newsletter_render import strip_comments

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "layouts" / "_partials" / "newsletter" / "email.html"

MARKER_OPEN = "<!-- iamhoi -->"
MARKER_CLOSE = "<!-- iamhoiend -->"

# THE MARKER RULE IS MEASURED IN PROSE, NOT IN CHARACTERS. Both numbers below come
# off the same ruler -- `_visible_prose`, which is what the reader sees and what the
# voice guard is there to police -- because two earlier versions of this rule were
# defeated by counting the wrong substance.
#
# Measured on the shipped template: pair 0 encloses 3427 raw characters but only 148
# characters of prose, and pair 1 encloses 977 raw for 334 prose. So a raw-character
# floor of 500 is satisfied by TABLE SCAFFOLDING: a marker pair wrapped around 600
# characters of <table> markup and no copy at all cleared it. Counting raw characters
# measured the markup and called it protection.
#
# The floors: the shipped template carries 496 characters of guarded prose and leaves
# 9 unguarded -- "hoiboy.uk", the header wordmark. (The spacer `&nbsp;` beside it used
# to bring that to 16; entities are decoded now, so it collapses to whitespace and
# scores nothing, which is the point of decoding them.)
MIN_GUARDED_PROSE = 300
MAX_UNGUARDED_PROSE = 40

# Matches how blog-priv#81 AC 1.3 extracts declarations. The character class stops
# at a double quote as well as a semicolon, which is why the template quotes face
# names with single quotes: a double-quoted name truncates the match before it
# reaches the generic family, and the declaration then fails this check while
# looking perfectly correct in a browser.
_FONT_DECL = re.compile(r'font-family:[^;"]*')
_GENERIC_TAIL = re.compile(r"(serif|sans-serif|monospace)\s*$")
_UNSUPPORTED_CSS = re.compile(r"var\(--|display:\s*(?:flex|grid)")

# Hugo parses every file under layouts/ as a Go template, INCLUDING inside html
# comments, so a Brevo merge tag written in its native double-curly form anywhere
# in this file fails the whole site build. Measured: exit 1 with the tag present,
# exit 0 with it removed. The template carries %%TOKEN%% placeholders instead and
# scripts/send_newsletter.py substitutes the real tags at build time.
_GO_TEMPLATE_ACTION = re.compile(r"\{\{")

_MARKER_PAIR = re.compile(re.escape(MARKER_OPEN) + r"(.*?)" + re.escape(MARKER_CLOSE), re.S)
_TAGS = re.compile(r"<[^>]+>")

# Copy reaches the reader through THREE channels, not one, and deleting a tag
# deletes two of them. `alt` is not decorative in email: most clients block
# images by default, so alt text is what the reader actually reads. `title` is a
# tooltip and `aria-label` is what a screen reader announces.
#
# Ralph round 7 restart 3 tier 2: an <img alt="..."> of 100 characters appended
# outside the markers left the unguarded count at 16 and the gate green, because
# `_TAGS` had already eaten the whole tag. Sweeping the class rather than the one
# reported channel: `title` and single-quoted `alt` were open the same way, and
# `aria-label` LOOKED closed only because the probe's fixture happened to trip an
# unrelated table rule.
#
# The list is closed deliberately. `href`/`src`/`style`/`class`/`role` are not
# copy, and counting them would fail the gate on ordinary markup. Add a channel
# here only if a reader can READ it, and add its test alongside.
#
# The lookbehind is `(?<![\w-])`, NOT `\b`. A word boundary sits between the
# hyphen and the `a` of `data-alt`, so `\b` also matched `data-alt`,
# `data-title` and `x-aria-label` -- attributes no reader can see. Ralph round 7
# restart 4 tier 1 spotted the over-match but read it as a smuggling hole; it is
# the opposite, and worse. Over-counting means invisible text ANSWERS the rule:
# measured, 400 characters of `data-alt` padding inside a gutted marker pair put
# guarded prose at 562 against a floor of 300 and the gate stayed green. A fifth
# way for this rule to be answered by the wrong substance.
#
# A name that merely ENDS in one of the tokens was never matched and still is
# not: `salt`, `xtitle` and `subtitle` are all correctly ignored.
_VISIBLE_ATTRS = re.compile(
    r"""(?<![\w-])(?:alt|title|aria-label)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I
)

# Stylesheet and script bodies survive tag-stripping (the tags go, the text
# between them stays) and would be counted as prose. No reader reads them. The
# shipped template has no <style> block -- the only `<style` in the file is
# inside the engineering notes at the top, which `strip_comments` removes -- so
# this guards a future edit rather than a present one.
_INERT_ELEMENTS = re.compile(r"<(style|script)\b[^>]*>.*?</\1\s*>", re.I | re.S)


def _visible_prose(text: str) -> str:
    """The words a reader actually sees: text nodes PLUS readable attributes.

    ENTITIES ARE DECODED, and that is a rule not a nicety. Left encoded, an
    entity is measured as its source characters, so `&nbsp;` scores 6 against a
    floor that is supposed to count copy. Measured before this line existed: 80
    non-breaking spaces -- 480 characters that render as whitespace -- put
    guarded prose at 642 against a floor of 300 and the gate stayed green, the
    same padding attack as the `data-*` one, in a different substance.

    Decoding fixes both directions at once. `&nbsp;` becomes \\xa0, which
    `str.split()` treats as whitespace and drops, so padding scores nothing; and
    copy written as `&#72;&#105;` decodes to the words it renders as, so it is
    measured as the copy it is rather than as inflated source text.
    """
    body = _INERT_ELEMENTS.sub(" ", strip_comments(text))
    readable = [double or single for double, single in _VISIBLE_ATTRS.findall(body)]
    return " ".join(html.unescape(_TAGS.sub(" ", body) + " " + " ".join(readable)).split())


def _prose_split(text: str) -> tuple[str, str]:
    """Split the template's prose into (inside the markers, outside them).

    Spans are cut from the RAW text, because the markers are html comments and
    `_visible_prose` deletes them. Both halves are then measured on the same
    ruler, which is the whole point: the previous rule compared a raw-character
    count against a floor and was answered by markup.
    """
    guarded, outside, last = [], [], 0
    for m in _MARKER_PAIR.finditer(text):
        outside.append(text[last : m.start()])
        guarded.append(m.group(1))
        last = m.end()
    outside.append(text[last:])
    return _visible_prose(" ".join(guarded)), _visible_prose(" ".join(outside))


def failures(text: str) -> list[str]:
    """Every contract violation in the template, so one run reports them all.

    TWO SURFACES, AND THE SPLIT IS THE WHOLE POINT OF THIS FUNCTION.

    `text` is the file as written. `body` is the file with html comments removed,
    which is the markup a mail client actually receives (the sender strips comments
    before building an email, scripts/newsletter_render.py:87).

    Every rule below that asks "does the EMAIL have property X" now reads `body`,
    because the template DOCUMENTS ITSELF: ~50 lines of engineering notes at the
    top quote the very literals these rules search for. Measured on the shipped
    file: `role="presentation"` appears 5 times in the raw text and 4 in the markup,
    `#c0533a` 10 times and 9. So a whole-file substring search was satisfied by the
    prose before a single real table or link was read, and the class sweep confirmed
    the consequence: every one of the four tables could become role="none", and
    every one of the nine accent colours could go black, with this gate green.

    The rules that ask about the FILE rather than the email keep reading `text`:
    the iamhoi markers ARE comments, and the Go-template rule exists precisely
    because Hugo parses inside comments too.
    """
    out: list[str] = []
    body = strip_comments(text)

    opens, closes = text.count(MARKER_OPEN), text.count(MARKER_CLOSE)
    if opens == 0:
        out.append(
            f"no {MARKER_OPEN} region: the voice guard is marker-driven and "
            f"default-SKIP, so with the markers gone it scans nothing and reports OK. "
            f"The campaign copy would ship unguarded with a green tick."
        )
    elif opens != closes:
        out.append(f"unbalanced markers: {opens} {MARKER_OPEN} vs {closes} {MARKER_CLOSE}")
    else:
        # PRESENT AND BALANCED IS NOT ENOUGH, AND NEITHER IS "ENCLOSES SOMETHING".
        #
        # This rule has now been defeated twice, the same way both times: it was
        # answered by something other than the thing it asks about.
        #
        #   1. Counting markers was the whole rule, so two adjacent markers passed
        #      while protecting nothing (Ralph round 7 tier 3).
        #   2. The repair counted RAW CHARACTERS and summed them ACROSS pairs, which
        #      failed twice over (Ralph round 7 restart 2 tier 2, plus a second case
        #      found re-deriving it). Summing meant either pair could be collapsed
        #      on its own while the other alone cleared the floor -- including the
        #      footer pair, which carries the operator's no-spam promise and the
        #      unsubscribe control. And counting raw characters measured MARKUP:
        #      pair 0 is 3427 raw characters of which 148 are prose, so a pair
        #      wrapped around table scaffolding and no copy cleared a 500 floor.
        #
        # So the question is no longer "how much is inside the markers" but "is any
        # of the reader-visible copy OUTSIDE them", which is the property the voice
        # guard actually depends on. Collapsing a pair pushes that pair's copy into
        # the unguarded half and fails; so does adding new copy outside the markers,
        # which the old rule could never see at all.
        guarded, unguarded = _prose_split(text)
        if len(guarded) < MIN_GUARDED_PROSE:
            out.append(
                f"the iamhoi markers enclose only {len(guarded)} characters of prose "
                f"(expected at least {MIN_GUARDED_PROSE}). The voice guard is "
                f"marker-driven and default-SKIP, so copy outside them ships "
                f"unscanned while every count in this gate still passes."
            )
        if len(unguarded) > MAX_UNGUARDED_PROSE:
            out.append(
                f"{len(unguarded)} characters of reader-visible copy sit OUTSIDE the "
                f"iamhoi markers (at most {MAX_UNGUARDED_PROSE} may): {unguarded[:120]!r}. "
                f"The voice guard never reads it. Move it inside a marker pair."
            )

    if _GO_TEMPLATE_ACTION.search(text):
        out.append(
            "contains a Go-template action '{{'. Hugo parses this file (comments "
            "included) and will fail the site build. Use a %%TOKEN%% placeholder "
            "and let the sender emit the real Brevo tag."
        )

    decls = _FONT_DECL.findall(body)
    if len(decls) < 3:
        out.append(f"only {len(decls)} font-family declaration(s); the template should carry at least 3")
    bare = [d for d in decls if not _GENERIC_TAIL.search(d)]
    if bare:
        out.append(
            f"{len(bare)} font-family declaration(s) do not end in a generic family, "
            f"so the email has no fallback where the face is absent: {bare[:3]}"
        )

    if _UNSUPPORTED_CSS.search(body):
        out.append("uses a CSS custom property or flex/grid; none survives the Outlook Word engine")

    # EVERY table, not "at least one somewhere in the file". A whole-file
    # membership test passes while three of four tables carry role="none", and the
    # outer table is the one that matters most: a screen reader announces the whole
    # email as a data table if it is missing there.
    tables = body.count("<table")
    presentation = body.count('role="presentation"')
    if presentation < tables:
        out.append(
            f'only {presentation} of {tables} <table> elements carry '
            f'role="presentation"; every one must, or a screen reader announces the '
            f"layout scaffolding as tabular data"
        )
    if tables == 0:
        out.append("no <table> in the markup; the layout must be table-based for mail clients")

    # Matched on a TABLE carrying the width, not on the string anywhere in the
    # markup. `max-width:600px` occurs twice: once on the content column and once
    # on the hero <img>, so a plain membership test was satisfied by the image
    # while the column itself went full-bleed. Same vacuity as the comments, one
    # level in -- the rule was being answered by something that is not the thing it
    # asks about.
    if not re.search(r"<table[^>]*max-width:600px", body):
        out.append(
            "no <table> carries max-width:600px; the content column is the width "
            "every mail client's preview pane is built around, and without it the "
            "email renders full-bleed in Outlook"
        )
    if "#c0533a" not in body.lower():
        out.append("the terracotta accent #c0533a is absent; it must be a literal hex, not a token")

    # ---------------------------------------------------------------------
    # The template as DATA, not as construction (blog-priv#81, class sweep).
    #
    # Everything above checks how the email is BUILT. Nothing checked what it
    # SAYS or where it POINTS, and a workflow sweep of the template as an
    # artefact found fourteen mutations that survived the whole suite. The
    # worst inverted the consent promise below; the rest silently broke the
    # unsubscribe control, the call to action, and the privacy link.
    # ---------------------------------------------------------------------

    # The operator's requirement, in his own words: "you're making it sound like I
    # will spam them with HOIBOY AI LTD services. it needs to be more about blog
    # posts." The sentence below is what that turned into, and it is a PROMISE to
    # every subscriber. Rewriting it to admit services mail survived every test.
    if "We do not send anything about" not in body:
        out.append(
            "the footer no longer promises that this list is used ONLY for new posts. "
            "That sentence is a commitment made to every subscriber and is not "
            "editorial: widening it to admit services or product mail needs fresh "
            "consent, per content/legal/privacy/index.md, the newsletter Purpose bullet"
        )
    for admission in ("We may also send", "our latest offers", "news about our services"):
        if admission in body:
            out.append(
                f"the footer now admits sending non-post mail ({admission!r}); the list "
                f"was collected on a blog-posts-only promise"
            )

    # A reader must be able to SEE the way out. The href surviving is not enough:
    # colouring the anchor white or shrinking it to 1px keeps every href assertion
    # green while making the control invisible, which is a dark pattern and a PECR
    # problem, not a styling choice.
    unsub = re.search(r'<a href="%%UNSUBSCRIBE_URL%%"[^>]*>', body)
    if unsub is None:
        out.append("no <a> wrapping %%UNSUBSCRIBE_URL%%; the one-click control must be a link")
    else:
        attrs = unsub.group(0)
        if "#c0533a" not in attrs.lower():
            out.append("the unsubscribe link does not carry the accent colour; it must be visible")
        if re.search(r"font-size:\s*[0-3]px", attrs) or "#ffffff" in attrs.lower():
            out.append("the unsubscribe link is styled to be invisible; that is a dark pattern")

    # Where the reader is sent. The CTA repointed at the site root, and the privacy
    # link repointed at a path that 404s, both survived: no link checker reads
    # layouts/ (lychee is scoped to ./**/*.md and validate_internal_links.py to
    # content/), so these are the only assertion they get.
    # Three separate anchors carry the reader to the post: the hero image, the CTA
    # button, and the plain-text fallback. A presence check is NOT enough, because
    # repointing any ONE of them leaves the other two matching. The sweep repointed
    # the button at the site root and every assertion stayed green.
    post_links = body.count('<a href="%%POST_URL%%"')
    if post_links < 3:
        out.append(
            f"only {post_links} of the 3 post links point at %%POST_URL%% (hero image, "
            f"'Read the full post' button, plain-text fallback); one has been repointed "
            f"and readers land somewhere else"
        )
    cta = re.search(r'<a href="([^"]*)"[^>]*>Read the full post</a>', body)
    if cta is None:
        out.append("no 'Read the full post' call to action found")
    elif cta.group(1) != "%%POST_URL%%":
        out.append(
            f"the call to action points at {cta.group(1)!r}, not %%POST_URL%%; every "
            f"reader who clicks the button lands on the wrong page"
        )
    if "https://hoiboy.uk/legal/privacy/" not in body:
        out.append("the privacy-notice link is not the published URL https://hoiboy.uk/legal/privacy/")

    # The accent has to be on the thing the reader clicks, not merely somewhere in
    # the file. Stripping comments above already stops the prose from satisfying
    # the colour rule; this names the one element where losing it is most visible.
    cta_cell = re.search(r'<td[^>]*bgcolor="([^"]*)"[^>]*>\s*<a[^>]*>Read the full post', body)
    if cta_cell is None:
        out.append("the call-to-action button has no bgcolor cell; it will render as bare text")
    elif cta_cell.group(1).lower() != "#c0533a":
        out.append(
            f"the call-to-action button is {cta_cell.group(1)!r}, not the terracotta "
            f"accent #c0533a"
        )

    # The hero cell, which is a DIFFERENT cell from the button above. Gmail blocks
    # images by default, so the image-off state is the common one, and AC 1.6's
    # whole point is that the blocked hero degrades to a deliberate neutral block
    # rather than a white gap. Nothing gated it: the AC's recorded proof and the
    # suite both counted `bgcolor=` across the WHOLE FILE, which the button above
    # satisfies on its own. Measured with the hero's bgcolor stripped: this gate
    # clean, the AC grep reading 3 >= 1 and passing, not one assertion firing.
    # Ralph round 7 restart 5 tier 3.
    hero_cell = re.search(r"<td([^>]*)>\s*<a[^>]*>\s*<img", body)
    if hero_cell is None:
        out.append("no <td> wrapping the hero image; the layout must be table-based")
    elif not re.search(r'bgcolor="#[0-9a-fA-F]{3,6}"', hero_cell.group(1)):
        out.append(
            "the hero cell carries no bgcolor. Most clients block images by "
            "default, and without it that blocked hero is a white gap rather "
            "than a deliberate neutral block."
        )

    return out


def main() -> int:
    present = [TEMPLATE] if TEMPLATE.is_file() else []
    require_examined(
        "check_newsletter_template",
        "newsletter email template",
        present,
        hint=(
            f"Expected {TEMPLATE.relative_to(REPO_ROOT)}. Either the checkout is "
            f"partial, or the template was moved and this gate now guards nothing."
        ),
    )

    try:
        raw = TEMPLATE.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        # A template that cannot be decoded used to kill this gate with a raw
        # UnicodeDecodeError traceback. gate_coverage ships require_readable for
        # exactly this case, and its reasoning applies here in full: a gate cannot
        # assert an absence in a surface it failed to parse, so an unreadable
        # template is a COVERAGE failure with a remedy rather than a crash.
        require_readable(
            "check_newsletter_template",
            TEMPLATE,
            exc,
            remedy="Re-save the template as UTF-8, or restore it from git.",
        )
        raise  # unreachable: require_readable always raises

    problems = failures(raw)
    if problems:
        print(f"newsletter-template: {len(problems)} contract violation(s)", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"OK: newsletter template contract holds ({TEMPLATE.relative_to(REPO_ROOT)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
