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
import subprocess
import sys
from pathlib import Path

from unittest.mock import patch

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


class TestCoverageFloor:
    """A scan that opened no file may not report "no secrets detected".

    Named in tests/test_gate_vacuity.py's EXEMPT entry, which is why the class
    name is load-bearing: that harness cannot build an empty tree for this gate
    (its skeleton copies scripts/, which is this gate's own scan surface), so
    these stand in its place and drive the real main() instead.
    """

    def _repo(self, tmp_path, public: bool):
        """A real git repo, because the gate resolves its root from one.

        `main()` takes repo_root from `get_repo_root()` -- the git toplevel of
        the CWD -- and only the SCAN path from argv. An in-process call from
        the test session therefore reads THIS repo's `.public-repo` no matter
        what path is passed, and the first version of these tests did exactly
        that: `public=False` still resolved to a public repo and the assertions
        measured the wrong tree. Initialising a git repo and running inside it
        is what makes the marker under test the one the gate actually reads.
        """
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        if public:
            (tmp_path / ".public-repo").write_text("", encoding="utf-8")
        return tmp_path

    @staticmethod
    def _run(tmp_path, *argv: str) -> subprocess.CompletedProcess:
        """Drive the real entry point as a real process, from inside the repo.

        A subprocess rather than an in-process call so CWD (and therefore
        `get_repo_root()`) is genuinely the tree under test, and so the exit
        code asserted is the one a caller actually receives.
        """
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "check-public-repo-secrets.py"), *argv],
            cwd=tmp_path, capture_output=True, text=True, timeout=120,
        )

    def test_empty_public_repo_fails_rather_than_passing_clean(self, tmp_path):
        """The defect: 'PASS: No secrets detected' over zero collected files."""
        self._repo(tmp_path, public=True)
        r = self._run(tmp_path, ".")
        assert r.returncode == 2, (
            f"a public repo with no scannable file scored {r.returncode}; "
            f"'no secrets' was true of nothing scanned:\n{r.stdout}{r.stderr}"
        )
        assert "vacuous-gate" in r.stderr

    def test_scan_with_files_still_passes(self, tmp_path):
        """Contrast case, so the floor above cannot pass by failing everything."""
        self._repo(tmp_path, public=True)
        (tmp_path / "clean.py").write_text("x = 1\n", encoding="utf-8")
        r = self._run(tmp_path, ".")
        assert r.returncode == 0, f"a clean public repo must pass: {r.stderr}"
        assert "1 file(s) scanned" in r.stdout, (
            "the passing message must carry the count; a bare PASS is what made "
            "the empty-scan case unreadable in a green log"
        )

    def test_require_public_fails_when_marker_missing(self, tmp_path):
        """Deleting .public-repo must not silently retire the scan."""
        self._repo(tmp_path, public=False)
        (tmp_path / "clean.py").write_text("x = 1\n", encoding="utf-8")
        r = self._run(tmp_path, ".", "--require-public")
        assert r.returncode == 2, (
            f"missing marker under --require-public must fail, got "
            f"{r.returncode}:\n{r.stdout}{r.stderr}")
        assert ".public-repo does not exist" in r.stderr

    def test_private_repo_skip_is_announced(self, tmp_path):
        """A silent exit 0 is indistinguishable from a completed clean scan."""
        self._repo(tmp_path, public=False)
        r = self._run(tmp_path, ".")
        assert r.returncode == 0, f"a private repo is a no-op, not a failure: {r.stderr}"
        assert "[SKIP]" in r.stdout and "nothing scanned" in r.stdout, (
            f"the no-op must say so; got stdout={r.stdout!r}"
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

    def test_git_cannot_answer_keeps_every_candidate(self, tmp_path):
        """The fallback branch, exercised so that breaking it is observable.

        `test_non_repo_keeps_every_candidate` above reaches this branch but
        cannot DISCRIMINATE on it: git prints nothing for a non-repo, and the
        "no paths matched" branch also returns every candidate, so removing the
        exit-status check leaves that assertion still passing. Verified by
        mutation. Here the stubbed stdout NAMES the candidate, so skipping the
        check drops it and the test bites.
        """
        (tmp_path / "secrets.conf").write_text("x = 1\n", encoding="utf-8")
        cand = [tmp_path / "secrets.conf"]

        class _Result:
            returncode = 128
            stdout = str((tmp_path / "secrets.conf").resolve()) + "\n"
            stderr = "fatal: pathspec is beyond a symbolic link"

        with patch.object(sec.subprocess, "run", return_value=_Result()):
            assert sec._drop_git_ignored(tmp_path, cand) == cand, (
                "git did not answer, so nothing may be removed from the scan"
            )

    def test_tracked_file_matching_an_ignore_rule_is_still_kept(self, tmp_path):
        """The property that makes this filter safe to have at all.

        `git check-ignore` never reports a TRACKED file, even when a rule
        matches its name, so a COMMITTED secret can never be dropped by this
        filter -- only an untracked one. Paired with the untracked contrast
        case so neither can pass vacuously.
        """
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        (tmp_path / ".gitignore").write_text("secrets.conf\n", encoding="utf-8")
        (tmp_path / "secrets.conf").write_text("password=trackedsecret1\n", encoding="utf-8")  # secret-allow (synthetic fixture)
        subprocess.run(["git", "-C", str(tmp_path), "add", "-f", "secrets.conf"], check=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-qm", "track it"], check=True)
        cand = [tmp_path / "secrets.conf"]
        assert sec._drop_git_ignored(tmp_path, cand) == cand, (
            "a TRACKED file matching an ignore rule was dropped; a committed "
            "secret would then never be scanned"
        )

    def test_untracked_matching_file_is_dropped(self, tmp_path):
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        (tmp_path / ".gitignore").write_text("secrets.conf\n", encoding="utf-8")
        (tmp_path / "secrets.conf").write_text("password=untrackedsecret1\n", encoding="utf-8")  # secret-allow (synthetic fixture)
        assert sec._drop_git_ignored(tmp_path, [tmp_path / "secrets.conf"]) == []
