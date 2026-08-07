"""E2E tier for the newsletter sender: the whole chain, end to end.

Two modes, and the difference matters.

DEFAULT (``BREVO_E2E`` unset, which is what CI runs on every push): the full chain
runs against a mocked transport with no network access at all. Render a post,
create the draft campaign, send the review copy, hand the token back, fire
``sendNow``. This is a real exercise of the chain rather than a placeholder, so the
Three-Tier gate's USE clause is satisfied on every change.

LIVE (``BREVO_E2E`` set, run deliberately by hand): the same chain against the real
Brevo API. It is gated for three reasons, none of which is "it burns a lifetime
quota" (the free tier's 300 is a DAILY allowance that resets, so that framing would
be wrong):

1. List 4's two members are the operator's real personal inbox and the sending
   address, so an ungated live send would land in his actual mail on every push and
   loop a copy back to the sender.
2. That 300/day cap is SHARED with the double-opt-in and operator-alert lane, so a
   burst of pushes competes with real subscriber confirmations, whose failure mode
   is silent from the reader's side.
3. This repo's commit cadence ran to 10+ commits across a few days on #56 alone.

So the live variant never touches list 4. It creates its own throwaway contact list,
points the sender at that, and deletes the list in teardown.

It deletes the LIST and never the CAMPAIGN. That asymmetry is deliberate and is the
expensive lesson of this issue: a campaign's id is baked into the unsubscribe URL of
every email it has already delivered, so deleting one 404s the unsubscribe link in
mail already sitting in people's inboxes. On a real send that is a PECR breach. The
sender has no delete path and must not gain one, and neither does this test.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import send_newsletter as sn  # noqa: E402

# Reused rather than re-modelled. The fake provider in the unit tier encodes two
# facts that were measured against the live API and are easy to get wrong twice:
# it PERSISTS across transport instances, and it does NOT echo the posted html
# byte-for-byte, because Brevo rewrites it slightly on ingest. Duplicating that
# model here would mean maintaining the same hard-won behaviour in two places.
from test_send_newsletter import BACKEND, SLUG, ok_transport, write_page  # noqa: E402

LIVE = os.environ.get("BREVO_E2E", "").strip()
LIVE_REASON = (
    "live Brevo E2E is opt-in: set BREVO_E2E=1 to run it. Unset, the chain still "
    "runs in full against a mocked transport, so this tier is never skipped wholesale."
)


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Throwaway tree + throwaway state for every test in this module."""
    rendered = tmp_path / "public" / "blogs"
    rendered.mkdir(parents=True)
    monkeypatch.setattr(sn, "RENDERED_ROOT", rendered)
    monkeypatch.setattr(sn, "STATE_FILE", tmp_path / ".newsletter-state.json")
    monkeypatch.setenv(sn.API_KEY_ENV, "test-key-not-a-real-credential")
    sn._COUNTERS.clear()
    BACKEND["path"] = tmp_path / "fake-brevo.json"
    return rendered


# --------------------------------------------------------------------------
# AC 4.5 -- the default tier: the full chain, mocked transport, no network
# --------------------------------------------------------------------------


