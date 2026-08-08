#!/usr/bin/env python3
"""Nothing invisible on the page may arrive as visible text in a feed (blog-priv#81).

THE DEFECT THIS EXISTS FOR. Hugo's embedded RSS template escapes `.Summary` into
`<description>`, so an HTML comment -- invisible on the rendered page -- becomes
reader-visible text in a feed client. Ralph round 6 found it live: an editorial
WORDING directive in content/posts/how-to-actually-build-communities/index.md,
naming the operator's SEO split and his CV and LinkedIn, was shipping as the FIRST
VISIBLE TEXT of that item in public/index.xml and public/blogs/index.xml. It
contained no `iamhoi`, so the marker-shaped check passed straight over it while it
was going out. `layouts/_default/rss.xml` now strips every comment; this keeps it
stripped, in both directions.

WHY THIS IS A GATE SCRIPT AND NOT JUST A TEST FILE. It was a test file, and the
class sweep showed what that costs: `assert not offenders` could be rewritten to
`assert not offenders or True` and NOTHING in the repo noticed, because the only
thing checking the feed lived in the same file as the assertion being neutered.
tests/test_gate_mutations.py is this repo's answer to that, and it works by
reverting a guard in one file and requiring a test in ANOTHER to go red -- which
is only possible once the logic lives outside the test. Splitting it also gives
the check a CLI, so it can run outside pytest.

SCOPING IS DELIBERATE: XML only, never a whole-tree sweep. The canonical form is

    grep -rc 'iamhoi' public/ --include='*.xml'

because public/blogs/your-voice-is-a-brand/index.html carries a LEGITIMATE hit --
that post is about the voice guard and quotes the marker syntax in a code block.
A whole-tree grep would fail forever on correct content, and a gate that fails on
correct content gets disabled, which is worse than no gate.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

# defusedxml rather than xml.etree, even though every file parsed here is output
# from this repo's own Hugo build rather than untrusted input. The stdlib parser
# is exposed to entity-expansion attacks by default, the swap is one import, and
# a gate that hardens its own parsing is a better default than one that reasons
# about who could reach it. Added to requirements-dev.txt in the same commit.
from defusedxml import ElementTree as ET  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_coverage import require_examined

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC = REPO_ROOT / "public"

MARKER = "iamhoi"

# The DEFECT CLASS, not the one instance of it that happened to be found first.
# Derived rather than typed, so the needle cannot drift away from what Hugo
# actually emits: this is what an html comment opener looks like after the
# XML-escaping that turns it into visible text.
ESCAPED_COMMENT = html.escape("<!--")

# Measured when this gate was written: the build produced 19 XML files, of which 6
# leaked. The floor sits well below 19 so ordinary content growth or pruning does
# not trip it, while still catching a build that produced no feeds at all. Zero
# feeds and zero leaks are the same answer, which is the vacuity trap here.
MIN_FEEDS = 6

# A post whose description is two short sentences with a comment between them. It
# is the canary for the OTHER failure direction: Ralph round 6 changed the strip's
# `.*?` to a greedy `.*`, which swallows to the LAST `-->` on the page. All three
# leak tests stayed green while 1926 bytes vanished across three feeds, because a
# strip that eats too much removes comments perfectly.
GREEDY_CANARY_SLUG = "deterministic-vs-probabilistic"
GREEDY_CANARY_TEXT = "Two words."

# ONE SWEEP LEAD IS DELIBERATELY NOT GATED, and the measurement is here so nobody
# re-derives it. Widening the strip to `(?s).?<!--.*?-->\s*` -- eating one
# character to the LEFT of every comment -- survives this gate. Built both ways
# and diffed: it changes 1 description in each of index.xml and blogs/index.xml
# and costs 4 bytes in total, every one of them a newline sitting between a
# `</p>` and the next `<p>`. Nothing a reader can see, because every comment in
# the current corpus is preceded by whitespace rather than by prose.
#
# So a rule failing on it would be gating on invisible whitespace, and would fire
# on ordinary reformatting forever. The planted-offender test in
# tests/test_feed_markers.py covers the case that WOULD matter (a comment directly
# after a word), so the detector is proven even though the corpus cannot currently
# exercise it. Re-measure before treating this as safe if the corpus changes.


def collect(public: Path | None = None) -> list[Path]:
    return sorted((public or PUBLIC).rglob("*.xml"))


def failures(feeds: list[Path]) -> list[str]:
    """Every feed problem, so one run reports them all."""
    out: list[str] = []

    if len(feeds) < MIN_FEEDS:
        out.append(
            f"only {len(feeds)} .xml files found, expected at least {MIN_FEEDS}. "
            f"Refusing to report a clean leak result over a tree that was never "
            f"built: zero feeds and zero leaks are the same answer. Run "
            f"`hugo --gc --minify -e production` first."
        )
        return out

    texts = {feed: feed.read_text(encoding="utf-8", errors="replace") for feed in feeds}

    markers = {f.name: t.count(MARKER) for f, t in texts.items() if MARKER in t}
    if markers:
        out.append(
            f"voice-guard markers leaked into {len(markers)} feed(s): {markers}. "
            f"They render as visible text in a reader's feed client. The strip lives "
            f"in layouts/_default/rss.xml; check whether a NEW marker shape was "
            f"introduced that its regex does not match."
        )

    comments = {f.name: t.count(ESCAPED_COMMENT) for f, t in texts.items()
                if ESCAPED_COMMENT in t}
    if comments:
        out.append(
            f"{len(comments)} feed(s) carry an escaped HTML comment: {comments}. "
            f"Whatever it says, a reader sees it as text. The strip lives in "
            f"layouts/_default/rss.xml and matches every comment, not a marker shape."
        )

    # Every feed must PARSE. Dropping `transform.XMLEscape` from the description
    # pipeline was a survivor, and it is the strongest possible feed failure: a
    # conformant reader rejects the whole document rather than degrading, so those
    # feeds stop working entirely. Nothing in this repo ever parsed a feed before;
    # the checks were all substring counting, which cannot see malformed XML.
    for feed in feeds:
        try:
            ET.fromstring(texts[feed])
        except ET.ParseError as exc:
            out.append(
                f"{feed.name} is not well-formed XML: {exc}. A conformant reader "
                f"rejects the whole document, so this feed stops working rather "
                f"than degrading. Usually an unescaped & or < reaching <description>."
            )

    # The strip must not become the damage it prevents. Two directions, both
    # survivors: widening the marker regex to `(?s)<.*?>` strips every tag, so
    # paragraphs run together and every in-body link disappears; over-eating one
    # character to the left silently truncates the text before each comment.
    if not any("&lt;p&gt;" in t for t in texts.values()):
        out.append(
            "no feed description contains a paragraph tag. The strip is removing "
            "markup, not just comments, so every <p> and every <a href> has gone "
            "and the descriptions are running together as one block."
        )

    return out


def canary_failures(feeds: list[Path]) -> list[str]:
    """The greedy-strip canary, separated because it depends on one post existing.

    Kept out of `failures` so that a legitimate future rename of that post is a
    clear, single failure to fix rather than a mysterious feed error.
    """
    for feed in feeds:
        text = feed.read_text(encoding="utf-8", errors="replace")
        # `<description>` is the scope, and it is not defensive padding. Without
        # it this fired on sitemap.xml, which carries the slug in a <loc> and has
        # no descriptions at all -- a canary that reports damage on a file it does
        # not apply to. Caught by running the gate rather than by reading it.
        if "<description>" not in text:
            continue
        if GREEDY_CANARY_SLUG in text and GREEDY_CANARY_TEXT not in text:
            return [
                f"{feed.name} carries {GREEDY_CANARY_SLUG} but its description has "
                f"lost {GREEDY_CANARY_TEXT!r}. The comment strip is eating the "
                f"content around the comment, not only the comment. Check whether "
                f"the regex in layouts/_default/rss.xml is still non-greedy."
            ]
    return []


def main() -> int:
    feeds = collect()
    require_examined(
        "check_feed_markers",
        "rendered XML feeds",
        feeds,
        hint=(
            "Expected .xml files under public/. Run "
            "`hugo --gc --minify -e production` first: a leak check over zero feeds "
            "passes vacuously and looks identical to a clean result."
        ),
    )

    problems = failures(feeds) + canary_failures(feeds)
    if problems:
        print(f"feed-markers: {len(problems)} problem(s) across {len(feeds)} feed(s)",
              file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"OK: {len(feeds)} feeds carry no comment, no marker and parse as XML")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
