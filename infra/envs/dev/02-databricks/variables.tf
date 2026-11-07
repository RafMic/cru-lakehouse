variable "project" {
  type        = string
  description = "Prefix for the names this root module creates, except the catalog and its external locations"
  default     = "cru-lakehouse"
}

variable "databricks_host" {
  type        = string
  description = "infra/envs/dev/01-azure's `workspace_url` output"
}

variable "access_connector_id" {
  type        = string
  description = "infra/envs/dev/01-azure's `access_connector_id` output"
}

variable "storage_account_name" {
  type        = string
  description = "infra/envs/dev/01-azure's `storage_account_name` output"
}

variable "resource_group_name" {
  type        = string
  description = "infra/envs/dev/01-azure's `resource_group_name` output"
}

variable "subscription_id" {
  type        = string
  description = "Azure subscription that holds this environment's resources"
}

variable "landing_container_name" {
  type        = string
  description = "infra/envs/dev/01-azure's `landing_container_name` output"
}

variable "catalog_container_name" {
  type        = string
  description = "infra/envs/dev/01-azure's `catalog_container_name` output"
}

variable "deploy_sp_application_id" {
  type        = string
  description = "Application ID of the deploy identity"
}

variable "dev_job_sp_application_id" {
  type        = string
  description = "Application ID of the dev job service principal"
}

variable "admins_group_name" {
  type        = string
  description = "Display name of the admins Entra ID group, which owns every Unity Catalog object this root module creates"
}

variable "dev_group_name" {
  type        = string
  description = "Display name of the dev Entra ID group"
}
