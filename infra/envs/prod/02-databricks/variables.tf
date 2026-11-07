variable "project" {
  type        = string
  description = "Prefix for the names this root module creates, except the catalog and its external locations"
  default     = "cru-lakehouse"
}

variable "databricks_host" {
  type        = string
  description = "infra/envs/prod/01-azure's `workspace_url` output"
}

variable "databricks_workspace_id" {
  type        = number
  description = "infra/envs/prod/01-azure's `workspace_id` output"
}

variable "access_connector_id" {
  type        = string
  description = "infra/envs/prod/01-azure's `access_connector_id` output"
}

variable "storage_account_id" {
  type        = string
  description = "infra/envs/prod/01-azure's `storage_account_id` output"
}

variable "storage_account_name" {
  type        = string
  description = "infra/envs/prod/01-azure's `storage_account_name` output"
}

variable "resource_group_name" {
  type        = string
  description = "infra/envs/prod/01-azure's `resource_group_name` output"
}

variable "subscription_id" {
  type        = string
  description = "Azure subscription that holds this environment's resources"
}

variable "landing_container_name" {
  type        = string
  description = "infra/envs/prod/01-azure's `landing_container_name` output"
}

variable "catalog_container_name" {
  type        = string
  description = "infra/envs/prod/01-azure's `catalog_container_name` output"
}

variable "location" {
  type        = string
  description = "infra/envs/prod/01-azure's `location` output"
}

variable "databricks_account_id" {
  type        = string
  description = "Databricks account ID, shown in the account console. Not a workspace ID"
}

variable "databricks_admin_sp_application_id" {
  type        = string
  description = "Application ID of the Databricks admin identity, which creates the NCC"
}

variable "deploy_sp_application_id" {
  type        = string
  description = "Application ID of the deploy identity"
}

variable "prod_job_sp_application_id" {
  type        = string
  description = "Application ID of the prod job service principal"
}

variable "admins_group_name" {
  type        = string
  description = "Display name of the admins Entra ID group, which owns every Unity Catalog object this root module creates"
}

variable "prod_group_name" {
  type        = string
  description = "Display name of the prod Entra ID group"
}
