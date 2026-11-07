variable "display_name" {
  type        = string
  description = "Display name of the application and its service principal"
}

variable "owners" {
  type        = list(string)
  description = "Object IDs of the application and service principal owners"
}

# Example: { main_ref = { name = "gh-ref-main", subject = "repo:owner/repo:ref:refs/heads/main" } }
variable "federated_credentials" {
  type = map(object({
    name    = string
    subject = string
  }))
  description = "Map of context name to GitHub Actions OIDC credential. name is its display name in Entra ID, subject must match the token's sub claim exactly"
  default     = {}
}
