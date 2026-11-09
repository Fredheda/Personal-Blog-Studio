# shellcheck shell=bash
# shellcheck disable=SC2034  # constants are used by the scripts that source this file
# Building blocks for the Entra setup scripts. Sourced, not executed. Every
# helper is idempotent: calling it twice leaves Entra as one call would.

GRAPH=https://graph.microsoft.com/v1.0
READ_ROLE_VALUE=Blog.Read
# Fixed, so a re-run writes the same role definition (Entra matches roles by id).
READ_ROLE_ID=5d8f2b6e-3a41-4c7e-9f0b-8a1e6c2d4b73
STUDIO_API_APP=blogstudio-api
BLOG_API_APP=blogapi
EASYAUTH_APP=blogstudio-easyauth
GATE_CALLER_APP=blogapi-gate-caller
GATE_DENIED_APP=blogapi-gate-denied
ENV_FILE=${BLOG_ENV_FILE:-.env}

# Set KEY=VALUE in the env file (created with mode 600), replacing an existing KEY.
set_env() {
  local key=$1 value=$2 tmp
  touch "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  tmp=$(mktemp)
  grep -v "^${key}=" "$ENV_FILE" >"$tmp" || true
  printf '%s=%s\n' "$key" "$value" >>"$tmp"
  cat "$tmp" >"$ENV_FILE"
  rm -f "$tmp"
}

# Value of KEY in the env file; empty if the file or the key is missing.
get_env() {
  { grep -E "^$1=" "$ENV_FILE" 2>/dev/null || true; } | tail -1 | cut -d= -f2-
}

# Client ID of the app registration with this exact display name; empty if there
# is none. Fails if the name is ambiguous, so a script never writes to the wrong
# app. The lookup is an exact OData filter: `--display-name` matches every name
# that merely STARTS with the value (blogapi would match blogapi-gate-caller).
app_id() {
  local count filter="displayName eq '$1'"
  count=$(az ad app list --filter "$filter" --query "length(@)" -o tsv)
  if [ "$count" -gt 1 ]; then
    echo "ERROR: $count app registrations are named '$1'; delete the extras first." >&2
    return 1
  fi
  az ad app list --filter "$filter" --query "[0].appId" -o tsv
}

# Create the app registration if it does not exist; print its client ID.
ensure_app() {
  local id
  id=$(app_id "$1") || return 1
  if [ -z "$id" ]; then
    id=$(az ad app create --display-name "$1" --sign-in-audience AzureADMyOrg --query appId -o tsv)
  fi
  echo "$id"
}

# Object ID of the service principal of an app; created if missing.
ensure_sp() {
  local sp
  sp=$(az ad sp show --id "$1" --query id -o tsv 2>/dev/null) || sp=""
  if [ -z "$sp" ]; then
    sp=$(az ad sp create --id "$1" --query id -o tsv)
  fi
  echo "$sp"
}

# Object ID of the app registration (Graph addresses applications by it).
app_object_id() {
  az ad app show --id "$1" --query id -o tsv
}

# PATCH a Graph resource, e.g. graph_patch "servicePrincipals/<id>" '{"a": 1}'.
graph_patch() {
  az rest --method PATCH --uri "$GRAPH/$1" --body "$2" --output none
}

# Give a service principal (object ID) the Blog.Read role on the read API.
approve_client() {
  local caller_sp=$1 api_app api_sp existing
  api_app=$(app_id "$BLOG_API_APP")
  if [ -z "$api_app" ]; then
    echo "ERROR: run scripts/setup-api-auth.sh first." >&2
    return 1
  fi
  api_sp=$(ensure_sp "$api_app")
  existing=$(az rest --method GET --uri "$GRAPH/servicePrincipals/$api_sp/appRoleAssignedTo" \
    --query "value[?principalId=='$caller_sp' && appRoleId=='$READ_ROLE_ID'] | length(@)" -o tsv)
  if [ "$existing" -gt 0 ]; then
    echo "Already approved: $caller_sp"
    return 0
  fi
  az rest --method POST --uri "$GRAPH/servicePrincipals/$api_sp/appRoleAssignedTo" \
    --body "{\"principalId\": \"$caller_sp\", \"resourceId\": \"$api_sp\", \"appRoleId\": \"$READ_ROLE_ID\"}" \
    --output none
  echo "Approved: $caller_sp"
}

# Add a client ID to BLOG_APPROVED_CLIENT_IDS in the env file (once).
add_approved_client() {
  local current
  current=$(get_env BLOG_APPROVED_CLIENT_IDS)
  case ",$current," in
    *",$1,"*) return 0 ;;
  esac
  set_env BLOG_APPROVED_CLIENT_IDS "${current:+$current,}$1"
}
