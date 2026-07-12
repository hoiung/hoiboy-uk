#!/usr/bin/env python3
"""Unit tests for agit_approval.py (hoiboy-uk #48 Phase 4).

Pure logic (config load, strict approval detection, email compose, record write,
body extract) plus the Gmail send/poll paths driven by a FAKE injected service,
so nothing here needs the google libraries or live credentials.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import agit_approval as aa  # noqa: E402

AFFIRM, NEGATE = aa.load_approval_phrases()


# --------------------------------------------------------- fake Gmail service

class _Exec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _Messages:
    def __init__(self, send_result):
        self._send_result = send_result
        self.captured = None

    def send(self, userId=None, body=None):
        self.captured = {"userId": userId, "body": body}
        return _Exec(self._send_result)


class _Threads:
    def __init__(self, thread):
        self._thread = thread
        self.captured = None

    def get(self, userId=None, id=None):
        self.captured = {"userId": userId, "id": id}
        return _Exec(self._thread)


class _Users:
    def __init__(self, send_result, thread):
        self._messages = _Messages(send_result)
        self._threads = _Threads(thread)

    def messages(self):
        return self._messages

    def threads(self):
        return self._threads


class FakeService:
    def __init__(self, send_result=None, thread=None):
        self._users = _Users(send_result, thread)

    def users(self):
        return self._users


def _gmail_message(msg_id: str, from_addr: str, body_text: str) -> dict:
    data = base64.urlsafe_b64encode(body_text.encode("utf-8")).decode("ascii")
    return {
        "id": msg_id,
        "payload": {
            "mimeType": "text/plain",
            "headers": [{"name": "From", "value": from_addr}],
            "body": {"data": data},
        },
    }


# ------------------------------------------------------------- approval logic

def test_config_phrases_loaded():
    assert "approved" in AFFIRM
    assert "not approved" in NEGATE


def test_plain_approval_detected():
    assert aa.is_approval_reply("Approved, thank you!", AFFIRM, NEGATE) is True
    assert aa.is_approval_reply("yes, publish it please", AFFIRM, NEGATE) is True


def test_negation_blocks_even_with_affirmative_token():
    # "not approved" contains "approved" but must NOT count as approval.
    assert aa.is_approval_reply("This is not approved yet", AFFIRM, NEGATE) is False
    assert aa.is_approval_reply("Happy to publish but one change first", AFFIRM, NEGATE) is False


def test_ambiguous_is_not_approval():
    assert aa.is_approval_reply("thanks, got it", AFFIRM, NEGATE) is False
    assert aa.is_approval_reply("", AFFIRM, NEGATE) is False


def test_compose_email_carries_exact_wording():
    msg = aa.compose_approval_email("m@example.com", "hoiboyuk@gmail.com",
                                    "Jane the Builder", "The EXACT story body.", "jane")
    assert msg["To"] == "m@example.com"
    assert "Jane the Builder" in msg["Subject"]
    assert "The EXACT story body." in msg.get_content()
    assert msg["X-AGIT-Slug"] == "jane"


def test_gmail_raw_roundtrip():
    msg = aa.compose_approval_email("m@example.com", "f@example.com", "T", "BODY-XYZ", "s")
    raw = aa.gmail_raw(msg)
    decoded = base64.urlsafe_b64decode(raw["raw"].encode("ascii")).decode("utf-8")
    assert "BODY-XYZ" in decoded


def test_extract_plain_text_nested_multipart():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(
                b"<p>ignored</p>").decode()}},
            {"mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(
                b"the real reply").decode()}},
        ],
    }
    assert aa.extract_plain_text(payload) == "the real reply"


# ------------------------------------------------------------- record writing

def test_record_approval_writes_json(tmp_path):
    path = aa.record_approval(tmp_path, approved=True, reply_text="approved",
                              reply_from="m@example.com", message_id="m1",
                              thread_id="t1", replied_at="2026-07-12T00:00:00+00:00")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["approved"] is True
    assert data["thread_id"] == "t1"


# ------------------------------------------------------------- Gmail I/O paths

def test_send_records_request(tmp_path):
    svc = FakeService(send_result={"id": "msg1", "threadId": "thr1"})
    aa.send_approval_request(svc, tmp_path, to_addr="m@example.com",
                             from_addr="hoiboyuk@gmail.com", feature_title="T",
                             final_wording="BODY", slug="s")
    req = json.loads((tmp_path / aa.REQUEST_FILE).read_text(encoding="utf-8"))
    assert req["message_id"] == "msg1"
    assert req["thread_id"] == "thr1"
    # the send body was a base64url raw message carrying the wording
    body = svc.users().messages().captured["body"]["raw"]
    assert "BODY" in base64.urlsafe_b64decode(body.encode()).decode("utf-8")


def test_poll_records_approval_on_member_yes(tmp_path):
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "Jane <m@example.com>", "Approved, go for it!"),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is True
    assert (tmp_path / aa.APPROVAL_FILE).is_file()


def test_poll_records_not_approved_on_member_changes(tmp_path):
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "m@example.com", "Looks good but one change please"),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is False


def test_poll_returns_none_when_no_member_reply(tmp_path):
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
    ]}
    svc = FakeService(thread=thread)
    assert aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                member_email="m@example.com") is None


# ------------------------------------- multi-reply threads (latest decision wins)
# A member may reply more than once on the same approval thread. poll_for_approval
# must record the LATEST decision, never a stale first reply.

def test_poll_hedge_then_approval_records_approval(tmp_path):
    # The reported bug: a hedge first, the real approval second. Must be approved.
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "m@example.com", "Hold off for a sec, let me reread this."),
        _gmail_message("in2", "m@example.com", "OK reread it. Approved, please publish it."),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is True
    assert "publish it" in result["reply_text"].lower()  # recorded the real approval


def test_poll_approval_then_thankyou_stays_approved(tmp_path):
    # Non-decisive chatter after an approval must NOT undo the approval.
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "m@example.com", "Approved, please publish it."),
        _gmail_message("in2", "m@example.com", "Thanks so much, really appreciate it!"),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is True


def test_poll_approval_then_retraction_blocks(tmp_path):
    # A later retraction supersedes an earlier approval -- fail-safe.
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "m@example.com", "Approved, publish it."),
        _gmail_message("in2", "m@example.com", "Actually hold off, I want one change."),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is False


def test_poll_non_decisive_reply_records_not_approved(tmp_path):
    # A reply that neither approves nor refuses is recorded as not-approved.
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "m@example.com", "Give me a day to think about it."),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is False


def test_is_decisive_reply_distinguishes_chatter():
    assert aa.is_decisive_reply("Approved, publish it", AFFIRM, NEGATE) is True
    assert aa.is_decisive_reply("Please hold off", AFFIRM, NEGATE) is True
    assert aa.is_decisive_reply("Thanks, got it!", AFFIRM, NEGATE) is False


def test_poll_ignores_superstring_address_bystander(tmp_path):
    # A colleague at a superstring address (s.wei@corp.com) must NOT be mistaken for
    # the member (wei@corp.com) -- exact address match, not substring. Here the only
    # reply is from a bystander whose address contains the member's -> not the member.
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "Mallory <mjo@example.com>", "Approved, publish it now!"),
    ]}
    svc = FakeService(thread=thread)
    # member is jo@example.com; mjo@example.com is a different person.
    assert aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                member_email="jo@example.com") is None


def test_poll_matches_member_with_display_name(tmp_path):
    # The member's own reply is still detected when their From carries a display name.
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "Jo Bloggs <jo@example.com>", "Approved, publish it."),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="jo@example.com")
    assert result is not None and result["approved"] is True


if __name__ == "__main__":
    import subprocess
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
