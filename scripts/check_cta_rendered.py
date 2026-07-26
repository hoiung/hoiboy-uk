#!/usr/bin/env python3
"""What the browser actually computes for the CTA button, on every page it appears.

blog-priv#63.

`scripts/test_cta_button.py` scores selector specificity from the stylesheet
source. That is a MODEL of the cascade, and a model can be right about the rule
and wrong about the page: a later rule, a minifier rewrite, a template that
stops emitting the class, or a colour token that fails to resolve all leave the
source assertions green and the button broken. This gate asks the only authority
there is. It loads the built pages in Chromium and reads
`getComputedStyle` off the real element.

Three properties, one per way the button has already been observed to fail:

  background-color   the fill resolves to the CONFIGURED colour. Catches a
                     --cta token that did not resolve (an unresolved var()
                     computes to the initial value, so the button turns
                     transparent while the CSS source still reads correctly).
  text-decoration    no underline. This is the specificity defect made visible:
                     with a bare `.btn` rule the source looks right and the
                     browser paints an underlined link.
  color              the label colour, which on the accent fill once computed to
                     the fill colour itself and rendered the text invisible.

Both colour schemes are checked, not one. The site has no theme toggle; it
follows `prefers-color-scheme`, so "it looks right" on the author's machine
covers exactly half the readers. The button is deliberately theme-independent,
and this asserts that rather than trusting it.

Expected values are DERIVED, from `config/_default/params.toml` for the fill and
from the stylesheet rule for the label, not restated here. A gate carrying its
own copy of the colour passes when the config and the page disagree, which is
the disagreement worth catching.

Coverage cannot be silently lost: the pages are discovered by scanning the built
tree for the class, and the run fails if fewer than `--min-pages` carry it. A
template change that stops emitting the button fails here instead of quietly
reducing this to a no-op.

Fails LOUD on a missing browser (exit 2). A gate that skips itself when its
dependency is absent reports success for work it did not do.

Usage:
  python3 scripts/check_cta_rendered.py --built public
  python3 scripts/check_cta_rendered.py --built public --screenshots ~/DevProjects/screenshots/cta-button

Exit 0 = pass. 1 = a named failure. 2 = cannot run (no build, no browser).
"""

from __future__ import annotations

import argparse
import functools
import http.server
import re
import socketserver
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "assets" / "css" / "main.css"
PARAMS = ROOT / "config" / "_default" / "params.toml"

SELECTOR = "a.btn"

# Floors, not a list to check against: the pages are found by scanning the built
# tree, so a NEW page carrying the button is covered automatically and only a
# LOSS of coverage trips these.
#
# Measured, not assumed. blog-priv#63's AC 1.6 asked for "three existing call
# sites (/hire-hoi/ai-consultancy/, /hire-hoi/ict-consultancy/,
# /hire-hoi/permanent-roles/) plus the four service pages". That was a
# conflation: those three landing pages call the `brand-intro` shortcode, not
# `consulting-cta`, and carry no button at all. The real coverage is five
# service pages under /hire-hoi/ai-consultancy/ holding six buttons, because
# claude-code-harness-architect calls the shortcode twice (top and bottom of a
# long page).
#
# Both floors are load-bearing. Pages alone would not notice the second button
# on the harness-architect page disappearing.
DEFAULT_MIN_PAGES = 5
DEFAULT_MIN_INSTANCES = 6

SCHEMES = ("light", "dark")

# Every class attribute in the document, quoted or not.
#
# READ THIS BEFORE GREPPING THE BUILT TREE. Hugo's minifier here does NOT drop
# attribute quotes: config/_default/hugo.toml:117 sets `keepQuotes = true`, so
# the built HTML always says class="btn", exactly as the source did. Measured on
# the built tree: 11,642 quoted single-token class attributes, 0 unquoted.
#
# This matters because the opposite belief is self-confirming and cost this
# session real time. A probe for the unquoted form returns 0 on EVERY page,
# including the pages that do carry the button, so it reads as "the button is
# nowhere" and quietly confirms whatever hypothesis you brought to it. Always
# grep class="btn" WITH the quotes. The unquoted branch below is kept only as
# defensive tolerance in case the minifier config ever changes; it is not
# evidence of anything today.
#
# The tokens are then compared whole. A `\bbtn\b` substring match looks
# equivalent and is not: `-` is a non-word character, so it matches inside
# `menu-toggle-btn`, the mobile nav hamburger that the shared sidebar puts on
# every page of the site. That made this gate "find" the button on all 339 built
# HTML pages, then fail on the 333 where no such element exists. (339 is the
# file count this gate walks via rglob below. Hugo separately reports 468 "page
# objects" in its build summary; the two numbers are not interchangeable.)
CLASS_ATTR = re.compile(r'class=(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))')

