variable "name" {
  type        = string
  description = "Name of the workspace"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group of the workspace"
}

variable "location" {
  type        = string
  description = "Azure region of the workspace"
}

variable "sku" {
  type        = string
  description = "Workspace SKU"
  default     = "premium"
}

variable "managed_resource_group_name" {
  type        = string
  description = "Name of the managed resource group Databricks creates for the workspace"
}

variable "vnet_injection" {
  type = object({
    virtual_network_id                = string
    public_subnet_name                = string
    private_subnet_name               = string
    public_subnet_nsg_association_id  = string
    private_subnet_nsg_association_id = string
  })
  description = "VNet to inject the workspace into. null keeps the workspace on the Databricks-managed VNet"
  default     = null
}

variable "no_public_ip" {
  type        = bool
  description = "Secure cluster connectivity, applied only with vnet_injection"
  default     = true
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the workspace"
  default     = {}
}
