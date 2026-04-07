#!/usr/bin/env python3
"""Config traceability: every key in params.toml is read by layouts/.

Greps layouts/ (NOT vendored themes) for each top-level key in params.toml.
Dead key (declared but never read) = FAIL. Standards Fail Fast.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARAMS = ROOT / "config" / "_default" / "params.toml"
LAYOUTS = ROOT / "layouts"
ASSETS = ROOT / "assets"

# Keys we declare but do not directly grep for in layouts (e.g. provenance,
# read indirectly via the build pipeline). Document each exemption.
EXEMPT = {
    "build",        # nested table, populated by CI for build-info.json
    "hugoVersion",
    "commitSha",
}


def extract_keys(toml: str) -> list[str]:
    keys: list[str] = []
    for line in toml.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line and not line.startswith("["):
            key, _, _ = line.partition("=")
            keys.append(key.strip())
    return keys


def main() -> int:
    if not PARAMS.exists():
        print(f"FAIL: {PARAMS} missing", file=sys.stderr)
        return 1
    if not LAYOUTS.exists():
        print(f"FAIL: {LAYOUTS} missing", file=sys.stderr)
        return 1

    keys = extract_keys(PARAMS.read_text(encoding="utf-8"))
    layout_text = ""
    for f in LAYOUTS.rglob("*.html"):
        layout_text += f.read_text(encoding="utf-8")
    if ASSETS.exists():
        for f in ASSETS.rglob("*.css"):
            layout_text += f.read_text(encoding="utf-8")

    dead: list[str] = []
    for k in keys:
        if k in EXEMPT:
            continue
        if k not in layout_text:
            dead.append(k)

    if dead:
        print("CONFIG TRACEABILITY FAILED:", file=sys.stderr)
        for k in dead:
            print(f"  dead key in params.toml: {k}", file=sys.stderr)
        return 1
    print(f"Config traceability OK ({len(keys)} keys, {len(EXEMPT)} exempt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
