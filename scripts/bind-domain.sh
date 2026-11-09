#!/usr/bin/env bash
# Custom domain of the studio web app, in two owner-gated phases. Dry run unless
# --apply.
#
#   dns   The two DNS records at GoDaddy, added with `gddy dns add` (append only,
#         never set or delete): CNAME <label> to the app's own generated hostname
#         (never a proxy: an intermediate CNAME blocks certificate issuance and
#         renewal) and TXT asuid.<label> to the app's verification id. A
#         `--dry-run` of each missing record is always shown first; with --apply
#         the zone is read back and a missing record is an error.
#   bind  Needs both records to resolve. Adds the hostname to the app, binds it
#         with a free Azure-managed certificate (CNAME validation), waits for the
#         certificate, checks the binding is SNI, then writes
#         BLOG_WEB_CUSTOM_DOMAIN and BLOG_WEB_CERTIFICATE_NAME to .env.
#
# Then run ./infra/deploy.sh <sha>: the Bicep declares the domain, so every later
# deploy keeps it (deploy.sh refuses a deploy that would unbind it).
#
# Usage: ./scripts/bind-domain.sh dns|bind [--apply]
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=lib/entra.sh
source scripts/lib/entra.sh

RG=rg-chatbot
WEB_APP=ca-blogstudio-web
ENVIRONMENT=cae-blogstudio
HOST=${BLOG_STUDIO_DOMAIN:-blog-studio.frederikheda.com}
LABEL=${HOST%%.*}
ZONE=${HOST#*.}
TTL=3600
TRIES=${CERT_TRIES:-30}
SLEEP=${CERT_SLEEP:-20}

usage() {
  echo "usage: bind-domain.sh dns|bind [--apply]" >&2
  exit 2
}
PHASE=${1:-}
APPLY=0
case "$PHASE" in dns | bind) ;; *) usage ;; esac
case "${2:-}" in "") ;; --apply) APPLY=1 ;; *) usage ;; esac
[ "$#" -le 2 ] || usage
if ! [[ "$LABEL" =~ ^[a-z0-9-]+$ ]] || ! [[ "$ZONE" =~ ^[a-z0-9-]+\.[a-z0-9-]+$ ]]; then
  echo "ERROR: BLOG_STUDIO_DOMAIN must be <label>.<domain>, e.g. blog-studio.example.com (got '$HOST')." >&2
  exit 2
fi

FQDN=$(az containerapp show -n "$WEB_APP" -g "$RG" \
  --query properties.configuration.ingress.fqdn -o tsv 2>/dev/null || true)
VERIFY_ID=$(az containerapp show -n "$WEB_APP" -g "$RG" \
  --query properties.customDomainVerificationId -o tsv 2>/dev/null || true)
if [ -z "$FQDN" ] || [ -z "$VERIFY_ID" ]; then
  echo "ERROR: $WEB_APP is not deployed in $RG (no hostname or verification id yet)." >&2
  exit 1
fi

# Lower case, no quotes, no trailing dot: tools print the same name differently.
norm() { printf '%s' "$1" | tr -d '"' | tr '[:upper:]' '[:lower:]' | sed 's/\.$//'; }

# Print a change; run it only with --apply.
run() {
  echo "+ $*"
  if [ "$APPLY" -eq 1 ]; then
    "$@"
  fi
}

# --- dns ---------------------------------------------------------------------

# Values of the records gddy lists for one type and name, one per line. The
# envelope is {"data": [...]}; a bare array is accepted too.
records_of() {
  gddy dns list "$ZONE" --type "$1" --name "$2" -o json |
    jq -r '(.data // .) | if type == "array" then .[].data else empty end'
}

# 0 when the record (type, name, value) is listed.
has_value() {
  local v want
  want=$(norm "$3")
  while IFS= read -r v; do
    [ -n "$v" ] && [ "$(norm "$v")" = "$want" ] && return 0
  done < <(records_of "$1" "$2")
  return 1
}

add_record() {
  local type=$1 name=$2 value=$3
  echo "+ gddy dns add $ZONE --type $type --name $name --data $value --ttl $TTL"
  gddy dns add "$ZONE" --type "$type" --name "$name" --data "$value" --ttl "$TTL" --dry-run
  if [ "$APPLY" -eq 1 ]; then
    gddy dns add "$ZONE" --type "$type" --name "$name" --data "$value" --ttl "$TTL"
  fi
}

