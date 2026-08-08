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

import importlib.util
import io
import json
import re
import subprocess
import sys
import urllib.error
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
<meta property="og:image" content="{hero}">
<meta property="og:image:alt" content="{hero_alt}">
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
        "hero": f"https://hoiboy.uk/blogs/{slug}/hero_hu_deadbeef.jpg",
        "hero_alt": TITLE,
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
    sn._COUNTERS.clear()
    # The fake provider's persistence, fresh per test.
    BACKEND["path"] = tmp_path / "fake-brevo.json"
    return rendered


BACKEND: dict[str, Path] = {}


def ok_transport(created_id: int = 42, drift: str = "", html_drift: str = "") -> mock.Mock:
    """A transport that answers every documented success status.

    It MODELS the provider rather than echoing the request, in two ways that both
    turned out to matter:

    1. It PERSISTS. State is written to a file, so a campaign created by --prepare is
       still there for a --send in a different transport instance, or a different
       process. A per-instance dict looked fine and quietly made every cross-invocation
       test compare against an empty campaign.
    2. The stored html is deliberately NOT byte-identical to what was posted, because
       Brevo really does rewrite it slightly on ingest (measured on the live API: 5461
       bytes sent, 5459 read back). A mock that echoed the request perfectly would have
       hidden that, and the send-side comparison would have been written against two
       values that can never match in production.

    `drift` overrides the stored subject and `html_drift` the stored body, each
    standing in for a dashboard edit made after review. Both exist because
    `content_fingerprint` hashes subject AND body, so a fixture that could only move
    the subject left half the guard with no test able to kill it. Ralph tier 3 found
    that gap by mutation rather than by reading.
    """
    store = BACKEND["path"]

    def _load() -> dict:
        return json.loads(store.read_text(encoding="utf-8")) if store.is_file() else {}

    def _call(method: str, path: str, **kw: object) -> tuple[int, dict]:
        if path == "/v3/emailCampaigns" and method == "POST":
            body = dict(kw.get("json") or {})
            data = _load()
            data[str(created_id)] = {
                "id": created_id,
                "status": "draft",
                # The provider's own normalisation, modelled not assumed away.
                # `.strip()` is the whole model, and that is deliberate. An earlier
                # version also stripped a `<!doctype html>` prefix, which measured as
                # pure decoration: the template carries no doctype (`grep -ci doctype`
                # on it returns 0), so that clause changed zero bytes and only made the
                # fixture look like it modelled more than it did.
                "htmlContent": str(body.get("htmlContent", "")).strip(),
                "subject": str(body.get("subject", "")),
            }
            store.write_text(json.dumps(data), encoding="utf-8")
            return 201, {"id": created_id}
        if path == f"/v3/emailCampaigns/{created_id}" and method == "GET":
            camp = dict(_load().get(str(created_id), {}))
            if not camp:
                return 404, {"message": "not found"}
            if drift:
                camp["subject"] = drift
            if html_drift:
                camp["htmlContent"] = html_drift
            return 200, camp
        return 204, {}

    return mock.Mock(side_effect=_call)


def prepare_then_confirmation(rendered: Path, transport: mock.Mock, slug: str = SLUG) -> str:
    write_page(rendered, slug)
    with mock.patch.object(sn, "_api_call", transport):
        assert sn.prepare(slug, sn.STATE_FILE) == 0
    state = json.loads(sn.STATE_FILE.read_text(encoding="utf-8"))
    return state["pending"][slug]["confirmation"]


def endpoint_of(method: str, path: str, created_id: int = 42) -> str:
    """Name the Brevo endpoint a (method, path) pair addresses.

    Written as a helper rather than inline `.endswith` checks because `.endswith`
    is what let the sendNow VERB and the campaign id in its PATH go unpinned: a
    suffix match is satisfied by `DELETE /v3/emailCampaigns/sendNow` just as
    happily as by the real call.
    """
    if path == "/v3/emailCampaigns" and method == "POST":
        return "create"
    if path == f"/v3/emailCampaigns/{created_id}/sendTest" and method == "POST":
        return "send_test"
    if path == f"/v3/emailCampaigns/{created_id}/sendNow" and method == "POST":
        return "send_now"
    if path == f"/v3/emailCampaigns/{created_id}" and method == "GET":
        return "campaign_get"
    return f"UNEXPECTED {method} {path}"


def transport_answering(
    overrides: dict[str, tuple[int, dict]], created_id: int = 42
) -> mock.Mock:
    """ok_transport with one endpoint's answer replaced.

    Exists so each `_expect` ok-tuple can be driven with a status just OUTSIDE it.
    Every one of the five was unpinned: the suite proved `_expect` was wired (a 402
    exits non-zero) but never that any particular tuple held its contents, so
    widening `(204,)` to `(204, 400)` on the send made a REFUSED send print
    "Campaign 42 sent to list 4.", record the slug as sent and then refuse every
    retry forever.
    """
    base = ok_transport(created_id)

    def _call(method: str, path: str, **kw: object) -> tuple[int, dict]:
        name = endpoint_of(method, path, created_id)
        if name in overrides:
            return overrides[name]
        return base.side_effect(method, path, **kw)  # type: ignore[misc]

    return mock.Mock(side_effect=_call)


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
        # The fake provider is read from the SAME file the parent process wrote, so
        # the campaign created by --prepare is still there. A blanket 204 mock would
        # answer the send path's campaign re-read with the wrong shape entirely.
        f"store = __import__('pathlib').Path({str(BACKEND['path'])!r})\n"
        "def fake(method, path, **kw):\n"
        "    data = json.loads(store.read_text()) if store.is_file() else {}\n"
        "    if method == 'GET' and path.startswith('/v3/emailCampaigns/'):\n"
        "        cid = path.rsplit('/', 1)[-1]\n"
        "        return (200, data[cid]) if cid in data else (404, {})\n"
        "    return (204, {})\n"
        "with mock.patch.object(sn, '_api_call', mock.Mock(side_effect=fake)) as m:\n"
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
    """The token is a live approval credential, and this repo is public.

    Asserted against the module's OWN constant rather than a repeated literal. The
    literal-only version left the constant and the ignore rule free to drift: the
    module could be renamed to write `.newsletter-tokens.json`, which nothing
    ignores, while this test went on happily confirming that a filename the code no
    longer uses is still listed. Live approval tokens would then be sitting in the
    working tree of a PUBLIC repo, one `git add -A` from being published.

    The fresh module load is not ceremony, and writing it without one is how this
    was nearly missed twice. The autouse fixture patches `sn.STATE_FILE` onto a
    tmp_path for every test in this file, so `sn.STATE_FILE.name` reads
    ".newsletter-state.json" from the FIXTURE whatever the source says -- the
    rename mutation survived an assertion that looked exactly right. Same trap as
    `test_the_rendered_root_is_hugos_own_output_directory` below.
    """
    spec = importlib.util.spec_from_file_location("_send_newsletter_state_path", sn.__file__)
    assert spec is not None and spec.loader is not None
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)

    ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert fresh.STATE_FILE.name == ".newsletter-state.json"
    assert fresh.STATE_FILE.name in ignored
    assert fresh.STATE_FILE.parent == fresh.REPO_ROOT


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


def test_a_category_landing_is_refused_by_the_metadata_guard_not_the_url_guard(
    isolated: Path,
) -> None:
    """A landing is unsendable, and this pins WHICH guard does it.

    The category landings really do live under /blogs/, next to the posts: `ls
    public/blogs/` shows `adventure/` sitting beside `why-bpm-matters-...`. So the
    canonical-URL check CANNOT tell them apart. Same prefix, same shape.

    This test was named for the landing rule while asserting `read_post`'s "missing
    title", which made the consent gate look like it was doing work it never did.
    Ralph tier 3 measured the truth: `assert_is_blog_post` ACCEPTS
    `https://hoiboy.uk/blogs/tech-ai/`. Both halves are asserted now, so the division
    of labour is deliberate instead of incidental, and nobody later relaxes
    `read_post`'s metadata requirement believing the URL check has it covered.
    """
    path = isolated / "tech-ai" / "index.html"
    path.parent.mkdir(parents=True)
    path.write_text(
        "<html><head><meta name='description' content='Posts about tech.'>"
        "<link rel='canonical' href='https://hoiboy.uk/blogs/tech-ai/'></head>"
        "<body><main><h2>Tech</h2></main></body></html>",
        encoding="utf-8",
    )

    # The guard that actually stops it: no title inside <article>, no publish date.
    with pytest.raises(sn.NewsletterError, match="missing title"):
        sn.read_post("tech-ai")

    # And the guard that does NOT, stated rather than left implied. If this ever
    # starts raising, the URL check has gained real post-vs-landing knowledge and
    # assert_is_blog_post's docstring needs to change with it.
    sn.assert_is_blog_post({
        "url": "https://hoiboy.uk/blogs/tech-ai/",
        "title": "Tech",
        "excerpt": "e",
        "published": PUBLISHED,
    })


def test_a_canonical_that_escapes_the_blogs_tree_is_refused() -> None:
    """`.../blogs/../hire-hoi/` starts with the prefix and points somewhere else.

    A bare `startswith` accepted it. That target is the services tree, which
    `content/legal/privacy/index.md:77` puts off limits without fresh consent, so a
    prefix check reaching the right verdict only by luck was not good enough.
    """
    with pytest.raises(sn.NewsletterError, match="traverses out of"):
        sn.assert_is_blog_post({
            "url": "https://hoiboy.uk/blogs/../hire-hoi/ai-consultancy/",
            "title": "T", "excerpt": "e", "published": PUBLISHED,
        })


def test_the_blogs_index_itself_is_not_a_post() -> None:
    with pytest.raises(sn.NewsletterError, match="blogs index itself"):
        sn.assert_is_blog_post({
            "url": sn.CANONICAL_PREFIX,
            "title": "T", "excerpt": "e", "published": PUBLISHED,
        })


