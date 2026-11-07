locals {
  env  = "dev"
  name = "${var.project}-${local.env}"
}

module "databricks_environment" {
  source = "../../../modules/databricks_environment"

  environment                  = local.env
  name                         = local.name
  catalog_name                 = "cru_${local.env}"
  access_connector_id          = var.access_connector_id
  storage_account_name         = var.storage_account_name
  resource_group_name          = var.resource_group_name
  subscription_id              = var.subscription_id
  landing_container_name       = var.landing_container_name
  catalog_container_name       = var.catalog_container_name
  owner                        = var.admins_group_name
  deploy_sp_application_id     = var.deploy_sp_application_id
  job_sp_application_id        = var.dev_job_sp_application_id
  environment_group_name       = var.dev_group_name
  environment_group_privileges = ["USE_CATALOG", "USE_SCHEMA", "CREATE_SCHEMA", "CREATE_TABLE", "CREATE_MATERIALIZED_VIEW", "MODIFY", "SELECT", "READ_VOLUME"]
}
