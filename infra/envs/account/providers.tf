terraform {
  required_version = ">= 1.15.0"

  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = ">= 1.137.0, < 2.0.0"
    }
    time = {
      source  = "hashicorp/time"
      version = ">= 0.14.2, < 1.0.0"
    }
  }

  backend "azurerm" {
    # Configured with -backend-config at init
  }
}

# Authenticates through ARM_CLIENT_ID and ARM_TENANT_ID as the Databricks admin identity
provider "databricks" {
  host       = "https://accounts.azuredatabricks.net"
  account_id = var.databricks_account_id
}
