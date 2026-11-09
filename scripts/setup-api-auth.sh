#!/usr/bin/env bash
# Create or reuse the Entra app registrations behind the token validation of
# the two APIs, and two credential-less "gate caller" apps for the live gate.
# Idempotent: every property is applied on every run, so a re-run (or a run
# against an app that predates a fix) always ends correct.
#
#   blogstudio-api  audience of the studio API (api://<appId>, token v2)
#   blogapi         audience of the read API (api://<appId>, token v2), app role
#                   Blog.Read, assignment required (no role, no token)
#   blogapi-gate-caller  approved (Blog.Read), no credentials at rest
#   blogapi-gate-denied  not approved, no credentials at rest
#
# Writes the IDs, the tenant and the owner's object ID to the git-ignored .env
# that infra/deploy.sh reads. Default is a DRY RUN (reads only); --apply writes
# to Entra and needs the owner's yes.
#
# Usage: ./scripts/setup-api-auth.sh [--apply]
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=lib/entra.sh
source scripts/lib/entra.sh

APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

if [ "$APPLY" -ne 1 ]; then
  echo "Dry run. With --apply this ensures these Entra app registrations and service principals:"
  for name in "$STUDIO_API_APP" "$BLOG_API_APP" "$GATE_CALLER_APP" "$GATE_DENIED_APP"; do
    if [ -n "$(app_id "$name")" ]; then state=exists; else state=missing; fi
    echo "  - $name ($state)"
  done
  echo "and applies: identifier URI api://<appId> and token version 2 on both APIs; role $READ_ROLE_VALUE and assignment-required on $BLOG_API_APP; $READ_ROLE_VALUE for $GATE_CALLER_APP; then writes the IDs to $ENV_FILE."
  exit 0
fi

TENANT_ID=$(az account show --query tenantId -o tsv)
OWNER_OID=$(az ad signed-in-user show --query id -o tsv)

# Identifier URI and token version, applied on every run.
configure_api() {
  local id obj
  id=$(ensure_app "$1")
  ensure_sp "$id" >/dev/null
  az ad app update --id "$id" --identifier-uris "api://$id" --output none
  obj=$(app_object_id "$id")
  graph_patch "applications/$obj" '{"api": {"requestedAccessTokenVersion": 2}}'
  echo "$id"
}

STUDIO_API_ID=$(configure_api "$STUDIO_API_APP")
BLOG_API_ID=$(configure_api "$BLOG_API_APP")

roles=$(jq -c -n --arg id "$READ_ROLE_ID" --arg value "$READ_ROLE_VALUE" '[{
  allowedMemberTypes: ["Application"],
  description: "Callers that may read published blog posts.",
  displayName: $value, id: $id, isEnabled: true, value: $value}]')
az ad app update --id "$BLOG_API_ID" --app-roles "$roles" --output none
BLOG_API_SP=$(ensure_sp "$BLOG_API_ID")
graph_patch "servicePrincipals/$BLOG_API_SP" '{"appRoleAssignmentRequired": true}'

CALLER_ID=$(ensure_app "$GATE_CALLER_APP")
CALLER_SP=$(ensure_sp "$CALLER_ID")
DENIED_ID=$(ensure_app "$GATE_DENIED_APP")
ensure_sp "$DENIED_ID" >/dev/null
approve_client "$CALLER_SP"

set_env BLOG_TENANT_ID "$TENANT_ID"
set_env BLOG_OWNER_OBJECT_ID "$OWNER_OID"
set_env BLOG_STUDIO_API_CLIENT_ID "$STUDIO_API_ID"
set_env BLOG_API_CLIENT_ID "$BLOG_API_ID"
set_env BLOG_GATE_CALLER_CLIENT_ID "$CALLER_ID"
set_env BLOG_GATE_DENIED_CLIENT_ID "$DENIED_ID"
add_approved_client "$CALLER_ID"

echo "Done. IDs written to $ENV_FILE. Add the real callers' client IDs with scripts/approve-client.sh."
