#!/usr/bin/env python3
"""static/_redirects ordering, status codes and chain-freedom (blog-priv#62).

  AC 5.4   - the ai-jargon alias resolves, and it resolves because of its
             POSITION. Cloudflare applies the top-most matching rule, not the
             most specific one, so `/posts/*` placed above the alias would send
             /posts/ai-jargon-for-noobs/ to a dead /blogs/ai-jargon-for-noobs/.
             Placement IS the fix, so placement is what is asserted.
  AC 5.15a - every rule is 301. A 302 tells search engines the move is temporary
             and the ranking stays on the retired URL.
  AC 5.15b - no redirect chains: no rule's target is another rule's source. Each
             hop costs latency and bleeds link equity, and a two-hop chain is how
             a redirect set quietly stops passing authority.

Usage:  python3 scripts/test_redirects_order.py
Exit 0 = clean. Exit 1 = a named failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from redirects_rules import Rule, parse, resolve  # noqa: E402

REDIRECTS = ROOT / "static" / "_redirects"

# The one post whose published path is not its bundle directory name.
ALIAS_SOURCE = "/posts/ai-jargon-for-noobs/"
ALIAS_TARGET = "/blogs/ai-jargon-for-newbies/"


def check_alias_order(rules: list[Rule], failures: list[str]) -> None:
    """AC 5.4 - the alias resolves AND it precedes the wildcard that would eat it."""
    hit = resolve(rules, ALIAS_SOURCE)
    if hit is None:
        failures.append(f"AC 5.4: {ALIAS_SOURCE} matches no rule at all")
        return
    rule, target = hit
    if target != ALIAS_TARGET:
        failures.append(
            f"AC 5.4: {ALIAS_SOURCE} resolves to {target} (line {rule.line_no}), not "
            f"{ALIAS_TARGET}. That URL is not served, so the link is dead."
        )
    # Position, asserted independently of the resolution above: a future edit that
    # moved the wildcard up would still resolve correctly today only by accident of
    # rule text, and this is the assertion that would catch it.
    wildcards = [r for r in rules if r.source == "/posts/*"]
    if not wildcards:
        failures.append("AC 5.4: no /posts/* wildcard exists, so the 79 post URLs "
                        "are not covered")
        return
    aliases = [r for r in rules if r.source.startswith("/posts/ai-jargon-for-noobs")]
    if not aliases:
        failures.append("AC 5.4: no explicit rule for the ai-jargon alias")
        return
    if min(r.index for r in aliases) > min(r.index for r in wildcards):
        failures.append(
            f"AC 5.4: the ai-jargon alias (line {min(r.line_no for r in aliases)}) sits "
            f"BELOW /posts/* (line {min(r.line_no for r in wildcards)}). Cloudflare "
            f"applies the top-most match, so the wildcard swallows it."
        )


def check_all_permanent(rules: list[Rule], failures: list[str]) -> None:
    """AC 5.15a - 301 everywhere, including rules that omitted the status entirely
    (Cloudflare defaults an absent status to 302, so an omission is a defect)."""
    for r in rules:
        if r.status != "301":
            failures.append(
                f"AC 5.15a: {REDIRECTS.name}:{r.line_no} `{r.source}` uses status "
                f"{r.status}, not 301. A temporary redirect leaves the ranking on the "
                f"retired URL."
            )


def check_no_chains(rules: list[Rule], failures: list[str]) -> None:
    """AC 5.15b - no rule's TARGET is itself matched by another rule."""
    for r in rules:
        # Compare the literal part: a :splat target is a family of URLs, and the
        # question is whether ANY of them would be redirected again.
        target = r.target.replace(":splat", "")
        hit = resolve(rules, target)
        if hit is None:
            continue
        hit_rule, second = hit
        if hit_rule.index == r.index:
            continue                       # a rule matching its own target prefix
        failures.append(
            f"AC 5.15b: redirect chain. {REDIRECTS.name}:{r.line_no} sends "
            f"`{r.source}` -> `{r.target}`, which line {hit_rule.line_no} then sends "
            f"on to `{second}`. Point the first rule at the final destination."
        )


def main() -> int:
    failures: list[str] = []
    if not REDIRECTS.is_file():
        print(f"FAIL: {REDIRECTS} does not exist", file=sys.stderr)
        return 1
    rules = parse(REDIRECTS)
    if not rules:
        print(f"FAIL: {REDIRECTS} parsed to zero rules (vacuous pass)", file=sys.stderr)
        return 1

    check_alias_order(rules, failures)
    check_all_permanent(rules, failures)
    check_no_chains(rules, failures)

    if failures:
        print(f"FAIL: {len(failures)} redirect-ordering violation(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print(f"OK: {len(rules)} redirect rules, all 301, no chains, and the ai-jargon "
          f"alias sits above the /posts/* wildcard that would otherwise swallow it")
    return 0


def test_redirects_order() -> None:
    """pytest entry point (CI runs pytest through explicit file lists)."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
