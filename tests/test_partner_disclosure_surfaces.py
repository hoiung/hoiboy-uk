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


def test_the_notice_discloses_every_surface_it_publishes_her_on() -> None:
    """The opening paragraph must name the page, not only the brochure.

    Ralph round 5 Tier 3's finding in one assertion: the subsection said "It
    contains her photograph, her professional credentials, the languages she
    works in, and her location", where "It" is the brochure, while the page
    itself independently named her, described her role and gave her location.
    """
    body = _subsection("Partnership brochure")
    opening = body.strip().split("\n\n", 1)[0]
    assert "brochure" in opening, (
        "PREMISE BROKEN: the opening paragraph no longer mentions the brochure, "
        f"so this gate is reading the wrong text.\n{opening}"
    )

    # Require ONE SENTENCE that ties the page to HER, not the bare token "page".
    # The first draft of this gate asserted `"page" in opening` and a mutation
    # proved it vacuous in the way this whole Issue keeps rediscovering: the
    # pre-fix opening already read "The ICT consultancy PAGE publishes the ...
    # brochure", so the token was present for an unrelated reason and the gate
    # passed on the exact text it existed to reject. Sentence-scoping is what
    # makes it fail: pre-fix, "page" and "her" never co-occur in one sentence
    # (the page sentence says "my consultancy partner, Jolyn Pek"; the "her"
    # sentence begins "It contains", where "It" is the brochure).
    page_and_her = re.search(r"[^.]*\bpage\b[^.]*\bher\b[^.]*\.", opening)
    assert page_and_her, (
        "the notice's Partnership brochure subsection discloses the brochure but "
        "not the page's own mention of her. The ICT consultancy page names her, "
        "describes her role and says where she is based, independently of the "
        "PDF. A notice that describes one of two publication surfaces "
        "under-reports what was published about a named third party.\n"
        f"opening paragraph was:\n{opening}"
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
    assert not missing, (
        f"the Retention promise does not reach {missing}. It promises a takedown "
        "of a strict subset of what the subsection says is published about her, "
        "so a withdrawal performed exactly as written would leave the rest live. "
        "That is the defect Ralph round 5 Tier 3 stopped this Issue on.\n"
        f"Retention bullet was:\n{retention.strip()}"
    )
