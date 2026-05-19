output "resource_group_id" {
  description = "Full ARM ID of the MediSync resource group."
  value       = data.azurerm_resource_group.main.id
}

output "resource_group_location" {
  description = "Region the resource group lives in."
  value       = data.azurerm_resource_group.main.location
}

# Add per-service outputs (cosmos endpoint, function app hostname, etc.) as
# resources are introduced in the *.tf files below.
