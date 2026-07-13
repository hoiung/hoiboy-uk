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


def test_deferral_temporal_reply_is_not_approval():
    # Ralph round-4 finding: a reply that carries an affirmative phrase but DEFERS
    # (temporal / hypothetical) is not a present approval and must block -- same class
    # as the conditional cues above. Cues are kept NARROW (unambiguous deferrals only)
    # so they never over-block a genuine approval; the ambiguous tail (e.g. "once I've
    # checked with my manager, you can publish") is left to the mandatory operator read.
    for deferral in (
        "Let me think before I approve it.",
        "I would approve it but I need a day.",
        "Before you publish it, can we chat?",
        "I'll let you know when to publish it.",
        "Give me the weekend to sleep on it, then publish it.",
    ):
        assert aa.is_approval_reply(deferral, AFFIRM, NEGATE) is False, deferral
        assert aa.is_decisive_reply(deferral, AFFIRM, NEGATE) is True, deferral
    # Clean, present approvals must still clear -- the cues must NOT over-block, even
    # when the approval mentions narrative/courtesy context (Ralph round-5 flagged the
    # first, over-broad cue set wrongly blocking these).
    for clean in ("Approved, please publish it.", "Yes, publish it.",
                  "Happy to publish.", "Approved, go for it!",
                  "I checked with my manager and we're both happy, approved, publish it.",
                  "Just to let you know, this looks great, approved!",
                  "Before you ask, yes I approve, publish it.",
                  "When I saw the final draft I loved it, approved, publish it.",
                  "Once I read it through I knew it was perfect, approved, publish it.",
                  "Once I've read this through twice I'm confident, approved, publish it.",
                  "This is great, approved, publish it. Can we chat about the next one?",
                  "Approved, publish it! I'll let you know when the next story is ready."):
        assert aa.is_approval_reply(clean, AFFIRM, NEGATE) is True, clean


# ---------------------------------------- quoted-reply stripping (#48 leak fix)
# An email reply carries the quoted original below the new text. Our OWN request
# template contains 'reply to this email with "approved" to publish it', so if the
# detector reads the quoted copy, almost any reply looks like an approval. This is
# the confirmed CRITICAL leak: real-template replies of "please cancel" / "let me
# think" / "declined" would otherwise wrongly PUBLISH. strip_quoted_text removes
# the quote before detection; the FULL body is still recorded for the operator.
#
# The quote is stripped by finding our template SENTINEL, so it works for EVERY
# mail client / UI language -- not just Gmail's `>`/"wrote:" convention. These
# fixtures reproduce the real client quoting styles that a `>`-only allowlist
# missed (Ralph #48 findings 1-2): new Outlook (underscore + From: header block,
# no `>`), a localized client (non-English separator, no `>`), and marker-less
# quoting. All quote the ACTUAL composed email, so the sentinel is present exactly
# as it ships.

# The real request email's plain body -- this is what a member's reply quotes back.
_SENT_PLAIN = aa.compose_approval_email(
    "m@example.com", "hoiboyuk@gmail.com", "Jane the Builder",
    "My story about starting out in tech.", "jane"
).get_body(preferencelist=("plain",)).get_content()


def _gmail_quote(new_text: str) -> str:
    """Gmail-style: new text, an "On ... wrote:" attribution, then `>`-prefixed body."""
    quoted = "".join("> " + ln + "\n" for ln in _SENT_PLAIN.splitlines())
    return (f"{new_text}\n\n"
            "On Mon, 13 Jul 2026 at 15:04, Asians & Gingers in Tech "
            "<hello@hoiboy.uk> wrote:\n" + quoted)


def _outlook_quote(new_text: str) -> str:
    """New Outlook / OWA: underscore rule + From/Sent/To/Subject block, no `>`/wrote:."""
    return (f"{new_text}\n\n"
            "________________________________\n"
            "From: Asians & Gingers in Tech <hello@hoiboy.uk>\n"
            "Sent: Monday, July 13, 2026 3:04 PM\n"
            "To: member@corp.com\n"
            "Subject: Please approve your AGIT feature: Jane\n\n"
            + _SENT_PLAIN)


