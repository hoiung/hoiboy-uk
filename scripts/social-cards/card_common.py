#!/usr/bin/env python3
"""Shared helpers for the social-card generators (gen_card.py, gen_agit_feature.py).

Both render an SVG through rsvg-convert with the type faces embedded as base64
@font-face rules, so the cards render identically anywhere with no system-font
dependency. These two helpers are the common bit; everything else differs
(text-only consulting cards vs photo-driven AGIT feature cards).
"""
import base64
import pathlib


def b64(path):
    """Base64-encode a file's bytes (for data: URIs)."""
    return base64.b64encode(pathlib.Path(path).read_bytes()).decode()


def font_face(family, ttf, weight):
    """An @font-face rule embedding `ttf` as a base64 data URI."""
    return (f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"src:url(data:font/ttf;base64,{b64(ttf)}) format('truetype');}}")
