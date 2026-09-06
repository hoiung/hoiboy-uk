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

import os
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
    # blog-priv#81, Ralph round 3 tier 3. The #55 comment above describes an Issue
    # that added five gate behaviours and registered none of them here; this Issue
    # added one and did the same. The gate's contract logic was tested five ways,
    # all against failures(), and its exit code not at all -- yet
    # .pre-commit-config.yaml runs it as a command and reads nothing else. Measured
    # at the time: return 1 -> return 0 printed "1 contract violation(s)" and exited
    # 0 with the suite at "62 passed".
    pytest.param(
        "scripts/check_newsletter_template.py",
        "        return 1",
        "        return 0",
        "scripts/test_check_newsletter_template.py",
        id="template-contract-violation-exits-clean",
    ),
    # The feed gate, registered here for the reason it was extracted out of
    # tests/test_feed_markers.py in the first place. While the checks lived inside
    # that test file, `assert not offenders` could be rewritten to `assert not
    # offenders or True` and NOTHING in the repo noticed: a file cannot guard its
    # own assertions, and this file is the mechanism that covers that -- but only
    # for logic living outside the test. The class sweep found four such
    # self-neutering edits in that one file. Each mutation below is a real
    # survivor from it.
    pytest.param(
        "scripts/check_feed_markers.py",
        "    comments = {f.name: t.count(ESCAPED_COMMENT) for f, t in texts.items()\n"
        "                if ESCAPED_COMMENT in t}",
        "    comments = {}",
        "tests/test_feed_markers.py",
        id="feed-comment-leak-check-reports-nothing",
    ),
    pytest.param(
        "scripts/check_feed_markers.py",
        'ESCAPED_COMMENT = html.escape("<!--")',
        'ESCAPED_COMMENT = "&lt;!--zz-never-matches"',
        "tests/test_feed_markers.py",
        id="feed-comment-needle-cannot-match-anything",
    ),
    pytest.param(
        "scripts/check_feed_markers.py",
        "MIN_FEEDS = 6",
        "MIN_FEEDS = 0",
        "tests/test_feed_markers.py",
        id="feed-vacuity-floor-accepts-an-unbuilt-tree",
    ),
    # `pass` rather than a narrowed `except`, deliberately. Naming an exception the
    # parser never raises makes the gate CRASH on a malformed feed, which the test
    # catches for the wrong reason: a crash is loud, and the failure this registry
    # exists to detect is a check that quietly stops checking. This makes the parse
    # a no-op instead, which is silent.
    pytest.param(
        "scripts/check_feed_markers.py",
        "            ET.fromstring(texts[feed])",
        "            pass",
        "tests/test_feed_markers.py",
        id="malformed-feed-xml-is-not-detected",
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
    pytest.param(
        "scripts/check_wordcount.py",
        '    r"^(?P<fence>`{3,}|~{3,})[^\\n]*\\n"',
        '    r"(?P<fence>`{3,}|~{3,})[^\\n]*\\n"',
        "scripts/test_check_wordcount.py",
        id="wordcount-unanchored-fence-eats-prose-before-counting",
    ),
    pytest.param(
        "scripts/check-iamhoi-wrapping.py",
        '        content = repo_root / "content"',
        '        content = repo_root / "content" / "posts"',
        "scripts/test_check_iamhoi_wrapping.py",
        id="iamhoi-ci-default-scans-less-than-the-hook-it-mirrors",
    ),
    pytest.param(
        "scripts/check-public-repo-secrets.py",
        "    if name in SCAN_FILENAMES:",
        "    if False:",
        "scripts/test_check_public_repo_secrets.py",
        id="secrets-extensionless-config-file-never-opened",
    ),
    # hoiboy-uk#59, Ralph round 1 Tier 2. The four below are one CLASS, not four
    # incidents: a static-link guard changed so that it still contains every
    # token the test looked for, while doing the opposite of what it says.
    # The first version of scripts/test_static_link_shortcode.py asserted that
    # `fileExists`, `hasPrefix $path "/"` and three `errorf` call sites were
    # PRESENT in the template. Dropping a `not` keeps all of that text and
    # inverts the guard, so all three polarity mutants passed every assertion.
    # That test now builds a throwaway Hugo site per guard and asserts which
    # build fails and with whose message, which is what these rows pin.
    pytest.param(
        "layouts/_shortcodes/static-link.html",
        '{{- if or (not $path) (not (hasPrefix $path "/")) -}}',
        '{{- if or (not $path) (hasPrefix $path "/") -}}',
        "scripts/test_static_link_shortcode.py",
        id="static-link-root-relative-guard-inverted-accepts-relative-paths",
    ),
    pytest.param(
        "layouts/_shortcodes/static-link.html",
        "{{- if not $label -}}",
        "{{- if $label -}}",
        "scripts/test_static_link_shortcode.py",
        id="static-link-label-guard-inverted-ships-an-invisible-link",
    ),
    pytest.param(
        "layouts/_shortcodes/static-link.html",
        "{{- if not (fileExists $file) -}}",
        "{{- if (fileExists $file) -}}",
        "scripts/test_static_link_shortcode.py",
        id="static-link-missing-file-guard-inverted-ships-a-dead-link",
    ),
    # Same class again, and the subtlest member: the guard is neither inverted
    # nor deleted, just taught to accept one more vocabulary. An absolute URL
    # CONTAINS a "/", so widening the prefix set survives every case that only
    # feeds relative or missing paths. Found by Ralph round 2 Tier 2 attacking
    # the round-1 fix, which is the tier's job.
    pytest.param(
        "layouts/_shortcodes/static-link.html",
        '{{- if or (not $path) (not (hasPrefix $path "/")) -}}',
        '{{- if or (not $path) (not (or (hasPrefix $path "/") (hasPrefix $path "http"))) -}}',
        "scripts/test_static_link_shortcode.py",
        id="static-link-root-relative-guard-widened-to-admit-absolute-urls",
    ),
    # Same class, different mechanism: the guard's polarity is intact but it is
    # asked about the wrong file, so it passes on a path the browser never
    # requests. `$file := printf` survives, so the old substring check did too.
    pytest.param(
        "layouts/_shortcodes/static-link.html",
        '{{- $file := printf "static%s" $path -}}',
        '{{- $file := printf "%s" $path -}}',
        "scripts/test_static_link_shortcode.py",
        id="static-link-file-check-drops-the-static-prefix",
    ),
    # This one pins the COUPLING check rather than a guard: a fourth guard added
    # to the template with no row in GUARD_CASES must turn the suite red, which
    # is what stops the enumerator quietly falling behind the thing it enumerates.
    # Written in the no-trim-dash spelling on purpose. Ralph round 2 Tier 3 found
    # the old `^\s*\{\{- errorf ` pattern blind to exactly this, so the guard was
    # live in the template and invisible to the count that claimed to cover it.
    pytest.param(
        "layouts/_shortcodes/static-link.html",
        '{{- $file := printf "static%s" $path -}}',
        '{{- if not (hasSuffix $path ".pdf") -}}\n  {{ errorf "static-link: only pdfs (called from %s)" .Page.Path }}\n{{- end -}}\n{{- $file := printf "static%s" $path -}}',
        "scripts/test_static_link_shortcode.py",
        id="static-link-fourth-guard-added-with-no-row-in-the-guard-table",
    ),
    # hoiboy-uk#59, Ralph round 5 Tier 2, and it pins a POSITIVE CONTROL rather
    # than a guard. test_withdrawal_path_removes_link_and_file_together binds the
    # privacy notice's promise to a data subject that taking the brochure down
    # "removes both the link and the file together". Its first half used to build
    # a page with NO shortcode call at all and assert only `exit == 0` -- true of
    # any page whatsoever, and it passed with static-link.html deleted outright,
    # while the docstring claimed it asserted the coupling. It now opens by
    # building the PUBLISHED state and proving the anchor and the file are really
    # there, so "the link is gone" cannot pass on a site that never had a link.
    # Detach the anchor from its path argument and the published state silently
    # stops pointing at the brochure.
    #
    # The target is a pytest NODE ID, not the file. Ralph round 5 Tier 3 found
    # that naming the file here would NOT pin the positive control at all: this
    # harness asserts only that the named target goes red, so with the two
    # positive-control asserts deleted the row still passed, because the
    # happy-path test reddens the same FILE under this same mutant. A row that
    # cannot tell which test caught the defect does not protect the test it was
    # written for -- and an unprotected positive control is precisely the rot
    # this Issue's history is made of. Scoping to the node id makes the row fail
    # if and only if the withdrawal test itself notices.
    pytest.param(
        "layouts/_shortcodes/static-link.html",
        '<a href="{{ $path }}" target="_blank" rel="noopener">{{ $label }}</a>',
        '<a href="#" target="_blank" rel="noopener">{{ $label }}</a>',
        "scripts/test_static_link_shortcode.py::test_withdrawal_path_removes_link_and_file_together",
        id="static-link-anchor-href-detached-from-its-path-argument",
    ),
    # hoiboy-uk#59, Ralph round 5 Tier 3, the finding that terminally stopped the
    # loop. These three pin the PARTNER-DISCLOSURE gates, and the defect each
    # re-injects is the exact PRE-FIX text, so the rows fail if the notice ever
    # narrows back to what it said when the gap was found. All three are scoped
    # to a pytest NODE ID rather than the file, for the reason recorded on the
    # row above: a file-scoped row is satisfied by any sibling test.
    #
    # The class: the privacy notice promised a takedown that "removes both the
    # link and the file together" while the SAME Issue published the data
    # subject a second time in the page's own prose. The sentence was BACKED and
    # its SCOPE was wrong, which is the question the escalation's sweep never
    # asked.
    # TWO rows, one per passage, because the notice states this fact TWICE and
    # the rework re-validation found the section-2 summary still carrying the
    # pre-fix narrowing after section 4 had been widened. One document, two
    # statements, one of them fixed, and the gate was scoped to the subsection so
    # it could not see the other. Each row reverts its own passage to the exact
    # text it had when the gap was found.
    pytest.param(
        "content/legal/privacy/index.md",
        "languages and location. The page itself also names her, describes her role, and says where she is based. Both are published on the basis of her consent",
        "languages and location, published on the basis of her consent",
        "tests/test_partner_disclosure_surfaces.py::test_every_passage_naming_her_discloses_the_page_as_a_publisher",
        id="partner-disclosure-section-2-summary-narrowed-back-to-the-brochure",
    ),
    pytest.param(
        "content/legal/privacy/index.md",
        "and her location. The page itself also names her, describes her role, and says where she is based.",
        "and her location.",
        "tests/test_partner_disclosure_surfaces.py::test_every_passage_naming_her_discloses_the_page_as_a_publisher",
        id="partner-disclosure-section-4-opening-narrowed-back-to-the-brochure",
    ),
    pytest.param(
        "content/legal/privacy/index.md",
        "- **Retention**: the brochure and the mention of her on the page stay published until she or I take them down, which removes the link, the file and the page's description of her together. The public repository's git history keeps them unless",
        "- **Retention**: the brochure stays published until she or I take it down, which removes both the link and the file together. The public repository's git history keeps the file unless",
        "tests/test_partner_disclosure_surfaces.py::test_the_retention_promise_reaches_every_declared_surface",
        id="partner-disclosure-retention-narrowed-back-to-link-and-file",
    ),
    # These two pin the DISCRIMINATORS rather than the passages, and both were
    # found by Ralph Tier 3 SURVIVING the first version of the gate. Each is a
    # rewrite that keeps every token the gate looked for while saying the
    # opposite thing, which is the vacuity class this whole Issue is made of.
    pytest.param(
        "content/legal/privacy/index.md",
        "and her location. The page itself also names her, describes her role, and says where she is based.",
        "and her location, and the brochure names her throughout.",
        "tests/test_partner_disclosure_surfaces.py::test_every_passage_naming_her_discloses_the_page_as_a_publisher",
        id="partner-disclosure-verb-attributed-to-the-brochure-not-the-page",
    ),
    pytest.param(
        "content/legal/privacy/index.md",
        "- **Retention**: the brochure and the mention of her on the page stay published until she or I take them down, which removes the link, the file and the page's description of her together.",
        "- **Retention**: the brochure stays published until she or I take it down, which removes both the link and the file together. Nothing else on the page is affected.",
        "tests/test_partner_disclosure_surfaces.py::test_the_retention_promise_reaches_every_declared_surface",
        id="partner-disclosure-retention-narrowed-behind-both-surface-nouns",
    ),
    # The enumerator itself: a new content surface starts naming her and nobody
    # declares it. This is the row that makes the gate a CLASS fix rather than a
    # sixth instance fix.
    pytest.param(
        "content/legal/sub-processors/index.md",
        "## Cross-references",
        "## Cross-references\n\nJolyn Pek.",
        "tests/test_partner_disclosure_surfaces.py::test_every_shipped_surface_naming_the_partner_is_declared",
        id="partner-disclosure-undeclared-new-surface-names-the-partner",
    ),
]


