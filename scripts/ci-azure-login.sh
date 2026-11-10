#!/usr/bin/env bash
# Log the Azure CLI in from a GitHub Actions job with OpenID Connect: no stored
# secret. Asks the runner for a short-lived GitHub OIDC token and exchanges it
# for an Azure session as the given managed identity, whose federated
# credential must trust this repo's `production` environment (see
# setup-github-deploy.sh).
#
# This is the exchange the azure/login action performs; it is done here with the
# Azure CLI so the pipeline needs no third-party action (the repo allows only
# GitHub-owned actions and a short list).
#
# `az login --federated-token` takes the token as an argument. It is valid for
# minutes, the runner is ephemeral and the value is masked in the run log first.
#
# Usage: ./scripts/ci-azure-login.sh <managed-identity-client-id>
# Needs: AZURE_TENANT_ID and AZURE_SUBSCRIPTION_ID in the environment, and the
# job to have `permissions: id-token: write` (that sets
# ACTIONS_ID_TOKEN_REQUEST_URL and ACTIONS_ID_TOKEN_REQUEST_TOKEN).
set -euo pipefail

client_id="${1:?usage: ci-azure-login.sh <client-id>}"
: "${AZURE_TENANT_ID:?AZURE_TENANT_ID is not set}"
: "${AZURE_SUBSCRIPTION_ID:?AZURE_SUBSCRIPTION_ID is not set}"

if [ -z "${ACTIONS_ID_TOKEN_REQUEST_URL:-}" ] || [ -z "${ACTIONS_ID_TOKEN_REQUEST_TOKEN:-}" ]; then
  echo "ERROR: no GitHub OIDC token endpoint; the job needs 'permissions: id-token: write'." >&2
  exit 1
fi

token=$(curl -sSfG -H "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
  --data-urlencode "audience=api://AzureADTokenExchange" \
  "$ACTIONS_ID_TOKEN_REQUEST_URL" | jq -r .value)
if [ -z "$token" ] || [ "$token" = "null" ]; then
  echo "ERROR: GitHub returned no OIDC token." >&2
  exit 1
fi
echo "::add-mask::$token"

az login --service-principal -u "$client_id" -t "$AZURE_TENANT_ID" \
  --federated-token "$token" --allow-no-subscriptions --output none
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
echo "Logged in to Azure as managed identity $client_id"
