#!/usr/bin/env python3
"""Mutation tests: reintroduce a defect, require its own test to go red.

blog-priv#63 / #64, plan step 8.

WHY THIS EXISTS. Ralph ran NINE rounds on these two issues, every one failing at
Tier 2, and the escalation deep dive found that the review could not terminate
because its acceptance criterion looked BACKWARDS: a corpus of mutations each
named after a defect already found. "16 of 16 caught" is a statement about the
past. It was proven compatible with a live fail-open in the deploy gate.

The forward-looking question is narrow enough to be finite: can a WELL-FORMED
input make a derived value grant a pass, an exemption, or a green CI it should
not? The derivations that can do that in this repo are enumerable, and each one
below is a guard on one of them. Reverting the guard MUST turn its own test red.

WHY IT IS A MUTATION TEST AND NOT JUST MORE ASSERTIONS. Five times in this one
workstream a test was written that asserted a HELPER and not the WIRING, so
reverting the real call site left the suite green:

  - a test named for a CSS state-layer filter that never called the function
  - scripts/test_404.py collecting zero pytest tests for its whole life
  - the string-blanking test that called the blanker instead of stylesheet()
  - the CI-wiring test that called the new credit function instead of the guard
  - the lychee test that asserted a regex constant instead of driving check()

Every one was caught by reintroducing the defect, and none by reading the diff.
A guard authored in the same pass as the code it guards cannot be trusted on a
green run; this file is what makes that check automatic instead of manual.

A stale anchor FAILS LOUD rather than silently skipping. That is deliberate and
has already paid for itself: several anchors went stale as the code was
rewritten, and each time the harness said so instead of quietly passing.

Run:  python3 -m pytest tests/test_gate_mutations.py -q
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# (id, source file, text present now, what to replace it with, test file to run)
#
# Each `now` string is a guard that closes a permission-granting derivation.
# Each `reverted` string is that guard removed, i.e. the defect put back.
MUTATIONS = [
    pytest.param(
        "scripts/check_cta_rendered.py",
        'decl = re.findall(r"(?:^|;)\\s*color\\s*:\\s*([^;]+)", decls)',
        'decl = re.findall(r"(?:^|;)\\s*color\\s*:\\s*([^;]+)", decls)[:1]',
        "scripts/test_check_cta_rendered.py",
        id="cta-source-model-takes-first-declaration-not-last",
    ),
    pytest.param(
        "scripts/test_cta_button.py",
        'found = re.findall(rf"(?:^|;)\\s*{re.escape(prop)}\\s*:\\s*([^;]+)", decls)',
        'found = re.findall(rf"(?:^|;)\\s*{re.escape(prop)}\\s*:\\s*([^;]+)", decls)[:1]',
        "scripts/test_cta_button.py",
        id="wcag-gate-scores-first-declaration-not-last",
    ),
    pytest.param(
        "scripts/test_cta_button.py",
        'return blank_string_contents(COMMENTS.sub("", CSS.read_text(encoding="utf-8")))',
        'return COMMENTS.sub("", CSS.read_text(encoding="utf-8"))',
        "scripts/test_cta_button.py",
        id="wcag-gate-blind-to-a-brace-inside-a-css-string",
    ),
    pytest.param(
        "scripts/check_cta_rendered.py",
        "    if not HEX_COLOUR.match(h):",
        "    if False:",
        "scripts/test_check_cta_rendered.py",
        id="non-hex-colour-crashes-instead-of-dying-actionably",
    ),
    pytest.param(
        "scripts/check_cta_rendered.py",
        'STRING_LITERAL = re.compile(r"""([\'"])(?:\\\\.|(?!\\1)[^\\\\\\n])*\\1""")',
        'STRING_LITERAL = re.compile(r"""([\'"])(?:\\\\.|(?!\\1)[^\\\\])*\\1""", re.S)',
        "scripts/test_check_cta_rendered.py",
        id="unterminated-quote-swallows-braces-across-lines",
    ),
    pytest.param(
        "scripts/check_social_cards.py",
        '            continue\n        if directive in ("noindex", "none"):',
        '            directive = _rest.strip()\n        if directive in ("noindex", "none"):',
        "scripts/test_check_social_cards.py",
        id="agent-scoped-noindex-grants-a-blanket-exemption",
    ),
    pytest.param(
        "scripts/social-cards/gen_card.py",
        "if isinstance(value, bool) or not isinstance(value, (str, int, float)):",
        "if not isinstance(value, (str, int, float)):",
        "scripts/test_gen_card.py",
        id="yaml-boolean-renders-onto-a-published-share-card",
    ),
    pytest.param(
        "tests/test_gate_wiring.py",
        '    covered = _workflow_pytest_covered(CI.read_text(encoding="utf-8"))',
        '    covered = _pytest_covered(CI.read_text(encoding="utf-8"))',
        "tests/test_gate_wiring.py",
        id="ci-wiring-guard-credits-a-step-that-cannot-fail",
    ),
    pytest.param(
        "scripts/check_lychee_expiry.py",
        "if _EXCLUDE_KEY.match(stripped):",
        'if stripped.startswith("exclude"):',
        "scripts/test_check_lychee_expiry.py",
        id="allowlist-block-opens-on-the-wrong-key",
    ),
    # #55 Stage 5. The Issue added five gate behaviours and registered none of them
    # here, in the file whose whole premise is that a guard authored in the same pass
    # as the code it guards cannot be trusted on a green run. Measured at the time:
    # rewriting the `url:` branch to `&& false` left its own suite at
    # "3 passed, 3 skipped" -- byte-identical to the control.
    pytest.param(
        "scripts/pre-publish.sh",
        '    if [[ -n "$fm_url" ]]; then',
        '    if [[ -n "$fm_url" ]] && false; then',
        "scripts/test_pre_publish_rendered_path.py",
        id="frontmatter-url-override-silently-ignored",
    ),
    pytest.param(
        "scripts/check_social_cards.py",
        '    if not any(public.rglob("index.html")):',
        "    if False:",
        "scripts/test_check_social_cards.py",
        id="non-build-passes-the-rendered-og-image-tier",
    ),
    # The two-segment prefixes were an unconditional allow-list for the whole life
    # of the validator, so the 15 root-relative /hire-hoi/, /legal/, /community/,
    # /tags/ and /series/ links in the repo were resolved by no tier at all. This
    # mutation puts the allow-list back; the resolution tests must go red.
    pytest.param(
        "scripts/validate_internal_links.py",
        "    if first in _TAXONOMY_TWO_PREFIX:",
        "    if first in _ALLOW_TWO_PREFIX:\n        return True, \"\"\n    if first in _TAXONOMY_TWO_PREFIX:",
        "scripts/test_validate_internal_links.py",
        id="two-segment-prefixes-accept-anything-beneath-them",
    ),
    pytest.param(
        "scripts/validate_internal_links.py",
        '    slug = re.sub(r"[^a-z0-9_/-]", "", slug)',
        '    slug = re.sub(r"[^a-z0-9/-]", "", slug)',
        "tests/test_taxonomy_terms_match_build.py",
        id="urlize-folds-the-underscore-and-rejects-a-live-tag",
    ),
    # The single-segment allow-list is hand-maintained and had drifted in BOTH
    # directions at once. One mutation per direction: a stale entry that accepts
    # a 404, and a missing entry that rejects a live page.
    pytest.param(
        "scripts/validate_internal_links.py",
        '        "tags",  # /tags/ taxonomy list page',
        '        "about",',
        "tests/test_taxonomy_terms_match_build.py",
        id="allow-list-entry-for-a-page-that-404s",
    ),
    pytest.param(
        "scripts/validate_internal_links.py",
        '        "series",  # /series/ taxonomy list page',
        "",
        "tests/test_taxonomy_terms_match_build.py",
        id="live-list-page-missing-from-the-allow-list",
    ),
    # #57 Stage 5. Same omission the #55 note above records, one issue later: the
    # AGIT story counter arrived with two gates and registered neither here. The
    # first four mutate the decision logic that says what "correct" means for the
    # counter; the fifth removes the only line that opens a browser at all; the
    # last three break a promise the form makes to a member, which is the class
    # the binding tests exist for.
    pytest.param(
        "scripts/check_agit_form_counter.py",
        'return "met" if count >= minimum else "short"',
        'return "met" if count > minimum else "short"',
        "scripts/test_check_agit_form_counter.py",
        id="counter-tells-a-member-at-the-minimum-to-keep-writing",
    ),
    pytest.param(
        "scripts/check_agit_form_counter.py",
        '    return "length" if str(minimum) in text else "other"',
        '    return "length"',
        "scripts/test_check_agit_form_counter.py",
        id="turnstile-complaint-stands-in-for-the-length-complaint",
    ),
    pytest.param(
        "scripts/check_agit_form_counter.py",
        "        if missing:",
        "        if False:",
        "scripts/test_check_agit_form_counter.py",
        id="a-theme-with-no-counter-colour-runs-half-a-gate",
    ),
    pytest.param(
        "scripts/check_agit_form_counter.py",
        "    if not HEX6.match(h):",
        "    if False:",
        "scripts/test_check_agit_form_counter.py",
        id="unresolvable-counter-colour-crashes-instead-of-dying-actionably",
    ),
    # The whole browser half hangs off this one line. Everything else in its
    # suite is pure decision logic and stays green with Chromium never opened.
    pytest.param(
        "scripts/pre-publish.sh",
        'run_check "agit-counter" python3 scripts/check_agit_form_counter.py --built public',
        "",
        "scripts/test_check_agit_form_counter.py",
        id="agit-browser-gate-named-in-prose-and-invoked-nowhere",
    ),
    # Site JS is unfingerprinted, so a hard-coded src never changes when the
    # file does and the pre-#57 script -- no counter, no submit guard -- is
    # served for hours against markup already promising the minimum. The
    # Cache-Control route to fixing this was tried and MEASURED not to work
    # (Cloudflare Pages joins same-name headers; the asset default's max-age
    # won), so the version lives in the URL instead.
    pytest.param(
        "content/community/asians-gingers-in-tech/index.md",
        '{{< versioned-script "js/agit-form.js" >}}',
        '<script src="/js/agit-form.js" defer></script>',
        "scripts/test_agit_counter_contrast.py",
        id="form-script-url-carries-no-version-so-it-outlives-its-markup",
    ),
    pytest.param(
        "content/community/asians-gingers-in-tech/index.md",
        'maxlength="8000"',
        'maxlength="4000"',
        "scripts/test_agit_counter_contrast.py",
        id="story-field-advertises-a-ceiling-the-server-does-not-hold",
    ),
    # Shrunk below the height of the chip it exists to hold, so the counter
    # paints onto the last line of the story. The rendered proof lives in the
    # pre-publish Chromium lane; this is the half that runs everywhere else.
    pytest.param(
        "content/community/asians-gingers-in-tech/index.md",
        'textarea[name="feature"] { padding-bottom: 1.35rem;',
        'textarea[name="feature"] { padding-bottom: .7rem;',
        "scripts/test_agit_counter_contrast.py",
        id="story-gutter-too-small-for-the-counter-it-holds",
    ),
    # socials is routed through cleanLines() and is deliberately absent from
    # FIELD_CAPS, so a binding built only from FIELD_CAPS reports full coverage
    # with this pair unguarded.
    pytest.param(
        "functions/api/contribute.js",
        "const SOCIALS_MAX_TOTAL = 1000;",
        "const SOCIALS_MAX_TOTAL = 500;",
        "scripts/test_agit_counter_contrast.py",
        id="socials-cap-drifts-outside-the-field-caps-table",
    ),
    pytest.param(
        "scripts/check_wordcount.py",
        '_HTML_COMMENT_RE = re.compile(r"<!--(?:(?!<!--)[\\s\\S])*?-->")',
        '_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)',
        "scripts/test_check_wordcount.py",
        id="unterminated-html-comment-undercounts-a-post",
    ),
    # #56 Ralph escalation, class sweep. Same story as the #55 entry above: the
    # Issue added two gate behaviours and registered neither here, and the sweep
    # then found both of them reporting success over surfaces they never
    # examined. Registered now so the fixes cannot rot the way the gates did.
    pytest.param(
        "scripts/check_noindex_frontmatter.py",
        "        if not matched_pages:",
        "        if False:",
        "scripts/test_check_noindex_frontmatter.py",
        id="noindex-gate-passes-over-a-stale-tree",
    ),
    pytest.param(
        "scripts/check_subscribe_placement.py",
        "    for cls, seen in sorted(per_class.items()):",
        "    for cls, seen in []:",
        "scripts/test_check_subscribe_placement.py",
        id="suppression-floor-is-aggregate-not-per-class",
    ),
    pytest.param(
        "scripts/check-exif.py",
        '        if ctype == b"IEND":',
        '        if ctype == b"IDAT" or ctype == b"IEND":',
        "scripts/test_check_exif.py",
        id="png-exif-after-idat-scores-clean",
    ),
]


