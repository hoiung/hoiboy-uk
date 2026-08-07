#!/usr/bin/env python3
"""Unit tier for the newsletter sender (blog-priv#81 Phase 2, AC 2.3 to AC 2.14).

Every test here drives the real entry points in scripts/send_newsletter.py against a
mocked transport and a synthetic rendered-post tree. Nothing in this file touches the
network, the real public/ tree, or the real state file.

WHY THE TRANSPORT IS THE ONLY MOCK. The seam is one function, `_api_call`, and the
tests assert on the exact keyword arguments it received. A mock that swallowed
`**kwargs` would accept any payload at all and prove nothing about what Brevo would
actually be sent, which is the failure mode where a test stays green while the wire
format is wrong.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import send_newsletter as sn  # noqa: E402

# A page shaped the way this site actually renders one. The masthead h1 before the
# <article> is not decoration in this fixture: it is the exact structure
# layouts/_partials/sidebar.html:5 emits, and reproducing it here is what keeps the
# title extractor honest about which heading it reads.
PAGE = """<!doctype html><html><head>
<meta name="description" content="{excerpt}">
<meta property="article:published_time" content="{published}">
<link rel="canonical" href="{url}">
</head><body>
<aside><h1><a href="/" class="brand"><img src="/l.png" alt="logo">Life of O'Hoi</a></h1></aside>
<main><article>
  <h1>{title}</h1>
  <div class="post-meta"><time datetime="2026-06-04">4 June 2026</time></div>
  <p>Body copy the email never uses, because G-D settled on excerpt plus link.</p>
</article></main>
</body></html>
"""

SLUG = "a-real-post"
TITLE = "A Real Post About Something"
EXCERPT = "A description of the post, which is what the email actually carries."
PUBLISHED = "2026-06-04T12:00:00+01:00"


def write_page(root: Path, slug: str, **over: str) -> Path:
    fields = {
        "title": TITLE,
        "excerpt": EXCERPT,
        "published": PUBLISHED,
        "url": f"https://hoiboy.uk/blogs/{slug}/",
    }
    fields.update(over)
    path = root / slug / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PAGE.format(**fields), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every path the module reads at a throwaway tree, and clear the counters.

    The real template is used rather than a stub: it is the artefact under test as much
    as the sender is, and a stub template would let a placeholder-contract break pass.
    """
    rendered = tmp_path / "public" / "blogs"
    rendered.mkdir(parents=True)
    monkeypatch.setattr(sn, "RENDERED_ROOT", rendered)
    monkeypatch.setattr(sn, "STATE_FILE", tmp_path / ".newsletter-state.json")
    monkeypatch.setenv(sn.API_KEY_ENV, "test-key-not-a-real-credential")
    monkeypatch.delenv(sn.UNSUB_PAGE_ENV, raising=False)
    sn._COUNTERS.clear()
    return rendered


def ok_transport(created_id: int = 42) -> mock.Mock:
    """A transport that answers every documented success status."""

    def _call(method: str, path: str, **kw: object) -> tuple[int, dict]:
        if path == "/v3/emailCampaigns":
            return 201, {"id": created_id}
        return 204, {}

    return mock.Mock(side_effect=_call)


def prepare_then_confirmation(rendered: Path, transport: mock.Mock, slug: str = SLUG) -> str:
    write_page(rendered, slug)
    with mock.patch.object(sn, "_api_call", transport):
        assert sn.prepare(slug, sn.STATE_FILE) == 0
    state = json.loads(sn.STATE_FILE.read_text(encoding="utf-8"))
    return state["pending"][slug]["confirmation"]


# --------------------------------------------------------------------------
# AC 2.3 -- sendTest always names its recipient
# --------------------------------------------------------------------------


def test_send_test_always_passes_an_explicit_email_to(isolated: Path) -> None:
    """Omitting emailTo makes Brevo send to the whole test list, per its own spec."""
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)

    test_calls = [c for c in transport.call_args_list if c.args[1].endswith("/sendTest")]
    assert len(test_calls) == 1
    call_args = test_calls[0]
    assert call_args.kwargs["json"]["emailTo"] == [sn.REVIEW_ADDRESS]
    assert call_args.kwargs["json"]["emailTo"], "an empty list is the same hazard"


