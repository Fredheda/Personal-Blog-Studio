#!/usr/bin/env bash
# Create or reuse the Entra app registration behind Easy Auth on the studio web
# app (blogstudio-easyauth): redirect URIs, assignment required, the owner
# assigned, and one client secret. Idempotent; every property is applied on
# every run. The owner-only rule has two layers: this assignment, and the owner
# object ID the Bicep admits (infra/main.bicep).
#
# The client secret is written to the git-ignored .env as BLOG_WEB_CLIENT_SECRET
# (mode 600), never printed. It lasts 2 YEARS: record the date in EXPIRATIONS.md
# and rotate with --rotate (the old secret keeps working until it expires, so a
# running deployment is not interrupted; redeploy to apply the new one).
#
# Run it before the first deploy (custom domain redirect only) and again after
# it (adds the default hostname redirect). Default is a DRY RUN; --apply writes
# to Entra and needs the owner's yes.
#
# Usage: ./scripts/setup-easyauth.sh [--apply] [--rotate]
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=lib/entra.sh
source scripts/lib/entra.sh

RG=rg-chatbot
WEB_APP=ca-blogstudio-web
CUSTOM_DOMAIN=${BLOG_STUDIO_DOMAIN:-blog-studio.frederikheda.com}
OWNER_ROLE=00000000-0000-0000-0000-000000000000

APPLY=0
ROTATE=0
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --rotate) ROTATE=1 ;;
    *) echo "usage: setup-easyauth.sh [--apply] [--rotate]" >&2; exit 2 ;;
  esac
done

if [ "$APPLY" -ne 1 ]; then
  if [ -n "$(app_id "$EASYAUTH_APP")" ]; then state=exists; else state=missing; fi
  echo "Dry run. With --apply this ensures the Entra app $EASYAUTH_APP ($state): redirect URIs for $CUSTOM_DOMAIN and the web app's default hostname, assignment required, the signed-in owner assigned, and a 2-year client secret written to $ENV_FILE (only if none is there, or with --rotate)."
  exit 0
fi

OWNER_OID=$(az ad signed-in-user show --query id -o tsv)
APP_ID=$(ensure_app "$EASYAUTH_APP")
SP_ID=$(ensure_sp "$APP_ID")

redirects=("https://$CUSTOM_DOMAIN/.auth/login/aad/callback")
if fqdn=$(az containerapp show -n "$WEB_APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv 2>/dev/null) && [ -n "$fqdn" ]; then
  redirects+=("https://$fqdn/.auth/login/aad/callback")
else
  echo "The web app is not deployed yet: only the $CUSTOM_DOMAIN redirect is registered. Re-run after the first deploy."
fi
az ad app update --id "$APP_ID" --web-redirect-uris "${redirects[@]}" --enable-id-token-issuance true --output none
echo "Redirect URIs set: ${redirects[*]}"

graph_patch "servicePrincipals/$SP_ID" '{"appRoleAssignmentRequired": true}'

assigned=$(az rest --method GET --uri "$GRAPH/servicePrincipals/$SP_ID/appRoleAssignedTo" \
  --query "value[?principalId=='$OWNER_OID'] | length(@)" -o tsv)
if [ "$assigned" -eq 0 ]; then
  az rest --method POST --uri "$GRAPH/servicePrincipals/$SP_ID/appRoleAssignedTo" \
    --body "{\"principalId\": \"$OWNER_OID\", \"resourceId\": \"$SP_ID\", \"appRoleId\": \"$OWNER_ROLE\"}" \
    --output none
  echo "Owner assigned to $EASYAUTH_APP."
else
  echo "Owner already assigned to $EASYAUTH_APP."
fi

set_env BLOG_WEB_CLIENT_ID "$APP_ID"
if [ "$ROTATE" -eq 1 ] || [ -z "$(get_env BLOG_WEB_CLIENT_SECRET)" ]; then
  secret=$(az ad app credential reset --id "$APP_ID" --append --display-name blogstudio-easyauth \
    --years 2 --query password -o tsv)
  set_env BLOG_WEB_CLIENT_SECRET "$secret"
  echo "New client secret written to $ENV_FILE (mode 600). It expires in 2 years: record the date in EXPIRATIONS.md, then run ./infra/deploy.sh to apply it."
else
  echo "Client secret already in $ENV_FILE; use --rotate to replace it."
fi