@pytest.mark.parametrize(
    "url",
    [
        "http://hoiboy.uk/blogs/a-real-post/",                # downgraded scheme
        "https://hoiboy.uk.example.com/blogs/x/",             # look-alike host
        "https://example.com/blogs/x/",                       # wrong host entirely
        "https://example.com/?u=https://hoiboy.uk/blogs/x/",  # prefix present, not leading
        "//hoiboy.uk/blogs/x/",                               # scheme-relative
        "",                                                   # empty
    ],
)
def test_the_consent_gate_rejects_the_adversarial_url_band(url: str) -> None:
    """Near-misses around the canonical prefix, not just the obvious services page.

    Ralph tier 3's structural finding was that nearly every guard here had exactly
    one test, each sitting comfortably inside or outside the boundary and none ON it.
    A classifier is only as good as its worst near-miss.
    """
    with pytest.raises(sn.NewsletterError):
        sn.assert_is_blog_post({
            "url": url, "title": "T", "excerpt": "e", "published": PUBLISHED,
        })


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


def test_the_unsubscribe_merge_tag_is_the_one_brevo_actually_resolves(
    isolated: Path,
) -> None:
    """The most legally load-bearing string in the message, pinned at both sites.

    Ralph round 3 tier 3 misspelled BREVO_UNSUBSCRIBE_TAG, repointed it at a dead
    URL, and blanked it to an empty string. All three SURVIVED a green 67-test
    run, while the same mutation applied to the sibling FIRSTNAME tag was caught.
    An unresolved tag ships mail whose only unsubscribe control is a dead link,
    which is a PECR problem, not a cosmetic one.

    The literal is written out here ON PURPOSE. Asserting
    `sn.BREVO_UNSUBSCRIBE_TAG in body` would pass under every one of those three
    mutations, because the constant and the rendered output move together: that
    assertion tests that a substitution happened, not that the result is the
    string Brevo resolves. This file's own history is the argument for the
    distinction.
    """
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    create = [c for c in transport.call_args_list if c.args[1] == "/v3/emailCampaigns"][0]
    payload = create.kwargs["json"]

    assert "{{ unsubscribe }}" in payload["htmlContent"], (
        "the campaign body must carry Brevo's own unsubscribe merge tag verbatim; "
        "anything else reaches the reader unresolved"
    )
    assert "{{ unsubscribe }}" in payload["footer"], (
        "the footer's Unsubscribe href is the one a mail client surfaces natively"
    )


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


def test_the_hero_is_the_og_image_not_the_on_page_webp(isolated: Path) -> None:
    """WebP is the one format the Outlook Word engine cannot render.

    The post PAGE shows hero.webp. The email must not: it takes the og:image
    beside it, which Hugo emits as a JPEG at 1200x630 (exactly 2x the 600px
    column), already absolute and already alt-texted. Measured across the corpus,
    90 of 90 sendable posts satisfy that, so this needs no new asset pipeline.
    """
    path = write_page(isolated, SLUG)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "<main>",
            '<main><img class="post-hero" src="/blogs/x/hero.webp" alt="on-page">',
        ),
        encoding="utf-8",
    )
    transport = ok_transport()
    with mock.patch.object(sn, "_api_call", transport):
        sn.prepare(SLUG, sn.STATE_FILE)
    body = [
        c for c in transport.call_args_list if c.args[1] == "/v3/emailCampaigns"
    ][0].kwargs["json"]["htmlContent"]
    assert ".webp" not in body, "a WebP hero would break Outlook"
    assert "hero_hu_deadbeef.jpg" in body
    assert body.count("<img") == 1
    # Absolute, because a mail client has no base URL to resolve against.
    assert 'src="https://' in body


def test_a_blocked_hero_still_reads(isolated: Path) -> None:
    """Gmail blocks images by default, so the image-off state is the common one."""
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    body = [
        c for c in transport.call_args_list if c.args[1] == "/v3/emailCampaigns"
    ][0].kwargs["json"]["htmlContent"]
    imgs = body.count("<img")
    assert imgs == 1
    # Alt text carries the meaning when the pixels never arrive, and the bgcolor
    # makes the gap a deliberate neutral block rather than broken white space.
    assert body.count('alt="') == imgs
    assert body.count("bgcolor=") >= imgs
    assert f'alt="{TITLE}"' in body


def test_a_post_with_no_og_image_is_refused_not_sent_headless(isolated: Path) -> None:
    """Fail loud rather than send an email with a hole where the hero goes."""
    path = write_page(isolated, SLUG)
    stripped = re.sub(r'<meta property="og:image"[^>]*>', "", path.read_text(encoding="utf-8"))
    path.write_text(stripped, encoding="utf-8")
    with pytest.raises(sn.NewsletterError, match="og:image"):
        sn.read_post(SLUG)


def test_a_generic_branded_card_is_refused_as_hard_as_no_image(isolated: Path) -> None:
    """Operator rule: every email carries a real image, or no email is sent.

    An absent og:image is not the realistic failure. The site always resolves one,
    falling back to the branded default card, so the actual bad outcome is an email
    whose picture says nothing about the thing it links to. That is refused just as
    hard as nothing at all. Measured today across the corpus, 0 of 90 posts hit this,
    and scripts/check_social_cards.py already fails the BUILD for a singular page that
    would fall back, so this is the runtime twin of an existing gate rather than its
    replacement.
    """
    for marker in sn.GENERIC_CARD_MARKERS:
        write_page(
            isolated,
            SLUG,
            hero=f"https://hoiboy.uk/{marker}_hu_abc123.jpg",
        )
        with pytest.raises(sn.NewsletterError, match="no image of its own"):
            sn.read_post(SLUG)


def test_a_page_whose_image_is_a_share_card_is_accepted(isolated: Path) -> None:
    """The site resolves share-card BEFORE hero (head.html:84), so both must work.

    Posts carry no share-card and resolve to their hero; a generated service or
    landing page carries a share-card and no hero. Reading og:image inherits that
    whole chain, so neither shape needs special handling here. This pins that the
    share-card shape is genuinely accepted rather than accidentally excluded.
    """
    write_page(
        isolated,
        SLUG,
        hero=f"https://hoiboy.uk/blogs/{SLUG}/share-card_hu_abc123.jpg",
    )
    post = sn.read_post(SLUG)
    assert post["hero"].endswith("share-card_hu_abc123.jpg")


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


def test_a_campaign_edited_after_review_is_refused(isolated: Path) -> None:
    """The gate must verify the thing that SHIPS, not only the thing it was built from.

    The post fingerprint catches an edited post. It cannot catch an edited campaign:
    anything holding the API key can change a draft's subject or body after --prepare,
    and the post it was rendered from stays untouched, so the send would fire happily.

    Not hypothetical. A test-round subject marker was written straight onto a live
    draft through the API and nothing objected, which is how this hole was found: the
    campaign that would have gone out carried a subject the operator never saw.
    """
    write_page(isolated, SLUG)
    transport = ok_transport()
    with mock.patch.object(sn, "_api_call", transport):
        sn.prepare(SLUG, sn.STATE_FILE)
    state = json.loads(sn.STATE_FILE.read_text(encoding="utf-8"))
    confirmation = state["pending"][SLUG]["confirmation"]

    # Someone edits the draft's subject between review and send.
    edited = ok_transport(drift="[TEST MARKER] a subject nobody reviewed")
    with mock.patch.object(sn, "_api_call", edited):
        with pytest.raises(sn.NewsletterError, match="no longer matches the review copy"):
            sn.send(SLUG, confirmation, sn.STATE_FILE)
    assert not [c for c in edited.call_args_list if c.args[1].endswith("/sendNow")]


def test_the_campaign_fingerprint_survives_provider_normalisation(
    isolated: Path,
) -> None:
    """The stored copy is NOT byte-identical to what was posted, and that is fine.

    Brevo rewrites the html slightly on ingest. The fingerprint is therefore taken
    from the PROVIDER's stored version at review time, not from what we generated.
    Getting this wrong would not fail loudly: it would mismatch on every send and
    block the path permanently, which is a worse bug than the one it guards against.
    """
    write_page(isolated, SLUG)
    transport = ok_transport()
    with mock.patch.object(sn, "_api_call", transport):
        sn.prepare(SLUG, sn.STATE_FILE)
    entry = json.loads(sn.STATE_FILE.read_text(encoding="utf-8"))["pending"][SLUG]
    assert entry["campaign_fingerprint"] != entry["fingerprint"], (
        "the two digests must differ, or the test transport is echoing the request "
        "back unchanged and is not modelling the provider at all"
    )

    with mock.patch.object(sn, "_api_call", ok_transport()):
        assert sn.send(SLUG, entry["confirmation"], sn.STATE_FILE) == 0


def test_a_campaign_no_longer_in_draft_is_refused(isolated: Path) -> None:
    """Already left draft means it may already have gone out. Do not send again."""
    write_page(isolated, SLUG)
    transport = ok_transport()
    with mock.patch.object(sn, "_api_call", transport):
        sn.prepare(SLUG, sn.STATE_FILE)
    confirmation = json.loads(
        sn.STATE_FILE.read_text(encoding="utf-8")
    )["pending"][SLUG]["confirmation"]

    def already_sent(method: str, path: str, **kw: object) -> tuple[int, dict]:
        if path == "/v3/emailCampaigns/42" and method == "GET":
            return 200, {"id": 42, "status": "sent", "htmlContent": "", "subject": ""}
        return 204, {}

    guard = mock.Mock(side_effect=already_sent)
    with mock.patch.object(sn, "_api_call", guard):
        with pytest.raises(sn.NewsletterError, match="not a draft"):
            sn.send(SLUG, confirmation, sn.STATE_FILE)
    assert not [c for c in guard.call_args_list if c.args[1].endswith("/sendNow")]