def test_prepare_never_calls_send_now(isolated: Path) -> None:
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    assert not [c for c in transport.call_args_list if c.args[1].endswith("/sendNow")]


# --------------------------------------------------------------------------
# AC 2.4 / AC 2.5 -- the token is the only way through
# --------------------------------------------------------------------------


def test_send_without_a_prepared_token_never_calls_send_now(isolated: Path) -> None:
    write_page(isolated, SLUG)
    send_now = mock.Mock(side_effect=AssertionError("sendNow must be unreachable here"))
    with mock.patch.object(sn, "_api_call", send_now):
        with pytest.raises(sn.NewsletterError, match="no prepared campaign"):
            sn.send(SLUG, "any-token-at-all", sn.STATE_FILE)
    send_now.assert_not_called()


def test_wrong_token_is_refused_and_sends_nothing(isolated: Path) -> None:
    prepare_then_confirmation(isolated, ok_transport())
    after_prepare = mock.Mock(side_effect=AssertionError("nothing may be sent"))
    with mock.patch.object(sn, "_api_call", after_prepare):
        with pytest.raises(sn.NewsletterError, match="does not match"):
            sn.send(SLUG, "wrong-token", sn.STATE_FILE)
    after_prepare.assert_not_called()


def test_the_token_survives_into_a_completely_fresh_process(
    isolated: Path, tmp_path: Path
) -> None:
    """A real second interpreter, because the operator's approval arrives later.

    This is the property the state file exists for, and it cannot be demonstrated in
    the process that minted the token: anything held in memory would appear to work.
    """
    confirmation = prepare_then_confirmation(isolated, ok_transport())

    driver = tmp_path / "driver.py"
    driver.write_text(
        "import sys, json\n"
        f"sys.path.insert(0, {str(REPO_ROOT / 'scripts')!r})\n"
        "from unittest import mock\n"
        "import send_newsletter as sn\n"
        f"sn.RENDERED_ROOT = {str(isolated)!r} and __import__('pathlib').Path({str(isolated)!r})\n"
        f"sn.STATE_FILE = __import__('pathlib').Path({str(sn.STATE_FILE)!r})\n"
        "with mock.patch.object(sn, '_api_call', mock.Mock(return_value=(204, {}))) as m:\n"
        f"    rc = sn.send({SLUG!r}, sys.argv[1], sn.STATE_FILE)\n"
        "    paths = [c.args[1] for c in m.call_args_list]\n"
        "print(json.dumps({'rc': rc, 'paths': paths}))\n",
        encoding="utf-8",
    )

    good = subprocess.run(
        [sys.executable, str(driver), confirmation],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", sn.API_KEY_ENV: "test-key-not-a-real-credential"},
    )
    assert good.returncode == 0, good.stderr
    result = json.loads(good.stdout.strip().splitlines()[-1])
    assert result["rc"] == 0
    assert any(p.endswith("/sendNow") for p in result["paths"])

    bad = subprocess.run(
        [sys.executable, str(driver), "wrong-token"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", sn.API_KEY_ENV: "test-key-not-a-real-credential"},
    )
    assert bad.returncode != 0


def test_state_file_path_is_gitignored() -> None:
    """The token is a live approval credential, and this repo is public."""
    ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".newsletter-state.json" in ignored


# --------------------------------------------------------------------------
# AC 2.7 -- the published promise about what this list is for
# --------------------------------------------------------------------------


def test_a_services_page_is_refused_naming_the_privacy_promise(isolated: Path) -> None:
    services = {
        "title": "AI Consultancy That Ships",
        "excerpt": "What we do for clients.",
        "url": "https://hoiboy.uk/hire-hoi/ai-consultancy/",
        "published": PUBLISHED,
    }
    with pytest.raises(sn.NewsletterError) as exc:
        sn.assert_is_blog_post(services)
    assert "privacy/index.md:77" in str(exc.value)


def test_a_category_landing_is_not_a_post(isolated: Path) -> None:
    """The seven category landings live under /blogs/ too, and are not sendable."""
    path = isolated / "tech-ai" / "index.html"
    path.parent.mkdir(parents=True)
    path.write_text(
        "<html><head><meta name='description' content='Posts about tech.'>"
        "<link rel='canonical' href='https://hoiboy.uk/blogs/tech-ai/'></head>"
        "<body><main><h2>Tech</h2></main></body></html>",
        encoding="utf-8",
    )
    with pytest.raises(sn.NewsletterError, match="missing title"):
        sn.read_post("tech-ai")


def test_a_slug_cannot_escape_the_rendered_tree(isolated: Path) -> None:
    for hostile in ("../hire-hoi", "..%2Fhire-hoi", "a/../../etc", "UPPER", ""):
        with pytest.raises(sn.NewsletterError):
            sn.rendered_path(hostile)


# --------------------------------------------------------------------------
# AC 2.8 -- personalisation that actually resolves
# --------------------------------------------------------------------------


def test_personalisation_uses_the_attribute_signup_actually_stores(
    isolated: Path,
) -> None:
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    create = [c for c in transport.call_args_list if c.args[1] == "/v3/emailCampaigns"][0]
    body = create.kwargs["json"]["htmlContent"]
    assert "FIRSTNAME" in body
    # The spec's own toField example uses a different attribute spelling, which this
    # site never writes; copying it would render an empty greeting for every reader.
    assert "FNAME}" not in body


def test_the_title_read_is_the_article_heading_not_the_masthead(isolated: Path) -> None:
    """Every page renders two h1 elements and the masthead comes first.

    Regression guard for a defect this suite's own sample run caught: an unscoped
    "first h1 wins" extractor read the site name, so every campaign would have gone
    out subject-lined with the masthead instead of the post title.
    """
    write_page(isolated, SLUG)
    post = sn.read_post(SLUG)
    assert post["title"] == TITLE
    assert "Life of O'Hoi" not in post["title"]


# --------------------------------------------------------------------------
# AC 2.9 -- exactly once
# --------------------------------------------------------------------------


def test_second_send_is_refused(isolated: Path) -> None:
    confirmation = prepare_then_confirmation(isolated, ok_transport())
    transport = ok_transport()
    with mock.patch.object(sn, "_api_call", transport):
        assert sn.send(SLUG, confirmation, sn.STATE_FILE) == 0
        with pytest.raises(sn.NewsletterError, match="already sent"):
            sn.send(SLUG, confirmation, sn.STATE_FILE)
    sends = [c for c in transport.call_args_list if c.args[1].endswith("/sendNow")]
    assert len(sends) == 1


def test_preparing_an_already_sent_post_is_refused(isolated: Path) -> None:
    confirmation = prepare_then_confirmation(isolated, ok_transport())
    with mock.patch.object(sn, "_api_call", ok_transport()):
        sn.send(SLUG, confirmation, sn.STATE_FILE)
    with mock.patch.object(sn, "_api_call", ok_transport()):
        with pytest.raises(sn.NewsletterError, match="already sent"):
            sn.prepare(SLUG, sn.STATE_FILE)


def test_a_post_edited_after_review_is_refused(isolated: Path) -> None:
    """What ships must be what was approved, or the gate has been walked around."""
    confirmation = prepare_then_confirmation(isolated, ok_transport())
    write_page(isolated, SLUG, title="A Rewritten Title Nobody Reviewed")
    transport = ok_transport()
    with mock.patch.object(sn, "_api_call", transport):
        with pytest.raises(sn.NewsletterError, match="has changed since the review"):
            sn.send(SLUG, confirmation, sn.STATE_FILE)
    assert not [c for c in transport.call_args_list if c.args[1].endswith("/sendNow")]


# --------------------------------------------------------------------------
# AC 2.10 -- loud failure
# --------------------------------------------------------------------------


def test_402_exits_nonzero(isolated: Path) -> None:
    """The free plan makes an out-of-credit sendNow genuinely reachable."""
    confirmation = prepare_then_confirmation(isolated, ok_transport())

    def broke(method: str, path: str, **kw: object) -> tuple[int, dict]:
        if path.endswith("/sendNow"):
            return 402, {"code": "not_enough_credits", "message": "no credit"}
        return 204, {}

    with mock.patch.object(sn, "_api_call", mock.Mock(side_effect=broke)):
        with pytest.raises(sn.NewsletterError, match="402"):
            sn.send(SLUG, confirmation, sn.STATE_FILE)

    # And the state must NOT record it as sent, or the double-send guard would block
    # the retry that is now the correct action.
    state = json.loads(sn.STATE_FILE.read_text(encoding="utf-8"))
    assert SLUG not in state["sent"]
    assert SLUG in state["pending"]


def test_a_non_2xx_create_exits_nonzero_through_main(isolated: Path) -> None:
    write_page(isolated, SLUG)
    with mock.patch.object(sn, "_api_call", mock.Mock(return_value=(400, {"m": "bad"}))):
        with mock.patch.object(sn, "STATE_FILE", sn.STATE_FILE):
            rc = sn.main(["--slug", SLUG, "--prepare"])
    assert rc == 1


def test_a_missing_key_is_named_not_guessed(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(sn.API_KEY_ENV, raising=False)
    with pytest.raises(sn.NewsletterError, match=sn.API_KEY_ENV):
        sn.brevo_key_from_env()


# --------------------------------------------------------------------------
# AC 2.11 -- no address reaches a log line
# --------------------------------------------------------------------------


def test_no_recipient_in_logs(isolated: Path, capsys: pytest.CaptureFixture) -> None:
    """Including an address arriving by an unexpected route, inside an error body.

    Driven through main() rather than prepare(), because main() is what the operator
    actually runs and is the only path that writes the fatal line. Testing the inner
    function would have skipped the very log line most likely to carry an address:
    the one built from an upstream error body.
    """
    write_page(isolated, SLUG)
    leaky = "a.subscriber@example.com"

    def leaks(method: str, path: str, **kw: object) -> tuple[int, dict]:
        if path == "/v3/emailCampaigns":
            return 201, {"id": 7}
        return 400, {"message": f"could not deliver to {leaky}"}

    with mock.patch.object(sn, "_api_call", mock.Mock(side_effect=leaks)):
        assert sn.main(["--slug", SLUG, "--prepare"]) == 1

    captured = capsys.readouterr()
    stream = captured.out + captured.err
    assert leaky not in stream
    assert sn.REVIEW_ADDRESS not in stream
    assert "[email-redacted]" in stream, "the address was dropped, not redacted"
    assert "400" in stream, "the status must still be diagnosable"


def test_redaction_survives_nesting(isolated: Path) -> None:
    # RFC 2606 reserved domains, which the repo's own secret scanner allowlists.
    payload = {
        "a": ["reader@example.com"],
        "b": {"c": "delivery failed for someone@example.org"},
        "n": 3,
    }
    cleaned = sn._redact(payload)
    assert "@" not in json.dumps(cleaned)
    assert cleaned["n"] == 3


# --------------------------------------------------------------------------
# AC 2.12 / AC 2.13 / AC 2.14 -- what actually goes on the wire
# --------------------------------------------------------------------------


def test_the_body_is_the_rendered_pages_own_words(isolated: Path) -> None:
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    create = [c for c in transport.call_args_list if c.args[1] == "/v3/emailCampaigns"][0]
    payload = create.kwargs["json"]
    assert payload["subject"] == TITLE
    assert EXCERPT in payload["htmlContent"]
    assert f"https://hoiboy.uk/blogs/{SLUG}/" in payload["htmlContent"]
    # The engineering notes and the voice markers are repo-side only.
    assert "<!--" not in payload["htmlContent"]
    assert "iamhoi" not in payload["htmlContent"]
    assert "%%" not in payload["htmlContent"]


def test_all_eight_branding_fields_reach_the_wire(isolated: Path) -> None:
    """Set explicitly, not inherited. A grep of the source cannot prove this."""
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    payload = [
        c for c in transport.call_args_list if c.args[1] == "/v3/emailCampaigns"
    ][0].kwargs["json"]
    for field in (
        "footer",
        "header",
        "previewText",
        "replyTo",
        "utmCampaign",
        "mirrorActive",
        "inlineImageActivation",
    ):
        assert field in payload, f"{field} left to a Brevo default"
    assert payload["replyTo"] == sn.REPLY_TO
    assert payload["mirrorActive"] is False
    assert payload["inlineImageActivation"] is False


def test_the_unsubscribe_page_is_dropped_rather_than_sent_empty(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty string is a malformed page id, not a weaker one."""
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    payload = [
        c for c in transport.call_args_list if c.args[1] == "/v3/emailCampaigns"
    ][0].kwargs["json"]
    assert "unsubscriptionPageId" not in payload

    monkeypatch.setenv(sn.UNSUB_PAGE_ENV, "62cbb7fabbe85021021aac52")
    post = sn.read_post(SLUG)
    with_page = sn.campaign_payload(post, SLUG, "<p>body</p>")
    assert with_page["unsubscriptionPageId"] == "62cbb7fabbe85021021aac52"


def test_exactly_one_content_field_is_sent(isolated: Path) -> None:
    """The API treats the three content fields as mutually exclusive."""
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    payload = [
        c for c in transport.call_args_list if c.args[1] == "/v3/emailCampaigns"
    ][0].kwargs["json"]
    present = [f for f in ("htmlContent", "htmlUrl", "templateId") if f in payload]
    assert present == ["htmlContent"]


def test_the_campaign_targets_the_newsletter_list_and_the_verified_sender(
    isolated: Path,
) -> None:
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    payload = [
        c for c in transport.call_args_list if c.args[1] == "/v3/emailCampaigns"
    ][0].kwargs["json"]
    assert payload["recipients"] == {"listIds": [sn.LIST_ID]}
    assert payload["sender"] == {"id": sn.SENDER_ID}


def test_utm_campaign_obeys_the_charset_the_api_documents(isolated: Path) -> None:
    """Brevo allows only alphanumerics and spaces here, and every slug is hyphenated."""
    import re

    for slug in ("a-real-post", "16-skills-ultimate-adventurer", "2026-04-07-foundation"):
        value = sn.utm_campaign(slug)
        assert re.fullmatch(r"[A-Za-z0-9 ]+", value), value


def test_the_campaign_name_is_the_documented_handle(isolated: Path) -> None:
    assert sn.campaign_name(SLUG, PUBLISHED) == f"blog-{SLUG}-2026-06-04"


def test_an_unbuilt_site_is_named_as_the_reason(isolated: Path) -> None:
    with pytest.raises(sn.NewsletterError, match="hugo --gc --minify"):
        sn.read_post("never-rendered")


def test_a_corrupt_state_file_stops_everything(isolated: Path) -> None:
    """A send guard that cannot read its own record must not guess."""
    sn.STATE_FILE.write_text("{not json", encoding="utf-8")
    with pytest.raises(sn.NewsletterError, match="unreadable"):
        sn.load_state(sn.STATE_FILE)


def test_the_audit_trail_records_both_acts(isolated: Path) -> None:
    confirmation = prepare_then_confirmation(isolated, ok_transport())
    with mock.patch.object(sn, "_api_call", ok_transport()):
        sn.send(SLUG, confirmation, sn.STATE_FILE)
    audit = json.loads(sn.STATE_FILE.read_text(encoding="utf-8"))["audit"]
    assert [entry["action"] for entry in audit] == ["prepare", "send"]
    assert all(entry["campaign_id"] == 42 for entry in audit)


def test_main_writes_state_where_the_module_currently_points(isolated: Path) -> None:
    """The state path must resolve when called, not when the module was imported.

    A `state_path: Path = STATE_FILE` default freezes the constant into the signature
    at import, so main() would keep writing to the repo root however STATE_FILE was
    later set. The earlier tests all happened to fail before reaching save_state, so
    they passed either way; this one runs a full prepare through main() and looks at
    where the file landed.
    """
    write_page(isolated, SLUG)
    with mock.patch.object(sn, "_api_call", ok_transport()):
        assert sn.main(["--slug", SLUG, "--prepare"]) == 0
    assert sn.STATE_FILE.is_file(), "state went somewhere other than the patched path"
    assert not (REPO_ROOT / ".newsletter-state.json").exists()
    assert SLUG in json.loads(sn.STATE_FILE.read_text(encoding="utf-8"))["pending"]


def test_send_requires_the_confirm_flag_through_main(isolated: Path) -> None:
    write_page(isolated, SLUG)
    guard = mock.Mock(side_effect=AssertionError("must not reach the API"))
    with mock.patch.object(sn, "_api_call", guard):
        assert sn.main(["--slug", SLUG, "--send"]) == 1
    guard.assert_not_called()
