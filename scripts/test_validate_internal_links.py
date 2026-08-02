"""Self-test for ``validate_internal_links.py`` (per Issue #23 AC 2.6;
satisfies dotfiles#460 W4 pending improvement — every new pre-commit
hook must be self-tested on a contrived input that exercises the new
logic at least once).

Four contrived inputs:
 * ``valid.md``               — exercise every PASS path, expect exit 0
 * ``bad_section_prefix.md``  — exercise the section-prefix FAIL path
 * ``bad_post_slug.md``       — exercise the unserved-slug FAIL path
 * ``bad_retired_url.md``     — exercise the retired pre-/blogs/ FAIL path

Tests invoke the validator as a subprocess so the CLI surface is exercised
end-to-end (argparse, repo_root resolution, exit codes, stderr format).

``test_classify_url_contract`` additionally calls ``_classify`` directly, in
BOTH directions, on the pair blog-priv#62 AC 5.7 turns on: every ``/blogs/*``
form must be VALID and the retired ``/tech-ai/`` must be INVALID. Asserting only
the first half would pass on a validator that accepts everything.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "validate_internal_links.py"
FIXTURES = REPO_ROOT / "scripts" / "tests" / "fixtures" / "validate_internal_links_fixtures"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from validate_internal_links import _classify, _served_post_slugs  # noqa: E402


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
    # Error must reference the category ('dance') AND the suggested correction.
    assert re.search(r"dance.*did you mean /blogs/", result.stderr, re.IGNORECASE), (
        f"expected 'dance ... did you mean /blogs/' hint; got:\n{result.stderr}"
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
    # A bundle DIRECTORY name whose page is served under a frontmatter `slug:`
    # override is not a served URL either, and must be rejected by the same run.
    assert "2026-04-07-foundation" in result.stderr, (
        "a link to the bundle dir of a slug-overridden post must be rejected "
        f"(it is not the URL the site serves); got:\n{result.stderr}"
    )


def test_bad_retired_url_exits_one() -> None:
    """The pre-/blogs/ URL shapes are rejected, each named with its class."""
    result = _run(FIXTURES / "bad_retired_url.md")
    assert result.returncode == 1, (
        f"bad_retired_url.md should fail; got exit {result.returncode}\n"
        f"stderr:\n{result.stderr}"
    )
    for retired in ("/posts/same-dancers-on-the-sidelines/", "/tech-ai/", "/dance/index.xml"):
        assert retired in result.stderr, (
            f"retired URL {retired} was not flagged; got:\n{result.stderr}"
        )
    assert result.stderr.lower().count("retired url") == 3, (
        f"expected all 3 hits classified as retired; got:\n{result.stderr}"
    )


def test_classify_url_contract() -> None:
    """blog-priv#62 AC 5.7, asserted in BOTH directions.

    Accepting `/blogs/*` proves nothing on its own: a validator that returned
    True unconditionally would pass that half. The retired shapes are asserted
    INVALID in the same test so the pair discriminates.
    """
    valid = [
        "/blogs/",                              # the hub
        "/blogs/tech-ai/",                      # a category landing
        "/blogs/same-dancers-on-the-sidelines/",  # a post at its directory name
        "/blogs/foundation/",                   # a post at its frontmatter slug
        "/blogs/index.xml",                     # the section feed
        "/blogs/tech-ai/index.xml",             # a per-category feed
    ]
    invalid = [
        "/tech-ai/",                            # retired category landing
        "/dance/",
        "/posts/same-dancers-on-the-sidelines/",  # retired post URL
        "/posts/",
        "/blogs/tech-ai/some-post/",            # section-prefix bug
        "/blogs/2026-04-07-foundation/",        # bundle dir, not the served slug
        "/blogs/no-such-post/",
    ]
    for target in valid:
        ok, msg = _classify(target, REPO_ROOT)
        assert ok, f"{target} must be VALID; validator said: {msg}"
    for target in invalid:
        ok, _ = _classify(target, REPO_ROOT)
        assert not ok, f"{target} must be INVALID; validator accepted it"


def test_served_slugs_track_frontmatter_overrides() -> None:
    """The served-slug set is what the site publishes, not the directory listing.

    Both halves matter: the override must be present AND the directory name it
    replaced must be absent. Without the second half a resolver that simply
    returned every directory name would pass.
    """
    served = _served_post_slugs(REPO_ROOT)
    for slug in ("foundation", "ai-jargon-for-newbies"):
        assert slug in served, f"{slug} is served but missing from the slug set"
    for bundle_dir in ("2026-04-07-foundation", "ai-jargon-for-noobs"):
        assert bundle_dir not in served, (
            f"{bundle_dir} is a bundle directory whose page is served under a "
            f"frontmatter `slug:` override; it is not itself a served URL"
        )
    assert len(served) == len(list((REPO_ROOT / "content" / "posts").glob("*/index.md"))), (
        "every post bundle must contribute exactly one served slug"
    )


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
        "![alt][shared] and [text][shared]\n\n[shared]: /blogs/dance/foo/\n",
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


def test_zero_walk_is_a_failure_not_a_silent_pass(tmp_path):
    """An empty content/ used to exit 0 with ZERO stdout (#55 Stage 5).

    That made a run which walked nothing byte-identical in the CI log to a real
    122-file run. It matters more for this gate than most: docs/AUTHORING.md
    nominates this tier as the compensating control for keeping content/posts in
    lychee's exclude_path, so a silent zero-walk means posts have no internal-link
    coverage at all while the log still looks clean.
    """
    (tmp_path / "content").mkdir()
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(tmp_path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1, (
        f"a walk that found no markdown must fail. stdout={result.stdout} "
        f"stderr={result.stderr}"
    )
    assert "vacuous pass" in result.stderr, result.stderr


def test_a_clean_run_states_how_many_files_it_scanned(tmp_path):
    """A pass must be distinguishable from a vacuous one without reading the exit code."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(REPO_ROOT)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert re.search(r"OK \(\d+ file\(s\) scanned", result.stdout), (
        f"a clean run must state its walk size. stdout={result.stdout}"
    )


def test_an_explicit_path_list_does_not_trip_the_walk_floor(tmp_path):
    """pre-commit passes the STAGED set, which is legitimately empty on a non-md commit.

    The floor is scoped to the walk for exactly this reason; without that scoping
    every non-markdown commit would fail the hook.
    """
    md = tmp_path / "ok.md"
    md.write_text("# no links here\n")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(REPO_ROOT), str(md)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, (
        f"an explicit path list must not trip the walk floor. stderr={result.stderr}"
    )
