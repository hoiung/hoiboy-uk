#!/usr/bin/env python3
"""AGIT email-approval automation (hoiboy-uk #48 Phase 4).

Sends the exact final wording of a member feature to the submitter and detects
their approval reply, so the publish gate can hard-fail until approval is on file.

Least-privilege by design (see docs/gmail-approval-oauth-setup.md):
  * OAuth scopes: gmail.send + gmail.readonly, on a dedicated OAuth client for
    hoiboyuk@gmail.com. NOT a broad IMAP/SMTP app-password.
  * Application-level restriction: only ever reads the approval thread it created
    (tracked by threadId); it never browses the mailbox.
  * The token + client secret live OUTSIDE the repo; nothing is committed.

The pure logic (compose / detect approval / record) has NO google dependency and
is fully unit-tested. The Gmail I/O takes an injected `service` object, so it is
testable with a fake; the real OAuth service builder (`build_gmail_service`)
lazily imports the google libraries and is only reached at runtime, once the
operator has granted credentials.

Approval detection is deliberately strict and fail-safe: a reply approves only if
it carries an affirmative phrase AND no negation phrase. Anything ambiguous is
NOT approval. No approval, no publish.

Issue: hoiung/hoiboy-uk#48 (Phase 4)
Exit codes (CLI): 0 = ok, 1 = no approval yet / not approved, 2 = usage/IO error
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from functools import lru_cache
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path(__file__).with_name("agit-feature-edit-check.config.yaml")
APPROVAL_FILE = "approval.json"
REQUEST_FILE = "approval_request.json"
# Read-only + send-only. Deliberately NOT gmail.modify or full-mailbox access.
GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
)


def load_approval_phrases(config_path: Path = DEFAULT_CONFIG) -> tuple[list[str], list[str]]:
    """Load (affirmative, negation) phrase lists from the pipeline config."""
    if not config_path.is_file():
        raise FileNotFoundError(f"config not found: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    approval = raw.get("approval", {})
    affirmative = [str(p).lower() for p in approval.get("affirmative_phrases", [])]
    negation = [str(p).lower() for p in approval.get("negation_phrases", [])]
    if not affirmative:
        raise ValueError("config approval.affirmative_phrases is empty")
    return affirmative, negation


# Apostrophe-class characters are stripped from BOTH the reply text and the cue
# phrases before matching, so a contraction matches its cue no matter HOW the member
# typed the apostrophe: dropped ("dont"), the standard straight/curly form, MISPLACED
# by a key ("do'nt"/"ca'nt"), or any look-alike a client/IME emits (curly U+2019,
# prime U+2032, fullwidth U+FF07 on a CJK keyboard, acute U+00B4, backtick, the
# LETTER-category modifier apostrophe U+02BC). Without this an apostrophe-variant
# refusal would carry the affirmative "publish it" past a negation cue stored as
# "don't publish" -> a dangerous false approval on the legal publish gate. Stripping
# is used rather than a flexible \W separator because it ALSO handles a misplaced
# apostrophe and an apostrophe that Unicode classes as a LETTER (U+02BC) -- neither
# of which a separator-class match can cover. The set is a curated table of the
# realistic apostrophe variants; the rare obscure tail is backstopped by the operator
# read of the verbatim reply.
_APOSTROPHES = dict.fromkeys((
    0x27,    # ' apostrophe
    0x2018,  # left single quote
    0x2019,  # right single quote (the standard curly apostrophe)
    0x201B,  # single high-reversed-9 quote
    0x2032,  # prime
    0x2035,  # reversed prime
    0x02B9,  # modifier letter prime
    0x02BB,  # modifier letter turned comma
    0x02BC,  # modifier letter apostrophe (Unicode LETTER category)
    0x02BE,  # modifier letter right half ring
    0x02BF,  # modifier letter left half ring
    0x0060,  # ` grave accent
    0x00B4,  # acute accent
    0xFF07,  # fullwidth apostrophe (CJK IME)
    0xFF40,  # fullwidth grave accent
    0xA78B,  # latin capital letter saltillo
    0xA78C,  # latin small letter saltillo
    0x275B,  # heavy single turned comma ornament
    0x275C,  # heavy single comma ornament
), None)


def _normalise(text: str) -> str:
    """Lower-case and strip apostrophe-class chars, so a contraction's spelling and
    apostrophe placement never decide a match."""
    return text.lower().translate(_APOSTROPHES)


@lru_cache(maxsize=None)
def _compile_phrase(phrase: str) -> re.Pattern[str] | None:
    """Compile a phrase to a word-boundary-anchored, punctuation-tolerant regex.

    Cached: the affirmative/negation phrase lists are small and fixed, and every
    reply re-tests each phrase, so compiling once per distinct phrase (instead of
    on every call) removes ~52 regex compilations per message with no behaviour
    change. Returns None for an empty phrase (never matches).

    The phrase is normalised (apostrophes stripped) so a cue like "don't publish"
    matches every apostrophe spelling of the reply once the caller normalises it the
    same way. Word-parts are joined with \\W* (zero-or-more) rather than \\W+ so that
    stripping an apostrophe that a member glued BETWEEN two cue words (e.g.
    "not'approved" -> "notapproved", "do'not" -> "donot") still matches the multi-word
    cue -- otherwise deleting that apostrophe would fuse the words and silently defeat
    the negation. \\W* can never span a WORD char, so it never fuses across a separate
    intervening word, and the \\b anchors keep "approved" from matching "unapproved".
    """
    words = re.findall(r"\w+", _normalise(phrase))
    if not words:
        return None
    return re.compile(r"\b" + r"\W*".join(re.escape(w) for w in words) + r"\b")


def _phrase_present(low_text: str, phrase: str) -> bool:
    """Whole-word match of a (possibly multi-word) phrase, punctuation-tolerant.

    Word-boundary anchored so a phrase is not matched inside a larger word -- e.g.
    the affirmative "approved" must NOT match "unapproved". Words are joined with
    \\W+ so "yes, approve" and "yes approve" both match.
    """
    pattern = _compile_phrase(phrase)
    return pattern is not None and pattern.search(low_text) is not None


# PRIMARY quote marker: the distinctive opening line of OUR approval-request email
# (compose_approval_email emits it verbatim -- single source of truth). It appears
# at the top of the quoted original in EVERY reply, regardless of the member's mail
# client or its UI language, because it is our own content quoted back to us. This
# is what makes the cut client- and language-independent: it fires even when the
# client quotes WITHOUT `>` prefixes and WITHOUT a recognisable attribution -- new
# Outlook / Outlook.com (underscore rule + "From:" header block), localized clients
# ("-----Urspr..." / "Am ... schrieb:"), or marker-less quoting -- the exact leak
# classes a `>`/English-marker allowlist misses.
_APPROVAL_EMAIL_SENTINEL = "Your Asians & Gingers in Tech feature is ready"
# TWO independent template anchors, both emitted verbatim by compose_approval_email
# and both sitting ABOVE the first affirmative word in the template. strip cuts at
# the earliest one found, so a client mangling ONE phrase does not re-open the leak
# -- both must be defeated for the quoted 'approved' to survive.
_TEMPLATE_ANCHORS = (
    _APPROVAL_EMAIL_SENTINEL,
    "This is the EXACT wording we will publish",
)
# Match each anchor WHITESPACE-FLEXIBLY and case-insensitively: join its words with
# \s+ so the cut still fires when the client mangles the inter-word spacing of the
# quoted copy -- a non-breaking space (Outlook injects &nbsp;), a tab, a double
# space, or a hard line-wrap that splits the phrase across lines. A byte-exact
# substring search would miss all of these and re-open the leak. \s also matches
# U+00A0, so nbsp is handled here as well as in _html_to_text. A member would never
# type either exact branded sentence.
_ANCHOR_RES = tuple(
    re.compile(r"\s+".join(re.escape(w) for w in anchor.split()), re.IGNORECASE)
    for anchor in _TEMPLATE_ANCHORS
)
# SECONDARY, client-generic markers (defence in depth; also strip the quoted-block
# header lines the anchors leave above them, e.g. Gmail's "> Hi,"). An
# "On <date> ... wrote:" attribution, an "-----Original Message-----" separator, or
# a long underscore rule reliably precede a quoted original, and a member almost
# never types one. Bounded so a wrapped attribution is still caught without
# swallowing an unrelated later "... wrote:" sentence.
_ATTRIBUTION_RE = re.compile(r"(?ms)^\s*On\b.{0,400}?\bwrote:\s*$")
_ORIGINAL_MSG_RE = re.compile(r"(?mi)^\s*-{2,}\s*original message\s*-{2,}\s*$")
_UNDERSCORE_SEP_RE = re.compile(r"(?m)^\s*_{5,}\s*$")
# NB: deliberately NO bare `>`-line cut. A member may type `>` in their OWN new
# text (quoting an aside), and cutting at the first `>` would drop their later
# words -- including a retraction after an earlier approval -> a dangerous false
# publish. Our own quoted template is caught by the anchors instead, whether or
# not it is `>`-prefixed (the anchor survives inside a "> ..." line).


def strip_quoted_text(text: str) -> str:
    """Return only the member's NEW text, dropping the quoted original beneath it.

    This is the fix for the quoted-text leak: our OWN request template contains the
    sentence 'reply to this email with "approved" to publish it', so if the quoted
    copy of that line reaches the approval detector, almost any reply looks like an
    approval. The detector must read ONLY what the member actually typed.

    Cuts at the earliest of: either template anchor (primary, client-independent,
    whitespace-flexible, case-insensitive), an "On ... wrote:" attribution, an
    "-----Original Message-----" separator, or a long underscore rule (Outlook). The
    FULL body is still recorded verbatim for the operator, so nothing is lost.

    Fails safe: if a member bottom-posts their reply BELOW the quote (rare), the new
    text is stripped too and detection sees nothing -> not approved -> blocked, and
    the operator confirms by hand. Blocking a genuine approval is the safe failure
    direction for a legal publish gate; publishing on a misread is not.
    """
    cut = len(text)
    for rx in _ANCHOR_RES:
        anchor = rx.search(text)
        if anchor:
            cut = min(cut, text.rfind("\n", 0, anchor.start()) + 1)  # START of its line
    for rx in (_ATTRIBUTION_RE, _ORIGINAL_MSG_RE, _UNDERSCORE_SEP_RE):
        match = rx.search(text)
        if match:
            cut = min(cut, match.start())
    return text[:cut].rstrip()


def is_approval_reply(text: str, affirmative: list[str], negation: list[str]) -> bool:
    """True iff the reply carries an affirmative phrase AND no negation phrase.

    Deliberately conservative and fail-safe: negation always wins. A convoluted
    approval that happens to contain a refusal word ("don't hold off, publish it")
    is treated as NOT approved and blocked -- never wrongly published. The operator
    confirms such edge phrasings by hand. This is the safe failure direction for a
    legal publish gate: we would rather block a genuine approval than publish on a
    misread one.
    """
    low = _normalise(text)
    if any(_phrase_present(low, neg) for neg in negation):
        return False
    return any(_phrase_present(low, aff) for aff in affirmative)


def is_decisive_reply(text: str, affirmative: list[str], negation: list[str]) -> bool:
    """True iff the reply carries an approval OR a refusal signal (not just chatter).

    A thank-you or a clarifying question is NOT decisive; it must not override an
    earlier approval or refusal on the same thread.
    """
    low = _normalise(text)
    return (any(_phrase_present(low, aff) for aff in affirmative)
            or any(_phrase_present(low, neg) for neg in negation))


def compose_approval_email(to_addr: str, from_addr: str, feature_title: str,
                           final_wording: str, slug: str,
                           socials: str = "") -> EmailMessage:
    """Build the approval-request email carrying the exact final wording.

    If ``socials`` is given (the member's profile links, one per line), the email
    echoes them back and states that the same approval reply confirms the tagging
    too -- so a single "approved" covers both the wording AND being tagged at the
    exact handles shown, and a wrong handle can be corrected before anything is
    shared. Blank/omitted socials leaves the email exactly as before. The echoed
    block sits AFTER the sentinel, so a quoted copy of it in the member's reply is
    removed by strip_quoted_text along with the rest of the template (its "tag"
    wording can never leak an approval).
    """
    socials = (socials or "").strip()
    socials_plain = (
        "When we share your feature, we'll tag you at:\n"
        f"{socials}\n\n"
        "Your approval above covers this too. If a handle is wrong, just tell us "
        "and we'll fix it before anything is shared.\n\n"
    ) if socials else ""
    socials_html = (
        "<p>When we share your feature, we'll tag you at:</p>"
        f"<pre style=\"white-space:pre-wrap\">{html.escape(socials)}</pre>"
        "<p>Your approval above covers this too. If a handle is wrong, just tell "
        "us and we'll fix it before anything is shared.</p>"
    ) if socials else ""
    msg = EmailMessage()
    msg["To"] = to_addr
    msg["From"] = from_addr
    msg["Subject"] = f"Please approve your AGIT feature: {feature_title}"
    msg["X-AGIT-Slug"] = slug
    msg.set_content(
        "Hi,\n\n"
        # The sentinel opens the body verbatim so strip_quoted_text can find it in
        # the quoted copy of ANY reply, regardless of the member's mail client.
        f"{_APPROVAL_EMAIL_SENTINEL}. This is the EXACT wording "
        "we will publish. Nothing goes live until you reply to approve it.\n\n"
        "Please read it and reply to this email with \"approved\" to publish it, or "
        "tell us what to change and we'll send a new version.\n\n"
        "----- Your feature, exactly as it will publish -----\n\n"
        f"{final_wording}\n\n"
        "----- End of feature -----\n\n"
        + socials_plain
        + "Thanks,\nAsians & Gingers in Tech\nhello@hoiboy.uk\n"
    )
    # HTML alternative: identical wording, but the action word is bold so the
    # member cannot miss what to type. The plain-text part above is unchanged and
    # stays the body the approval detector reads; this alternative is display-only
    # (the member's REPLY is what gets detected, and it is quote-stripped first).
    safe_wording = html.escape(final_wording)
    msg.add_alternative(
        "<html><body style=\"font-family:sans-serif\">"
        "<p>Hi,</p>"
        # Sentinel from the single-source constant so the html part a member may
        # quote back also carries it verbatim (strip_quoted_text can then cut it).
        f"<p>{html.escape(_APPROVAL_EMAIL_SENTINEL)}. This is the EXACT "
        "wording we will publish. Nothing goes live until you reply to approve it.</p>"
        "<p>Please read it and reply to this email with <strong>approved</strong> "
        "to publish it, or tell us what to change and we'll send a new version.</p>"
        "<p>----- Your feature, exactly as it will publish -----</p>"
        f"<pre style=\"white-space:pre-wrap\">{safe_wording}</pre>"
        "<p>----- End of feature -----</p>"
        + socials_html
        + "<p>Thanks,<br>Asians &amp; Gingers in Tech<br>hello@hoiboy.uk</p>"
        "</body></html>",
        subtype="html",
    )
    return msg


def gmail_raw(msg: EmailMessage) -> dict:
    """Encode an EmailMessage as the Gmail API send body ({'raw': base64url})."""
    return {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def wording_sha256(text: str) -> str:
    """Fingerprint of the exact wording sent for approval (binds approval to text)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_request(record_dir: Path, *, to_addr: str, message_id: str,
                   thread_id: str, wording_hash: str | None = None,
                   sent_at: str | None = None) -> Path:
    """Persist the sent approval-request metadata into the record.

    Stores the fingerprint of the exact wording sent, so poll_for_approval can bind
    the recorded approval to that wording and the publish gate can reject an approval
    that was for a different (earlier) edit.
    """
    record_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "to": to_addr,
        "message_id": message_id,
        "thread_id": thread_id,
        "wording_sha256": wording_hash,
        "sent_at": sent_at or _now_iso(),
    }
    path = record_dir / REQUEST_FILE
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def record_approval(record_dir: Path, *, approved: bool, reply_text: str,
                    reply_from: str, message_id: str, thread_id: str,
                    wording_hash: str | None = None,
                    later_replies: list[str] | None = None,
                    replied_at: str | None = None) -> Path:
    """Persist the member's approval decision into the record (approval.json).

    Carries the wording fingerprint forward from the request so the publish gate can
    verify the approval was for the exact wording of the current edit. `later_replies`
    holds any member message sent after the decision, so a follow-up is never lost.
    """
    record_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "approved": bool(approved),
        "reply_from": reply_from,
        "reply_text": reply_text,
        "message_id": message_id,
        "thread_id": thread_id,
        "wording_sha256": wording_hash,
        "later_replies": later_replies or [],
        "replied_at": replied_at or _now_iso(),
    }
    path = record_dir / APPROVAL_FILE
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def _decode_part(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("ascii")).decode("utf-8", "replace")


