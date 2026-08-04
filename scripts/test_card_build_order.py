#!/usr/bin/env python3
"""The card build is a pinned two-pass order (blog-priv#62 AC 3.0).

Card generation cannot be a single pass. A card's eyebrow comes from
public/<url>/trail.json, which only exists after Hugo renders the page; and both
generators write share-card.png into a content/ page bundle, never into static/, so
a card written after a build is absent from public/ until Hugo runs again. Getting
that order wrong does not error — it silently ships stale cards, which is exactly
the failure mode this issue exists to remove.

Four assertions:

  1. scripts/gen-social-cards.sh runs hugo exactly TWICE, with both generators
     strictly between the two, and check_social_cards.py --strict last.
  2. scripts/pre-publish.sh invokes gen-social-cards.sh.
  3. A generator run against a build with ONE trail.json removed exits non-zero and
     NAMES the page. This is the fail-loud clause: no default eyebrow, no silent
     skip. Asserted by executing it, not by reading the source.
  4. Two cases, since hoiboy-uk#56 narrowed what --strict is for. On a REAL build
     a missing rendered page now fails WITHOUT --strict, because the content tree
     says the page exists and every documented reason it would not render has
     already been excluded: that is a stale tree, not an alias edge. --strict is
     left owning the case where no trail.json sidecar exists at all, so every URL
     came from the non-permalink-aware fallback and the guard may have invented
     the URL it is complaining about. Both halves are asserted, because only the
     second one discriminates
     (the lenient default is what let a wrong url-derivation skip 87 pages
     while CI stayed green).

Usage:  python3 scripts/test_card_build_order.py [--built public]
Exit 0 = the order is pinned. Exit 1 = a named failure.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "gen-social-cards.sh"
PRE_PUBLISH = ROOT / "scripts" / "pre-publish.sh"

# Command markers, in the order they must appear.
HUGO_RE = re.compile(r"^\s*hugo\b", re.M)
GEN_CARD_RE = re.compile(r"gen_card\.py")
GEN_AGIT_RE = re.compile(r"gen_agit_feature\.py")
CHECK_RE = re.compile(r"check_social_cards\.py[^\n]*--strict")


def _code_lines(path: Path) -> str:
    """The script with comment-only lines stripped, so a command NAMED in a comment
    cannot satisfy an ordering assertion about commands actually RUN."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def check_order(failures: list[str]) -> None:
    """AC 3.0 assertion 1 — two hugo runs, generators between them, strict check last."""
    if not SCRIPT.exists():
        failures.append(f"AC 3.0: {SCRIPT.relative_to(ROOT)} does not exist")
        return
    body = _code_lines(SCRIPT)

    hugos = [m.start() for m in HUGO_RE.finditer(body)]
    if len(hugos) != 2:
        failures.append(f"AC 3.0: gen-social-cards.sh runs hugo {len(hugos)} time(s), expected exactly 2")
        return

    card = GEN_CARD_RE.search(body)
    agit = GEN_AGIT_RE.search(body)
    check = CHECK_RE.search(body)
    if not card:
        failures.append("AC 3.0: gen-social-cards.sh never invokes gen_card.py")
    if not agit:
        failures.append("AC 3.0: gen-social-cards.sh never invokes gen_agit_feature.py")
    if not check:
        failures.append("AC 3.0: gen-social-cards.sh never invokes check_social_cards.py --strict")
    if not (card and agit and check):
        return

    first, second = hugos
    for name, m in (("gen_card.py", card), ("gen_agit_feature.py", agit)):
        if not (first < m.start() < second):
            failures.append(
                f"AC 3.0: {name} does not run strictly between the two hugo builds "
                f"(hugo at {first} and {second}, {name} at {m.start()})"
            )
    if card.start() > agit.start():
        failures.append("AC 3.0: gen_agit_feature.py runs before gen_card.py; the order is pinned")
    if check.start() < second:
        failures.append("AC 3.0: check_social_cards.py --strict runs before the second hugo build, "
                        "so it would verify the pre-regeneration tree")


def check_wired(failures: list[str]) -> None:
    """AC 3.0 assertion 2 — pre-publish.sh calls it."""
    if not PRE_PUBLISH.exists():
        failures.append(f"AC 3.0: {PRE_PUBLISH.relative_to(ROOT)} does not exist")
        return
    if "gen-social-cards.sh" not in _code_lines(PRE_PUBLISH):
        failures.append("AC 3.0: scripts/pre-publish.sh does not invoke gen-social-cards.sh, so "
                        "nothing in the repo ever regenerates a card")


