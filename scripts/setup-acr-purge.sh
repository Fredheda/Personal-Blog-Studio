#!/usr/bin/env bash
# Keep the registry from growing without bound: a weekly ACR Task runs
# `acr purge` on this project's three image repositories only.
#
# Default (a DRY RUN, nothing is changed or deleted): prints which running tags
# it would lock, then runs the purge once with --dry-run and prints what it would
# delete. Read that list first.
#
# --apply (needs the owner's yes) locks the SHA tag each container app runs right
# now, so the purge can never delete an image a replica needs for its next cold
# start (the Deploy workflow and redeploy.sh keep these locks up to date
# afterwards), and creates or replaces the weekly task `purge-blogstudio-images`,
# Sundays 03:00 UTC, with the same command minus --dry-run.
#
# What it deletes: tags that are a full 40-character git SHA, in blogstudio-web,
# blogstudio-api and blogapi only, older than 30 days, but always keeping the
# newest 10 per repository; --untagged also removes the manifests those deletions
# leave behind. `latest`, other tags, other projects' repositories and locked
# tags are never touched, and --include-locked is never used. `acr purge` is a
# preview feature and deletes permanently.
#
# Auth is the live `az login` session. The task authenticates to the registry by
# itself.
#
# Usage: ./scripts/setup-acr-purge.sh [--apply]
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=lib/images.sh
source scripts/lib/images.sh

TASK="purge-blogstudio-images"
SCHEDULE="0 3 * * Sun"
AGO=30d
KEEP=10

APPLY=0
case "${1:-}" in
  "") ;;
  --apply) APPLY=1 ;;
  *) echo "usage: setup-acr-purge.sh [--apply]" >&2; exit 2 ;;
esac

# 1. The tags the apps run now: locked with --apply, listed otherwise.
for entry in "${IMAGES[@]}"; do
  IFS='|' read -r repo app _ _ <<<"$entry"
  current=$(az containerapp show -n "$app" -g "$RG" \
    --query "properties.template.containers[0].image" -o tsv)
  tag="${current##*:}"
  if ! is_sha "$tag"; then
    echo "not locking $repo: $app runs '$current', not a SHA tag"
  elif [ "$APPLY" -eq 1 ]; then
    lock_tag "$repo" "$tag"
    echo "locked $repo:$tag (running in $app)"
  else
    echo "would lock $repo:$tag (running in $app)"
  fi
done

# 2. The purge command, one filter per repository.
purge="acr purge"
for entry in "${IMAGES[@]}"; do
  IFS='|' read -r repo _ _ _ <<<"$entry"
  # The repository part is a regular expression: anchored, so it cannot also
  # match another project's repository that merely contains the name.
  purge+=" --filter '^$repo\$:^[0-9a-f]{40}\$'"
done
purge+=" --ago $AGO --keep $KEEP --untagged"

echo
echo "Dry run of the purge (nothing is deleted):"
az acr run --registry "$ACR" --cmd "$purge --dry-run" /dev/null

if [ "$APPLY" -eq 0 ]; then
  echo
  echo "Dry run: nothing was locked or created. If the list above only names old SHA tags of"
  echo "blogstudio-web, blogstudio-api and blogapi, re-run with --apply (the owner's yes)."
  exit 0
fi

# 3. Create the weekly task (replace it if it exists).
if az acr task show -n "$TASK" -r "$ACR" -o none 2>/dev/null; then
  az acr task delete -n "$TASK" -r "$ACR" --yes
fi
az acr task create -n "$TASK" -r "$ACR" --cmd "$purge" \
  --schedule "$SCHEDULE" --context /dev/null --output none
echo "Task $TASK created: $SCHEDULE UTC, tags older than $AGO, newest $KEEP kept."
