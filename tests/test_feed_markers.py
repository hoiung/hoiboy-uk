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

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC = REPO_ROOT / "public"
MARKER = "iamhoi"

# The DEFECT CLASS, not one instance of it. Hugo escapes `.Summary` into
# `<description>`, so ANY HTML comment surviving into a feed arrives as visible text.
ESCAPED_COMMENT = "&lt;!--"

# Measured at the time this gate was written. The build produced 19 XML files, of
# which 6 leaked. The floor is set well below 19 so ordinary content growth or
# pruning does not trip it, while still catching a build that produced no feeds.
MIN_FEEDS = 6


def test_the_feed_floor_is_a_real_floor() -> None:
    """Pin MIN_FEEDS itself, because nothing else did.

    Ralph round 6 tier 3 set MIN_FEEDS to 0 and the suite stayed green: both
    anti-vacuity assertions below go trivially true, and the constant appears in no
    other file. The guard against a vacuous pass was itself vacuously guarded.
    """
    assert MIN_FEEDS >= 6, (
        "MIN_FEEDS is what stops a leak check over zero feeds reporting clean. "
        "Lowering it toward 0 disables the anti-vacuity guard silently."
    )


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
    """The actual regression gate, scoped to XML only.

    The vacuity guard is asserted HERE as well as in its own test, not out of
    duplication but because the two were uncoupled: pytest runs each test
    independently, so this one passed on an absent `public/` (rglob returns []) even
    while its sibling failed. Ralph tier 3 pointed out that the protection only
    existed if you read the file as a whole. Now this assertion cannot pass without
    a real build behind it.
    """
    feeds = _feeds()
    assert len(feeds) >= MIN_FEEDS, (
        f"only {len(feeds)} .xml files under {PUBLIC}: refusing to report a clean "
        f"leak result over a tree that was never built, since zero feeds and zero "
        f"leaks are the same answer. Run `hugo --gc --minify -e production` first."
    )

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


def test_no_html_comment_of_any_shape_reaches_a_feed() -> None:
    """The defect class, not the one marker that happened to be found first.

    Ralph round 6 tier 3 found a LIVE leak that the `iamhoi` count above could not
    see: an editorial WORDING directive in
    content/posts/how-to-actually-build-communities/index.md, naming the operator's
    SEO split and his CV and LinkedIn, shipping as the FIRST VISIBLE TEXT of that item
    in public/index.xml and public/blogs/index.xml. It contained no `iamhoi`, so both
    AC 6.1's and AC 6.2's verify commands passed over it while it was going out.

    That is the difference between testing an instance and testing the class. A
    comment is invisible on the page and visible in the feed, whatever it says, so
    that is what this asserts.
    """
    feeds = _feeds()
    assert len(feeds) >= MIN_FEEDS, (
        f"only {len(feeds)} .xml files under {PUBLIC}: refusing to report clean over "
        f"a tree that was never built. Run `hugo --gc --minify -e production` first."
    )

    offenders = {}
    for feed in feeds:
        count = feed.read_text(encoding="utf-8", errors="replace").count(ESCAPED_COMMENT)
        if count:
            offenders[str(feed.relative_to(REPO_ROOT))] = count

    assert not offenders, (
        f"{len(offenders)} feed(s) carry an escaped HTML comment: {offenders}. "
        f"Whatever it says, a reader sees it as text. The strip lives in "
        f"layouts/_default/rss.xml and matches every comment, not a marker shape."
    )


def test_the_strip_does_not_eat_the_content_around_it() -> None:
    """The other half: stripping must not become the damage it prevents.

    Ralph round 6 tier 3 changed the strip's `.*?` to greedy `.*`, which swallows to
    the LAST `-->` on the page. All three feed tests stayed green while 1926 bytes
    vanished across three feeds, because they counted markers and nothing counted
    content. Non-greediness was described as load-bearing in the template and was
    pinned by nothing.

    An empty description is the visible form of that failure, so it is what this
    asserts, on the item that actually carried the comment.
    """
    feed = PUBLIC / "blogs" / "index.xml"
    assert feed.is_file(), f"{feed} missing; run the build first"
    text = feed.read_text(encoding="utf-8", errors="replace")

    descriptions = re.findall(r"<description>(.*?)</description>", text, re.S)
    assert len(descriptions) >= MIN_FEEDS, f"only {len(descriptions)} descriptions"
    empty = [i for i, d in enumerate(descriptions) if not d.strip()]
    assert not empty, (
        f"{len(empty)} feed item(s) have an EMPTY description. The strip is eating "
        f"real summary text, which is the failure mode a greedy match introduces."
    )

    # The canary. `deterministic-vs-probabilistic` is the item that actually
    # DEMONSTRATES the greedy failure: its summary holds a comment with more content
    # after it, so a greedy match runs past the comment's own close and swallows the
    # opening paragraph, leaving the description starting mid-article.
    #
    # Measured before choosing this assertion, rather than assumed. Two weaker ideas
    # were tested and rejected: an empty-description check (greedy leaves them
    # non-empty, so it SURVIVED), and "no description starts with a heading" (32 of
    # 228 legitimately do, all legacy posts, so it would fail on correct content,
    # which is the exact mistake this file's scoping note warns about).
    item = next(
        (i for i in re.findall(r"<item>(.*?)</item>", text, re.S)
         if "deterministic-vs-probabilistic" in i),
        None,
    )
    assert item is not None, (
        "the canary post is not in the feed. It was chosen because its summary "
        "contains a comment followed by more content, which is what makes a greedy "
        "strip observable. If it is gone, pick another item of that shape."
    )
    body = re.search(r"<description>(.*?)</description>", item, re.S).group(1)
    assert "Two words." in body, (
        "the canary's opening line is gone from its feed summary: the strip ran past "
        "the comment it was removing and took real content with it. Check that the "
        "marker regex in layouts/_default/rss.xml is still non-greedy (`.*?`)."
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
