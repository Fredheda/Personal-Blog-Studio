#!/usr/bin/env bash
# One-time (idempotent) setup so GitHub Actions can build and deploy the blog
# with no stored secrets, using OpenID Connect (workload identity federation).
# Default is a DRY RUN that reads and prints the plan; --apply writes to Azure
# and GitHub and needs the owner's yes.
#
# What --apply does:
#   1. Two user-assigned managed identities in rg-chatbot:
#        id-blogstudio-gh-build   pushes images (the build step of Deploy)
#        id-blogstudio-gh-deploy  rolls the three container apps (the deploy step)
#   2. Only the roles each needs:
#        build:  AcrPush + Container Registry Tasks Contributor on the registry
#                (it cannot change a container app)
#        deploy: AcrPush on the registry (to lock and unlock tags; the registry
#                is in legacy permission mode, which cannot scope a push by
#                repository, so this also lets it push images), Container Apps
#                Contributor on each of the three apps, and Managed Identity
#                Operator on each identity attached to them (updating an app
#                that uses a user-assigned identity needs assign/action on it)
#   3. One federated credential on each identity, trusting only jobs that run in
#      the `production` environment of this repo (Deploy logs in twice, as build
#      and then as deploy).
#   4. The `production` GitHub environment: only the main branch may deploy, the
#      owner is the required reviewer, admins cannot bypass. (The deploy identity
#      trusts any job in that environment on any branch, and the main-only check
#      inside deploy.yml is in a file any branch author can edit, so the
#      environment itself admits only main: GitHub enforces it outside the file.)
#   5. The Azure IDs the workflow reads, as repo SECRETS (identifiers, not
#      credentials; a secret so GitHub masks them in run logs), sent on stdin.
#
# Auth is the live `az login` and `gh auth` sessions; nothing secret is written.
# Federated credentials do not expire.
#
# Usage: ./scripts/setup-github-deploy.sh [--apply]
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=lib/images.sh
source scripts/lib/images.sh

GH_REPO=Fredheda/Personal-Blog-Studio
OWNER=${GH_REPO%%/*}
LOCATION=westeurope
BUILD_ID="id-blogstudio-gh-build"
DEPLOY_ID="id-blogstudio-gh-deploy"
ATTACHED_IDS=(id-blogstudio-acrpull id-blogstudio-web id-blogstudio-api id-blogapi)
ISSUER=https://token.actions.githubusercontent.com
SUBJECT="repo:$GH_REPO:environment:production"

APPLY=0
case "${1:-}" in
  "") ;;
  --apply) APPLY=1 ;;
  *) echo "usage: setup-github-deploy.sh [--apply]" >&2; exit 2 ;;
esac

TENANT_ID=$(az account show --query tenantId -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "Subscription $SUBSCRIPTION_ID, repo $GH_REPO. Mode: $([ "$APPLY" -eq 1 ] && echo APPLY || echo dry run)"

apps=()
for entry in "${IMAGES[@]}"; do
  IFS='|' read -r _ app _ _ <<<"$entry"
  apps+=("$app")
done

if [ "$APPLY" -ne 1 ]; then
  for id in "$BUILD_ID" "$DEPLOY_ID"; do
    if az identity show -g "$RG" -n "$id" -o none 2>/dev/null; then state=exists; else state=missing; fi
    echo "  identity $id: $state"
  done
  echo "  build roles:  AcrPush, Container Registry Tasks Contributor on $ACR"
  echo "  deploy roles: AcrPush on $ACR; Container Apps Contributor on ${apps[*]}; Managed Identity Operator on ${ATTACHED_IDS[*]}"
  echo "  federated credential github-production on both identities, subject $SUBJECT"
  echo "  GitHub environment production: main branch only, required reviewer $OWNER, admins cannot bypass"
  echo "  repo secrets: AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID, AZURE_BUILD_CLIENT_ID, AZURE_DEPLOY_CLIENT_ID"
  echo "Dry run: nothing was changed. Re-run with --apply (the owner's yes) to do the above."
  exit 0
fi

ensure_identity() {
  local name=$1
  if az identity show -g "$RG" -n "$name" -o none 2>/dev/null; then
    echo "identity $name: exists"
  else
    az identity create -g "$RG" -n "$name" -l "$LOCATION" -o none
    echo "identity $name: created"
  fi
}

# Role assignment by object id + principal type, so a just-created identity does
# not have to wait for Entra replication before the lookup succeeds. Re-running
# returns the existing assignment.
ensure_role() {
  local principal=$1 role=$2 scope=$3
  az role assignment create --assignee-object-id "$principal" \
    --assignee-principal-type ServicePrincipal \
    --role "$role" --scope "$scope" -o none
  echo "role '$role' on ${scope##*/}: ensured"
}