def _card_fingerprints() -> dict[str, tuple[int, int]]:
    """size + mtime_ns of every card in the working tree, so a test that writes one
    can be caught doing it."""
    out = {}
    for p in sorted((ROOT / "content").rglob("share-card.png")):
        st = p.stat()
        out[str(p.relative_to(ROOT))] = (st.st_size, st.st_mtime_ns)
    for name in ("share-card.png", "default-card.png"):
        p = ROOT / "content" / name
        if p.exists():
            st = p.stat()
            out[str(p.relative_to(ROOT))] = (st.st_size, st.st_mtime_ns)
    return out


def _first_carded_slug() -> str:
    """The FIRST bundle in cards.tsv — the generator's first target for that set.

    Which row is chosen matters. The generators write share-card.png into content/ page
    bundles as they go, so deleting the sidecar of a LATER row lets every earlier row
    render a real card into the working tree before the run dies. Deleting the FIRST
    row's sidecar makes it fail on its first lookup, before anything is written, and
    reading the row from the TSV rather than hardcoding it keeps that true if the file
    is reordered. (Found the hard way: an earlier version of this test named a
    mid-file row and silently regenerated a shipped card on every run.)
    """
    tsv = ROOT / "scripts" / "social-cards" / "cards.tsv"
    for raw in tsv.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            return f"hire-hoi/ai-consultancy/{line.split(chr(9))[0].strip()}"
    sys.exit(f"FAIL: {tsv} has no card rows")


