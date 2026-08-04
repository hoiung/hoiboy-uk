#!/usr/bin/env python3
"""What the browser actually does with the AGIT story counter, on the real page.

hoiboy-uk#57.

`tests/agit-form.test.js` drives the shipped module under jsdom, which is a good
model and still a model. It cannot see whether Hugo inlined the stylesheet,
whether `/js/agit-form.js` is actually referenced by the built page, whether the
CSP blocks it, or whether the counter element survived a template edit. Every one
of those leaves the JS suite green and the form broken. This gate asks the only
authority there is: a real Chromium, on the built tree.

What the trailing-Enter case below does and does NOT prove, stated precisely,
because an earlier version of this docstring overclaimed it. It exercises the
CLIENT-side normalisation the guarantee depends on: a counter reading raw
`.value.length` shows a green 1200 there for a story the server would refuse. It
does NOT observe wire serialisation or the server's count, because the POST is
aborted before it leaves the browser, so on its own it does not confirm the
LF-to-CRLF expansion the issue derived from the WHATWG rule.

That derivation turns out not to be load-bearing anyway. Both sides apply the
identical normalisation, and serialisation can only ADD characters, never remove
them, so "the counter is green" implies "the server accepts" whether or not any
expansion occurs. Measured over 18180 generated cases against four different
wire models, including an identity model where no expansion happens at all:
zero violations in every one.

Three cases, in the order a member meets them:

  1199 characters        counter reads 1199 in the SHORT colour, submit blocked
                         with a worded notice naming the minimum.
  one more character     counter reads 1200 in the MET colour, and the submit
                         gets PAST the length check.
  1199 plus Enter        counter still reads 1199, still blocked. This is the
                         case that discriminates the normalisation: a counter
                         reading raw `.value.length` shows 1200 here and lets a
                         story through that the server would then refuse.

"Past the length check" rather than "submits", deliberately. Turnstile injects
its hidden token from challenges.cloudflare.com, which does not load against a
local build, so the handler always stops at the verification step. That is the
proof: reaching a DIFFERENT complaint is what shows the length gate let it by.

Both colour schemes are checked. The site has no theme toggle, it follows the
system preference, so testing one covers half the readers. The expected colours
are DERIVED from the built page's own stylesheet, not restated here, because a
gate carrying its own copy of a colour passes when the page and the gate
disagree, and that disagreement is the thing worth catching.

Served over HTTP rather than file://. The script is referenced root-relative
(`/js/agit-form.js`), which over file:// resolves to the filesystem root, and the
form would silently render with no JavaScript at all: no counter, no gate, and
every assertion below failing for the wrong reason.

Fails LOUD on a missing browser (exit 2). A gate that skips itself when its
dependency is absent reports success for work it did not do.

Usage:
  python3 scripts/check_agit_form_counter.py --built public
  python3 scripts/check_agit_form_counter.py --built public --screenshots ~/DevProjects/screenshots/agit-counter

Exit 0 = pass. 1 = a named failure against the built page. 2 = cannot run.
"""

import argparse
import functools
import http.server
import re
import socketserver
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PAGE_URL = "/community/asians-gingers-in-tech/"
STORY = '[name="feature"]'
COUNTER = ".agit-count"
NOTICE = ".agit-notice"
SCHEMES = ("light", "dark")

# Kept in step with STORY_MIN in static/js/agit-form.js and FIELD_FLOORS.feature
# in functions/api/contribute.js. Asserted against the rendered page below rather
# than trusted: the label has to state this same number.
MINIMUM = 1200

STYLE_BLOCK = re.compile(r"<style>(.*?)</style>", re.S)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
DARK_QUERY = re.compile(r"@media\s*\(\s*prefers-color-scheme\s*:\s*dark\s*\)\s*\{")
COUNTER_RULE = re.compile(r"\.agit-count\.is-(short|met)\s*\{[^}]*?color\s*:\s*(#[0-9a-fA-F]{6})", re.S)
HEX6 = re.compile(r"\A#[0-9a-fA-F]{6}\Z")


def die(msg: str, code: int = 2) -> None:
    print(f"AGIT COUNTER GATE: {msg}", file=sys.stderr)
    raise SystemExit(code)


