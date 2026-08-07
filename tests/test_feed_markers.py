"""The voice-guard markers must never reach the XML feeds again (blog-priv#81 AC 6.2).

The defect: `iamhoi` markers are HTML comments, invisible on a rendered page, but
Hugo's embedded RSS template escapes `.Summary` into `<description>`, which turned
them into visible text in readers' feed clients. Six of nineteen feeds carried them.
`layouts/_default/rss.xml` strips them; this keeps them stripped.

SCOPING IS THE WHOLE DESIGN OF THIS GATE, and it is why the check is XML-only rather
than a whole-tree sweep. The canonical form is

    grep -rc 'iamhoi' public/ --include='*.xml'

because `public/blogs/your-voice-is-a-brand/index.html` carries a LEGITIMATE hit: that
post is about the voice guard and quotes the marker syntax inside a code block. A
whole-tree `grep -rc iamhoi public/` would fail forever on correct content, and a gate
that fails on correct content gets disabled, which is worse than no gate.

Fails rather than skips on a missing build, matching
`tests/test_taxonomy_terms_match_build.py`: a gate that silently passes when there is
nothing to check is indistinguishable from a passing gate, and this one has a real
vacuity trap. With zero XML present the leak count is 0, which is byte-identical to
the healthy state.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC = REPO_ROOT / "public"
MARKER = "iamhoi"

# Measured at the time this gate was written. The build produced 19 XML files, of
# which 6 leaked. The floor is set well below 19 so ordinary content growth or
# pruning does not trip it, while still catching a build that produced no feeds.
MIN_FEEDS = 6


def _feeds() -> list[Path]:
    return sorted(PUBLIC.rglob("*.xml"))


def test_the_build_actually_produced_feeds() -> None:
    """Guard the vacuity trap before asserting anything about leaks.

    Without this, a missing or empty `public/` reports zero leaking feeds, which is
    exactly what a healthy tree reports. The gate would pass hardest precisely when
    it had checked nothing.
    """
    assert PUBLIC.is_dir(), (
        f"{PUBLIC} does not exist. Run `hugo --gc --minify -e production` first. "
        f"This fails rather than skips because a leak check over zero feeds passes "
        f"vacuously and looks identical to a clean result."
    )
    feeds = _feeds()
    assert len(feeds) >= MIN_FEEDS, (
        f"only {len(feeds)} .xml files under {PUBLIC}, expected at least {MIN_FEEDS}. "
        f"The build is not what CI produces, so a clean leak result would prove nothing."
    )


def test_no_voice_markers_in_any_feed() -> None:
    """The actual regression gate, scoped to XML only."""
    offenders = {}
    for feed in _feeds():
        text = feed.read_text(encoding="utf-8", errors="replace")
        count = text.count(MARKER)
        if count:
            offenders[str(feed.relative_to(REPO_ROOT))] = count

    assert not offenders, (
        f"voice-guard markers leaked into {len(offenders)} feed(s): {offenders}. "
        f"They render as visible text in a reader's feed client. The strip lives in "
        f"layouts/_default/rss.xml; check whether a NEW marker shape was introduced "
        f"that its regex does not match (the multi-line `<!-- iamhoi-claims ... -->` "
        f"block is why that regex needs the `(?s)` flag and a non-greedy match)."
    )


def test_the_scoping_is_load_bearing_not_incidental() -> None:
    """Prove the XML-only scoping is required, so nobody 'simplifies' it later.

    This asserts the legitimate HTML hit still EXISTS. If someone widens the gate to
    the whole tree, they get a permanent failure on correct content; if someone
    removes the post that documents the voice guard, this test tells them the reason
    for the scoping has changed rather than letting the constraint linger unexplained.
    """
    html_hits = [
        path
        for path in PUBLIC.rglob("*.html")
        if MARKER in path.read_text(encoding="utf-8", errors="replace")
    ]
    assert html_hits, (
        "no HTML page quotes the marker syntax any more. The XML-only scoping of this "
        "gate exists because such a page did. Re-check whether the scoping is still "
        "needed before widening it."
    )
