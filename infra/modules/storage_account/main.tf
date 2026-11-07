resource "azurerm_storage_account" "this" {
  name                              = var.name
  resource_group_name               = var.resource_group_name
  location                          = var.location
  account_tier                      = var.account_tier
  account_replication_type          = var.account_replication_type
  account_kind                      = "StorageV2"
  is_hns_enabled                    = true
  min_tls_version                   = "TLS1_2"
  infrastructure_encryption_enabled = true
  public_network_access             = var.public_network_access
  shared_access_key_enabled         = false
  tags                              = var.tags

  # azurerm leaves the Allow and AzureServices defaults out of state, so setting them shows a change on every plan
  dynamic "network_rules" {
    for_each = var.network_default_action == "Deny" ? [1] : []
    content {
      default_action = "Deny"
      bypass         = ["AzureServices"]
    }
  }
}

resource "azurerm_storage_container" "landing" {
  name                  = var.landing_container_name
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "catalog" {
  name                  = var.catalog_container_name
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}
