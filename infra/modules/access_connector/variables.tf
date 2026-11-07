variable "name" {
  type        = string
  description = "Name of the access connector"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group of the access connector"
}

variable "location" {
  type        = string
  description = "Azure region of the access connector"
}

variable "storage_account_id" {
  type        = string
  description = "Resource ID of the storage account the connector reads, writes and sets up file events on"
}

variable "resource_group_id" {
  type        = string
  description = "Resource ID of the resource group that holds the storage account, for the file events Event Grid subscription"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the access connector"
  default     = {}
}
