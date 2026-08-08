#!/usr/bin/env python3
"""Fill the newsletter email template's %%TOKEN%% placeholders (blog-priv#81).

WHY THIS IS A SHARED MODULE and not a function inside the sender. Two callers need
the same substitution: `--preview` below, which renders the template to a PNG for
AC 1.5, and `scripts/send_newsletter.py` in Phase 2, which builds the real
`htmlContent`. Writing it twice would let the preview drift from what actually gets
sent, which would make the preview worse than useless: it would look like evidence.

WHY %%TOKEN%% AND NOT THE NATIVE BREVO SYNTAX. Hugo parses every file under
layouts/ as a Go template, html comments included, so a double-curly Brevo merge
tag written into the template fails the whole site build. The template therefore
carries inert placeholders and the SENDER emits the real merge tag as the VALUE of
%%FIRSTNAME%%. That keeps the personalisation tag in exactly one place.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "layouts" / "_partials" / "newsletter" / "email.html"

# Named _PLACEHOLDER_RE rather than _TOKEN on purpose. The public-repo secret
# scanner keys on `token` appearing as an assignment target, so the shorter name
# tripped it as a GENERIC_SECRET and blocked the commit. Renaming is the honest
# fix; an allowlist entry or a `# secret-allow` comment would have left a
# permanent hole in a gate that exists to protect a public repo, in exchange for
# keeping a name that was less accurate anyway. This is a compiled regex.
_PLACEHOLDER_RE = re.compile(r"%%([A-Z_]+)%%")

# Every html comment is removed before an email is built. Three reasons, and the
# first is the one that matters to a reader:
#   1. The template opens with ~50 lines of engineering notes explaining the Word
#      engine, the Hugo brace collision and the placeholder contract. Sent as-is,
#      all of it travels to every subscriber inside the message source.
#   2. The <!-- iamhoi --> markers exist so the voice guard reads the copy in the
#      REPO. They have no business in the delivered email.
#   3. Those notes necessarily quote the placeholder syntax to explain it, so a
#      comment-blind renderer reads the explanation as a real placeholder named
#      TOKEN and refuses to render. Found exactly that way.
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

# The contract the template and the sender both hold. Kept as a frozenset so a
# typo in either direction is a loud KeyError-shaped failure rather than a token
# that silently survives into a subscriber's inbox as literal %%POST_TITLE%%.
PLACEHOLDERS = frozenset(
    {
        "FIRSTNAME",
        "POST_TITLE",
        "POST_DATE",
        "POST_EXCERPT",
        "POST_URL",
        "HERO_URL",
        "HERO_ALT",
        "UNSUBSCRIBE_URL",
    }
)


class PlaceholderError(RuntimeError):
    """Raised loudly rather than shipping a half-substituted email.

    THE BASE CLASS IS NOT LOAD-BEARING, and that is deliberate rather than an
    oversight, so a mutation swapping `RuntimeError` for any other builtin is an
    EQUIVALENT MUTANT no test can kill. Recorded here because Ralph round 7 tier 2
    went looking for this reasoning, could not find it written down anywhere, and
    had to re-derive it.

    It used to matter, and wrongly: `NewsletterError` is also a RuntimeError, so
    the two are SIBLINGS, and `send_newsletter.main()`'s `except NewsletterError`
    did not catch this at all. Every refusal below escaped as a raw traceback with
    no `_log("fatal")` audit line. The fix was to catch this type BY NAME at both
    call sites (`send_newsletter.py` build_html, and `preview()` in this file), and
    once both do that the base class stops carrying any behaviour.

    Verified rather than assumed: `grep -rn "except RuntimeError" scripts/ tests/`
    returns two hits, both unrelated (`test_404.py`, `check-public-repo-secrets.py`),
    and neither touches the newsletter modules. Re-run that grep before relying on
    this note.
    """


def tokens_in(text: str) -> set[str]:
    return set(_PLACEHOLDER_RE.findall(text))


def strip_comments(text: str) -> str:
    """Drop every html comment. See _HTML_COMMENT for why this is not optional."""
    return _HTML_COMMENT.sub("", text)


def render(template_text: str, values: dict[str, str]) -> str:
    """Substitute every placeholder, refusing any mismatch in either direction.

    Both directions matter. An unfilled token reaches the reader as raw
    %%POST_TITLE%% text; an unknown key means the caller thinks it is setting
    something the template stopped using, so its value silently disappears.

    Comments are stripped FIRST, so the engineering notes and the iamhoi markers
    never reach a subscriber and their prose is never mistaken for a placeholder.
    """
    template_text = strip_comments(template_text)
    present = tokens_in(template_text)

    unknown_in_template = present - PLACEHOLDERS
    if unknown_in_template:
        raise PlaceholderError(
            f"template uses placeholder(s) not in the contract: {sorted(unknown_in_template)}. "
            f"Add them to PLACEHOLDERS here and to the sender, or fix the typo."
        )

    unknown_from_caller = set(values) - PLACEHOLDERS
    if unknown_from_caller:
        raise PlaceholderError(
            f"caller supplied value(s) for unknown placeholder(s): {sorted(unknown_from_caller)}"
        )

    missing = present - set(values)
    if missing:
        raise PlaceholderError(
            f"no value supplied for placeholder(s) still in the template: {sorted(missing)}"
        )

    # Single pass, and deliberately NOT recursive: a value is data, not another
    # template. Re-expanding it would let post content reach into the placeholder
    # contract, so a title containing token-looking text is passed through as the
    # literal characters the author wrote.
    #
    # ESCAPED, because every value lands in HTML and some of them land inside a
    # double-quoted ATTRIBUTE. email.html:102 is `alt="%%HERO_ALT%%"`, and
    # `_PostExtractor` runs with convert_charrefs=True, so an og:image:alt written
    # as `&quot;` arrives here as a literal `"` and closes the attribute early:
    # everything after it becomes markup in the delivered campaign. Measured, not
    # imagined -- the live corpus already carries a bare `&` in three og:image:alt
    # values ("Food & Booze", "Hen & Chickens Pub Grill", "Tech & AI"), which is
    # already invalid inside an attribute; a single `"` in any alt text or title
    # turns that from invalid into injectable. Found by Ralph round 7 tier 2.
    #
    # quote=True so `"` becomes `&quot;`. Safe for all eight values: the two Brevo
    # merge tags contain none of the escaped characters and pass through untouched,
    # and `&` in a URL becoming `&amp;` is the CORRECT encoding for an href, which
    # every client decodes back.
    out = _PLACEHOLDER_RE.sub(
        lambda m: html.escape(values[m.group(1)], quote=True), template_text
    )

    # Defence in depth. The checks above already guarantee every TEMPLATE token had
    # a value, so anything surviving here must have arrived inside a value. That is
    # legitimate (see above); a survivor traceable to no value would mean the
    # substitution itself is broken, which is worth failing loudly for.
    survivors = tokens_in(out)
    if survivors:
        from_values: set[str] = set()
        for v in values.values():
            from_values |= tokens_in(v)
        unexplained = survivors - from_values
        if unexplained:
            raise PlaceholderError(
                f"substitution left token(s) behind that came from no value: "
                f"{sorted(unexplained)}. The renderer is broken, not the input."
            )
    return out


# Sample content for the preview only. Deliberately NOT a real post: a preview that
# happens to look like a genuine send is the kind of screenshot that later gets
# mistaken for proof that something was sent.
PREVIEW_VALUES = {
    "FIRSTNAME": "Sam",
    "POST_TITLE": "A sample post title, roughly the length a real one runs to",
    "POST_DATE": "7 August 2026",
    "POST_EXCERPT": (
        "This is sample excerpt copy standing in for a post's frontmatter description, "
        "at about the length those actually run, so the preview shows realistic wrapping "
        "rather than one short line."
    ),
    "POST_URL": "https://hoiboy.uk/blogs/sample-post/",
    "HERO_URL": "https://hoiboy.uk/blogs/sample-post/hero.jpg",
    "HERO_ALT": "A sample post title, roughly the length a real one runs to",
    "UNSUBSCRIBE_URL": "https://hoiboy.uk/legal/privacy/",
}


def preview(out_path: Path, width: int = 700) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "playwright is not installed. `pip install playwright && playwright install chromium`",
            file=sys.stderr,
        )
        return 2

    if not TEMPLATE.is_file():
        print(f"template not found: {TEMPLATE}", file=sys.stderr)
        return 2

    # Caught rather than allowed to propagate, so this entry point answers the way
    # its two guards above already do: a sentence and a status, not a traceback.
    # The sender had the same hole in a worse place (a PlaceholderError escaped
    # main()'s handler entirely, losing the fatal audit line), and there is no
    # reason for the preview command to behave differently from the send command
    # when the same template fails to render.
    try:
        html = render(TEMPLATE.read_text(encoding="utf-8"), PREVIEW_VALUES)
    except PlaceholderError as exc:
        print(f"the template did not render: {exc}", file=sys.stderr)
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # A real inbox is not a bare fragment, so wrap it the way a client would and
    # keep the viewport a little wider than the 600px column to show the gutter.
    page_html = (
        "<!doctype html><html><head><meta charset='utf-8'></head>"
        f"<body style='margin:0'>{html}</body></html>"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.set_content(page_html, wait_until="load")
            page.screenshot(path=str(out_path), full_page=True)
        finally:
            browser.close()

    print(f"wrote {out_path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--preview",
        metavar="PNG",
        required=True,
        help="render the template with sample values and write a full-page PNG here",
    )
    ap.add_argument("--width", type=int, default=700, help="viewport width (default 700)")
    args = ap.parse_args()
    return preview(Path(args.preview).expanduser(), args.width)


if __name__ == "__main__":
    raise SystemExit(main())
