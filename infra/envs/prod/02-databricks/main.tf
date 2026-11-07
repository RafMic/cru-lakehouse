locals {
  env  = "prod"
  name = "${var.project}-${local.env}"

  # Matched by endpoint name, so only the NCC's own connection requests are approved
  ncc_connection_names = {
    for key, endpoint_name in module.network_connectivity_config.private_endpoint_names : key => one([
      for connection in data.azapi_resource_list.storage_private_endpoint_connections.output.connections :
      connection.name if endswith(lower(connection.endpoint_id), "/${lower(endpoint_name)}")
    ])
  }
}

module "databricks_environment" {
  source = "../../../modules/databricks_environment"

  environment              = local.env
  name                     = local.name
  catalog_name             = "cru_${local.env}"
  access_connector_id      = var.access_connector_id
  storage_account_name     = var.storage_account_name
  resource_group_name      = var.resource_group_name
  subscription_id          = var.subscription_id
  landing_container_name   = var.landing_container_name
  catalog_container_name   = var.catalog_container_name
  owner                    = var.admins_group_name
  deploy_sp_application_id = var.deploy_sp_application_id
  job_sp_application_id    = var.prod_job_sp_application_id
  environment_group_name   = var.prod_group_name
  # Read-only, since only the job service principal writes prod data
  environment_group_privileges = ["USE_CATALOG", "USE_SCHEMA", "SELECT", "READ_VOLUME"]
}

module "network_connectivity_config" {
  source    = "../../../modules/network_connectivity_config"
  providers = { databricks = databricks.account }

  name         = "ncc-${local.name}"
  region       = var.location
  workspace_id = var.databricks_workspace_id
  private_endpoint_rules = {
    storage_blob = { resource_id = var.storage_account_id, group_id = "blob" }
    storage_dfs  = { resource_id = var.storage_account_id, group_id = "dfs" }
  }
}

data "azapi_resource_list" "storage_private_endpoint_connections" {
  type      = "Microsoft.Storage/storageAccounts/privateEndpointConnections@2025-01-01"
  parent_id = var.storage_account_id
  response_export_values = {
    connections = "value[].{name: name, endpoint_id: properties.privateEndpoint.id}"
  }

  # Read after the rules exist, so their connections are listed
  depends_on = [module.network_connectivity_config]
}

# The NCC's private endpoints take effect only once the storage account owner approves them
resource "azapi_update_resource" "ncc_private_endpoint_approval" {
  for_each = local.ncc_connection_names

  type      = "Microsoft.Storage/storageAccounts/privateEndpointConnections@2025-01-01"
  name      = each.value
  parent_id = var.storage_account_id
  body = {
    properties = {
      privateLinkServiceConnectionState = {
        status      = "Approved"
        description = "Approved for the Databricks NCC by Terraform"
      }
    }
  }

  lifecycle {
    precondition {
      condition     = each.value != null
      error_message = "The storage account has no private endpoint connection for NCC endpoint ${module.network_connectivity_config.private_endpoint_names[each.key]}"
    }
  }
}