ensure_federated_credential() {
  local identity=$1 name=$2 subject=$3
  if az identity federated-credential show -g "$RG" --identity-name "$identity" \
    --name "$name" -o none 2>/dev/null; then
    echo "federated credential $identity/$name: exists"
  else
    az identity federated-credential create -g "$RG" --identity-name "$identity" \
      --name "$name" --issuer "$ISSUER" --subject "$subject" \
      --audiences api://AzureADTokenExchange -o none
    echo "federated credential $identity/$name: created ($subject)"
  fi
}

set_secret() { printf '%s' "$2" | gh secret set "$1" -R "$GH_REPO"; }

ensure_identity "$BUILD_ID"
ensure_identity "$DEPLOY_ID"
BUILD_PRINCIPAL=$(az identity show -g "$RG" -n "$BUILD_ID" --query principalId -o tsv)
BUILD_CLIENT=$(az identity show -g "$RG" -n "$BUILD_ID" --query clientId -o tsv)
DEPLOY_PRINCIPAL=$(az identity show -g "$RG" -n "$DEPLOY_ID" --query principalId -o tsv)
DEPLOY_CLIENT=$(az identity show -g "$RG" -n "$DEPLOY_ID" --query clientId -o tsv)
ACR_ID=$(az acr show -n "$ACR" --query id -o tsv)

ensure_role "$BUILD_PRINCIPAL" "AcrPush" "$ACR_ID"
ensure_role "$BUILD_PRINCIPAL" "Container Registry Tasks Contributor" "$ACR_ID"

ensure_role "$DEPLOY_PRINCIPAL" "AcrPush" "$ACR_ID"
for name in "${ATTACHED_IDS[@]}"; do
  identity_resource=$(az identity show -g "$RG" -n "$name" --query id -o tsv)
  ensure_role "$DEPLOY_PRINCIPAL" "Managed Identity Operator" "$identity_resource"
done
for app in "${apps[@]}"; do
  app_resource=$(az containerapp show -n "$app" -g "$RG" --query id -o tsv)
  ensure_role "$DEPLOY_PRINCIPAL" "Container Apps Contributor" "$app_resource"
done

ensure_federated_credential "$BUILD_ID" github-production "$SUBJECT"
ensure_federated_credential "$DEPLOY_ID" github-production "$SUBJECT"

owner_id=$(gh api "users/$OWNER" --jq .id)
jq -n --argjson id "$owner_id" '{
  deployment_branch_policy: {protected_branches: false, custom_branch_policies: true},
  reviewers: [{type: "User", id: $id}],
  prevent_self_review: false,
  can_admins_bypass: false}' |
  gh api -X PUT "repos/$GH_REPO/environments/production" --input - \
    --jq '"environment " + .name + ": ensured"'

policies=$(gh api "repos/$GH_REPO/environments/production/deployment-branch-policies" \
  --jq '.branch_policies[].name')
if grep -qx main <<<"$policies"; then
  echo "environment production: branch policy main exists"
else
  gh api -X POST "repos/$GH_REPO/environments/production/deployment-branch-policies" \
    -f name=main -f type=branch --silent
  echo "environment production: branch policy main created"
fi
while IFS= read -r other; do
  if [ -n "$other" ] && [ "$other" != main ]; then
    echo "WARNING: environment production also admits branch '$other'; remove it in Settings, Environments unless intended." >&2
  fi
done <<<"$policies"

set_secret AZURE_TENANT_ID "$TENANT_ID"
set_secret AZURE_SUBSCRIPTION_ID "$SUBSCRIPTION_ID"
set_secret AZURE_BUILD_CLIENT_ID "$BUILD_CLIENT"
set_secret AZURE_DEPLOY_CLIENT_ID "$DEPLOY_CLIENT"
echo "repo secrets: set"
echo "Done. Re-running changes nothing."
