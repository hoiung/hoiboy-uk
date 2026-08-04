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
import re
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


def noindex_globs(text: str) -> list[str]:
    """Path globs in static/_headers carrying an X-Robots-Tag noindex."""
    found: list[str] = []
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("/"):
            current = line.strip()
        elif current and re.search(r"X-Robots-Tag:.*noindex", line, re.I):
            if current not in found:
                found.append(current)
    return found


def glob_to_regex(glob: str) -> re.Pattern[str]:
    """Cloudflare `_headers` path glob -> regex over a URL path."""
    return re.compile("^" + re.escape(glob).replace(r"\*", ".*") + "$")


def urls_in(path: Path, tag: str) -> list[str]:
    """Every URL inside <tag>...</tag> in a generated XML file."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    raw = re.findall(rf"<{tag}>([^<]+)</{tag}>", text)
    return [re.sub(r"^https?://[^/]+", "", u).strip() for u in raw]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--built", default="public", help="built site directory")
    args = parser.parse_args()

    built = (REPO / args.built) if not Path(args.built).is_absolute() else Path(args.built)
    sitemap = built / "sitemap.xml"
    feed = built / "index.xml"

    if not sitemap.exists() or not feed.exists():
        print(
            f"[FAIL] [no-built-tree] {sitemap} or {feed} missing. This gate reads "
            f"the GENERATED output; run `hugo --gc --minify -e production` first. "
            f"Passing without them would prove nothing.",
            file=sys.stderr,
        )
        return 2

    globs = [g for g in noindex_globs(HEADERS.read_text(encoding="utf-8"))]
    if not globs:
        print(
            "[FAIL] [no-noindex-rules-found] static/_headers declares no "
            "X-Robots-Tag noindex rule, so this gate proved nothing.",
            file=sys.stderr,
        )
        return 1

    sitemap_urls = urls_in(sitemap, "loc")
    feed_urls = urls_in(feed, "link")
    if not sitemap_urls:
        print(
            "[FAIL] [empty-sitemap] the built sitemap lists no URLs, so this gate "
            "would pass no matter what leaked.",
            file=sys.stderr,
        )
        return 1

    failures: list[str] = []
    enforced = 0

    for glob in globs:
        if glob in EXEMPT:
            continue
        enforced += 1
        pattern = glob_to_regex(glob)

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
                    f"published in index.xml, the RSS feed every page advertises. "
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

    print(
        f"[OK] noindex exclusion: {enforced} noindex rule(s) enforced against "
        f"{len(sitemap_urls)} sitemap URL(s) and {len(feed_urls)} feed item(s); "
        f"no leaks."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
