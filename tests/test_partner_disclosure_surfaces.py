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
#
# CONTAINMENT, NOT EQUALITY, and the distinction is the whole of Stage 5 finding
# 1. The first version of this table was compared with `found == DECLARED`, which
# reads as "these are the surfaces" but asserts something much stronger: that
# every declared surface STILL names her. That turned the current publication
# state into a required invariant, so performing the takedown the notice promises
# at `content/legal/privacy/index.md` Retention reddened this gate, and because
# `ci.yml` gates `deploy.yml` and Cloudflare auto-build is off, a red CI means the
# withdrawal never reaches the live site. The gate written to protect her would
# have been the thing keeping her data published.
#
# Measured, not theorised: a full withdrawal applied to a scratch copy of HEAD
# failed all four tests; a page-only withdrawal failed this one; the pristine tree
# passed. So the direction is now one-way. A surface that STOPS naming her is
# lawful and passes. A surface that STARTS naming her without being declared and
# disclosed fails, which is the only thing this table was ever for.
DECLARED_SURFACES = {
    "content/hire-hoi/ict-consultancy/_index.md": "page",
    "content/legal/privacy/index.md": "notice",
}

# The same containment rule for the files that are not reader-facing pages but do
# carry her name in a PUBLIC repository. Stage 5 found "Jolyn Pek" committed at
# `tests/test_gate_mutations.py` with no row here and no mention in the notice:
# the enumerator globbed `content/**/*.md`, so a whole class of public occurrences
# was outside the population it claimed to enumerate. That is a different axis
# from the wording blindness recorded below (this one is file-type based) and its
# occurred count was ONE, not zero.
#
# These are not publication surfaces and the notice does not owe them a "where to
# read it" disclosure. What it owes is the repository disclosure, which is why the
# fourth test requires the notice to say the repo itself carries her name.
DECLARED_REPO_SITES = {
    "static/hire-hoi/ict-consultancy/Jolyn-Hoi_CRE+ICT_brochure_v1.0.pdf":
        "the brochure itself, the primary publisher of her details",
    "tests/test_partner_disclosure_surfaces.py": "this gate",
    "tests/test_gate_mutations.py": "the mutation rows that prove this gate",
    "scripts/test_static_link_shortcode.py": "the shortcode contract fixture",
    ".pre-commit-config.yaml": "the large-file exclude for the brochure path",
    "static/_headers": "the Content-Disposition rule for the brochure path",
    "docs/runbooks/partner-brochure-withdrawal.md":
        "the operator procedure for taking her details down",
}

# The brochure itself. It is the PRIMARY publisher of her photograph, credentials,
# languages, location and her clients' figures, and it sat outside the old
# enumerator entirely because it is not a `.md` file under `content/`.
BROCHURE_ASSET = "static/hire-hoi/ict-consultancy/Jolyn-Hoi_CRE+ICT_brochure_v1.0.pdf"

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

# How the notice may refer to the data subject as the OBJECT of those verbs.
# Stage 5 finding 2: binding the verb to its SUBJECT was only half the job. The
# old pattern accepted any clause shaped "The page ... names <anything>", so
# rewriting both passages to "The page itself also names our combined CRE and ICT
# service and describes what we sell." left the notice saying only the BROCHURE
# names her, which is the exact claim this gate exists to reject, and all four
# tests passed. A disclosure verb has to take HER as its object.
HER = ("her", "hers", "she", PARTNER)

# Verbs that count as the Retention promise actually REMOVING something. Stage 5
# finding 3: the previous check asserted the PRESENCE of a page-content phrase in
# the bullet, not that a removal verb governed it, so a Retention bullet reading
# "...removes the link and the file together. The mention of her on the page is
# not affected and stays live." passed while promising the literal opposite of the
# required disclosure. The removal verb must come BEFORE the page phrase in the
# same sentence, which is what makes the phrase an object of the removal rather
# than merely a neighbour of it.
REMOVAL_VERBS = (
    "removes", "remove", "removed", "removing",
    "takes down", "take down", "taken down",
    "deletes", "delete", "deleted",
    "unpublishes", "unpublish", "unpublished",
)

