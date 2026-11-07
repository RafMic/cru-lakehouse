locals {
  env  = "dev"
  name = "${var.project}-${local.env}"
  tags = merge(var.tags, { environment = local.env, project = var.project })
}

module "resource_group" {
  source = "../../../modules/resource_group"

  name     = "rg-${local.name}"
  location = var.location
  tags     = local.tags
}

module "storage_account" {
  source = "../../../modules/storage_account"

  name                = "st${replace(local.name, "-", "")}"
  resource_group_name = module.resource_group.name
  location            = var.location
  # Allowing classic compute through a storage firewall requires VNet injection
  public_network_access  = "Enabled"
  network_default_action = "Allow"
  tags                   = local.tags
}

resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-${local.name}"
  resource_group_name = module.resource_group.name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

resource "azurerm_monitor_diagnostic_setting" "storage" {
  for_each = toset(["blobServices", "queueServices"])

  name                       = "storage-logs"
  target_resource_id         = "${module.storage_account.id}/${each.key}/default"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id

  enabled_log {
    category = "StorageRead"
  }
  enabled_log {
    category = "StorageWrite"
  }
  enabled_log {
    category = "StorageDelete"
  }
}

module "access_connector" {
  source = "../../../modules/access_connector"

  name                = "ac-${local.name}"
  resource_group_name = module.resource_group.name
  location            = var.location
  storage_account_id  = module.storage_account.id
  resource_group_id   = module.resource_group.id
  tags                = local.tags
}

module "databricks_workspace" {
  source = "../../../modules/databricks_workspace"

  name                        = "dbw-${local.name}"
  resource_group_name         = module.resource_group.name
  location                    = var.location
  managed_resource_group_name = "rg-${local.name}-dbw-managed"
  tags                        = local.tags
}

# Lets the dev group browse landing files without compute.
# The catalog container stays reachable only through Unity Catalog
resource "azurerm_role_assignment" "dev_group_landing_reader" {
  scope                = module.storage_account.landing_container_id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = var.dev_group_object_id
}

resource "azurerm_role_assignment" "dev_group_storage_reader" {
  scope                = module.storage_account.id
  role_definition_name = "Reader"
  principal_id         = var.dev_group_object_id
}
