"""No WhatsApp invite link is ever committed (#65 AC 5.1).

The AGIT WhatsApp invite went private because a public link let spam bots into
the groups. It now lives only in the AGIT_WHATSAPP_INVITE_URL Pages secret and
in the welcome emails sent from it. This repo is public, so one committed link
would undo that, and the shared public-repo secret scanner does not catch it
(measured 2026-10-14: phone, email and WhatsApp ID blocked, an invite URL passed).

Every tracked file is read as raw bytes, binaries included. Known limit: text
inside a compressed stream (a PDF's deflated content) is not visible to a raw
scan; this design never puts the invite into a document, so the guard covers
what it can produce. The built public/ tree is not scanned: it is built only
from tracked files, and the invite is a runtime secret, never a build input.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Built from parts so this file does not match itself.
NEEDLE = ("chat." + "whatsapp" + ".com").encode()


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z"], capture_output=True, check=True,
    ).stdout
    files = [REPO / name for name in out.decode("utf-8").split("\0") if name]
    assert files, "git ls-files returned nothing; this guard would pass while checking nothing"
    return files


def test_no_tracked_file_contains_a_whatsapp_invite_link():
    hits = []
    for path in tracked_files():
        if path.is_file() and NEEDLE in path.read_bytes().lower():
            hits.append(str(path.relative_to(REPO)))
    assert not hits, (
        f"a WhatsApp invite link is committed in {hits}. The invite is private on purpose "
        "(bots spam a public link); it belongs only in the AGIT_WHATSAPP_INVITE_URL Pages "
        "secret. Remove it, and reset the invite link in WhatsApp if it was ever pushed."
    )
