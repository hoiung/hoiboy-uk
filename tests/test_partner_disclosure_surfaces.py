#!/usr/bin/env python3
"""Every shipped surface naming the consultancy partner is disclosed in the notice.

hoiboy-uk#59, Ralph round 5 Tier 3.

WHY THIS FILE EXISTS, and why it asks a different question from every gate that
came before it.

The privacy notice promised a named third party that taking the brochure down
"removes both the link and the file together". That sentence was true of the
brochure, and blind to the fact that the SAME Issue published her a second time,
in the ICT page's own prose: her name, her role, and where she is based. Executed
literally, the promised takedown would have left all of that published and
indexable. Rounds 3, 4 and 5 each rewrote that sentence. Not one of them checked
the SURFACE the sentence describes.

The escalation's sweep enumerated SENTENCES in `content/legal/` and asked of each
"is this operational claim BACKED by machinery or a runbook?". That question
cannot see this defect, because the sentence WAS backed and its SCOPE was wrong.
A gate can be backed and still be wrong. So this file asks the other question,
which is the one the class actually needs:

    enumerate the SURFACES that publish her, and require the notice to cover
    every one.

That is an enumerator over a population, not another assertion about one
sentence, which is what makes it a class fix rather than a sixth instance fix.
If her name lands on a new page and nobody updates the notice, this fails.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONTENT = REPO / "content"
NOTICE = CONTENT / "legal" / "privacy" / "index.md"

# The data subject this gate is for. She is named in shipped, public content on a
# consent basis, so the notice owes her an accurate account of WHERE.
PARTNER = "Jolyn"

# Every content file allowed to name her, and what each one is. Adding a surface
# here without disclosing it in the notice fails the second test, so this table
# cannot be used to wave a new surface through.
DECLARED_SURFACES = {
    "content/hire-hoi/ict-consultancy/_index.md": "page",
    "content/legal/privacy/index.md": "notice",
}

# The nouns the notice uses for the surfaces it discloses. The Retention promise
# has to reach every surface the opening paragraph declares; a rewrite that
# narrows the promise back to the brochure alone drops one of these and fails.
SURFACE_NOUNS = ("brochure", "page")

# Verbs that count as the notice disclosing the PAGE as a publisher of her
# details in its own right, rather than merely as the thing that carries the
# brochure. The distinction is the whole finding: "the ICT consultancy page
# PUBLISHES our brochure" says nothing about the page naming her, and it is what
# both passages said before the fix. `publishes` is deliberately NOT in this set.
DISCLOSURE_VERBS = ("names", "describes", "identifies")

# KNOWN BLINDNESS, disclosed rather than papered over (mutation-verification.md
# sweep quality gate 2: a sweep enumerates what its generator CANNOT produce
# beside what it does).
#
# The enumerator below matches the literal token in PARTNER. A surface that
# identifies her WITHOUT naming her -- by role and location, which is exactly the
# descriptive shape the ICT page already uses -- passes clean. The rework
# re-validation proved this on a scratch clone: a paraphrase appended to a copy
# of a legal page left all three tests green.
#
# It is recorded, not fixed, for a reason worth keeping: the fix is a
# similarity/NLP judgement about whether prose identifies a person, and a gate
# that guesses at that would fail on unrelated copy and get disabled. The
# population it does cover is checked exactly, and the residual is one
# occurred-count of zero: no such surface exists in the shipped tree today
# (verified by a repo-wide sweep at the rework re-validation). If one ever lands,
# it lands as a DECLARED surface here or it is caught by review, not by this file.


def _subsection(name: str) -> str:
    """Return the body of one `### ` subsection of the notice."""
    text = NOTICE.read_text(encoding="utf-8")
    match = re.search(rf"^### {re.escape(name)}$(.*?)(?=^#{{2,3}} )", text, re.M | re.S)
    assert match, (
        f"PREMISE BROKEN, not a defect detected: no '### {name}' subsection in "
        f"{NOTICE.relative_to(REPO)}. This gate cannot report on a subsection "
        "that is not there, so it fails loud rather than passing vacuously."
    )
    return match.group(1)


def test_every_shipped_surface_naming_the_partner_is_declared() -> None:
    """The enumerator. A new surface that names her must be declared here.

    This is the check the escalation's sweep could not make. It walks the whole
    of `content/` rather than the sentences of one file, so a page that starts
    naming her tomorrow shows up as a failure tomorrow, not four review rounds
    later.
    """
    found = {
        str(path.relative_to(REPO))
        for path in CONTENT.rglob("*.md")
        if PARTNER in path.read_text(encoding="utf-8")
    }
    assert found, (
        "PREMISE BROKEN, not a defect detected: no content file names the "
        f"partner at all. Either {PARTNER!r} is the wrong search term or the "
        "brochure work was reverted, and either way this gate is measuring "
        "nothing."
    )
    assert found == set(DECLARED_SURFACES), (
        "a content file naming the consultancy partner is not declared in "
        "DECLARED_SURFACES, or a declared one no longer names her.\n"
        f"  found:    {sorted(found)}\n"
        f"  declared: {sorted(DECLARED_SURFACES)}\n"
        "Publishing a named third party's personal data on a new surface means "
        "the privacy notice has to disclose that surface too. Declaring it here "
        "is step one; the next test checks the notice actually says so."
    )


def test_every_passage_naming_her_discloses_the_page_as_a_publisher() -> None:
    """EVERY passage in the notice that names her, not one hardcoded subsection.

    This test was scoped to the `### Partnership brochure` subsection until the
    rework re-validation, and that scoping is exactly how it missed the defect it
    was written to prevent. The subsection at section 4 was widened; the SUMMARY
    bullet at section 2, which makes the same claim in the passage a reader hits
    first, was left saying the brochure "includes my consultancy partner Jolyn
    Pek's photograph, professional credentials, languages and location" and
    nothing about the page's own mention of her. One document, two statements of
    the same fact, one of them fixed. A `_subsection()` regex could not see the
    other one BY CONSTRUCTION.

    So the gate now enumerates instead of pointing: every line in the notice that
    names her has to disclose the page as a publisher of her details in its own
    right, and a new passage about her anywhere in the notice is covered the day
    it lands.

    The discriminator is a disclosure VERB applied to the page, not the token
    "page". Both pre-fix passages contained "page" already, for an unrelated
    reason ("the ICT consultancy page publishes ... brochure"), and an earlier
    draft of this gate asserted the bare token and was proven vacuous by mutation
    against the very text it existed to reject.
    """
    lines = NOTICE.read_text(encoding="utf-8").splitlines()
    passages = [(n, line) for n, line in enumerate(lines, 1) if PARTNER in line]
    assert len(passages) >= 2, (
        "PREMISE BROKEN, not a defect detected: the notice names the partner in "
        f"fewer than two passages ({[n for n, _ in passages]}). This gate exists "
        "because the same fact is stated in a section-2 summary AND a section-4 "
        "subsection; if that is no longer true, the gate is measuring the wrong "
        "document and must be rewritten rather than trusted."
    )

    # The verb must be attributed to the PAGE, with no "brochure" intervening.
    # `\bpage\b[^.]*\b(verb)\b` was not enough and the rework re-validation broke
    # it: "the ICT consultancy page publishes our ... brochure, WHICH NAMES my
    # consultancy partner Jolyn Pek" matches that pattern while saying only that
    # the BROCHURE names her, which is the exact claim this gate exists to reject.
    # Excluding "brochure" between the page token and the verb is what binds the
    # verb to its subject.
    verbs = "|".join(DISCLOSURE_VERBS)
    undisclosed = [
        n for n, line in passages
        if not re.search(rf"\bpage\b(?:(?!brochure)[^.])*\b(?:{verbs})\b", line)
    ]
    assert not undisclosed, (
        f"line(s) {undisclosed} of the privacy notice name the partner but "
        "describe only the brochure as publishing her details. The ICT "
        "consultancy page names her, describes her role and says where she is "
        "based, independently of the PDF, so a passage that accounts for one of "
        "two publication surfaces under-reports what is published about a named "
        "third party. Every passage naming her has to say the page does it too, "
        f"using one of {DISCLOSURE_VERBS}.\n"
        + "\n".join(f"  :{n} {line[:160]}" for n, line in passages)
    )


def test_the_retention_promise_reaches_every_declared_surface() -> None:
    """Withdrawal has to remove everything the opening paragraph declares.

    The round-4 defect was a Retention sentence that described an operation which
    could not work. This is the round-5 defect one level up: a Retention sentence
    that works perfectly and removes only part of what is published. Both fail in
    the direction that harms the data subject, which is why the promise is pinned
    to the declared surface set rather than to its own wording.
    """
    body = _subsection("Partnership brochure")
    match = re.search(r"^- \*\*Retention\*\*:(.*)$", body, re.M)
    assert match, (
        "PREMISE BROKEN, not a defect detected: no Retention bullet in the "
        "Partnership brochure subsection."
    )
    retention = match.group(1)
    missing = [noun for noun in SURFACE_NOUNS if noun not in retention]

    # Token presence is necessary and NOT sufficient, and this test learned that
    # the hard way. The rework re-validation reverted this bullet to the exact
    # pre-fix promise and appended "Nothing else on the page is affected." -- the
    # literal opposite of the required disclosure -- and the bare-token check
    # passed it, because both nouns were present. That is the same vacuity class
    # the sibling test above records as "proven vacuous by mutation", left live
    # here in the same commit that fixed it there.
    #
    # So the bullet must also ATTRIBUTE removable content to the page: a
    # possessive or locative phrase tying what comes down to the page itself,
    # rather than the noun appearing anywhere in any role.
    page_content = re.search(r"page's\s+(?:description|mention)|mention of her on the page", retention)

    assert not missing and page_content, (
        f"the Retention promise does not reach {missing or 'the page as a surface'}. "
        "It promises a takedown of a strict subset of what the subsection says is "
        "published about her, so a withdrawal performed exactly as written would "
        "leave the rest live. That is the defect Ralph round 5 Tier 3 stopped this "
        "Issue on. Naming the page is not enough: the bullet has to say what comes "
        "down WITH the file, in a phrase that attributes content to the page.\n"
        f"Retention bullet was:\n{retention.strip()}"
    )
