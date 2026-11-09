#!/usr/bin/env bash
# The three-step live gate for the read API (run after every deploy that
# touches auth). It creates a one-day secret on each of the two gate caller
# apps, runs the steps, and removes both secrets on exit, also when a step
# fails or the script is interrupted.
#
#   1. an unauthenticated request gets 401
#   2. an authenticated but unapproved caller is rejected: Entra refuses it a
#      token (assignment required), or the API answers 401/403
#   3. the approved caller succeeds: a 2xx, or the app's own 404 body
#      {"detail":"Not Found"} (until BLOG-18 adds /v1/posts, then 200). An
#      ingress 404 for a stopped or missing app has another body and fails.
#
# Needs the IDs setup-api-auth.sh wrote to .env and a deployed read API. Default
# is a DRY RUN; --run writes temporary credentials to Entra and needs the
# owner's yes.
#
# Usage: ./scripts/live-gate.sh [--run]
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=lib/entra.sh
source scripts/lib/entra.sh

if [ "${1:-}" != "--run" ]; then
  echo "Dry run. With --run this adds a one-day secret to $GATE_CALLER_APP and $GATE_DENIED_APP, asks the read API for /v1/posts three ways (no token, denied caller, approved caller), and removes both secrets again."
  exit 0
fi

set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a
: "${BLOG_TENANT_ID:?missing in $ENV_FILE}" "${BLOG_API_CLIENT_ID:?missing in $ENV_FILE}"
: "${BLOG_GATE_CALLER_CLIENT_ID:?missing in $ENV_FILE}" "${BLOG_GATE_DENIED_CLIENT_ID:?missing in $ENV_FILE}"

RG=rg-chatbot
TRIES=${GATE_TOKEN_TRIES:-4}
SLEEP=${GATE_RETRY_SLEEP:-20}
FQDN=$(az containerapp show -n ca-blogapi -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)
URL="https://$FQDN/v1/posts"
END=$(date -u -v+1d +%Y-%m-%d 2>/dev/null || date -u -d '+1 day' +%Y-%m-%d)

tmp=$(mktemp -d)
chmod 700 "$tmp"
created=()
# shellcheck disable=SC2329  # runs from the EXIT trap below
cleanup() {
  local pair
  for pair in ${created[@]+"${created[@]}"}; do
    az ad app credential delete --id "${pair%%:*}" --key-id "${pair##*:}" ||
      echo "WARNING: remove credential ${pair##*:} from app ${pair%%:*} by hand." >&2
  done
  rm -rf "$tmp"
}
trap cleanup EXIT

# Add a one-day secret to an app; the secret is left in the global SECRET.
# Stale blog-gate credentials from an interrupted earlier run are deleted first,
# so exactly one exists afterwards and it is the one this run removes on exit.
SECRET=""
temp_secret() {
  local old keys
  for old in $(az ad app credential list --id "$1" --query "[?displayName=='blog-gate'].keyId" -o tsv); do
    az ad app credential delete --id "$1" --key-id "$old" --output none
  done
  SECRET=$(az ad app credential reset --id "$1" --append --display-name blog-gate \
    --end-date "$END" --query password -o tsv)
  keys=$(az ad app credential list --id "$1" --query "[?displayName=='blog-gate'].keyId" -o tsv)
  if [ "$(printf '%s\n' "$keys" | grep -c .)" -ne 1 ]; then
    echo "ERROR: expected exactly one blog-gate credential on $1, found: ${keys:-none}" >&2
    exit 1
  fi
  created+=("$1:$keys")
}

# Ask Entra for a token as client $1 (secret in $SECRET). Sets TOKEN, and
# REFUSED=1 when Entra refused because the caller has no role (AADSTS501051).
# A secret that has not propagated yet (AADSTS7000215) is retried.
TOKEN=""
REFUSED=0
fetch_token() {
  local form="$tmp/form" resp i
  TOKEN=""
  REFUSED=0
  for ((i = 1; i <= TRIES; i++)); do
    : >"$form"
    chmod 600 "$form"
    printf 'grant_type=client_credentials&client_id=%s&scope=%s&client_secret=%s' \
      "$1" \
      "$(S="api://$BLOG_API_CLIENT_ID/.default" jq -rn '$ENV.S | @uri')" \
      "$(S="$SECRET" jq -rn '$ENV.S | @uri')" >"$form"
    resp=$(curl -s -d "@$form" "https://login.microsoftonline.com/$BLOG_TENANT_ID/oauth2/v2.0/token")
    TOKEN=$(jq -r '.access_token // empty' <<<"$resp")
    [ -n "$TOKEN" ] && return 0
    if jq -e '(.error_description // "") | test("AADSTS501051")' <<<"$resp" >/dev/null; then
      REFUSED=1
      return 0
    fi
    if jq -e '(.error_description // "") | test("AADSTS7000215")' <<<"$resp" >/dev/null && [ "$i" -lt "$TRIES" ]; then
      sleep "$SLEEP"
      continue
    fi
    return 0
  done
}

# HTTP status of GET $URL, with the bearer token $1 when given. The response
# body is kept in $tmp/body.
http_code() {
  local args=(-s -o "$tmp/body" -w '%{http_code}')
  if [ -n "${1:-}" ]; then
    printf 'Authorization: Bearer %s\n' "$1" >"$tmp/header"
    chmod 600 "$tmp/header"
    args+=(-H "@$tmp/header")
  fi
  curl "${args[@]}" "$URL"
}

fail=0
pass() { echo "PASS  $1"; }
failed() { echo "FAIL  $1"; fail=1; }

echo "Read API: $URL"

code=$(http_code)
if [ "$code" = 401 ]; then pass "1 unauthenticated request gets 401"; else failed "1 unauthenticated request got HTTP $code, expected 401"; fi

temp_secret "$BLOG_GATE_DENIED_CLIENT_ID"
fetch_token "$BLOG_GATE_DENIED_CLIENT_ID"
if [ "$REFUSED" -eq 1 ]; then
  pass "2 unapproved caller was refused a token (assignment required)"
elif [ -z "$TOKEN" ]; then
  failed "2 unapproved caller got no token, but not because of the role requirement"
else
  code=$(http_code "$TOKEN")
  case "$code" in
    401 | 403) pass "2 unapproved caller was rejected (HTTP $code)" ;;
    *) failed "2 unapproved caller got HTTP $code, expected 401 or 403" ;;
  esac
fi

temp_secret "$BLOG_GATE_CALLER_CLIENT_ID"
fetch_token "$BLOG_GATE_CALLER_CLIENT_ID"
if [ -z "$TOKEN" ]; then
  failed "3 approved caller could not get a token"
else
  code=$(http_code "$TOKEN")
  body=$(jq -c . "$tmp/body" 2>/dev/null || true)
  case "$code" in
    2??) pass "3 approved caller reached the app (HTTP $code)" ;;
    404)
      # FastAPI's own 404 proves the request passed authentication and reached
      # the app. An ingress 404 (stopped or missing app) has another body.
      if [ "$body" = '{"detail":"Not Found"}' ]; then
        pass "3 approved caller reached the app (the app's own 404, no /v1/posts yet)"
      else
        failed "3 approved caller got a 404 that did not come from the app (is ca-blogapi running?)"
      fi ;;
    *) failed "3 approved caller was rejected or did not reach the app (HTTP $code)" ;;
  esac
fi

exit "$fail"
