locals {
  schemas = {
    landing = "Raw API responses (raw_agreements volume) and the ingestion ledger"
    bronze  = "Raw records loaded into Delta by Auto Loader, with ingestion metadata"
    silver  = "Typed, deduplicated and conformed agreements, parties and addresses"
    gold    = "Star schema for reporting"
  }
}

resource "databricks_catalog" "this" {
  name    = var.catalog_name
  comment = "CRU lakehouse - ${var.environment} catalog"
  # Required because the metastore has no storage root
  storage_root   = module.storage_credential.external_location_urls["catalog"]
  isolation_mode = "ISOLATED"
  owner          = var.owner
}

module "storage_credential" {
  source = "../storage_credential"

  name                 = var.name
  access_connector_id  = var.access_connector_id
  storage_account_name = var.storage_account_name
  resource_group_name  = var.resource_group_name
  subscription_id      = var.subscription_id
  comment              = "CRU lakehouse ${var.environment} - access connector managed identity"
  owner                = var.owner

  external_locations = {
    landing = {
      name           = "${var.catalog_name}_landing"
      container_name = var.landing_container_name
      comment        = "CRU lakehouse ${var.environment} - landing zone access"
    }
    catalog = {
      name           = "${var.catalog_name}_catalog"
      container_name = var.catalog_container_name
      comment        = "CRU lakehouse ${var.environment} - Unity Catalog managed storage root"
    }
  }
}

resource "databricks_schema" "this" {
  for_each = local.schemas

  catalog_name = databricks_catalog.this.name
  name         = each.key
  comment      = each.value
  owner        = var.owner
}

resource "databricks_volume" "landing" {
  name             = "raw_agreements"
  catalog_name     = databricks_catalog.this.name
  schema_name      = databricks_schema.this["landing"].name
  volume_type      = "EXTERNAL"
  storage_location = "${module.storage_credential.external_location_urls["landing"]}raw_agreements"
  comment          = "Raw API responses, agreements_search/ and agreements_detail/ partitioned by year=/month=/day="
  owner            = var.owner
}

resource "databricks_cluster_policy" "this" {
  name = var.name
  definition = jsonencode({
    "dbus_per_hour" : {
      "type" : "range",
      "maxValue" : var.cluster_policy_max_dbus_per_hour
    }
  })
}

resource "databricks_permissions" "cluster_policy" {
  cluster_policy_id = databricks_cluster_policy.this.id

  access_control {
    service_principal_name = var.job_sp_application_id
    permission_level       = "CAN_USE"
  }
}

data "databricks_service_principal" "job" {
  application_id = var.job_sp_application_id
}

resource "databricks_entitlements" "job_sp" {
  service_principal_id = data.databricks_service_principal.job.id
  workspace_access     = true
}

data "databricks_group" "environment" {
  display_name = var.environment_group_name
}

resource "databricks_entitlements" "environment_group" {
  group_id              = data.databricks_group.environment.id
  workspace_access      = true
  databricks_sql_access = true
}

resource "databricks_sql_endpoint" "this" {
  name                      = var.name
  cluster_size              = var.sql_warehouse_cluster_size
  max_num_clusters          = var.sql_warehouse_max_num_clusters
  auto_stop_mins            = var.sql_warehouse_auto_stop_mins
  enable_serverless_compute = var.sql_warehouse_enable_serverless_compute
}

resource "databricks_permissions" "sql_warehouse" {
  sql_endpoint_id = databricks_sql_endpoint.this.id

  access_control {
    group_name       = var.environment_group_name
    permission_level = "CAN_USE"
  }
}

# Grants made outside Terraform are removed
resource "databricks_grants" "catalog" {
  catalog = databricks_catalog.this.name

  grant {
    principal  = var.environment_group_name
    privileges = var.environment_group_privileges
  }
  grant {
    principal  = var.deploy_sp_application_id
    privileges = ["MANAGE"]
  }
  grant {
    principal  = var.job_sp_application_id
    privileges = ["USE_CATALOG", "USE_SCHEMA", "SELECT", "MODIFY", "CREATE_TABLE", "CREATE_MATERIALIZED_VIEW", "READ_VOLUME", "WRITE_VOLUME"]
  }
}

resource "databricks_grants" "storage_credential" {
  storage_credential = module.storage_credential.name

  grant {
    principal  = var.deploy_sp_application_id
    privileges = ["MANAGE"]
  }
}

resource "databricks_grants" "external_location" {
  for_each = module.storage_credential.external_location_names

  external_location = each.value

  grant {
    principal  = var.deploy_sp_application_id
    privileges = ["MANAGE"]
  }
}
