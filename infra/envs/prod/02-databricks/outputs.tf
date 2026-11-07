output "catalog_name" {
  type        = string
  description = "Unity Catalog catalog for this environment"
  value       = module.databricks_environment.catalog_name
}

output "sql_warehouse_jdbc_url" {
  type        = string
  description = "JDBC URL of the SQL warehouse"
  value       = module.databricks_environment.sql_warehouse_jdbc_url
}

output "cluster_policy_id" {
  type        = string
  description = "ID of the cluster policy for job and pipeline clusters"
  value       = module.databricks_environment.cluster_policy_id
}
