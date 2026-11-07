output "id" {
  type        = string
  description = "Resource ID of the private DNS zone"
  value       = azurerm_private_dns_zone.this.id
}
