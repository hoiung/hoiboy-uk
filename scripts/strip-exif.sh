#!/bin/sh
# Strip EXIF metadata from image files in-place via exiftool.
#
# Invoked MANUALLY before publishing a blog post with a hero image.
# NOT a pre-commit hook: exiftool -overwrite_original mutates files in-place,
# which is a documented pre-commit anti-pattern (commit succeeds with the
# unstripped file because the hook ran AFTER staging).
#
# Usage:
#   bash scripts/strip-exif.sh content/posts/<slug>/hero.webp [more.jpg ...]
#
# Issue: hoiung/bakeoff-priv#3 (Phase 1 infra).
# Exit codes: 0 = success, 1 = exiftool failure on at least one file,
#             2 = wrong usage, 127 = exiftool not installed.

set -eu

if [ "$#" -eq 0 ]; then
    printf >&2 'usage: %s <image-file> [more-files...]\n' "$0"
    printf >&2 'Supported extensions: .jpg .jpeg .png .webp\n'
    exit 2
fi

if ! command -v exiftool >/dev/null 2>&1; then
    printf >&2 'ERR: exiftool not installed.\n'
    printf >&2 'Install on Ubuntu/WSL: sudo apt-get install -y libimage-exiftool-perl\n'
    printf >&2 'Install on macOS:      brew install exiftool\n'
    exit 127
fi

rc=0
for file in "$@"; do
    if [ ! -f "$file" ]; then
        printf >&2 'ERR: not a file: %s\n' "$file"
        rc=1
        continue
    fi
    case "$file" in
        *.jpg|*.JPG|*.jpeg|*.JPEG|*.png|*.PNG|*.webp|*.WEBP) ;;
        *)
            printf >&2 'WARN: unsupported extension, skipping: %s\n' "$file"
            continue
            ;;
    esac
    if exiftool -all= -overwrite_original "$file" >/dev/null; then
        printf '[STRIPPED] %s\n' "$file"
    else
        printf >&2 'ERR: exiftool failed on %s\n' "$file"
        rc=1
    fi
done

exit "$rc"
