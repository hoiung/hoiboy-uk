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