def _cold_bytecode_env() -> dict:
    """Environment that guarantees the subprocess cannot import stale bytecode.

    Python validates a cached `.pyc` against the source's (mtime, size). A
    mutation that is the SAME LENGTH as what it replaces leaves the size
    unchanged, and a rewrite inside the filesystem's mtime granularity can leave
    that unchanged too, so the subprocess silently imports the ORIGINAL code and
    the mutant appears to survive.

    That is not hypothetical. `feed-vacuity-floor-accepts-an-unbuilt-tree` mutates
    `MIN_FEEDS = 6` to `MIN_FEEDS = 0`, both 13 bytes. Run alone the row passed;
    run inside the full suite, after an earlier row had warmed
    `scripts/__pycache__`, it reported `15 passed` from the target and failed with
    "VACUOUS GATE" against a guard that is not vacuous at all.

    Redirecting the cache to a fresh directory per invocation means every
    subprocess starts cold, so no earlier row can poison a later one, and the
    harness stops writing `__pycache__` into the repo as a side effect. This
    fails in the SAFE direction either way (a stale import makes a row cry
    vacuous, never green), but a gate harness that cries wolf gets ignored, and
    on this repo it would redden CI on main and hold the deploy hook shut.
    """
    env = dict(os.environ)
    env["PYTHONPYCACHEPREFIX"] = tempfile.mkdtemp(prefix="mutation-pycache-")
    return env


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

    # STALE TARGET guard. `test_file` may be a pytest NODE ID, and pytest exits
    # 4 on a node id that matches nothing ("no tests ran"). Since the assertion
    # below is `returncode != 0`, a renamed or deleted test would make this row
    # PASS while proving nothing at all: the mutation would be scored as caught
    # by a test that never ran. That is the "a self-check must not read as a
    # catch" rule (mutation-verification.md sweep quality gate 6), and the hazard
    # is real rather than theoretical -- a test renamed during the hoiboy-uk#59
    # rework re-validation left exactly this stale target behind.
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", str(ROOT / test_file), "--collect-only", "-q",
         "-p", "no:cacheprovider"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert collected.returncode == 0, (
        f"STALE TARGET, not a defect detected: `{test_file}` collects nothing, so "
        "this row cannot prove the mutation is caught. A node id that matches no "
        "test makes pytest exit non-zero for the WRONG reason, which would score "
        "as a catch. Update the row to the test's current name.\n"
        f"{collected.stdout[-500:]}"
    )

    backup = Path(tempfile.mkdtemp()) / "backup"
    shutil.copy(src, backup)
    try:
        src.write_text(original.replace(now, reverted, 1), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(ROOT / test_file), "-q", "-p", "no:cacheprovider"],
            capture_output=True, text=True, cwd=ROOT, env=_cold_bytecode_env(),
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