# The phrases that attribute removable content to the PAGE, as opposed to the
# file. Kept as a set rather than one literal so an honest rewording is not
# gratuitously rejected.
PAGE_CONTENT = (
    r"page's\s+(?:description|mention|account)\s+of\s+her",
    r"mention\s+of\s+her\s+on\s+the\s+page",
    r"description\s+of\s+her\s+on\s+the\s+page",
)

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


# Directories that are build output, dependencies or scratch rather than shipped
# source. `public/` is a Hugo artefact of the very content already enumerated, so
# counting it would double-report every surface and make the gate noisy enough to
# be disabled.
_SKIP_DIRS = {
    ".git", ".claude", ".venv", "public", "node_modules", "__pycache__",
    "legacy", ".pytest_cache", ".ruff_cache", "resources",
}


def _names_her(path: Path) -> bool:
    """True if this file carries the partner's name as readable text."""
    try:
        return PARTNER in path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        # A binary asset. The brochure is one, and it is declared explicitly
        # rather than sniffed, because a PDF's name occurrences live in a
        # compressed stream that a text read cannot see. Treating "cannot decode"
        # as "does not name her" is exactly the blindness that let the brochure
        # sit outside this population, so the caller checks the asset by name.
        return False


def _tracked_files():
    """Every shipped source file, build output and dependencies excluded."""
    for path in REPO.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(REPO).parts):
            continue
        yield path


def _surfaces_naming_her() -> set:
    """Reader-facing content files that name her, repo-relative."""
    return {
        str(p.relative_to(REPO))
        for p in CONTENT.rglob("*.md")
        if _names_her(p)
    }


def _repo_sites_naming_her() -> set:
    """Non-content shipped files that carry her name in a public repository."""
    return {
        str(p.relative_to(REPO))
        for p in _tracked_files()
        if not str(p.relative_to(REPO)).startswith("content/") and _names_her(p)
    }


def _page_is_a_live_surface() -> bool:
    """Does the ICT consultancy page still name her?

    Every claim the notice makes about the PAGE is conditional on this. It is what
    lets a withdrawal be both performed and described truthfully: while the page
    names her the notice must say so, and once it stops the notice must stop
    saying so. Neither state is privileged, and that is the fix for the Stage 5
    finding that the gate forbade the takedown it was written to guarantee.
    """
    page = REPO / "content" / "hire-hoi" / "ict-consultancy" / "_index.md"
    return page.is_file() and _names_her(page)


def _passages() -> list:
    """Every (line number, line) in the notice that names her."""
    lines = NOTICE.read_text(encoding="utf-8").splitlines()
    return [(n, line) for n, line in enumerate(lines, 1) if PARTNER in line]


def _page_discloses_her(line: str) -> bool:
    """Does this passage say the PAGE, in its own right, names HER?

    Three bindings, each one a Stage 5 finding:
      subject  the verb attaches to `page`, with no `brochure` intervening
      object   the verb takes her as its object, not the service or the offer
      case     the `brochure` exclusion is case-insensitive, so capitalising one
               letter no longer escapes the discriminator
    `[^.]` cannot cross a sentence boundary, so all three hold within one
    sentence rather than anywhere on a long markdown line.
    """
    verbs = "|".join(DISCLOSURE_VERBS)
    her = "|".join(re.escape(h) for h in HER)
    pattern = (
        rf"\bpage\b(?:(?!brochure)[^.])*"
        rf"\b(?:{verbs})\b(?:(?!brochure)[^.])*"
        rf"\b(?:{her})\b"
    )
    return re.search(pattern, line, re.IGNORECASE) is not None


