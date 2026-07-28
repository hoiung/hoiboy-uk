#!/usr/bin/env python3
"""Mutation tests for the landing-sync gate (hoiboy-uk#54 AC 3.2 + AC 3.3).

A gate is unproven until its defect is reintroduced and it goes red, and the thing
asserted is the MESSAGE, not the exit code. An exit code alone cannot tell you the
gate failed for the reason you think: `check_landing_sync` returns 1 for a missing
landing file, an unparseable frontmatter title, a duplicate title, and both orphan
directions, so `rc == 1` is compatible with the gate being red for a reason that has
nothing to do with the defect under test.

Both mutations run against a COPY of the real content tree, not a fixture invented
here. A hand-built fixture would prove the gate works on hand-built input, which is
not the claim. The copy is mutated and thrown away, so the working tree is never
touched and a failed test cannot strand the repo in a broken state.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "check_landing_sync", _HERE / "check_landing_sync.py"
)
cls = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = cls
_spec.loader.exec_module(cls)


@pytest.fixture()
def section_copy(tmp_path, monkeypatch):
    """A throwaway copy of the real section, with the gate pointed at it."""
    dest = tmp_path / "ai-consultancy"
    shutil.copytree(cls.SECTION, dest)
    monkeypatch.setattr(cls, "SECTION", dest)
    monkeypatch.setattr(cls, "LANDING", dest / "_index.md")
    return dest


def test_passes_on_the_real_tree():
    """The live tree must be clean, or every mutation below proves nothing."""
    assert cls.main() == 0


def test_copy_is_clean_before_mutation(section_copy):
    """Guards the fixture itself: a copy that is already red would fake both proofs."""
    assert cls.main() == 0


def test_orphan_bundle_names_the_bundle(section_copy, capsys):
    """(a) Bundle present, its `## ` block deleted -> red, naming the orphan BUNDLE."""
    landing = section_copy / "_index.md"
    title = cls._frontmatter_title(section_copy / "ai-adoption-talk" / "index.md")
    assert title == "AI Adoption Talk (FREE)"

    lines = landing.read_text(encoding="utf-8").splitlines(keepends=True)
    start = next(i for i, l in enumerate(lines) if l.startswith(f"## {title}"))
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    landing.write_text("".join(lines[:start] + lines[end:]), encoding="utf-8")

    assert cls.main() == 1
    err = capsys.readouterr().err
    assert "orphan bundle" in err, err
    assert "ai-adoption-talk" in err, err          # names the bundle, per the AC
    assert f"## {title}" in err, err               # and the block it wants back
    assert "orphan heading" not in err, err        # red for THIS reason, not the other


def test_orphan_heading_names_the_heading(section_copy, capsys):
    """(b) Block present, bundle directory renamed -> red, naming the orphan HEADING."""
    (section_copy / "ai-adoption-talk").rename(section_copy / "ai-adoption-talk-moved")

    assert cls.main() == 1
    err = capsys.readouterr().err
    assert "orphan heading" in err, err
    assert "## AI Adoption Talk (FREE)" in err, err   # names the heading, per the AC

    # The renamed directory is now an unlisted service bundle, so the gate is
    # correctly red in BOTH directions here. That is the honest reading of this
    # mutation, and asserting it stops a future edit from quietly making the
    # rename produce only one complaint.
    assert "orphan bundle" in err, err
    assert "ai-adoption-talk-moved" in err, err


def test_rename_without_updating_the_landing_names_both_titles(section_copy, capsys):
    """(c) Bundle kept, its frontmatter title changed -> red on `name mismatch`.

    The third failure branch, and the one a real rename actually hits: the slug and
    the directory are untouched, so neither orphan check fires. Only the title moved,
    which is exactly what happens when a service is renamed on its own page and the
    landing is forgotten. Without this the branch at `check_landing_sync.py:184-189`
    was live but unproven, which is the condition this file's own docstring exists
    to forbid.
    """
    page = section_copy / "ai-adoption-talk" / "index.md"
    text = page.read_text(encoding="utf-8")
    assert 'title: "AI Adoption Talk (FREE)"' in text
    page.write_text(
        text.replace('title: "AI Adoption Talk (FREE)"', 'title: "AI Adoption Chat (FREE)"'),
        encoding="utf-8",
    )

    assert cls.main() == 1
    err = capsys.readouterr().err
    assert "name mismatch" in err, err
    assert "AI Adoption Chat (FREE)" in err, err     # the page's new title
    assert "## AI Adoption Talk (FREE)" in err, err  # the landing heading left behind
    assert "ai-adoption-talk" in err, err            # and the bundle they disagree about
    # Red for THIS reason: the directory never moved, so neither orphan check applies.
    assert "orphan bundle" not in err, err
    assert "orphan heading" not in err, err


def test_non_service_bundles_are_excluded_not_counted(section_copy):
    """The exclusions are named exceptions, not a count fudge.

    Naive count equality is FALSE on this tree: there are more child directories
    than service headings, and always were. If someone rewrites the gate as
    len(headings) == len(dirs) this test goes red.
    """
    dirs = [d for d in section_copy.iterdir() if d.is_dir()]
    services = cls.service_bundles()
    assert len(dirs) > len(services), (dirs, services)
    assert set(cls.NON_SERVICE_SLUGS) & {d.name for d in dirs} == set(
        cls.NON_SERVICE_SLUGS
    )


def test_service_set_is_derived_from_the_tree_not_hardcoded(section_copy, capsys):
    """A NEW bundle nobody hardcoded anywhere must be seen.

    This is the test_hub_listing.py:82 trap: that gate compares the blog hub against
    a hardcoded 7-tuple that never reads the filesystem, so a new directory is
    invisible to it. Adding a bundle here must make this gate red WITHOUT anyone
    editing a constant.
    """
    newbie = section_copy / "totally-new-service"
    newbie.mkdir()
    (newbie / "index.md").write_text(
        '---\ntitle: "Totally New Service"\n---\n\nbody\n', encoding="utf-8"
    )

    assert cls.main() == 1
    err = capsys.readouterr().err
    assert "totally-new-service" in err, err
    assert "Totally New Service" in err, err


def test_duplicate_titles_cannot_share_one_block(section_copy, capsys):
    """Two bundles with the same title would let one block stand for both."""
    dupe = section_copy / "duplicate-title-service"
    dupe.mkdir()
    (dupe / "index.md").write_text(
        '---\ntitle: "AI Adoption Talk (FREE)"\n---\n\nbody\n', encoding="utf-8"
    )

    assert cls.main() == 1
    err = capsys.readouterr().err
    assert "duplicate service titles" in err, err


def test_a_cross_link_above_the_offer_line_does_not_hijack_the_binding(section_copy, capsys):
    """A second ai-consultancy ref in a block must not rebind it (hoiboy-uk#54).

    The gate's docstring says the '[Read the full offer](...)' link is what binds
    a block to a bundle. The regex did not say that: it took the FIRST
    ai-consultancy ref anywhere in the block. Nothing forbids a service block
    carrying an ordinary cross-link, so adding one above the offer line silently
    rebound the block to that slug, and the gate then failed naming the wrong
    bundle. A failure that points at the wrong file is worse than a clean one.

    This whole file had eight tests and not one of them put two refs in a block,
    so the defect was live and unprovable at the same time.
    """
    landing = section_copy / "_index.md"
    text = landing.read_text(encoding="utf-8-sig")
    # A legitimate editorial cross-link, inserted ABOVE the offer link in the
    # first service block. Points at a real sibling bundle, so it is not a typo.
    text = text.replace(
        '[Read the full offer]({{< ref "/hire-hoi/ai-consultancy/ai-adoption-talk" >}})',
        'Costs are on the [pricing page]({{< ref "/hire-hoi/ai-consultancy/ai-adoption-training" >}}).\n\n'
        '[Read the full offer]({{< ref "/hire-hoi/ai-consultancy/ai-adoption-talk" >}})',
        1,
    )
    landing.write_text(text, encoding="utf-8")

    assert cls.main() == 0, capsys.readouterr().err


def test_a_reworded_offer_label_is_named_as_its_own_failure(section_copy, capsys):
    """Losing the label is a different defect from never having a link.

    Both leave the block unbound, but one is fixed by restoring a label and the
    other by adding a link, so they get separate messages. Without this the
    anchored regex would just report 'carries no Read the full offer link' on a
    block that visibly carries one, and the next reader would go looking for a
    link that is already there.
    """
    landing = section_copy / "_index.md"
    text = landing.read_text(encoding="utf-8-sig").replace(
        '[Read the full offer]({{< ref "/hire-hoi/ai-consultancy/ai-adoption-talk" >}})',
        '[Read more]({{< ref "/hire-hoi/ai-consultancy/ai-adoption-talk" >}})',
        1,
    )
    landing.write_text(text, encoding="utf-8")

    assert cls.main() == 1
    err = capsys.readouterr().err
    assert "unbound heading" in err, err
    assert "## AI Adoption Talk (FREE)" in err, err
    assert "ai-adoption-talk" in err, err
    # It must NOT claim the block carries no link, which is the message the
    # anchored regex would otherwise produce for a block that plainly has one.
    assert "carries no" not in err, err
