variable "environment" {
  type        = string
  description = "Environment name, used in object comments"
}

variable "name" {
  type        = string
  description = "Name of the storage credential, cluster policy and SQL warehouse"
}

variable "catalog_name" {
  type        = string
  description = "Name of the Unity Catalog catalog"
}

variable "access_connector_id" {
  type        = string
  description = "Resource ID of the access connector whose managed identity the storage credential uses"
}

variable "storage_account_name" {
  type        = string
  description = "Storage account that holds the landing and catalog containers"
}

variable "resource_group_name" {
  type        = string
  description = "Resource group that holds the storage account"
}

variable "subscription_id" {
  type        = string
  description = "Azure subscription that holds the storage account"
}

variable "landing_container_name" {
  type        = string
  description = "Container for the raw API responses"
}

variable "catalog_container_name" {
  type        = string
  description = "Container for Unity Catalog managed storage"
}

variable "owner" {
  type        = string
  description = "Owner of every Unity Catalog object this module creates"
}

variable "deploy_sp_application_id" {
  type        = string
  description = "Application ID of the deploy identity"
}

variable "job_sp_application_id" {
  type        = string
  description = "Application ID of the job service principal"
}

variable "environment_group_name" {
  type        = string
  description = "Display name of the environment's Entra ID group"
}

variable "environment_group_privileges" {
  type        = list(string)
  description = "Catalog privileges of the environment's Entra ID group"
}

variable "cluster_policy_max_dbus_per_hour" {
  type        = number
  description = "Maximum DBUs per hour of a cluster that uses the cluster policy"
  default     = 10
}

variable "sql_warehouse_cluster_size" {
  type        = string
  description = "Cluster size of the SQL warehouse"
  default     = "2X-Small"
}

variable "sql_warehouse_max_num_clusters" {
  type        = number
  description = "Maximum number of clusters of the SQL warehouse"
  default     = 1
}

variable "sql_warehouse_auto_stop_mins" {
  type        = number
  description = "Idle minutes before the SQL warehouse stops"
  default     = 10

  validation {
    condition     = var.sql_warehouse_auto_stop_mins > 0
    error_message = "sql_warehouse_auto_stop_mins must be greater than 0, since 0 disables auto-stop"
  }
}

variable "sql_warehouse_enable_serverless_compute" {
  type        = bool
  description = "Whether the SQL warehouse runs on serverless compute"
  default     = true
}
