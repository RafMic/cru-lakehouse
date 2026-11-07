#!/usr/bin/env bash
# Exports DATABRICKS_HOST and BUNDLE_VAR_cluster_policy_id for one bundle target from its Terraform state
# With skip_if_missing=true, a target whose infrastructure isn't applied yet is skipped instead of failing
set -euo pipefail

target="$1"
skip_if_missing="${2:-false}"

for root in 01-azure 02-databricks; do
  terraform -chdir="infra/envs/$target/$root" init -input=false \
    -backend-config="resource_group_name=$TFSTATE_RESOURCE_GROUP" \
    -backend-config="storage_account_name=$TFSTATE_STORAGE_ACCOUNT" \
    -backend-config="container_name=tfstate" \
    -backend-config="use_azuread_auth=true" \
    -backend-config="key=$target/$root.tfstate" >/dev/null
done

if host=$(terraform -chdir="infra/envs/$target/01-azure" output -raw workspace_url 2>/dev/null) && [ -n "$host" ] &&
   policy_id=$(terraform -chdir="infra/envs/$target/02-databricks" output -raw cluster_policy_id 2>/dev/null) && [ -n "$policy_id" ]; then
  printf 'DATABRICKS_HOST=%s\nBUNDLE_VAR_cluster_policy_id=%s\n' "$host" "$policy_id" >> "$GITHUB_ENV"
  printf 'available=true\n' >> "$GITHUB_OUTPUT"
elif [ "$skip_if_missing" = true ]; then
  printf '::notice::infra/envs/%s is not applied yet - skipping\n' "$target"
  printf 'available=false\n' >> "$GITHUB_OUTPUT"
else
  printf '::error::No workspace_url or cluster_policy_id in infra/envs/%s state - apply the infrastructure first\n' "$target"
  exit 1
fi
