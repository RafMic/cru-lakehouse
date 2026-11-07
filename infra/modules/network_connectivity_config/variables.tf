variable "name" {
  type        = string
  description = "Name of the NCC"
}

variable "region" {
  type        = string
  description = "Azure region of the NCC, same as the workspace's region"
}

variable "workspace_id" {
  type        = number
  description = "ID of the workspace the NCC is bound to"
}

# Example: { storage_blob = { resource_id = azurerm_storage_account.this.id, group_id = "blob" } }
variable "private_endpoint_rules" {
  type = map(object({
    resource_id = string
    group_id    = string
  }))
  description = "Map of rule name to private endpoint target. resource_id is the Azure resource, group_id its sub-resource, such as blob or dfs"
}
