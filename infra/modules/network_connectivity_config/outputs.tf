output "private_endpoint_names" {
  type        = map(string)
  description = "Private endpoint name for each rule, under the same key as in private_endpoint_rules"
  value       = { for key, rule in databricks_mws_ncc_private_endpoint_rule.this : key => rule.endpoint_name }
}
