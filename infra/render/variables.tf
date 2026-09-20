variable "name_prefix" {
  type        = string
  description = "Name prefix for Render resources."
  default     = "tenant-access"
}

variable "region" {
  type        = string
  description = "Render region (frankfurt, oregon, ohio, singapore, virginia)."
  default     = "frankfurt"
}

variable "repo_url" {
  type        = string
  description = "GitHub repo URL for the Docker web service."
  default     = "https://github.com/Henvag/tenant-access-dashboard"
}

variable "branch" {
  type    = string
  default = "main"
}

variable "google_client_id" {
  type      = string
  sensitive = true
}

variable "google_client_secret" {
  type      = string
  sensitive = true
}

variable "entra_client_id" {
  type      = string
  default   = ""
  sensitive = true
}

variable "entra_client_secret" {
  type      = string
  default   = ""
  sensitive = true
}

variable "entra_tenant_id" {
  type    = string
  default = "common"
}