def _localized_quote(new_text: str) -> str:
    """Localized client: a non-English separator our English markers do NOT match,
    no `>` -- so ONLY the template sentinel can catch it."""
    return (f"{new_text}\n\n"
            "-----Ursprungliche Nachricht-----\n"  # deliberately not "Original Message"
            + _SENT_PLAIN)


def _markerless_quote(new_text: str) -> str:
    """Minimal client: the quoted body simply appended, with no markers at all."""
    return f"{new_text}\n\n" + _SENT_PLAIN


_ALL_QUOTE_STYLES = (_gmail_quote, _outlook_quote, _localized_quote, _markerless_quote)


def test_compose_email_emits_the_strip_sentinel():
    # strip_quoted_text keys on this exact sentinel; compose MUST emit it verbatim
    # (single source of truth), else the client-independent cut silently stops working.
    assert aa._APPROVAL_EMAIL_SENTINEL in _SENT_PLAIN


def test_no_client_quote_style_leaks_a_neutral_reply(tmp_path):
    # The headline leak, across EVERY client quoting style: a neutral/refusal reply
    # that quotes our 'approved' template must NOT read as an approval, and the
    # quoted 'approved' must be gone from the detection input.
    for style in _ALL_QUOTE_STYLES:
        for neutral in ("Thanks, let me think about it.", "please cancel", "declined",
                        "Can you change the second line first?", "nah, not for me"):
            stripped = aa.strip_quoted_text(style(neutral))
            ctx = (style.__name__, neutral)
            assert aa.is_approval_reply(stripped, AFFIRM, NEGATE) is False, ctx
            assert "approved" not in stripped.lower(), ctx  # quoted template gone


def test_every_client_quote_style_keeps_a_genuine_approval(tmp_path):
    # A genuine approval that ALSO quotes our template still reads as approval, in
    # every client style.
    for style in _ALL_QUOTE_STYLES:
        stripped = aa.strip_quoted_text(style("Approved, please publish it."))
        assert aa.is_approval_reply(stripped, AFFIRM, NEGATE) is True, style.__name__


def test_strip_keeps_plain_reply_unchanged():
    assert aa.strip_quoted_text("Approved, publish it.") == "Approved, publish it."
    assert aa.strip_quoted_text("Please cancel, I changed my mind.") == \
        "Please cancel, I changed my mind."


def test_strip_does_not_drop_members_own_quote_line(tmp_path):
    # Ralph #48 finding 2: a member types their OWN `>` aside then a LATER retraction.
    # We must NOT cut at the bare `>` (that would drop the retraction and wrongly
    # approve). No template sentinel here, so nothing is stripped; "cancel" then wins.
    reply = ("Approved, publish it.\n"
             "> (an aside I am quoting)\n"
             "Actually wait, please cancel for now.")
    stripped = aa.strip_quoted_text(reply)
    assert "please cancel" in stripped.lower()               # retraction preserved
    assert aa.is_approval_reply(stripped, AFFIRM, NEGATE) is False  # negation wins -> BLOCK


def test_strip_outlook_original_message_english_separator():
    text = ("Please cancel this.\n\n"
            "-----Original Message-----\n"
            "reply to this email with \"approved\" to publish it")
    assert aa.strip_quoted_text(text) == "Please cancel this."


def test_inflected_refusals_are_decisive():
    # #48 secondary gap incl. Ralph finding 3: whole-word matching means base verbs do
    # NOT match their inflected forms, so each real reply wording must be decisive --
    # else a later "I'm withdrawing my approval" fails to supersede an earlier approval.
    for refusal in ("Please cancel this.", "I've cancelled it.", "Consider it canceled.",
                    "I'm cancelling it.", "Declined.", "I have declined.", "I am declining.",
                    "I withdraw my approval.", "Approval withdrawn.",
                    "I'm withdrawing my approval, sorry.", "I request withdrawal."):
        assert aa.is_approval_reply(refusal, AFFIRM, NEGATE) is False, refusal
        assert aa.is_decisive_reply(refusal, AFFIRM, NEGATE) is True, refusal


# ------------------- html-only reply fallback (Ralph Opus finding 2: supersede)

