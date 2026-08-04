#!/usr/bin/env python3
"""Tests for the subscribe-form placement gate (hoiboy-uk#56, Ralph escalation).

Like its sibling `check_noindex_frontmatter.py`, this gate shipped with no test.
The escalation class sweep found its "did this gate examine anything" floor was
AGGREGATE: `suppressed_seen == 0` asks whether the suppressed set as a whole
matched something, and a tree predating `/newsletter/` still counts the legal,
private and AGIT pages. So the total stayed healthy while the one suppression
rule this Issue exists to enforce was never exercised, and the gate reported
clean.

The assertions below are on the MESSAGE, not the exit code: this gate returns 1
for six distinct reasons, so `rc == 1` is compatible with it being red for
something unrelated to the defect under test.

Run: python3 -m pytest scripts/test_check_subscribe_placement.py -q
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "check_subscribe_placement", _HERE / "check_subscribe_placement.py"
)
gate = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gate
_spec.loader.exec_module(gate)

REPO = _HERE.parent
PUBLIC = REPO / "public"

def _with_form(href: str = "/legal/privacy/") -> str:
    """A page rendering through baseof AND carrying the form.

    The href is a parameter rather than a constant because the real one points
    into `legal/`, which is itself a suppressed class: baking it in meant the
    link target alone populated that class, and the per-class test for `legal/`
    could never see it empty. The fixture was masking the very thing under test.
    """
    return (
        '<html><footer><div class="subscribe-form">'
        f'<form><a href="{href}">Privacy Notice</a></form>'
        "</div></footer></html>"
    )


WITH_FORM = _with_form()
# Rendered through baseof, deliberately without the form: what a suppressed page
# must look like.
NO_FORM = "<html><footer>no form here</footer></html>"


def _write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _tree(tmp_path: Path, *, suppressed: list[str],
          link_href: str = "/legal/privacy/") -> Path:
    """A synthetic built tree the gate should pass.

    `suppressed` names the suppressed pages to include, so a test can build the
    stale-tree case by leaving a whole class out. `link_href` moves the form's
    internal link out of a class a test needs to observe as empty.
    """
    root = tmp_path / "public"
    body = _with_form(link_href)
    for rel in suppressed:
        _write(root, rel, NO_FORM)
    for rel in gate.PRESENT_PATHS:
        _write(root, rel, body)
    _write(root, "blogs/some-post/index.html", body)        # the sampled post
    _write(root, link_href.strip("/") + "/index.html", NO_FORM)   # the link target
    return root


ALL_SUPPRESSED = [
    "legal/some-notice/index.html",
    "private/tools/meet-recorder/index.html",
    "community/asians-gingers-in-tech/thanks/index.html",
    "newsletter/index.html",
    "404.html",
]


def _run(built: Path, monkeypatch) -> int:
    monkeypatch.setattr(sys, "argv", ["check_subscribe_placement.py", "--built", str(built)])
    return gate.main()


# --------------------------------------------------------------------------
# Positive controls.
# --------------------------------------------------------------------------

@pytest.mark.skipif(not (PUBLIC / "index.html").exists(),
                    reason="no built tree; run `hugo --gc --minify -e production`")
def test_the_real_built_tree_passes(monkeypatch, capsys):
    """The live tree must be clean, or every red test below proves nothing."""
    assert _run(PUBLIC, monkeypatch) == 0
    assert "[OK]" in capsys.readouterr().out


def test_synthetic_good_tree_passes(tmp_path, monkeypatch, capsys):
    """Guards the fixture: one already red would fake every proof below."""
    assert _run(_tree(tmp_path, suppressed=ALL_SUPPRESSED), monkeypatch) == 0
    assert "[OK]" in capsys.readouterr().out


# --------------------------------------------------------------------------
# The escalation defect: the floor must be per-class, not aggregate.
# --------------------------------------------------------------------------

def test_a_class_with_no_pages_is_named(tmp_path, monkeypatch, capsys):
    """A tree predating /newsletter/ must not report that rule exercised.

    Every other suppressed class is present, so the AGGREGATE count is a healthy
    4 and the old floor stayed silent. This is the exact shape the sweep found.
    """
    built = _tree(tmp_path, suppressed=[p for p in ALL_SUPPRESSED
                                        if not p.startswith("newsletter/")])
    assert _run(built, monkeypatch) == 1
    err = capsys.readouterr().err
    assert "[unexercised-suppression-class]" in err
    assert "'newsletter/'" in err
    assert "STALE" in err


@pytest.mark.parametrize("missing", sorted(
    {"legal/", "private/", "community/asians-gingers-in-tech/", "newsletter/", "404.html"}))
def test_every_suppression_class_has_its_own_floor(tmp_path, monkeypatch, capsys, missing):
    """Not just the newsletter one: each class must be independently exercised.

    Parametrised deliberately. A floor that happens to cover the class under
    discussion, and no other, is the aggregate bug wearing a different shape.
    """
    kept = [p for p in ALL_SUPPRESSED if not (p == missing or p.startswith(missing))]
    # Park the form's link outside the class under test, or the target page alone
    # would populate it and the floor could never be observed empty.
    href = "/about/" if "legal/".startswith(missing) or missing == "legal/" else "/legal/privacy/"
    assert _run(_tree(tmp_path, suppressed=kept, link_href=href), monkeypatch) == 1
    assert f"'{missing}'" in capsys.readouterr().err


def test_ok_line_reports_per_class_counts(tmp_path, monkeypatch, capsys):
    """The evidence belongs in the message, not just the verdict."""
    assert _run(_tree(tmp_path, suppressed=ALL_SUPPRESSED), monkeypatch) == 0
    out = capsys.readouterr().out
    assert "Suppression classes exercised:" in out
    assert "newsletter/ -> 1" in out


# --------------------------------------------------------------------------
# The gate's original assertions still hold.
# --------------------------------------------------------------------------

def test_a_suppressed_page_carrying_the_form_is_caught(tmp_path, monkeypatch, capsys):
    built = _tree(tmp_path, suppressed=ALL_SUPPRESSED)
    _write(built, "newsletter/index.html", WITH_FORM)
    assert _run(built, monkeypatch) == 1
    assert "[suppressed-but-present] newsletter/index.html" in capsys.readouterr().err


def test_a_page_that_lost_the_form_is_caught(tmp_path, monkeypatch, capsys):
    built = _tree(tmp_path, suppressed=ALL_SUPPRESSED)
    _write(built, "skills/index.html", NO_FORM)
    assert _run(built, monkeypatch) == 1
    assert "skills/index.html" in capsys.readouterr().err


def test_a_dead_form_link_is_caught(tmp_path, monkeypatch, capsys):
    built = _tree(tmp_path, suppressed=ALL_SUPPRESSED)
    (built / "legal" / "privacy" / "index.html").unlink()
    assert _run(built, monkeypatch) == 1
    assert "[dead-form-link]" in capsys.readouterr().err
