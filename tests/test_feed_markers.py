"""Drive scripts/check_feed_markers.py against the real build (blog-priv#81 AC 6.2).

WHAT MOVED AND WHY. The checks used to live here, as assertions inside test
functions. The class sweep showed the cost: `assert not offenders` could be
rewritten to `assert not offenders or True` and nothing in the repo noticed,
because the only thing checking the feeds was the same file as the assertion being
neutered. This file has no way to guard its own assertions -- no file does. This
repo's answer is tests/test_gate_mutations.py, which reverts a guard in one file
and requires a test in ANOTHER to go red, and that is only possible once the logic
lives outside the test. So the logic is now scripts/check_feed_markers.py and this
file drives it.

Two kinds of test below, and both are needed:

  1. the real build must be clean, which is the regression gate;
  2. the gate must FAIL on a planted offender, which is what stops (1) from being
     a green tick over a check that cannot detect anything.

(2) is the half that was missing. A gate asserted only against a healthy tree
reports exactly the same thing whether it works or not.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_feed_markers as gate  # noqa: E402

PUBLIC = gate.PUBLIC
MARKER = gate.MARKER
MIN_FEEDS = gate.MIN_FEEDS

# A minimal but structurally real feed, used for the planted-offender tests. Built
# rather than copied from public/ so each test can plant exactly one defect.
FEED = """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<rss version="2.0"><channel>
  <title>hoiboy.uk</title>
  <item>
    <title>A post</title>
    <link>https://hoiboy.uk/blogs/a-post/</link>
    <description>{description}</description>
  </item>