def check_fail_loud(built: Path, failures: list[str]) -> None:
    """AC 3.0 assertion 3 — a missing trail.json fails the generator, naming the page.

    Executed, not read. The generator is pointed at a COPY of the built tree with one
    sidecar deleted, so the built tree is untouched; and the sidecar chosen is the
    FIRST target of the set, so the run dies during trail resolution before writing any
    card. The working tree's cards are fingerprinted either side of the run and any
    change is a failure — this test must never mutate the repo.
    """
    victim = _first_carded_slug()
    before = _card_fingerprints()
    tmp = Path(tempfile.mkdtemp(prefix="card-build-order-"))
    try:
        shutil.copytree(built, tmp / "public", symlinks=True,
                        ignore=shutil.ignore_patterns("*.png", "*.jpg", "*.webp"))
        sidecar = tmp / "public" / victim / "trail.json"
        if not sidecar.exists():
            failures.append(f"AC 3.0: cannot run the fail-loud check — no sidecar at {sidecar}")
            return
        sidecar.unlink()
        env = {**os.environ, "HOIBOY_PUBLIC_DIR": str(tmp / "public")}
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "social-cards" / "gen_card.py"), "consulting"],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )
        if proc.returncode == 0:
            failures.append(f"AC 3.0: gen_card.py exited 0 with {victim}'s trail.json removed — "
                            f"a missing trail must fail loud, not fall back to a default eyebrow")
        elif victim not in (proc.stdout + proc.stderr):
            failures.append(f"AC 3.0: gen_card.py failed on a missing trail.json but did not name "
                            f"{victim}; output was {(proc.stdout + proc.stderr)[-300:]!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    touched = [k for k, v in _card_fingerprints().items() if before.get(k) != v]
    if touched:
        failures.append(f"AC 3.0: the fail-loud check WROTE cards into the working tree: {touched}. "
                        f"This test must be side-effect free; card generation is a reviewed step "
                        f"(AC 3.7), not something a test does behind the operator's back.")


def check_strict_bites(built: Path, failures: list[str]) -> None:
    """AC 3.0 assertion 4 — --strict turns a missing rendered page into a failure.

    This assertion used to run ONE case: remove a rendered page from a real build,
    require lenient to pass and strict to fail. hoiboy-uk#56's escalation class
    sweep showed that "lenient must pass" was the fail-open itself. On a real
    build the content tree says the page exists and every documented reason it
    would not render has already been excluded, so a missing rendered page is a
    stale tree, not an alias edge, and lenient now fails too. Neither live
    --built caller passes --strict, so the lenient path is the one that runs.

    So the two cases are now split, and BOTH are asserted:

      A. Real build, page removed  -> lenient FAILS (the #56 improvement).
      B. No trail.json anywhere, page removed -> lenient passes, strict FAILS.

    B is what keeps this assertion discriminating. With no sidecars there is no
    Hugo output to read, every URL comes from the non-permalink-aware fallback,
    and the guard genuinely may have invented the URL it is complaining about —
    which is the one remaining case where silence is the right default and
    --strict is the way to break it.
    """
    victim = "legal/privacy"
    check = [sys.executable, str(ROOT / "scripts" / "check_social_cards.py")]

    # --- Case A: a real build missing a page must fail WITHOUT --strict.
    tmp_a = Path(tempfile.mkdtemp(prefix="card-stale-"))
    try:
        shutil.copytree(built, tmp_a / "public", symlinks=True,
                        ignore=shutil.ignore_patterns("*.png", "*.jpg", "*.webp"))
        page = tmp_a / "public" / victim / "index.html"
        if not page.exists():
            failures.append(f"AC 3.0: cannot run the stale-tree check — no rendered page at {page}")
            return
        page.unlink()
        lenient = subprocess.run(check + ["--built", str(tmp_a / "public")],
                                 cwd=ROOT, capture_output=True, text=True)
        if lenient.returncode == 0:
            failures.append(f"AC 3.0: the lenient check exited 0 on a real build missing "
                            f"{victim} — a partially stale tree must not pass the rendered tier")
        elif "rendered-stale" not in (lenient.stdout + lenient.stderr):
            failures.append(f"AC 3.0: the lenient check failed on a stale tree but not with "
                            f"[rendered-stale]; it may be red for an unrelated reason. Output: "
                            f"{(lenient.stdout + lenient.stderr)[-300:]!r}")
    finally:
        shutil.rmtree(tmp_a, ignore_errors=True)

    # --- Case B: with no sidecars, only --strict speaks.
    tmp_b = Path(tempfile.mkdtemp(prefix="card-strict-"))
    try:
        shutil.copytree(built, tmp_b / "public", symlinks=True,
                        ignore=shutil.ignore_patterns("*.png", "*.jpg", "*.webp"))
        page = tmp_b / "public" / victim / "index.html"
        if page.exists():
            page.unlink()
        trails = list((tmp_b / "public").rglob("trail.json"))
        if not trails:
            failures.append("AC 3.0: cannot run the --strict check — the build has no trail.json "
                            "sidecars, so case B cannot be distinguished from case A")
            return
        for t in trails:
            t.unlink()
        base = check + ["--built", str(tmp_b / "public")]
        lenient = subprocess.run(base, cwd=ROOT, capture_output=True, text=True)
        strict = subprocess.run(base + ["--strict"], cwd=ROOT, capture_output=True, text=True)
        if lenient.returncode != 0:
            failures.append(f"AC 3.0: the lenient check failed with no sidecars present "
                            f"({(lenient.stdout + lenient.stderr)[-300:]!r}); the two modes no "
                            f"longer differ, so --strict proves nothing")
        if strict.returncode == 0:
            failures.append(f"AC 3.0: check_social_cards.py --strict exited 0 with {victim}'s "
                            f"rendered page removed and no sidecars — --strict does not bite")
    finally:
        shutil.rmtree(tmp_b, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    """`argv=None` reads sys.argv, which under pytest is the pytest command line
    (file paths + flags), so argparse exits 2 before a single assertion runs. CI
    invokes these through pytest, so the entry point below passes an explicit []
    and this signature is what makes that possible."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--built", default="public", help="built site root (default: public)")
    args = ap.parse_args(argv)

    built = Path(args.built)
    if not built.is_absolute():
        built = ROOT / built

    failures: list[str] = []
    check_order(failures)
    check_wired(failures)
    if not built.is_dir():
        failures.append(f"AC 3.0: built site not found at {built} (run `hugo` first); the "
                        f"fail-loud and --strict checks need a real build")
    else:
        check_fail_loud(built, failures)
        check_strict_bites(built, failures)

    if failures:
        print(f"FAIL: {len(failures)} card-build-order violation(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("OK: two-pass card build pinned (hugo -> generators -> hugo -> strict check), "
          "wired into pre-publish.sh, fails loud on a missing trail, --strict bites")
    return 0


def test_card_build_order() -> None:
    """pytest entry point (CI runs pytest through explicit file lists)."""
    assert main([]) == 0


if __name__ == "__main__":
    sys.exit(main())
