mock_provider "azuread" {}

variables {
  display_name = "sp-test"
  owners       = ["00000000-0000-0000-0000-000000000000"]
}

run "no_federated_credentials_by_default" {
  command = plan

  assert {
    condition     = length(azuread_application_federated_identity_credential.this) == 0
    error_message = "The service principal must not accept external tokens unless the caller opts in"
  }
}

run "federated_credentials_trust_github_actions" {
  command = plan

  variables {
    federated_credentials = {
      main_ref = {
        name    = "gh-ref-main"
        subject = "repo:owner/repo:ref:refs/heads/main"
      }
    }
  }

  assert {
    condition     = azuread_application_federated_identity_credential.this["main_ref"].issuer == "https://token.actions.githubusercontent.com"
    error_message = "Federated credentials must trust the GitHub Actions OIDC issuer"
  }

  assert {
    condition     = azuread_application_federated_identity_credential.this["main_ref"].subject == "repo:owner/repo:ref:refs/heads/main"
    error_message = "The subject must be passed through unchanged"
  }
}
