#!/usr/bin/env bash
# Exports TF_VAR_<env>_workspace_id for every environment whose 01-azure state has a workspace
# infra/envs/account manages every workspace's assignments in one state, so an omitted ID removes that workspace's assignments
set -euo pipefail

for env in dev prod; do
  dir="infra/envs/$env/01-azure"
  terraform -chdir="$dir" init -input=false \
    -backend-config="resource_group_name=$TFSTATE_RESOURCE_GROUP" \
    -backend-config="storage_account_name=$TFSTATE_STORAGE_ACCOUNT" \
    -backend-config="container_name=tfstate" \
    -backend-config="use_azuread_auth=true" \
    -backend-config="key=$env/01-azure.tfstate" >/dev/null

  if id=$(terraform -chdir="$dir" output -raw workspace_id 2>/dev/null) && [ -n "$id" ]; then
    printf 'TF_VAR_%s_workspace_id=%s\n' "$env" "$id" >> "$GITHUB_ENV"
    printf '%s workspace: %s\n' "$env" "$id"
  else
    printf '%s workspace: not deployed, its assignments are skipped\n' "$env"
  fi
done
