"""Unit tests for validate_frontmatter.py parser.

Run: python3 -m pytest scripts/test_validate_frontmatter.py -q
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

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
    # PyYAML types a bare `true` as a bool, not the string "true" that the old
    # hand-rolled parser stored (blog-priv#56).
    assert fm["draft"] is True
    missing = REQUIRED - set(fm.keys())
    assert not missing


# --- Gate behaviour: description is enforced, not merely declared (AC 2.2/2.6) ---

def test_post_missing_description_fails(monkeypatch, tmp_path, capsys):
    no_desc = '---\ntitle: "x"\ndate: 2026-04-07\ncategories: [tech-ai]\ntags: [a]\n---\nbody\n'
    rc = _run(monkeypatch, tmp_path, [("legacy", no_desc)], [])
    assert rc == 1
    assert "missing ['description']" in capsys.readouterr().err


def test_post_with_description_passes(monkeypatch, tmp_path):
    # Scoped to posts on purpose: this test populates only the posts tree, and
    # the vacuous-walk guard in main() now fails a scope whose tree yields
    # nothing. Declaring the scope keeps the test about what it is named after
    # instead of incidentally depending on the consulting tree.
    assert _run(monkeypatch, tmp_path, [("good", POST_FM)], [],
                argv=["--scope", "posts"]) == 0


def test_project_page_missing_description_fails(monkeypatch, tmp_path, capsys):
    # Pre-fix this file was not even read: the validator walked content/posts/ only.
    no_desc = '---\ntitle: "Svc"\nhideDate: true\n---\nbody\n'
    rc = _run(monkeypatch, tmp_path, [], [("a-service", no_desc)])
    assert rc == 1
    assert "missing ['description']" in capsys.readouterr().err


def test_project_page_with_description_passes(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, [], [("a-service", PAGE_FM)],
                argv=["--scope", "consulting"]) == 0


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
    assert _run(monkeypatch, tmp_path, [], [("svc", PAGE_FM)],
                argv=["--scope", "consulting"]) == 0


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
    # Bare invocation (what the pre-commit hook runs; CI and pre-publish.sh use
    # the disjoint --scope posts / --scope consulting pair instead) must catch a
    # bad project page.
    assert _run(monkeypatch, tmp_path, [("good", POST_FM)], [("svc", bad_page)]) == 1


def test_unknown_category_still_fails(monkeypatch, tmp_path, capsys):
    bad_cat = ('---\ntitle: "x"\ndate: 2026-04-07\ncategories: [foood]\ntags: [a]\n'
               'description: "d"\n---\nbody\n')
    rc = _run(monkeypatch, tmp_path, [("typo", bad_cat)], [])
    assert rc == 1
    assert "unknown categories" in capsys.readouterr().err


def test_check_tree_still_tolerates_a_missing_root(tmp_path):
    # check_tree is a library function and keeps its documented tolerance: a
    # missing root is simply an empty tree, which is how a partial checkout
    # behaves. The "that is suspicious" judgement lives in main(), where the
    # specific trees are known to be non-empty. See the test below.
    failures, count = vf.check_tree(tmp_path / "nope", REQUIRED, check_categories=True)
    assert (failures, count) == ([], 0)


def test_main_rejects_a_tree_that_yields_nothing(monkeypatch, tmp_path, capsys):
    # This REPLACES an earlier test that asserted empty trees exit 0. That
    # assertion encoded the defect: Ralph round 16 pointed POSTS at a
    # nonexistent path and got "Frontmatter OK (0 posts)", exit 0, passing
    # pre-commit, both pre-publish gates, both ci.yml steps and all four wiring
    # tests. A walk that finds nothing gates nothing, so every page it should
    # have checked passes by omission rather than by compliance.
    assert _run(monkeypatch, tmp_path, [], [], argv=["--scope", "posts"]) == 1
    assert "walked 0 files" in capsys.readouterr().err


# --- Walk coverage: a skipped page passes by omission, which is a false PASS ---
# Regression tests for a Ralph Tier-2 finding: the walk originally matched only
# `index.md`, so a flat single page under content/consulting/ was never read and
# the gate reported success without ever checking it.

def _flat(root: Path, name: str, text: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(text, encoding="utf-8")


def test_flat_md_project_page_is_not_skipped(monkeypatch, tmp_path, capsys):
    consulting = tmp_path / "consulting"
    _flat(consulting, "flat-page.md", '---\ntitle: "Flat"\n---\nbody\n')
    monkeypatch.setattr(vf, "POSTS", tmp_path / "posts")
    monkeypatch.setattr(vf, "CONSULTING", consulting)
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "consulting"]) == 1
    assert "flat-page.md" in capsys.readouterr().err


def test_flat_markdown_and_html_project_pages_are_not_skipped(monkeypatch, tmp_path, capsys):
    consulting = tmp_path / "consulting"
    _flat(consulting, "a.markdown", '---\ntitle: "A"\n---\nbody\n')
    _flat(consulting, "b.html", '---\ntitle: "B"\n---\n<p>x</p>\n')
    monkeypatch.setattr(vf, "POSTS", tmp_path / "posts")
    monkeypatch.setattr(vf, "CONSULTING", consulting)
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "consulting"]) == 1
    err = capsys.readouterr().err
    assert "a.markdown" in err and "b.html" in err


def test_walk_covers_the_same_formats_as_the_social_card_guard():
    # Kept identical to CONTENT_EXTS in check_social_cards.py. A narrower walk
    # here would silently exempt page shapes that guard already treats as real.
    # Import the guard and compare, rather than asserting a literal: a literal
    # cannot detect the drift this test is named for, because widening the
    # guard alone would leave it green.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_social_cards", Path(__file__).parent / "check_social_cards.py"
    )
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    assert vf.CONTENT_EXTS == guard.CONTENT_EXTS


def test_uppercase_extension_is_walked(monkeypatch, tmp_path, capsys):
    # CONTENT_EXTS is matched against p.suffix.lower(), so a page saved as
    # .MD must still be gated. Without this test the `.lower()` can be dropped
    # and the whole suite stays green while an uppercase page silently escapes
    # the contract. That `.lower()` is also the behaviour .pre-commit-config.yaml
    # cites to justify its (?i) files regex, so the two must not drift apart.
    consulting = tmp_path / "content" / "consulting"
    consulting.mkdir(parents=True)
    (consulting / "UPPER.MD").write_text('---\ntitle: "T"\n---\nbody\n', encoding="utf-8")
    monkeypatch.setattr(vf, "CONSULTING", consulting)
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "consulting"]) == 1
    assert "description" in capsys.readouterr().err


def test_posts_section_index_is_still_exempt(monkeypatch, tmp_path):
    # content/posts/_index.md is Hugo-generated and has no frontmatter contract
    # to meet; widening the walk must not start failing on it.
    posts = tmp_path / "posts"
    _flat(posts, "_index.md", '---\ntitle: "Posts"\n---\nbody\n')
    _bundle(posts, "good", POST_FM)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 0


def test_blank_value_counts_as_missing(monkeypatch, tmp_path, capsys):
    # `description:` with nothing after it satisfied a naive key-presence check
    # while Hugo's `.Description | default site.Params.description` treats ""
    # as falsy and serves the site default. The gate could pass while shipping
    # exactly the near-duplicate it exists to prevent.
    posts = tmp_path / "posts"
    blank = POST_FM.replace('description: "A unique summary."', "description:")
    assert "description:\n" in blank, "fixture rewrite did not take effect"
    _bundle(posts, "blank", blank)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 1
    assert "description" in capsys.readouterr().err


def test_block_list_categories_are_parsed_and_checked(monkeypatch, tmp_path, capsys):
    # YAML block-list form:
    #     categories:
    #       - dance
    # The parser only understood the bracketed form, so a block-list key parsed
    # to "" and the allowlist check skipped the page entirely (its isinstance
    # list-guard never fired). A typo'd category in this form shipped silently.
    # 1 of the 78 real posts uses this form.
    posts = tmp_path / "posts"
    fm = (
        '---\ntitle: "T"\ndate: 2026-01-01\n'
        "categories:\n  - nonsense-category\n"
        "tags:\n  - a\n"
        'description: "D"\n---\nbody\n'
    )
    _bundle(posts, "blocklist", fm)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 1
    assert "unknown categories" in capsys.readouterr().err


def test_block_list_categories_that_are_valid_pass(monkeypatch, tmp_path):
    # The mirror of the test above: block-list parsing must not turn a
    # correctly categorised post into a false failure, which is what happened
    # to content/posts/entrepreneurship-in-a-nutshell/ when blank values first
    # started counting as missing.
    posts = tmp_path / "posts"
    fm = (
        '---\ntitle: "T"\ndate: 2026-01-01\n'
        "categories:\n  - entrepreneurship\n  - life\n"
        "tags:\n  - a\n  - b\n"
        'description: "D"\n---\nbody\n'
    )
    _bundle(posts, "blocklist-ok", fm)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 0


@pytest.mark.parametrize("sentinel", ["null", "Null", "NULL", "~", "# TODO write this"])
def test_yaml_null_sentinels_count_as_missing(monkeypatch, tmp_path, capsys, sentinel):
    # Siblings of the blank-value case above, and the same failure end to end:
    # Ralph round 16 seeded `description: null` into a real post and the gate
    # printed "Frontmatter OK (79 posts)" and exited 0, while the built page
    # served site.Params.description verbatim. `~` is YAML's other null literal
    # and a comment-only value is null too. All are "no value" to Hugo.
    posts = tmp_path / "posts"
    nulled = POST_FM.replace('description: "A unique summary."', f"description: {sentinel}")
    assert f"description: {sentinel}" in nulled, "fixture rewrite did not take effect"
    _bundle(posts, "nulled", nulled)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 1
    assert "description" in capsys.readouterr().err


def test_quoted_value_starting_with_hash_is_still_a_real_value(monkeypatch, tmp_path):
    # Guard on the null-sentinel fix above: it is confined to UNQUOTED values on
    # purpose. A quoted description that happens to begin with '#' is a real
    # description and must keep passing, or the fix trades one false pass for a
    # false failure.
    posts = tmp_path / "posts"
    hashed = POST_FM.replace('description: "A unique summary."',
                             'description: "# hashtags, and why they died"')
    assert '"# hashtags' in hashed, "fixture rewrite did not take effect"
    _bundle(posts, "hashed", hashed)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 0


def test_a_walk_that_finds_nothing_fails_rather_than_passing(monkeypatch, tmp_path, capsys):
    # A renamed root, a typo, or a broken extension filter makes the walk return
    # zero files, and every page it should have gated then passes by omission.
    # Round 16 proved this was undefended end to end: pointing POSTS at a
    # nonexistent path printed "Frontmatter OK (0 posts)" and exited 0, through
    # pre-commit, both pre-publish gates, both ci.yml steps and all four wiring
    # tests. The tree is never legitimately empty in a real checkout.
    monkeypatch.setattr(vf, "POSTS", tmp_path / "no-such-posts-tree")
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "no-such-consulting-tree")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 1
    assert "walked 0 files" in capsys.readouterr().err


@pytest.mark.parametrize("indicator", [">", "|", ">-", "|-", ">+"])
def test_empty_block_scalar_counts_as_missing(monkeypatch, tmp_path, capsys, indicator):
    # Sibling of the null-sentinel case: an empty folded/literal block scalar
    # resolves to "" in real YAML (confirmed against PyYAML) and Hugo serves the
    # site default, but the parser stored the literal indicator ">" or "|",
    # which is non-empty, so the page passed. Ralph round 17.
    posts = tmp_path / "posts"
    empty_block = POST_FM.replace('description: "A unique summary."',
                                  f"description: {indicator}")
    assert f"description: {indicator}" in empty_block, "fixture rewrite did not take effect"
    _bundle(posts, "emptyblock", empty_block)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 1
    assert "description" in capsys.readouterr().err


def test_block_scalar_with_text_is_a_real_value(monkeypatch, tmp_path):
    # The other half of the fix, and the reason it reads the continuation lines
    # rather than just treating a bare ">" as empty: a block scalar that HAS
    # text is a real description and must pass, or the fix trades a false pass
    # for a false failure.
    posts = tmp_path / "posts"
    filled = POST_FM.replace('description: "A unique summary."',
                             "description: >\n  A real folded summary\n  over two lines.")
    _bundle(posts, "filledblock", filled)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 0


def test_block_scalar_does_not_swallow_the_next_key():
    # The block ends at the first dedented line. If it did not, every key after
    # a block scalar would vanish and its required-key check would fire falsely.
    fm = parse_frontmatter(
        '---\ntitle: "x"\ndescription: >\n  Folded text.\ncategories: [tech-ai]\n'
        'tags: [a]\ndate: 2026-04-07\n---\nbody\n'
    )
    # A folded block scalar keeps a trailing newline in real YAML; strip it for
    # the comparison, the point of the test is that the next key survives.
    assert fm["description"].strip() == "Folded text."
    assert fm["categories"] == ["tech-ai"]
    assert fm["tags"] == ["a"]


@pytest.mark.parametrize("indicator", ["|2-", ">3+", "|-2", ">+3", ">9"])
def test_block_header_accepts_digit_and_chomp_in_either_order(monkeypatch, tmp_path, capsys, indicator):
    # A YAML block header takes an optional indentation digit and an optional
    # chomping sign in EITHER order. The first regex only allowed
    # sign-then-digit, so `|2-` fell through and was stored as the literal
    # "|2-", which is non-empty: an empty block scalar written that way passed
    # the gate while Hugo served the site default. Ralph round 18.
    posts = tmp_path / "posts"
    empty = POST_FM.replace('description: "A unique summary."', f"description: {indicator}")
    assert f"description: {indicator}" in empty, "fixture rewrite did not take effect"
    _bundle(posts, "hdr", empty)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 1
    assert "description" in capsys.readouterr().err


def test_orphan_list_item_is_surfaced_as_invalid_yaml():
    # A stray dash-list line with no governing key after a block scalar is
    # invalid YAML. The hand-rolled parser silently invented a shape for it
    # (it kept the block's resolved string, Ralph round 18); PyYAML rejects it
    # outright, and parse_frontmatter now lets that surface so check_tree fails
    # the page rather than guessing at a shape YAML never had (blog-priv#56).
    with pytest.raises(yaml.YAMLError):
        parse_frontmatter(
            '---\ntitle: "x"\ndescription: >\n  Folded text.\n- orphan item\n---\nbody\n'
        )


@pytest.mark.parametrize("sentinel", ["~ # TODO", "null # TODO", "NULL  # x", "Null # x", '"" # x', "'' # x"])
def test_null_sentinel_with_trailing_comment_counts_as_missing(monkeypatch, tmp_path, capsys, sentinel):
    # Ralph round 21 blocker. Sentinels were tested by exact match, so any
    # trailing YAML comment made `~` parse as the string "~ # TODO" and count as
    # present, while YAML reads it as null and Hugo serves the site default.
    # Proven end to end on a real build before the fix. The composition was
    # never exercised: there were tests for bare sentinels and a test for a
    # quoted value containing '#', but none for a comment AFTER a value.
    posts = tmp_path / "posts"
    seeded = POST_FM.replace('description: "A unique summary."', f"description: {sentinel}")
    assert f"description: {sentinel}" in seeded, "fixture rewrite did not take effect"
    _bundle(posts, "sentcomment", seeded)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 1
    assert "description" in capsys.readouterr().err


def test_hash_inside_a_quoted_value_is_not_treated_as_a_comment(monkeypatch, tmp_path):
    # The false failure the fix above must not introduce: a '#' inside a quoted
    # scalar is literal in YAML, so the value survives whole and still passes.
    posts = tmp_path / "posts"
    quoted = POST_FM.replace('description: "A unique summary."',
                             'description: "hello # world, a real summary"')
    _bundle(posts, "quotedhash", quoted)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 0
    fm = parse_frontmatter(quoted)
    assert fm["description"] == "hello # world, a real summary"


def test_trailing_comment_is_stripped_from_a_real_value():
    # Presence was never at risk here, but the parser now agrees with YAML on
    # the VALUE too, which is what the docstring claims.
    fm = parse_frontmatter('---\ntitle: "x"\ndescription: Real text # note\n---\nbody\n')
    assert fm["description"] == "Real text"


@pytest.mark.parametrize("shape", ['""#TODO', "''#TODO", '""#', "''#x"])
def test_quoted_empty_with_no_space_before_comment_counts_as_missing(monkeypatch, tmp_path, capsys, shape):
    # Ralph round 22. The first version of strip_trailing_comment required a
    # space before '#' on BOTH sides of a closing quote, but a closing quote is
    # itself a sufficient token boundary in YAML: `description: ""#TODO` is an
    # empty string. Requiring the space let that through as the literal
    # '""#TODO'. Valid YAML, so Hugo builds fine and the page ships the site
    # default: no downstream gate catches it.
    posts = tmp_path / "posts"
    seeded = POST_FM.replace('description: "A unique summary."', f"description: {shape}")
    assert f"description: {shape}" in seeded, "fixture rewrite did not take effect"
    _bundle(posts, "nospace", seeded)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 1
    assert "description" in capsys.readouterr().err


def test_plain_scalar_still_requires_whitespace_before_a_comment():
    # The other side of that rule, and it must NOT change: for a PLAIN scalar
    # the space really is required, so `null#TODO` is the seven-character
    # string "null#TODO" in YAML, not null. Treating it as a comment would
    # invent a missing description that YAML says is present.
    fm = parse_frontmatter('---\ntitle: "x"\ndescription: null#TODO\n---\nbody\n')
    assert fm["description"] == "null#TODO"


def test_bracket_list_with_no_space_before_comment_still_parses_as_a_list():
    # Same root cause as the quoted case, on the flow sequence: `]` closes the
    # sequence so a following '#' is a comment. Before this, the trailing text
    # broke the endswith("]") check, the value fell through as a plain string,
    # and the category allowlist silently skipped the page - the same failure
    # shape as the round-16 block-list bug.
    fm = parse_frontmatter(
        '---\ntitle: "x"\ncategories: [foood]#c\ntags: [a] # note\n---\nbody\n'
    )
    assert fm["categories"] == ["foood"]
    assert fm["tags"] == ["a"]


# --- Presence oracle: check_tree's _has_value vs real YAML --------------------
# Rounds 16 through 22 on blog-priv#55 each found a shape where the OLD
# hand-rolled parser and YAML disagreed about whether `description` had a value,
# and each fix was a hand-picked case the next round defeated with a variant:
# null, then a block scalar, then a block header ordering, then a trailing
# comment, then a trailing comment with no space. Five rounds, five variants,
# one class.
#
# blog-priv#56 ended the class by making parse_frontmatter itself yaml.safe_load,
# so a parser-vs-YAML differential is now tautological (both sides ARE yaml).
# What still CAN diverge is check_tree's presence decision - _has_value(), which
# decides whether a parsed value counts as present for the required-field gate.
# This matrix drives production's _has_value across ~292 real YAML shapes and
# asserts it agrees with an INDEPENDENT presence oracle (_present below). Break
# _has_value - drop the None check, forget the empty-collection case - and a
# shape reddens here instead of waiting for a Ralph round or a shipped
# near-duplicate.

def _present(v: object) -> bool:
    """Independent presence oracle: did YAML yield a real value here?

    Deliberately a SECOND implementation of the rule in production's
    _has_value, so the matrix below is a genuine differential between the two,
    not a tautology. KNOWN LIMIT (Ralph round 23, still true): presence is a
    YAML-layer question, so neither this nor _has_value can catch both agreeing
    while HUGO does something else - a list-valued or mapping-valued
    `description` is "present" to YAML yet discarded by Hugo. Those Hugo-
    semantics cases have their own explicit tests (test_list_valued_description
    _is_rejected and the blog-priv#56 mapping/bool/int shape tests).
    """
    if v is None:
        return False
    if isinstance(v, (list, dict)):
        return len(v) > 0
    return str(v).strip() != ""


def test_has_value_matches_real_yaml_across_a_shape_matrix():
    yaml = pytest.importorskip("yaml")
    import itertools

    values = ['""', "''", '"a"', "'a'", '"a # b"', '"#h"', '"   "', "[x]", "[x, y]", "[]",
              "null", "Null", "NULL", "~", "text", "a b", "0", '"0"', "true",
              ">", "|", ">-", "|-", "|2-", ">3+"]
    separators = ["", " ", "  "]
    tails = ["", "#c", "# c", "#", "#TODO write"]

    compared, mismatches = 0, []
    for value, sep, tail in itertools.product(values, separators, tails):
        raw = value + sep + tail
        if not raw.strip():
            continue
        line = f"description: {raw}"
        try:
            expected = yaml.safe_load(line).get("description")
        except Exception:
            continue  # invalid YAML: the real Hugo build rejects it, not our problem
        compared += 1
        got = parse_frontmatter(f'---\ntitle: "x"\n{line}\n---\nbody\n').get("description")
        # got == expected here (both parse through yaml.safe_load); the test is
        # on production's _has_value against the independent oracle, not on parse.
        if vf._has_value(got) != _present(expected):
            mismatches.append((raw, got, expected))

    assert compared > 250, f"matrix collapsed to {compared} cases; it is not exercising anything"
    assert not mismatches, (
        "check_tree's _has_value disagrees with the independent YAML presence "
        "oracle, which is how every description-gate bypass in blog-priv#55 "
        "happened:\n" + "\n".join(
            f"  {r!r}: has_value={vf._has_value(g)!r} oracle={_present(e)!r}"
            for r, g, e in mismatches
        )
    )


def test_list_valued_description_is_rejected(monkeypatch, tmp_path, capsys):
    # Hugo discards a list-valued description and serves the site default.
    # Verified on a real build: `description: [alpha, beta]` rendered
    # content="Personal blog of Hoi. ..." byte-identical to the homepage, while
    # the gate said "Frontmatter OK (80 posts)", exit 0. Presence was never the
    # problem here; the TYPE was. Ralph round 23.
    posts = tmp_path / "posts"
    listed = POST_FM.replace('description: "A unique summary."', "description: [alpha, beta]")
    assert "description: [alpha, beta]" in listed, "fixture rewrite did not take effect"
    _bundle(posts, "listdesc", listed)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 1
    assert "is a list" in capsys.readouterr().err


def test_bare_scalar_categories_is_rejected(monkeypatch, tmp_path, capsys):
    # `categories: badcategory` (no brackets) parsed to a plain string, so the
    # allowlist guard never fired and a typo'd category was never checked. Hugo
    # then hard-fails the build with "range can't iterate over badcategory",
    # so the real cost was a confusing template error at build time instead of
    # a clear message here. Ralph round 23.
    posts = tmp_path / "posts"
    bare = POST_FM.replace("categories: [tech-ai]", "categories: badcategory")
    assert "categories: badcategory" in bare, "fixture rewrite did not take effect"
    _bundle(posts, "barecat", bare)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 1
    assert "categories must be a list" in capsys.readouterr().err


def test_valid_list_shapes_still_pass(monkeypatch, tmp_path):
    # The false-failure guard for both fixes above: a normal bracketed list and
    # a block list are the shapes real posts use and must keep passing.
    posts = tmp_path / "posts"
    _bundle(posts, "bracket", POST_FM)
    block = POST_FM.replace("categories: [tech-ai]", "categories:\n  - tech-ai")
    # Distinct descriptions: this fixture puts two bundles in one tree, and the
    # uniqueness check would otherwise fail it for a reason that has nothing to
    # do with the list shapes under test.
    block = block.replace('"A unique summary."', '"A second, different summary."')
    _bundle(posts, "block", block)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 0


def test_lastmod_earlier_than_date_is_rejected(monkeypatch, tmp_path, capsys):
    # Phase 8 of this issue added the lastmod convention and gated nothing, so
    # a lastmod before date shipped silently: gate exit 0, Hugo exit 0, and the
    # page published JSON-LD dateModified BEFORE datePublished. Ralph round 24.
    posts = tmp_path / "posts"
    inverted = POST_FM.replace("date: 2026-04-07", "date: 2026-04-07\nlastmod: 2026-01-01")
    _bundle(posts, "inverted", inverted)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 1
    assert "precedes date" in capsys.readouterr().err


def test_lastmod_after_date_passes(monkeypatch, tmp_path):
    # The false-failure guard: a real revision is the whole point of the field.
    posts = tmp_path / "posts"
    ok = POST_FM.replace("date: 2026-04-07", "date: 2026-04-07\nlastmod: 2026-07-20")
    _bundle(posts, "revised", ok)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 0


def test_duplicate_categories_are_rejected(monkeypatch, tmp_path, capsys):
    # The category renders once per entry, so the built page visibly shows it
    # twice. Ralph round 24; cosmetic but a human notices it on the live page.
    posts = tmp_path / "posts"
    dup = POST_FM.replace("categories: [tech-ai]", "categories: [tech-ai, tech-ai]")
    _bundle(posts, "dup", dup)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    assert vf.main(["--scope", "posts"]) == 1
    assert "duplicate categories" in capsys.readouterr().err


def test_duplicate_description_across_two_posts_is_rejected(monkeypatch, tmp_path, capsys):
    # Presence was gated from the start; sameness was not. Copy-pasting a
    # sibling post's description produced exactly the near-duplicate this gate
    # exists to prevent, and passed every check. Surfaced by the Stage 5 audit
    # of blog-priv#55.
    other = POST_FM.replace('title: "x"', 'title: "y"')
    rc = _run(monkeypatch, tmp_path, [("a", POST_FM), ("b", other)], [],
              argv=["--scope", "posts"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "identical to" in err
    # The message must name BOTH sides, or the author has to go hunting.
    assert "posts/a/index.md" in err and "posts/b/index.md" in err


def test_duplicate_description_across_different_roots_is_rejected(monkeypatch, tmp_path, capsys):
    # The seen-map is threaded across roots by main() on purpose: a post and a
    # project page sharing one description are as duplicate as two posts. A
    # per-root map would miss this entirely.
    rc = _run(monkeypatch, tmp_path, [("p", POST_FM)], [("a-service", PAGE_FM)])
    assert rc == 1
    assert "identical to" in capsys.readouterr().err


def test_descriptions_differing_only_by_case_and_spacing_collide(monkeypatch, tmp_path, capsys):
    # Normalised before comparison: a duplicate reformatted with different
    # capitalisation or run-together whitespace is still the same text to a
    # search engine, so matching it byte-for-byte would let the common case of
    # a hand-retyped copy slip through.
    # Kept to a single line: a newline inside a quoted scalar is a shape this
    # hand-rolled parser does not represent, so folding it in here would test
    # the parser's limits rather than the normalisation under test.
    twin = POST_FM.replace('"A unique summary."', '"a   UNIQUE   summary."')
    rc = _run(monkeypatch, tmp_path, [("a", POST_FM), ("b", twin)], [],
              argv=["--scope", "posts"])
    assert rc == 1
    assert "identical to" in capsys.readouterr().err


def test_distinct_descriptions_pass(monkeypatch, tmp_path):
    # The false-failure guard: the check must not fire on genuinely different
    # text, or every real multi-post tree fails.
    other = POST_FM.replace('"A unique summary."', '"A different summary entirely."')
    assert _run(monkeypatch, tmp_path, [("a", POST_FM), ("b", other)], [],
                argv=["--scope", "posts"]) == 0


# --- blog-priv#56: the shapes the hand-rolled parser could not represent ------
# The parser stored every value as a string, so a YAML null, an empty explicit
# type tag, an alias to an empty node, a mapping, a bool and an int all became
# non-empty strings that passed the presence gate while Hugo shipped garbage or
# the site default. Rounds 16-24 on #55 hand-patched shape after shape and each
# next round found a sibling; the swap to PyYAML resolves the whole class at
# once. One regression test per surviving shape, proven the way the earlier
# ones were: run the gate on a seeded tree and assert it fails.

def _run_one_post(monkeypatch, tmp_path, fm):
    posts = tmp_path / "posts"
    _bundle(posts, "seeded", fm)
    monkeypatch.setattr(vf, "POSTS", posts)
    monkeypatch.setattr(vf, "CONSULTING", tmp_path / "consulting")
    monkeypatch.setattr(vf, "ROOT", tmp_path)
    return vf.main(["--scope", "posts"])


def test_explicit_str_tag_empty_counts_as_missing(monkeypatch, tmp_path, capsys):
    # `description: !!str` is an empty explicit-type tag: "" in YAML, so Hugo
    # serves the site default. The old parser stored the literal "!!str" and
    # passed. Body table, row 6 (unfixed in #55).
    fm = POST_FM.replace('description: "A unique summary."', "description: !!str")
    assert _run_one_post(monkeypatch, tmp_path, fm) == 1
    err = capsys.readouterr().err
    assert "missing" in err and "description" in err


def test_anchor_to_an_empty_node_counts_as_missing(monkeypatch, tmp_path, capsys):
    # `description: *a` aliasing an empty anchor resolves to null in YAML, so
    # Hugo serves the site default. The old parser stored the literal "*a" and
    # passed. Body table, row 7 (unfixed in #55).
    fm = POST_FM.replace('description: "A unique summary."', "anchored: &a\ndescription: *a")
    assert _run_one_post(monkeypatch, tmp_path, fm) == 1
    err = capsys.readouterr().err
    assert "missing" in err and "description" in err


def test_tab_indented_block_continuation_is_rejected(monkeypatch, tmp_path, capsys):
    # `description: >` then a TAB-indented line is invalid YAML (tabs cannot
    # start indentation). The old parser folded it and passed, then Hugo
    # hard-failed the build. PyYAML rejects it here, at the gate, with a clear
    # message. Body table, row 8 (unfixed in #55).
    fm = POST_FM.replace('description: "A unique summary."', "description: >\n\ttext")
    assert _run_one_post(monkeypatch, tmp_path, fm) == 1
    assert "invalid frontmatter YAML" in capsys.readouterr().err


def test_non_mapping_frontmatter_is_rejected(monkeypatch, tmp_path, capsys):
    # A fence that parses to a scalar or list, not a mapping (e.g. a stranded
    # body with no keys), would crash check_tree's `fm.items()` if it reached
    # it. parse_frontmatter raises ValueError, check_tree catches it, and the
    # page fails with a clear message. Guards that ValueError branch (Ralph #56
    # Tier 2, same class as the numeric-category and whitespace guards).
    fm = "---\njust a stranded line, no keys\n---\nbody\n"
    assert _run_one_post(monkeypatch, tmp_path, fm) == 1
    assert "invalid frontmatter YAML" in capsys.readouterr().err


def test_mapping_valued_title_is_rejected(monkeypatch, tmp_path, capsys):
    # `title: {en: "..."}` renders an empty <title>/<h1>/og:title in Hugo. The
    # worst of the four shapes in the #56 issue comment: it blanks the page's
    # heading, not just a meta field. The old parser stored the literal string.
    fm = POST_FM.replace('title: "x"', 'title: {en: "hi"}')
    assert _run_one_post(monkeypatch, tmp_path, fm) == 1
    assert "title is a mapping" in capsys.readouterr().err


def test_mapping_valued_description_is_rejected(monkeypatch, tmp_path, capsys):
    # `description: {en: "..."}` -> Hugo discards it and serves the site default
    # (the near-duplicate the gate exists to prevent). #56 issue comment.
    fm = POST_FM.replace('description: "A unique summary."', 'description: {en: "hi"}')
    assert _run_one_post(monkeypatch, tmp_path, fm) == 1
    assert "description is a mapping" in capsys.readouterr().err


def test_bool_valued_description_is_rejected(monkeypatch, tmp_path, capsys):
    # `description: true` renders the literal content="true" in Hugo. The old
    # parser stored "true" and passed the presence gate. #56 issue comment.
    fm = POST_FM.replace('description: "A unique summary."', "description: true")
    assert _run_one_post(monkeypatch, tmp_path, fm) == 1
    assert "description is a bool" in capsys.readouterr().err


def test_int_valued_description_is_rejected(monkeypatch, tmp_path, capsys):
    # `description: 12345` renders the literal content="12345" in Hugo. #56
    # issue comment.
    fm = POST_FM.replace('description: "A unique summary."', "description: 12345")
    assert _run_one_post(monkeypatch, tmp_path, fm) == 1
    assert "description is a int" in capsys.readouterr().err


def test_mapping_valued_tags_is_rejected(monkeypatch, tmp_path, capsys):
    # `tags: {a: b}` -> Hugo ranges the map and emits article:tag for the map's
    # VALUE, not its key. The old parser stored the literal string and passed
    # (tags had no type check at all). #56 issue comment.
    fm = POST_FM.replace("tags: [a]", "tags: {a: b}")
    assert _run_one_post(monkeypatch, tmp_path, fm) == 1
    assert "tags must be a list" in capsys.readouterr().err


def test_numeric_category_items_are_reported_not_crashed(monkeypatch, tmp_path, capsys):
    # PyYAML types `categories: [123]` (a typo/misuse) as a list with an int
    # item; the old string-storing parser always yielded strings. The allowlist
    # and duplicate comparisons str() each item so a non-string is reported as
    # an unknown category rather than crashing the gate with AttributeError.
    # [123, 123] exercises BOTH the unknown-category and duplicate str() wraps.
    # Guards them against a revert (Ralph #56 Tier 2).
    fm = POST_FM.replace("categories: [tech-ai]", "categories: [123, 123]")
    assert _run_one_post(monkeypatch, tmp_path, fm) == 1
    assert "unknown categories" in capsys.readouterr().err


def test_whitespace_only_description_counts_as_missing(monkeypatch, tmp_path, capsys):
    # `description: "   "` is a non-empty string, so the scalar-type check (which
    # exempts every str) waves it through; _has_value's .strip() is the ONLY
    # thing that rejects it. Hugo would render content="   ", a meaningless meta
    # description - the same near-duplicate class the gate exists to prevent.
    # Guards the .strip() in _has_value against a regression (Ralph #56 Tier 2).
    fm = POST_FM.replace('description: "A unique summary."', 'description: "   "')
    assert _run_one_post(monkeypatch, tmp_path, fm) == 1
    err = capsys.readouterr().err
    assert "missing" in err and "description" in err


def test_dates_are_normalised_to_iso_strings():
    # PyYAML types `date:` / `lastmod:` as datetime.date objects; the rest of
    # the contract (the lastmod<date check, the string compares) treats them as
    # ISO strings, so parse_frontmatter renders them back. Dropping that
    # coercion silently skips the lastmod<date check, so this guards it, and
    # test_lastmod_earlier_than_date_is_rejected is the end-to-end half.
    fm = parse_frontmatter(
        '---\ntitle: "x"\ndate: 2026-04-07\nlastmod: 2026-07-20\n'
        'categories: [tech-ai]\ntags: [a]\ndescription: "d"\n---\nbody\n'
    )
    assert fm["date"] == "2026-04-07" and isinstance(fm["date"], str)
    assert fm["lastmod"] == "2026-07-20" and isinstance(fm["lastmod"], str)


def test_missing_pyyaml_fails_loud():
    # The whole point of #56: with PyYAML unavailable the gate fails loudly, it
    # does NOT silently degrade to a hand-rolled fallback that reintroduces the
    # divergences. Run in a subprocess that blocks the yaml import so the module
    # cannot even load; assert it exits non-zero with a PyYAML message.
    code = (
        "import builtins\n"
        "_real = builtins.__import__\n"
        "def _blocked(name, *a, **k):\n"
        "    if name == 'yaml' or name.startswith('yaml.'):\n"
        "        raise ImportError('blocked for the test')\n"
        "    return _real(name, *a, **k)\n"
        "builtins.__import__ = _blocked\n"
        "import sys\n"
        f"sys.path.insert(0, {str(Path(__file__).parent)!r})\n"
        "import validate_frontmatter\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode != 0, "importing without PyYAML should fail, not succeed"
    assert "PyYAML" in result.stderr, result.stderr
