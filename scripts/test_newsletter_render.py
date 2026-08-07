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
    with pytest.raises(nr.PlaceholderError) as exc:
        nr.render("<p>%%NOT_A_REAL_ONE%%</p>", FULL)
    assert "NOT_A_REAL_ONE" in str(exc.value), "the message must name the offender"


def test_unknown_key_from_caller_is_refused():
    """A value for a placeholder the template dropped would vanish silently."""
    with pytest.raises(nr.PlaceholderError) as exc:
        nr.render("<p>%%POST_TITLE%%</p>", {"POST_TITLE": "x", "STALE_KEY": "y"})
    assert "STALE_KEY" in str(exc.value)


def test_missing_value_is_refused_rather_than_left_raw():
    with pytest.raises(nr.PlaceholderError) as exc:
        nr.render("<p>%%POST_TITLE%% %%POST_URL%%</p>", {"POST_TITLE": "x"})
    assert "POST_URL" in str(exc.value)


def test_substitution_is_not_recursive():
    """A value that itself looks like a token must not be re-expanded."""
    out = nr.render("<p>%%POST_TITLE%%</p>", {"POST_TITLE": "%%POST_URL%%"})
    assert out == "<p>%%POST_URL%%</p>", (
        "a value is data, not another template; re-expanding it would let post "
        "content reach into the placeholder contract"
    )


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
