variable "name" {
  type        = string
  description = "Name of the resource group"
}

variable "location" {
  type        = string
  description = "Azure region of the resource group"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the resource group"
  default     = {}
}
