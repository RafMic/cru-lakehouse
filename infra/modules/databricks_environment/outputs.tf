output "catalog_name" {
  type        = string
  description = "Unity Catalog catalog for this environment"
  value       = databricks_catalog.this.name
}

output "sql_warehouse_jdbc_url" {
  type        = string
  description = "JDBC URL of the SQL warehouse"
  value       = databricks_sql_endpoint.this.jdbc_url
}

output "cluster_policy_id" {
  type        = string
  description = "ID of the cluster policy for job and pipeline clusters"
  value       = databricks_cluster_policy.this.id
}
