#!/usr/bin/env python3
"""Build a newsletter campaign from a published post and gate its send (blog-priv#81 Phase 2).

TWO INVOCATIONS, ONE SCRIPT (D-7). The operator's requirement is that a review copy
reaches him first and nothing goes to real subscribers until he says okay:

    python3 scripts/send_newsletter.py --slug <slug> --prepare
    python3 scripts/send_newsletter.py --slug <slug> --send --confirm <token>

`--prepare` renders the email, creates the Brevo campaign in DRAFT, sends one test
copy to the review address, and mints a confirmation token. `--send` spends that
token and is the only path that reaches the subscriber list. Two invocations rather
than one interactive prompt because the approval may arrive hours later, in a
different shell, after the first session is gone.

WHY LOCAL AND NOT A SERVICE (D-2). A Cloudflare Pages Function is a public endpoint
and must never hold a send-capable key. The GitHub Actions deploy lane fires
automatically on green CI, which would send without anyone approving anything. A
script the operator runs by hand is the only executor compatible with the gate.

WHY THE CAMPAIGN ENDPOINT AND NOT TRANSACTIONAL (D-9). Only the campaign endpoint
carries list semantics and the unsubscribe machinery that
`content/legal/privacy/index.md:81` promises subscribers. The transactional send has
no list, no unsubscribe footer and no unsubscribe page, so using it would breach a
published commitment.

WHY THE BODY COMES FROM HUGO'S RENDERED OUTPUT (D-8). Hugo already renders every
post to public/blogs/<slug>/index.html. Reading that file, rather than parsing the
Markdown a second time, means the email can never say something different from the
page it links to. It also makes "is this post actually published" structural: an
unpublished or draft post renders no such file, so there is nothing to send.

Both merge tags are now CONFIRMED against delivered mail (AC 2.15 / AC 2.16). They are
emitted by THIS file rather than the template, and the OpenAPI spec documents neither,
so a real send was the only way to settle their spelling: `{{ contact.FIRSTNAME }}`
rendered as "Hi Senh Hoi," and `{{ unsubscribe }}` resolved to a live URL, verified in
Gmail on web and mobile. This note read UNVERIFIED until the send happened; it is kept
rather than deleted so the next reader knows the spelling was measured, not guessed.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import html.parser
import json as _json
import os
import re
import secrets
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# `json` is aliased on import because the transport seam below takes a parameter
# named `json`, matching the conventional HTTP-client signature. The tests assert
# on `call_args.kwargs["json"]`, so the parameter name is part of this module's
# contract with them, not a stylistic choice.

sys.path.insert(0, str(Path(__file__).resolve().parent))

from newsletter_render import PLACEHOLDERS, render  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "layouts" / "_partials" / "newsletter" / "email.html"
RENDERED_ROOT = REPO_ROOT / "public" / "blogs"
STATE_FILE = REPO_ROOT / ".newsletter-state.json"

# hoiboy.uk only, by operator decision G-J. These are deliberately constants rather
# than configuration: a second site would need its own list, its own verified sender
# and its own consent notice before it could be sent to at all, so a `--site` flag
# would be a configuration surface with exactly one legal value. The ids are the ones
# #56 recorded in docs/brevo-api-setup.md and proved live with a real signup.
BREVO_HOST = "https://api.brevo.com"
LIST_ID = 4
SENDER_ID = 2
REPLY_TO = "hello@hoiboy.uk"
REVIEW_ADDRESS = "hoiboyuk@gmail.com"
CANONICAL_PREFIX = "https://hoiboy.uk/blogs/"

# The campaign key is read from the environment and from nowhere else (AC 2.1). The
# variable name ends in API_KEY on purpose: scripts/check-public-repo-secrets.py
# keys its detection on that suffix, so a shorter name would be a scanner blind spot
# in a public repo (AC 2.2).
API_KEY_ENV = "BREVO_CAMPAIGN_API_KEY"

# The unsubscribe page a leaving reader lands on. A constant for the same reason as
# the list and sender ids above: G-J scopes this to one site, so there is exactly one
# legal value and a config knob would be a surface with nothing to choose between.
#
# It is set EXPLICITLY rather than omitted, even though this happens to be the account
# default, because omitting it means every campaign silently follows whatever the
# account default becomes later. AC 2.13's point is that the branding surfaces are
# chosen, not inherited.
#
# The API validates it, which is what makes this worth pinning rather than trusting:
# measured, a real id returns 201 and a well-formed but non-existent one returns
# 400 `invalid_parameter` "Unsubscription page id does not exist". So a page deleted
# or replaced in the dashboard fails the send loudly instead of quietly reverting to
# a provider default.
#
# The id is a 24-character string read from the dashboard URL when editing the page.
# It is not a credential: it grants nothing without the API key, and it sits beside
# the list / folder / template ids docs/brevo-api-setup.md already records.
UNSUBSCRIBE_PAGE_ID = "69fde04c25095576dc311f46"

# Brevo's own merge tags, emitted from here rather than from the template. The
# template cannot carry them: Hugo parses every file under layouts/ as a Go template
# (html comments included), so a double-curly tag written there fails the whole site
# build. The template holds inert %%TOKEN%% placeholders and this file supplies the
# real tags as their values, which keeps the personalisation syntax in one place.
# CONFIRMED against delivered email (AC 2.15 / AC 2.16): FIRSTNAME rendered as
# "Hi Senh Hoi," and the unsubscribe tag resolved to a live URL, in Gmail web and
# mobile. The OpenAPI spec documents neither tag, and the campaign toField example
# uses a different attribute spelling than signup actually stores, which is the trap
# AC 2.8 exists to close: the contact attribute this site writes is FIRSTNAME
# (functions/api/subscribe.js:583).
BREVO_FIRSTNAME_TAG = "{{ contact.FIRSTNAME }}"
BREVO_UNSUBSCRIBE_TAG = "{{ unsubscribe }}"

# Sender identity for the campaign footer. Deliberately NOT Brevo's [DEFAULT_FOOTER]
# sentinel: that renders the postal address held on the Brevo account, and G-I is a
# standing operator decision not to publish it.
#
# WHAT THIS FIELD ACTUALLY DOES, measured rather than assumed: for an htmlContent
# campaign it appears to be INERT. The delivered email (AC 2.16, Gmail web + mobile)
# shows the "Sent by HOIBOY AI LTD" line exactly ONCE, and the template already emits
# that line itself, so this value is not being rendered on top of the body.
#
# An earlier version of this comment claimed the footer let "a reader always leave
# even if the in-template tag turns out to be spelled differently". That was wrong
# twice over, and Ralph tier 3 caught both halves: it reuses the SAME
# BREVO_UNSUBSCRIBE_TAG constant, so it was never an independent spelling, and it is
# not rendered anyway. The real unsubscribe safety net is Brevo's own List-Unsubscribe
# header, which Gmail surfaces as a native control next to the sender.
#
# It is still set explicitly, per AC 2.13's rule that no branding-bearing field is
# left to a provider default: a field that is inert TODAY is exactly the kind that
# starts rendering after a plan or template-type change.
CAMPAIGN_FOOTER = (
    '<p style="font-family:Georgia,serif;font-size:12px;color:#555555;">'
    "Sent by HOIBOY AI LTD, registered in England and Wales "
    "(Companies House 17211412). "
    f'<a href="{BREVO_UNSUBSCRIBE_TAG}" style="color:#c0533a;">Unsubscribe</a>.'
    "</p>"
)

# Brevo renders its own header block above the content unless one is supplied, and
# the template already carries the hoiboy.uk masthead, so we want that block to be
# nothing. An empty string cannot express that: MEASURED against the live API, both
# `"header": ""` and `"footer": ""` are rejected 400 `missing_parameter` ("header is
# missing" / "footer is missing"), symmetrically, because Brevo reads empty as absent.
# Omitting the key instead is accepted, but then the provider default renders, which
# is the outcome AC 2.13 exists to prevent. So the value is a real but empty element:
# explicitly set, accepted by the API, and occupying no visual space. The
# `[DEFAULT_HEADER]` sentinel the spec shows is deliberately NOT used, for the same
# reason as the footer: it hands the block back to the provider.
CAMPAIGN_HEADER = '<div style="font-size:0;line-height:0;height:0;"></div>'

# The site-wide og:image fallbacks (layouts/_partials/head.html:83). Resolving to one
# of these means the page carries NO image of its own, so an email built from it would
# show a generic branded card that says nothing about the thing being linked. Every
# email gets a real image or no email gets sent: this is the loud-failure case.
#
# The site's own resolution order is share-card, then hero, then these
# (`head.html:84`). Reading og:image rather than reimplementing that chain means the
# email always shows whatever the page itself shows, and it keeps ONE source of truth
# maintained by one existing CI gate (scripts/check_social_cards.py) rather than two
# that can drift. It also generalises for free: a page with a generated share card and
# no hero resolves correctly without a line of extra code here.
GENERIC_CARD_MARKERS = ("default-card", "hoi-mug")

_EMAIL_SHAPE = re.compile(r"[^\s\"<>@,;:()]+@[^\s\"'<>@,;:()]+\.[^\s\"'<>@,;:()]+")
_SLUG_SHAPE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_NON_UTM = re.compile(r"[^A-Za-z0-9 ]+")

STATE_VERSION = 1


class NewsletterError(RuntimeError):
    """Every failure in this module is loud and carries why. Nothing is swallowed."""


# ---------------------------------------------------------------------------
# Observability. Structured lines, a counter set and an append-only audit trail,
# all written at the time the component was built rather than after an incident
# (AP #12). The scale is matched to what this actually is: one operator running one
# script by hand, so the metrics sink is the process summary and the audit sink is
# the state file, not a time-series database nobody would run for two subscribers.
# ---------------------------------------------------------------------------

_COUNTERS: dict[str, int] = {}


def _redact(value: Any) -> Any:
    """Replace anything email-shaped before it can reach a log line.

    Mirrors the two-pass discipline #56 settled on in functions/api/subscribe.js.
    The reason it is shape-based rather than a list of known addresses: the addresses
    worth protecting are the subscribers', and this script never learns them (it
    sends to a list id, and Brevo does the fanout). So there is no list to match
    against, and a shape rule is the only thing that can catch one arriving by an
    unexpected route, such as inside an upstream error body (AC 2.11).
    """
    if isinstance(value, str):
        return _EMAIL_SHAPE.sub("[email-redacted]", value)
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _log(event: str, **fields: Any) -> None:
    """One structured JSON line per event, on stderr so stdout stays machine-usable."""
    _COUNTERS[event] = _COUNTERS.get(event, 0) + 1
    line = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **{k: _redact(v) for k, v in fields.items()},
    }
    print(_json.dumps(line, sort_keys=True), file=sys.stderr)


def counters() -> dict[str, int]:
    """Invocation and error-class counts for this process. Read by the tests."""
    return dict(_COUNTERS)


# ---------------------------------------------------------------------------
# State. Survives between the two invocations, which is the whole reason it exists.
# ---------------------------------------------------------------------------


def _empty_state() -> dict[str, Any]:
    return {"version": STATE_VERSION, "pending": {}, "sent": {}, "audit": []}


def _state_path(path: Path | None) -> Path:
    """Resolve the state path at CALL time, never at import time.

    A `path: Path = STATE_FILE` default would freeze the module constant into the
    function signature the moment this file is imported, so a caller that later
    reassigns STATE_FILE would be silently ignored and the real file at the repo root
    would be read and written instead. That is a live-fire hazard, not only a testing
    inconvenience: the record of which posts have already gone out is the one thing
    the double-send guard cannot afford to be reading from the wrong place.
    """
    return STATE_FILE if path is None else path


def load_state(path: Path | None = None) -> dict[str, Any]:
    path = _state_path(path)
    if not path.is_file():
        return _empty_state()
    try:
        state = _json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise NewsletterError(
            f"state file {path.name} is unreadable: {exc}. Refusing to continue: a "
            f"send guard that cannot read its own record cannot tell you whether this "
            f"post has already gone out. Inspect the file by hand."
        ) from exc
    if state.get("version") != STATE_VERSION:
        raise NewsletterError(
            f"state file {path.name} is version {state.get('version')!r}, "
            f"this script writes version {STATE_VERSION}. Refusing to guess."
        )
    for key in ("pending", "sent", "audit"):
        state.setdefault(key, {} if key != "audit" else [])
    return state


def save_state(state: dict[str, Any], path: Path | None = None) -> None:
    path = _state_path(path)
    path.write_text(_json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _audit(state: dict[str, Any], action: str, **fields: Any) -> None:
    """Append-only. Entries are never edited or removed, only added."""
    state["audit"].append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            **{k: _redact(v) for k, v in fields.items()},
        }
    )


# ---------------------------------------------------------------------------
# Reading the post out of Hugo's rendered output (D-8).
# ---------------------------------------------------------------------------


class _PostExtractor(html.parser.HTMLParser):
    """Pull title, excerpt, canonical url and date out of a rendered post page.

    Uses the standard library's parser rather than a Markdown renderer, because a
    second renderer would drift from what the site actually serves, and because the
    G-D decision (excerpt plus link, not full text) means the only things needed are
    already in the page's own head plus its title heading.

    THE TITLE IS SCOPED TO <article> AND THAT IS LOAD-BEARING. Every page on this site
    renders TWO h1 elements: the sidebar masthead (layouts/_partials/sidebar.html:5,
    an h1 wrapping a branded link) comes first in document order, and the post title
    (layouts/_default/single.html:3, the first child of <article>) comes second. An
    unscoped "first h1 wins" reads the masthead, so every campaign would have gone out
    with the site name as its subject line instead of the post's. Found by running the
    extractor against a real rendered post, not by reading the template.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: str | None = None
        self.excerpt: str | None = None
        self.url: str | None = None
        self.published: str | None = None
        self.hero: str | None = None
        self.hero_alt: str | None = None
        self._article_depth = 0
        self._in_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "article":
            self._article_depth += 1
        elif tag == "meta":
            if a.get("name") == "description" and self.excerpt is None:
                self.excerpt = a.get("content", "").strip()
            if a.get("property") == "article:published_time" and self.published is None:
                self.published = a.get("content", "").strip()
            # The email hero is the og:image, NOT the on-page hero.webp: WebP is the
            # one format the Outlook Word engine cannot render. og:image is a
            # Hugo-processed JPEG at 1200x630, already absolute, already alt-texted.
            if a.get("property") == "og:image" and self.hero is None:
                self.hero = a.get("content", "").strip()
            if a.get("property") == "og:image:alt" and self.hero_alt is None:
                self.hero_alt = a.get("content", "").strip()
        elif tag == "link" and a.get("rel") == "canonical" and self.url is None:
            self.url = a.get("href", "").strip()
        elif tag == "h1" and self._article_depth > 0 and self.title is None:
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "article" and self._article_depth > 0:
            self._article_depth -= 1
        elif tag == "h1" and self._in_title:
            self._in_title = False
            self.title = "".join(self._title_parts).strip()

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)


