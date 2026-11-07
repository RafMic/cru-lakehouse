variable "name" {
  type        = string
  description = "Name of the storage credential"
}

variable "access_connector_id" {
  type        = string
  description = "Resource ID of the access connector whose managed identity the credential uses"
}

variable "storage_account_name" {
  type        = string
  description = "Storage account that holds the external locations' containers"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group that holds the storage account"
}

variable "subscription_id" {
  type        = string
  description = "Azure subscription that holds the storage account"
}

# Example: { landing = { name = "cru_dev_landing", container_name = "landing", comment = "Landing zone access" } }
variable "external_locations" {
  type = map(object({
    name           = string
    container_name = string
    comment        = optional(string)
  }))
  description = "Map of location key to external location, one per container. name is its Unity Catalog name, container_name the container it points to"
}

variable "comment" {
  type        = string
  description = "Comment on the storage credential"
  default     = null
}

variable "owner" {
  type        = string
  description = "Owner of the credential and its external locations, or the creating identity when null"
  default     = null
}
