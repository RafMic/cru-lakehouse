output "client_id" {
  type        = string
  description = "Application (client) ID"
  value       = azuread_application.this.client_id
}

output "object_id" {
  type        = string
  description = "Object ID of the service principal"
  value       = azuread_service_principal.this.object_id
}