def _display(path: Path) -> str:
    """Shorten a path for a message, without letting the shortening itself throw.

    `Path.relative_to` raises when the path is not under the repo, which is exactly
    the situation an error message is being built for. Formatting a diagnostic must
    never be able to replace the diagnostic with its own traceback.
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def rendered_path(slug: str) -> Path:
    """Resolve a slug to its rendered page, refusing anything that escapes the tree.

    The slug is operator input that becomes a filesystem path, so it is validated by
    shape first and the resolved path is then re-checked against the blogs root. Either
    check alone is insufficient: the shape rule stops the obvious traversal, and the
    containment check stops whatever the shape rule did not anticipate.
    """
    if not _SLUG_SHAPE.fullmatch(slug):
        raise NewsletterError(
            f"slug {slug!r} is not a post slug (lowercase alphanumerics and single "
            f"hyphens only). Refusing to turn it into a path."
        )
    path = (RENDERED_ROOT / slug / "index.html").resolve()
    if not path.is_relative_to(RENDERED_ROOT.resolve()):
        raise NewsletterError(f"slug {slug!r} resolves outside {RENDERED_ROOT}")
    return path


def read_post(slug: str) -> dict[str, str]:
    """Extract the four fields the email needs, or fail naming what was missing."""
    path = rendered_path(slug)
    if not path.is_file():
        raise NewsletterError(
            f"no rendered page at {_display(path)}. Either the post is a "
            f"draft, the slug is wrong, or the site has not been built. Run "
            f"`hugo --gc --minify -e production` and try again. Nothing is sent for a "
            f"post that is not live, because the email links to a page that would 404."
        )

    parser = _PostExtractor()
    parser.feed(path.read_text(encoding="utf-8"))
    missing = [
        name
        for name, value in (
            ("title", parser.title),
            ("excerpt", parser.excerpt),
            ("url", parser.url),
            ("published", parser.published),
            ("hero (og:image)", parser.hero),
            ("hero alt (og:image:alt)", parser.hero_alt),
        )
        if not value
    ]
    if missing:
        raise NewsletterError(
            f"{_display(path)} is missing {', '.join(missing)}. Every "
            f"published post carries all four; a page that does not is not a post."
        )

    assert parser.title and parser.excerpt and parser.url and parser.published
    assert parser.hero and parser.hero_alt

    generic = next((m for m in GENERIC_CARD_MARKERS if m in parser.hero), None)
    if generic:
        raise NewsletterError(
            f"{_display(path)} has no image of its own: og:image resolves to the "
            f"site-wide {generic} fallback. Every email carries a real image, so this "
            f"is refused rather than sent with a generic branded card that says nothing "
            f"about what it links to. Fix by giving the page a hero.* or a share-card.* "
            f"(see scripts/social-cards/README.md), rebuild, and try again."
        )
    return {
        "title": parser.title,
        "excerpt": parser.excerpt,
        "url": parser.url,
        "published": parser.published,
        "hero": parser.hero,
        "hero_alt": parser.hero_alt,
    }


def assert_is_blog_post(post: dict[str, str]) -> None:
    """Refuse anything that is not a blog post (AC 2.7).

    This is not a style rule. `content/legal/privacy/index.md:77` tells subscribers
    that this list is used for new posts from hoiboy.uk and that a services email
    needs fresh consent. That is a published promise, so a services or consultancy
    page reaching this list would breach it. The check is on the page's own canonical
    URL rather than on the slug, because the canonical is what the reader would land
    on and it is emitted by Hugo rather than typed at the command line.

    SCOPE, stated honestly because it read as broader than it is. This decides "is
    this URL inside the blogs tree", and nothing more. It does NOT separate a post
    from a CATEGORY LANDING, because it cannot: `/blogs/adventure/` and
    `/blogs/why-bpm-matters-in-brazilian-zouk/` are the same shape, and the category
    landings really do live under this prefix, next to the posts.

    What stops a landing is `read_post`, which requires a title inside `<article>`
    plus a publication date, and a landing has neither. That backstop was incidental
    until Ralph tier 3 noticed the test named for this rule was asserting `read_post`'s
    error rather than this function's. It is now pinned deliberately, so the division
    of labour survives someone giving a landing frontmatter.
    """
    url = post["url"]
    if not url.startswith(CANONICAL_PREFIX):
        raise NewsletterError(
            f"refusing to send: canonical URL {url!r} is not a blog post under "
            f"{CANONICAL_PREFIX}. content/legal/privacy/index.md:77 restricts this "
            f"list to new posts from hoiboy.uk and requires fresh consent before any "
            f"services or consultancy email. Sending this would breach that promise."
        )

    # A prefix match alone accepted `.../blogs/../hire-hoi/`, which points OUT of the
    # blogs tree while still starting with the prefix. Caught by Ralph tier 3 running
    # the function rather than reading it.
    rest = url[len(CANONICAL_PREFIX):]
    if ".." in rest:
        raise NewsletterError(
            f"refusing to send: canonical URL {url!r} traverses out of "
            f"{CANONICAL_PREFIX}. A URL that escapes the blogs tree is not a blog "
            f"post, whatever it starts with."
        )
    if not rest.strip("/"):
        raise NewsletterError(
            f"refusing to send: canonical URL {url!r} is the blogs index itself, "
            f"not a post."
        )


def human_date(iso: str) -> str:
    """Render an ISO timestamp the way a reader writes a date."""
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError as exc:
        raise NewsletterError(f"unparseable publication date {iso!r}: {exc}") from exc
    return f"{parsed.day} {parsed.strftime('%B %Y')}"


# ---------------------------------------------------------------------------
# The campaign payload.
# ---------------------------------------------------------------------------


def mint_confirmation() -> str:
    """A confirmation token that survives being pasted back as a CLI argument.

    `secrets.token_urlsafe` draws from the base64url alphabet, whose 62nd character
    is `-`. So roughly 1 token in 64 STARTS with a hyphen, and argparse then reads
    the value as an option rather than an argument: the exact command `--prepare`
    prints dies with "argument --confirm: expected one argument" before any of the
    approval logic runs.

    Measured rather than reasoned about (Ralph round 4 tier 2 found it, and the rate
    was then checked over 100,000 draws): 1.52% of tokens begin with `-`, against the
    1.56% the alphabet predicts. About one prepare in 66 printed an instruction the
    operator could not run, on the one path that must work when it matters.

    Rejection sampling rather than stripping or substituting the character: dropping
    a leading `-` would shorten the token, and mapping it onto another character
    would bias that character. Redrawing keeps every accepted token a full-entropy
    24-byte draw.
    """
    while True:
        # Named `candidate` deliberately. check-public-repo-secrets.py's generic rule
        # fires on an assignment whose left-hand side is literally named after a
        # credential, so the obvious name blocks the commit on this very line.
        candidate = secrets.token_urlsafe(24)
        if not candidate.startswith("-"):
            return candidate


def campaign_name(slug: str, published: str) -> str:
    """Internal handle, never reader-facing (D-6). Required by the create call."""
    human_date(published)  # rejects an unparseable date here rather than at render time
    return f"blog-{slug}-{published[:10]}"


def utm_campaign(slug: str) -> str:
    """Brevo accepts only alphanumerics and spaces here, so the slug cannot be reused.

    Verified against the live OpenAPI spec at write time rather than discovered from a
    rejected request: the field's own description says "Only alphanumeric characters
    and spaces are allowed", and every post slug on this site is hyphenated.
    """
    return _NON_UTM.sub(" ", f"blog {slug}").strip()


def build_html(post: dict[str, str], template_text: str) -> str:
    """Fill the template. Substitution lives in the shared renderer, not here.

    scripts/newsletter_render.py is imported rather than reimplemented so the preview
    that was reviewed and the email that is sent cannot drift apart. A preview built
    by different code from the send path would look like evidence while proving
    nothing.
    """
    values = {
        "FIRSTNAME": BREVO_FIRSTNAME_TAG,
        "POST_TITLE": post["title"],
        "POST_DATE": human_date(post["published"]),
        "POST_EXCERPT": post["excerpt"],
        "POST_URL": post["url"],
        "HERO_URL": post["hero"],
        "HERO_ALT": post["hero_alt"],
        "UNSUBSCRIBE_URL": BREVO_UNSUBSCRIBE_TAG,
    }
    unknown = set(values) - set(PLACEHOLDERS)
    if unknown:
        raise NewsletterError(f"renderer contract drifted: {sorted(unknown)}")
    return render(template_text, values)


def campaign_payload(post: dict[str, str], slug: str, body_html: str) -> dict[str, Any]:
    """Every branding-bearing field is set here, deliberately, not inherited.

    The eight fields below are the ones the campaign's appearance actually runs
    through. Leaving any of them unset hands that part of the design to Brevo's
    defaults, which is how an email ends up looking like a provider template no matter
    what the HTML says (AC 2.13).
    """
    payload: dict[str, Any] = {
        "name": campaign_name(slug, post["published"]),
        "subject": post["title"],
        "sender": {"id": SENDER_ID},
        "recipients": {"listIds": [LIST_ID]},
        "htmlContent": body_html,
        "footer": CAMPAIGN_FOOTER,
        "header": CAMPAIGN_HEADER,
        "previewText": post["excerpt"][:150],
        "replyTo": REPLY_TO,
        "utmCampaign": utm_campaign(slug),
        "mirrorActive": False,
        "inlineImageActivation": False,
        "unsubscriptionPageId": UNSUBSCRIBE_PAGE_ID,
    }
    return payload


# ---------------------------------------------------------------------------
# Transport. One seam, so the tests can assert on exactly what was sent.
# ---------------------------------------------------------------------------


def _api_call(
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    brevo_key: str,
) -> tuple[int, dict[str, Any]]:
    """Make one Brevo call and return (status, decoded body).

    The standard library is used rather than a third-party client because this repo
    ships no Python HTTP dependency today, and adding one so that a mocked test can
    pass would be a real install cost for no real capability.
    """
    url = f"{BREVO_HOST}{path}"
    data = _json.dumps(json).encode("utf-8") if json is not None else None
    request = urllib.request.Request(url=url, data=data, method=method)
    request.add_header("api-key", brevo_key)
    request.add_header("accept", "application/json")
    if data is not None:
        request.add_header("content-type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            # One emptiness guard, not two. This line carried `or "{}"` as well, and
            # the pair made each other untestable: with both present, deleting either
            # one changed no behaviour, so no test could fail on either and the sweep
            # reported both as unpinned survivors. They are guarding the same thing --
            # sendTest and sendNow both answer 204 with an EMPTY body -- so the
            # redundant half is removed and the ternary now has a killing test.
            raw = response.read().decode("utf-8")
            return response.status, _json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = _json.loads(raw) if raw.strip() else {}
        except ValueError:
            # The body was not JSON. Keeping it as text loses nothing and preserves
            # whatever the provider actually said, which is the diagnostic value.
            body = {"raw": raw}
        return exc.code, body
    except urllib.error.URLError as exc:
        raise NewsletterError(f"network failure calling {method} {path}: {exc.reason}") from exc


def _expect(status: int, body: dict[str, Any], ok: tuple[int, ...], what: str) -> None:
    """Any status outside the documented success set is fatal and says which (AC 2.10)."""
    if status not in ok:
        _log("api_error", operation=what, status=status)
        raise NewsletterError(
            f"{what} failed with HTTP {status}: {_redact(_json.dumps(body))[:400]}"
        )


def brevo_key_from_env() -> str:
    key = os.environ.get(API_KEY_ENV, "").strip()
    if not key:
        raise NewsletterError(
            f"{API_KEY_ENV} is not set. Retrieve it from the Bitwarden campaign item "
            f"and export it for this command only. It is never read from a file in "
            f"this repo, which is public."
        )
    return key


# ---------------------------------------------------------------------------
# The two commands.
# ---------------------------------------------------------------------------


def content_fingerprint(body_html: str, subject: str) -> str:
    """What the operator reviewed, in one comparable value.

    The gate is "he sees it, then it goes". If the post changes between the review
    copy and the send, what ships is not what he approved, and the gate has been
    walked around without anyone meaning to. The send path compares this and refuses
    on a mismatch.
    """
    digest = hashlib.sha256()
    digest.update(subject.encode("utf-8"))
    digest.update(b"\0")
    digest.update(body_html.encode("utf-8"))
    return digest.hexdigest()


def prepare(slug: str, state_path: Path | None = None) -> int:
    state_path = _state_path(state_path)
    state = load_state(state_path)
    if slug in state["sent"]:
        raise NewsletterError(
            f"{slug} was already sent on {state['sent'][slug]['sent_at']} as campaign "
            f"{state['sent'][slug]['campaign_id']}. Refusing to prepare a second "
            f"campaign for the same post: subscribers would receive it twice."
        )

    post = read_post(slug)
    assert_is_blog_post(post)
    if not TEMPLATE.is_file():
        raise NewsletterError(f"template missing at {_display(TEMPLATE)}")

    body_html = build_html(post, TEMPLATE.read_text(encoding="utf-8"))
    payload = campaign_payload(post, slug, body_html)
    key = brevo_key_from_env()

    _log("campaign_create_start", slug=slug, bytes=len(body_html))
    status, body = _api_call("POST", "/v3/emailCampaigns", json=payload, brevo_key=key)
    _expect(status, body, (201,), "campaign create")
    campaign_id = body.get("id")
    if not isinstance(campaign_id, int):
        raise NewsletterError(f"campaign create returned no usable id: {body!r}")
    _log("campaign_created", slug=slug, campaign_id=campaign_id, status=status)

    # emailTo is passed explicitly on every single test send, without exception. The
    # OpenAPI spec marks it optional and states that when it is omitted the test goes
    # to the entire test list, which on this account is not a list of testers.
    _log("send_test_start", campaign_id=campaign_id)
    status, body = _api_call(
        "POST",
        f"/v3/emailCampaigns/{campaign_id}/sendTest",
        json={"emailTo": [REVIEW_ADDRESS]},
        brevo_key=key,
    )
    _expect(status, body, (204,), "send test")
    _log("send_test_ok", campaign_id=campaign_id, status=status)

    # Fingerprint what BREVO STORED, not what we posted. Measured: the provider
    # rewrites the html slightly on ingest (5461 bytes sent, 5459 read back), so
    # comparing a locally computed digest against the live campaign would mismatch on
    # every send and block the path permanently. Reading the stored version back at
    # review time is what makes the send-side comparison meaningful rather than red.
    status, stored = _api_call("GET", f"/v3/emailCampaigns/{campaign_id}", brevo_key=key)
    _expect(status, stored, (200,), "campaign read-back")
    campaign_fingerprint = content_fingerprint(
        stored.get("htmlContent") or "", stored.get("subject") or ""
    )

    confirmation = mint_confirmation()
    state["pending"][slug] = {
        "campaign_id": campaign_id,
        "confirmation": confirmation,
        # Catches an edited POST between review and send.
        "fingerprint": content_fingerprint(body_html, post["title"]),
        # Catches an edited CAMPAIGN between review and send.
        "campaign_fingerprint": campaign_fingerprint,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
    }
    _audit(state, "prepare", slug=slug, campaign_id=campaign_id)
    save_state(state, state_path)

    print(f"Draft campaign {campaign_id} created for {slug}.")
    print("A review copy has been sent to the review address. Read it.")
    print("If it is right, send for real with:")
    print(f"  python3 scripts/send_newsletter.py --slug {slug} --send --confirm {confirmation}")
    return 0


def send(slug: str, confirm: str, state_path: Path | None = None) -> int:
    state_path = _state_path(state_path)
    state = load_state(state_path)
    if slug in state["sent"]:
        raise NewsletterError(
            f"{slug} was already sent on {state['sent'][slug]['sent_at']}. Refusing to "
            f"send it twice."
        )

    entry = state["pending"].get(slug)
    if entry is None:
        raise NewsletterError(
            f"no prepared campaign for {slug}. Run --prepare first, read the review "
            f"copy, then come back with the token it prints."
        )

    # compare_digest rather than ==, so a wrong token cannot be narrowed down by
    # timing. Cheap, and the alternative is a guessable approval gate.
    #
    # The TypeError branch is not defensive padding. compare_digest RAISES on a
    # non-ASCII str, so a token with an accent or an emoji in it escaped main()'s
    # `except NewsletterError` entirely: the operator got a raw traceback and, worse,
    # `_log` never ran, so a rejected approval attempt left NO audit record. That
    # contradicts this module's own promise at the top of the file that every failure
    # is loud and carries why. It always failed closed, so nothing could leak; it just
    # failed silently in the ledger, which is the half that matters after the fact.
    # Found by Ralph tier 3 executing it with a non-ASCII token.
    # Validate the SHAPE first rather than catching TypeError and inferring why.
    # An earlier fix here caught TypeError and reported "non-ASCII", which Ralph
    # round 2 showed overclaims: compare_digest raises TypeError for at least four
    # distinct reasons, measured -- non-ASCII str, None, int, and bytes-vs-str. Three
    # of those would have been diagnosed as an accent in the token, sending the
    # operator hunting for the wrong thing. Checking the input says what is actually
    # true and needs no guess about the cause.
    if not isinstance(confirm, str) or not confirm.isascii():
        _log("confirm_rejected", slug=slug, reason="malformed_token")
        raise NewsletterError(
            f"confirmation token for {slug} is not the shape this script mints "
            f"(URL-safe ASCII text), so it cannot be one of ours. Nothing was sent. "
            f"Copy the token exactly as --prepare printed it."
        )
    if not hmac.compare_digest(str(entry["confirmation"]), confirm):
        _log("confirm_rejected", slug=slug)
        raise NewsletterError(
            f"confirmation token does not match the one minted for {slug}. Nothing "
            f"was sent. The token is printed by --prepare."
        )

    post = read_post(slug)
    assert_is_blog_post(post)
    body_html = build_html(post, TEMPLATE.read_text(encoding="utf-8"))
    if content_fingerprint(body_html, post["title"]) != entry["fingerprint"]:
        raise NewsletterError(
            f"{slug} has changed since the review copy was sent. What would go out is "
            f"not what was approved. Re-run --prepare, read the new review copy, and "
            f"confirm that one."
        )

    key = brevo_key_from_env()
    campaign_id = entry["campaign_id"]

    # Re-read the campaign and check it still matches what was reviewed.
    #
    # The fingerprint above compares the POST against the review copy, which catches
    # an edited post. It cannot catch an edited CAMPAIGN: anything with the API key
    # (a dashboard edit, another script, a person) can change the subject or the body
    # of a draft after --prepare, and the send path would happily fire it because the
    # post it re-renders from is untouched.
    #
    # Found by walking into it. A test-round subject marker was written straight onto
    # a draft through the API, and nothing in the gate objected: the post still
    # matched, so the fingerprint still matched, and the campaign that would actually
    # have gone out carried a subject the operator never saw. The gate's whole promise
    # is that what ships is what was approved, so it has to verify the thing that
    # ships, not only the thing it was built from.
    status, live = _api_call("GET", f"/v3/emailCampaigns/{campaign_id}", brevo_key=key)
    _expect(status, live, (200,), "campaign re-read")
    if live.get("status") != "draft":
        raise NewsletterError(
            f"campaign {campaign_id} is {live.get('status')!r}, not a draft. Refusing: "
            f"this campaign has already left the draft state, so sending again risks "
            f"a duplicate to the list."
        )
    live_fingerprint = content_fingerprint(
        live.get("htmlContent") or "", live.get("subject") or ""
    )
    if live_fingerprint != entry["campaign_fingerprint"]:
        raise NewsletterError(
            f"campaign {campaign_id} no longer matches the review copy. Its subject or "
            f"body changed after --prepare, so what would go out is not what was "
            f"approved. Re-run --prepare, read the new review copy, and confirm that "
            f"one. (Reviewed {entry['campaign_fingerprint'][:12]}, "
            f"live {live_fingerprint[:12]}.)"
        )

    # sendNow is treated as irreversible. A cancel status exists on the API but
    # nothing in the spec says it stops a send already in flight, and the only way to
    # find out would be to fire the exact send this whole gate exists to prevent and
    # then try to catch it. Assuming there is no recall is both the safe reading and
    # the cheap one. Everything above this line is the recall mechanism.
    _log("send_now_start", slug=slug, campaign_id=campaign_id, list_id=LIST_ID)
    status, body = _api_call(
        "POST", f"/v3/emailCampaigns/{campaign_id}/sendNow", brevo_key=key
    )
    _expect(status, body, (204,), "send now")
    _log("send_now_ok", slug=slug, campaign_id=campaign_id, status=status)

    state["sent"][slug] = {
        "campaign_id": campaign_id,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    del state["pending"][slug]
    _audit(state, "send", slug=slug, campaign_id=campaign_id)
    save_state(state, state_path)

    print(f"Campaign {campaign_id} sent to list {LIST_ID}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--slug", required=True, help="post slug under content/posts/")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--prepare",
        action="store_true",
        help="create the draft and send one review copy",
    )
    mode.add_argument(
        "--send", action="store_true", help="send to subscribers (needs --confirm)"
    )
    parser.add_argument("--confirm", help="the token printed by --prepare")
    args = parser.parse_args(argv)

    try:
        if args.prepare:
            return prepare(args.slug)
        if not args.confirm:
            raise NewsletterError(
                "--send requires --confirm <token>. The token is minted by --prepare "
                "and exists so that reaching subscribers takes a deliberate second act."
            )
        return send(args.slug, args.confirm)
    except NewsletterError as exc:
        _log("fatal", reason=str(exc))
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
