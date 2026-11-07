variable "name" {
  type        = string
  description = "Name of the private endpoint"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group of the private endpoint"
}

variable "location" {
  type        = string
  description = "Azure region of the private endpoint"
}

variable "subnet_id" {
  type        = string
  description = "Resource ID of the subnet the private endpoint is placed in"
}

variable "target_resource_id" {
  type        = string
  description = "Resource ID of the resource the private endpoint connects to"
}

variable "subresource_names" {
  type        = list(string)
  description = "Target sub-resources of the private endpoint, such as blob or dfs"
}

variable "private_dns_zone_ids" {
  type        = list(string)
  description = "Resource IDs of the private DNS zones the endpoint registers its records in"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the private endpoint"
  default     = {}
}
