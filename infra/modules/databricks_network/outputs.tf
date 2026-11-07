output "vnet_id" {
  type        = string
  description = "Resource ID of the virtual network"
  value       = azurerm_virtual_network.this.id
}

output "public_subnet_name" {
  type        = string
  description = "Name of the public subnet"
  value       = azurerm_subnet.public.name
}

output "private_subnet_name" {
  type        = string
  description = "Name of the private subnet"
  value       = azurerm_subnet.private.name
}

output "public_subnet_nsg_association_id" {
  type        = string
  description = "ID of the public subnet's NSG association"
  value       = azurerm_subnet_network_security_group_association.public.id
}

output "private_subnet_nsg_association_id" {
  type        = string
  description = "ID of the private subnet's NSG association"
  value       = azurerm_subnet_network_security_group_association.private.id
}

output "private_endpoints_subnet_id" {
  type        = string
  description = "Resource ID of the private endpoint subnet"
  value       = azurerm_subnet.private_endpoints.id
}