def test_402_exits_nonzero(isolated: Path) -> None:
    """The free plan makes an out-of-credit sendNow genuinely reachable."""
    confirmation = prepare_then_confirmation(isolated, ok_transport())

    healthy = ok_transport()

    def broke(method: str, path: str, **kw: object) -> tuple[int, dict]:
        if path.endswith("/sendNow"):
            return 402, {"code": "not_enough_credits", "message": "no credit"}
        # Everything up to the send behaves normally, including the campaign re-read,
        # so the 402 is reached rather than the run failing earlier for another reason.
        return healthy(method, path, **kw)

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


def test_a_confirmation_token_never_starts_with_a_hyphen(monkeypatch) -> None:
    """The printed --confirm command has to be runnable, every time.

    token_urlsafe draws from base64url, whose 62nd character is `-`, so about 1
    token in 64 began with one. argparse then reads the value as an option and the
    exact command --prepare prints dies with "expected one argument" before any
    approval logic runs. Measured at 1.52% over 100,000 draws.

    Driven deterministically rather than by sampling: a probabilistic test would
    pass ~98% of the time with the guard deleted, which is worse than no test.
    """
    draws = iter(["-leading-dash-token", "-another-one", "cleanToken_123"])
    monkeypatch.setattr(sn.secrets, "token_urlsafe", lambda n: next(draws))

    minted = sn.mint_confirmation()

    assert minted == "cleanToken_123", "it must keep drawing until the token is usable"
    assert not minted.startswith("-")


def test_a_hyphen_leading_token_really_would_break_the_cli() -> None:
    """Pins WHY the guard above exists, so nobody deletes it as paranoia.

    If argparse ever stops treating a leading-dash value as an option, this goes
    red and the redraw can be reconsidered. Until then it is load-bearing.
    """
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "send_newsletter.py"),
         "--slug", "some-post", "--send",
         "--confirm", "-XWKGnfiTNyQ2eB2s_4Z7uDYEoGHDVxT"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2, (
        f"expected argparse's own usage failure, got rc={proc.returncode}"
    )
    assert "expected one argument" in proc.stderr, proc.stderr


def test_the_campaign_identity_constants_are_pinned_to_their_literals() -> None:
    """Who gets the review copy, and who gets the send. Both were unpinned.

    Ralph round 6 tier 3 changed REVIEW_ADDRESS, LIST_ID, SENDER_ID, REPLY_TO and
    UNSUBSCRIBE_PAGE_ID one at a time and the suite stayed green through all five.
    Every existing assertion is of the form `payload[...] == sn.<CONST>`, which
    compares the value against itself: both sides move together, so the test proves a
    field was populated and says nothing about what it was populated with.

    REVIEW_ADDRESS is the one that matters most. The operator's requirement is that a
    review copy reaches him BEFORE anything goes to subscribers. A silently retargeted
    review address defeats that requirement completely while every test stays green,
    and the failure would be invisible until a campaign nobody reviewed had already
    gone out. LIST_ID is the same argument pointed at the audience.

    Literals here, deliberately. That is the entire point.
    """
    assert sn.REVIEW_ADDRESS == "hoiboyuk@gmail.com"
    assert sn.LIST_ID == 4
    assert sn.SENDER_ID == 2
    assert sn.REPLY_TO == "hello@hoiboy.uk"
    assert sn.UNSUBSCRIBE_PAGE_ID == "69fde04c25095576dc311f46"
    assert sn.CANONICAL_PREFIX == "https://hoiboy.uk/blogs/"


def test_the_review_copy_goes_to_the_review_address_and_nowhere_else(
    isolated: Path,
) -> None:
    """And the wire agrees with the constant, against a literal.

    Pinning the constant is half the job; this asserts the value that actually
    reaches the sendTest call, so a change that rewired the recipient without
    touching the constant is caught too.
    """
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    test_send = [
        c for c in transport.call_args_list if str(c.args[1]).endswith("/sendTest")
    ][0]
    emails = test_send.kwargs["json"]["emailTo"]

    assert emails == ["hoiboyuk@gmail.com"], (
        f"the review copy must go to the operator's review inbox and only there, "
        f"got {emails}"
    )


def test_build_html_refuses_when_the_renderer_contract_drifts(monkeypatch) -> None:
    """Defence-in-depth, but bindable, so bind it.

    Found by a class sweep after Ralph round 5, not by a reviewer: deleting this
    guard left the suite green. It cannot fire while `values` and PLACEHOLDERS agree,
    which is why an earlier tier reasonably called the mutation equivalent. Shrinking
    PLACEHOLDERS reproduces the drift it guards against, so "unreachable today" and
    "untestable" turn out to be different claims.

    The message assertion is specific on purpose: newsletter_render.render() raises
    its OWN unknown-placeholder error a few lines later, so a bare pytest.raises here
    would pass while proving the wrong guard fired. That exact substitution has caught
    this workstream twice.
    """
    monkeypatch.setattr(sn, "PLACEHOLDERS", frozenset({"FIRSTNAME"}))
    post = {
        "title": "A Title",
        "published": "2026-08-04T09:30:00+00:00",
        "excerpt": "An excerpt.",
        "url": "https://hoiboy.uk/blogs/a-post/",
        "hero": "https://hoiboy.uk/blogs/a-post/hero.jpg",
        "hero_alt": "Alt text.",
    }
    with pytest.raises(sn.NewsletterError, match="renderer contract drifted"):
        sn.build_html(post, "<p>%%FIRSTNAME%%</p>")


def test_prepare_names_a_missing_template_rather_than_rendering_nothing(
    isolated: Path, monkeypatch
) -> None:
    """The template-missing guard, which every test had made unreachable by having one."""
    monkeypatch.setattr(sn, "TEMPLATE", isolated / "no" / "such" / "email.html")
    write_page(isolated, SLUG)
    with mock.patch.object(sn, "_api_call", ok_transport()):
        with pytest.raises(sn.NewsletterError, match="template missing at"):
            sn.prepare(SLUG, sn.STATE_FILE)


def test_a_campaign_create_without_a_usable_id_is_refused(isolated: Path) -> None:
    """A 201 carrying no integer id must not be treated as a created campaign.

    Every fixture returned a real int, so the guard was unreachable in tests and
    deleting it changed nothing. A string id would otherwise be written into the
    state file and later interpolated into the campaign URL, failing much further
    from the cause.
    """
    write_page(isolated, SLUG)
    transport = ok_transport(created_id="42")  # a string, as a flaky provider might send
    with mock.patch.object(sn, "_api_call", transport):
        with pytest.raises(sn.NewsletterError, match="no usable id"):
            sn.prepare(SLUG, sn.STATE_FILE)


def test_human_date_reads_the_way_a_person_writes_a_date() -> None:
    """The one string in the email a subscriber reads that nothing asserted.

    `human_date` feeds POST_DATE into every campaign (send_newsletter.py:562). Ralph
    round 5 tier 2 rewrote its format from "4 August 2026" to "4/08/2026" and the
    whole suite stayed green, byte-identical to baseline: the function had zero test
    references anywhere. Not a weak guard, no guard.

    The no-leading-zero detail is the reason the format is built by hand instead of
    with a single strftime: `%d` renders "04 August 2026", which is not how anyone
    writes it. That is exactly the kind of thing a reformat quietly reintroduces.
    """
    assert sn.human_date("2026-08-04T09:30:00+00:00") == "4 August 2026"
    assert sn.human_date("2026-12-25T00:00:00+00:00") == "25 December 2026"
    # A date-only value is what the frontmatter actually carries most of the time.
    assert sn.human_date("2026-01-09") == "9 January 2026"


def test_an_unparseable_date_is_named_rather_than_rendered() -> None:
    """The error path was untested too, and it fires at --prepare.

    campaign_name calls human_date purely for this rejection
    (send_newsletter.py:537), so that a bad date fails while the operator is still
    reading output, not silently at render time inside a campaign body.
    """
    with pytest.raises(sn.NewsletterError, match="unparseable publication date"):
        sn.human_date("the fourth of August")


def test_the_utm_campaign_actually_varies_with_the_slug() -> None:
    """Charset alone is not the contract.

    The existing test regex-checks the value's characters, which stays green if
    utm_campaign ignores its argument and returns a constant. Every post would then
    collapse into one UTM bucket in Brevo's analytics, silently, with a green suite.
    Ralph round 4 tier 2 mutated exactly that and watched it survive.
    """
    a = sn.utm_campaign("why-bpm-matters")
    b = sn.utm_campaign("how-to-actually-build-communities")

    assert a != b, "a constant here merges every post into one analytics bucket"
    assert "why bpm matters" in a
    assert "how to actually build communities" in b


def test_the_rendered_root_is_hugos_own_output_directory() -> None:
    """D-8's source of truth, pinned to a value instead of to prose.

    AC 2.12's recorded verify was `grep -c 'public/blogs' send_newsletter.py >= 1`.
    Ralph round 3 tier 3 found the single hit is the MODULE DOCSTRING: RENDERED_ROOT
    is a path join, so it structurally cannot contain that literal, and the grep
    would stay green with the constant repointed anywhere.

    Nothing else covered it either. Every other test in this file monkeypatches
    RENDERED_ROOT onto a fixture directory, which is right for isolation and means
    the real value was read by no assertion at all.

    Hence the fresh module load. The autouse fixture at the top of this file patches
    `sn.RENDERED_ROOT` for EVERY test here, so asserting on `sn` would read the
    fixture's tmp_path and fail no matter what the source says. Loading the file
    under its own name gets the constant the script actually runs with. The first
    version of this test did assert on `sn` and went red immediately, which is the
    only reason the fixture's reach was noticed.
    """
    spec = importlib.util.spec_from_file_location("_send_newsletter_unpatched", sn.__file__)
    assert spec is not None and spec.loader is not None
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)

    assert fresh.RENDERED_ROOT == fresh.REPO_ROOT / "public" / "blogs", (
        "the email body must come from Hugo's own rendered output (D-8); repointing "
        "this is how the campaign silently starts sourcing something else"
    )
    assert fresh.RENDERED_ROOT.name == "blogs"
    assert fresh.RENDERED_ROOT.parent.name == "public"


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
    """Set explicitly, not inherited. A grep of the source cannot prove this.

    The name says eight and the loop ran seven until Ralph round 3 tier 3 counted
    them: `unsubscriptionPageId` was the one missing, covered only by its own
    value assertion further down. Both belong. This loop is the presence check
    across the whole branding set named in `campaign_payload`'s docstring, and a
    field can be present here yet carry the wrong value there.
    """
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
        "unsubscriptionPageId",
    ):
        assert field in payload, f"{field} left to a Brevo default"
    assert payload["replyTo"] == sn.REPLY_TO
    assert payload["mirrorActive"] is False
    assert payload["inlineImageActivation"] is False