# ----------------------------------------------------------------------
# Pure decision logic. Covered by scripts/test_check_agit_form_counter.py,
# which runs in CI where there is no browser. These decide what "correct"
# means, so leaving them reachable only through the manual Chromium lane is
# the exact gap Ralph Tier 2 caught once on the CTA gate.
# ----------------------------------------------------------------------


def hex_to_rgb_string(value: str) -> str:
    """`#b3261e` -> `rgb(179, 38, 30)`, which is how Chromium reports a colour."""
    h = value.strip()
    if not HEX6.match(h):
        die(f"the counter colour is declared as `{h}`, which this gate cannot resolve. "
            f"It compares against a browser-computed value, so the source has to carry "
            f"a plain 6-digit hex rather than a var() token or a named colour.")
    h = h.lstrip("#")
    return f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"


def split_on_dark_query(css: str) -> tuple[str, str]:
    """Return (light_css, dark_css), brace-matched on the dark media query.

    A lazy `\\{.*?\\}` stops at the first nested rule's close brace, which leaves
    most of the dark rules sitting in the light half. The gate would then expect
    the light colour in dark mode and fail against a correct page.
    """
    match = DARK_QUERY.search(css)
    if not match:
        return css, ""
    depth, i = 1, match.end()
    while i < len(css) and depth:
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
        i += 1
    if depth:
        die("unbalanced braces in the page's dark-theme media query")
    return css[:match.start()] + css[i:], css[match.end():i - 1]


def counter_colours(html: str) -> dict[str, dict[str, str]]:
    """{scheme: {state: 'rgb(...)'}} for the counter, read off the built page.

    Comments are stripped first: the rationale comment beside these rules names
    both background hexes, and parsed naively that prose reads as colours.
    """
    blocks = STYLE_BLOCK.findall(html)
    if not blocks:
        die("the built page carries no inline <style> block, so the counter has no colours")
    css = CSS_COMMENT.sub("", "\n".join(blocks))
    light_css, dark_css = split_on_dark_query(css)

    out: dict[str, dict[str, str]] = {}
    for scheme, source in (("light", light_css), ("dark", dark_css)):
        found = {state: hex_to_rgb_string(hexv) for state, hexv in COUNTER_RULE.findall(source)}
        missing = {"short", "met"} - set(found)
        if missing:
            die(f"the built page declares no {sorted(missing)} counter colour for the "
                f"{scheme} theme. Both states need a value in both themes: no single "
                f"hex clears WCAG AA against both page backgrounds.")
        out[scheme] = found
    return out


def state_for(count: int, minimum: int = MINIMUM) -> str:
    """Which colour the counter should be wearing at this length.

    At exactly the minimum the story is long enough. Off-by-one here is the
    difference between a member being told to keep writing at 1200 and a story
    the server would accept being blocked by its own counter.
    """
    return "met" if count >= minimum else "short"


def classify_notice(text: str | None, minimum: int = MINIMUM) -> str:
    """'length' | 'other' | 'none' -- which complaint the form is making.

    'other' is a pass for the long-story case and a fail for the short one, so
    the three-way answer matters: collapsing this to a boolean "was it blocked"
    would let the Turnstile message stand in for the length message and report a
    working gate that never fired.
    """
    if text is None or not text.strip():
        return "none"
    return "length" if str(minimum) in text else "other"


# ----------------------------------------------------------------------
# Browser half
# ----------------------------------------------------------------------


def serve(public: Path):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        # Silenced on the CLASS: assigning to the functools.partial sets an
        # attribute the handler never consults, and every asset request lands
        # on the console.
        def log_message(self, *args, **kwargs):
            pass

    handler = functools.partial(Quiet, directory=str(public))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def fill_the_rest_of_the_form(page) -> None:
    """Every other required field, so native validation lets the submit through.

    Not optional scaffolding. Native constraint validation runs BEFORE the
    submit listener, so with an empty name or an unticked consent box the
    handler never fires at all and every assertion here would pass for the
    wrong reason: no notice, because no code ran.
    """
    page.fill('[name="name"]', "Test Person")
    page.fill('[name="email"]', "test@example.com")
    page.fill('[name="email_confirm"]', "test@example.com")
    page.check('[name="consent"]')