_HTML_COMMENT_RE = re.compile(r"(?s)<!--.*?-->")
_SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style)\b.*?</\1>")
# Block-, list- and CELL-level tags become newlines so words in separate blocks
# do not fuse: "<td>please</td><td>cancel</td>" must read as "please\ncancel", not
# "pleasecancel" (which would hide the refusal from whole-word matching). A broad
# set of the standard HTML block/table/list elements is listed (not just a few) so
# the fusion class is closed generally, not tag-by-tag. Matches the opening OR
# closing form of each. Remaining INLINE tags (<b>, <span>, <a>...) are then
# removed WITHOUT a space, so whole-word inline formatting like "<b>approved</b>"
# stays a single word rather than fragmenting.
_HTML_BREAK_RE = re.compile(
    r"(?i)<\s*/?\s*(?:br|p|div|tr|td|th|thead|tbody|tfoot|caption|table|li|ul|ol|dl|dt|dd"
    r"|h[1-6]|blockquote|pre|section|article|aside|header|footer|nav|main|hgroup"
    r"|address|figure|figcaption|fieldset|details|summary|hr|form|option)\b[^>]*>")
_HTML_TAG_RE = re.compile(r"(?s)<[^>]+>")


def _html_to_text(html_body: str) -> str:
    """Best-effort plain text from an HTML email part (line structure preserved).

    Used only as a fallback when a reply has NO text/plain part. Drop comments and
    script/style, turn block/cell tags into newlines, remove remaining inline tags,
    unescape entities, and normalise non-breaking spaces to ordinary spaces -- so
    the approval detector and strip_quoted_text read what the member typed and can
    find the quoted template sentinel even when the client used &nbsp; spacing.
    """
    body = _HTML_COMMENT_RE.sub("", html_body)
    body = _SCRIPT_STYLE_RE.sub("", body)
    body = _HTML_BREAK_RE.sub("\n", body)
    body = _HTML_TAG_RE.sub("", body)
    return html.unescape(body).replace("\xa0", " ")


