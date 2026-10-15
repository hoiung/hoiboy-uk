"""AGIT signup page: consent-version traceability and copy checks (#65 AC 1.7(b), AC 3.1).

The join page (content/community/agit-join/index.md) posts to the newsletter
endpoint with audience=agit and carries TWO consent boxes:

  1. the required membership box, whose hidden member_consent_version must be
     in KNOWN_AGIT_CONSENT_VERSIONS (functions/api/subscribe.js) and in the
     mirror in tests/subscribe.test.js, and
  2. the optional newsletter box, which must be the footer form's box exactly:
     the same label and the same hidden consent_version as
     layouts/_partials/subscribe-form.html, or a member would be recorded as
     agreeing to newsletter wording they never saw.

A content page cannot read site params, so the join page carries its own copy
of the form action and the Turnstile site key; both are pinned to
config/_default/params.toml here.

The last two tests read the BUILT page (public/), so CI runs this file after
the Hugo build. A missing built page fails loudly rather than skipping, because
a skipped copy check would pass while checking nothing.
"""

from __future__ import annotations

import html
import re
import sys
import tomllib
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from consent_version_surfaces import (  # noqa: E402
    REPO,
    assignment_expression,
    hidden_input_version,
    js_string_list,
)

JOIN = REPO / "content" / "community" / "agit-join" / "index.md"
FOOTER_FORM = REPO / "layouts" / "_partials" / "subscribe-form.html"
ENDPOINT = REPO / "functions" / "api" / "subscribe.js"
JS_TEST = REPO / "tests" / "subscribe.test.js"
PARAMS = REPO / "config" / "_default" / "params.toml"
BUILT_JOIN = REPO / "public" / "community" / "asians-gingers-in-tech" / "join" / "index.html"

# The approved C1 sentences that carry the operator's asks (#65 User Brief +
# Stage-3 sign-off R10): signing up is required to attend, once, free, why the
# WhatsApp link is private, and photos and videos at events.
BRIEF_SENTENCES = (
    "You need to sign up to attend our events.",
    "You only need to sign up once and become a member of our AGIT community and join our WhatsApp group.",
    "This is mandatory.",
    "The membership is free because we're a self-contributing community where members give to build what we have.",
    "Our WhatsApp link used to be public on Meetup, and we have been bombarded by crypto and stock bots "
    "spamming our groups constantly.",
    "Attendees to our events may take photos and videos and share them.",
    "AGIT's own channels may share them too, but never in adverts.",
)


def _label_for(text: str, control_id: str) -> str:
    match = re.search(rf'<label for="{re.escape(control_id)}">(.*?)</label>', text, re.DOTALL)
    assert match, f"no <label for={control_id!r}> found"
    return match.group(1).strip()


def _input_id(text: str, name: str) -> str:
    match = re.search(rf'<input type="checkbox" id="([^"]+)" name="{re.escape(name)}"', text)
    assert match, f"no checkbox named {name!r}"
    return match.group(1)


def test_join_page_membership_version_is_accepted_by_the_endpoint():
    rendered = hidden_input_version(JOIN, "member_consent_version")
    accepted = js_string_list(ENDPOINT, "KNOWN_AGIT_CONSENT_VERSIONS")
    assert rendered in accepted, (
        f"the join page posts member_consent_version={rendered!r} but subscribe.js accepts "
        f"{accepted!r}; every AGIT signup would be rejected with a 400"
    )


def test_js_mirror_matches_the_endpoint_agit_list():
    assert js_string_list(JS_TEST, "KNOWN_AGIT_CONSENT_VERSIONS_MIRROR") == js_string_list(
        ENDPOINT, "KNOWN_AGIT_CONSENT_VERSIONS"
    ), "tests/subscribe.test.js KNOWN_AGIT_CONSENT_VERSIONS_MIRROR has drifted from subscribe.js"


def test_the_membership_version_is_read_without_a_default():
    expression = assignment_expression(ENDPOINT.read_text(encoding="utf-8"), "memberConsentVersion")
    assert not re.search(r"\|\||\?\?", expression), (
        f"subscribe.js defaults member_consent_version ({expression.strip()!r}); that would "
        "record agreement to wording the member never saw"
    )


def test_join_page_newsletter_box_is_the_footer_box():
    join = JOIN.read_text(encoding="utf-8")
    footer = FOOTER_FORM.read_text(encoding="utf-8")
    assert hidden_input_version(JOIN, "consent_version") == hidden_input_version(
        FOOTER_FORM, "consent_version"
    ), "the join page's newsletter consent_version differs from the footer form's"
    assert _label_for(join, _input_id(join, "consent")) == _label_for(
        footer, _input_id(footer, "consent")
    ), "the join page's newsletter label differs from the footer form's"


def test_join_page_action_and_site_key_match_site_params():
    params = tomllib.loads(PARAMS.read_text(encoding="utf-8"))
    join = JOIN.read_text(encoding="utf-8")
    actions = re.findall(r'<form method="POST" action="([^"]+)"', join)
    keys = re.findall(r'class="[^"]*cf-turnstile[^"]*" data-sitekey="([^"]+)"', join)
    assert actions == [params["subscribeAction"]], f"form action {actions!r} vs params {params['subscribeAction']!r}"
    assert keys == [params["turnstileSiteKey"]], f"site key {keys!r} vs params {params['turnstileSiteKey']!r}"


class _Inputs(HTMLParser):
    """Every <input> on a page (attribute dict per input), plus the visible text."""

    def __init__(self) -> None:
        super().__init__()
        self.inputs: list[dict[str, str | None]] = []
        self.text: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag == "input":
            self.inputs.append(dict(attrs))
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.text.append(data)


def _built_join() -> _Inputs:
    assert BUILT_JOIN.is_file(), (
        f"{BUILT_JOIN.relative_to(REPO)} is missing; run `hugo --gc --minify -e production` first"
    )
    parser = _Inputs()
    parser.feed(BUILT_JOIN.read_text(encoding="utf-8"))
    return parser


def test_newsletter_box_on_the_join_page_is_optional():
    """newsletter box on the join page is optional; the membership box is required."""
    inputs = _built_join().inputs
    # Named checkboxes only: the site menu's toggle is an unnamed checkbox on every page.
    by_name = {i["name"]: i for i in inputs if i.get("type") == "checkbox" and i.get("name")}
    assert set(by_name) == {"consent", "member_consent"}, f"checkboxes on the join page: {sorted(by_name)}"
    assert "checked" not in by_name["consent"], "the newsletter box is ticked by default"
    assert "required" not in by_name["consent"], "the newsletter box is mandatory on the join page"
    assert "required" in by_name["member_consent"], "the membership box is not required"


def test_join_page_says_what_his_brief_asked():
    """join page says what his brief asked: required to attend, once, free, why, photos."""
    raw = " ".join(_built_join().text)
    text = re.sub(r"\s+", " ", html.unescape(raw)).replace("’", "'").replace("‘", "'")
    missing = [s for s in BRIEF_SENTENCES if s not in text]
    assert not missing, f"the built join page no longer says: {missing}"
