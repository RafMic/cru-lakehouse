plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

plugin "azurerm" {
  enabled = true
  version = "0.33.0"
  source  = "github.com/terraform-linters/tflint-ruleset-azurerm"
}

# prevent_destroy can't differ per environment in a shared module, and dev must stay destroyable
rule "azurerm_resources_missing_prevent_destroy" {
  enabled = false
}