def test_header_and_footer_are_non_empty_because_brevo_rejects_empty(
    isolated: Path,
) -> None:
    """An empty string is not a quieter value here, it is a 400.

    Measured against the live API with disposable drafts: `"header": ""` returns
    400 missing_parameter "header is missing", and `"footer": ""` returns the
    symmetric "footer is missing". Brevo reads empty as absent. Omitting the key
    is accepted but then the provider default renders, which is the outcome AC 2.13
    exists to prevent. So both carry a real value, and this test stops a future edit
    reintroducing the empty string that cost a live 400 the first time.
    """
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    payload = [
        c for c in transport.call_args_list if c.args[1] == "/v3/emailCampaigns"
    ][0].kwargs["json"]
    for field in ("header", "footer"):
        assert isinstance(payload[field], str)
        assert payload[field] != "", f"{field} empty is rejected 400 by the live API"
    # And neither hands the block back to the provider.
    assert "[DEFAULT_HEADER]" not in payload["header"]
    assert "[DEFAULT_FOOTER]" not in payload["footer"]


def test_the_unsubscribe_page_is_always_set_explicitly(isolated: Path) -> None:
    """Set, not inherited, and shaped the way the API actually validates.

    It happens to be the account default today, which is exactly why it is pinned:
    omitting it means every campaign silently follows whatever that default becomes
    later. Measured against the live API, a well-formed but non-existent id returns
    400 `invalid_parameter` "Unsubscription page id does not exist", so a page deleted
    in the dashboard fails the send loudly rather than reverting to a provider page
    nobody chose.
    """
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    payload = [
        c for c in transport.call_args_list if c.args[1] == "/v3/emailCampaigns"
    ][0].kwargs["json"]
    assert payload["unsubscriptionPageId"] == sn.UNSUBSCRIBE_PAGE_ID
    assert len(sn.UNSUBSCRIBE_PAGE_ID) == 24, "the API documents a 24-character id"
    assert sn.UNSUBSCRIBE_PAGE_ID.isalnum()


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
    assert SLUG in json.loads(sn.STATE_FILE.read_text(encoding="utf-8"))["pending"]

    # The repo-root file may legitimately exist: it is the operator's real state
    # from a real --prepare. So the assertion is that THIS test's slug never
    # reached it, not that the file is absent. An absence check passed for the
    # wrong reason until a real run created that file, which is exactly the kind
    # of environment-dependent assertion that rots into a false green.
    live = REPO_ROOT / ".newsletter-state.json"
    if live.exists():
        assert SLUG not in live.read_text(encoding="utf-8"), "leaked into real state"


def test_send_requires_the_confirm_flag_through_main(
    isolated: Path, capsys: pytest.CaptureFixture
) -> None:
    """`--send` without `--confirm` is refused BY THE FLAG GUARD, not by luck.

    This test used to prove nothing. It never ran `--prepare`, so with the guard at
    `main()` deleted the call fell through to `send(slug, None)`, hit "no prepared
    campaign", and returned the same rc=1 having touched no API. The mutant survived
    the whole suite. Ralph tier 3 caught it by deleting the guard and watching the
    suite stay green.

    Two changes make it discriminate: a campaign IS prepared first, so the
    no-pending-campaign branch cannot be what answers, and the refusal message is
    asserted, so only the flag guard can produce it.
    """
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)

    guard = mock.Mock(side_effect=AssertionError("must not reach the API"))
    with mock.patch.object(sn, "_api_call", guard):
        assert sn.main(["--slug", SLUG, "--send"]) == 1
    guard.assert_not_called()

    err = capsys.readouterr().err
    assert "requires --confirm" in err, (
        f"refused for the wrong reason, so this test cannot see the flag guard: {err!r}"
    )


# --------------------------------------------------------------------------
# Guards that had no killing test until Ralph tier 3 mutated them
#
# Every test below was written because deleting the guard it covers left the whole
# suite green. A guard no test can kill is decoration: it reads as protection, and
# the day someone "simplifies" it nothing objects.
# --------------------------------------------------------------------------


def test_a_campaign_whose_BODY_drifted_after_review_is_refused(isolated: Path) -> None:
    """The body half of the campaign fingerprint, which had no test.

    `content_fingerprint` hashes subject AND html, and there was a drift test for the
    subject only, because the fake transport could not move the body. So half of the
    guard the author added specifically after being bitten was itself unprotected.

    This is the more dangerous half, too: a subject edit is visible in any inbox list,
    whereas a body edit is exactly the change an operator would never notice.
    """
    confirmation = prepare_then_confirmation(isolated, ok_transport())
    drifted = ok_transport(html_drift="<html>not what was reviewed at all</html>")
    with mock.patch.object(sn, "_api_call", drifted):
        with pytest.raises(sn.NewsletterError, match="no longer matches the review copy"):
            sn.send(SLUG, confirmation, sn.STATE_FILE)
    assert not any(
        c.args[1].endswith("/sendNow") for c in drifted.call_args_list
    ), "a body-drifted campaign reached sendNow"


def test_a_state_file_from_a_future_version_is_refused(isolated: Path) -> None:
    """The state-version check, which no test exercised.

    It exists so a state file written by a newer script is not silently
    misinterpreted by an older one. Deleting it changed nothing observable, so it was
    load-bearing only in intent.
    """
    sn.STATE_FILE.write_text(
        json.dumps({"version": 99, "pending": {}, "sent": {}, "audit": []}),
        encoding="utf-8",
    )
    with pytest.raises(sn.NewsletterError, match="version"):
        sn.load_state(sn.STATE_FILE)