def submit_and_read_notice(page) -> str | None:
    page.click('button[type="submit"]')
    page.wait_for_timeout(150)
    notice = page.locator(NOTICE)
    return notice.first.text_content() if notice.count() else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--built", default="public", help="built output dir (default: public)")
    ap.add_argument("--screenshots", metavar="DIR",
                    help="also write one screenshot of the counter per colour scheme")
    args = ap.parse_args(argv)

    public = Path(args.built) if Path(args.built).is_absolute() else ROOT / args.built
    if not public.is_dir():
        die(f"no build at {public} - run `hugo --gc --minify -e production` first")

    page_file = public / PAGE_URL.strip("/") / "index.html"
    if not page_file.is_file():
        die(f"no built page at {page_file}")
    html = page_file.read_text(encoding="utf-8")

    if f"minimum {MINIMUM} characters" not in html:
        die(f"the built page does not state the {MINIMUM}-character minimum in words. "
            f"The counter is a colour, and colour alone is not an accessible signal "
            f"(WCAG 2.1 SC 1.4.1) nor a readable instruction.", 1)

    colours = counter_colours(html)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        die("playwright is not installed. `pip install playwright && playwright "
            "install chromium`. This gate does not skip: what the real browser "
            "computes is the whole point, and a source grep is not a substitute.")

    httpd, base = serve(public)
    failures: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                for scheme in SCHEMES:
                    ctx = browser.new_context(color_scheme=scheme,
                                              viewport={"width": 1280, "height": 1000})
                    page = ctx.new_page()
                    # Belt and braces: if a future change drops the Turnstile
                    # guard, an unblocked submit would navigate away mid-run and
                    # the failure would read as a missing element.
                    page.route("**/api/contribute", lambda route: route.abort())
                    page.goto(base + PAGE_URL, wait_until="load")

                    counter = page.locator(COUNTER)
                    if counter.count() != 1:
                        failures.append(f"[{scheme}] expected exactly one {COUNTER} element, "
                                        f"found {counter.count()}")
                        ctx.close()
                        continue

                    for label, value, expected_count, expect in (
                        ("1199 characters", "x" * 1199, 1199, "length"),
                        ("1200 characters", "x" * 1200, 1200, "other"),
                        ("1199 characters plus Enter", "x" * 1199 + "\n", 1199, "length"),
                    ):
                        page.goto(base + PAGE_URL, wait_until="load")
                        page.route("**/api/contribute", lambda route: route.abort())
                        fill_the_rest_of_the_form(page)
                        page.fill(STORY, value)
                        page.wait_for_timeout(50)

                        shown = page.locator(COUNTER).first.text_content().strip()
                        if shown != str(expected_count):
                            failures.append(f"[{scheme}] {label}: counter reads {shown!r}, "
                                            f"expected {expected_count!r}")

                        if "/" in shown:
                            failures.append(f"[{scheme}] {label}: counter reads {shown!r}, "
                                            f"which is a fraction. It must be one bare number.")

                        want_state = state_for(expected_count)
                        want_colour = colours[scheme][want_state]
                        got_colour = page.locator(COUNTER).first.evaluate(
                            "el => getComputedStyle(el).color")
                        if got_colour != want_colour:
                            failures.append(f"[{scheme}] {label}: counter is {got_colour}, "
                                            f"expected the {want_state} colour {want_colour}")

                        got = classify_notice(submit_and_read_notice(page))
                        if got != expect:
                            failures.append(
                                f"[{scheme}] {label}: submit produced a {got!r} notice, "
                                f"expected {expect!r}"
                                + (" (the length gate did not fire)" if expect == "length"
                                   else " (the length gate fired on a long-enough story)"))

                    if args.screenshots:
                        out = Path(args.screenshots).expanduser()
                        out.mkdir(parents=True, exist_ok=True)
                        page.locator(COUNTER).first.screenshot(
                            path=str(out / f"agit-counter-{scheme}.png"))
                    ctx.close()
            finally:
                browser.close()
    finally:
        httpd.shutdown()

    if failures:
        for f in failures:
            print(f"AGIT COUNTER GATE: {f}", file=sys.stderr)
        return 1

    print(f"AGIT counter OK: 3 cases x {len(SCHEMES)} colour schemes on {PAGE_URL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
