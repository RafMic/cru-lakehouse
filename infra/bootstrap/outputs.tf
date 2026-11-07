output "github_variables" {
  type        = map(string)
  description = "GitHub Actions repository variables"
  value = {
    AZURE_CLIENT_ID            = module.deploy.client_id
    DATABRICKS_ADMIN_CLIENT_ID = module.databricks_admin.client_id
    DEV_JOB_SP_APPLICATION_ID  = module.dev_job.client_id
    PROD_JOB_SP_APPLICATION_ID = module.prod_job.client_id
    DEV_GROUP_OBJECT_ID        = azuread_group.dev.object_id
    PROD_GROUP_OBJECT_ID       = azuread_group.prod.object_id
    ADMINS_GROUP_OBJECT_ID     = azuread_group.admins.object_id
    DEV_GROUP_NAME             = azuread_group.dev.display_name
    PROD_GROUP_NAME            = azuread_group.prod.display_name
    ADMINS_GROUP_NAME          = azuread_group.admins.display_name
    TFSTATE_RESOURCE_GROUP     = azurerm_resource_group.tfstate.name
    TFSTATE_STORAGE_ACCOUNT    = azurerm_storage_account.tfstate.name
    AZURE_TENANT_ID            = data.azuread_client_config.current.tenant_id
    AZURE_SUBSCRIPTION_ID      = var.subscription_id
  }
}
