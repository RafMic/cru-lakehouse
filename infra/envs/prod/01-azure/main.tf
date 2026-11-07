locals {
  env  = "prod"
  name = "${var.project}-${local.env}"
  tags = merge(var.tags, { environment = local.env, project = var.project })
}

module "resource_group" {
  source = "../../../modules/resource_group"

  name     = "rg-${local.name}"
  location = var.location
  tags     = local.tags
}

module "network" {
  source = "../../../modules/databricks_network"

  name_prefix         = local.name
  resource_group_name = module.resource_group.name
  location            = var.location
  tags                = local.tags
}

module "storage_account" {
  source = "../../../modules/storage_account"

  name                  = "st${replace(local.name, "-", "")}"
  resource_group_name   = module.resource_group.name
  location              = var.location
  public_network_access = "Disabled"
  tags                  = local.tags
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
  vnet_injection = {
    virtual_network_id                = module.network.vnet_id
    public_subnet_name                = module.network.public_subnet_name
    private_subnet_name               = module.network.private_subnet_name
    public_subnet_nsg_association_id  = module.network.public_subnet_nsg_association_id
    private_subnet_nsg_association_id = module.network.private_subnet_nsg_association_id
  }
  tags = local.tags
}

module "dns_zone_blob" {
  source = "../../../modules/private_dns_zone"

  zone_name           = "privatelink.blob.core.windows.net"
  resource_group_name = module.resource_group.name
  virtual_network_id  = module.network.vnet_id
  tags                = local.tags
}

module "dns_zone_dfs" {
  source = "../../../modules/private_dns_zone"

  zone_name           = "privatelink.dfs.core.windows.net"
  resource_group_name = module.resource_group.name
  virtual_network_id  = module.network.vnet_id
  tags                = local.tags
}

module "pe_storage_blob" {
  source = "../../../modules/private_endpoint"

  name                 = "pe-${local.name}-blob"
  resource_group_name  = module.resource_group.name
  location             = var.location
  subnet_id            = module.network.private_endpoints_subnet_id
  target_resource_id   = module.storage_account.id
  subresource_names    = ["blob"]
  private_dns_zone_ids = [module.dns_zone_blob.id]
  tags                 = local.tags
}

module "pe_storage_dfs" {
  source = "../../../modules/private_endpoint"

  name                 = "pe-${local.name}-dfs"
  resource_group_name  = module.resource_group.name
  location             = var.location
  subnet_id            = module.network.private_endpoints_subnet_id
  target_resource_id   = module.storage_account.id
  subresource_names    = ["dfs"]
  private_dns_zone_ids = [module.dns_zone_dfs.id]
  tags                 = local.tags
}

resource "azurerm_role_assignment" "prod_group_reader" {
  scope                = module.resource_group.id
  role_definition_name = "Reader"
  principal_id         = var.prod_group_object_id
}
