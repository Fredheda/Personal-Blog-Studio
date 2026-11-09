#!/usr/bin/env bash
# Approve one more caller of the read API by its client ID (for a managed
# identity: `az identity show -n <name> -g <rg> --query clientId -o tsv`).
# Assigns the Blog.Read role to the caller's service principal and adds the
# client ID to BLOG_APPROVED_CLIENT_IDS in .env; ./infra/deploy.sh <sha> then
# puts it on the read API's allow list. Idempotent. Default is a DRY RUN;
# --apply writes to Entra and needs the owner's yes.
#
# Usage: ./scripts/approve-client.sh <client-id> [--apply]
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=lib/entra.sh
source scripts/lib/entra.sh

CLIENT_ID=${1:-}
if ! [[ "$CLIENT_ID" =~ ^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$ ]]; then
  echo "usage: approve-client.sh <client-id> [--apply]   (the client ID is a GUID)" >&2
  exit 2
fi
APPLY=0
[ "${2:-}" = "--apply" ] && APPLY=1

if [ "$APPLY" -ne 1 ]; then
  echo "Dry run. With --apply this assigns the $READ_ROLE_VALUE role to the service principal of $CLIENT_ID and adds it to BLOG_APPROVED_CLIENT_IDS in $ENV_FILE."
  exit 0
fi

SP=$(az ad sp show --id "$CLIENT_ID" --query id -o tsv)
if [ -z "$SP" ]; then
  echo "ERROR: no service principal for $CLIENT_ID." >&2
  exit 1
fi
approve_client "$SP"
add_approved_client "$CLIENT_ID"
echo "Run ./infra/deploy.sh <sha> to put $CLIENT_ID on the read API's allow list."
