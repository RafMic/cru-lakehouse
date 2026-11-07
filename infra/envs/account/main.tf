locals {
  environments = {
    dev = {
      group_name            = var.dev_group_name
      group_object_id       = var.dev_group_object_id
      job_sp_application_id = var.dev_job_sp_application_id
      workspace_id          = var.dev_workspace_id
    }
    prod = {
      group_name            = var.prod_group_name
      group_object_id       = var.prod_group_object_id
      job_sp_application_id = var.prod_job_sp_application_id
      workspace_id          = var.prod_workspace_id
    }
  }

  # Only environments whose workspace exists get workspace assignments
  workspace_access = merge([
    for env, cfg in local.environments : {
      "${env}_group"  = { workspace_id = cfg.workspace_id, principal_id = databricks_group.environment[env].id }
      "${env}_job_sp" = { workspace_id = cfg.workspace_id, principal_id = databricks_service_principal.job[env].id }
      "${env}_admins" = { workspace_id = cfg.workspace_id, principal_id = databricks_group.admins.id }
    } if cfg.workspace_id != null
  ]...)
}

# external_id links each group to its Entra ID group, so automatic identity management doesn't create a duplicate
resource "databricks_group" "environment" {
  for_each = local.environments

  display_name = each.value.group_name
  external_id  = each.value.group_object_id
}

resource "databricks_group" "admins" {
  display_name = var.admins_group_name
  external_id  = var.admins_group_object_id
}

resource "databricks_service_principal" "job" {
  for_each = local.environments

  application_id = each.value.job_sp_application_id
}

# A rule set written right after its service principal is created can fail with "Internal RBAC store resource conflict"
resource "time_sleep" "job_sp_ready" {
  for_each = local.environments

  create_duration = "30s"

  triggers = {
    application_id = databricks_service_principal.job[each.key].application_id
  }
}

# Lets the deploy identity set a job's run_as to the job service principal
# Authoritative: replaces any other roles on the rule set
resource "databricks_access_control_rule_set" "job_sp_user" {
  for_each = local.environments

  name = "accounts/${var.databricks_account_id}/servicePrincipals/${time_sleep.job_sp_ready[each.key].triggers["application_id"]}/ruleSets/default"

  grant_rules {
    role       = "roles/servicePrincipal.user"
    principals = ["servicePrincipals/${var.deploy_sp_application_id}"]
  }
}

# Workspace access for object ACLs such as the bundle's permissions, which Unity Catalog grants don't need
resource "databricks_mws_permission_assignment" "workspace_access" {
  for_each = local.workspace_access

  workspace_id = each.value.workspace_id
  principal_id = each.value.principal_id
  permissions  = ["USER"] # Capabilities come from Unity Catalog grants and the bundle's permissions
}
