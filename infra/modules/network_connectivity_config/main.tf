resource "databricks_mws_network_connectivity_config" "this" {
  name   = var.name
  region = var.region
}

# Each rule creates a private endpoint that stays PENDING until the target resource's owner approves it
resource "databricks_mws_ncc_private_endpoint_rule" "this" {
  for_each = var.private_endpoint_rules

  network_connectivity_config_id = databricks_mws_network_connectivity_config.this.network_connectivity_config_id
  resource_id                    = each.value.resource_id
  group_id                       = each.value.group_id
}

resource "databricks_mws_ncc_binding" "this" {
  network_connectivity_config_id = databricks_mws_network_connectivity_config.this.network_connectivity_config_id
  workspace_id                   = var.workspace_id
}
