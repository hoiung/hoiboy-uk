#!/usr/bin/env python3
"""Landing-sync gate: the AI Consultancy landing must list exactly the service bundles.

hoiboy-uk#54 AC 3.2.

WHY THIS EXISTS. Adding a service to this site means editing two places that nothing
connects: the page bundle under content/hire-hoi/ai-consultancy/<slug>/, and a
`## <Service>` block on that section's _index.md landing. Nothing noticed when the
fourth service shipped on 2026-07-24 with its landing block but no propagation
anywhere else, and nothing would notice a fifth bundle landing with no block at all.
This gate closes the one half of that gap that is mechanically checkable: bundle and
block must move together.

THE MEMBERSHIP RULE IS EXPLICIT, BECAUSE NAIVE COUNT EQUALITY IS FALSE HERE.
Before this issue the landing carried 6 `## ` headings against 7 child directories,
and the two numbers were never meant to match: work-with-hoi/ and pricing-billing/
are bundles that are not services, and `## Portfolio` is a landing heading whose
bundle is a branch bundle, not a service leaf. A gate asserting len(headings) ==
len(dirs) would have been red on the day it was written. So both sides carry a
named, commented exclusion list and the comparison is set-based, not count-based.

DO NOT REWRITE THIS AGAINST A HARDCODED TUPLE. scripts/test_hub_listing.py:82
compares the blog hub against CATEGORIES, a hardcoded 7-tuple at :37-45 that never
reads the filesystem. Copying that shape here would produce a hand-maintained
constant that drifts the moment someone adds a bundle without editing it, which is
the exact drift class this gate exists to end, and a direct hit on this issue's own
"No Hardcoded Settings" prerequisite. The service set is DERIVED from the tree on
every run; only the non-service exclusions are named, and each is named because it
is a documented exception rather than a member.

WHAT BINDS A BLOCK TO A BUNDLE IS THE LINK, NOT THE HEADING TEXT. Each service block
carries a `[Read the full offer]({{< ref "/hire-hoi/ai-consultancy/<slug>" >}})`, and
that slug is compared against the directory names. The heading is then checked against
that bundle's frontmatter title on top, so the landing and the page cannot disagree
about what the service is called.

The first cut of this gate compared heading text against frontmatter title alone. Its
own mutation test caught that renaming the bundle directory left the gate GREEN, since
the moved directory kept its title and still matched the heading - the exact defect
AC 3.2 direction (b) names. Comparing on the slug is what makes that mutation red.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

# The "Read the full offer" link inside a landing block, e.g.
#   [Read the full offer]({{< ref "/hire-hoi/ai-consultancy/ai-adoption-talk" >}})
REF_RE = re.compile(r'\{\{<\s*ref\s+"/hire-hoi/ai-consultancy/([A-Za-z0-9._-]+)"')

REPO_ROOT = Path(__file__).resolve().parent.parent
SECTION = REPO_ROOT / "content" / "hire-hoi" / "ai-consultancy"
LANDING = SECTION / "_index.md"

# Child bundles under the section that are NOT services. Each is an exception with a
# reason, not a convenience filter.
NON_SERVICE_SLUGS = {
    "work-with-hoi": "the front door / who-I-am page, not an offer",
    "pricing-billing": "the shared pricing page for every offer, not an offer itself",
    "portfolio": "a branch bundle of client case studies, not an offer",
}

# `## ` headings on the landing that are NOT services, for the same reason.
NON_SERVICE_HEADINGS = {
    "Pricing & Billing": "links the shared pricing page",
    "Portfolio": "links the client case-study branch",
}


def _rel(path: Path) -> str:
    """Repo-relative path for messages, tolerating a fixture tree outside the repo.

    The tests point SECTION/LANDING at a temp copy so they can reintroduce the real
    defects without mutating the working tree; a bare relative_to(REPO_ROOT) would
    raise ValueError there and the gate would fail for the wrong reason.
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _frontmatter_title(index_md: Path) -> str | None:
    """Return the frontmatter `title` of a page bundle, or None if unparseable."""
    text = index_md.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    meta = yaml.safe_load(text[3:end])
    if not isinstance(meta, dict):
        return None
    title = meta.get("title")
    return title if isinstance(title, str) else None


