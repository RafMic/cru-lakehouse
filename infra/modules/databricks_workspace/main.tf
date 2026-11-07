resource "azurerm_databricks_workspace" "this" {
  name                        = var.name
  resource_group_name         = var.resource_group_name
  location                    = var.location
  sku                         = var.sku
  managed_resource_group_name = var.managed_resource_group_name
  tags                        = var.tags

  dynamic "custom_parameters" {
    for_each = var.vnet_injection != null ? [var.vnet_injection] : []
    content {
      virtual_network_id                                   = custom_parameters.value.virtual_network_id
      public_subnet_name                                   = custom_parameters.value.public_subnet_name
      private_subnet_name                                  = custom_parameters.value.private_subnet_name
      public_subnet_network_security_group_association_id  = custom_parameters.value.public_subnet_nsg_association_id
      private_subnet_network_security_group_association_id = custom_parameters.value.private_subnet_nsg_association_id
      no_public_ip                                         = var.no_public_ip
    }
  }
}
