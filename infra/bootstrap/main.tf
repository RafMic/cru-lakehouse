# Applied manually with a personal Azure login
# Creates the identities and the remote state backend that CI uses for every other root module

locals {
  current_user_object_id = data.azuread_client_config.current.object_id
  subscription_scope     = "/subscriptions/${var.subscription_id}"

  default_names = {
    tfstate_resource_group  = "rg-${var.project}-tfstate"
    tfstate_storage_account = "st${replace(var.project, "-", "")}tfstate"
    deploy_sp               = "sp-${var.project}-deploy"
    databricks_admin_sp     = "sp-${var.project}-databricks-admin"
    dev_job_sp              = "sp-${var.project}-dev-job"
    prod_job_sp             = "sp-${var.project}-prod-job"
    dev_group               = "az-${var.project}-dev"
    prod_group              = "az-${var.project}-prod"
    admins_group            = "az-${var.project}-admins"
  }
  names = merge(local.default_names, var.name_overrides)

  deploy_assignable_role_ids = join(", ", [for role in data.azurerm_role_definition.deploy_assignable : role.role_definition_id])

  # Both CI identities accept tokens from dev and prod environment jobs, PR plans and prod plans on main
  github_federated_credentials = {
    dev_env = {
      name    = "gh-environment-dev"
      subject = "${var.github_sub_claim_prefix}:environment:dev"
    }
    prod_env = {
      name    = "gh-environment-prod"
      subject = "${var.github_sub_claim_prefix}:environment:prod"
    }
    pull_request = {
      name    = "gh-pull-request"
      subject = "${var.github_sub_claim_prefix}:pull_request"
    }
    main_ref = {
      name    = "gh-ref-main"
      subject = "${var.github_sub_claim_prefix}:ref:refs/heads/main"
    }
  }
}

data "azuread_client_config" "current" {}

# Roles that infra/envs/* assigns. The deploy identity can assign only these
data "azurerm_role_definition" "deploy_assignable" {
  for_each = toset([
    "Storage Blob Data Contributor",
    "Storage Blob Data Reader",
    "Reader",
    "Storage Queue Data Contributor",
    "Storage Account Contributor",
    "EventGrid EventSubscription Contributor",
  ])

  name  = each.key
  scope = local.subscription_scope
}

# Deploy identity used by CI for all Azure and Databricks workspace resources
module "deploy" {
  source = "../modules/service_principal"

  display_name          = local.names.deploy_sp
  owners                = [local.current_user_object_id]
  federated_credentials = local.github_federated_credentials
}

resource "azurerm_role_assignment" "deploy_contributor" {
  scope                = local.subscription_scope
  role_definition_name = "Contributor"
  principal_id         = module.deploy.object_id
}

resource "azurerm_role_assignment" "deploy_rbac_administrator" {
  scope                = local.subscription_scope
  role_definition_name = "Role Based Access Control Administrator"
  principal_id         = module.deploy.object_id
  condition_version    = "2.0"
  condition            = <<-EOT
    (
      (!(ActionMatches{'Microsoft.Authorization/roleAssignments/write'}))
      OR
      (@Request[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAnyValues:GuidEquals {${local.deploy_assignable_role_ids}})
    )
    AND
    (
      (!(ActionMatches{'Microsoft.Authorization/roleAssignments/delete'}))
      OR
      (@Resource[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAnyValues:GuidEquals {${local.deploy_assignable_role_ids}})
    )
  EOT
}

resource "azurerm_role_assignment" "deploy_tfstate_access" {
  scope                = azurerm_storage_account.tfstate.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = module.deploy.object_id
}

# Identity for the account-level Databricks resources in infra/envs/account and the prod NCC
# Account Admin itself must be granted manually in the Databricks account console
module "databricks_admin" {
  source = "../modules/service_principal"

  display_name          = local.names.databricks_admin_sp
  owners                = [local.current_user_object_id]
  federated_credentials = local.github_federated_credentials
}

resource "azurerm_role_assignment" "databricks_admin_tfstate_access" {
  scope                = azurerm_storage_account.tfstate.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = module.databricks_admin.object_id
}

# Identities that Databricks jobs run as
module "dev_job" {
  source = "../modules/service_principal"

  display_name = local.names.dev_job_sp
  owners       = [local.current_user_object_id]
}

module "prod_job" {
  source = "../modules/service_principal"

  display_name = local.names.prod_job_sp
  owners       = [local.current_user_object_id]
}

# Access groups, synced to the Databricks account by infra/envs/account
resource "azuread_group" "dev" {
  display_name     = local.names.dev_group
  security_enabled = true
  owners           = [local.current_user_object_id]
  members          = [local.current_user_object_id]
}

resource "azuread_group" "prod" {
  display_name     = local.names.prod_group
  security_enabled = true
  owners           = [local.current_user_object_id]
  members          = [local.current_user_object_id]
}

# Owns every Unity Catalog object that infra/envs/*/02-databricks creates
resource "azuread_group" "admins" {
  display_name     = local.names.admins_group
  security_enabled = true
  owners           = [local.current_user_object_id]
  members = [
    local.current_user_object_id,
    module.deploy.object_id,
  ]
}

resource "azurerm_resource_group" "tfstate" {
  name     = local.names.tfstate_resource_group
  location = var.location
}

resource "azurerm_storage_account" "tfstate" {
  name                      = local.names.tfstate_storage_account
  resource_group_name       = azurerm_resource_group.tfstate.name
  location                  = azurerm_resource_group.tfstate.location
  account_tier              = "Standard"
  account_replication_type  = "LRS"
  account_kind              = "StorageV2"
  min_tls_version           = "TLS1_2"
  shared_access_key_enabled = false
  public_network_access     = "Enabled" # GitHub-hosted runners have no fixed IP range

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 30
    }

    container_delete_retention_policy {
      days = 30
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_container" "tfstate" {
  name                  = "tfstate"
  storage_account_id    = azurerm_storage_account.tfstate.id
  container_access_type = "private"

  lifecycle {
    prevent_destroy = true
  }
}
