resource "azurerm_private_dns_zone" "this" {
  name                = var.zone_name
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "this" {
  name                = "link-${replace(var.zone_name, ".", "-")}"
  private_dns_zone_id = azurerm_private_dns_zone.this.id
  virtual_network_id  = var.virtual_network_id
  tags                = var.tags
}
