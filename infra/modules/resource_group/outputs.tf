output "id" {
  type        = string
  description = "Resource ID of the resource group"
  value       = azurerm_resource_group.this.id
}

output "name" {
  type        = string
  description = "Name of the resource group"
  value       = azurerm_resource_group.this.name
}

output "location" {
  type        = string
  description = "Azure region of the resource group"
  value       = azurerm_resource_group.this.location
}
