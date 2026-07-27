#!/usr/bin/env python3
"""The site ships a real 404, so a dead URL cannot soft-404 as HTTP 200.

blog-priv#64.

The defect this exists to stop: hoiboy.uk had NO `layouts/404.html`, so Hugo
emitted no `public/404.html`. Cloudflare Pages serves a 404 status only when the
build output carries a root `404.html`; without one it falls through and answers
every unmatched path with the site's own page HTML at HTTP 200.

That is invisible to a human, which is exactly why it survived so long: the page
renders, so nothing looks wrong. It is not invisible to anything automated:

  * a crawler is told every typo'd URL is a real, indexable page whose content
    duplicates the homepage;
  * a link checker can never fail, because no URL ever returns a failing status,
    so `lychee` and `validate_internal_links.py` both pass over genuinely dead
    links;
  * `static/_redirects` had to carry a bare slash-less rule beside every wildcard
    purely to work around it, and says so twice in its own comments.

Three checks, because each catches a different way of losing the fix:

  A. SOURCE  - `layouts/404.html` exists. Deleting it is the original defect.
  B. BUILT   - a build emits `public/404.html` AND that file carries the
               `data-page="404"` marker the template's own content block emits.
               A template can exist and still render nothing (wrong block name,
               empty define), which check A cannot see. The marker is what makes
               this discriminating: a byte-size floor was tried here first and
               PASSED the blank-block mutation, because an empty block still
               renders the entire shell - sidebar, footer and brand heading are
               already several KB before the page says a word.
  C. LINKS   - every internal link ON the 404 page resolves in the built tree.
               A 404 page that itself links to dead URLs is worse than none: it
               is the one page a lost reader is guaranteed to be looking at.
               This check caught a fabricated `/about/` link during authoring.

Two lanes, because checks B and C need a build and pre-commit does not have one:

  pre-commit   `--source-only`  -> check A. Catches deletion of the template the
                                   moment it is staged, with no build required.
  CI / publish  (no flag)       -> A + B + C against the built tree.

`--source-only` is an explicit flag, never an automatic fallback on a missing
build: a gate that silently downgrades itself when the build is absent reports
success for work it did not do.

Usage:  python3 scripts/test_404.py [--built public] [--source-only]
Exit 0 = pass. Exit 1 = a named failure. Exit 2 = no build to check.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "layouts" / "404.html"

# Emitted by the 404 template's own content block (layouts/404.html), so it is
# present only when that block actually rendered. Deliberately NOT a byte-size
# floor: the shared shell alone is several KB, so a size check passes even when
# the content block is empty (verified by mutation, not assumed).
CONTENT_MARKER = 'data-page="404"'

# Markers that only layouts/baseof.html can put on the page: the doctype and
# <div class="layout"> come from the shell itself, the sidebar from its partial.
# CONTENT_MARKER alone cannot tell a page that rendered THROUGH the shell from a
# standalone template that merely carries the attribute, because the marker
# lives in the content block either way.
#
# That gap was real, not hypothetical. Replacing layouts/404.html with a bare
# <article data-page="404"> carrying two working links, no `define "main"` and
# no partials, produced a 160-byte public/404.html with no doctype, no head, no
# stylesheet and no navigation, and every check here still exited 0. The issue's
# own Expected Behavior ("The 404 page uses the site shell so a lost reader has
# real navigation") had no gate behind it at all.
SHELL_MARKERS = ("<!doctype html>", 'class="layout"', 'class="sidebar')

# Cloudflare Pages also serves this template as an ordinary asset at /404.html,
# which 308-redirects to /404 and answers HTTP 200. Without a robots rule that
# is an indexable page titled "Page not found" - the same soft-200 class this
# whole gate exists to eliminate, just parked at one fixed URL instead of spread
# across every dead path. static/_headers is where the site already keeps that
# kind of rule (see the thanks-page block).
HEADERS = ROOT / "static" / "_headers"


def noindex_globs() -> list[str]:
    """Path globs `static/_headers` marks noindex, via the repo's existing parser.

    Reused rather than re-implemented, deliberately. The first version of this
    check hand-rolled `re.compile(r"^/404\\*?\\s*$\\s+^\\s*X-Robots-Tag:\\s*noindex")`,
    which requires the header line to sit IMMEDIATELY after the path line. That
    is not how Cloudflare's `_headers` works: a block carries any number of
    directives in any order, and this very file already has a four-directive
    block (`/private/tools/meet-recorder/*`). So reordering the directives under
    `/404*` -- a functionally identical edit -- would have false-FAILED the gate,
    and two parsers for one file would have disagreed about the same contract.

    `check_social_cards.py` already scans this file correctly for exactly this
    purpose. One file, one parser.
    """
    spec = importlib.util.spec_from_file_location(
        "check_social_cards", ROOT / "scripts" / "check_social_cards.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.parse_noindex_globs(HEADERS)

# The 404 page's OWN content block, isolated from the shared shell. Check C is
# scoped to this and not to the whole document, which is a correctness fix and
# not a tidy-up: the shared sidebar puts 11 root-relative nav links on every page
# of the site, so a whole-document scan made the "no navigation links at all"
# guard below unreachable, and let the page's entire "Try one of these" escape
# list be deleted while this gate still reported "every navigation link on it
# resolves". Proven by mutation: removing the <ul> wholesale exited 0.
#
# The sidebar's own links are not skipped work, they are covered site-wide by
# scripts/validate_internal_links.py. What only this gate can check is the escape
# hatch the 404 page adds for a reader who is already lost.
CONTENT_BLOCK = re.compile(
    r'<article[^>]*\bdata-page="404"[^>]*>(.*?)</article>', re.S)


def site_base() -> str:
    """baseURL from config, so an absolute self-link is not invisible to check C."""
    cfg = (ROOT / "config" / "_default" / "hugo.toml").read_text(encoding="utf-8")
    m = re.search(r'^\s*baseURL\s*=\s*["\']([^"\']+)["\']', cfg, re.M)
    return m.group(1).rstrip("/") if m else ""


# Matches a root-relative href AND the same link written absolutely against the
# site's own baseURL, normalising both to a path. A root-relative-only pattern
# went invisible the moment a link was written with absURL/permalink, which is a
# routine refactor, so the gate would have silently stopped checking.
HREF = re.compile(
    r'href="(?:' + re.escape(site_base()) + r')?(/[^"]*)"' if site_base()
    else r'href="(/[^"]*)"')

# Asset URLs are emitted by the shared shell (fingerprinted CSS, images,
# favicon, feeds) and are verified by the site's other gates. This check is
# about NAVIGATION links on the 404 page - the ones a lost reader clicks.
ASSET_PREFIXES = ("/css/", "/js/", "/images/", "/vendor/", "/fonts/")
ASSET_SUFFIXES = (".css", ".js", ".png", ".jpg", ".jpeg", ".webp", ".svg",
                  ".ico", ".xml", ".json", ".txt")


def resolves(url: str, public: Path) -> bool:
    """True when `url` corresponds to something the built tree actually serves."""
    rel = url.lstrip("/")
    for candidate in (public / rel / "index.html", public / rel, public / f"{rel.rstrip('/')}.html"):
        if candidate.is_file():
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--built", default="public", help="built output dir (default: public)")
    ap.add_argument("--source-only", action="store_true",
                    help="check A only (template present); for the pre-commit lane, "
                         "which has no build. Never used as a fallback.")
    args = ap.parse_args(argv)
    public = (ROOT / args.built) if not Path(args.built).is_absolute() else Path(args.built)

    failures: list[str] = []

    # A. SOURCE
    if not SOURCE.is_file():
        failures.append(
            f"{SOURCE.relative_to(ROOT)} is missing. Without it Hugo emits no "
            "public/404.html and Cloudflare Pages answers every dead URL with "
            "HTTP 200 plus page HTML (a soft-404)."
        )

    # E. NOINDEX. A source-file rule, so it runs in every lane including
    # pre-commit, which has no build.
    if not HEADERS.is_file():
        failures.append(f"{HEADERS.relative_to(ROOT)} is missing, so the 404 "
                        "page cannot be kept out of the search index.")
    elif not any(g.rstrip("*").rstrip("/") in ("/404", "") and g.startswith("/404")
                 for g in noindex_globs()):
        failures.append(
            "static/_headers has no `X-Robots-Tag: noindex` rule for /404*. "
            "Cloudflare serves this template at /404.html -> 308 -> /404 with "
            "HTTP 200, so without that rule the site publishes an indexable "
            "page titled 'Page not found' - the soft-200 this gate exists to "
            "prevent, relocated rather than removed."
        )

    if args.source_only:
        if failures:
            print("404 GATE FAILED:", file=sys.stderr)
            for f in failures:
                print(f"  - {f}", file=sys.stderr)
            return 1
        print("404 gate: OK (source-only; template present. Built-output and link "
              "checks run in CI against a real build).")
        return 0

    built = public / "404.html"
    if not public.is_dir():
        print(f"no build at {public} - run `hugo --minify` first", file=sys.stderr)
        return 2

    # B. BUILT
    if not built.is_file():
        failures.append(
            f"{args.built}/404.html was not emitted by the build. Cloudflare Pages "
            "needs this exact file at the output root to return a 404 status."
        )
    else:
        html = built.read_text(encoding="utf-8", errors="replace")
        if CONTENT_MARKER not in html:
            failures.append(
                f"{args.built}/404.html does not carry {CONTENT_MARKER}, so the "
                "template's content block rendered nothing. The file exists and is "
                "not small (the shared shell fills it), but the page says nothing "
                "to the reader."
            )

        # E2. NOINDEX, second layer, in the page itself.
        #
        # static/_headers (check E) is authoritative, but it is one file away from
        # a reformat that silently stops matching, and nothing about a header is
        # visible in the built artefact. The meta tag is, so assert it here.
        #
        # Also: no canonical. Hugo hard-codes this page's output filename as
        # 404.html regardless of the site's clean-URL permalinks, so .Permalink is
        # /404.html, which Cloudflare 308-redirects to /404. A canonical pointing
        # at a redirect is wrong anywhere, and a deliberately non-indexable page
        # should not declare one at all.
        if 'name="robots"' not in html or "noindex" not in html:
            failures.append(
                f"{args.built}/404.html carries no `noindex` robots meta tag. "
                "layouts/_partials/head.html emits one for .Kind == \"404\"; if "
                "that guard is gone, the only thing keeping this page out of the "
                "index is static/_headers, and a single reformat there would "
                "publish an indexable page titled 'Page not found'."
            )
        if 'rel="canonical"' in html:
            failures.append(
                f"{args.built}/404.html declares a canonical URL. Hugo emits "
                "https://hoiboy.uk/404.html there, which 308-redirects to /404, so "
                "it points at a redirect; and a page this deliberately "
                "non-indexable should not declare a canonical at all."
            )

        # D. SHELL. See SHELL_MARKERS: proves the page rendered THROUGH
        # layouts/baseof.html rather than as a standalone template.
        missing = [m for m in SHELL_MARKERS if m not in html]
        if missing:
            failures.append(
                f"{args.built}/404.html is missing {missing}, so it did not "
                "render through layouts/baseof.html. It carries the content "
                "marker but not the site shell, which means no head, no "
                "stylesheet and no sidebar: a lost reader gets a bare block of "
                "text with no way out. Use `{{ define \"main\" }}`."
            )

        # C. LINKS, scoped to the page's own content block (see CONTENT_BLOCK).
        block = CONTENT_BLOCK.search(html)
        if not block:
            failures.append(
                f"{args.built}/404.html carries {CONTENT_MARKER} but its "
                "<article> block could not be isolated, so the escape links "
                "cannot be checked. Do not widen this check back to the whole "
                "document: the shared sidebar's links would make it pass "
                "unconditionally."
            )
        else:
            nav = sorted({
                u for u in HREF.findall(block.group(1))
                if not u.startswith(ASSET_PREFIXES)
                and not u.lower().endswith(ASSET_SUFFIXES)
            })
            if not nav:
                failures.append(
                    "the 404 page's own content offers no navigation links at all - "
                    "a dead end for a lost reader. The shared sidebar does not count: "
                    "every page has it, so it cannot tell a useful 404 from a useless "
                    "one."
                )
            for u in nav:
                if not resolves(u, public):
                    failures.append(
                        f"the 404 page links to {u}, which the build does not serve. "
                        "The one page a lost reader is guaranteed to see must not itself "
                        "contain dead links."
                    )

    if failures:
        print("404 GATE FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"404 gate: OK (source template present; {args.built}/404.html emitted; "
          "every navigation link on it resolves).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
