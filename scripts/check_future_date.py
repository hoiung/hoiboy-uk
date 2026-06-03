#!/usr/bin/env python3
"""Fail if a post's frontmatter `date` is in the future relative to now (UTC).

Hugo's production build silently DROPS future-dated posts (`buildFuture`
defaults off), the same way `draft: true` does, so a post-dated entry vanishes
from the live site and every category/section listing. Cloudflare builds in
UTC, while the site sets `timeZone` in hugo.toml. This check replicates Hugo's
interpretation: a bare `YYYY-MM-DD` date is read in the site timeZone, a date
with an explicit time/offset is used as-is, then the instant is compared to the
current UTC time.

See docs/AUTHORING.md section 2 ("date and the production build") and the
timeZone comment in config/_default/hugo.toml.

Usage: check_future_date.py <post.md | bundle-dir>
Exit 0 = date is now/past (will build) or unparseable (deferred to the
         frontmatter validator). Exit 1 = future (would be excluded).
"""
import os
import re
import sys
from datetime import datetime, timezone


def site_timezone(repo_root):
    """Read `timeZone = "..."` from hugo.toml; default to UTC (Hugo's default)."""
    cfg = os.path.join(repo_root, "config", "_default", "hugo.toml")
    try:
        with open(cfg, encoding="utf-8") as f:
            for line in f:
                m = re.match(r'\s*timeZone\s*=\s*"([^"]+)"', line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return "UTC"


def read_date(post_file):
    with open(post_file, encoding="utf-8") as f:
        text = f.read()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return None
    dm = re.search(r"^\s*date\s*:\s*(.+?)\s*$", m.group(1), re.M)
    if not dm:
        return None
    return dm.group(1).strip().strip('"').strip("'")


def attach_tz(naive, tzname):
    try:
        from zoneinfo import ZoneInfo

        return naive.replace(tzinfo=ZoneInfo(tzname))
    except Exception:
        # No tz database available: fall back to UTC (slightly stricter, never
        # looser, so it can over-warn but never miss a genuine future date).
        return naive.replace(tzinfo=timezone.utc)


def parse_instant(raw, tzname):
    # Full ISO 8601 with time and/or offset.
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt if dt.tzinfo else attach_tz(dt, tzname)
    except ValueError:
        pass
    # Bare YYYY-MM-DD -> midnight in the site timeZone (Hugo's behaviour).
    dm = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", raw)
    if dm:
        y, mo, d = map(int, dm.groups())
        return attach_tz(datetime(y, mo, d), tzname)
    return None


def main():
    if len(sys.argv) != 2:
        print("usage: check_future_date.py <post.md|bundle-dir>", file=sys.stderr)
        return 2
    target = sys.argv[1]
    post = os.path.join(target, "index.md") if os.path.isdir(target) else target
    if not os.path.isfile(post):
        print(f"ERR: no post file at {post}", file=sys.stderr)
        return 2

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tzname = site_timezone(repo_root)
    raw = read_date(post)
    if raw is None:
        print("  no parseable date field; deferring to frontmatter validator")
        return 0
    inst = parse_instant(raw, tzname)
    if inst is None:
        print(f"  date '{raw}' not in a recognised form; skipping future check")
        return 0

    now = datetime.now(timezone.utc)
    inst_utc = inst.astimezone(timezone.utc)
    if inst_utc > now:
        print(
            f"  FUTURE date: {raw} -> {inst_utc.isoformat()} is after now "
            f"{now.isoformat()} (UTC).",
            file=sys.stderr,
        )
        print(
            "  Hugo would DROP this post from the production build "
            "(buildFuture off) -> it vanishes from the live site + all listings.",
            file=sys.stderr,
        )
        print(
            f"  Fix: set date to today or earlier; do not post-date "
            f"(site timeZone={tzname}). See docs/AUTHORING.md section 2.",
            file=sys.stderr,
        )
        return 1
    print(f"  date {raw} -> {inst_utc.isoformat()} <= now (UTC); will build (tz={tzname})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
