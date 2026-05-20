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
# regardless, but surfacing them invites copy-paste leaks. Functions read data
# via managed identity + Cosmos data-plane RBAC (see identity.tf).

# --- Function Apps (runbook 09) ---

output "function_app_names" {
  description = "Function App names — pass to `func azure functionapp publish`."
  value = {
    user      = azurerm_linux_function_app.user.name
    inventory = azurerm_linux_function_app.inventory.name
    match     = azurerm_linux_function_app.match.name
  }
}

output "function_app_hostnames" {
  description = "Default HTTPS hostnames of the three Function Apps."
  value = {
    user      = azurerm_linux_function_app.user.default_hostname
    inventory = azurerm_linux_function_app.inventory.default_hostname
    match     = azurerm_linux_function_app.match.default_hostname
  }
}

# --- Event Grid (runbook 09) ---

output "eventgrid_topic_endpoint" {
  description = "Event Grid topic endpoint the match service publishes to."
  value       = azurerm_eventgrid_topic.main.endpoint
}

# The Event Grid topic access key is NOT output — the match service publishes
# via managed identity + the EventGrid Data Sender role (see identity.tf).

# --- Observability ---

output "application_insights_name" {
  description = "Application Insights resource — open its Application Map for the cross-service trace."
  value       = azurerm_application_insights.main.name
}
