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
