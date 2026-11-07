resource "azuread_application" "this" {
  display_name = var.display_name
  owners       = var.owners
}

resource "azuread_service_principal" "this" {
  client_id = azuread_application.this.client_id
  owners    = var.owners
}

resource "azuread_application_federated_identity_credential" "this" {
  for_each = var.federated_credentials

  application_id = azuread_application.this.id
  display_name   = each.value.name
  description    = "GitHub Actions OIDC - ${each.key}"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = each.value.subject
}
