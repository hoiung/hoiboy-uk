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


def noindex_covers_404(globs: list[str]) -> bool:
    """True when one of `globs` names the 404 page itself.

    `/404`, `/404/` and `/404*` are three spellings of the same rule and all
    count. Two near-misses deliberately do not:

      `/404.html`  Cloudflare 308-redirects that asset path to `/404`, and it is
                   `/404` that answers HTTP 200. A rule pinned to the `.html`
                   form leaves the URL a crawler actually lands on uncovered.
      `/*`         a site-wide blanket rule would technically cover the 404, but
                   the gate requires the rule to NAME the page. Inheriting it
                   means a later narrowing of the blanket silently un-covers the
                   404, with nothing connecting the two edits.

    Extracted from an inline expression in `main()` at Ralph round 2 so it could
    be tested at all: it had none of the shapes above pinned by anything, on a
    predicate whose whole job is telling near-misses apart. The original also
    accepted a second empty-string form, which was unreachable -- reaching it
    needs a glob made only of `/` and `*`, which cannot also start with `/404` --
    so it is gone rather than carried as an untestable branch.
    """
    return any(g.startswith("/404") and g.rstrip("*").rstrip("/") == "/404"
               for g in globs)

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
    elif not noindex_covers_404(noindex_globs()):
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


# ---------------------------------------------------------------------------
# Unit tests for the noindex helpers above.
#
# pytest collects this file by name and, until Ralph round 2, found NOTHING in
# it: it is a CLI gate wearing a `test_` prefix, so the suite counted it as a
# test file while it asserted nothing at all. Thirteen other gates under
# scripts/ are both a CLI and a pytest module, so the coverage goes here in the
# house pattern rather than into a companion file that would have to be called
# `test_test_404.py`.
#
# Deliberately NO `import pytest`. pre-commit runs this file as a bare CLI
# (`--source-only`, hook `check-404`), and a gate that cannot start unless a
# test framework is installed fails for a reason that has nothing to do with the
# site. Plain `test_*` functions and the `tmp_path` / `monkeypatch` fixtures need
# no import, so the CLI stays independent of pytest.
#
# CI runs these through an explicit pytest step, SEPARATE from the existing
# `python3 scripts/test_404.py --built public` step -- that one is the CLI, and
# a CLI run executes no test functions. Worth stating because
# tests/test_gate_wiring.py is satisfied by the file being NAMED in ci.yml, and
# the CLI line already names it: without the added pytest step these tests would
# have been listed, green locally, and never once run by CI. That is precisely
# the "a test file nobody runs" class the wiring guard exists to catch, arriving
# through the one door the guard does not watch.
# ---------------------------------------------------------------------------

def _headers(tmp_path, body: str) -> Path:
    p = tmp_path / "_headers"
    p.write_text(body, encoding="utf-8")
    return p


def test_noindex_globs_reads_the_rule_whatever_order_the_block_declares_it(tmp_path, monkeypatch):
    """A `_headers` block carries any number of directives in ANY order.

    This is the case the hand-rolled regex this helper replaced got wrong: it
    required `X-Robots-Tag` to be the line immediately after the path, so moving
    a sibling directive above it -- a functionally identical edit -- false-FAILED
    the gate. This file already ships a four-directive block for the
    meet-recorder page, so the shape is real, not hypothetical.
    """
    monkeypatch.setattr(sys.modules[__name__], "HEADERS", _headers(tmp_path, (
        "/404*\n"
        "  X-Frame-Options: DENY\n"
        "  Referrer-Policy: no-referrer\n"
        "  X-Robots-Tag: noindex, nofollow\n"
    )))
    assert noindex_globs() == ["/404*"]


def test_noindex_globs_tolerates_blank_lines_and_tab_indentation(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "HEADERS", _headers(tmp_path, (
        "/404*\n"
        "\n"
        "\tX-Robots-Tag: noindex, nofollow\n"
    )))
    assert noindex_globs() == ["/404*"]


def test_noindex_globs_accepts_the_none_directive(tmp_path, monkeypatch):
    """`X-Robots-Tag: none` is `noindex, nofollow` by another name."""
    monkeypatch.setattr(sys.modules[__name__], "HEADERS", _headers(tmp_path, (
        "/404*\n  X-Robots-Tag: none\n"
    )))
    assert noindex_globs() == ["/404*"]


def test_noindex_globs_ignores_a_commented_out_rule(tmp_path, monkeypatch):
    """A commented rule is not a rule. Cloudflare never reads it, nor may this."""
    monkeypatch.setattr(sys.modules[__name__], "HEADERS", _headers(tmp_path, (
        "# /404*\n#   X-Robots-Tag: noindex, nofollow\n"
    )))
    assert noindex_globs() == []


