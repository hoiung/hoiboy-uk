"""Unit tests for validate_frontmatter.py parser.

Run: python3 -m pytest scripts/test_validate_frontmatter.py -q
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

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
    assert fm["description"] == "Folded text."
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


def test_orphan_list_item_does_not_overwrite_a_closed_block():
    # close_block() clears current_key, so a stray dash-list line with no
    # governing key cannot be misattributed to the block key just closed and
    # overwrite its resolved string with a list. Ralph round 18; the input is
    # invalid YAML that PyYAML rejects outright, so this only guards against
    # the parser silently inventing a different shape than YAML would.
    fm = parse_frontmatter(
        '---\ntitle: "x"\ndescription: >\n  Folded text.\n- orphan item\n---\nbody\n'
    )
    assert fm["description"] == "Folded text."


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


# --- Differential gate: this parser vs real YAML -----------------------------
# Rounds 16 through 22 each found a shape where parse_frontmatter and YAML
# disagreed about whether `description` had a value, and each fix was a
# hand-picked case that the next round defeated with a variant: null, then a
# block scalar, then a block header ordering, then a trailing comment, then a
# trailing comment with no space. Five rounds, five variants, one class.
#
# So stop hand-picking. PyYAML is the oracle and it is already a test-time
# dependency (requirements-dev.txt), which is why this lives in the tests and
# not in the validator: production keeps the hand-rolled parser per the
# operator's patch-and-ship decision, and blog-priv#56 tracks the swap.
# What this buys is that a NEW divergence fails the suite instead of waiting
# for a Ralph round to notice it.

def _present(v: object) -> bool:
    """Did YAML yield a value here, for the purpose of comparing two parsers?

    KNOWN LIMIT of the gate below, and it is structural, not an oversight
    (Ralph round 23). This function is applied to BOTH sides of the
    comparison, so it can only catch the parser disagreeing with PyYAML. It
    can never catch both agreeing while HUGO does something else, which is a
    layer above YAML. That is exactly how a list-valued `description` slipped
    through: `[x]` and `[x, y]` are already in the matrix below, both parsers
    call them present, and Hugo still discards the field and serves the site
    default. Hugo-semantics cases need their own explicit tests against a real
    build; see test_list_valued_description_is_rejected.
    """
    if v is None:
        return False
    if isinstance(v, list):
        return len(v) > 0
    return str(v).strip() != ""


def test_presence_matches_real_yaml_across_a_shape_matrix():
    yaml = pytest.importorskip("yaml")
    import itertools

    values = ['""', "''", '"a"', "'a'", '"a # b"', '"#h"', "[x]", "[x, y]", "[]",
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
        if _present(got) != _present(expected):
            mismatches.append((raw, got, expected))

    assert compared > 250, f"matrix collapsed to {compared} cases; it is not exercising anything"
    assert not mismatches, (
        "parse_frontmatter disagrees with real YAML about whether a description "
        "exists, which is how every description-gate bypass in this issue "
        f"happened:\n" + "\n".join(f"  {r!r}: ours={g!r} yaml={e!r}" for r, g, e in mismatches)
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
