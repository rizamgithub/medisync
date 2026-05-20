variable "project_name" {
  description = "Short project identifier used as a resource name prefix."
  type        = string
  default     = "medisync"
}

variable "environment" {
  description = "Deployment environment (prod / dev / staging). Phase 1 only uses prod."
  type        = string
  default     = "prod"
}

variable "location" {
  description = "Azure region for all resources."
  type        = string
  default     = "southeastasia"
}

variable "resource_group_name" {
  description = "Existing resource group that holds every MediSync resource. Created in runbook 01."
  type        = string
  default     = "rg-medisync-prod"
}

variable "owner_email" {
  description = "Contact email recorded in resource tags."
  type        = string
  default     = "rizam.ibrahim.my@gmail.com"
}

variable "enable_match_event_subscription" {
  description = <<-EOT
    Wire the Event Grid topic to the match service's on_emergency_request
    trigger. Keep false for the first apply — the function must be deployed
    before the subscription can validate its endpoint. Flip to true only
    after `func azure functionapp publish` for the match service (runbook 09).
  EOT
  type        = bool
  default     = false
}