@pytest.mark.parametrize("source,now,reverted,test_file", MUTATIONS)
def test_reverting_a_guard_turns_its_own_test_red(source, now, reverted, test_file):
    """The defect goes back in; the test that exists for it must notice.

    A guard that stays green with its defect restored is not protecting
    anything, and would report the codebase as safe while the thing it names is
    broken. That is the single shape this whole workstream kept producing.
    """
    src = ROOT / source
    original = src.read_text(encoding="utf-8")
    assert now in original, (
        f"STALE ANCHOR: {source} no longer contains the guard this mutation "
        f"reverts. The code was rewritten and this entry was not updated. Failing "
        f"loud rather than skipping, because a silently skipped mutation reports "
        f"as coverage that does not exist.\n\nExpected to find:\n{now}"
    )

    backup = Path(tempfile.mkdtemp()) / "backup"
    shutil.copy(src, backup)
    try:
        src.write_text(original.replace(now, reverted, 1), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(ROOT / test_file), "-q", "-p", "no:cacheprovider"],
            capture_output=True, text=True, cwd=ROOT,
        )
    finally:
        shutil.copy(backup, src)

    assert result.returncode != 0, (
        f"VACUOUS GATE: reverting the guard in {source} left {test_file} fully "
        f"green, so nothing in the suite is actually pinning it.\n\n"
        f"Reverted to:\n{reverted}\n\npytest said:\n{result.stdout[-2000:]}"
    )


