#!/usr/bin/env python3
"""No noindex page may appear in the sitemap or the RSS feed.

`static/_headers` can stop a crawler indexing a page. It cannot stop Hugo
advertising it. Those are different surfaces with different mechanisms:

  X-Robots-Tag: noindex   ->  a crawler that FETCHES the page is told not to index
  sitemap.disable         ->  the page is not listed in public/sitemap.xml
  build.list: never       ->  the page is not listed anywhere, INCLUDING the feed

A page with only the header still lands in `public/index.xml`, with its full
rendered body, and every page on the site advertises that feed through
`<link rel="alternate">`. For a private or transactional page that is not an
indexing problem, it is a delivery problem: the page arrives in subscribers'
readers as a post.

This has happened three times in this repo:

  1. `content/private/tools/meet-recorder/index.md` -- found in Ralph round 15
     of blog-priv#55, fixed, and the reason written into that file's frontmatter.
  2. `content/community/agit-thanks/` -- carried the same defect from #62.
  3. The two newsletter pages added by #56 -- found in Ralph round 5, where both
     pages AND the section index were in the sitemap and both bodies in the feed.

Instance 3 happened despite instance 1 being fixed and documented in-repo,
because nothing mechanical connected them. Prose in one file cannot stop the
same mistake in another. This gate is that missing link.

WHY IT CHECKS THE BUILT TREE, not frontmatter. The first version of this gate
resolved each noindex glob to a content directory by string surgery
(`/newsletter/*` -> `content/newsletter`) and skipped any glob whose directory
did not exist. That silently skipped `/community/asians-gingers-in-tech/thanks/*`,
whose bundle actually lives at `content/community/agit-thanks/` behind a `url:`
override -- the one page that was still leaking. A gate that quietly skips what
it cannot resolve reports success for the case it failed to examine. So this
version asserts the OUTCOME in the generated files, where a `url:` override, an
alias and a section index are all already resolved.

Run: `python3 scripts/check_noindex_frontmatter.py [--built public]`.
Needs a built tree: run `hugo --gc --minify -e production` first.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import xml.etree.ElementTree as ET
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HEADERS = REPO / "static" / "_headers"

# Globs whose noindex rule does NOT imply exclusion from these surfaces, with
# the reason. Explicit so an exemption is a decision, never a silent gap.
EXEMPT = {
    # Hugo never lists the 404 page in either output; it is not a content page.
    "/404*": "Hugo does not emit the 404 page into the sitemap or the feed",
}


def noindex_globs() -> list[str]:
    """Path globs `static/_headers` marks noindex, via the repo's existing parser.

    Reused rather than re-implemented, following the precedent `test_404.py` set
    for this same file. The first version of this gate hand-rolled
    `re.search(r"X-Robots-Tag:.*noindex", line)` over `read_text(encoding="utf-8")`,
    and that copy disagreed with the canonical parser in two ways, both reachable:

      BOM          `utf-8` leaves a leading U+FEFF on the first line, so it does
                   not start with "/", the first block's path line is not
                   recognised, and that block's rule is dropped silently. Save
                   this file from any BOM-emitting editor and the first rule stops
                   being enforced with every gate still green. The canonical
                   parser reads `utf-8-sig` for exactly this reason, and names the
                   defect by issue number at check_social_cards.py:172.
      `none`       `X-Robots-Tag: none` is the documented equivalent of
                   `noindex, nofollow`. A literal "noindex" matcher misses it
                   entirely, so a page protected only by `none` was invisible to
                   this gate, which then reported OK over it.

    Two parsers for one file will always drift, and the drift is silent in the
    passing direction. `check_social_cards.py` already scans this file correctly
    for exactly this purpose, and its parser is also what `test_404.py` asserts
    the 404 rule through. One file, one parser.
    """
    spec = importlib.util.spec_from_file_location(
        "check_social_cards", REPO / "scripts" / "check_social_cards.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.parse_noindex_globs(HEADERS)


def glob_to_regex(glob: str) -> re.Pattern[str]:
    """Cloudflare `_headers` path glob -> regex over a URL path."""
    return re.compile("^" + re.escape(glob).replace(r"\*", ".*") + "$")


def built_urls(built: Path) -> list[str]:
    """Every page URL the build actually emitted, read from the rendered tree.

    Hugo writes a pretty URL as `<dir>/index.html`, so the set of directories
    containing one IS the set of served pages, with `url:` overrides, aliases and
    section indexes already resolved. That is the same reason the leak assertions
    below read generated output rather than frontmatter.
    """
    urls: list[str] = []
    for path in built.rglob("index.html"):
        rel = path.parent.relative_to(built).as_posix()
        urls.append("/" if rel == "." else f"/{rel}/")
    return urls


def urls_in(path: Path, tag: str) -> list[str]:
    """Every URL inside <tag>...</tag> in a generated XML file."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    raw = re.findall(rf"<{tag}>([^<]+)</{tag}>", text)
    return [re.sub(r"^https?://[^/]+", "", u).strip() for u in raw]


