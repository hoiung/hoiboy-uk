"""Self-test for ``validate_internal_links.py`` (per Issue #23 AC 2.6;
satisfies dotfiles#460 W4 pending improvement — every new pre-commit
hook must be self-tested on a contrived input that exercises the new
logic at least once).

Three contrived inputs:
 * ``valid.md``               — exercise every PASS path, expect exit 0
 * ``bad_section_prefix.md``  — exercise the section-prefix FAIL path
 * ``bad_post_slug.md``       — exercise the missing-post-bundle FAIL path

Tests invoke the validator as a subprocess so the CLI surface is exercised
end-to-end (argparse, repo_root resolution, exit codes, stderr format).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "validate_internal_links.py"
FIXTURES = REPO_ROOT / "scripts" / "tests" / "fixtures" / "validate_internal_links_fixtures"


def _run(*paths: Path) -> subprocess.CompletedProcess[str]:
    """Run the validator against ``paths`` (or content/ tree if empty)
    using the real repo root so post-bundle lookups resolve."""
    cmd = [sys.executable, str(SCRIPT), "--repo-root", str(REPO_ROOT), *map(str, paths)]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def test_valid_fixture_exits_zero() -> None:
    result = _run(FIXTURES / "valid.md")
    assert result.returncode == 0, (
        f"valid.md should pass; got exit {result.returncode}\n"
        f"stderr:\n{result.stderr}"
    )
    assert result.stderr == "", f"valid.md emitted unexpected stderr:\n{result.stderr}"


def test_bad_section_prefix_exits_one() -> None:
    result = _run(FIXTURES / "bad_section_prefix.md")
    assert result.returncode == 1, (
        f"bad_section_prefix.md should fail; got exit {result.returncode}\n"
        f"stderr:\n{result.stderr}"
    )
    # Error must reference the section ('dance') AND the suggested correction ('/posts/').
    assert re.search(r"dance.*did you mean /posts/", result.stderr, re.IGNORECASE), (
        f"expected 'dance ... did you mean /posts/' hint; got:\n{result.stderr}"
    )


def test_bad_post_slug_exits_one() -> None:
    result = _run(FIXTURES / "bad_post_slug.md")
    assert result.returncode == 1, (
        f"bad_post_slug.md should fail; got exit {result.returncode}\n"
        f"stderr:\n{result.stderr}"
    )
    # Error must mention the missing slug and identify the broken-link class.
    assert re.search(
        r"nonexistent-bogus-slug.*broken internal link",
        result.stderr,
        re.IGNORECASE | re.DOTALL,
    ), f"expected 'nonexistent...broken internal link'; got:\n{result.stderr}"


def test_ref_style_image_only_def_does_not_false_positive(tmp_path) -> None:
    """Reference-style image definitions must not be classified as links —
    image existence is out of scope, same as inline ``![alt](path)``."""
    md = tmp_path / "img_ref_only.md"
    md.write_text(
        "![alt][img]\n\n[img]: /dance/foo.jpg\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(REPO_ROOT), str(md)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"image-only ref-def must not flag as broken link; got exit "
        f"{result.returncode}\nstderr:\n{result.stderr}"
    )


def test_ref_style_used_as_both_image_and_link_still_validates(tmp_path) -> None:
    """If the same ref id is used as both ``![alt][ref]`` (image) and
    ``[text][ref]`` (link), the link use forces URL classification — image
    suppression only applies when the ref is image-only."""
    md = tmp_path / "img_and_link_ref.md"
    md.write_text(
        "![alt][shared] and [text][shared]\n\n[shared]: /dance/foo/\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(REPO_ROOT), str(md)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, (
        f"ref used as both image AND link must validate URL; got exit "
        f"{result.returncode}\nstderr:\n{result.stderr}"
    )
    assert "section-prefix" in result.stderr, result.stderr
