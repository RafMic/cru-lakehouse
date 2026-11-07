variable "subscription_id" {
  type        = string
  description = "Azure subscription that holds the state backend"
}

variable "tenant_id" {
  type        = string
  description = "Entra ID tenant for the service principals and groups this root module creates"
}

variable "location" {
  type        = string
  description = "Azure region for the state backend"
  default     = "swedencentral"
}

variable "project" {
  type        = string
  description = "Prefix for every resource and identity name this root module creates"
  default     = "cru-lakehouse"
}

variable "name_overrides" {
  type        = map(string)
  description = "Names that differ from the project-based convention in local.default_names, keyed the same way"
  default     = {}

  validation {
    condition     = alltrue([for key in keys(var.name_overrides) : contains(keys(local.default_names), key)])
    error_message = "name_overrides keys must be one of ${join(", ", keys(local.default_names))}"
  }
}

variable "github_sub_claim_prefix" {
  type        = string
  description = "The repo's OIDC sub_claim_prefix, as returned by `gh api repos/OWNER/REPO/actions/oidc/customization/sub`"
}