def _extract_by_type(payload: dict, mime: str) -> str:
    """First body of the given MIME type found in the payload tree, decoded."""
    if payload.get("mimeType") == mime:
        data = payload.get("body", {}).get("data")
        if data:
            return _decode_part(data)
    for part in payload.get("parts", []) or []:
        found = _extract_by_type(part, mime)
        if found:
            return found
    return ""


def extract_plain_text(payload: dict) -> str:
    """Pull the member's text out of a Gmail payload, preferring text/plain.

    Falls back to text extracted from a text/html part when there is NO text/plain
    part anywhere in the message. Without the fallback an html-only reply decodes
    to empty, so a later refusal would be non-decisive and silently fail to
    supersede an earlier approval -- a dangerous direction on the publish gate.
    """
    plain = _extract_by_type(payload, "text/plain")
    if plain:
        return plain
    html_body = _extract_by_type(payload, "text/html")
    if html_body:
        return _html_to_text(html_body)
    return ""


# ------------------------------------------------------------------ Gmail I/O
# These take an injected `service` (the google API client) so they are testable
# with a fake. The real service is built by build_gmail_service() at runtime.

def send_approval_request(service, record_dir: Path, *, to_addr: str,
                          from_addr: str, feature_title: str, final_wording: str,
                          slug: str, socials: str = "") -> dict:
    """Send the approval email; record the sent message + thread id."""
    msg = compose_approval_email(to_addr, from_addr, feature_title, final_wording,
                                 slug, socials)
    sent = service.users().messages().send(userId="me", body=gmail_raw(msg)).execute()
    record_request(record_dir, to_addr=to_addr,
                   message_id=sent.get("id", ""), thread_id=sent.get("threadId", ""),
                   wording_hash=wording_sha256(final_wording))
    return sent