def _gmail_html_message(msg_id: str, from_addr: str, html_body: str) -> dict:
    data = base64.urlsafe_b64encode(html_body.encode("utf-8")).decode("ascii")
    return {"id": msg_id, "payload": {
        "mimeType": "text/html",
        "headers": [{"name": "From", "value": from_addr}],
        "body": {"data": data}}}


def test_extract_plain_text_falls_back_to_html_when_no_plain_part():
    payload = {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(
        b"<p>Hello</p><div>please cancel this</div>").decode()}}
    text = aa.extract_plain_text(payload).lower()
    assert "please cancel this" in text


def test_extract_plain_text_prefers_plain_over_html():
    # With BOTH parts present, the plain part still wins (fallback is html-only).
    payload = {"mimeType": "multipart/alternative", "parts": [
        {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(
            b"<p>ignored html</p>").decode()}},
        {"mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(
            b"the real plain reply").decode()}},
    ]}
    assert aa.extract_plain_text(payload) == "the real plain reply"


# --------------- sentinel spacing robustness (Ralph re-review: whitespace holes)
# A byte-exact sentinel search missed a quoted template whose inter-word spacing the
# client had mangled (a non-breaking space, a tab, a double space, or a hard line-
# wrap), re-opening the leak. The whitespace-flexible sentinel must still cut, and
# _html_to_text must normalise nbsp and not fuse words across table cells.

def test_strip_sentinel_survives_whitespace_mutations():
    neutral = "Still reading through it, will get back to you soon."
    base = _markerless_quote(neutral)          # no secondary marker -> ONLY the
    approval = _markerless_quote("Approved, publish it.")  # sentinel can cut here
    def mut(s):  # every spacing mutation a client might apply to the quoted sentinel
        return {
            "nbsp": s.replace("Gingers in Tech", "Gingers\u00a0in\u00a0Tech"),
            "tab": s.replace("feature is ready", "feature\tis\tready"),
            "double_space": s.replace("Asians & Gingers", "Asians  &  Gingers"),
            "narrow_wrap": s.replace("Gingers in Tech feature", "Gingers in Tech\nfeature"),
        }
    for name, reply in mut(base).items():
        stripped = aa.strip_quoted_text(reply)
        assert "approved" not in stripped.lower(), (name, "quoted template leaked")
        assert aa.is_approval_reply(stripped, AFFIRM, NEGATE) is False, name
    # A genuine approval over the same mangled quote still publishes.
    for name, reply in mut(approval).items():
        stripped = aa.strip_quoted_text(reply)
        assert aa.is_approval_reply(stripped, AFFIRM, NEGATE) is True, name


def test_poll_html_only_nbsp_quoted_template_does_not_leak(tmp_path):
    # The html-only fallback path (Ralph Opus): &nbsp; spacing in the quoted template
    # must still be sentinel-cut. html.unescape yields U+00A0; _html_to_text (and the
    # whitespace-flexible sentinel) handle it. Neutral html-only reply -> BLOCK.
    sent_html = aa.compose_approval_email(
        "m@example.com", "hoiboyuk@gmail.com", "Jane", "My story.", "jane"
    ).get_body(preferencelist=("html",)).get_content()
    quoted = sent_html.replace("Gingers in Tech", "Gingers&nbsp;in&nbsp;Tech")
    reply_html = ("<div>Thanks, let me think about it.</div>"
                  "<blockquote>" + quoted + "</blockquote>")
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_html_message("in1", "m@example.com", reply_html),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is False


def test_html_to_text_does_not_fuse_words_across_table_cells():
    # Ralph finding: "<td>please</td><td>cancel</td>" fused to "pleasecancel", hiding
    # the refusal. Cell boundaries must become breaks so whole-word matching sees it.
    text = aa._html_to_text("<table><tr><td>please</td><td>cancel</td></tr></table>")
    assert aa.is_decisive_reply(text, AFFIRM, NEGATE) is True
    assert aa.is_approval_reply(text, AFFIRM, NEGATE) is False