def service_bundles() -> dict[str, str]:
    """Map slug -> frontmatter title for every SERVICE bundle, derived from the tree."""
    found: dict[str, str] = {}
    for child in sorted(SECTION.iterdir()):
        if not child.is_dir() or child.name in NON_SERVICE_SLUGS:
            continue
        index_md = child / "index.md"
        if not index_md.is_file():
            continue
        title = _frontmatter_title(index_md)
        if title is None:
            print(
                f"check-landing-sync: {_rel(index_md)} has no parseable "
                f"frontmatter title, so it cannot be matched to a landing block.",
                file=sys.stderr,
            )
            continue
        found[child.name] = title
    return found


def landing_blocks() -> list[tuple[str, str | None]]:
    """Return (heading, linked-slug) for each `## ` block that claims to be a service.

    The link, not the heading text, is the binding half. An earlier cut of this gate
    matched heading against frontmatter title only, and its own mutation test caught
    that renaming the bundle directory left the gate GREEN: the moved directory kept
    its title, so the title still matched. The slug is what the reader actually
    follows, so the slug is what is compared, with the title checked on top.
    """
    blocks: list[tuple[str, str | None]] = []
    heading: str | None = None
    slug: str | None = None
    for line in LANDING.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("## "):
            if heading is not None:
                blocks.append((heading, slug))
            candidate = line[3:].strip()
            heading = None if candidate in NON_SERVICE_HEADINGS else candidate
            slug = None
        elif heading is not None and slug is None:
            match = REF_RE.search(line)
            if match:
                slug = match.group(1)
    if heading is not None:
        blocks.append((heading, slug))
    return blocks


def main() -> int:
    if not LANDING.is_file():
        print(f"check-landing-sync: {LANDING} does not exist.", file=sys.stderr)
        return 1

    bundles = service_bundles()
    blocks = landing_blocks()
    linked = {slug for _, slug in blocks if slug}

    failures = []

    # Direction 1: a service bundle exists with no block linking to it.
    for slug, title in sorted(bundles.items()):
        if slug not in linked:
            failures.append(
                f"orphan bundle: service bundle '{slug}' (title {title!r}) has no "
                f"'## {title}' block linking to it on {_rel(LANDING)}. A service "
                f"nobody can find from the landing is not shipped."
            )

    # Direction 2: a block advertises a service whose bundle is not there.
    for heading, slug in blocks:
        if slug is None:
            failures.append(
                f"orphan heading: '## {heading}' on {_rel(LANDING)} carries no "
                f"'Read the full offer' link, so nothing ties it to a bundle."
            )
        elif slug not in bundles:
            failures.append(
                f"orphan heading: '## {heading}' on {_rel(LANDING)} links to "
                f"'{slug}', which is not a service bundle. Its 'Read the full offer' "
                f"link points at a page that is not there."
            )
        elif bundles[slug] != heading:
            failures.append(
                f"name mismatch: '## {heading}' on {_rel(LANDING)} links to bundle "
                f"'{slug}', whose frontmatter title is {bundles[slug]!r}. The landing "
                f"and the page must agree on what the service is called."
            )

    # Duplicate titles would let one block satisfy two bundles.
    if len(set(bundles.values())) != len(bundles):
        failures.append(
            "duplicate service titles across bundles: "
            f"{sorted(bundles.items())} - one landing block cannot stand for two services."
        )

    if failures:
        print(
            "::error::Landing and service bundles are out of sync "
            f"({len(failures)} problem(s)):",
            file=sys.stderr,
        )
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        print(
            "Fix by adding the missing `## <title>` block, adding the missing bundle, "
            "or - if the page is genuinely not an offer - naming it in "
            "NON_SERVICE_SLUGS / NON_SERVICE_HEADINGS with a reason.",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: landing lists exactly the {len(bundles)} service bundle(s) "
        f"({', '.join(sorted(bundles))}); "
        f"{len(NON_SERVICE_SLUGS)} non-service bundle(s) excluded by name."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