def poll_for_approval(service, record_dir: Path, *, thread_id: str,
                      member_email: str, config_path: Path = DEFAULT_CONFIG) -> dict | None:
    """Read ONLY the approval thread; if the member replied, record the decision.

    Records the member's LATEST decision: a member may reply more than once on the
    same thread (hedge or ask a question, then approve once satisfied; or approve,
    then retract). A later DECISIVE reply (one carrying an approval or refusal
    signal) supersedes an earlier one, so the recorded verdict is always the
    member's most recent word -- never a stale first reply. Non-decisive chatter (a
    thank-you, a clarifying question) never overrides an earlier decision. Fail-safe
    by construction: with no decisive reply, the verdict is not-approved.

    Any member message sent AFTER the decisive reply is recorded verbatim in
    `later_replies` -- never silently dropped -- because a non-decisive follow-up
    ("can we swap the photo?") may qualify the decision and the operator must see it
    (the publish gate surfaces these; SKILL.md step 4 tells the operator to read them).

    Returns the written approval payload, or None if the member has not replied
    yet. Reads exactly one thread (the one we created), never the mailbox.
    """
    affirmative, negation = load_approval_phrases(config_path)
    member_addr = (parseaddr(member_email)[1] or member_email).strip().lower()
    thread = service.users().threads().get(userId="me", id=thread_id).execute()
    replies: list[tuple[str, str, str, str]] = []  # (full_body, new_text, sender, msg_id)
    decisive_idx: int | None = None            # index of the latest approve/refuse
    for message in thread.get("messages", []):
        payload = message.get("payload", {})
        headers = {h.get("name", "").lower(): h.get("value", "")
                   for h in payload.get("headers", [])}
        sender = headers.get("from", "")
        # Exact address match (not substring): a colleague at s.wei@corp.com must not
        # be mistaken for the member at wei@corp.com. Only the member's OWN replies
        # count; our own outgoing message is skipped the same way.
        if parseaddr(sender)[1].strip().lower() != member_addr:
            continue
        body = extract_plain_text(payload)
        # Detection reads ONLY the member's new text -- the quoted original (which
        # echoes our own 'reply with "approved"' template line) must never be
        # matched. The FULL body is still recorded (reply_text / later_replies) so
        # the operator sees everything the member wrote.
        new_text = strip_quoted_text(body)
        replies.append((body, new_text, sender, message.get("id", "")))
        if is_decisive_reply(new_text, affirmative, negation):
            decisive_idx = len(replies) - 1  # a later decisive reply supersedes

    if not replies:
        return None  # the member has not replied yet

    chosen_idx = decisive_idx if decisive_idx is not None else len(replies) - 1
    body, new_text, sender, message_id = replies[chosen_idx]
    approved = is_approval_reply(new_text, affirmative, negation)
    # Everything the member said AFTER the decision -- surfaced, never dropped.
    later_replies = [r[0] for r in replies[chosen_idx + 1:]]
    request_path = record_dir / REQUEST_FILE
    wording_hash = None
    if request_path.is_file():
        wording_hash = json.loads(
            request_path.read_text(encoding="utf-8")).get("wording_sha256")
    path = record_approval(record_dir, approved=approved, reply_text=body,
                           reply_from=sender, message_id=message_id,
                           later_replies=later_replies,
                           thread_id=thread_id, wording_hash=wording_hash)
    return json.loads(path.read_text(encoding="utf-8"))