def feed_item_urls(path: Path) -> list[str]:
    """Every URL published as a feed ITEM, ignoring channel metadata.

    A feed's `<channel>` carries its OWN `<link>` — a self-reference to the
    section, not a published page. Collecting every `<link>` in the document
    therefore reports the section itself as leaking into its own feed. The
    root feed hid this because its channel link is `/`, which matches no
    noindex glob; the moment per-section feeds were read, `/newsletter/`
    flagged against `/newsletter/*` while that feed had ZERO items.

    What actually publishes a body is an `<item>`, so only item links count.
    """
    if not path.exists():
        return []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        # A feed we cannot parse is not a feed we can clear. Fail loud rather
        # than returning [] , which would read as "nothing leaked".
        raise SystemExit(
            f"[FAIL] [unparseable-feed] {path}: {exc}. This gate cannot assert "
            f"an absence in a file it could not read."
        )
    # `root.iter` rather than `channel.findall`: a feed whose items are not
    # under a <channel> would otherwise yield [] , and an empty result from this
    # function is indistinguishable from "nothing leaked" — a silent skip, which
    # is the exact class this gate exists to close.
    out = []
    for item in root.iter("item"):
        link = item.findtext("link")
        if link:
            out.append(re.sub(r"^https?://[^/]+", "", link).strip())
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--built", default="public", help="built site directory")
    args = parser.parse_args()

    built = (REPO / args.built) if not Path(args.built).is_absolute() else Path(args.built)
    sitemap = built / "sitemap.xml"
    # EVERY feed, not just the site-wide one. `config/_default/hugo.toml` sets
    # `section = ["HTML", "RSS", "trails"]`, so Hugo emits a per-section
    # index.xml alongside the root one -- 18 of them at the time this was
    # written, including public/newsletter/index.xml. Reading only the root feed
    # reopened the exact defect this gate exists to prevent: round 6 shipped the
    # newsletter pages into RSS with full body text, and the fix asserted the
    # outcome in the root feed while stopping one output format short. A page
    # excluded from the root feed can still be published in full by its section
    # feed, and the gate reported [OK].
    feeds = sorted(built.rglob("index.xml"))

    if not sitemap.exists() or not feeds:
        print(
            f"[FAIL] [no-built-tree] {sitemap} missing, or no index.xml feed under "
            f"{built}. This gate reads the GENERATED output; run "
            f"`hugo --gc --minify -e production` first. Passing without them would "
            f"prove nothing.",
            file=sys.stderr,
        )
        return 2

    globs = noindex_globs()
    if not globs:
        print(
            "[FAIL] [no-noindex-rules-found] static/_headers declares no "
            "X-Robots-Tag noindex rule, so this gate proved nothing.",
            file=sys.stderr,
        )
        return 1

    sitemap_urls = urls_in(sitemap, "loc")
    # Union across every feed, each labelled, so a violation names the feed that
    # actually published the page rather than a generic "the RSS feed".
    feed_urls: list[str] = []
    feed_of: dict[str, str] = {}
    for f in feeds:
        for u in feed_item_urls(f):
            feed_urls.append(u)
            feed_of.setdefault(u, f.relative_to(built).as_posix())
    if not sitemap_urls:
        print(
            "[FAIL] [empty-sitemap] the built sitemap lists no URLs, so this gate "
            "would pass no matter what leaked.",
            file=sys.stderr,
        )
        return 1

    # BUILD-FRESHNESS FLOOR. Every assertion below is an ABSENCE: this URL is not
    # in the sitemap, that one is not in the feed. An absence only means the rule
    # is working if the page was actually built. Against a tree that predates a
    # whole noindex route, every one of those absences held vacuously and the gate
    # printed "[OK] ... 4 noindex rule(s) enforced ... no leaks" having examined
    # zero of the pages it exists to protect -- with a plausible-looking URL count
    # in the message, which is what made it dangerous rather than merely useless.
    #
    # CI never ran that path (.github/workflows/ci.yml builds at :271 and checks at
    # :305, same job), but the local pre-push hook has no build step anywhere in
    # .pre-commit-config.yaml, and pre-publish.sh -- which does rebuild -- never
    # invokes this gate at all. So the stale-tree path was the LOCAL one.
    #
    # The floor is per-RULE, not aggregate: a tree carrying /private/ but not yet
    # /newsletter/ still yields a healthy total, so a total proves nothing about
    # the rule that matters.
    pages = built_urls(built)
    failures: list[str] = []
    enforced = 0
    covered: dict[str, int] = {}

    for glob in globs:
        if glob in EXEMPT:
            continue
        enforced += 1
        pattern = glob_to_regex(glob)

        matched_pages = [u for u in pages if pattern.match(u)]
        covered[glob] = len(matched_pages)
        if not matched_pages:
            failures.append(
                f"  [unbuilt-rule] '{glob}' matched no page in {built}, so its "
                f"absence from the sitemap and the feed proves nothing -- the "
                f"rule was never exercised. Either the built tree is STALE "
                f"(rebuild: `hugo --gc --minify -e production`), or the rule "
                f"names a route this site no longer serves and belongs in EXEMPT "
                f"with a stated reason."
            )
            continue

        for url in sitemap_urls:
            if pattern.match(url):
                failures.append(
                    f"  [sitemap] {url} is noindex via '{glob}' but is listed in "
                    f"sitemap.xml. Add `sitemap: disable` to its frontmatter."
                )
        for url in feed_urls:
            if pattern.match(url):
                failures.append(
                    f"  [feed] {url} is noindex via '{glob}' but its FULL BODY is "
                    f"published in {feed_of.get(url, 'index.xml')}. "
                    f"A noindex header does not cover the feed. Add "
                    f"`build: {{list: never, render: always}}` to its frontmatter. "
                    f"See content/private/tools/meet-recorder/index.md."
                )

    if not enforced:
        print(
            "[FAIL] [no-rules-enforced] every noindex glob was exempted, so this "
            "gate proved nothing.",
            file=sys.stderr,
        )
        return 1

    if failures:
        print(
            f"[FAIL] noindex pages leaking into the sitemap or the feed, "
            f"{len(failures)} problem(s):",
            file=sys.stderr,
        )
        for line in sorted(set(failures)):
            print(line, file=sys.stderr)
        return 1

    # Report the per-rule built-page counts, not just a total. The counts ARE the
    # evidence that each absence was measured against something.
    detail = ", ".join(f"{g} -> {covered[g]} built page(s)" for g in sorted(covered))
    print(
        f"[OK] noindex exclusion: {enforced} noindex rule(s) enforced against "
        f"{len(sitemap_urls)} sitemap URL(s) and {len(feed_urls)} feed item(s); "
        f"no leaks. Rules exercised: {detail}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
