output "id" {
  type        = string
  description = "Resource ID of the access connector"
  value       = azurerm_databricks_access_connector.this.id
}