phase_dns() {
  local todo=0 current
  command -v gddy >/dev/null || { echo "ERROR: gddy is not installed." >&2; exit 1; }
  echo "Zone $ZONE. Records for $HOST:"
  current=$(records_of CNAME "$LABEL")
  if has_value CNAME "$LABEL" "$FQDN"; then
    echo "  present  CNAME $LABEL -> $FQDN"
  elif [ -n "$current" ]; then
    echo "ERROR: CNAME $LABEL already points to $current, not $FQDN. Nothing is overwritten; resolve it by hand." >&2
    exit 1
  else
    add_record CNAME "$LABEL" "$FQDN"
    todo=1
  fi
  if has_value TXT "asuid.$LABEL" "$VERIFY_ID"; then
    echo "  present  TXT asuid.$LABEL"
  else
    add_record TXT "asuid.$LABEL" "$VERIFY_ID"
    todo=1
  fi
  if [ "$todo" -eq 0 ]; then
    echo "Both records are in place."
  elif [ "$APPLY" -ne 1 ]; then
    echo "Dry run: nothing was added. Re-run with --apply (the owner's yes) to add the records above."
  else
    if ! has_value CNAME "$LABEL" "$FQDN" || ! has_value TXT "asuid.$LABEL" "$VERIFY_ID"; then
      echo "ERROR: a record is not listed after the add; check the zone at GoDaddy." >&2
      exit 1
    fi
    echo "Records added (TTL ${TTL}s). When 'dig +short CNAME $HOST' shows $FQDN, run: ./scripts/bind-domain.sh bind"
  fi
}

# --- bind --------------------------------------------------------------------

dig_values() { dig +short "$1" "$2" | tr -d '"' | sed 's/\.$//'; }

phase_bind() {
  local cname txts ready=1 listed bound certs state name="" binding i
  cname=$(dig_values CNAME "$HOST" | head -1)
  if [ "$(norm "$cname")" != "$(norm "$FQDN")" ]; then
    echo "DNS not ready: CNAME $HOST is '${cname:-none}', expected $FQDN. Run bind-domain.sh dns, then wait for DNS." >&2
    ready=0
  fi
  txts=$(dig_values TXT "asuid.$HOST" | tr '[:upper:]' '[:lower:]')
  if ! grep -qxF -- "$(norm "$VERIFY_ID")" <<<"$txts"; then
    echo "DNS not ready: TXT asuid.$HOST is '${txts:-none}', expected $VERIFY_ID." >&2
    ready=0
  fi
  [ "$ready" -eq 1 ] || exit 1

  # A host that was added but never bound (an earlier run stopped between the two
  # calls) is listed without an SNI binding: finish the bind, do not skip it.
  listed=$(az containerapp show -n "$WEB_APP" -g "$RG" \
    --query "properties.configuration.ingress.customDomains[].name" -o tsv)
  bound=$(az containerapp show -n "$WEB_APP" -g "$RG" \
    --query "properties.configuration.ingress.customDomains[?bindingType=='SniEnabled'].name" -o tsv)
  if grep -qxF -- "$HOST" <<<"$bound"; then
    echo "$HOST is already bound to $WEB_APP."
  else
    if grep -qxF -- "$HOST" <<<"$listed"; then
      echo "$HOST was added to $WEB_APP but not bound yet; finishing the bind."
    else
      run az containerapp hostname add --hostname "$HOST" -g "$RG" -n "$WEB_APP" -o none
    fi
    run az containerapp hostname bind --hostname "$HOST" -g "$RG" -n "$WEB_APP" \
      --environment "$ENVIRONMENT" --validation-method CNAME -o none
  fi
  if [ "$APPLY" -ne 1 ]; then
    echo "Dry run: nothing was changed. With --apply it then waits (up to $TRIES x ${SLEEP}s) for the managed certificate and writes BLOG_WEB_CUSTOM_DOMAIN and BLOG_WEB_CERTIFICATE_NAME to $ENV_FILE."
    exit 0
  fi

  for ((i = 1; i <= TRIES; i++)); do
    certs=$(az containerapp env certificate list -n "$ENVIRONMENT" -g "$RG" --managed-certificates-only \
      --query "[?properties.subjectName=='$HOST'].{name:name,state:properties.provisioningState}" -o json)
    state=$(jq -r '.[0].state // "none"' <<<"$certs")
    case "$state" in
      Succeeded)
        name=$(jq -r '.[0].name' <<<"$certs")
        break
        ;;
      Failed | DeleteFailed)
        echo "ERROR: the managed certificate for $HOST failed ($state). Check that the CNAME points directly at $FQDN, that any CAA record allows digicert.com, and that the app answers; then run this again." >&2
        exit 1
        ;;
    esac
    echo "Certificate for $HOST: $state (try $i of $TRIES)"
    if [ "$i" -lt "$TRIES" ]; then sleep "$SLEEP"; fi
  done
  if [ -z "$name" ]; then
    echo "ERROR: no issued certificate for $HOST after $TRIES tries." >&2
    exit 1
  fi

  binding=$(az containerapp hostname list -n "$WEB_APP" -g "$RG" \
    --query "[?name=='$HOST'].bindingType" -o tsv)
  if [ "$binding" != SniEnabled ]; then
    echo "ERROR: $HOST is not bound with SNI (binding: ${binding:-none})." >&2
    exit 1
  fi
  set_env BLOG_WEB_CUSTOM_DOMAIN "$HOST"
  set_env BLOG_WEB_CERTIFICATE_NAME "$name"
  echo "Bound $HOST with managed certificate $name; both written to $ENV_FILE. Run ./infra/deploy.sh <sha> next so the Bicep declares the domain."
}

if [ "$PHASE" = dns ]; then phase_dns; else phase_bind; fi
