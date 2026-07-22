#!/usr/bin/env python3
"""Frontmatter contract for hoiboy.uk posts and project pages.

Posts (content/posts/)            required: title, date, categories, tags, description
Project pages (content/consulting/) required: title, description

Phase 0 inline schema. 08_FRONTMATTER_SCHEMA.md is deferred to Phase 1
once real WordPress posts shape the schema.

Walks content/posts/ and content/consulting/, parses YAML frontmatter with
PyYAML, validates required fields. Fails loudly.

`description` became REQUIRED on 2026-07-20 (blog-priv#55 Phase 2). Before
that it sat in OPTIONAL, so 33 posts (32 legacy plus one dated on the
2026-04-07 cutoff) rendered with the site-default
meta description, so they shipped as near-duplicates of each other. Phase 1
backfilled all 33; this gate stops the field regressing. This is SEO hygiene,
not a GEO lever: nothing supports a claim that unique descriptions increase
AI citations (see the /blog skill's SEO/GEO authoring rules).

Project pages carry a SEPARATE, smaller required set: they have no
categories/tags taxonomy, and several legitimately carry no date (the
service pages set `hideDate: true`). Applying the post contract to them
would hard-fail a compliant tree.
"""
from __future__ import annotations
import argparse
import datetime
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # exercised via a subprocess in the tests
    raise SystemExit(
        "validate_frontmatter.py needs PyYAML. Install it with "
        "`pip install -r requirements-dev.txt` (or `pip install pyyaml`). "
        "Refusing to fall back to a hand-rolled parser: that reintroduces the "
        "YAML divergences blog-priv#56 removed."
    ) from exc

REQUIRED = {"title", "date", "categories", "tags", "description"}
# Project/service pages under content/consulting/ (including portfolio/<client>/).
# Intentionally NOT the post contract - see module docstring.
CONSULTING_REQUIRED = {"title", "description"}
# Optional fields (informational schema, not enforced for backward compat).
# `series` + `order` added 2026-04-26 (Issue #3) for the bake-off teaser series
# taxonomy. Posts lacking these fields continue to validate as PASS.
OPTIONAL = {"slug", "draft", "series", "order", "lastmod", "hideDate", "type"}
# Allowed category values. Sourced from config/_default/menus.toml at runtime.
# A typo like categories: [foood] would create an orphan term page no
# sidebar link reaches. Hard fail.
ALLOWED_CATEGORIES = {"food-booze", "adventure", "dance", "tech-ai", "life", "entrepreneurship", "trading"}
# Content formats Hugo renders natively. Kept identical to CONTENT_EXTS in
# scripts/check_social_cards.py: a walk narrower than this silently skips real
# pages, and a skipped page passes the contract by omission rather than by
# compliance. Matching only `index.md` would miss a flat `content/consulting/x.md`
# single page entirely.
CONTENT_EXTS = (".md", ".markdown", ".html")
ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "content" / "posts"
CONSULTING = ROOT / "content" / "consulting"


def parse_frontmatter(text: str) -> dict[str, object] | None:
    """Parse a page's YAML frontmatter with PyYAML.

    Returns the frontmatter mapping, or None when `text` has no `---...---`
    fence (a body-only file is legitimately not frontmatter). Raises
    yaml.YAMLError on a malformed fence and ValueError when the fence parses to
    something other than a mapping; check_tree turns both into a per-file
    failure rather than letting a page with unparseable frontmatter through.

    This replaced a 145-line hand-rolled parser (blog-priv#56). That parser
    stored every value as a string, so it could not tell YAML null, an empty
    block scalar, a mapping or a bool from a real description, and each shape it
    got wrong shipped a page with the site-default meta description. Nine Ralph
    rounds on #55 each hand-patched one shape and the next round found its
    sibling; PyYAML is the single oracle that ends the class. It is already a
    dependency (requirements-dev.txt, the CI install), and the differential
    test that hunted these divergences one by one is now vacuous because the
    parser IS PyYAML.

    Dates are the one value normalised: YAML types `date: 2026-04-07` as a
    datetime.date, but the rest of the contract treats date and lastmod as ISO
    strings (the lastmod<date check, the string compares), so a date/datetime
    is rendered back to its ISO string here. Nothing else is coerced: a bool,
    int, list or mapping keeps its real type so check_tree's type checks can
    reject it instead of storing it as a string that passes.
    """
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    data = yaml.safe_load(text[3:end])
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"frontmatter is not a mapping (parsed as {type(data).__name__})")
    for key, value in list(data.items()):
        if isinstance(value, datetime.date):  # datetime.datetime is a subclass too
            data[key] = value.isoformat()
    return data