def test_every_shipped_surface_naming_the_partner_is_declared() -> None:
    """The enumerator. A new surface that names her must be declared here.

    This is the check the escalation's sweep could not make. It walks the whole
    of `content/` rather than the sentences of one file, so a page that starts
    naming her tomorrow shows up as a failure tomorrow, not four review rounds
    later.
    """
    undeclared = sorted(_surfaces_naming_her() - set(DECLARED_SURFACES))
    assert not undeclared, (
        "a content file naming the consultancy partner is not declared in "
        f"DECLARED_SURFACES: {undeclared}\n"
        f"  declared: {sorted(DECLARED_SURFACES)}\n"
        "Publishing a named third party's personal data on a new surface means "
        "the privacy notice has to disclose that surface too. Declaring it here "
        "is step one; the next test checks the notice actually says so."
    )

    undeclared_repo = sorted(_repo_sites_naming_her() - set(DECLARED_REPO_SITES))
    assert not undeclared_repo, (
        "a shipped non-content file carries the partner's name and is not "
        f"declared in DECLARED_REPO_SITES: {undeclared_repo}\n"
        "This repository is PUBLIC, so her name in a test fixture or a config "
        "path is published too, even though nobody navigates to it. Declare it "
        "with what it is, and keep the notice's repository disclosure true."
    )

    # The declared tables are allowed to describe surfaces that no longer name
    # her. That direction is a withdrawal, and forbidding it is what made the
    # previous version of this gate hold the takedown shut. It is not silent: a
    # declared surface that has gone quiet flips `_page_is_a_live_surface()` and
    # the notice is then required to stop claiming the page names her.
    assert BROCHURE_ASSET in DECLARED_REPO_SITES or not (REPO / BROCHURE_ASSET).is_file(), (
        f"{BROCHURE_ASSET} is shipped but not declared. It is the primary "
        "publisher of her photograph, credentials, languages, location and her "
        "clients' figures, and a text-only enumerator cannot see inside it."
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
    passages = _passages()

    if not _page_is_a_live_surface():
        # The page has stopped naming her. The notice must stop saying it does,
        # and this is the assertion that makes the truthful post-withdrawal state
        # the GREEN one. Before Stage 5 the only green state after a page-only
        # takedown kept the notice asserting "The page itself also names her"
        # when the page no longer did, so the gate rewarded a false disclosure
        # and reddened on the correction.
        stale = [n for n, line in passages if _page_discloses_her(line)]
        assert not stale, (
            f"line(s) {stale} of the privacy notice still say the ICT "
            "consultancy page names her, but the page no longer does. A notice "
            "that over-reports is as wrong as one that under-reports: correct "
            "the passage to the past tense, or restore the page.\n"
            + "\n".join(f"  :{n} {line[:160]}" for n, line in passages)
        )
        return

    assert len(passages) >= 2, (
        "PREMISE BROKEN, not a defect detected: the notice names the partner in "
        f"fewer than two passages ({[n for n, _ in passages]}). This gate exists "
        "because the same fact is stated in a section-2 summary AND a section-4 "
        "subsection; if that is no longer true, the gate is measuring the wrong "
        "document and must be rewritten rather than trusted."
    )

    undisclosed = [n for n, line in passages if not _page_discloses_her(line)]
    assert not undisclosed, (
        f"line(s) {undisclosed} of the privacy notice name the partner but "
        "describe only the brochure as publishing her details. The ICT "
        "consultancy page names her, describes her role and says where she is "
        "based, independently of the PDF, so a passage that accounts for one of "
        "two publication surfaces under-reports what is published about a named "
        "third party. Every passage naming her has to say the page does it too, "
        f"using one of {DISCLOSURE_VERBS}, taking HER as the object.\n"
        + "\n".join(f"  :{n} {line[:160]}" for n, line in passages)
    )


def test_every_passage_naming_her_lists_the_client_figures_category() -> None:
    """The inventory must list what the brochure publishes, not a subset of it.

    Ralph Tier 3's finding, and the eighth instance of this Issue's one class.
    Rounds 3 to 5 fixed WHERE her data is published, WHEN it comes down and HOW.
    The rework fixed which SURFACES. Nobody checked WHAT: both passages listed
    "photograph, professional credentials, languages and location" while the
    brochure also publishes, under SELECTED PROJECTS, her client engagements with
    the savings figures she delivered (measured with `pdftotext -layout`: USD 4M,
    USD 1.2M, USD 7.4M).

    That category was identified at CONSENT time and then dropped from the
    notice, which is what makes it a defect rather than a judgement call. The
    repo says so twice: consent commit `20aa19e` ("the brochure carries a third
    party's portrait, credentials AND HER CLIENTS' FIGURES") and AC 0.1, the
    consent gate itself ("her portrait, credentials, languages, location AND HER
    CLIENTS' SAVINGS FIGURES"). Five categories consented, four disclosed.

    The gate is deliberately about the CATEGORY, not the numbers: the notice
    should not restate USD figures, it should say the brochure carries them.
    """
    if not (REPO / BROCHURE_ASSET).is_file():
        # The brochure is what publishes the figures. Once it is withdrawn the
        # notice is not required to keep inventorying them, for the same reason
        # the page claim is conditional above. This check comes FIRST: ordering it
        # after the premise assert below is what still blocked a full withdrawal
        # after finding 1's first fix, because a notice with her name removed has
        # no passages left to inventory and the premise fired instead.
        return

    passages = _passages()
    assert passages, (
        "PREMISE BROKEN, not a defect detected: the brochure is still shipped but "
        "no passage of the notice names her, so the inventory this gate checks "
        "does not exist. Either the notice was gutted without withdrawing the "
        "brochure, or the search term is wrong."
    )

    # Two bindings, both Stage 5 findings on this one regex.
    #
    # POSSESSIVE. `\bclient\b` did not match "clients'", so the consent record's
    # own wording, quoted in this docstring, would have FAILED the gate written
    # to enforce it. Over-strict and under-bound in the same expression.
    #
    # OWNERSHIP. The category has to be attributed to HER. Without that, dropping
    # the consented category from both inventories and appending "Prospective
    # client projects are discussed separately." passed: the tokens were present,
    # attached to nobody.
    missing = [
        n for n, line in passages
        if not re.search(
            r"\bher\b[^.]*\bclients?'?\b[^.]*\b(?:projects?|figures?|savings)\b"
            r"|\bclients?'?\b[^.]*\b(?:projects?|figures?|savings)\b[^.]*\bshe\b",
            line,
            re.IGNORECASE,
        )
    ]
    assert not missing, (
        f"line(s) {missing} inventory what is published about her but omit her "
        "client projects and the savings figures the brochure prints for them. "
        "The consent record enumerated that category (commit 20aa19e and AC 0.1) "
        "and the brochure publishes it under SELECTED PROJECTS, so a notice that "
        "lists four of the five consented categories under-reports what was "
        "published. Say the category; do not restate the figures.\n"
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
    if not _page_is_a_live_surface():
        return

    body = _subsection("Partnership brochure")
    match = re.search(r"^- \*\*Retention\*\*:(.*)$", body, re.M)
    assert match, (
        "PREMISE BROKEN, not a defect detected: no Retention bullet in the "
        "Partnership brochure subsection."
    )
    retention = match.group(1)
    missing = [noun for noun in SURFACE_NOUNS if noun not in retention]

    # Token presence is necessary and NOT sufficient, and this test learned that
    # the hard way TWICE. The rework re-validation reverted this bullet to the
    # exact pre-fix promise and appended "Nothing else on the page is affected."
    # and the bare-token check passed it, because both nouns were present.
    #
    # The fix for that moved from a bare TOKEN to a bare PHRASE, which Stage 5
    # then broke the same way one level down: asserting that the phrase EXISTS
    # says nothing about what is claimed of it, so "...removes the link and the
    # file together. The mention of her on the page is not affected and stays
    # live." passed while promising the opposite of the required disclosure.
    #
    # So the removal verb must come BEFORE the page phrase within the SAME
    # sentence. `[^.]` cannot cross a sentence boundary, which is what makes the
    # page phrase an object of the removal rather than a neighbour of it.
    removal = "|".join(re.escape(v) for v in REMOVAL_VERBS)
    page_content = re.search(
        rf"\b(?:{removal})\b[^.]*(?:{'|'.join(PAGE_CONTENT)})",
        retention,
        re.IGNORECASE,
    )

    assert not missing and page_content, (
        f"the Retention promise does not reach {missing or 'the page as a surface'}. "
        "It promises a takedown of a strict subset of what the subsection says is "
        "published about her, so a withdrawal performed exactly as written would "
        "leave the rest live. That is the defect Ralph round 5 Tier 3 stopped this "
        "Issue on. Naming the page is not enough: the bullet has to say what comes "
        "down WITH the file, in a phrase that attributes content to the page.\n"
        f"Retention bullet was:\n{retention.strip()}"
    )
