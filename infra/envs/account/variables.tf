variable "databricks_account_id" {
  type        = string
  description = "Databricks account ID, shown in the account console. Not a workspace ID"
}

variable "deploy_sp_application_id" {
  type        = string
  description = "Application ID of the deploy identity"
}

variable "admins_group_name" {
  type        = string
  description = "Display name of the admins Entra ID group"
}

variable "admins_group_object_id" {
  type        = string
  description = "Object ID of the admins Entra ID group"
}

variable "dev_group_name" {
  type        = string
  description = "Display name of the dev Entra ID group"
}

variable "dev_group_object_id" {
  type        = string
  description = "Object ID of the dev Entra ID group"
}

variable "dev_job_sp_application_id" {
  type        = string
  description = "Application ID of the dev job service principal"
}

variable "dev_workspace_id" {
  type        = number
  description = "Dev workspace ID from infra/envs/dev/01-azure. Null skips the dev workspace assignments"
  default     = null
}

variable "prod_group_name" {
  type        = string
  description = "Display name of the prod Entra ID group"
}

variable "prod_group_object_id" {
  type        = string
  description = "Object ID of the prod Entra ID group"
}

variable "prod_job_sp_application_id" {
  type        = string
  description = "Application ID of the prod job service principal"
}

variable "prod_workspace_id" {
  type        = number
  description = "Prod workspace ID from infra/envs/prod/01-azure. Null skips the prod workspace assignments"
  default     = null
}