</channel></rss>
"""

CLEAN_DESCRIPTION = "&lt;p&gt;Two words. And a second sentence.&lt;/p&gt;"


def write_feeds(root: Path, count: int, description: str = CLEAN_DESCRIPTION) -> list[Path]:
    """`count` feeds, so the MIN_FEEDS floor is satisfied and the real rule is reached."""
    out = []
    for i in range(count):
        path = root / f"feed{i}.xml"
        path.write_text(FEED.format(description=description), encoding="utf-8")
        out.append(path)
    return sorted(out)


# --------------------------------------------------------------------------
# The real build
# --------------------------------------------------------------------------


def test_the_build_actually_produced_feeds() -> None:
    """The vacuity trap, guarded before anything is asserted about leaks.

    Without this, a missing or empty public/ reports zero leaking feeds, which is
    byte-identical to what a healthy tree reports. The gate would pass hardest
    precisely when it had checked nothing. Fails rather than skips, matching
    tests/test_taxonomy_terms_match_build.py.
    """
    assert PUBLIC.is_dir(), (
        f"{PUBLIC} does not exist. Run `hugo --gc --minify -e production` first."
    )
    assert len(gate.collect()) >= MIN_FEEDS


def test_the_feed_floor_is_a_real_floor() -> None:
    """Pin MIN_FEEDS itself, because nothing else does.

    Ralph round 6 set it to 0 and the suite stayed green: every anti-vacuity
    assertion goes trivially true and the constant appears in no other file. Now
    that the constant lives in the gate rather than here, the mutation registry
    can reach it too.
    """
    assert gate.MIN_FEEDS >= 6, (
        "MIN_FEEDS is what stops a leak check over zero feeds reporting clean. "
        "Lowering it toward 0 disables the anti-vacuity guard silently."
    )


def test_the_real_build_carries_no_marker_no_comment_and_parses() -> None:
    """The regression gate itself, over what the build actually produced."""
    assert gate.failures(gate.collect()) == []


def test_the_real_build_did_not_lose_content_to_the_strip() -> None:
    """The other direction: stripping must not become the damage it prevents.

    Ralph round 6 changed the strip's `.*?` to a greedy `.*`, which swallows to the
    LAST `-->` on the page. All three leak tests stayed green while 1926 bytes
    vanished across three feeds, because a strip that eats too much removes
    comments perfectly.
    """
    assert gate.canary_failures(gate.collect()) == []


# --------------------------------------------------------------------------
# The gate must be able to FAIL
# --------------------------------------------------------------------------


def test_an_empty_tree_is_refused_rather_than_reported_clean(tmp_path: Path) -> None:
    problems = gate.failures([])
    assert any("zero feeds and zero leaks are the same answer" in p for p in problems)


def test_a_planted_marker_is_caught(tmp_path: Path) -> None:
    feeds = write_feeds(tmp_path, MIN_FEEDS)
    feeds[2].write_text(
        FEED.format(description=f"&lt;p&gt;text {MARKER} more&lt;/p&gt;"), encoding="utf-8"
    )
    problems = gate.failures(feeds)
    assert any("voice-guard markers leaked" in p for p in problems), problems


def test_a_planted_comment_of_any_shape_is_caught(tmp_path: Path) -> None:
    """The defect class, not the one marker found first.

    The live leak carried no `iamhoi` at all: it was an editorial WORDING directive
    naming the operator's SEO split, his CV and his LinkedIn, shipping as the first
    visible text of a feed item. Both marker-shaped verify commands passed over it.
    """
    feeds = write_feeds(tmp_path, MIN_FEEDS)
    feeds[1].write_text(
        FEED.format(description="&lt;!-- an editorial note --&gt;&lt;p&gt;body&lt;/p&gt;"),
        encoding="utf-8",
    )
    problems = gate.failures(feeds)
    assert any("escaped HTML comment" in p for p in problems), problems


def test_a_feed_that_is_not_well_formed_xml_is_caught(tmp_path: Path) -> None:
    """The strongest possible feed failure, and nothing in this repo could see it.

    Dropping `transform.XMLEscape` from the description pipeline was a survivor: it
    makes 6 of the 19 feeds invalid XML, so a conformant reader rejects the whole
    document rather than degrading. Every previous check was substring counting,
    which cannot detect malformed XML no matter how many strings it counts.
    """
    feeds = write_feeds(tmp_path, MIN_FEEDS)
    feeds[0].write_text(
        FEED.format(description="<p>raw markup & an unescaped ampersand</p>"),
        encoding="utf-8",
    )
    problems = gate.failures(feeds)
    assert any("not well-formed XML" in p for p in problems), problems


def test_a_strip_that_removes_every_tag_is_caught(tmp_path: Path) -> None:
    """Widening the marker regex to `(?s)<.*?>` strips every tag, not just comments.

    It looks like a plausible simplification and it silently removes every <p> and
    every in-body <a href>, so paragraphs run together and the links disappear.
    Nothing asserted that a description still CONTAINS its markup.
    """
    feeds = write_feeds(tmp_path, MIN_FEEDS, description="Two words. And more.")
    problems = gate.failures(feeds)
    assert any("removing markup" in p for p in problems), problems


def test_a_strip_that_eats_leftwards_is_caught(tmp_path: Path) -> None:
    """The canary, planted.

    Measured before choosing this assertion rather than assumed, and two weaker
    ideas were tested and rejected: an empty-description check (a greedy strip
    leaves them non-empty, so it SURVIVED) and "no description starts with a
    heading" (32 of 228 legitimately do, all legacy posts, so it would fail on
    correct content).
    """
    feeds = write_feeds(tmp_path, MIN_FEEDS)
    feeds[3].write_text(
        FEED.format(
            description=f"&lt;p&gt;{gate.GREEDY_CANARY_SLUG} but the opening is gone&lt;/p&gt;"
        ),
        encoding="utf-8",
    )
    assert gate.canary_failures(feeds), "a truncated canary description must be caught"


def test_the_canary_ignores_a_file_with_no_descriptions(tmp_path: Path) -> None:
    """sitemap.xml carries the canary slug in a <loc> and has no descriptions at all.

    The first version of the canary fired on it, i.e. reported content damage on a
    file the check does not apply to. Found by running the gate rather than by
    reading it, which is the same lesson this whole workstream keeps paying for.
    """
    feeds = write_feeds(tmp_path, MIN_FEEDS)
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text(
        '<?xml version="1.0" encoding="utf-8"?><urlset><url><loc>'
        f"https://hoiboy.uk/blogs/{gate.GREEDY_CANARY_SLUG}/</loc></url></urlset>",
        encoding="utf-8",
    )
    assert gate.canary_failures(sorted(feeds + [sitemap])) == []


def test_the_comment_needle_is_derived_not_typed() -> None:
    """ESCAPED_COMMENT is the SOLE guard of the any-comment check, and it appeared
    in no other file, so retyping it as anything at all disabled that check
    silently. Derived from html.escape now, so it cannot drift away from what Hugo
    actually emits."""
    assert gate.ESCAPED_COMMENT == "&lt;!--"


# --------------------------------------------------------------------------
# Scoping
# --------------------------------------------------------------------------


def test_the_scoping_is_load_bearing_not_incidental() -> None:
    """Prove the XML-only scoping is required, so nobody 'simplifies' it later.

    public/blogs/your-voice-is-a-brand/index.html carries a LEGITIMATE marker hit:
    that post is about the voice guard and quotes the syntax in a code block. A
    whole-tree sweep would fail forever on correct content, and a gate that fails
    on correct content gets disabled, which is worse than no gate.
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


@pytest.mark.parametrize("needle", ["<description>", "<item>"])
def test_the_real_feeds_have_the_shape_the_planted_fixtures_model(needle: str) -> None:
    """Keep the fixtures honest. If Hugo's output stopped looking like this, every
    planted-offender test above would still pass while modelling something the
    build no longer produces."""
    blogs = PUBLIC / "blogs" / "index.xml"
    assert blogs.is_file(), f"{blogs} missing; run the build first"
    assert needle in blogs.read_text(encoding="utf-8")
    assert re.search(r"<description>.+?</description>", blogs.read_text(encoding="utf-8"), re.S)
