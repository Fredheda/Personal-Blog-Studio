#!/usr/bin/env bash
# Roll the three container apps to the images built from a given commit.
# Usage: ./scripts/redeploy.sh <full-commit-sha>   (required: it never defaults
# to the local HEAD, so a checkout that is not at the commit cannot roll the
# apps to the wrong images). Rollback is this script with an older SHA.
#
# Image-only: no Bicep run, no secret. SHA tags (not `latest`) so every deploy is
# a distinct revision.
#
# Order of work:
#   1. Refuse a malformed SHA, then refuse unless ALL three images exist, so a
#      half-built commit can never leave the apps on mixed versions.
#   2. Read the tag each app runs now, then roll the apps.
#   3. Lock the three deployed tags (`acr purge` skips locked tags, so the image
#      a replica needs for its next cold start is never deleted) and unlock the
#      SHA tags the apps ran before. Nothing is locked or unlocked if a rollout
#      fails.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=lib/images.sh
source scripts/lib/images.sh

SHA="${1:-}"
if ! is_sha "$SHA"; then
  echo "usage: redeploy.sh <full 40-character commit SHA>" >&2
  exit 2
fi
echo "Deploying images for commit $SHA"

missing=0
for entry in "${IMAGES[@]}"; do
  IFS='|' read -r repo _ _ _ <<<"$entry"
  if ! image_exists "$repo" "$SHA"; then
    echo "ERROR: image $repo:$SHA is not in $ACR (build for this commit missing or unfinished)." >&2
    missing=1
  fi
done
[ "$missing" -eq 0 ] || exit 1

# The tag each app runs now, read before anything changes.
old_tags=()
for entry in "${IMAGES[@]}"; do
  IFS='|' read -r _ app _ _ <<<"$entry"
  current=$(az containerapp show -n "$app" -g "$RG" \
    --query "properties.template.containers[0].image" -o tsv)
  old_tags+=("${current##*:}")
done

for entry in "${IMAGES[@]}"; do
  IFS='|' read -r repo app _ _ <<<"$entry"
  az containerapp update -n "$app" -g "$RG" \
    --image "$ACR.azurecr.io/$repo:$SHA" --output none
done

status=0
i=0
for entry in "${IMAGES[@]}"; do
  IFS='|' read -r repo _ _ _ <<<"$entry"
  lock_tag "$repo" "$SHA" || { echo "ERROR: could not lock $repo:$SHA" >&2; status=1; }
  old="${old_tags[$i]}"
  if is_sha "$old" && [ "$old" != "$SHA" ]; then
    unlock_tag "$repo" "$old" || { echo "ERROR: could not unlock $repo:$old" >&2; status=1; }
  fi
  i=$((i + 1))
done
if [ "$status" -ne 0 ]; then
  echo "The apps ARE rolled to $SHA; only the tag locking failed. Fix it with" >&2
  echo "az acr repository update --image <repo>:<tag> --delete-enabled false." >&2
  exit "$status"
fi

FQDN=$(az containerapp show -n ca-blogstudio-web -g "$RG" \
  --query properties.configuration.ingress.fqdn -o tsv)
echo "Deployed. https://$FQDN"
