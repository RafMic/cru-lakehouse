output "name" {
  type        = string
  description = "Name of the storage credential"
  value       = databricks_storage_credential.this.id
}

output "external_location_names" {
  type        = map(string)
  description = "External location name for each entry, under the same key as in external_locations"
  value       = { for key, location in databricks_external_location.this : key => location.id }
}

output "external_location_urls" {
  type        = map(string)
  description = "External location URL for each entry, under the same key as in external_locations"
  value       = { for key, location in databricks_external_location.this : key => location.url }
}
