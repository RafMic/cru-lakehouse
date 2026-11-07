variable "subscription_id" {
  type        = string
  description = "Azure subscription that holds this environment's resources"
}

variable "project" {
  type        = string
  description = "Prefix for every resource name this root module creates"
  default     = "cru-lakehouse"
}

variable "location" {
  type        = string
  description = "Azure region for every resource in this root module"
  default     = "swedencentral"
}

variable "tags" {
  type        = map(string)
  description = "Extra tags for every resource, on top of environment and project"
  default     = {}
}

variable "dev_group_object_id" {
  type        = string
  description = "Object ID of the dev Entra ID group, from DEV_GROUP_OBJECT_ID in infra/bootstrap's github_variables output"
}
