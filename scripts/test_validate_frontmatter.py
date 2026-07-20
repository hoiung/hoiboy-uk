"""Unit tests for validate_frontmatter.py parser.

Run: python3 -m pytest scripts/test_validate_frontmatter.py -q
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import validate_frontmatter as vf
from validate_frontmatter import parse_frontmatter, REQUIRED, CONSULTING_REQUIRED


POST_FM = ('---\ntitle: "x"\ndate: 2026-04-07\ncategories: [tech-ai]\n'
           'tags: [a]\ndescription: "A unique summary."\n---\nbody\n')
PAGE_FM = '---\ntitle: "Svc"\ndescription: "A unique summary."\nhideDate: true\n---\nbody\n'


def _bundle(root: Path, slug: str, text: str, name: str = "index.md") -> None:
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(text, encoding="utf-8")


def _run(monkeypatch, tmp_path, posts_files, consulting_files, argv=None):
    """Point the validator at a temp tree and run main()."""
    posts, consulting = tmp_path / "posts", tmp_path / "consulting"
    posts.mkdir(exist_ok=True)
    consulting.mkdir(exist_ok=True)
    for slug, text in posts_files:
        _bundle(posts, slug, text)
    for slug, text in consulting_files:
        name = "_index.md" if slug.endswith("/section") else "index.md"
        _bundle(consulting, slug.removesuffix("/section"), text, name)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", consulting)
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    return vf.main(argv or [])


def test_basic_frontmatter():
    text = '---\ntitle: "Hello"\ndate: 2026-04-07\ncategories: [tech]\ntags: [a, b]\n---\nbody'
    fm = parse_frontmatter(text)
    assert fm is not None
    assert fm["title"] == "Hello"
    assert fm["date"] == "2026-04-07"
    assert fm["categories"] == ["tech"]
    assert fm["tags"] == ["a", "b"]


def test_colon_in_title():
    text = '---\ntitle: "Why: a manifesto"\ndate: 2026-04-07\ncategories: [tech]\ntags: [test]\n---\nbody'
    fm = parse_frontmatter(text)
    assert fm is not None
    assert fm["title"] == "Why: a manifesto"


def test_unquoted_value():
    text = '---\ntitle: bare title\ndate: 2026-04-07\ncategories: [tech]\ntags: [foo]\n---\n'
    fm = parse_frontmatter(text)
    assert fm["title"] == "bare title"


def test_multiple_tags():
    text = '---\ntitle: "x"\ndate: 2026-04-07\ncategories: [adventure]\ntags: [hike, mountains, "new zealand"]\n---\n'
    fm = parse_frontmatter(text)
    assert fm["tags"] == ["hike", "mountains", "new zealand"]


def test_no_frontmatter():
    assert parse_frontmatter("just body, no fence") is None


def test_unclosed_frontmatter():
    assert parse_frontmatter("---\ntitle: x\nno closing") is None


def test_required_fields_match_contract():
    # `description` promoted OPTIONAL -> REQUIRED 2026-07-20 (blog-priv#55 Phase 2).
    assert REQUIRED == {"title", "date", "categories", "tags", "description"}


def test_consulting_contract_is_smaller_than_post_contract():
    # Project pages have no categories/tags taxonomy and several carry no date
    # (service pages set hideDate). Applying the post contract would hard-fail
    # a compliant tree.
    assert CONSULTING_REQUIRED == {"title", "description"}
    assert CONSULTING_REQUIRED < REQUIRED


def test_draft_flag_optional():
    text = ('---\ntitle: "x"\ndate: 2026-04-07\ncategories: [tech]\ntags: [a]\n'
            'description: "d"\ndraft: true\n---\n')
    fm = parse_frontmatter(text)
    assert fm["draft"] == "true"
    missing = REQUIRED - set(fm.keys())
    assert not missing


# --- Gate behaviour: description is enforced, not merely declared (AC 2.2/2.6) ---

def test_post_missing_description_fails(monkeypatch, tmp_path, capsys):
    no_desc = '---\ntitle: "x"\ndate: 2026-04-07\ncategories: [tech-ai]\ntags: [a]\n---\nbody\n'
    rc = _run(monkeypatch, tmp_path, [("legacy", no_desc)], [])
    assert rc == 1
    assert "missing ['description']" in capsys.readouterr().err


def test_post_with_description_passes(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, [("good", POST_FM)], []) == 0


def test_project_page_missing_description_fails(monkeypatch, tmp_path, capsys):
    # Pre-fix this file was not even read: the validator walked content/posts/ only.
    no_desc = '---\ntitle: "Svc"\nhideDate: true\n---\nbody\n'
    rc = _run(monkeypatch, tmp_path, [], [("a-service", no_desc)])
    assert rc == 1
    assert "missing ['description']" in capsys.readouterr().err


def test_project_page_with_description_passes(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, [], [("a-service", PAGE_FM)]) == 0


def test_nested_portfolio_page_is_walked(monkeypatch, tmp_path, capsys):
    no_desc = '---\ntitle: "Client"\nhideDate: true\n---\nbody\n'
    rc = _run(monkeypatch, tmp_path, [], [("portfolio/client-x", no_desc)])
    assert rc == 1
    assert "portfolio/client-x" in capsys.readouterr().err


def test_consulting_section_page_is_walked(monkeypatch, tmp_path, capsys):
    # rglob("index.md") does NOT match _index.md; section pages need their own glob.
    no_desc = '---\ntitle: "Consulting"\n---\nbody\n'
    rc = _run(monkeypatch, tmp_path, [], [("portfolio/section", no_desc)])
    assert rc == 1
    assert "_index.md" in capsys.readouterr().err


def test_project_page_not_held_to_post_contract(monkeypatch, tmp_path):
    # No date, no categories, no tags: valid for a project page, invalid for a post.
    assert _run(monkeypatch, tmp_path, [], [("svc", PAGE_FM)]) == 0


def test_scope_posts_skips_consulting(monkeypatch, tmp_path):
    bad_page = '---\ntitle: "Svc"\n---\nbody\n'
    assert _run(monkeypatch, tmp_path, [("good", POST_FM)], [("svc", bad_page)],
                argv=["--scope", "posts"]) == 0


def test_scope_consulting_skips_posts(monkeypatch, tmp_path):
    bad_post = '---\ntitle: "x"\ndate: 2026-04-07\ncategories: [tech-ai]\ntags: [a]\n---\nbody\n'
    assert _run(monkeypatch, tmp_path, [("legacy", bad_post)], [("svc", PAGE_FM)],
                argv=["--scope", "consulting"]) == 0


def test_default_scope_covers_both_trees(monkeypatch, tmp_path):
    bad_page = '---\ntitle: "Svc"\n---\nbody\n'
    # Bare invocation (what pre-commit and CI run) must catch a bad project page.
    assert _run(monkeypatch, tmp_path, [("good", POST_FM)], [("svc", bad_page)]) == 1


def test_unknown_category_still_fails(monkeypatch, tmp_path, capsys):
    bad_cat = ('---\ntitle: "x"\ndate: 2026-04-07\ncategories: [foood]\ntags: [a]\n'
               'description: "d"\n---\nbody\n')
    rc = _run(monkeypatch, tmp_path, [("typo", bad_cat)], [])
    assert rc == 1
    assert "unknown categories" in capsys.readouterr().err


def test_missing_trees_are_not_an_error(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, [], []) == 0