COMMENTS = re.compile(r"/\*.*?\*/", re.S)


def die(msg: str, code: int = 2) -> None:
    print(f"CTA RENDER GATE: {msg}", file=sys.stderr)
    raise SystemExit(code)


def hex_to_rgb_string(value: str) -> str:
    """`#188418` -> `rgb(24, 132, 24)`, which is how Chromium reports it."""
    h = value.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"


def expected_fill() -> str:
    text = PARAMS.read_text(encoding="utf-8")
    if sys.version_info >= (3, 11):
        import tomllib
        colour = tomllib.loads(text).get("ctaColor")
    else:
        m = re.search(r'^ctaColor\s*=\s*"([^"]+)"', text, re.M)
        colour = m.group(1) if m else None
    if not colour:
        die("ctaColor is not declared in config/_default/params.toml")
    return hex_to_rgb_string(colour)


def expected_label() -> str:
    """The label colour the stylesheet's stateless .btn rule declares."""
    css = COMMENTS.sub("", CSS.read_text(encoding="utf-8"))
    for sel_group, decls in re.findall(r"([^{}]+)\{([^{}]*)\}", css, re.S):
        sels = [s.strip() for s in sel_group.split(",")]
        if not any(re.search(r"\.btn(?![\w-])", s) and ":" not in s for s in sels):
            continue
        m = re.search(r"(?:^|;)\s*color\s*:\s*([^;]+)", decls)
        if m:
            return hex_to_rgb_string(m.group(1))
    die("no stateless .btn rule with a color declaration found in assets/css/main.css")
    return ""  # unreachable; keeps type checkers quiet


def has_button(html: str) -> bool:
    """True when some element in `html` carries `btn` as a whole class token."""
    for quoted, single, bare in CLASS_ATTR.findall(html):
        if "btn" in (quoted or single or bare).split():
            return True
    return False


def pages_with_button(public: Path) -> list[str]:
    """Every built page carrying the button, as a site-root-relative URL."""
    urls = []
    for html in sorted(public.rglob("*.html")):
        if not has_button(html.read_text(encoding="utf-8", errors="replace")):
            continue
        rel = html.relative_to(public)
        urls.append("/" + (str(rel.parent) + "/" if rel.name == "index.html" else str(rel)).lstrip("./"))
    return urls