# Byte snapshot of every file the mutations write to, taken at import time and
# therefore before any mutation has run. The leak check below compares against
# THIS, not against git.
#
# It used to run `git diff --name-only` on the same paths. That compares the
# working tree to the index, which answers a different question: it fires on
# any unstaged edit, including legitimate uncommitted work by whoever is
# editing these gates right now. hoiboy-uk#54 edited check_cta_rendered.py and
# the suite went red with "a mutation leaked" while nothing had leaked; staging
# the file made it pass, which is a tell that the check was measuring staging,
# not leakage. A snapshot has neither failure mode: it is blind to what git
# thinks and sensitive only to a change that happened during this run.
_GUARDED_FILES = sorted({m.values[0] for m in MUTATIONS})
_TREE_SNAPSHOT = {
    path: (ROOT / path).read_bytes()
    for path in _GUARDED_FILES
    if (ROOT / path).exists()
}


def test_the_tree_is_left_exactly_as_it_was_found():
    """Every mutation restores its file; prove no edit leaked out of a failure.

    The mutations above write to real repo files. If one aborted between the
    write and the restore, the working tree would carry a reverted guard and
    every later assertion in this session would be measured against it.
    """
    missing = [p for p in _GUARDED_FILES if p not in _TREE_SNAPSHOT]
    assert not missing, (
        f"guarded files absent at import, so no snapshot exists for them: {missing}"
    )

    drifted = [
        path for path, original in _TREE_SNAPSHOT.items()
        if (ROOT / path).read_bytes() != original
    ]
    assert not drifted, (
        f"a mutation leaked into the working tree: {drifted!r}. These files "
        f"differ from their contents at the start of this pytest session, so a "
        f"mutation wrote to them and did not restore. Restore them before "
        f"trusting any other result in this run."
    )
