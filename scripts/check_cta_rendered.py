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


HEX_COLOUR = re.compile(r"#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\Z")


def hex_to_rgb_string(value: str) -> str:
    """`#188418` -> `rgb(24, 132, 24)`, which is how Chromium reports it.

    Only a hex literal can be converted here. Every OTHER colour in main.css is
    already a `var()` token, so `color: var(--cta-label)` on the button rule is
    the single most likely edit to this file - and without the guard below it
    reached `int("va", 16)` and surfaced as a raw ValueError traceback pointing
    at this function, which tells the reader nothing about what to fix.
    """
    h = value.strip()
    if not HEX_COLOUR.match(h):
        die(
            f"{CSS}: the button's colour is declared as `{h}`, which is not a hex "
            f"literal. This gate models the cascade by reading the stylesheet, so "
            f"it can only resolve hex values - a var()/named/rgb() colour has to be "
            f"resolved by the browser it is compared against. Either inline the hex "
            f"here or teach this gate to resolve the token."
        )
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"


def expected_fill() -> str:
    # utf-8-sig for the same reason parse_noindex_globs uses it: a BOM-prefixed
    # save from a Windows editor is a real thing on this operator's host, and
    # TOML disallows a leading BOM, so plain utf-8 turned that into an unhandled
    # TOMLDecodeError traceback instead of this file's normal actionable die().
    text = PARAMS.read_text(encoding="utf-8-sig")
    if sys.version_info >= (3, 11):
        import tomllib
        colour = tomllib.loads(text).get("ctaColor")
    else:
        m = re.search(r'^ctaColor\s*=\s*"([^"]+)"', text, re.M)
        colour = m.group(1) if m else None
    if not colour:
        die("ctaColor is not declared in config/_default/params.toml")
    return hex_to_rgb_string(colour)


# Conditional at-rules. Their contents apply only when the condition holds, so a
# rule inside one is NOT the unconditional answer this gate needs. The flat
# brace-scan below cannot see nesting at all: it extracts the inner rule and
# treats it as top-level.
CONDITIONAL_AT_RULE = re.compile(r"@(?:media|supports|container)\b[^{]*\{", re.I)

# A CSS string literal, single or double quoted, honouring backslash escapes.
# Deliberately NOT re.S, and the body excludes a raw newline: per CSS syntax a
# string ends at the newline (it becomes a "bad-string" and the parser recovers
# there). With re.S an unterminated quote instead paired with the NEXT quote of
# the same type however far away, blanking every real brace in between - which
# either buried the button's own rule behind a misleading "no stateless a.btn
# rule found", or, when a second disagreeing rule survived outside the swallowed
# span, returned the WRONG colour silently with no die at all. That defeated the
# ambiguity-is-fatal contract this file promises (blog-priv#63, Ralph round 9).
STRING_LITERAL = re.compile(r"""(['"])(?:\\.|(?!\1)[^\\\n])*\1""")

QUOTE = re.compile(r"""(?<!\\)['"]""")


def _blank_strings(css: str) -> str:
    """Blank the CONTENTS of string literals, keeping quotes and total length.

    A brace inside a string is data, not structure. `content: "}"` is ordinary
    valid CSS - this stylesheet already uses `content` for list markers - and
    it desynchronised the brace-depth counter below, truncating an @media block
    early so the rest of it leaked into the "unconditional" text. A dark-only
    `.main a.btn` rule then came back as the single universal label and was
    asserted under the light scheme too: the exact silent-wrong-answer this
    file's conditional handling exists to stop, reached by another door
    (blog-priv#63, Ralph round 8).

    Blanking rather than deleting keeps every offset intact, so nothing else
    that reads this text shifts underneath. Applied once, up front, which fixes
    the depth counter and the flat rule-scan together instead of hardening one
    and leaving the other - the mistake that produced this finding in the first
    place (round 4 made comment-stripping quote-aware and left the split naive).
    """
    blanked = STRING_LITERAL.sub(
        lambda m: m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[0], css)
    # Any quote still standing after the well-formed literals are blanked never
    # closes. Report it by line and name it as the cause: the failure otherwise
    # surfaces as "no stateless a.btn rule found", which blames the button for a
    # typo somewhere else entirely.
    # Probe on a copy with the well-formed literals removed OUTRIGHT, quotes and
    # all. Blanking keeps its quotes (offsets must not shift), so probing the
    # blanked text re-anchors on a CLOSING quote and false-fires on valid CSS.
    probe = STRING_LITERAL.sub(lambda m: " " * len(m.group(0)), css)
    stray = QUOTE.search(probe)
    if stray:
        line = probe.count("\n", 0, stray.start()) + 1
        die(
            f"{CSS} line {line}: unterminated string literal ({stray.group(0)}). A "
            f"CSS string cannot span a newline, so this quote never closes and the "
            f"button's label colour cannot be read. Fix the quote; this gate is not "
            f"reporting a problem with the button."
        )
    return blanked


