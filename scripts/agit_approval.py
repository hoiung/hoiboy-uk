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
import json
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr
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


def is_approval_reply(text: str, affirmative: list[str], negation: list[str]) -> bool:
    """True iff the reply carries an affirmative phrase AND no negation phrase."""
    low = text.lower()
    if any(neg in low for neg in negation):
        return False
    return any(aff in low for aff in affirmative)


def is_decisive_reply(text: str, affirmative: list[str], negation: list[str]) -> bool:
    """True iff the reply carries an approval OR a refusal signal (not just chatter).

    A thank-you or a clarifying question is NOT decisive; it must not override an
    earlier approval or refusal on the same thread.
    """
    low = text.lower()
    return any(aff in low for aff in affirmative) or any(neg in low for neg in negation)


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
        "Your Asians & Gingers in Tech feature is ready. This is the EXACT wording "
        "we will publish. Nothing goes live until you reply to approve it.\n\n"
        "Please read it and reply to this email with \"approved\" to publish it, or "
        "tell us what to change and we'll send a new version.\n\n"
        "----- Your feature, exactly as it will publish -----\n\n"
        f"{final_wording}\n\n"
        "----- End of feature -----\n\n"
        "Thanks,\nAsians & Gingers in Tech\nhello@hoiboy.uk\n"
    )
    return msg


def gmail_raw(msg: EmailMessage) -> dict:
    """Encode an EmailMessage as the Gmail API send body ({'raw': base64url})."""
    return {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_request(record_dir: Path, *, to_addr: str, message_id: str,
                   thread_id: str, sent_at: str | None = None) -> Path:
    """Persist the sent approval-request metadata into the record."""
    record_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "to": to_addr,
        "message_id": message_id,
        "thread_id": thread_id,
        "sent_at": sent_at or _now_iso(),
    }
    path = record_dir / REQUEST_FILE
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def record_approval(record_dir: Path, *, approved: bool, reply_text: str,
                    reply_from: str, message_id: str, thread_id: str,
                    replied_at: str | None = None) -> Path:
    """Persist the member's approval decision into the record (approval.json)."""
    record_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "approved": bool(approved),
        "reply_from": reply_from,
        "reply_text": reply_text,
        "message_id": message_id,
        "thread_id": thread_id,
        "replied_at": replied_at or _now_iso(),
    }
    path = record_dir / APPROVAL_FILE
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def _decode_part(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("ascii")).decode("utf-8", "replace")


def extract_plain_text(payload: dict) -> str:
    """Pull the text/plain body out of a Gmail message payload (recursively)."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data")
        if data:
            return _decode_part(data)
    for part in payload.get("parts", []) or []:
        text = extract_plain_text(part)
        if text:
            return text
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
                   message_id=sent.get("id", ""), thread_id=sent.get("threadId", ""))
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

    Returns the written approval payload, or None if the member has not replied
    yet. Reads exactly one thread (the one we created), never the mailbox.
    """
    affirmative, negation = load_approval_phrases(config_path)
    member_addr = (parseaddr(member_email)[1] or member_email).strip().lower()
    thread = service.users().threads().get(userId="me", id=thread_id).execute()
    decisive: tuple[str, str, str] | None = None  # latest reply that approves/refuses
    latest: tuple[str, str, str] | None = None     # latest member reply of any kind
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
        latest = (body, sender, message.get("id", ""))
        if is_decisive_reply(body, affirmative, negation):
            decisive = latest  # a later decisive reply supersedes an earlier one

    chosen = decisive or latest  # prefer the last decision; else the last reply
    if chosen is None:
        return None  # the member has not replied yet

    body, sender, message_id = chosen
    approved = is_approval_reply(body, affirmative, negation)
    path = record_approval(record_dir, approved=approved, reply_text=body,
                           reply_from=sender, message_id=message_id,
                           thread_id=thread_id)
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


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - runtime CLI
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
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

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


if __name__ == "__main__":
    sys.exit(main())
