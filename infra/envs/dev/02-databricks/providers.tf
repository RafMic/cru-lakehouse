terraform {
  required_version = ">= 1.15.0"

  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = ">= 1.137.0, < 2.0.0"
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
