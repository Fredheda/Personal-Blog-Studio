#!/usr/bin/env bash
# One-time, idempotent setup of the blog's DEV containers on the SHARED storage
# account, for complete local runs. Default is a DRY RUN that prints each
# change; --apply performs them (needs the owner's yes).
#
#   1. create blog-drafts-dev and blog-published-dev, public access off
#   2. give the signed-in user Storage Blob Data Contributor on those two
#      containers only (never the account)
#
# Required condition, checked before any change and again after: the signed-in
# user holds no Storage Blob Data role anywhere except on the two dev
# containers. It is what keeps a wrongly configured local run away from the
# production containers. The check goes by role name.
#
# The output contains the subscription id and the user's object id: do not
# paste it into chat or tickets.
#
# Usage: ./scripts/setup-dev-storage.sh [--apply]
set -euo pipefail

ACCOUNT=${BLOG_STORAGE_ACCOUNT:-fhstorageportfolio}
SA_RG=${BLOG_STORAGE_RG:-FrederikHedaPlayground}
DRAFTS=${BLOG_DEV_DRAFTS_CONTAINER:-blog-drafts-dev}
PUBLISHED=${BLOG_DEV_PUBLISHED_CONTAINER:-blog-published-dev}
ROLE="Storage Blob Data Contributor"

for name in "$DRAFTS" "$PUBLISHED"; do
  case "$name" in
    *-dev) ;;
    *) echo "ERROR: $name does not end in -dev; refusing." >&2; exit 1 ;;
  esac
done
if [ "$DRAFTS" = "$PUBLISHED" ]; then
  echo "ERROR: the two container names must differ." >&2
  exit 1
fi

APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

# Print a change; run it only with --apply.
run() {
  echo "+ $*"
  if [ "$APPLY" -eq 1 ]; then
    "$@"
  fi
}

OID=$(az ad signed-in-user show --query id -o tsv)
SUB=$(az account show --query id -o tsv)
BASE="/subscriptions/$SUB/resourceGroups/$SA_RG/providers/Microsoft.Storage/storageAccounts/$ACCOUNT/blobServices/default/containers"

echo "Storage account: $ACCOUNT ($SA_RG). Mode: $([ "$APPLY" -eq 1 ] && echo APPLY || echo dry run)"

# Every role assignment of the signed-in user, inherited and through groups.
roles() {
  az role assignment list --assignee "$OID" --all --include-inherited --include-groups -o json
}

# Blob data roles held anywhere except on the two dev containers. Scopes are
# compared without regard to case: Azure returns the same scope as
# /resourcegroups/... in one listing entry and /resourceGroups/... in another.
check_clean() {
  local bad
  bad=$(roles | jq -c --arg a "$BASE/$DRAFTS" --arg b "$BASE/$PUBLISHED" '
    [.[] | select((.roleDefinitionName // "") | startswith("Storage Blob Data"))
         | select((.scope | ascii_downcase) != ($a | ascii_downcase)
                  and (.scope | ascii_downcase) != ($b | ascii_downcase))]')
  if [ "$bad" != "[]" ]; then
    echo "ERROR: the signed-in user holds a blob data role outside the dev containers: $bad" >&2
    echo "A local run could then reach the production containers; stopping." >&2
    exit 1
  fi
  echo "Roles: no blob data role outside the dev containers."
}

has_role() {
  roles | jq -e --arg role "$ROLE" --arg scope "$1" \
    'any(.[]; .roleDefinitionName == $role and (.scope | ascii_downcase) == ($scope | ascii_downcase))' >/dev/null
}

check_clean

for name in "$DRAFTS" "$PUBLISHED"; do
  run az storage container-rm create --storage-account "$ACCOUNT" -g "$SA_RG" \
    -n "$name" --public-access off --output none
  if has_role "$BASE/$name"; then
    echo "Role: $ROLE already on $name."
  else
    run az role assignment create --assignee-object-id "$OID" \
      --assignee-principal-type User --role "$ROLE" --scope "$BASE/$name" --output none
  fi
done

if [ "$APPLY" -eq 1 ]; then
  for name in "$DRAFTS" "$PUBLISHED"; do
    access=$(az storage container-rm show --storage-account "$ACCOUNT" -g "$SA_RG" \
      -n "$name" --query publicAccess -o tsv)
    echo "Container $name: public access $access."
    if [ "$access" != "None" ]; then
      echo "ERROR: $name has public access $access; stopping." >&2
      exit 1
    fi
    if ! has_role "$BASE/$name"; then
      echo "ERROR: the role on $name is missing after the update; stopping." >&2
      exit 1
    fi
  done
  check_clean
fi
