#!/usr/bin/env python3
"""Keep the newsletter email template's construction contract enforced (blog-priv#81 AC 1.8).

WHY THIS GATE EXISTS AT ALL, given the voice guard already reads the file.

`.pre-commit-config.yaml` already selects `layouts/.*\\.html` for `check-voice-tells`,
so the tells guard CAN open the template. Measured by mutation, both directions: a
banned word placed INSIDE an `<!-- iamhoi -->` region is caught and exits 1, and the
same word placed OUTSIDE one is not caught and exits 0. That second half is the
problem. The guard is marker-driven and default-SKIP, so deleting the markers does
not make it complain that the copy is now unprotected: it makes it scan nothing and
report OK. The gate is vacuous rather than absent, which is the harder failure to
notice, because the green tick still appears.

So this gate asserts the one thing the voice guard structurally cannot: that the
markers are still there. It also floors the rest of the Phase-1 construction
contract, because every one of those properties is invisible until an email lands
in somebody's inbox looking wrong, and by then it has been sent.

WHY NO ARGUMENTS. `tests/test_gate_vacuity.py` enrols every `scripts/check*.py` by
existence and runs it with no arguments against an empty-but-structurally-valid
skeleton, demanding a non-zero exit. A gate reading a fixed known path satisfies
that honestly: on an empty tree the template is missing and the coverage floor
fires, which is a real answer rather than a usage error wearing a compliant code.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_coverage import require_examined

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "layouts" / "_partials" / "newsletter" / "email.html"

MARKER_OPEN = "<!-- iamhoi -->"
MARKER_CLOSE = "<!-- iamhoiend -->"

# Matches how blog-priv#81 AC 1.3 extracts declarations. The character class stops
# at a double quote as well as a semicolon, which is why the template quotes face
# names with single quotes: a double-quoted name truncates the match before it
# reaches the generic family, and the declaration then fails this check while
# looking perfectly correct in a browser.
_FONT_DECL = re.compile(r'font-family:[^;"]*')
_GENERIC_TAIL = re.compile(r"(serif|sans-serif|monospace)\s*$")
_UNSUPPORTED_CSS = re.compile(r"var\(--|display:\s*(?:flex|grid)")

# Hugo parses every file under layouts/ as a Go template, INCLUDING inside html
# comments, so a Brevo merge tag written in its native double-curly form anywhere
# in this file fails the whole site build. Measured: exit 1 with the tag present,
# exit 0 with it removed. The template carries %%TOKEN%% placeholders instead and
# scripts/send_newsletter.py substitutes the real tags at build time.
_GO_TEMPLATE_ACTION = re.compile(r"\{\{")


def failures(text: str) -> list[str]:
    """Every contract violation in the template, so one run reports them all."""
    out: list[str] = []

    opens, closes = text.count(MARKER_OPEN), text.count(MARKER_CLOSE)
    if opens == 0:
        out.append(
            f"no {MARKER_OPEN} region: the voice guard is marker-driven and "
            f"default-SKIP, so with the markers gone it scans nothing and reports OK. "
            f"The campaign copy would ship unguarded with a green tick."
        )
    elif opens != closes:
        out.append(f"unbalanced markers: {opens} {MARKER_OPEN} vs {closes} {MARKER_CLOSE}")

    if _GO_TEMPLATE_ACTION.search(text):
        out.append(
            "contains a Go-template action '{{'. Hugo parses this file (comments "
            "included) and will fail the site build. Use a %%TOKEN%% placeholder "
            "and let the sender emit the real Brevo tag."
        )

    decls = _FONT_DECL.findall(text)
    if len(decls) < 3:
        out.append(f"only {len(decls)} font-family declaration(s); the template should carry at least 3")
    bare = [d for d in decls if not _GENERIC_TAIL.search(d)]
    if bare:
        out.append(
            f"{len(bare)} font-family declaration(s) do not end in a generic family, "
            f"so the email has no fallback where the face is absent: {bare[:3]}"
        )

    if _UNSUPPORTED_CSS.search(text):
        out.append("uses a CSS custom property or flex/grid; none survives the Outlook Word engine")

    if 'role="presentation"' not in text:
        out.append('no <table role="presentation">; the layout must be table-based for mail clients')
    if "max-width:600px" not in text:
        out.append("no 600px content column")
    if "#c0533a" not in text.lower():
        out.append("the terracotta accent #c0533a is absent; it must be a literal hex, not a token")

    return out


def main() -> int:
    present = [TEMPLATE] if TEMPLATE.is_file() else []
    require_examined(
        "check_newsletter_template",
        "newsletter email template",
        present,
        hint=(
            f"Expected {TEMPLATE.relative_to(REPO_ROOT)}. Either the checkout is "
            f"partial, or the template was moved and this gate now guards nothing."
        ),
    )

    problems = failures(TEMPLATE.read_text(encoding="utf-8"))
    if problems:
        print(f"newsletter-template: {len(problems)} contract violation(s)", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"OK: newsletter template contract holds ({TEMPLATE.relative_to(REPO_ROOT)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
