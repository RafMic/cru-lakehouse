variable "name_prefix" {
  type        = string
  description = "Prefix for the name of every network resource"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group of the network resources"
}

variable "location" {
  type        = string
  description = "Azure region of the network resources"
}

variable "vnet_cidr" {
  type        = string
  description = "Address space of the virtual network. Each subnet gets a quarter of it"
  default     = "10.10.0.0/24"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to every network resource"
  default     = {}
}