def test_the_path_containment_check_holds_when_the_shape_rule_is_bypassed(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second half of the defence-in-depth pair, which was unreachable to test.

    `rendered_path` validates the slug by SHAPE and then re-checks that the resolved
    path is still inside the blogs root. The docstring says "either check alone is
    insufficient", but the shape rule permits only `[a-z0-9-]`, so no input can ever
    reach the containment check in practice, and deleting that check left the suite
    green.

    Rather than delete an honest defence-in-depth layer or leave the claim untested,
    this relaxes the shape rule for the length of the test, which is precisely the
    scenario the second layer exists for: someone widening the first one.
    """
    monkeypatch.setattr(sn, "_SLUG_SHAPE", re.compile(r".+", re.S))
    with pytest.raises(sn.NewsletterError, match="resolves outside"):
        sn.rendered_path("../../etc")


def test_a_non_ascii_confirmation_is_refused_loudly_not_as_a_traceback(
    isolated: Path, capsys: pytest.CaptureFixture
) -> None:
    """A non-ASCII token used to crash the approval gate with no audit record.

    `hmac.compare_digest` RAISES on a non-ASCII str rather than returning False, and
    `main()` catches only `NewsletterError`, so the operator got a raw traceback and
    `_log` never fired. It always failed CLOSED, so nothing could leak; it failed
    silently in the ledger, which is the half that matters when reconstructing who
    tried to send what.

    The guard validates the token's SHAPE rather than catching the TypeError, because
    compare_digest raises that for at least four different reasons (non-ASCII, None,
    int, bytes-vs-str) and a catch would have to guess which. This asserts the
    shape-guard's own message, so it cannot be satisfied by some other refusal.
    """
    confirmation = prepare_then_confirmation(isolated, ok_transport())
    assert confirmation.isascii(), "minted tokens are URL-safe base64"

    guard = mock.Mock(side_effect=AssertionError("must not reach the API"))
    with mock.patch.object(sn, "_api_call", guard):
        assert sn.main(["--slug", SLUG, "--send", "--confirm", "tokèn"]) == 1
    guard.assert_not_called()

    out = capsys.readouterr()
    assert "not the shape this script mints" in out.err, (
        f"refused, but not by the token-shape guard: {out.err!r}"
    )
    # counters() is the module's own purpose-built surface for this ("Read by the
    # tests"), and it beats string-matching the log stream: it survives any change to
    # the line format, and it is the thing that would actually be reconstructed from
    # afterwards. The audit record is the whole point of this test.
    assert sn.counters().get("confirm_rejected") == 1, (
        f"a rejected approval left no audit record: {sn.counters()}"
    )


def test_prepare_actually_CALLS_the_consent_gate(isolated: Path) -> None:
    """The gate is WIRED into --prepare, not merely present in the module.

    Round 2 hardened `assert_is_blog_post` itself and tested it thoroughly, but every
    one of those tests called it directly. Ralph tier 3 then deleted the CALL from
    both `prepare()` and `send()` and watched all 59 tests stay green. A guard nobody
    invokes is not a guard, and testing the function while never testing its wiring is
    the same mistake as a mock that swallows kwargs: the unit looks proven and the
    system is unprotected.

    This drives the real command over a page whose canonical is a services URL, with
    every other field valid so `read_post` succeeds and the consent gate is
    unambiguously what refuses.
    """
    write_page(isolated, SLUG, url="https://hoiboy.uk/hire-hoi/ai-consultancy/")
    transport = mock.Mock(side_effect=AssertionError("must not reach the API"))
    with mock.patch.object(sn, "_api_call", transport):
        with pytest.raises(sn.NewsletterError, match="privacy/index.md:77"):
            sn.prepare(SLUG, sn.STATE_FILE)
    transport.assert_not_called()


def test_send_actually_CALLS_the_consent_gate(isolated: Path) -> None:
    """The same wiring check on the path that actually reaches subscribers.

    `send()` re-reads the post from disk, so a page whose canonical moved out of the
    blogs tree between review and send must be refused there too, not only at prepare.

    The `match=` is load-bearing and was missing on the first attempt. Moving the
    canonical also changes the content fingerprint, so with the consent-gate call
    deleted the fingerprint check raises instead and a bare `pytest.raises` is
    satisfied by the wrong guard. The mutation survived until this asserted the
    consent gate's own message. That is the identical trap Ralph found in round 1,
    walked into again while fixing round 2, and caught only by re-running the
    mutation rather than trusting a green test.
    """
    confirmation = prepare_then_confirmation(isolated, ok_transport())
    # The post's canonical moves out of the blogs tree after review.
    write_page(isolated, SLUG, url="https://hoiboy.uk/hire-hoi/ai-consultancy/")

    transport = ok_transport()
    with mock.patch.object(sn, "_api_call", transport):
        with pytest.raises(sn.NewsletterError, match="privacy/index.md:77"):
            sn.send(SLUG, confirmation, sn.STATE_FILE)
    assert not any(
        c.args[1].endswith("/sendNow") for c in transport.call_args_list
    ), "a non-blog page reached sendNow"


def test_log_redacts_on_its_own_not_via_some_other_layer(
    capsys: pytest.CaptureFixture,
) -> None:
    """`_log` redacts by itself, proven by calling `_log` and nothing else.

    `test_no_recipient_in_logs` drives a whole flow and asserts no address appears in
    the output, but `_expect` runs its own independent `_redact`, so that test passed
    even with redaction removed from `_log`. The two-pass discipline the module claims
    was, in evidence terms, one pass. Ralph tier 3 found it by deleting the `_log`
    half and watching the suite stay green.
    """
    sn._log("probe", to="reader@example.com", nested={"cc": "other@example.org"})
    err = capsys.readouterr().err
    assert "reader@example.com" not in err, f"_log leaked an address: {err!r}"
    assert "other@example.org" not in err, f"_log leaked a nested address: {err!r}"
    assert "probe" in err, "the event itself should still be logged"


def test_a_non_string_confirmation_is_refused_without_a_traceback(
    isolated: Path,
) -> None:
    """The `isinstance` half of the token-shape guard.

    `confirm.isascii()` alone covers a str with an accent but raises `AttributeError`
    on `None`, and `str(confirm).isascii()` would quietly stringify it. Only the
    isinstance check refuses a non-str cleanly, and until now nothing tested it, so
    weakening the guard to the isascii half survived the suite.

    `main()` gates a missing `--confirm`, so this is defence-in-depth for a direct
    caller. That is exactly the situation the containment-check test already covers,
    and it gets the same treatment rather than being waved through as unreachable.
    """
    confirmation = prepare_then_confirmation(isolated, ok_transport())
    assert confirmation  # the real token exists, so we are past the pending check

    transport = ok_transport()
    with mock.patch.object(sn, "_api_call", transport):
        with pytest.raises(sn.NewsletterError, match="not the shape this script mints"):
            sn.send(SLUG, None, sn.STATE_FILE)  # type: ignore[arg-type]
    assert not any(c.args[1].endswith("/sendNow") for c in transport.call_args_list)


@pytest.mark.parametrize(
    "bad",
    [
        "",                                    # empty
        " ",                                   # whitespace only
        "a",                                   # far too short
        "x" * 32,                              # RIGHT LENGTH, wrong value
        "  padded-token  ",                    # whitespace-padded
        "tokèn",                          # non-ASCII, the crash case
        "\n",                                  # newline
    ],
)
def test_the_confirmation_gate_rejects_the_adversarial_token_band(
    isolated: Path, bad: str
) -> None:
    """Near-miss tokens, including one of the exact right length.

    The suite previously tested one wrong token, 11 to 13 characters long against a
    real token of 32, so nothing sat near the boundary. A length-correct wrong value
    is the case a sloppy comparison passes.
    """
    confirmation = prepare_then_confirmation(isolated, ok_transport())
    assert bad != confirmation, "the adversarial band must not contain the real token"

    transport = ok_transport()
    with mock.patch.object(sn, "_api_call", transport):
        with pytest.raises(sn.NewsletterError):
            sn.send(SLUG, bad, sn.STATE_FILE)
    assert not any(c.args[1].endswith("/sendNow") for c in transport.call_args_list)


# --------------------------------------------------------------------------
# The transport itself, and the five _expect ok-tuples (blog-priv#81 class sweep)
#
# WHY THIS SECTION EXISTS. Every test above this line mocks `_api_call`, which is
# the right seam for asserting what would be SENT -- and it means the function that
# actually talks to Brevo was executed by nothing. Measured by mutation: replacing
# the entire body of `_api_call` with `raise AssertionError` left the suite green.
# So the URL, the auth header, the timeout, the content negotiation and every branch
# of the error handling were unpinned, including `return exc.code, body` -> `return
# 200, body`, which turns every 401, 402 and 400 into a success.
#
# The five `_expect` ok-tuples were unpinned for a related reason: `test_402_exits_
# nonzero` proves `_expect` is WIRED, but nothing pinned any tuple's CONTENTS.
# --------------------------------------------------------------------------


class _FakeResponse:
    """The half of http.client.HTTPResponse that _api_call actually uses."""

    def __init__(self, status: int, payload: bytes) -> None:
        self.status = status
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def _urlopen_returning(status: int, payload: bytes) -> tuple[mock.Mock, list]:
    calls: list = []

    def _open(request: object, **kw: object) -> _FakeResponse:
        calls.append((request, kw))
        return _FakeResponse(status, payload)

    return mock.Mock(side_effect=_open), calls


def test_the_request_reaches_brevo_at_the_documented_url_with_the_key(
    isolated: Path,
) -> None:
    """The whole wire format, asserted once, because nothing else executes it.

    Each of these was an independent survivor: the host could be repointed at
    api.sendinblue.com, the api-key header could be blanked, the timeout could be
    dropped (leaving a hand-run send able to hang forever with no output), and the
    content-type could go missing.
    """
    opener, calls = _urlopen_returning(201, b'{"id": 42}')
    with mock.patch("urllib.request.urlopen", opener):
        status, body = sn._api_call(
            "POST", "/v3/emailCampaigns", json={"name": "x"}, brevo_key="a-test-key"
        )

    assert (status, body) == (201, {"id": 42})
    request, kwargs = calls[0]
    assert request.full_url == "https://api.brevo.com/v3/emailCampaigns", (
        "the base URL is the host the campaign API key is transmitted to"
    )
    assert request.get_method() == "POST"
    assert request.get_header("Api-key") == "a-test-key"
    assert request.get_header("Accept") == "application/json"
    assert request.get_header("Content-type") == "application/json"
    assert request.data == b'{"name": "x"}'
    assert kwargs == {"timeout": 30}, (
        "a send with no timeout blocks on the default socket timeout, and an operator "
        "staring at a hung --send cannot tell whether subscribers were reached"
    )


def test_a_get_carries_no_body_and_no_content_type(isolated: Path) -> None:
    """`json=None` is not a style choice: it decides what goes on the wire.

    Defaulting the parameter to `{}` instead makes `json is not None` true, so the
    two GETs -- the campaign read-back and the pre-send re-read, i.e. both halves of
    "what ships is what was approved" -- would carry a `b"{}"` body and a JSON
    content-type they should not have.
    """
    opener, calls = _urlopen_returning(200, b'{"id": 42, "status": "draft"}')
    with mock.patch("urllib.request.urlopen", opener):
        sn._api_call("GET", "/v3/emailCampaigns/42", brevo_key="k")

    request, _ = calls[0]
    assert request.data is None
    assert request.get_header("Content-type") is None


def test_a_204_with_an_empty_body_is_not_a_decode_error(isolated: Path) -> None:
    """The two most important successes -- sendTest and sendNow -- are empty 204s.

    `or "{}"` and the `raw.strip()` ternary are a matched pair guarding exactly this,
    and both were unpinned. Dropping either raises ValueError on the happy path of
    the send itself, immediately AFTER `_log("send_now_start")` has fired: the worst
    possible place to lose the return value.
    """
    opener, _ = _urlopen_returning(204, b"")
    with mock.patch("urllib.request.urlopen", opener):
        assert sn._api_call("POST", "/v3/emailCampaigns/42/sendNow", brevo_key="k") == (
            204,
            {},
        )


def _http_error(code: int, payload: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://api.brevo.com/x", code=code, msg="err",
        hdrs=None, fp=io.BytesIO(payload),  # type: ignore[arg-type]
    )


def test_a_provider_error_keeps_its_own_status(isolated: Path) -> None:
    """`return exc.code, body` -> `return 200, body` survived, and it is the worst
    single-line mutation in the file: pinned at 200, EVERY 4xx and 5xx becomes a
    success. A 401 bad key, a 402 out of credits and a 400 rejected payload would
    all sail through `_expect` and be recorded as sent.

    This also pins that HTTPError is caught HERE rather than by the URLError handler
    below it. HTTPError subclasses URLError, so narrowing the first `except` does not
    make the error escape -- it silently reroutes it into "network failure", which
    reads like a connectivity problem and loses the provider's actual status.
    """
    with mock.patch("urllib.request.urlopen", mock.Mock(
        side_effect=_http_error(402, b'{"code": "not_enough_credits"}')
    )):
        status, body = sn._api_call("POST", "/v3/emailCampaigns", json={}, brevo_key="k")

    assert status == 402, "the provider's status is the whole diagnostic"
    assert body == {"code": "not_enough_credits"}


def test_a_provider_error_body_that_is_not_json_is_kept_as_text(isolated: Path) -> None:
    """A gateway returning an HTML error page is routine, and losing it loses the
    only thing that says what went wrong. Narrowing `except ValueError` to TypeError
    made that page raise out of `_api_call` instead."""
    with mock.patch("urllib.request.urlopen", mock.Mock(
        side_effect=_http_error(502, b"<html><body>Bad Gateway</body></html>")
    )):
        status, body = sn._api_call("GET", "/v3/emailCampaigns/42", brevo_key="k")

    assert status == 502
    assert "Bad Gateway" in body["raw"]


def test_a_provider_error_body_that_is_not_utf8_still_produces_a_diagnostic(
    isolated: Path,
) -> None:
    """`errors="replace"` is there so that FORMATTING a diagnostic can never itself
    throw. Removed, a non-UTF-8 error body raises UnicodeDecodeError from inside the
    exception handler, replacing the provider's message with a decode traceback."""
    with mock.patch("urllib.request.urlopen", mock.Mock(
        side_effect=_http_error(500, b"\xff\xfe not utf-8 \x80")
    )):
        status, body = sn._api_call("GET", "/v3/emailCampaigns/42", brevo_key="k")

    assert status == 500
    assert "not utf-8" in body["raw"]


def test_an_empty_provider_error_body_does_not_itself_raise(isolated: Path) -> None:
    """4xx with an empty body is what proxies and gateways return."""
    with mock.patch("urllib.request.urlopen", mock.Mock(side_effect=_http_error(400, b""))):
        assert sn._api_call("POST", "/v3/emailCampaigns", json={}, brevo_key="k") == (400, {})


def test_a_network_failure_becomes_a_named_newsletter_error(isolated: Path) -> None:
    """DNS failure, refused connection or a TLS error. Left uncaught it escapes
    main()'s `except NewsletterError` as a raw URLError: traceback, and no
    `_log("fatal")` record of the attempt."""
    with mock.patch("urllib.request.urlopen", mock.Mock(
        side_effect=urllib.error.URLError("nodename nor servname provided")
    )):
        with pytest.raises(sn.NewsletterError, match="network failure calling POST /v3/x"):
            sn._api_call("POST", "/v3/x", json={}, brevo_key="k")


# ---- the five _expect ok-tuples, each driven one status outside its set ----


def test_a_create_that_did_not_create_is_refused(isolated: Path) -> None:
    """201 means created; 200 does not. Admitting 200 lets a non-creating response
    through the status gate, and the `isinstance(campaign_id, int)` check one line
    later only catches it when the body ALSO lacks an id."""
    write_page(isolated, SLUG)
    transport = transport_answering({"create": (200, {"id": 42})})
    with mock.patch.object(sn, "_api_call", transport):
        with pytest.raises(sn.NewsletterError, match="campaign create failed with HTTP 200"):
            sn.prepare(SLUG, sn.STATE_FILE)

    assert not any(
        endpoint_of(*c.args[:2]) == "send_test" for c in transport.call_args_list
    ), "nothing may be sent off the back of a campaign that was never created"


def test_a_review_copy_the_provider_refused_is_not_reported_as_delivered(
    isolated: Path,
) -> None:
    """The review copy IS the operator gate.

    If sendTest is refused but the status is accepted, --prepare still reads the
    campaign back, still mints the confirmation token, still writes the pending
    state and still prints "A review copy has been sent to the review address. Read
    it." The operator then confirms a copy he never received, which walks straight
    around the one instruction the two-invocation design depends on.
    """
    write_page(isolated, SLUG)
    transport = transport_answering({"send_test": (400, {"message": "rejected"})})
    with mock.patch.object(sn, "_api_call", transport):
        with pytest.raises(sn.NewsletterError, match="send test failed with HTTP 400"):
            sn.prepare(SLUG, sn.STATE_FILE)

    pending = (
        json.loads(sn.STATE_FILE.read_text(encoding="utf-8"))["pending"]
        if sn.STATE_FILE.is_file()
        else {}
    )
    assert SLUG not in pending, (
        "no confirmation token may exist for a review copy that never landed"
    )


def test_a_read_back_that_404s_is_refused_rather_than_fingerprinted(
    isolated: Path,
) -> None:
    """On a 404 the body carries no htmlContent and no subject, so the fingerprint
    becomes the digest of two empty strings and is stored as "what the operator
    reviewed". The send-side comparison would then be measuring against nothing."""
    write_page(isolated, SLUG)
    transport = transport_answering({"campaign_get": (404, {"message": "not found"})})
    with mock.patch.object(sn, "_api_call", transport):
        with pytest.raises(
            sn.NewsletterError, match="campaign read-back failed with HTTP 404"
        ):
            sn.prepare(SLUG, sn.STATE_FILE)


def test_a_pre_send_re_read_that_404s_is_refused(isolated: Path) -> None:
    """The re-read is the guard added after a dashboard edit slipped past the post
    fingerprint. A 404 admitted here happens to fail closed today, but only by
    accident of the `status != "draft"` check below it raising on None."""
    confirmation = prepare_then_confirmation(isolated, ok_transport())
    transport = transport_answering({"campaign_get": (404, {"message": "gone"})})
    with mock.patch.object(sn, "_api_call", transport):
        with pytest.raises(
            sn.NewsletterError, match="campaign re-read failed with HTTP 404"
        ):
            sn.send(SLUG, confirmation, sn.STATE_FILE)

    assert not any(
        endpoint_of(*c.args[:2]) == "send_now" for c in transport.call_args_list
    )


def test_a_refused_send_is_never_recorded_as_sent(isolated: Path) -> None:
    """The single highest-blast-radius survivor in the sweep.

    Widening the sendNow ok-tuple from `(204,)` to `(204, 400)` was MEASURED end to
    end: the identical rejected send printed "Campaign 42 sent to list 4.", returned
    0, wrote `state["sent"]` and deleted `state["pending"]`. So the operator is told
    the newsletter went out when nothing did, AND the double-send guard then refuses
    every retry forever -- the post can never be sent at all without hand-editing the
    state file.

    Asserted on all four observable consequences, not just the exception, because it
    is the state write that makes this unrecoverable rather than merely wrong.
    """
    confirmation = prepare_then_confirmation(isolated, ok_transport())
    transport = transport_answering({"send_now": (400, {"message": "rejected"})})
    with mock.patch.object(sn, "_api_call", transport):
        with pytest.raises(sn.NewsletterError, match="send now failed with HTTP 400"):
            sn.send(SLUG, confirmation, sn.STATE_FILE)

    state = json.loads(sn.STATE_FILE.read_text(encoding="utf-8"))
    assert SLUG not in state["sent"], "a refused send must not be recorded as sent"
    assert SLUG in state["pending"], "the retry must still be possible"
    assert sn.counters().get("api_error") == 1, (
        "_expect's structured log line is the only record that the provider refused; "
        "deleting it leaves the failure invisible to the audit trail (AP #12)"
    )


def test_every_call_the_two_commands_make_is_the_endpoint_it_claims(
    isolated: Path,
) -> None:
    """Method AND path, in order, compared by equality rather than by suffix.

    Every existing assertion about sendNow used `.endswith("/sendNow")`, which is
    satisfied by `DELETE /v3/emailCampaigns/sendNow` -- wrong verb, campaign id gone.
    sendNow is the one call that reaches real subscribers and the module treats it as
    irreversible, so its address is worth pinning exactly.
    """
    prepare_transport = ok_transport()
    confirmation = prepare_then_confirmation(isolated, prepare_transport)
    assert [
        endpoint_of(*c.args[:2]) for c in prepare_transport.call_args_list
    ] == ["create", "send_test", "campaign_get"]

    send_transport = ok_transport()
    with mock.patch.object(sn, "_api_call", send_transport):
        assert sn.send(SLUG, confirmation, sn.STATE_FILE) == 0
    assert [
        endpoint_of(*c.args[:2]) for c in send_transport.call_args_list
    ] == ["campaign_get", "send_now"]


# --------------------------------------------------------------------------
# What each value in the payload map actually IS (blog-priv#81 class sweep)
#
# `build_html`'s eight-entry value map and `campaign_payload`'s thirteen fields
# were checked for PRESENCE and almost never for CONTENT, so five of the six
# entries could be fed the wrong post field with the suite green. The recurring
# shape: an assertion that a value is somewhere in the 5KB of htmlContent, which
# a substring of the wrong field satisfies.
# --------------------------------------------------------------------------


def created_payload(transport: mock.Mock) -> dict:
    return [
        c for c in transport.call_args_list if endpoint_of(*c.args[:2]) == "create"
    ][0].kwargs["json"]


def test_the_email_body_carries_the_post_title(isolated: Path) -> None:
    """Nothing asserted the title reached the BODY, only the subject line.

    Feeding POST_TITLE the excerpt instead survived: `payload["subject"] == TITLE`
    still held (a different field), and `EXCERPT in htmlContent` still held (now
    twice over). The message would contradict itself, with the subject saying one
    thing and the largest element in the email saying another.
    """
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    body = created_payload(transport)["htmlContent"]
    assert TITLE in body, "the post title is the 24px headline, not just the subject"
    assert body.count(TITLE) >= 2, (
        "the title fills both POST_TITLE and HERO_ALT, so a single occurrence means "
        "one of them is being fed something else"
    )


def test_the_email_body_carries_a_human_date_not_a_machine_one(isolated: Path) -> None:
    """The exact tested-the-helper-not-the-wiring shape this workstream keeps hitting.

    Ralph round 5 found `human_date` had no test at all and added two, both of which
    still pass when the CALL is removed and POST_DATE is fed the raw ISO stamp
    instead. The helper is proved; its use was not. A reader would see
    "2026-06-04T12:00:00+01:00" where the design says "4 June 2026".
    """
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    body = created_payload(transport)["htmlContent"]
    assert sn.human_date(PUBLISHED) in body
    assert PUBLISHED not in body, "the raw ISO timestamp is not reader-facing copy"


def test_every_link_to_the_post_is_the_canonical_url_exactly(isolated: Path) -> None:
    """Why an `in` check could not catch POST_URL being fed the hero image.

    The hero is `https://hoiboy.uk/blogs/<slug>/hero_hu_deadbeef.jpg`, which CONTAINS
    the canonical `https://hoiboy.uk/blogs/<slug>/` as a prefix. So the existing
    membership assertion stayed green while every link in the email pointed at a
    .jpg and the reader had no way to the post at all.

    Counted on the exact href, and pinned at three, because the template carries
    three (hero image, CTA button, plain-text fallback) and repointing any ONE of
    them leaves the other two matching.
    """
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    body = created_payload(transport)["htmlContent"]
    assert body.count(f'href="https://hoiboy.uk/blogs/{SLUG}/"') == 3


def test_the_campaign_name_key_is_the_one_brevo_reads(isolated: Path) -> None:
    """`campaign_name` is thoroughly tested as a FUNCTION and its result reached
    no asserted key, so `"name"` could be renamed to `"campaignName"` or dropped
    entirely with the suite green. It is required by the create call, so the real
    consequence is a 400 the tests cannot see."""
    transport = ok_transport()
    prepare_then_confirmation(isolated, transport)
    assert created_payload(transport)["name"] == f"blog-{SLUG}-2026-06-04"


def test_the_inbox_preview_line_is_truncated_where_the_code_says(
    isolated: Path,
) -> None:
    """The cap was unobservable because the fixture made it unreachable.

    Module EXCERPT is 68 characters, so `[:150]` was the identity on every existing
    test and both directions of the bound survived. It is not theoretical: measured
    on the real corpus, 39 of 97 post descriptions run past 150 characters, so this
    truncation is live for 40% of what will actually be sent. previewText is the
    line every mail client renders next to the subject.
    """
    long_excerpt = "Ten chars." * 30  # 300 characters
    assert len(long_excerpt) == 300
    write_page(isolated, "long-excerpt-post", excerpt=long_excerpt)

    transport = ok_transport()
    with mock.patch.object(sn, "_api_call", transport):
        assert sn.prepare("long-excerpt-post", sn.STATE_FILE) == 0

    preview_text = created_payload(transport)["previewText"]
    assert len(preview_text) == 150
    assert preview_text == long_excerpt[:150]


# --------------------------------------------------------------------------
# The approval gate itself (blog-priv#81 class sweep)
#
# The confirmation token is the only thing standing between a draft and the
# subscriber list, and three separate properties of it were unpinned: how much
# entropy it is drawn with, how strictly it is compared, and whether the operator
# is actually handed it.
# --------------------------------------------------------------------------


def test_the_confirmation_token_is_drawn_with_the_documented_entropy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`token_urlsafe(24)` -> `token_urlsafe(1)` survived the whole suite.

    Nothing observed the draw size. `test_a_confirmation_token_never_starts_with_a
    _hyphen` monkeypatches `secrets.token_urlsafe` with `lambda n: next(draws)`,
    which DISCARDS its argument, so the byte count is invisible to the one test that
    looks closest at this function. A 1-byte draw is a 2-character token with 256
    possible values, guarding the send to a real subscriber list.

    Both halves are asserted: the argument that goes in, and the shape that comes
    out, so replacing the call with a short constant is caught too.
    """
    seen: list[int] = []
    real = sn.secrets.token_urlsafe

    def spy(n: int) -> str:
        seen.append(n)
        return real(n)

    monkeypatch.setattr(sn.secrets, "token_urlsafe", spy)
    minted = sn.mint_confirmation()

    assert seen and set(seen) == {24}, (
        f"every draw must ask for 24 bytes, saw {seen}"
    )
    assert len(minted) >= 32, (
        "24 bytes base64url-encode to 32 characters; anything shorter means the "
        "draw size was reduced somewhere this spy cannot see"
    )


def test_a_token_that_only_shares_a_prefix_is_refused(isolated: Path) -> None:
    """Weakening the comparison to `[:4]` survived, including the adversarial band.

    That band ('', ' ', 'a', 'x'*32, a padded token, a non-ASCII one, '\\n') was
    written to sit ON the boundary and still could not see a prefix comparison,
    because none of its entries happens to share the real token's first four
    characters. This one is derived FROM the real token, so it always does.
    """
    confirmation = prepare_then_confirmation(isolated, ok_transport())
    near_miss = confirmation[:4] + "x" * (len(confirmation) - 4)
    assert near_miss != confirmation
    assert near_miss[:4] == confirmation[:4]

    transport = ok_transport()
    with mock.patch.object(sn, "_api_call", transport):
        with pytest.raises(sn.NewsletterError, match="does not match"):
            sn.send(SLUG, near_miss, sn.STATE_FILE)
    assert not any(endpoint_of(*c.args[:2]) == "send_now" for c in transport.call_args_list)


def test_the_token_comparison_is_case_sensitive(isolated: Path) -> None:
    """`.lower()` on both sides also survived. base64url is a case-SIGNIFICANT
    alphabet, so folding case throws away roughly a bit per alphabetic character
    and makes a transcription error read as a match."""
    confirmation = prepare_then_confirmation(isolated, ok_transport())
    swapped = confirmation.swapcase()
    if swapped == confirmation:  # pragma: no cover - a token of pure digits
        pytest.skip("this draw carried no cased characters")

    transport = ok_transport()
    with mock.patch.object(sn, "_api_call", transport):
        with pytest.raises(sn.NewsletterError, match="does not match"):
            sn.send(SLUG, swapped, sn.STATE_FILE)
    assert not any(endpoint_of(*c.args[:2]) == "send_now" for c in transport.call_args_list)


def test_prepare_hands_the_operator_the_command_it_must_run(
    isolated: Path, capsys: pytest.CaptureFixture
) -> None:
    """The two-invocation design depends entirely on the token being PRINTED.

    Every test reads the token out of the state FILE, never out of stdout, so
    replacing the interpolated value with a literal `--confirm TOKEN` survived. The
    operator would be handed an instruction that cannot work, on the one path that
    must work when it matters, and the only way to recover would be to open a
    gitignored JSON file nobody told him about.
    """
    write_page(isolated, SLUG)
    with mock.patch.object(sn, "_api_call", ok_transport()):
        assert sn.prepare(SLUG, sn.STATE_FILE) == 0

    confirmation = json.loads(sn.STATE_FILE.read_text(encoding="utf-8"))[
        "pending"
    ][SLUG]["confirmation"]
    out = capsys.readouterr().out
    assert f"--slug {SLUG} --send --confirm {confirmation}" in out, (
        "the printed command must be runnable verbatim, token included"
    )


def test_a_template_that_does_not_render_is_a_diagnostic_not_a_traceback(
    isolated: Path, capsys: pytest.CaptureFixture
) -> None:
    """A shipped defect, not an evidence gap.

    `PlaceholderError` and `NewsletterError` are SIBLINGS -- both derive from
    RuntimeError, neither from the other -- so all three of the renderer's refusals
    escaped main()'s `except NewsletterError` untouched. Reproduced before fixing:
    adding a %%FIELD%% to the template and running --prepare gave a raw traceback
    instead of `error: ...`, and `_log("fatal")` never ran, so the refusal left NO
    audit line at all. Failing closed but silently in the ledger is the half that
    matters afterwards, and it is the same shape as the non-ASCII token bug Ralph
    round 2 found.

    Driven through main(), because main() is what the operator runs and is the only
    path that writes the fatal line.
    """
    write_page(isolated, SLUG)
    template = isolated.parent.parent / "email.html"
    template.write_text("<p>%%POST_TITLE%%</p><p>%%NOT_IN_THE_CONTRACT%%</p>", encoding="utf-8")

    with mock.patch.object(sn, "TEMPLATE", template):
        with mock.patch.object(sn, "_api_call", ok_transport()) as transport:
            assert sn.main(["--slug", SLUG, "--prepare"]) == 1

    err = capsys.readouterr().err
    assert "error: the email template did not render" in err, (
        "the operator must get a sentence, not a stack trace"
    )
    assert "NOT_IN_THE_CONTRACT" in err, "and it must name the offending token"
    assert sn.counters().get("fatal") == 1, (
        "every refusal writes one fatal log line; without it the attempt is invisible "
        "to the audit trail (AP #12)"
    )
    assert not transport.call_args_list, "nothing may be created from a template that failed"


# --------------------------------------------------------------------------
# Reading the post, and the two guards on the way in (blog-priv#81 class sweep)
#
# `read_post` and its extractor are where operator input and Hugo's output meet,
# and almost every structural decision in them was unpinned: which h1 counts,
# which <link> supplies the canonical, whether entities survive, and whether a
# missing field produces a named error or a bare assert.
# --------------------------------------------------------------------------


PAGE_WITH_MAIN_HEADING = """<!doctype html><html><head>
<meta name="description" content="{excerpt}">
<meta property="article:published_time" content="{published}">
<meta property="og:image" content="{hero}">
<meta property="og:image:alt" content="{hero_alt}">
<link rel="canonical" href="{url}">
</head><body>
<main>
  <h1>Section heading that is not the post</h1>
  <article><h1>{title}</h1><p>Body.</p></article>
</main>
</body></html>
"""


def test_the_title_comes_from_inside_the_article_not_merely_inside_main(
    isolated: Path,
) -> None:
    """The scope is `<article>`, and widening it by one element is silent.

    The existing masthead fixture cannot see this: it puts the branded h1 in an
    <aside> OUTSIDE <main>, so scoping to `main` instead of `article` still reads
    the right heading. A page with a section heading inside <main> and the post
    title inside <article> distinguishes them, and that shape is ordinary.
    """
    path = isolated / "scoped" / "index.html"
    path.parent.mkdir(parents=True)
    path.write_text(
        PAGE_WITH_MAIN_HEADING.format(
            title=TITLE, excerpt=EXCERPT, published=PUBLISHED,
            url="https://hoiboy.uk/blogs/scoped/",
            hero="https://hoiboy.uk/blogs/scoped/hero_hu_deadbeef.jpg", hero_alt=TITLE,
        ),
        encoding="utf-8",
    )
    assert sn.read_post("scoped")["title"] == TITLE


def test_only_the_first_heading_in_the_article_becomes_the_subject(
    isolated: Path,
) -> None:
    """Dropping `self.title is None` is worse than last-wins.

    `_title_parts` is never reset between headings, so the subject line becomes the
    CONCATENATION of every h1 inside <article>. The class docstring documents the
    sibling scoping bug and the first-wins half beside it was pinned by nothing.
    """
    page = PAGE.format(
        title=TITLE, excerpt=EXCERPT, published=PUBLISHED,
        url=f"https://hoiboy.uk/blogs/{SLUG}/",
        hero=f"https://hoiboy.uk/blogs/{SLUG}/hero_hu_deadbeef.jpg", hero_alt=TITLE,
    ).replace("</article>", "<h1>A Second Heading</h1></article>")
    path = isolated / SLUG / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")

    title = sn.read_post(SLUG)["title"]
    assert title == TITLE
    assert "A Second Heading" not in title


def test_an_ampersand_in_the_title_survives_into_the_subject(isolated: Path) -> None:
    """`convert_charrefs=False` drops the character entirely, it does not escape it.

    With conversion off, HTMLParser routes entities to handle_entityref /
    handle_charref, and _PostExtractor implements neither -- so the character is
    silently DISCARDED. Hugo escapes `&` in .Title as `&amp;`, so the first post
    with an ampersand in its title would have gone out as "Tea  Cake".
    """
    write_page(isolated, SLUG, title="Tea &amp; Cake")
    assert sn.read_post(SLUG)["title"] == "Tea & Cake"


def test_the_canonical_is_the_canonical_link_not_the_first_link(
    isolated: Path,
) -> None:
    """`post["url"]` is both the reader's destination and the input to the consent
    gate, so which <link> supplies it is a correctness question, not a parsing
    detail. Dropping the `rel == "canonical"` test leaves it depending on the
    stylesheet happening to come second in head.html."""
    page = PAGE.format(
        title=TITLE, excerpt=EXCERPT, published=PUBLISHED,
        url=f"https://hoiboy.uk/blogs/{SLUG}/",
        hero=f"https://hoiboy.uk/blogs/{SLUG}/hero_hu_deadbeef.jpg", hero_alt=TITLE,
    ).replace("<link rel=", '<link rel="stylesheet" href="/css/main.css">\n<link rel=', 1)
    path = isolated / SLUG / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")

    assert sn.read_post(SLUG)["url"] == f"https://hoiboy.uk/blogs/{SLUG}/"


@pytest.mark.parametrize(
    "field,named",
    [
        ("excerpt", "excerpt"),
        ("hero_alt", "hero alt (og:image:alt)"),
    ],
)
def test_a_missing_field_is_named_rather_than_asserted(
    isolated: Path, field: str, named: str
) -> None:
    """Dropping an entry from the `missing` list does not remove the check, it
    DOWNGRADES it: execution falls through to the bare `assert` two lines below.
    An AssertionError is not a NewsletterError, so main() does not catch it --
    traceback, no fatal log, no audit record -- and under `python -O` the assert
    vanishes entirely and a half-built email is constructed instead.
    """
    write_page(isolated, SLUG, **{field: ""})
    with pytest.raises(sn.NewsletterError, match=re.escape(named)):
        sn.read_post(SLUG)


@pytest.mark.parametrize(
    "url,why",
    [
        ("https://hoiboy.uk/blogs/..", "a bare .. normalises to the site root"),
        ("https://hoiboy.uk/blogs/../hire-hoi/", "the traversal the guard was added for"),
        ("https://hoiboy.uk/blogs//", "an empty path segment is still the index"),
        ("https://hoiboy.uk/blogs/", "the index itself"),
    ],
)
def test_the_consent_gate_refuses_every_url_that_is_not_a_post(url: str, why: str) -> None:
    """Two guards, each narrowable in a way the single tested URL cannot see.

    `".." in rest` -> `"../" in rest` still refuses `/blogs/../hire-hoi/`, which was
    the only traversal under test, while newly ACCEPTING `/blogs/..` -- a canonical
    that normalises to the site root, i.e. squarely outside the blogs tree. And
    `rest.strip("/")` -> `rest.strip()` still refuses `/blogs/` while accepting
    `/blogs//`, because a lone slash is truthy once you stop stripping slashes.
    """
    with pytest.raises(sn.NewsletterError, match="refusing to send"):
        sn.assert_is_blog_post({"url": url})


@pytest.mark.parametrize(
    "slug", ["-leading", "trailing-", "double--hyphen", "----", "Upper", "has space"]
)
def test_a_malformed_slug_is_refused_by_the_shape_rule(isolated: Path, slug: str) -> None:
    """Loosening `[a-z0-9]+(?:-[a-z0-9]+)*` to `[a-z0-9-]+` accepts all four hyphen
    shapes, and swapping `fullmatch` for `match` accepts anything with a valid
    PREFIX. Both survived: the five hostile slugs already tested are refused by the
    containment check further down, so the shape rule itself was never the thing
    being proved."""
    with pytest.raises(sn.NewsletterError, match="not a post slug"):
        sn.rendered_path(slug)


def test_a_slug_with_a_valid_prefix_is_refused_by_the_shape_rule(
    isolated: Path,
) -> None:
    """`fullmatch` -> `match` specifically. `abc$(whoami)` has a matching prefix, so
    `match` accepts it and execution reaches the containment check, which passes
    because the path stays under the blogs root. The run then fails with "no
    rendered page", a message that sends the operator looking for a build problem
    rather than at the slug he typed."""
    with pytest.raises(sn.NewsletterError, match="not a post slug"):
        sn.rendered_path("abc$(whoami)")


def test_redaction_covers_the_whole_local_part(isolated: Path) -> None:
    """The redaction tests assert the WHOLE address is absent, which a partially
    redacted address satisfies. Narrowing the local-part class to stop at a dot
    logs `a.subscriber@example.com` as `a.[email-redacted]`, leaking the prefix,
    with both existing assertions still green. Asserted on equality instead."""
    assert sn._redact("a.subscriber@example.com") == "[email-redacted]"
    assert sn._redact("contact me at first.last@example.org please") == (
        "contact me at [email-redacted] please"
    )


def test_nothing_the_sender_reads_relies_on_the_locale_encoding(
    isolated: Path, tmp_path: Path
) -> None:
    """Four separate `encoding="utf-8"` arguments, none of them pinned.

    They are not decoration. MEASURED: all 97 rendered pages under public/blogs/
    contain non-ASCII bytes, so an implicit decode is load-bearing for every single
    post rather than for an edge case, and the state file inherits any non-ASCII
    slug or campaign name written into its audit trail.

    Driven under `-X warn_default_encoding`, which is CPython's own detector for
    exactly this, promoted to an error. Patching `locale.getpreferredencoding` was
    tried first and does nothing: TextIOWrapper resolves the encoding in C and
    never consults the Python-level attribute.
    """
    write_page(isolated, SLUG, title="Café Society")

    driver = tmp_path / "encoding_driver.py"
    driver.write_text(
        "import json, pathlib, sys\n"
        f"sys.path.insert(0, {str(REPO_ROOT / 'scripts')!r})\n"
        "from unittest import mock\n"
        "import send_newsletter as sn\n"
        f"sn.RENDERED_ROOT = pathlib.Path({str(isolated)!r})\n"
        f"sn.STATE_FILE = pathlib.Path({str(tmp_path / 'state.json')!r})\n"
        "store = {}\n"
        "def fake(method, path, **kw):\n"
        "    if path == '/v3/emailCampaigns' and method == 'POST':\n"
        "        store['c'] = dict(kw['json'])\n"
        "        return 201, {'id': 42}\n"
        "    if method == 'GET':\n"
        "        c = store.get('c', {})\n"
        "        return 200, {'id': 42, 'status': 'draft',\n"
        "                     'htmlContent': c.get('htmlContent', ''),\n"
        "                     'subject': c.get('subject', '')}\n"
        "    return 204, {}\n"
        "with mock.patch.object(sn, '_api_call', mock.Mock(side_effect=fake)):\n"
        f"    assert sn.prepare({SLUG!r}, sn.STATE_FILE) == 0\n"
        "    state = json.loads(sn.STATE_FILE.read_text(encoding='utf-8'))\n"
        # `minted`, not the obvious name: check-public-repo-secrets.py's generic
        # rule fires on any assignment whose left-hand side is named after a
        # credential, and it blocked this commit on this very line.
        f"    minted = state['pending'][{SLUG!r}]['confirmation']\n"
        f"    assert sn.send({SLUG!r}, minted, sn.STATE_FILE) == 0\n"
        "print('OK')\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, "-X", "warn_default_encoding", "-W", "error::EncodingWarning",
         str(driver)],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", sn.API_KEY_ENV: "test-key-not-a-real-credential"},
    )
    assert proc.returncode == 0, (
        "a read without an explicit encoding reached production code:\n" + proc.stderr
    )
    assert "EncodingWarning" not in proc.stderr
