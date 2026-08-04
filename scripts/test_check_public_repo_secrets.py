#!/usr/bin/env python3
"""Regression tests for the mirrored check-public-repo-secrets.py (#56 esc. B3).

This repo's CI runs the guard as a bare directory scan (`.github/workflows/ci.yml`
"Public-repo secret scan"), and the pre-commit hook runs it `--staged-only`. Those
two modes used to ask "should I open this file?" two different ways:

  directory walk  ->  f.name.lower().endswith(<SCAN_EXTENSIONS tuple>)
  staged-only     ->  Path(f).suffix.lower() in SCAN_EXTENSIONS

Two matchers for one contract. Neither opened a credential-bearing config file
that carries no extension, so a live auth token in `.npmrc`, an env-var
password assignment in a `Dockerfile` and a real `.env.local` all scored CLEAN
-- the gate reported them safe rather than declining to judge them.

(This docstring deliberately describes those shapes in words rather than
quoting them: the guard under test scans this file too, and a literal
assignment in a comment is indistinguishable from a real one.)

The canonical suite lives in dotfiles (`SST3/scripts/test_secret_guard.py`), but
this repo's CI runs `scripts/test_*.py`, not that one, so the mirrored fix is
tested here too.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

_spec = importlib.util.spec_from_file_location(
    "check_public_repo_secrets", SCRIPTS / "check-public-repo-secrets.py"
)
sec = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = sec
_spec.loader.exec_module(sec)


class TestShouldScanFile:
    """One predicate is the sole authority for both collection paths."""

    @pytest.mark.parametrize("name", [
        ".npmrc", ".netrc", ".pypirc", ".env", ".env.local", ".env.production",
        "Dockerfile", "Dockerfile.prod", "Makefile", ".gitconfig", ".htpasswd",
    ])
    def test_extensionless_config_is_scanned(self, name):
        assert sec.should_scan_file(Path(name)) is True, (
            f"{name} can carry a credential and would never have been opened"
        )

    @pytest.mark.parametrize("name", ["a.py", "a.js", "a.pem", "a.key", "a.toml"])
    def test_listed_extensions_still_scanned(self, name):
        assert sec.should_scan_file(Path(name)) is True

    @pytest.mark.parametrize("name", ["a.png", "a.jpg", "a.woff2"])
    def test_unrelated_binaries_not_scanned(self, name):
        assert sec.should_scan_file(Path(name)) is False

    def test_case_folded(self):
        assert sec.should_scan_file(Path("DOCKERFILE")) is True
        assert sec.should_scan_file(Path("KEY.PEM")) is True

    def test_exempt_filenames_are_reachable(self):
        """`.env.example` was exempted while unreachable, so the exemption was
        dead code. It must now be SELECTED and then dropped by the exemption."""
        for name in sec.EXEMPT_FILENAMES:
            assert sec.should_scan_file(Path(name)) is True
            assert sec.is_file_exempt(Path(name)) is True


class TestPlantedSecretsAreFound:
    """End-to-end: the shape the old matcher scored clean."""

    def test_all_four_planted_secrets_are_found(self, tmp_path):
        # The four fixtures are synthetic and must LOOK like real credentials --
        # that is the whole point, since the guard is what decides whether they
        # are opened. They are written into a pytest tmp_path, never committed.
        # Marked per-line rather than allowlisting the whole file, so any OTHER
        # line here keeps being scanned.
        npm_token = "//registry.npmjs.org/:_authToken=npm_" + "A" * 36 + "\n"  # secret-allow (synthetic fixture)
        pw_docker = "ENV DB_PASSWORD=hunter2supersecretvalue\n"  # secret-allow (synthetic fixture)
        pw_envloc = "DB_PASSWORD=realsecretvalue123456\n"  # secret-allow (synthetic fixture)
        pw_python = "DB_PASSWORD=alsorealsecret9876\n"  # secret-allow (synthetic fixture)

        (tmp_path / ".public-repo").write_text("", encoding="utf-8")
        (tmp_path / ".npmrc").write_text(npm_token, encoding="utf-8")
        (tmp_path / "Dockerfile").write_text(pw_docker, encoding="utf-8")
        (tmp_path / ".env.local").write_text(pw_envloc, encoding="utf-8")
        (tmp_path / "visible.py").write_text(pw_python, encoding="utf-8")

        found = {
            p.name for p in tmp_path.rglob("*")
            if p.is_file() and sec.should_scan_file(p)
            and sec.scan_file(p, blocklist=set(), allowlist=set())
        }
        assert found == {".npmrc", "Dockerfile", ".env.local", "visible.py"}, (
            f"expected all four planted secrets, got {sorted(found)}"
        )


class TestGitIgnoredFilesAreDropped:
    """A directory scan walks the filesystem, so it reaches gitignored files.

    A gitignored `.env` is where secrets are SUPPOSED to live, and firing on it
    is how a gate teaches people to bypass it. CI scans a fresh checkout where
    none exists, so this narrows nothing there.
    """

    def test_non_repo_keeps_every_candidate(self, tmp_path):
        """Cannot ask git => keep everything; over-reporting is the safe
        direction for a secret scanner."""
        cand = [tmp_path / ".npmrc"]
        assert sec._drop_git_ignored(tmp_path, cand) == cand
