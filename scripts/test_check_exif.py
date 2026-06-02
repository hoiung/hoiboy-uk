#!/usr/bin/env python3
"""Discriminating tests for scripts/check-exif.py (hoiboy-uk #33 AC 1.4).

Each test invokes the detector exactly as CI / pre-commit does — as a subprocess
on a fixture file — and asserts the exit code. Fixtures are built at test time
from a minimal baseline JPEG (no Pillow dependency in CI): an identifying-EXIF
fixture FAILs (exit 1) and a stripped fixture PASSes (exit 0). Edge cases prove
the gate is not toothless (empty Artist / GPSVersionID-only do NOT flag).
"""
from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

import piexif

DETECTOR = Path(__file__).resolve().parent / "check-exif.py"

# A minimal 2x2 white JPEG with NO EXIF (built once with Pillow, embedded here so
# the test needs only piexif at runtime, matching requirements-dev.txt).
BASELINE_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDACgcHiMeGSgjISMtKygwPGRBPDc3PHtYXUlkkYCZlo+A"
    "jIqgtObDoKrarYqMyP/L2u71////m8H////6/+b9//j/2wBDASstLTw1PHZBQXb4pYyl+Pj4+Pj4"
    "+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj/wAARCAACAAIDASIA"
    "AhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQA"
    "AAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3"
    "ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm"
    "p6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEA"
    "AwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSEx"
    "BhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElK"
    "U1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3"
    "uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDZoooo"
    "A//Z"
)


def _run(path: Path) -> int:
    """Invoke the detector on one file; return its exit code."""
    return subprocess.run(
        [sys.executable, str(DETECTOR), str(path)],
        capture_output=True,
        text=True,
    ).returncode


def _write_jpeg(path: Path, exif: dict | None) -> Path:
    path.write_bytes(BASELINE_JPEG)
    if exif is not None:
        piexif.insert(piexif.dump(exif), str(path))  # injects EXIF in place
    return path


def test_clean_jpeg_passes(tmp_path):
    """A JPEG with no EXIF exits 0 (the stripped state)."""
    clean = _write_jpeg(tmp_path / "clean.jpg", None)
    assert _run(clean) == 0


def test_make_model_jpeg_fails(tmp_path):
    """A JPEG carrying camera Make/Model exits 1 (the dirty state)."""
    dirty = _write_jpeg(
        tmp_path / "dirty.jpg",
        {"0th": {piexif.ImageIFD.Make: b"Canon", piexif.ImageIFD.Model: b"EOS 500D"}},
    )
    assert _run(dirty) == 1


def test_artist_jpeg_fails(tmp_path):
    """A JPEG carrying a non-empty Artist exits 1."""
    dirty = _write_jpeg(
        tmp_path / "artist.jpg", {"0th": {piexif.ImageIFD.Artist: b"Jane Doe"}}
    )
    assert _run(dirty) == 1


def test_real_gps_location_fails(tmp_path):
    """A JPEG carrying a GPS latitude/longitude exits 1."""
    gps = {
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: [(51, 1), (30, 1), (0, 1)],
        piexif.GPSIFD.GPSLongitudeRef: b"W",
        piexif.GPSIFD.GPSLongitude: [(0, 1), (7, 1), (0, 1)],
    }
    dirty = _write_jpeg(tmp_path / "gps.jpg", {"GPS": gps})
    assert _run(dirty) == 1


def test_empty_artist_not_flagged(tmp_path):
    """An empty-string Artist is NOT identifying (would be a false positive)."""
    clean = _write_jpeg(tmp_path / "empty_artist.jpg", {"0th": {piexif.ImageIFD.Artist: b""}})
    assert _run(clean) == 0


def test_gps_versionid_only_not_flagged(tmp_path):
    """A GPS IFD carrying only GPSVersionID (no location) is NOT a leak."""
    clean = _write_jpeg(
        tmp_path / "gpsver.jpg",
        {"GPS": {piexif.GPSIFD.GPSVersionID: (2, 3, 0, 0)}},
    )
    assert _run(clean) == 0
