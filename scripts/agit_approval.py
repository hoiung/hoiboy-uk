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


@lru_cache(maxsize=None)
def _compile_phrase(phrase: str) -> re.Pattern[str] | None:
    """Compile a phrase to a word-boundary-anchored, punctuation-tolerant regex.

    Cached: the affirmative/negation phrase lists are small and fixed, and every
    reply re-tests each phrase, so compiling once per distinct phrase (instead of
    on every call) removes ~52 regex compilations per message with no behaviour
    change. Returns None for an empty phrase (never matches).
    """
    words = re.findall(r"\w+", phrase.lower())
    if not words:
        return None
    return re.compile(r"\b" + r"\W+".join(re.escape(w) for w in words) + r"\b")


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
# SECONDARY, client-generic markers (defence in depth; also strip the quoted-block
# header lines the sentinel leaves above it, e.g. Gmail's "> Hi,"). An
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
# publish. Our own quoted template is caught by the sentinel instead, whether or
# not it is `>`-prefixed (the sentinel substring survives inside a "> ..." line).


def strip_quoted_text(text: str) -> str:
    """Return only the member's NEW text, dropping the quoted original beneath it.

    This is the fix for the quoted-text leak: our OWN request template contains the
    sentence 'reply to this email with "approved" to publish it', so if the quoted
    copy of that line reaches the approval detector, almost any reply looks like an
    approval. The detector must read ONLY what the member actually typed.

    Cuts at the earliest of: our template sentinel (primary, client-independent),
    an "On ... wrote:" attribution, an "-----Original Message-----" separator, or a
    long underscore rule (Outlook). The FULL body is still recorded verbatim for the
    operator, so nothing the member said is lost.

    Fails safe: if a member bottom-posts their reply BELOW the quote (rare), the new
    text is stripped too and detection sees nothing -> not approved -> blocked, and
    the operator confirms by hand. Blocking a genuine approval is the safe failure
    direction for a legal publish gate; publishing on a misread is not.
    """
    cut = len(text)
    idx = text.find(_APPROVAL_EMAIL_SENTINEL)
    if idx != -1:
        cut = text.rfind("\n", 0, idx) + 1  # cut from the START of the sentinel's line
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
    low = text.lower()
    if any(_phrase_present(low, neg) for neg in negation):
        return False
    return any(_phrase_present(low, aff) for aff in affirmative)


def is_decisive_reply(text: str, affirmative: list[str], negation: list[str]) -> bool:
    """True iff the reply carries an approval OR a refusal signal (not just chatter).

    A thank-you or a clarifying question is NOT decisive; it must not override an
    earlier approval or refusal on the same thread.
    """
    low = text.lower()
    return (any(_phrase_present(low, aff) for aff in affirmative)
            or any(_phrase_present(low, neg) for neg in negation))


def compose_approval_email(to_addr: str, from_addr: str, feature_title: str,
                           final_wording: str, slug: str) -> EmailMessage:
    """Build the approval-request email carrying the exact final wording."""
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
        "Thanks,\nAsians & Gingers in Tech\nhello@hoiboy.uk\n"
    )
    # HTML alternative: identical wording, but the action word is bold so the
    # member cannot miss what to type. The plain-text part above is unchanged and
    # stays the body the approval detector reads; this alternative is display-only
    # (the member's REPLY is what gets detected, and it is quote-stripped first).
    safe_wording = html.escape(final_wording)
    msg.add_alternative(
        "<html><body style=\"font-family:sans-serif\">"
        "<p>Hi,</p>"
        "<p>Your Asians &amp; Gingers in Tech feature is ready. This is the EXACT "
        "wording we will publish. Nothing goes live until you reply to approve it.</p>"
        "<p>Please read it and reply to this email with <strong>approved</strong> "
        "to publish it, or tell us what to change and we'll send a new version.</p>"
        "<p>----- Your feature, exactly as it will publish -----</p>"
        f"<pre style=\"white-space:pre-wrap\">{safe_wording}</pre>"
        "<p>----- End of feature -----</p>"
        "<p>Thanks,<br>Asians &amp; Gingers in Tech<br>hello@hoiboy.uk</p>"
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


_SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style)\b.*?</\1>")
# Tags that end a visible line -- converted to newlines so the quoted original
# stays on its own lines and strip_quoted_text can find the template sentinel.
_HTML_BREAK_RE = re.compile(r"(?i)<(?:br\s*/?|/p|/div|/tr|/li|/h[1-6]|/blockquote)\s*>")
_HTML_TAG_RE = re.compile(r"(?s)<[^>]+>")


def _html_to_text(html_body: str) -> str:
    """Best-effort plain text from an HTML email part (line structure preserved).

    Used only as a fallback when a reply has NO text/plain part. Kept deliberately
    simple: drop script/style, turn block-closing tags into newlines, strip the
    rest, and unescape entities -- enough for the approval detector and
    strip_quoted_text to read what the member typed and to find the quoted
    template sentinel.
    """
    body = _SCRIPT_STYLE_RE.sub("", html_body)
    body = _HTML_BREAK_RE.sub("\n", body)
    body = _HTML_TAG_RE.sub("", body)
    return html.unescape(body)


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
                          slug: str) -> dict:
    """Send the approval email; record the sent message + thread id."""
    msg = compose_approval_email(to_addr, from_addr, feature_title, final_wording, slug)
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
        sent = send_approval_request(service, args.record, to_addr=args.to,
                                     from_addr=args.from_addr, feature_title=args.title,
                                     final_wording=wording, slug=args.slug)
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