def serve(public: Path):
    """A local HTTP server over the built tree.

    Not file://. The stylesheet is referenced root-relative and fingerprinted
    (`/css/main.min.<hash>.css`); over file:// that resolves to the filesystem
    root, the CSS silently fails to load, and every computed value comes back as
    an unstyled default. Observed during colour testing, where it made three
    genuinely different renders come out byte-identical.
    """
    class Quiet(http.server.SimpleHTTPRequestHandler):
        # Silenced on the CLASS. Assigning log_message to the functools.partial
        # instead sets an attribute on the partial object, which the handler
        # never consults, and every asset request lands on the console.
        def log_message(self, *args, **kwargs):
            pass

    handler = functools.partial(Quiet, directory=str(public))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--built", default="public", help="built output dir (default: public)")
    ap.add_argument("--min-pages", type=int, default=DEFAULT_MIN_PAGES,
                    help=f"fail if fewer pages carry the button (default: {DEFAULT_MIN_PAGES})")
    ap.add_argument("--min-instances", type=int, default=DEFAULT_MIN_INSTANCES,
                    help=f"fail if fewer buttons found per colour scheme "
                         f"(default: {DEFAULT_MIN_INSTANCES})")
    ap.add_argument("--screenshots", metavar="DIR",
                    help="also write one full-page screenshot per scheme of the first page")
    args = ap.parse_args(argv)

    public = Path(args.built) if Path(args.built).is_absolute() else ROOT / args.built
    if not public.is_dir():
        die(f"no build at {public} - run `hugo --minify` first")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        die("playwright is not installed. `pip install playwright && playwright "
            "install chromium`. This gate does not skip: the computed cascade is "
            "the whole point, and a source grep is not a substitute.")

    fill, label = expected_fill(), expected_label()
    urls = pages_with_button(public)
    if len(urls) < args.min_pages:
        die(f"only {len(urls)} built page(s) carry {SELECTOR}, expected at least "
            f"{args.min_pages}: {urls}. Either the shortcode stopped emitting the "
            f"class, or pages that used to call it no longer do. Coverage cannot "
            f"drop silently.", 1)

    httpd, base = serve(public)
    failures: list[str] = []
    checked = 0
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                for scheme in SCHEMES:
                    ctx = browser.new_context(color_scheme=scheme, viewport={"width": 1280, "height": 900})
                    page = ctx.new_page()
                    found = 0
                    for url in urls:
                        page.goto(base + url, wait_until="load")
                        buttons = page.locator(SELECTOR)
                        n = buttons.count()
                        if n == 0:
                            failures.append(f"[{scheme}] {url}: the page HTML carries the class "
                                            f"but no {SELECTOR} element is in the DOM")
                            continue
                        found += n
                        for i in range(n):
                            got = buttons.nth(i).evaluate(
                                "el => { const s = getComputedStyle(el); return {"
                                " bg: s.backgroundColor, td: s.textDecorationLine, fg: s.color,"
                                " display: s.display }; }"
                            )
                            checked += 1
                            where = f"[{scheme}] {url} ({SELECTOR} #{i + 1})"
                            if got["bg"] != fill:
                                failures.append(
                                    f"{where}: background-color is {got['bg']}, expected {fill} "
                                    f"(ctaColor from params.toml). A transparent result means the "
                                    f"--cta token did not resolve; the accent colour means the "
                                    f"wrong token; anything else means another rule won.")
                            if got["td"] != "none":
                                failures.append(
                                    f"{where}: text-decoration-line is {got['td']!r}, expected "
                                    f"'none'. This is the specificity defect: `.main a` (0-1-1) "
                                    f"has beaten the button rule and it is painting a link.")
                            if got["fg"] != label:
                                failures.append(
                                    f"{where}: color is {got['fg']}, expected {label}. If it "
                                    f"equals the background the label is invisible.")
                            if got["display"] == "inline":
                                failures.append(
                                    f"{where}: display is 'inline', so it flows as text rather "
                                    f"than sitting as a block a reader can hit.")
                    if found < args.min_instances:
                        failures.append(
                            f"[{scheme}] found {found} button(s) across {len(urls)} page(s), "
                            f"expected at least {args.min_instances}. A page that calls the "
                            f"shortcode twice losing one of them is invisible to the page "
                            f"count alone.")
                    if args.screenshots and urls:
                        out = Path(args.screenshots).expanduser()
                        out.mkdir(parents=True, exist_ok=True)
                        page.goto(base + urls[0], wait_until="load")
                        # Scrolled to the button and shot at viewport size, not
                        # full_page: these exist for a human to judge whether the
                        # thing reads as a button, and a 6000px page render of a
                        # long service page buries it.
                        page.locator(SELECTOR).first.scroll_into_view_if_needed()
                        page.screenshot(path=str(out / f"cta-{scheme}.png"))
                        print(f"  screenshot: {out / f'cta-{scheme}.png'} ({urls[0]})")
                    ctx.close()
            finally:
                browser.close()
    finally:
        # Both calls, in this order. shutdown() stops the serve loop but leaves
        # the listening socket open for the garbage collector; server_close()
        # releases the fd. Matches scripts/test_check_ai_crawler_access.py:97-98,
        # which is the repo's existing pattern for the same primitive.
        httpd.shutdown()
        httpd.server_close()

    if failures:
        print("CTA RENDER GATE FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"CTA render gate: OK ({checked} button instance(s) across {len(urls)} page(s) "
          f"x {len(SCHEMES)} colour schemes; fill {fill}, label {label}, no underline).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
