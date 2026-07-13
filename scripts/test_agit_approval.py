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


def test_unapproved_is_not_read_as_approval():
    # "unapproved" contains the substring "approved" but must NOT count as approval
    # (word-boundary matching). It is an explicit refusal (decisive).
    assert aa.is_approval_reply("Please leave this unapproved for now.", AFFIRM, NEGATE) is False
    assert aa.is_decisive_reply("Please leave this unapproved.", AFFIRM, NEGATE) is True
    # A real approval is unaffected.
    assert aa.is_approval_reply("Approved, please publish it.", AFFIRM, NEGATE) is True


def test_plain_english_refusals_are_decisive():
    # Common refusal words a member may use are decisive refusals, so a later refusal
    # supersedes an earlier approval (fail-safe).
    for refusal in ("I disapprove of the current wording.",
                    "I decline this version.",
                    "Please reject this draft.",
                    "I want to retract my approval.",
                    "Please do not go ahead with this."):
        assert aa.is_approval_reply(refusal, AFFIRM, NEGATE) is False, refusal
        assert aa.is_decisive_reply(refusal, AFFIRM, NEGATE) is True, refusal


def test_negated_negation_fails_safe_not_approved():
    # "don't hold off, publish it" is a genuine approval but contains the negation
    # "hold off"; the gate deliberately fails SAFE (blocks), never wrongly publishes.
    assert aa.is_approval_reply(
        "Please don't hold off, go ahead and publish it now!", AFFIRM, NEGATE) is False


def test_refusal_with_filler_is_not_approval():
    # A refusal that puts filler between the negation and the verb must NOT read as
    # approval even though it contains the affirmative substring "approve this" /
    # "publish it" (the dangerous direction: a genuine refusal wrongly cleared).
    for refusal in ("I don't think you should approve this yet, let's talk first.",
                    "I don't feel ready for you to publish it, sorry.",
                    "I'm not sure I want you to publish it as-is, can we talk first?"):
        assert aa.is_approval_reply(refusal, AFFIRM, NEGATE) is False, refusal
    # A clean approval is unaffected.
    assert aa.is_approval_reply("Approved, please publish it.", AFFIRM, NEGATE) is True
    assert aa.is_approval_reply("Happy to publish.", AFFIRM, NEGATE) is True


def test_compose_email_carries_exact_wording():
    msg = aa.compose_approval_email("m@example.com", "hoiboyuk@gmail.com",
                                    "Jane the Builder", "The EXACT story body.", "jane")
    assert msg["To"] == "m@example.com"
    assert "Jane the Builder" in msg["Subject"]
    # The email is multipart/alternative (plain + html); the wording is in the
    # plain part, which stays the body the approval detector reads.
    plain = msg.get_body(preferencelist=("plain",)).get_content()
    assert "The EXACT story body." in plain
    assert msg["X-AGIT-Slug"] == "jane"


def test_compose_email_bolds_approved_in_html_part():
    # Operator ask: bold the action word "approved" so the member cannot miss what
    # to type. The bold lives in the added HTML alternative; the plain part is
    # unchanged. Display-only -- detection reads the member's quote-stripped reply,
    # never our sent email, so bolding cannot affect the verdict.
    msg = aa.compose_approval_email("m@example.com", "hoiboyuk@gmail.com",
                                    "Jane", "STORY-BODY.", "jane")
    html_part = msg.get_body(preferencelist=("html",)).get_content()
    assert "<strong>approved</strong>" in html_part
    assert "STORY-BODY." in html_part
    plain = msg.get_body(preferencelist=("plain",)).get_content()
    assert "STORY-BODY." in plain


def test_compose_email_html_escapes_wording():
    # The wording is injected into the HTML alternative; angle brackets and
    # ampersands must be escaped so wording can never break (or inject) markup.
    msg = aa.compose_approval_email("m@example.com", "hoiboyuk@gmail.com",
                                    "Jane", "5 < 10 & <b>hi</b>", "jane")
    html_part = msg.get_body(preferencelist=("html",)).get_content()
    assert "&lt;b&gt;hi&lt;/b&gt;" in html_part
    assert "<b>hi</b>" not in html_part
    # The plain part keeps the literal characters.
    plain = msg.get_body(preferencelist=("plain",)).get_content()
    assert "5 < 10 & <b>hi</b>" in plain


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


