output "workspace_url" {
  type        = string
  description = "Workspace hostname, without https://"
  value       = azurerm_databricks_workspace.this.workspace_url
}

output "workspace_id" {
  type        = string
  description = "Databricks workspace ID"
  value       = azurerm_databricks_workspace.this.workspace_id
}