def test_noindex_globs_returns_nothing_when_the_block_sets_no_robots_directive(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "HEADERS", _headers(tmp_path, (
        "/404*\n  X-Frame-Options: DENY\n"
    )))
    assert noindex_globs() == []


def test_noindex_covers_404_accepts_every_spelling_of_the_rule():
    for glob in ("/404", "/404/", "/404*", "/404/*"):
        assert noindex_covers_404([glob]), f"{glob} should count as covering /404"


def test_noindex_covers_404_rejects_the_html_asset_path():
    """`/404.html` 308s to `/404`, and `/404` is what answers 200.

    Covering only the asset path leaves the URL a crawler actually reaches
    uncovered, which is the soft-200 this whole gate exists to prevent, just
    relocated by one redirect hop.
    """
    assert not noindex_covers_404(["/404.html"])


def test_noindex_covers_404_rejects_a_sitewide_blanket_rule():
    """A `/*` rule would cover the 404 today and silently stop tomorrow.

    Narrowing the blanket is an edit nobody would connect to the 404 page, so
    the gate requires a rule that NAMES it.
    """
    assert not noindex_covers_404(["/*"])
    assert not noindex_covers_404(["/"])


def test_noindex_covers_404_rejects_unrelated_and_near_miss_paths():
    assert not noindex_covers_404([])
    assert not noindex_covers_404(["/private/tools/meet-recorder/*"])
    assert not noindex_covers_404(["/404-not-this-one/*"])


def test_the_shipped_headers_file_actually_covers_the_404():
    """The end-to-end anchor: real file, real parser, real predicate.

    Every test above runs on synthetic input, so all of them would stay green if
    the rule were deleted from the shipped `static/_headers`. This is the one
    that reads what the site actually ships.
    """
    assert noindex_covers_404(noindex_globs()), (
        "static/_headers no longer carries an X-Robots-Tag noindex rule naming "
        "/404. Cloudflare serves the template at /404.html -> 308 -> /404 with "
        "HTTP 200, so without it the site publishes an indexable page titled "
        "'Page not found'."
    )


def test_the_source_lane_fails_when_the_noindex_rule_is_missing(tmp_path, monkeypatch, capsys):
    """Predicate to exit code, so the wiring is pinned and not just the logic.

    A correct predicate whose result is dropped on the floor in `main()` gates
    nothing, and no assertion above would notice.
    """
    monkeypatch.setattr(sys.modules[__name__], "HEADERS", _headers(tmp_path, (
        "/thanks/*\n  X-Robots-Tag: noindex\n"
    )))
    assert main(["--source-only"]) == 1
    assert "no `X-Robots-Tag: noindex` rule for /404*" in capsys.readouterr().err


def test_the_source_lane_passes_against_the_shipped_headers_file(capsys):
    """The negative test above is only meaningful if the positive one holds."""
    assert main(["--source-only"]) == 0
    capsys.readouterr()


def test_a_failure_to_read_the_noindex_rules_is_not_swallowed(monkeypatch):
    """The gate must fail LOUDLY when it cannot determine the noindex state.

    `noindex_globs()` imports `check_social_cards.py` at call time, so renaming,
    moving or breaking that file makes this raise. The dangerous repair is a
    silent one: wrapping the call in `except Exception: covered = True` makes the
    gate report the rule as present when it has no idea, which is AP #12's
    fail-loud rule inverted on the exact check that keeps the 404 out of the
    search index.

    Nothing forced an exception here until this test, so that catch could be
    added and ship green -- measured, not assumed: adding it left the file at 12
    passed and the CLI lane at exit 0. And once the parser really did go missing,
    the CLI lane STILL exited 0 while only the pytest lane noticed, so the
    pre-commit gate was the one lane that would have stayed quiet.

    Asserting propagation rather than a specific exit code deliberately: the
    contract is that a broken gate is never mistaken for a passing one, and any
    loud failure satisfies it.
    """
    def boom() -> list[str]:
        raise RuntimeError("check_social_cards.py could not be imported")

    monkeypatch.setattr(sys.modules[__name__], "noindex_globs", boom)
    try:
        result = main(["--source-only"])
    except RuntimeError:
        return  # propagated: correct.
    raise AssertionError(
        f"the 404 gate returned {result} instead of letting the failure "
        "propagate. It could not read the noindex rules and reported a verdict "
        "anyway, so a missing X-Robots-Tag rule would now pass silently."
    )


if __name__ == "__main__":
    sys.exit(main())
