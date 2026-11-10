#!/usr/bin/env bash
# Laptop fallback for the Deploy workflow: build and push the images for the
# current commit, then roll the three apps to them. build-push.sh followed by
# redeploy.sh, with a clean-working-tree guard so the SHA-tagged images honestly
# match HEAD. For INFRA changes (Bicep, secrets, the domain) use
# ./infra/deploy.sh instead.
#
# Usage: ./scripts/ship.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# Only the committed HEAD is built (git archive), so uncommitted changes would be
# silently left out of what gets deployed.
if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: working tree is dirty. Commit (or stash) your changes first;" >&2
  echo "       only the committed HEAD is built and deployed." >&2
  git status --short >&2
  exit 1
fi

SHA=$(git rev-parse HEAD)
echo "==> Building and pushing images for ${SHA:0:12}..."
./scripts/build-push.sh "$SHA"

echo "==> Rolling the apps to the new images..."
./scripts/redeploy.sh "$SHA"