def _has_value(value: object) -> bool:
    """Did the author supply a real value for this key?

    YAML null (`description:` / `null` / `~`), an empty string, an empty block
    scalar and an empty list or mapping all mean "no value" to Hugo, which then
    serves the site default - the near-duplicate this gate exists to prevent.
    A bool/int/float IS a value here (even though it is the wrong TYPE for a
    description); the scalar-type check in check_tree rejects that with a
    clearer message than "missing" would give.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def check_tree(root: Path, required: set[str], check_categories: bool,
               include_section_pages: bool = False,
               seen_descriptions: dict[str, str] | None = None) -> tuple[list[str], int]:
    """Validate every page bundle under `root` against `required`.

    Returns (failures, files_checked). A missing root is not an error - the
    tree is simply empty, which is how a fresh clone or a partial checkout
    behaves.

    Walks EVERY natively-rendered content file (CONTENT_EXTS), not just
    `index.md`. A filename-specific walk skips flat single pages such as
    `content/consulting/thing.md`, and a skipped page passes by omission
    rather than by compliance, which is a false PASS.

    `include_section_pages` controls whether `_index.*` branch bundles are
    validated. Consulting section pages are real indexable URLs, so they are
    gated; the posts section index is Hugo-generated with no source
    frontmatter to validate.
    """
    failures: list[str] = []
    if not root.exists():
        return failures, 0

    md_files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in CONTENT_EXTS
        and (include_section_pages or not p.name.startswith("_index."))
    )

    for md in md_files:
        text = md.read_text(encoding="utf-8")
        try:
            fm = parse_frontmatter(text)
        except (yaml.YAMLError, ValueError) as exc:
            # Malformed YAML (a tab-indented block continuation is the shape #56
            # cared about) or a fence that is not a mapping. The hand-rolled
            # parser silently coerced these; PyYAML surfaces them, and a page
            # whose frontmatter does not parse must fail the gate, not sail
            # through. Kept to the first line so the message stays readable.
            reason = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
            failures.append(f"{md.relative_to(ROOT)}: invalid frontmatter YAML: {reason}")
            continue
        if fm is None:
            failures.append(f"{md.relative_to(ROOT)}: no frontmatter")
            continue
        # A key present with a BLANK value is treated as missing. Hugo's
        # `.Description | default site.Params.description` sees "" as falsy and
        # serves the site default, so `description:` with nothing after it
        # produces exactly the near-duplicate this gate exists to prevent while
        # satisfying a naive key-presence check. Same reasoning for an empty
        # title, an empty list or a YAML null (see _has_value).
        present = {k for k, v in fm.items() if _has_value(v)}
        missing = required - present
        if missing:
            failures.append(f"{md.relative_to(ROOT)}: missing {sorted(missing)}")
            continue
        # Right TYPE, not just non-empty. Presence alone was not enough: Hugo
        # discards a list-valued `description` and serves the site default, so
        # `description: [a, b]` passed the check above (a non-empty list) and
        # still shipped the near-duplicate this gate exists to prevent. Proven
        # on a real build, Ralph round 23. The differential matrix in the tests
        # cannot see this class, because it compares the parser against PyYAML
        # and both agree the list is "present"; the disagreement is with HUGO,
        # a layer above YAML.
        for scalar_key in ("description", "title"):
            if scalar_key not in required:
                continue
            value = fm.get(scalar_key)
            if value is None or isinstance(value, str):
                continue
            if isinstance(value, list):
                detail = "is a list; Hugo discards it and serves the site default"
            elif isinstance(value, dict):
                detail = "is a mapping; Hugo discards it and serves the site default"
            else:
                # A bool/int/float: PyYAML types `description: true` as True and
                # `12345` as an int, and Hugo renders the literal "true" / "12345"
                # as the meta value. The old string-storing parser could not see
                # this (blog-priv#56, comment on the mapping/bool/int shapes).
                detail = (f"is a {type(value).__name__}; Hugo renders it literally, "
                          f"not as a real value")
            failures.append(
                f"{md.relative_to(ROOT)}: {scalar_key} {detail}. Use a quoted string."
            )
        # tags must be a list. A mapping-valued `tags: {a: b}` stored as a
        # string under the old parser and passed; Hugo then ranges the map and
        # emits article:tag for the map's VALUE, not its key (blog-priv#56).
        if "tags" in required:
            tags = fm.get("tags")
            if tags is not None and not isinstance(tags, list):
                failures.append(
                    f"{md.relative_to(ROOT)}: tags must be a list "
                    f"(got {type(tags).__name__}); write it as [a, b] or a block list"
                )
        if check_categories:
            cats = fm.get("categories")
            # A bare scalar (`categories: life`, no brackets) skipped the
            # allowlist entirely, because this guard only fired for a list, so
            # a typo'd category was never checked. Hugo also cannot range over
            # it and hard-fails the build, so the cost was a confusing
            # build-time template error instead of a clear gate message here.
            if cats is not None and not isinstance(cats, list):
                failures.append(
                    f"{md.relative_to(ROOT)}: categories must be a list "
                    f"(got {cats!r}); write it as [a, b] or a block list"
                )
            elif isinstance(cats, list):
                # str() so a non-string list item (`categories: [123]` -> int
                # under PyYAML) is compared, not crashed on. A numeric category
                # is not on the allowlist, so it is reported as unknown.
                unknown = set(str(c).lower() for c in cats) - ALLOWED_CATEGORIES
                if unknown:
                    failures.append(
                        f"{md.relative_to(ROOT)}: unknown categories {sorted(unknown)} "
                        f"(allowed: {sorted(ALLOWED_CATEGORIES)})"
                    )
                lowered = [str(c).lower() for c in cats]
                dupes = sorted({c for c in lowered if lowered.count(c) > 1})
                if dupes:
                    failures.append(
                        f"{md.relative_to(ROOT)}: duplicate categories {dupes}; "
                        f"the category renders once per entry, so the page shows it twice"
                    )
        # date and lastmod must be scalar dates. PyYAML renders a valid date to
        # an ISO string (parse_frontmatter coerces datetime.date), so a
        # non-string here is a mapping/list/bool - a malformed date. The old
        # hand-rolled parser rejected `date:` followed by an indented mapping as
        # "missing" because it could not represent the shape; keep catching it,
        # now with a clear message, rather than passing it to a confusing Hugo
        # build error - the same class the categories/tags guards above fix
        # (blog-priv#56). An empty `date: {}` is already caught by the
        # missing-check above (it is not present); this catches the non-empty
        # non-string shapes that ARE present.
        for date_key in ("date", "lastmod"):
            value = fm.get(date_key)
            if value is not None and not isinstance(value, str):
                failures.append(
                    f"{md.relative_to(ROOT)}: {date_key} must be a date "
                    f"(got {type(value).__name__}); write it as an ISO date like 2026-04-07"
                )
        # `lastmod` earlier than `date` publishes JSON-LD dateModified BEFORE
        # datePublished, and an `article:modified_time` that predates the post.
        # Phase 8 of this issue added the lastmod convention but gated nothing,
        # so the contradiction shipped silently: gate exit 0, Hugo exit 0
        # (Ralph round 24). That matters here specifically because the whole
        # issue is about machine-readable trust signals, and a modified-before-
        # published pair is the kind of incoherence a consumer can check.
        # String compare is correct for ISO 8601, which is why the convention
        # requires that format; anything unparseable is left to the Hugo build,
        # which rejects a non-parsable date loudly.
        lastmod, date = fm.get("lastmod"), fm.get("date")
        if isinstance(lastmod, str) and isinstance(date, str) and lastmod and date:
            if lastmod[:10] < date[:10]:
                failures.append(
                    f"{md.relative_to(ROOT)}: lastmod {lastmod[:10]} precedes date "
                    f"{date[:10]}; that publishes dateModified before datePublished"
                )
        # Presence was gated; SAMENESS was not. Two pages with an identical
        # description are the same near-duplicate this gate exists to prevent -
        # the site-default fallback is just the most common way to get there,
        # not the only one. Copy-pasting a sibling post's description passed
        # every check above. The dict is threaded across roots by main() so a
        # posts/ page and a consulting/ page cannot collide either, and it
        # holds the first path seen so the message names both sides.
        if "description" in required:
            desc = fm.get("description")
            if seen_descriptions is not None and isinstance(desc, str):
                key = " ".join(desc.split()).casefold()
                if key:
                    here = str(md.relative_to(ROOT))
                    first = seen_descriptions.get(key)
                    if first is not None and first != here:
                        failures.append(
                            f"{here}: description is identical to {first}; "
                            f"two pages sharing one description are near-duplicates"
                        )
                    else:
                        seen_descriptions[key] = here
    return failures, len(md_files)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--scope",
        choices=("all", "posts", "consulting"),
        default="all",
        help="which tree to validate (default: all)",
    )
    args = ap.parse_args(argv)

    failures: list[str] = []
    counts: list[str] = []

    # A walk that finds NOTHING is a broken walk, not a clean tree. Both of
    # these trees are non-empty in any real checkout, so a zero count means the
    # root was renamed, mistyped, or CONTENT_EXTS stopped matching - and every
    # page it should have gated then passes by omission. Ralph round 16 proved
    # this was undefended: pointing POSTS at a nonexistent path printed
    # "Frontmatter OK (0 posts)" and exited 0, sailing through pre-commit,
    # pre-publish gates 4/4a, both ci.yml steps and all four wiring tests.
    # check_tree itself stays tolerant of a missing root (it is used as a
    # library and a partial checkout is legitimately empty); the "must not be
    # empty" judgement belongs here, where the specific trees are known.
    # Shared across both roots on purpose: a posts/ page and a consulting/ page
    # with the same description are as duplicate as two posts.
    seen_descriptions: dict[str, str] = {}

    if args.scope in ("all", "posts"):
        f, n = check_tree(POSTS, REQUIRED, check_categories=True,
                          seen_descriptions=seen_descriptions)
        failures += f
        counts.append(f"{n} posts")
        if n == 0:
            failures.append(
                f"walked 0 files under {POSTS} - the posts tree is never empty, "
                "so the root or the extension filter is broken (vacuous pass)"
            )

    if args.scope in ("all", "consulting"):
        f, n = check_tree(CONSULTING, CONSULTING_REQUIRED, check_categories=False,
                          include_section_pages=True,
                          seen_descriptions=seen_descriptions)
        failures += f
        counts.append(f"{n} project pages")
        if n == 0:
            failures.append(
                f"walked 0 files under {CONSULTING} - the consulting tree is never "
                "empty, so the root or the extension filter is broken (vacuous pass)"
            )

    if failures:
        print("FRONTMATTER VALIDATION FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"Frontmatter OK ({', '.join(counts)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
