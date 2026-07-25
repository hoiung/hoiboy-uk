#!/usr/bin/env python3
"""Parse and apply Cloudflare Pages `static/_redirects` rules.

Shared by scripts/test_redirects_order.py (ordering + no-chains + status) and
scripts/test_redirects_coverage.py (every retired URL resolves). One parser, so
the two tests cannot disagree about what a rule means, which is the whole point:
a coverage test that resolved rules differently from the ordering test could
report full coverage for a set the CDN would never apply that way.

Cloudflare semantics reproduced here, both of them counter-intuitive:

  * ORDER, NOT SPECIFICITY. "If there are multiple redirects for the same source
    path, the top-most redirect is applied." A wildcard above a specific rule
    swallows it, so resolution walks the file top-down and stops at the first
    match rather than preferring the longest one.
  * A SLASH-LESS PATH IS ITS OWN SOURCE. `/x/*` does not match `/x`.

Library only: no CLI, no side effects.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple


class Rule(NamedTuple):
    """One `_redirects` line. `index` is its position in the file, which is what
    decides precedence."""
    index: int
    line_no: int
    source: str
    target: str
    status: str

    @property
    def is_wildcard(self) -> bool:
        return self.source.endswith("/*")

    @property
    def prefix(self) -> str:
        """The literal part of a wildcard source (`/posts/*` -> `/posts/`)."""
        return self.source[:-1] if self.is_wildcard else self.source


def parse(path: Path) -> list[Rule]:
    """Every non-comment, non-blank rule, in file order."""
    rules: list[Rule] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            raise ValueError(f"{path}:{line_no}: malformed rule {line!r}")
        source, target = parts[0], parts[1]
        status = parts[2] if len(parts) > 2 else "302"   # Cloudflare's own default
        rules.append(Rule(len(rules), line_no, source, target, status))
    return rules


def match(rule: Rule, url: str) -> str | None:
    """The target `url` resolves to under `rule`, or None if it does not match.

    `:splat` is substituted with the remainder captured by the wildcard.
    """
    if rule.is_wildcard:
        if not url.startswith(rule.prefix):
            return None
        splat = url[len(rule.prefix):]
        return rule.target.replace(":splat", splat)
    return rule.target if url == rule.source else None


def resolve(rules: list[Rule], url: str) -> tuple[Rule, str] | None:
    """First matching rule, top-down, with its resolved target. None if unmatched."""
    for rule in rules:
        target = match(rule, url)
        if target is not None:
            return rule, target
    return None
