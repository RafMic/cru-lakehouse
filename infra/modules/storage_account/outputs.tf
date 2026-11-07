output "id" {
  type        = string
  description = "Resource ID of the storage account"
  value       = azurerm_storage_account.this.id
}

output "name" {
  type        = string
  description = "Name of the storage account"
  value       = azurerm_storage_account.this.name
}

output "landing_container_id" {
  type        = string
  description = "Resource ID of the landing container"
  value       = azurerm_storage_container.landing.id
}

output "landing_container_name" {
  type        = string
  description = "Name of the landing container"
  value       = azurerm_storage_container.landing.name
}

output "catalog_container_name" {
  type        = string
  description = "Name of the Unity Catalog managed storage container"
  value       = azurerm_storage_container.catalog.name
}
