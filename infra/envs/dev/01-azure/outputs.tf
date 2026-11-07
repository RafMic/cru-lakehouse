output "workspace_url" {
  type        = string
  description = "Databricks workspace hostname, without https://"
  value       = module.databricks_workspace.workspace_url
}

output "workspace_id" {
  type        = string
  description = "Databricks workspace ID"
  value       = module.databricks_workspace.workspace_id
}

output "resource_group_name" {
  type        = string
  description = "Resource group that holds this environment's resources"
  value       = module.resource_group.name
}

output "storage_account_name" {
  type        = string
  description = "ADLS Gen2 account behind the landing zone and Unity Catalog managed storage"
  value       = module.storage_account.name
}

output "landing_container_name" {
  type        = string
  description = "Container for the raw API responses"
  value       = module.storage_account.landing_container_name
}

output "catalog_container_name" {
  type        = string
  description = "Container for Unity Catalog managed storage"
  value       = module.storage_account.catalog_container_name
}

output "access_connector_id" {
  type        = string
  description = "Resource ID of the access connector behind the Unity Catalog storage credential"
  value       = module.access_connector.id
}
