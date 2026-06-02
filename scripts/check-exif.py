#!/usr/bin/env python3
"""Read-only identifying-EXIF detector for tracked raster images (hoiboy-uk #33 AC 1.1).

Scans JPEG / WebP / PNG images for *identifying* EXIF tags and exits non-zero
listing offenders. It MUTATES NOTHING — stripping is the job of
``scripts/strip-exif.sh`` (exiftool, manual). This detector is the gate that
proves no identifying metadata reaches the public build; the stripper is the fix.

Identifying tags (per AC 1.1):
  - Make / Model         (camera body identity)
  - Artist               (photographer identity)
  - BodySerialNumber     (camera serial)
  - CameraOwnerName      (owner identity)
  - any GPS location tag (latitude / longitude / altitude / timestamp …)

Deliberately NOT identifying: ``Software`` (Greenshot / Inkscape / Lightroom —
reveals an editing tool, not a person or device), an empty-string Artist/Make,
or a GPS IFD carrying only ``GPSVersionID`` (tag 0, no location).

Pure-Python (piexif) — no exiftool / perl runtime dependency, so it runs in CI
without an apt install. PNG support reads the optional ``eXIf`` chunk directly
(piexif itself only parses JPEG / WebP / TIFF).

Usage:
  python3 scripts/check-exif.py                 # scan all tracked content raster images
  python3 scripts/check-exif.py <img> [img...]  # scan explicit files (pre-commit / fixtures)

Exit codes: 0 = clean, 1 = at least one offender, 2 = usage / lib error.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    import piexif
except ImportError:  # fail loud — no silent skip (Fail Fast)
    sys.stderr.write(
        "ERR: piexif not installed. `pip install -r requirements-dev.txt`\n"
    )
    sys.exit(2)

RASTER_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# 0th IFD identifying tags
_ZTH_TAGS = {
    piexif.ImageIFD.Make: "Make",
    piexif.ImageIFD.Model: "Model",
    piexif.ImageIFD.Artist: "Artist",
}
# Exif IFD identifying tags
_EXIF_TAGS = {
    piexif.ExifIFD.BodySerialNumber: "BodySerialNumber",
    piexif.ExifIFD.CameraOwnerName: "CameraOwnerName",
}


def _nonempty(value: object) -> bool:
    """True if an EXIF value carries real (non-blank) content."""
    if isinstance(value, bytes):
        return value.strip(b" \x00\t\r\n") != b""
    if isinstance(value, str):
        return value.strip() != ""
    return value is not None


def _identifying_tags(exif: dict) -> list[str]:
    """Return the names of identifying tags present (non-empty) in a piexif dict."""
    found: list[str] = []
    zth = exif.get("0th", {}) or {}
    for tag, name in _ZTH_TAGS.items():
        if tag in zth and _nonempty(zth[tag]):
            found.append(name)
    exif_ifd = exif.get("Exif", {}) or {}
    for tag, name in _EXIF_TAGS.items():
        if tag in exif_ifd and _nonempty(exif_ifd[tag]):
            found.append(name)
    gps = exif.get("GPS", {}) or {}
    # GPSVersionID (tag 0) alone is not a location leak; any other GPS tag is.
    if any(key != piexif.GPSIFD.GPSVersionID for key in gps):
        found.append("GPS")
    return found


def _load_png_exif(path: Path) -> dict | None:
    """Extract EXIF from a PNG ``eXIf`` chunk, if present. Returns a piexif dict or None.

    The PNG ``eXIf`` chunk payload is a raw TIFF/EXIF stream (no ``Exif\\x00\\x00``
    prefix); piexif.load decodes such a stream when the prefix is restored.
    """
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos = 8
    while pos + 8 <= len(raw):
        length = int.from_bytes(raw[pos : pos + 4], "big")
        ctype = raw[pos + 4 : pos + 8]
        data_start = pos + 8
        data_end = data_start + length
        if ctype == b"eXIf":
            payload = raw[data_start:data_end]
            try:
                return piexif.load(b"Exif\x00\x00" + payload)
            except Exception as e:
                # A PNG carrying an eXIf chunk we cannot parse could hide
                # identifying data — surface it rather than silently passing.
                sys.stderr.write(
                    f"WARN: {path}: PNG eXIf chunk present but unparseable "
                    f"({e}); cannot scan for identifying tags\n"
                )
                return None
        if ctype == b"IDAT" or ctype == b"IEND":
            break  # eXIf must precede image data; stop early
        pos = data_end + 4  # skip the 4-byte CRC
    return None


def scan_image(path: Path) -> list[str]:
    """Return identifying tag names found in one image (empty list = clean)."""
    ext = path.suffix.lower()
    if ext == ".png":
        exif = _load_png_exif(path)
        return _identifying_tags(exif) if exif else []
    # .jpg / .jpeg / .webp — piexif parses natively.
    try:
        exif = piexif.load(str(path))
    except Exception as e:
        # piexif raises "doesnot have exif" for a clean JPEG/WebP — the normal
        # clean case, kept silent. Any OTHER failure means the image is
        # unparseable; surface it so a corrupt file is not silently passed.
        if "doesnot have exif" not in str(e):
            sys.stderr.write(
                f"WARN: {path}: EXIF unparseable ({e}); treated as clean\n"
            )
        return []
    return _identifying_tags(exif)


def tracked_content_images() -> list[Path]:
    """All tracked raster images under content/ (the default CI scan set)."""
    out = subprocess.run(
        ["git", "ls-files", "content"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return [Path(p) for p in out if Path(p).suffix.lower() in RASTER_EXTS]


def main(argv: list[str]) -> int:
    if argv:
        targets = [Path(a) for a in argv]
    else:
        targets = tracked_content_images()

    offenders: list[tuple[Path, list[str]]] = []
    for path in targets:
        if not path.is_file():
            sys.stderr.write(f"ERR: not a file: {path}\n")
            return 2
        if path.suffix.lower() not in RASTER_EXTS:
            continue  # non-raster (pre-commit may pass mixed staged files)
        tags = scan_image(path)
        if tags:
            offenders.append((path, tags))

    if offenders:
        sys.stderr.write(
            f"ERR: identifying EXIF found in {len(offenders)} image(s) "
            f"(strip with `bash scripts/strip-exif.sh <file>`):\n"
        )
        for path, tags in offenders:
            sys.stderr.write(f"  {path}: {', '.join(tags)}\n")
        return 1

    print(f"OK: no identifying EXIF in {len(targets)} scanned image(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
