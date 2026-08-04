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

Exit codes:
  0 = looked, and no image carries identifying EXIF
  1 = looked, and at least one does
  2 = could NOT look: the gate's own coverage failed (nothing collected, a
      declared input absent, or a surface it could not read). Distinct from 0
      on purpose -- "no violations" and "no evidence" are opposite outcomes an
      exit-code check alone cannot tell apart (#56). Taxonomy: scripts/gate_coverage.py.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_coverage import require_examined, require_readable  # noqa: E402

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

    The walk used to stop at the first ``IDAT`` on the reasoning that ``eXIf``
    must precede image data. The PNG spec does not say that: ``eXIf`` is an
    ancillary chunk and may appear either before or after ``IDAT``, and AFTER is
    what a naive "append the metadata" tool produces. So an image carrying an
    identifying tag written that way scored clean, which is worse than not
    scanning it at all -- the gate reported it safe. Only ``IEND`` stops the walk
    now, because nothing valid follows it.
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
                # identifying data. This used to warn and return None, which
                # scan_image() cannot tell apart from "this PNG has no EXIF at
                # all" -- so the image scored clean and the warning scrolled past
                # in a green run. An unreadable surface is a coverage failure,
                # not a clean one.
                raise require_readable(
                    "check-exif", path, e,
                    remedy="Re-export the PNG, or strip it with "
                           "`bash scripts/strip-exif.sh <file>` and re-run.",
                )
        if ctype == b"IEND":
            break  # last chunk in the stream; nothing valid follows
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
        # clean case, and the only one that may return an empty list. Any OTHER
        # failure means the file could not be parsed, and the previous
        # "treated as clean" said so out loud while doing the opposite of what a
        # privacy gate on a public repo should do with an image it cannot read.
        if "doesnot have exif" not in str(e):
            raise require_readable(
                "check-exif", path, e,
                remedy="The file is corrupt or not the raster its extension "
                       "claims. Re-export it, or drop it from the repo.",
            )
        return []
    return _identifying_tags(exif)


def tracked_content_images() -> list[Path]:
    """All tracked raster images that ship in the public repo and must be EXIF-clean:
    everything under content/, plus the social-card source photos vendored under
    scripts/social-cards/ (real personal submission/portrait photos used to generate
    the branded AGIT feature cards; #47). Personal photos living outside content/ are
    otherwise a CI blind spot -- camera/GPS EXIF would land in public git history
    uncaught, since CI invokes this scan set argless."""
    out = subprocess.run(
        ["git", "ls-files", "content", "scripts/social-cards"],
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

    # `tracked_content_images()` shells out to `git ls-files`, which returns
    # nothing for a path that was renamed, for a tree checked out without
    # content/, and for a non-repo. Each of those used to end at
    # "OK: no identifying EXIF in 0 scanned image(s)" and exit 0 -- a privacy
    # gate on a PUBLIC repo reporting clean over a set it never built.
    require_examined(
        "check-exif",
        "tracked image",
        targets,
        hint="`git ls-files content scripts/social-cards` returned no raster. "
             "Either a scan root moved (fix the list in tracked_content_images) "
             "or this is not a checkout of this repo.",
    )

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
