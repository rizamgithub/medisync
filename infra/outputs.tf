output "resource_group_id" {
  description = "Full ARM ID of the MediSync resource group."
  value       = data.azurerm_resource_group.main.id
}

output "resource_group_location" {
  description = "Region the resource group lives in."
  value       = data.azurerm_resource_group.main.location
}

# --- Cosmos DB (runbook 06) ---

output "cosmosdb_account_name" {
  description = "Name of the Cosmos DB account (includes the random uniqueness suffix)."
  value       = azurerm_cosmosdb_account.main.name
}

output "cosmosdb_endpoint" {
  description = "Cosmos DB data-plane endpoint URL. Functions connect here."
  value       = azurerm_cosmosdb_account.main.endpoint
}

output "cosmosdb_database_name" {
  description = "Name of the Cosmos SQL database."
  value       = azurerm_cosmosdb_sql_database.main.name
}

# Account keys are deliberately NOT exposed as outputs. They live in state
# regardless, but surfacing them invites copy-paste leaks. Functions will read
# data via managed identity + Cosmos data-plane RBAC (or Key Vault) in a later
# runbook — not via output values.

# Add per-service outputs (function app hostname, etc.) as resources are
# introduced in the *.tf files below.
