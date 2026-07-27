#!/usr/bin/env python3
"""Discriminating tests for the config-traceability boundary match (#33 AC 4.2).

The pre-fix gate used a plain `key in text` substring test, which let a dead key
that is a substring of an unrelated token pass (the toothless case). These tests
assert the token-boundary `is_key_referenced` flags such keys while still
recognising real `site.Params.<key>` references.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "cct", Path(__file__).resolve().parent / "check_config_traceability.py"
)
cct = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cct)
is_key_referenced = cct.is_key_referenced


def test_substring_of_css_token_not_referenced():
    # the documented toothless case: 'accent' must NOT match '--accent-color'
    assert is_key_referenced("accent", "body { color: var(--accent-color); }") is False


def test_substring_of_camelcase_token_not_referenced():
    # 'author' must NOT match inside 'authorSameAs'
    assert is_key_referenced("author", "{{ site.Params.authorSameAs }}") is False


def test_real_param_reference_is_found():
    assert is_key_referenced("accentColor", "color: {{ site.Params.accentColor }}") is True


def test_standalone_token_is_found():
    assert is_key_referenced("author", "{{ site.Params.author }}") is True


def test_dead_key_absent_entirely():
    assert is_key_referenced("ghostKey", "no reference anywhere here") is False


def test_extract_keys_ignores_assignments_inside_a_multiline_string():
    """Prose inside a TOML multi-line value is not a key declaration.

    The line scanner read any line containing `=` as one, so a bio block with
    `something = other` in it registered as a param that layouts must then
    reference. Parsed with tomllib it simply is not a key.
    """
    toml = 'bio = """\n  notAKey = prose inside a multi-line string\n"""\naccent = "#c0533a"\n'
    assert sorted(cct.extract_keys(toml)) == ["accent", "bio"]


def test_extract_keys_finds_nested_table_keys():
    """A key inside a table is still a declared key, and must be traced."""
    toml = '[social]\ngithub = "hoiung"\n\n[build]\nstamp = true\n'
    keys = cct.extract_keys(toml)
    assert set(keys) >= {"social", "github", "build", "stamp"}


def test_extract_keys_fails_loudly_on_invalid_toml():
    """Silence here would report zero keys and pass by vacuity."""
    import pytest

    with pytest.raises(SystemExit):
        cct.extract_keys('this is = not [valid toml\n"')