def build_gmail_service(client_secret_path: Path, token_path: Path):
    """Build a real Gmail API service (runtime only; lazily imports google libs).

    Requires `google-api-python-client` + `google-auth-oauthlib` (NOT in
    requirements-dev; the operator installs them when granting credentials). The
    token is cached at token_path (outside the repo) after the first consent.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover - runtime-only path
        raise RuntimeError(
            "Gmail live mode needs google-api-python-client + google-auth-oauthlib. "
            "Install them and grant credentials per docs/gmail-approval-oauth-setup.md."
        ) from exc

    creds = None
    if token_path.is_file():
        creds = Credentials.from_authorized_user_file(str(token_path), list(GMAIL_SCOPES))
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secret_path), list(GMAIL_SCOPES))
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=creds)


def _gmail_error_types() -> tuple[type, ...]:
    """The google Gmail HttpError type if the google libs are installed, else ().

    Lets the CLI treat a live Gmail API error as an exit-2 IO error without making
    the google import a hard dependency of the pure-logic module (the tests run
    without google installed).
    """
    try:  # pragma: no cover - runtime-only path (google libs absent in tests)
        from googleapiclient.errors import HttpError
        return (HttpError,)
    except ImportError:
        return ()


# An IO/usage failure while sending or polling (unreadable wording file, corrupt
# config or request record, a live Gmail API/transport error) is an error (exit 2),
# NEVER "no approval" (exit 1) -- so a genuine outage can never masquerade as the
# member's silence or refusal.
_DISPATCH_IO_ERRORS = (OSError, ValueError, json.JSONDecodeError) + _gmail_error_types()


def _dispatch(service, args) -> int:  # pragma: no cover - runtime CLI print paths
    """Run the requested send/poll command; may raise an IO error (caught by main)."""
    if args.command == "send":
        wording = args.wording_file.read_text(encoding="utf-8")
        socials = args.socials_file.read_text(encoding="utf-8") if args.socials_file else ""
        sent = send_approval_request(service, args.record, to_addr=args.to,
                                     from_addr=args.from_addr, feature_title=args.title,
                                     final_wording=wording, slug=args.slug, socials=socials)
        print(f"sent: message {sent.get('id')} thread {sent.get('threadId')}")
        return 0

    result = poll_for_approval(service, args.record, thread_id=args.thread_id,
                               member_email=args.member_email)
    if result is None:
        print("no reply from the member yet")
        return 1
    print(f"approved={result['approved']} from {result['reply_from']}")
    return 0 if result["approved"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AGIT email-approval automation.")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--record", required=True, type=Path, help="Record dir.")
    common.add_argument("--client-secret", type=Path,
                        default=Path.home() / ".agit-secrets/gmail_client_secret.json")
    common.add_argument("--token", type=Path,
                        default=Path.home() / ".agit-secrets/gmail_token.json")

    p_send = sub.add_parser("send", parents=[common], help="Send the approval request.")
    p_send.add_argument("--to", required=True)
    p_send.add_argument("--from-addr", default="hoiboyuk@gmail.com")
    p_send.add_argument("--title", required=True)
    p_send.add_argument("--wording-file", required=True, type=Path)
    p_send.add_argument("--slug", required=True)
    p_send.add_argument("--socials-file", type=Path, default=None,
                        help="Optional file of the member's profile links (one per "
                             "line) to echo back and confirm tagging in the same reply.")

    p_poll = sub.add_parser("poll", parents=[common], help="Check for the reply.")
    p_poll.add_argument("--thread-id", required=True)
    p_poll.add_argument("--member-email", required=True)

    args = parser.parse_args(argv)

    try:
        service = build_gmail_service(args.client_secret, args.token)
    except RuntimeError as exc:  # pragma: no cover - runtime-only path
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        return _dispatch(service, args)
    except _DISPATCH_IO_ERRORS as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