def test_html_to_text_does_not_fuse_words_across_definition_list():
    # Ralph round-3 finding: <dt>/<dd> (and other block tags) must also break, not
    # only table cells -- else "<dt>please</dt><dd>cancel</dd>" fuses and hides the
    # refusal. The break set now covers the standard block/list elements.
    text = aa._html_to_text("<dl><dt>please</dt><dd>cancel</dd></dl>")
    assert aa.is_decisive_reply(text, AFFIRM, NEGATE) is True
    assert aa.is_approval_reply(text, AFFIRM, NEGATE) is False


def test_html_to_text_keeps_inline_formatted_word_intact():
    # An inline tag INSIDE a word must not fragment it: "<b>approved</b>" -> "approved".
    text = aa._html_to_text("<p>Great, <b>approved</b>, publish it.</p>")
    assert aa.is_approval_reply(text, AFFIRM, NEGATE) is True


def test_second_anchor_cuts_when_first_anchor_is_mangled():
    # Ralph round-3: the anchor match is all-or-nothing per phrase, so a client that
    # mangles ONE anchor must not re-open the leak -- the SECOND anchor still cuts.
    # Here the first anchor (the opening sentinel) is corrupted; the second
    # ("This is the EXACT wording we will publish") survives and strips the quote.
    broken = _markerless_quote("Thanks, let me think about it.").replace(
        "Your Asians & Gingers in Tech feature is ready", "Your XXXX feature is ready")
    stripped = aa.strip_quoted_text(broken)
    assert "approved" not in stripped.lower()
    assert aa.is_approval_reply(stripped, AFFIRM, NEGATE) is False


def test_anchor_match_is_case_insensitive():
    # A client that lower-cases the quoted sentinel must not defeat the cut.
    reply = _markerless_quote("Thanks, let me think about it.").lower()
    stripped = aa.strip_quoted_text(reply)
    assert "approved" not in stripped.lower()
    assert aa.is_approval_reply(stripped, AFFIRM, NEGATE) is False


def test_compose_email_emits_both_strip_anchors():
    # strip keys on BOTH anchors; compose MUST emit each verbatim (single source of
    # truth) in the plain part, else the client-independent cut silently degrades.
    for anchor in aa._TEMPLATE_ANCHORS:
        assert anchor in _SENT_PLAIN, anchor


# ----------------------------------- poll end-to-end over a quoted-template reply

def test_poll_neutral_reply_over_quoted_template_blocks(tmp_path):
    # END-TO-END of the leak: the member's reply carries neutral text PLUS the quoted
    # original. poll must BLOCK, and still record the FULL body (quote included) so
    # the operator sees everything.
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "m@example.com",
                       _outlook_quote("Thanks, let me think about it.")),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is False
    assert "let me think about it" in result["reply_text"].lower()
    assert "approved" in result["reply_text"].lower()  # full quote preserved for operator


def test_poll_genuine_approval_over_quoted_template_publishes(tmp_path):
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "m@example.com",
                       _gmail_quote("Approved, please publish it.")),
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
        _gmail_message("in1", "m@example.com", _gmail_quote("Approved, publish it.")),
        _gmail_message("in2", "m@example.com", _gmail_quote("Actually please cancel.")),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is False


def test_poll_approval_then_withdrawing_over_quote_blocks(tmp_path):
    # Ralph finding 3 end-to-end: a later "I'm withdrawing my approval" must supersede.
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "m@example.com", _gmail_quote("Approved, publish it.")),
        _gmail_message("in2", "m@example.com",
                       _gmail_quote("Actually, I'm withdrawing my approval, sorry.")),
    ]}
    svc = FakeService(thread=thread)
    result = aa.poll_for_approval(svc, tmp_path, thread_id="thr1",
                                  member_email="m@example.com")
    assert result is not None and result["approved"] is False


def test_poll_html_only_cancel_supersedes_earlier_approval(tmp_path):
    # Ralph Opus finding 2: member approves in plain text, then sends an html-ONLY
    # cancel (no text/plain part). The html fallback must read it so the later refusal
    # supersedes -- otherwise the stale approval publishes.
    thread = {"messages": [
        _gmail_message("out1", "hoiboyuk@gmail.com", "here is your feature"),
        _gmail_message("in1", "m@example.com", "Approved, publish it."),
        _gmail_html_message("in2", "m@example.com",
                            "<div>Actually, <b>please cancel</b> this.</div>"),
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
