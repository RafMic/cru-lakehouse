terraform {
  required_version = ">= 1.15.0"

  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = ">= 1.137.0, < 2.0.0"
    }
    azapi = {
      source  = "Azure/azapi"
      version = ">= 2.13.0, < 3.0.0"
    }
  }

  backend "azurerm" {
    # Configured with -backend-config at init
  }
}

# Authenticates through ARM_CLIENT_ID and ARM_TENANT_ID as the deploy identity
provider "databricks" {
  host = var.databricks_host
}

# Authenticates through azure_client_id as the Databricks admin identity, which creates the NCC
provider "databricks" {
  alias           = "account"
  host            = "https://accounts.azuredatabricks.net"
  account_id      = var.databricks_account_id
  azure_client_id = var.databricks_admin_sp_application_id
}

provider "azapi" {}
