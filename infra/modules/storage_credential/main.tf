resource "databricks_storage_credential" "this" {
  name           = var.name
  comment        = var.comment
  owner          = var.owner
  isolation_mode = "ISOLATION_MODE_ISOLATED"

  azure_managed_identity {
    access_connector_id = var.access_connector_id
  }
}

resource "databricks_external_location" "this" {
  for_each = var.external_locations

  name               = each.value.name
  url                = "abfss://${each.value.container_name}@${var.storage_account_name}.dfs.core.windows.net/"
  credential_name    = databricks_storage_credential.this.id
  comment            = each.value.comment
  owner              = var.owner
  isolation_mode     = "ISOLATION_MODE_ISOLATED"
  enable_file_events = true

  # Databricks creates the storage queue and the Event Grid subscription for the file events
  file_event_queue {
    managed_aqs {
      resource_group  = var.resource_group_name
      subscription_id = var.subscription_id
    }
  }
}
