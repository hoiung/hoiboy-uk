#!/usr/bin/env python3
"""Parse the rendered Read Next box and post front matter (blog-priv#66 AC 0.1).

ONE parser, imported by both the Phase 0 baseline capture and
`scripts/test_related_ranking.py`, so the before/after comparison at AC 3.4 is
like-for-like. Two parsers would let the baseline and the test disagree about
what a box contains, which is exactly the comparison the issue rests on.

DENOMINATOR, load-bearing. Every count here is over the posts that RENDER a box
- the bundles under `content/posts/` - never the 87 directories under
`public/blogs/`. The extra 7 are `/blogs/<category>/` landing pages, which can
never appear in a box because `related-posts.html` draws only from
`site.RegularPages "Section" "posts"`. Counting over 87 reports all 7 landings
as permanently zero-inbound and inflates the real figure from 2 to 9.

TWO FRONT-MATTER TRAPS, both verified on the live corpus, both silent:

  * SHAPE. `content/posts/entrepreneurship-in-a-nutshell/index.md` writes `tags:`
    and `categories:` as block-style YAML lists rather than inline arrays. An
    inline-array regex returns 214 distinct tags / 417 applications; the correct
    figures via PyYAML are 218 / 423. Hence PyYAML, not a regex - reached here
    through `validate_frontmatter.parse_frontmatter`, which is the repo's single
    front-matter oracle rather than a second copy of the same fence logic.

  * TYPE. PyYAML fixes the shape trap and CAUSES this one.
    `content/posts/the-sun-had-set-for-2014/index.md` carries `2014` and `2015`
    as tags, which `yaml.safe_load` returns as `int`, not `str`. A bare
    `.lower()` raises AttributeError and a `sorted()` over mixed types raises
    TypeError. Hence `_norm_terms` coerces to `str` BEFORE lowering or sorting.

Library + CLI. As a CLI it writes the baseline artefact:

    python3 scripts/readnext_parse.py --out /tmp/readnext-baseline-before.json

Exit 0 = every post parsed and every box found. Exit 1 = a named failure.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "content" / "posts"

# Sibling import, so `scripts/` must be importable however this module was
# reached: as a CLI (`python3 scripts/readnext_parse.py`, which puts scripts/ on
# the path for free), via `test_related_ranking.py` (which inserts it itself), or
# by pytest naming this file directly on the command line - which does NOT, and
# is exactly how CI runs it.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_frontmatter import parse_frontmatter  # noqa: E402

_BOX_RE = re.compile(r'<ul class="read-next-list">(.*?)</ul>', re.S)
_HREF_RE = re.compile(r'<li><a href="([^"]+)"')


class PostMeta(NamedTuple):
    """One post's ranking-relevant front matter. Terms are already normalised.

    `slug` and `bundle` are NOT interchangeable and both are needed. Two posts
    override the URL with a front-matter `slug:` key - `2026-04-07-foundation`
    serves at `/blogs/foundation/` and `ai-jargon-for-noobs` at
    `/blogs/ai-jargon-for-newbies/`. Rendered hrefs carry the URL slug, front
    matter lives at the bundle path, so keying either map on the wrong one
    silently drops those two posts from the denominator.
    """

    slug: str
    bundle: str
    date: str
    tags: frozenset[str]
    categories: frozenset[str]


def _norm_terms(value: object) -> frozenset[str]:
    """A `tags:`/`categories:` value as a set of normalised terms.

    Coerces to `str` first: the TYPE trap above means a raw value can be an int.
    A scalar (`tags: zouk`) is treated as a one-element list, which is what Hugo
    itself does. Empty strings are dropped so a stray `- ` cannot become a term
    that silently matches nothing.
    """
    if value is None:
        return frozenset()
    items = value if isinstance(value, (list, tuple)) else [value]
    return frozenset(t for t in (str(i).strip().lower() for i in items) if t)


def frontmatter(path: Path) -> dict:
    """The YAML front-matter block of a page bundle, parsed.

    Delegates the fence-strip and the PyYAML load to
    `validate_frontmatter.parse_frontmatter`, which already owns that job for
    the repo's own front-matter gate. Re-deriving the fence regex here gave the
    tree two parsers that could disagree about what front matter IS - the exact
    divergence class blog-priv#56 spent nine Ralph rounds killing when it
    replaced a 145-line hand-rolled parser with PyYAML. One oracle. (Ralph
    Tier 2, AP #10.)

    What this wrapper adds is the LOUD contract: `parse_frontmatter` returns
    None for a page with no fence, because a body-only file is legitimately not
    front matter in its context. Here it is not - a post with no front matter
    has no tags, and silently returning {} would drop it from every count
    computed downstream while the denominator still said 80.
    """
    data = parse_frontmatter(path.read_text(encoding="utf-8"))
    if data is None:
        raise ValueError(f"{path}: no YAML front-matter block")
    return data


def post_meta(posts: Path = POSTS) -> dict[str, PostMeta]:
    """Every post bundle, keyed by URL slug. This set IS the denominator.

    Keyed by URL slug because that is what a rendered `<a href>` carries, so it
    is the only key that joins a box back to the front matter that produced it.
    """
    out: dict[str, PostMeta] = {}
    for path in sorted(posts.glob("*/index.md")):
        data = frontmatter(path)
        bundle = path.parent.name
        slug = str(data.get("slug") or bundle).strip()
        if slug in out:
            raise ValueError(
                f"{path}: URL slug {slug!r} collides with bundle {out[slug].bundle!r}; "
                f"two posts cannot serve the same URL"
            )
        out[slug] = PostMeta(
            slug=slug,
            bundle=bundle,
            date=str(data.get("date", "")),
            tags=_norm_terms(data.get("tags")),
            categories=_norm_terms(data.get("categories")),
        )
    return out


def read_next_slugs(html: str) -> list[str] | None:
    """The slugs linked in the Read Next box, in rendered order.

    Returns None when the page carries NO box at all, which is a different
    state from a box that rendered empty and must not be collapsed into it.
    The match is BLOCK-SCOPED on purpose: a document-wide href scan picks up
    the sidebar and reports links on pages that have no box (a bare
    `grep -c '<li><a href='` returns 1 on `public/blogs/dance/index.html`).
    """
    m = _BOX_RE.search(html)
    if not m:
        return None
    return [href.strip("/").split("/")[-1] for href in _HREF_RE.findall(m.group(1))]


def read_next_map(built: Path, slugs: list[str]) -> dict[str, list[str]]:
    """slug -> the slugs its rendered box links to, for every post in `slugs`.

    A post whose page is missing, or which renders no box, is a failure rather
    than an omission - silently skipping it would shrink the denominator and
    flatter every statistic derived from it.
    """
    out: dict[str, list[str]] = {}
    missing: list[str] = []
    boxless: list[str] = []
    for slug in slugs:
        page = built / "blogs" / slug / "index.html"
        if not page.is_file():
            missing.append(slug)
            continue
        links = read_next_slugs(page.read_text(encoding="utf-8"))
        if links is None:
            boxless.append(slug)
            continue
        out[slug] = links
    if missing:
        raise FileNotFoundError(
            f"{len(missing)} post(s) have no rendered page under {built}/blogs/: "
            f"{missing[:5]} (run `hugo --gc --minify -e production` first)"
        )
    if boxless:
        raise ValueError(
            f"{len(boxless)} post(s) render no read-next-list block: {boxless[:5]}"
        )
    return out


def inbound_counts(rn_map: dict[str, list[str]], slugs: list[str]) -> dict[str, int]:
    """slug -> how many boxes link TO it. Every post in `slugs` gets a key,
    including the zeros - a dict built only from observed links would omit the
    orphans, which are the figure this issue reports."""
    counts = {slug: 0 for slug in slugs}
    for links in rn_map.values():
        for target in links:
            if target in counts:
                counts[target] += 1
    return counts


def summarise(rn_map: dict[str, list[str]], slugs: list[str]) -> dict:
    """The three headline figures, with the denominator carried alongside them
    so no consumer can quote one without it (the denominator trap, above)."""
    counts = inbound_counts(rn_map, slugs)
    hub_slug = max(counts, key=lambda s: (counts[s], s))
    zero = sorted(s for s, n in counts.items() if n == 0)
    return {
        "denominator": len(slugs),
        "hub_slug": hub_slug,
        "hub_count": counts[hub_slug],
        "zero_inbound": zero,
        "zero_inbound_count": len(zero),
        "reachable": len(slugs) - len(zero),
    }


def build_baseline(built: Path) -> tuple[dict, dict]:
    """(per-post artefact keyed by slug, summary). The artefact has exactly one
    entry per post so `len(json)` IS the denominator."""
    meta = post_meta()
    slugs = sorted(meta)
    rn_map = read_next_map(built, slugs)
    counts = inbound_counts(rn_map, slugs)
    artefact = {
        slug: {
            "bundle": meta[slug].bundle,
            "read_next": rn_map[slug],
            "inbound": counts[slug],
            "tags": sorted(meta[slug].tags),
            "categories": sorted(meta[slug].categories),
            "date": meta[slug].date,
        }
        for slug in slugs
    }
    return artefact, summarise(rn_map, slugs)


def main(argv: list[str] | None = None) -> int:
    """`argv=None` reads sys.argv, which under pytest is the pytest command line
    (file paths + flags), so argparse exits 2 before anything runs. The explicit
    [] from a pytest entry point is what makes that safe."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--built", default="public", help="built site root (default: public)")
    ap.add_argument("--out", default=None, help="write the baseline artefact to this path")
    args = ap.parse_args(argv)
    built = Path(args.built)
    if not built.is_absolute():
        built = ROOT / built

    if not built.is_dir():
        print(f"FAIL: built site not found at {built} (run `hugo` first)", file=sys.stderr)
        return 1

    try:
        artefact, summary = build_baseline(built)
    except (ValueError, FileNotFoundError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    if args.out:
        out = Path(args.out)
        out.write_text(json.dumps(artefact, indent=2, sort_keys=True), encoding="utf-8")
        summary_path = out.with_suffix(".summary.json")
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote {out} ({len(artefact)} posts) and {summary_path}")

    print(
        f"OK: parsed {len(artefact)} posts (denominator {summary['denominator']}); "
        f"hub {summary['hub_slug']} = {summary['hub_count']} of {summary['denominator']}; "
        f"zero-inbound {summary['zero_inbound_count']} {summary['zero_inbound']}; "
        f"reachable {summary['reachable']}"
    )
    return 0


def test_readnext_parse() -> None:
    """pytest entry point: the parser survives every post in the corpus,
    including both front-matter traps (AC 0.2)."""
    assert main([]) == 0


if __name__ == "__main__":
    sys.exit(main())
