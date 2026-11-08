#!/usr/bin/env bash
# Provision (or update) cae-blogstudio, the three apps, their identities, the
# auth configs and the blog containers from infra/main.bicep. Idempotent.
# A LAPTOP step that changes production: run it only with the owner's explicit
# yes for that run.
#
# Needs the full SHA of a commit whose three images already exist
# (./scripts/build-push.sh <sha>). It never defaults the tag to local HEAD: a
# Bicep run from a checkout that is not at the deployed commit would otherwise
# roll the apps to that commit's images.
#
# Settings come from the git-ignored .env (names in .env.example), written by the
# Entra setup scripts. The Easy Auth client secret is read from
# BLOG_WEB_CLIENT_SECRET or prompted for; it is never stored in a file here.
#
# Usage: ./infra/deploy.sh <full-commit-sha>
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=../scripts/lib/images.sh
source scripts/lib/images.sh

SHA=${1:-}
if ! is_sha "$SHA"; then
  echo "ERROR: pass the full 40-character commit SHA whose images were built (scripts/build-push.sh <sha>)." >&2
  exit 2
fi

ENV_FILE=${BLOG_ENV_FILE:-.env}
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

missing=()
for name in BLOG_TENANT_ID BLOG_WEB_CLIENT_ID BLOG_STUDIO_API_CLIENT_ID BLOG_API_CLIENT_ID BLOG_APPROVED_CLIENT_IDS; do
  [ -n "${!name:-}" ] || missing+=("$name")
done
if [ "${#missing[@]}" -gt 0 ]; then
  echo "ERROR: missing settings: ${missing[*]} (see .env.example; the Entra setup scripts write them)." >&2
  exit 2
fi

# Comma list to a JSON array, dropping blanks. An empty list could let any caller
# with a valid token through, so it is refused.
approved=$(printf '%s' "$BLOG_APPROVED_CLIENT_IDS" | tr -d ' ' | jq -R -c 'split(",") | map(select(length > 0))')
if [ "$approved" = "[]" ]; then
  echo "ERROR: BLOG_APPROVED_CLIENT_IDS has no client ID; the read API needs at least one approved caller." >&2
  exit 2
fi

if [ -z "${BLOG_WEB_CLIENT_SECRET:-}" ]; then
  read -r -s -p "Easy Auth client secret for the studio web app: " BLOG_WEB_CLIENT_SECRET
  echo
fi
[ -n "$BLOG_WEB_CLIENT_SECRET" ] || { echo "ERROR: no secret entered" >&2; exit 2; }

for entry in "${IMAGES[@]}"; do
  IFS='|' read -r repo _ <<<"$entry"
  if ! image_exists "$repo" "$SHA"; then
    echo "ERROR: $repo:$SHA is not in the registry. Run ./scripts/build-push.sh $SHA first." >&2
    exit 1
  fi
done

# Parameters go through a mode-600 temporary file, so the Easy Auth client secret
# is never on a command line (visible to other processes) and the file is deleted
# when the script exits.
params=$(mktemp)
trap 'rm -f "$params"' EXIT
chmod 600 "$params"
jq -n \
  --arg imageTag "$SHA" --arg tenantId "$BLOG_TENANT_ID" \
  --arg webClientId "$BLOG_WEB_CLIENT_ID" --arg webClientSecret "$BLOG_WEB_CLIENT_SECRET" \
  --arg studioApiClientId "$BLOG_STUDIO_API_CLIENT_ID" --arg blogApiClientId "$BLOG_API_CLIENT_ID" \
  --argjson approvedClientIds "$approved" '{
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
    contentVersion: "1.0.0.0",
    parameters: {
      imageTag: {value: $imageTag}, tenantId: {value: $tenantId},
      webClientId: {value: $webClientId}, webClientSecret: {value: $webClientSecret},
      studioApiClientId: {value: $studioApiClientId}, blogApiClientId: {value: $blogApiClientId},
      approvedClientIds: {value: $approvedClientIds}
    }}' >"$params"

echo "Deploying image tag $SHA to resource group $RG..."
az deployment group create \
  --resource-group "$RG" \
  --template-file infra/main.bicep \
  --parameters "@$params" \
  --query "properties.provisioningState" -o tsv

echo "Web:      https://$(az containerapp show -n ca-blogstudio-web -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)"
echo "Read API: https://$(az containerapp show -n ca-blogapi -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)"
