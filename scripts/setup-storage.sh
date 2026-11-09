#!/usr/bin/env bash
# One-time, idempotent changes the blog needs on the SHARED storage account.
# Every change only adds or merges: other projects' CORS rules, soft-delete
# settings and lifecycle rules are never replaced. Default is a DRY RUN that
# prints each change; --apply performs them (needs the owner's yes).
#
#   1. one CORS rule so the browser can PUT uploads straight to blob storage
#   2. blob and container soft delete, only where it is currently off
#   3. one lifecycle rule: delete blog-drafts/uploads/ blobs after 30 days
#
# Usage: ./scripts/setup-storage.sh [--apply]
set -euo pipefail

ACCOUNT=${BLOG_STORAGE_ACCOUNT:-fhstorageportfolio}
SA_RG=${BLOG_STORAGE_RG:-FrederikHedaPlayground}
ORIGIN=${BLOG_STUDIO_ORIGIN:-https://blog-studio.frederikheda.com}
RULE_NAME=blog-drafts-uploads-30d

APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

# Print a change; run it only with --apply.
run() {
  echo "+ $*"
  if [ "$APPLY" -eq 1 ]; then
    "$@"
  fi
}

echo "Storage account: $ACCOUNT ($SA_RG). Mode: $([ "$APPLY" -eq 1 ] && echo APPLY || echo dry run)"

# 1. CORS -------------------------------------------------------------------
# Through the management API (blob-service-properties), not `az storage cors`:
# those data-plane commands take no --auth-mode and fall back to account keys.
# The API returns null when a service never had rules.
read_cors() {
  az storage account blob-service-properties show -n "$ACCOUNT" -g "$SA_RG" \
    --query "cors.corsRules" -o json
}
# Exact match against each rule's origin list: a look-alike such as
# "<origin>.example.test" must not count as ours.
has_origin() {
  jq -e --arg o "$ORIGIN" '
    any((. // [])[]; ((.allowedOrigins // []) | map(gsub("^\\s+|\\s+$"; ""))) | index($o) != null)' >/dev/null
}
cors=$(read_cors)
if has_origin <<<"$cors"; then
  echo "CORS: $ORIGIN already allowed."
else
  # The update replaces the whole rule list, so send the existing rules plus ours.
  rule=$(jq -n --arg o "$ORIGIN" '{
    allowedOrigins: [$o], allowedMethods: ["OPTIONS", "PUT"],
    allowedHeaders: ["x-ms-*", "content-type"], exposedHeaders: ["x-ms-*"],
    maxAgeInSeconds: 3600}')
  merged=$(jq -c --argjson rule "$rule" '(. // []) + [$rule]' <<<"$cors")
  echo "CORS: keeping $(jq '(. // []) | length' <<<"$cors") existing rule(s), adding $ORIGIN."
  run az storage account blob-service-properties update -n "$ACCOUNT" -g "$SA_RG" \
    --set "cors.corsRules=$merged"
  if [ "$APPLY" -eq 1 ]; then
    # A successful call is not proof: read the rules back. Our origin must be
    # there, and no existing rule may have been lost.
    after=$(read_cors)
    before_count=$(jq '(. // []) | length' <<<"$cors")
    after_count=$(jq '(. // []) | length' <<<"$after")
    if ! has_origin <<<"$after"; then
      echo "ERROR: CORS rule for $ORIGIN is missing after the update; stopping." >&2
      exit 1
    fi
    if [ "$after_count" -lt $((before_count + 1)) ]; then
      echo "ERROR: CORS has $after_count rule(s) after the update, expected at least $((before_count + 1)): an existing rule was lost; stopping." >&2
      exit 1
    fi
    echo "CORS: verified $ORIGIN is allowed ($after_count rule(s))."
  fi
fi

# 2. Soft delete ------------------------------------------------------------
blob_on=$(az storage account blob-service-properties show -n "$ACCOUNT" -g "$SA_RG" \
  --query "deleteRetentionPolicy.enabled" -o tsv)
container_on=$(az storage account blob-service-properties show -n "$ACCOUNT" -g "$SA_RG" \
  --query "containerDeleteRetentionPolicy.enabled" -o tsv)
sd_args=()
[ "$blob_on" = "true" ] || sd_args+=(--enable-delete-retention true --delete-retention-days 14)
[ "$container_on" = "true" ] || sd_args+=(--enable-container-delete-retention true --container-delete-retention-days 14)
if [ "${#sd_args[@]}" -eq 0 ]; then
  echo "Soft delete: blob and container already on; left unchanged."
else
  run az storage account blob-service-properties update -n "$ACCOUNT" -g "$SA_RG" "${sd_args[@]}"
fi

# 3. Lifecycle rule (merged into the existing policy) --------------------------
rule=$(jq -n --arg name "$RULE_NAME" '{
  name: $name, enabled: true, type: "Lifecycle",
  definition: {
    filters: {blobTypes: ["blockBlob"], prefixMatch: ["blog-drafts/uploads/"]},
    actions: {baseBlob: {delete: {daysAfterModificationGreaterThan: 30}}}
  }}')
if policy=$(az storage account management-policy show --account-name "$ACCOUNT" -g "$SA_RG" -o json 2>/dev/null); then
  existing=$(jq '.policy.rules // .rules // []' <<<"$policy")
else
  existing='[]'
fi
# Compare only what we set (name, enabled, prefix, age) on both sides: the
# service returns extra null keys, so an exact comparison would rewrite the
# policy on every run.
if jq -e --argjson rule "$rule" '
  def proj: {name, enabled,
             prefix: (.definition.filters.prefixMatch // []),
             days: .definition.actions.baseBlob.delete.daysAfterModificationGreaterThan};
  any(.[]; proj == ($rule | proj))' <<<"$existing" >/dev/null; then
  echo "Lifecycle: rule $RULE_NAME already present; left unchanged."
else
  merged=$(jq -c -n --argjson rules "$existing" --argjson rule "$rule" \
    '{rules: (($rules | map(select(.name != $rule.name))) + [$rule])}')
  echo "Lifecycle: keeping $(jq 'length' <<<"$existing") existing rule(s), adding or replacing $RULE_NAME."
  run az storage account management-policy create --account-name "$ACCOUNT" -g "$SA_RG" --policy "$merged"
fi
