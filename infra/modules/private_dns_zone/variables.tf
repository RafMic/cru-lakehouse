variable "zone_name" {
  type        = string
  description = "Name of the private DNS zone"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group of the DNS zone"
}

variable "virtual_network_id" {
  type        = string
  description = "Resource ID of the virtual network linked to the zone"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the zone and its virtual network link"
  default     = {}
}