def test_poll_approval_then_plain_english_refusal_blocks(tmp_path):
    # Member approves, then later disapproves in plain English (same wording, so the
    # sha binding does not apply) -> the later refusal must supersede. Fail-safe.
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "m@example.com", "Approved, publish it."),
        _gmail_message("in2", "m@example.com",
                       "Actually, on reflection, I disapprove. Please do not go ahead."),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is False


def test_poll_records_later_replies_after_decision(tmp_path):
    # A non-decisive follow-up after an approval must be recorded (never dropped) so
    # the operator sees it -- it may qualify or withdraw the approval.
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "m@example.com", "Approved, publish it."),
        _gmail_message("in2", "m@example.com", "Oh wait, can we swap the photo?"),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is True
    assert any("swap the photo" in r for r in result["later_replies"])


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


def test_conditional_approval_is_not_unconditional_approval():
    # An affirmative reply that attaches a CONDITION ("I approve, as long as you...")
    # is NOT unconditional approval of the exact wording -- it must fail safe (block).
    # The operator applies the change, re-sends, and gets a clean approval. Without
    # the conditional cues this reply would wrongly clear as full approval (the
    # dangerous direction a plain affirmative-word match misses).
    for conditional in (
        "I approve, as long as you remove my last name from the story.",
        "Approved, provided that you fix the date.",
        "Yes publish it, but only if you take out the company name.",
        "Happy to publish once you swap the photo.",
        "Approve this, assuming you cut the last paragraph.",
        "You can publish unless my manager objects first.",
    ):
        assert aa.is_approval_reply(conditional, AFFIRM, NEGATE) is False, conditional
        assert aa.is_decisive_reply(conditional, AFFIRM, NEGATE) is True, conditional
    # A clean, unconditional approval is unaffected.
    assert aa.is_approval_reply("Approved, please publish it.", AFFIRM, NEGATE) is True


# ---------------------------------------- quoted-reply stripping (#48 leak fix)
# An email reply carries the quoted original below the new text. Our OWN request
# template contains 'reply to this email with "approved" to publish it', so if the
# detector reads the quoted copy, almost any reply looks like an approval. This is
# the confirmed CRITICAL leak: real-template replies of "please cancel" / "let me
# think" / "declined" would otherwise wrongly PUBLISH. strip_quoted_text removes
# the quote before detection; the FULL body is still recorded for the operator.

# The exact leaking line our template quotes back to us, plus the quoted feature.
_TEMPLATE_QUOTE = (
    "> Please read it and reply to this email with \"approved\" to publish it, or\n"
    "> tell us what to change and we'll send a new version.\n"
    "> ----- Your feature, exactly as it will publish -----\n"
    "> My story about starting out in tech.\n"
)


def _reply_over_quote(new_text: str) -> str:
    """A realistic Gmail-style reply: the member's new text, a "wrote:" attribution,
    then the quoted original (which contains our 'approved' template line)."""
    return (f"{new_text}\n\n"
            "On Mon, 13 Jul 2026 at 15:04, Asians & Gingers in Tech "
            "<hello@hoiboy.uk> wrote:\n"
            f"{_TEMPLATE_QUOTE}")


def test_strip_quoted_text_drops_gmail_attribution_and_quote():
    stripped = aa.strip_quoted_text(_reply_over_quote("Sounds good, thanks."))
    assert stripped == "Sounds good, thanks."
    assert "approved" not in stripped.lower()


def test_strip_quoted_text_drops_bare_quote_lines():
    text = "no thanks\n> reply with \"approved\" to publish it"
    assert aa.strip_quoted_text(text) == "no thanks"


def test_strip_quoted_text_drops_outlook_original_message():
    text = ("Please cancel this.\n\n"
            "-----Original Message-----\n"
            "reply to this email with \"approved\" to publish it")
    assert aa.strip_quoted_text(text) == "Please cancel this."


