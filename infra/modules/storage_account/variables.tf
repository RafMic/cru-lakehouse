variable "name" {
  type        = string
  description = "Name of the storage account"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group of the storage account"
}

variable "location" {
  type        = string
  description = "Azure region of the storage account"
}

variable "account_tier" {
  type        = string
  description = "Standard or Premium"
  default     = "Standard"
}

variable "account_replication_type" {
  type        = string
  description = "Replication type"
  default     = "LRS"
}

variable "landing_container_name" {
  type        = string
  description = "Container for the raw API responses"
  default     = "landing"
}

variable "catalog_container_name" {
  type        = string
  description = "Container for Unity Catalog managed storage"
  default     = "unity-catalog"
}

variable "public_network_access" {
  type        = string
  description = "Public endpoint access"
  default     = "Disabled"

  validation {
    condition     = contains(["Enabled", "Disabled", "SecuredByPerimeter"], var.public_network_access)
    error_message = "public_network_access must be Enabled, Disabled or SecuredByPerimeter"
  }
}

variable "network_default_action" {
  type        = string
  description = "Network rules default action for the public endpoint"
  default     = "Deny"

  validation {
    condition     = contains(["Deny", "Allow"], var.network_default_action)
    error_message = "network_default_action must be Deny or Allow"
  }
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the storage account"
  default     = {}
}