def test_the_default_run_opens_no_socket(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prove the default run is offline, rather than asserting it in a docstring.

    Without this, "runs against a mocked transport" is a claim about intent. A
    transport that quietly fell through to the real API would still pass every other
    test in this file while sending real email to the operator's own inbox.

    urlopen is booby-trapped and then the FULL chain is driven over it. Reaching the
    end is the proof: had any call escaped the mock, the trap would have fired.
    """
    write_page(isolated, SLUG)

    def refuse(*a: object, **k: object) -> None:
        raise AssertionError("the default E2E run must not open a socket")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    transport = ok_transport()

    with mock.patch.object(sn, "_api_call", transport):
        assert sn.main(["--slug", SLUG, "--prepare"]) == 0
        state = json.loads(sn.STATE_FILE.read_text(encoding="utf-8"))
        confirmation = state["pending"][SLUG]["confirmation"]
        assert sn.main(["--slug", SLUG, "--send", "--confirm", confirmation]) == 0


def test_the_whole_chain_runs_through_the_real_cli_entry_point(isolated: Path) -> None:
    """render -> prepare -> sendTest -> confirm -> sendNow, driven through main().

    main() is used rather than prepare()/send() directly, because argument wiring is
    exactly the seam a unit test does not cover: a flag parsed into the wrong
    parameter is invisible to a function-level test and fatal in production.
    """
    write_page(isolated, SLUG)
    transport = ok_transport()

    with mock.patch.object(sn, "_api_call", transport):
        assert sn.main(["--slug", SLUG, "--prepare"]) == 0

    state = json.loads(sn.STATE_FILE.read_text(encoding="utf-8"))
    confirmation = state["pending"][SLUG]["confirmation"]

    with mock.patch.object(sn, "_api_call", transport):
        assert sn.main(["--slug", SLUG, "--send", "--confirm", confirmation]) == 0

    paths = [c.args[1] for c in transport.call_args_list]
    assert "/v3/emailCampaigns" in paths, "no campaign was created"
    assert any(p.endswith("/sendTest") for p in paths), "no review copy was sent"
    assert any(p.endswith("/sendNow") for p in paths), "the chain never reached sendNow"
    assert paths.index("/v3/emailCampaigns") < next(
        i for i, p in enumerate(paths) if p.endswith("/sendTest")
    ), "the review copy went before the campaign existed"

    final = json.loads(sn.STATE_FILE.read_text(encoding="utf-8"))
    assert SLUG in final["sent"], "the send was never recorded"
    assert SLUG not in final["pending"], "the pending entry outlived the send"


def test_the_review_copy_names_only_the_review_address(isolated: Path) -> None:
    """The whole gate is worthless if the review copy reaches the list."""
    write_page(isolated, SLUG)
    transport = ok_transport()
    with mock.patch.object(sn, "_api_call", transport):
        assert sn.main(["--slug", SLUG, "--prepare"]) == 0

    tests = [c for c in transport.call_args_list if c.args[1].endswith("/sendTest")]
    assert len(tests) == 1
    assert tests[0].kwargs["json"]["emailTo"] == [sn.REVIEW_ADDRESS]


def test_the_chain_stops_dead_without_the_token(isolated: Path) -> None:
    """The operator gate is the point of the whole tier, so E2E proves it too."""
    write_page(isolated, SLUG)
    transport = ok_transport()
    with mock.patch.object(sn, "_api_call", transport):
        assert sn.main(["--slug", SLUG, "--prepare"]) == 0
        assert sn.main(["--slug", SLUG, "--send", "--confirm", "not-the-token"]) != 0

    paths = [c.args[1] for c in transport.call_args_list]
    assert not any(p.endswith("/sendNow") for p in paths), "sendNow fired without approval"


# --------------------------------------------------------------------------
# AC 4.5 -- the live variant: real API, throwaway list, never list 4
# --------------------------------------------------------------------------


@pytest.mark.skipif(not LIVE, reason=LIVE_REASON)
class TestLiveChainAgainstItsOwnThrowawayList:
    """The real API, pointed at a list this test creates and destroys itself."""

    list_id: int | None = None
    folder_id: int | None = None

    @classmethod
    def setup_class(cls) -> None:
        brevo_key = sn.brevo_key_from_env()
        status, body = sn._api_call("GET", "/v3/contacts/folders", brevo_key=brevo_key)
        assert status == 200, f"could not read folders: {status} {body}"
        folders = body.get("folders") or []
        assert folders, "no contact folder exists to hold a throwaway list"
        cls.folder_id = folders[0]["id"]

        status, body = sn._api_call(
            "POST",
            "/v3/contacts/lists",
            json={"name": "blog-priv81 e2e throwaway", "folderId": cls.folder_id},
            brevo_key=brevo_key,
        )
        assert status == 201, f"throwaway list not created: {status} {body}"
        cls.list_id = body["id"]

    @classmethod
    def teardown_class(cls) -> None:
        """Delete the LIST. Never the campaign.

        A campaign id is baked into the unsubscribe URL of every email it has
        already delivered, so deleting one 404s that link in mail already sitting
        in inboxes. The draft this test leaves behind is deliberate litter.
        """
        if cls.list_id is None:
            return
        brevo_key = sn.brevo_key_from_env()
        status, body = sn._api_call(
            "DELETE", f"/v3/contacts/lists/{cls.list_id}", brevo_key=brevo_key
        )
        assert status in (204, 200), f"throwaway list {cls.list_id} not deleted: {status} {body}"

    def test_prepare_creates_a_draft_and_sends_a_real_review_copy(
        self, monkeypatch: pytest.MonkeyPatch, isolated: Path
    ) -> None:
        """Everything up to, but not including, sendNow.

        sendNow is deliberately NOT fired even against the throwaway list. The list
        is empty, so the send would carry no information, and the campaign it burns
        cannot be cleaned up afterwards for the reason in teardown_class. The
        approval gate below sendNow is what this tier can prove cheaply.
        """
        monkeypatch.setattr(sn, "LIST_ID", self.list_id)
        monkeypatch.setattr(sn, "RENDERED_ROOT", REPO_ROOT / "public" / "blogs")
        live_slug = os.environ.get("BREVO_E2E_SLUG", "").strip()
        if not live_slug:
            pytest.skip("set BREVO_E2E_SLUG to a rendered post slug for the live chain")

        assert sn.prepare(live_slug, sn.STATE_FILE) == 0
        state = json.loads(sn.STATE_FILE.read_text(encoding="utf-8"))
        entry = state["pending"][live_slug]
        assert entry["campaign_id"], "no campaign id recorded"

        brevo_key = sn.brevo_key_from_env()
        status, live = sn._api_call(
            "GET", f"/v3/emailCampaigns/{entry['campaign_id']}", brevo_key=brevo_key
        )
        assert status == 200
        assert live["status"] == "draft", "prepare left the campaign outside draft"