def test_strip_quoted_text_keeps_plain_reply_unchanged():
    assert aa.strip_quoted_text("Approved, publish it.") == "Approved, publish it."
    assert aa.strip_quoted_text("Please cancel, I changed my mind.") == \
        "Please cancel, I changed my mind."


def test_quoted_template_does_not_leak_neutral_reply_as_approval():
    # The headline leak: a NEUTRAL/REFUSAL reply that quotes our 'approved' template
    # must NOT read as an approval once the quote is stripped.
    for neutral in ("please cancel", "cancel it", "declined", "I have declined this",
                    "let me think about it", "nah, not for me", "give me a day",
                    "can you change the second line first?"):
        stripped = aa.strip_quoted_text(_reply_over_quote(neutral))
        assert aa.is_approval_reply(stripped, AFFIRM, NEGATE) is False, neutral


def test_quoted_original_does_not_hide_genuine_approval():
    # A genuine approval that ALSO quotes our template still reads as approval.
    stripped = aa.strip_quoted_text(_reply_over_quote("Approved, please publish it."))
    assert aa.is_approval_reply(stripped, AFFIRM, NEGATE) is True


def test_cancel_declined_withdraw_are_decisive_refusals():
    # #48 secondary gap: cancel / cancelled / canceled / declined / withdraw(n) were
    # not recognised as decisive refusals, so a "please cancel" retraction failed to
    # supersede an earlier approval.
    for refusal in ("Please cancel this.", "I've cancelled it.", "Consider it canceled.",
                    "Declined.", "I have declined.", "I withdraw my approval.",
                    "Approval withdrawn."):
        assert aa.is_approval_reply(refusal, AFFIRM, NEGATE) is False, refusal
        assert aa.is_decisive_reply(refusal, AFFIRM, NEGATE) is True, refusal


# ----------------------------------- poll end-to-end over a quoted-template reply

def test_poll_neutral_reply_over_quoted_template_blocks(tmp_path):
    # END-TO-END of the leak: the member's reply body carries neutral text PLUS the
    # quoted original (our 'approved' template line). poll must BLOCK, and still
    # record the FULL body (quote included) so the operator sees everything.
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "m@example.com",
                       _reply_over_quote("Thanks, let me think about it.")),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is False
    assert "let me think about it" in result["reply_text"].lower()
    assert "approved" in result["reply_text"].lower()  # full quote preserved for operator


def test_poll_cancel_reply_over_quoted_template_blocks(tmp_path):
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "m@example.com",
                       _reply_over_quote("Please cancel, I changed my mind.")),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is False


def test_poll_genuine_approval_over_quoted_template_publishes(tmp_path):
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "m@example.com",
                       _reply_over_quote("Approved, please publish it.")),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is True


def test_poll_approval_then_cancel_over_quote_blocks(tmp_path):
    # Member approves, then later replies "cancel" over the quoted template. The
    # later cancel is now decisive and supersedes the approval (fail-safe).
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "m@example.com", _reply_over_quote("Approved, publish it.")),
        _gmail_message("in2", "m@example.com", _reply_over_quote("Actually please cancel.")),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is False


def test_main_dispatch_io_error_exits_2(tmp_path, monkeypatch):
    # A send/poll failure (here a Gmail transport error surfacing as OSError) must
    # exit 2 (usage/IO error), NEVER exit 1 (which the CLI uses for "no approval
    # yet") -- so a real outage can never masquerade as the member's silence.
    class _RaisingService:
        def users(self):
            class _Users:
                def threads(self):
                    class _Threads:
                        def get(self, userId=None, id=None):
                            class _E:
                                def execute(self):
                                    raise OSError("simulated Gmail transport failure")
                            return _E()
                    return _Threads()
            return _Users()

    monkeypatch.setattr(aa, "build_gmail_service", lambda *a, **k: _RaisingService())
    rc = aa.main(["poll", "--record", str(tmp_path), "--thread-id", "t1",
                  "--member-email", "m@example.com"])
    assert rc == 2


if __name__ == "__main__":
    import subprocess
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
