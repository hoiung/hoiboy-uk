#!/usr/bin/env python3
"""Unit tests for scripts/newsletter_render.py (blog-priv#81 Phase 1).

The substitution is the seam between what the repo holds and what a subscriber
receives, so the tests that matter here are the refusals. A renderer that quietly
tolerates a mismatch sends a half-built email, and the first person to notice is
the reader.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import newsletter_render as nr  # noqa: E402

FULL = {k: f"<{k}>" for k in nr.PLACEHOLDERS}


def test_preview_reports_a_missing_template_instead_of_writing_a_blank_png(
    tmp_path, monkeypatch, capsys
):
    """`preview` was driven by no test at all.

    Found by a class sweep after Ralph round 5: renaming the function out from under
    its own CLI left the whole suite green. It is the operator's only look at the
    email before a campaign exists, so a preview that fails quietly is worse than one
    that fails loudly.

    The rendering path itself needs Chromium and is exercised by the pre-publish lane,
    not here. Its two refusals are pure logic and belong in this tier.
    """
    monkeypatch.setattr(nr, "TEMPLATE", tmp_path / "absent" / "email.html")
    out = tmp_path / "preview.png"

    rc = nr.preview(out)

    assert rc == 2, "a missing template must be a non-zero exit, not a silent success"
    assert not out.exists(), "nothing should be written when there is nothing to render"
    # Assert WHICH refusal fired. preview() checks playwright BEFORE the template and
    # returns 2 from that branch too, so on a machine without playwright this test
    # would pass having never reached the guard it is named for. That substitution
    # (right exit code, wrong guard) is the specific trap this workstream has hit
    # twice, so the message is the assertion and the return code is the corroboration.
    assert "template not found" in capsys.readouterr().err


def test_the_shipped_template_renders_with_preview_values():
    """If this fails, the template and the placeholder contract have diverged."""
    assert nr.TEMPLATE.is_file(), f"template missing: {nr.TEMPLATE}"
    out = nr.render(nr.TEMPLATE.read_text(encoding="utf-8"), nr.PREVIEW_VALUES)
    assert nr.tokens_in(out) == set(), "no placeholder may survive into a sent email"
    assert nr.PREVIEW_VALUES["POST_TITLE"] in out


def test_comments_never_reach_the_reader():
    """The template's engineering notes and iamhoi markers are repo-only.

    Sent as-is they travel to every subscriber inside the message source, and the
    markers in particular would be meaningless there.
    """
    out = nr.render(nr.TEMPLATE.read_text(encoding="utf-8"), nr.PREVIEW_VALUES)
    assert "<!--" not in out and "-->" not in out
    assert "iamhoi" not in out
    assert "Word engine" not in out, "the engineering notes must not ship"


def test_a_token_only_mentioned_in_a_comment_is_not_a_placeholder():
    """Regression for the exact failure that produced strip_comments().

    The template's own notes quote the placeholder syntax to explain it. A
    comment-blind renderer reads that prose as a real placeholder and refuses.
    """
    text = "<!-- placeholders look like %%TOKEN%% -->\n<p>%%POST_TITLE%%</p>"
    assert nr.render(text, {"POST_TITLE": "hello"}) == "\n<p>hello</p>"


def test_unknown_placeholder_in_template_is_refused():
    """Each of the three refusals is pinned to its OWN message, not just to the
    offender's name.

    Every value interpolates that name, so a test asserting only "NOT_A_REAL_ONE
    appears" passes when a DIFFERENT guard answers. Measured: deleting this guard
    entirely left the suite green, because execution then fell through to the
    missing-value guard, which named the same token in a different sentence.
    """
    with pytest.raises(nr.PlaceholderError) as exc:
        nr.render("<p>%%NOT_A_REAL_ONE%%</p>", FULL)
    assert "NOT_A_REAL_ONE" in str(exc.value), "the message must name the offender"
    assert "not in the contract" in str(exc.value), (
        "this guard's own wording, so a sibling guard answering here is a failure"
    )


def test_unknown_key_from_caller_is_refused():
    """A value for a placeholder the template dropped would vanish silently."""
    with pytest.raises(nr.PlaceholderError) as exc:
        nr.render("<p>%%POST_TITLE%%</p>", {"POST_TITLE": "x", "STALE_KEY": "y"})
    assert "STALE_KEY" in str(exc.value)
    assert "caller supplied value" in str(exc.value)


def test_missing_value_is_refused_rather_than_left_raw():
    with pytest.raises(nr.PlaceholderError) as exc:
        nr.render("<p>%%POST_TITLE%% %%POST_URL%%</p>", {"POST_TITLE": "x"})
    assert "POST_URL" in str(exc.value)
    assert "no value supplied" in str(exc.value)


def test_substitution_is_not_recursive():
    """A value that itself looks like a token must not be re-expanded."""
    out = nr.render("<p>%%POST_TITLE%%</p>", {"POST_TITLE": "%%POST_URL%%"})
    assert out == "<p>%%POST_URL%%</p>", (
        "a value is data, not another template; re-expanding it would let post "
        "content reach into the placeholder contract"
    )


def test_substitution_is_not_recursive_in_the_shape_the_sender_actually_uses():
    """The sibling above cannot see a recursive renderer, which is why this exists.

    It supplies ONE value, so a re-expanding pass finds no value for POST_URL and
    leaves the literal alone: the mutant and the correct code agree. But
    `build_html` always supplies all eight, and in THAT configuration recursion
    really does expand -- a post whose title contains %%POST_URL%% would have the
    reader's own link substituted into the headline.

    Measured: making the substitution recursive survived the entire suite.
    """
    values = dict(FULL, POST_TITLE="%%POST_URL%%")
    out = nr.render("<p>%%POST_TITLE%%</p>", values)
    assert out == "<p>%%POST_URL%%</p>", (
        "with every value supplied, a recursive pass would substitute POST_URL's "
        "value here instead of leaving the author's literal text"
    )


def test_a_token_assembled_from_two_values_is_refused():
    """The defence-in-depth block at the end of render(), driven for real.

    Both its `if` statements could be disabled with the suite green, because no
    test ever produced a survivor the three guards above had not already caught.
    One is reachable: substitution is a single pass over the template, so two
    adjacent placeholders whose values are fragments can CONCATENATE into a token
    that exists in neither value. `%%HERO` + `_ALT%%` is `%%HERO_ALT%%`, and that
    is a placeholder-shaped string arriving from nowhere the guards inspected.

    Exactly what the block is for, and until now it had never fired.
    """
    values = dict(FULL, POST_TITLE="%%HERO", POST_URL="_ALT%%")
    with pytest.raises(nr.PlaceholderError) as exc:
        nr.render("<p>%%POST_TITLE%%%%POST_URL%%</p>", values)
    assert "came from no value" in str(exc.value)
    assert "HERO_ALT" in str(exc.value)


def test_a_token_inside_a_single_value_is_left_alone():
    """The other direction of the same block, and the one a last-wins bug breaks.

    `from_values |= tokens_in(v)` accumulates across every value. Changed to `=`
    (last wins) it holds only the final value's tokens, so a legitimate token-shaped
    string in an EARLIER value becomes "unexplained" and render() raises a FALSE
    refusal -- blocking a send that should have gone out. That mutation survived,
    because no test put a token in anything but the last value.
    """
    values = dict(FULL, POST_TITLE="%%POST_URL%%", UNSUBSCRIBE_URL="https://x.example/u")
    out = nr.render("<p>%%POST_TITLE%% %%UNSUBSCRIBE_URL%%</p>", values)
    assert out == "<p>%%POST_URL%% https://x.example/u</p>"


def test_strip_comments_handles_multiline():
    assert nr.strip_comments("a<!--\nb\nc\n-->d") == "ad"


def test_placeholder_contract_matches_the_template():
    """Every contract entry is actually used, so the set cannot rot.

    An unused placeholder is dead config: the sender would keep computing a value
    for something no email renders.
    """
    used = nr.tokens_in(nr.strip_comments(nr.TEMPLATE.read_text(encoding="utf-8")))
    unused = nr.PLACEHOLDERS - used
    assert not unused, f"declared but not used by the template: {sorted(unused)}"


def test_every_preview_value_is_real_copy_and_reaches_the_output():
    """The one assertion that checked substitution worked compared a value to itself.

    `assert nr.PREVIEW_VALUES['POST_TITLE'] in out` cannot detect the WRONG value
    being substituted, because both sides move together -- and it degenerates
    completely when the value is blanked, since `"" in out` is true of any string.
    Every PREVIEW_VALUES entry could be emptied with the suite green, which would
    make the operator's only look at the email a page of missing copy.
    """
    out = nr.render(nr.TEMPLATE.read_text(encoding="utf-8"), nr.PREVIEW_VALUES)
    assert set(nr.PREVIEW_VALUES) == set(nr.PLACEHOLDERS)
    for key, value in nr.PREVIEW_VALUES.items():
        assert value.strip(), f"{key} is blank, so the preview shows nothing for it"
        assert value in out, f"{key}'s value never reached the rendered preview"
    assert nr.PREVIEW_VALUES["POST_URL"].startswith("https://hoiboy.uk/blogs/")


# --------------------------------------------------------------------------
# preview()'s Chromium half (blog-priv#81 class sweep)
#
# Its entire browser half could be deleted, blanked, or made to crop, with the
# suite green: the only preview test above drives the two refusals and stops
# before the render. A preview that silently writes nothing, writes a blank PNG,
# or writes only the first screenful is worse than no preview, because it looks
# like evidence.
#
# The fake below is not a mock that swallows calls. It models the ONE thing
# Chromium does that preview() depends on -- writing a file at the path it is
# handed -- so a deleted screenshot or a missing parent directory fails here the
# same way it would fail for real. No browser download, so it runs in CI, where
# `playwright install chromium` is not run.
# --------------------------------------------------------------------------


class _FakePage:
    def __init__(self, record: dict) -> None:
        self._record = record

    def set_content(self, html: str, wait_until: str = "load") -> None:
        self._record["html"] = html

    def screenshot(self, path: str, full_page: bool = False) -> None:
        self._record["full_page"] = full_page
        # Writes for real, so a dropped `out_path.parent.mkdir` raises here exactly
        # as Chromium would.
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes" * 8)


class _FakeBrowser:
    def __init__(self, record: dict) -> None:
        self._record = record

    def new_page(self, viewport: dict) -> _FakePage:
        self._record["viewport"] = viewport
        return _FakePage(self._record)

    def close(self) -> None:
        self._record["closed"] = True


class _FakePlaywright:
    def __init__(self, record: dict) -> None:
        self._record = record
        self.chromium = self

    def launch(self) -> _FakeBrowser:
        return _FakeBrowser(self._record)

    def __enter__(self) -> _FakePlaywright:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


@pytest.fixture()
def fake_browser(monkeypatch):
    import playwright.sync_api

    record: dict = {}
    monkeypatch.setattr(
        playwright.sync_api, "sync_playwright", lambda: _FakePlaywright(record)
    )
    return record


def test_preview_writes_the_whole_email_and_says_where(tmp_path, capsys, fake_browser):
    """Four survivors at once: the screenshot deleted, the html blanked, the
    full-page flag flipped, and the parent directory left uncreated.

    `full_page` is the quiet one, and it needed measuring rather than arguing.
    Rendered with a real 1200x630 hero the email is 999px tall against a 900px
    viewport, and the two things below the fold are the consent promise (ends
    y=974) and the unsubscribe control (ends y=909) -- the exact part of the email
    most worth reviewing. Cropped, the operator approves a page whose footer he has
    not seen.

    Recorded because the first two attempts at that measurement said the OPPOSITE.
    Both reported 900px exactly, i.e. content shorter than the viewport, because
    PREVIEW_VALUES points HERO_URL at a URL that does not resolve offline and then
    at a hand-written base64 literal the browser silently refused (naturalWidth 0).
    An image that fails to load takes ~300px of height with it, and the missing
    height reads identically to a page that was always short.
    """
    out = tmp_path / "nested" / "dir" / "preview.png"

    rc = nr.preview(out)

    assert rc == 0
    assert out.is_file(), "a preview that writes no file is not a preview"
    assert out.stat().st_size > 0
    assert fake_browser["full_page"] is True, (
        "cropping to the viewport hides the footer, where the consent promise is"
    )
    assert fake_browser["closed"] is True, "the browser must be closed on the happy path"
    assert nr.PREVIEW_VALUES["POST_TITLE"] in fake_browser["html"]
    assert "%%" not in fake_browser["html"]
    assert str(out) in capsys.readouterr().out, "the operator needs the path"


def test_preview_names_a_template_that_will_not_render(tmp_path, monkeypatch, capsys):
    """The third refusal, which used to be a traceback.

    preview()'s other two failures (no playwright, no template) print a sentence and
    return 2. A template carrying a token outside the contract went straight out as
    a PlaceholderError stack trace instead, from the command whose entire job is to
    show the operator what the email looks like. The sender had the same hole in a
    worse place, where it also lost the fatal audit line.
    """
    broken = tmp_path / "email.html"
    broken.write_text("<p>%%POST_TITLE%%</p><p>%%NOT_IN_THE_CONTRACT%%</p>", encoding="utf-8")
    monkeypatch.setattr(nr, "TEMPLATE", broken)
    out = tmp_path / "preview.png"

    assert nr.preview(out) == 2
    assert not out.exists()
    err = capsys.readouterr().err
    assert "the template did not render" in err
    assert "NOT_IN_THE_CONTRACT" in err


def test_preview_closes_the_browser_even_when_the_screenshot_fails(
    tmp_path, monkeypatch, fake_browser
):
    """The `finally` around `browser.close()` is not decoration: a leaked Chromium
    process outlives the script and the operator has no idea it is there."""

    def boom(self, path: str, full_page: bool = False) -> None:
        raise RuntimeError("chromium fell over")

    monkeypatch.setattr(_FakePage, "screenshot", boom)
    with pytest.raises(RuntimeError, match="chromium fell over"):
        nr.preview(tmp_path / "preview.png")
    assert fake_browser["closed"] is True


def test_main_hands_back_the_preview_exit_code(tmp_path, monkeypatch, capsys):
    """`return preview(...)` -> `preview(...); return 0` survived.

    main() is the CLI entry point and nothing drove it. Swallowing the status means
    a preview that failed -- missing template, missing playwright -- reports success
    to any wrapper or CI step reading the exit code, so a non-existent preview is
    treated as a reviewed one.
    """
    monkeypatch.setattr(nr, "TEMPLATE", tmp_path / "absent" / "email.html")
    monkeypatch.setattr(sys, "argv", ["newsletter_render.py", "--preview", str(tmp_path / "x.png")])

    assert nr.main() == 2, "the failing status must reach the shell"
    assert "template not found" in capsys.readouterr().err


def test_main_refuses_to_run_without_an_output_path(monkeypatch, capsys):
    """`required=True` -> `required=False` survived. Without it `args.preview` is
    None and `Path(None)` raises TypeError: a traceback where argparse would have
    printed a usage line."""
    monkeypatch.setattr(sys, "argv", ["newsletter_render.py"])
    with pytest.raises(SystemExit) as exc:
        nr.main()
    assert exc.value.code == 2
    assert "--preview" in capsys.readouterr().err