def _split_conditional(css: str) -> tuple[str, list[tuple[str, str]]]:
    """Separate unconditional CSS from conditional at-rule blocks.

    Returns the CSS with every `@media` / `@supports` / `@container` block
    removed, plus a list of `(condition, body)` for the blocks taken out, so
    each can be inspected and reported by name.
    """
    kept: list[str] = []
    blocks: list[tuple[str, str]] = []
    i = 0
    while True:
        m = CONDITIONAL_AT_RULE.search(css, i)
        if not m:
            kept.append(css[i:])
            return "".join(kept), blocks
        kept.append(css[i:m.start()])
        depth, j = 1, m.end()
        while j < len(css) and depth:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        blocks.append((m.group(0).rstrip("{").strip(), css[m.end():j - 1]))
        i = j


def _stateless_anchor_labels(css: str) -> dict[str, str]:
    """rgb -> the selector that declared it, for stateless `a.btn` rules."""
    found: dict[str, str] = {}
    for sel_group, decls in re.findall(r"([^{}]+)\{([^{}]*)\}", css, re.S):
        sels = [s.strip() for s in sel_group.split(",")]
        matching = [s for s in sels if re.search(r"\ba\.btn(?![\w-])", s) and ":" not in s]
        if not matching:
            continue
        # LAST declaration wins, which is what the cascade does within a rule.
        # `re.search` took the FIRST, so `color: #fff; color: #6b6b6b;` made this
        # gate model a colour the browser never paints - and because the sibling
        # authority scores WCAG contrast from the same parse, an unreadable
        # button passed both gates green.
        decl = re.findall(r"(?:^|;)\s*color\s*:\s*([^;]+)", decls)
        if decl:
            found.setdefault(hex_to_rgb_string(decl[-1]), matching[0])
    return found


def expected_label() -> str:
    """The label colour the stylesheet's stateless `a.btn` rule declares.

    Anchored to `a.btn`, not to a bare `.btn`, and that is load-bearing. The CTA
    is an `<a class="btn">`; a rule that does not match an anchor cannot be the
    one styling it. Matching any colon-free selector containing `.btn` returned
    whichever such rule came FIRST in file order, so adding an ordinary
    `.scroll-top button.btn { color: ... }` above line 138 made this compute the
    wrong label and the browser gate then assert that wrong value against the
    real button on every page (blog-priv#64, Ralph round 6). Proven by
    construction: a decoy rule declared first returned its colour, not the CTA's.

    Ambiguity is fatal rather than resolved. If several stateless `a.btn` rules
    declare DIFFERENT colours, which one wins is a cascade question this gate
    deliberately does not answer - the browser does. Guessing would put the
    silent-wrong-answer back, so it dies and names them instead.

    KNOWN BOUNDARY, tested rather than merely stated (Ralph round 7). The match
    is the literal substring `a.btn`, which is not CSS selector semantics. Two
    legitimate refactors that still style the button - `.main .btn` and
    `.main :where(a).btn`, both (0,2,0) and so both still beating `.main a` -
    make this find nothing and die. That is a LOUD failure with an actionable
    message, not a wrong answer, and pinning it here means the next maintainer
    meets a documented boundary instead of a confusing exit 2 in the middle of
    an unrelated change. Modelling the cascade properly would need a real CSS
    parser, which is not worth it for one rule.
    """
    css = _blank_strings(COMMENTS.sub("", CSS.read_text(encoding="utf-8-sig")))
    unconditional, conditional = _split_conditional(css)

    # A conditional rule is not the unconditional answer. Checked BEFORE the
    # main scan because the flat brace-scan cannot see nesting: a dark-mode rule
    # was extracted as though it were top-level, which made a base+dark pair
    # look like an ambiguous duplicate, and - far worse - made a dark-only rule
    # return silently as the single expected label asserted under BOTH schemes.
    for condition, body in conditional:
        inside = _stateless_anchor_labels(body)
        if inside:
            die(f"assets/css/main.css declares a CTA label colour inside "
                f"`{condition}` ({', '.join(sorted(inside))}). This gate derives "
                f"ONE expected label and asserts it under every scheme in "
                f"SCHEMES, so it cannot represent a colour that only applies "
                f"sometimes. Either keep a single label colour for the button, "
                f"or give this gate a per-scheme expectation to match.")

    found = _stateless_anchor_labels(unconditional)
    if not found:
        die("no stateless `a.btn` rule with a color declaration found in "
            "assets/css/main.css. The CTA is an <a class=\"btn\">, so its label "
            "colour has to come from a rule that matches an anchor. Note this "
            "check looks for the literal `a.btn`: a selector that styles the "
            "button without that exact form (`.main .btn`, `:where(a).btn`) is "
            "a known unsupported shape, not a missing rule.")
    if len(found) > 1:
        die("assets/css/main.css declares more than one stateless `a.btn` label "
            "colour, so this gate cannot say which applies to the CTA: "
            + ", ".join(f"{sel} -> {rgb}" for rgb, sel in sorted(found.items())))
    return next(iter(found))


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
