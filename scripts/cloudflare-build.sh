#!/usr/bin/env bash
# Cloudflare Pages build script.
# Runs Hugo, then writes public/build-info.json using Cloudflare env vars.
# Provenance lets Phase 0.8 verify the deployed commit + Hugo version.
set -euo pipefail

# Drift assert: Cloudflare Pages env var HUGO_VERSION must match .hugo-version.
PINNED=$(cat .hugo-version | tr -d '[:space:]')
if [ "${HUGO_VERSION:-}" != "$PINNED" ]; then
  echo "ERROR: HUGO_VERSION env var ($HUGO_VERSION) does not match .hugo-version ($PINNED)" >&2
  echo "Update Cloudflare Pages > Settings > Variables and Secrets > HUGO_VERSION" >&2
  exit 1
fi

hugo --gc --minify -e production

cat > public/build-info.json <<EOF
{
  "hugo_version": "${HUGO_VERSION:-unknown}",
  "commit_sha": "${CF_PAGES_COMMIT_SHA:-unknown}",
  "branch": "${CF_PAGES_BRANCH:-unknown}",
  "built_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "site": "hoiboy.uk"
}
EOF

echo "Wrote public/build-info.json:"
cat public/build-info.json
