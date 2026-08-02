#!/usr/bin/env python3
"""Parse the rendered Read Next box and post front matter (blog-priv#66 AC 0.1).

ONE parser, imported by both the Phase 0 baseline capture and
`scripts/test_related_ranking.py`, so the before/after comparison at AC 3.4 is
like-for-like. Two parsers would let the baseline and the test disagree about
what a box contains, which is exactly the comparison the issue rests on.

DENOMINATOR, load-bearing. Every count here is over the POSTS - the bundles under
`content/posts/`, resolved to `public/blogs/<slug>/index.html` - never the 87
directories under `public/blogs/`. The extra 7 are `/blogs/<category>/` landing
pages, which can never appear in a box because `related-posts.html` draws its
candidates only from `site.RegularPages "Section" "posts"`. Counting over 87
reports all 7 landings as permanently zero-inbound and inflates the real figure
from 2 to 9.

State that as "the posts", NOT as "the pages that render a box". The two are the
same set only while `related-posts.html` is gated to the posts section, and for
one release it was not: the box rendered on 18 categoryless singular pages
(legal, hire-hoi, the unlisted tool page) and this module could not see any of
them, because the path it builds is `public/blogs/<slug>/` by construction. Every
figure it produced stayed correct for posts while being wrong for the site - the
hub read 11 of 81 when the site-wide truth was 26. A denominator defined by what
the parser LOOKS at cannot detect something appearing outside it, so the gate for
that lives in `test_related_ranking.check_box_is_posts_only`, which walks the
built tree directly instead of coming through here.

TWO FRONT-MATTER TRAPS, both verified on the live corpus, both silent:

  * SHAPE. `content/posts/entrepreneurship-in-a-nutshell/index.md` writes `tags:`
    and `categories:` as block-style YAML lists rather than inline arrays. An
    inline-array regex returns 214 distinct tags / 417 applications against the
    correct 218 / 423 (measured 2026-08-01 at base 9179b55, BEFORE this issue's
    merges took distinct tags to 209; the pair is quoted as-of because
    what matters is the 4-tag gap the regex opens, not either total). Hence
    PyYAML, not a regex - reached here through
    `validate_frontmatter.parse_frontmatter`, the repo's single front-matter
    oracle, rather than a second copy of the same fence logic.

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
# reached. All three of today's routes already provide it - a CLI run puts the
# script's own dir on the path, `test_related_ranking.py` inserts it, and
# pytest's default `prepend` import mode inserts the rootdir of a directly-named
# file. This line is insurance against the fourth: `--import-mode=importlib`,
# which CI does not use today and which would break the import silently if it
# ever did.
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

    What this wrapper adds is the LOUD contract: a post with no usable front
    matter has no tags, so letting it through would drop it from every count
    computed downstream while the denominator still said 80.

    The guard is `not data`, NOT `data is None`, and the difference is the whole
    point. `parse_frontmatter` returns None only for a missing fence; an EMPTY
    one (`---\\n---`), a whitespace-only one, and an explicit `null` all come
    back as `{}`, which is falsy but not None. A `data is None` guard passes all
    three straight through as a post with zero tags - silently, which is the
    exact outcome this docstring claims to prevent. (Ralph Tier 3 caught the
    wrapper asserting a contract it had stopped implementing.)
    """
    data = parse_frontmatter(path.read_text(encoding="utf-8"))
    if not data:
        raise ValueError(f"{path}: no usable YAML front-matter block")
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


def test_frontmatter_guard_is_loud(tmp_path) -> None:
    """All four degenerate front-matter shapes raise, none is waved through.

    The guard is `not data`, not `data is None`, and the difference is the whole
    reason this test exists: `parse_frontmatter` returns None ONLY for a missing
    fence, while an empty fence, a whitespace-only one and an explicit `null` all
    come back as `{}` - falsy but not None. A `data is None` guard passes those
    three straight through as a post with zero tags, silently, which is exactly
    the outcome `frontmatter`'s docstring promises to prevent.

    That guard was corrected in 7884906 on the strength of an ad-hoc check that
    was never persisted; Ralph round 3 Tier 2 pointed out the contract had no test
    behind it. A hand-run check proves the code once. This proves it every build.
    """
    # Measured, not assumed: `missing-fence` returns None, the other three return
    # `{}`. A TAB inside the fence is deliberately not in this set - PyYAML rejects
    # tabs as indentation and raises ScannerError before the guard is ever reached,
    # which is loud by a different mechanism and would test PyYAML, not this guard.
    shapes = {
        "missing-fence": "no front matter here\n",
        "empty-fence": "---\n---\n",
        "whitespace-only-fence": "---\n   \n\n---\n",
        "explicit-null-fence": "---\nnull\n---\n",
    }
    for label, text in shapes.items():
        path = tmp_path / f"{label}.md"
        path.write_text(text, encoding="utf-8")
        try:
            frontmatter(path)
        except ValueError:
            continue
        raise AssertionError(
            f"{label}: frontmatter() returned instead of raising. A post with no "
            f"usable front matter has no tags, so letting it through drops it from "
            f"every count computed downstream while the denominator still says 80."
        )

    # And the guard is not simply "raise on everything": a real fence still parses.
    good = tmp_path / "good.md"
    good.write_text("---\ntitle: t\ntags: [zouk]\n---\nbody\n", encoding="utf-8")
    assert frontmatter(good)["tags"] == ["zouk"]


if __name__ == "__main__":
    sys.exit(main())
