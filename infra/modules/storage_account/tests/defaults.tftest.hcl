mock_provider "azurerm" {}

variables {
  name                = "sttest"
  resource_group_name = "rg-test"
  location            = "swedencentral"
}

run "network_access_is_denied_by_default" {
  command = plan

  assert {
    condition     = azurerm_storage_account.this.network_rules[0].default_action == "Deny"
    error_message = "Storage must deny network access unless the caller opts out"
  }

  assert {
    condition     = azurerm_storage_account.this.public_network_access == "Disabled"
    error_message = "The public endpoint must be disabled by default"
  }
}

run "account_is_hardened" {
  command = plan

  assert {
    condition     = azurerm_storage_account.this.shared_access_key_enabled == false
    error_message = "Shared key access must stay disabled, so only Entra ID can authorize requests"
  }

  assert {
    condition     = azurerm_storage_account.this.min_tls_version == "TLS1_2"
    error_message = "The minimum TLS version must be 1.2"
  }

  assert {
    condition     = azurerm_storage_account.this.infrastructure_encryption_enabled == true
    error_message = "Infrastructure encryption must stay enabled"
  }

  assert {
    condition     = azurerm_storage_account.this.is_hns_enabled == true
    error_message = "Hierarchical namespace must stay enabled, as Unity Catalog external locations need ADLS Gen2"
  }
}
