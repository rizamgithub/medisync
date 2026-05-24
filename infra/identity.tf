# Identity & access — least-privilege data-plane role assignments.
#
# Each Function App runs as its own system-assigned Managed Identity (declared
# in functions.tf) and authenticates to Cosmos DB and Event Grid as itself —
# no account keys or connection strings (context.md §6).
#
# PREREQUISITE: the medisync-deploy SP only has Contributor on the resource
# group, which CANNOT create role assignments. Grant it "Role Based Access
# Control Administrator" on the RG once, as Owner, before `terraform apply`
# (runbook 09, Step 2). Without it the assignments below fail with 403.

# ---------------------------------------------------------------------------
# Cosmos DB — data-plane RBAC
# ---------------------------------------------------------------------------
# "Cosmos DB Built-in Data Contributor" grants item read/write on the data
# plane. Its definition id is the well-known built-in 00...02. Cosmos uses a
# dedicated role-assignment resource (azurerm_cosmosdb_sql_role_assignment) —
# this is NOT the same as a control-plane azurerm_role_assignment.
locals {
  cosmos_data_contributor_role_id = "${azurerm_cosmosdb_account.main.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
}

# Each service is granted access at the account scope. Tightening this to the
# per-service container scope (".../dbs/medisync/colls/<container>") is a
# documented future hardening — all three services share one account and one
# database today, so account scope is the pragmatic Phase 1 choice.
resource "azurerm_cosmosdb_sql_role_assignment" "user" {
  resource_group_name = data.azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  role_definition_id  = local.cosmos_data_contributor_role_id
  principal_id        = azurerm_linux_function_app.user.identity[0].principal_id
  scope               = azurerm_cosmosdb_account.main.id
}

resource "azurerm_cosmosdb_sql_role_assignment" "inventory" {
  resource_group_name = data.azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  role_definition_id  = local.cosmos_data_contributor_role_id
  principal_id        = azurerm_linux_function_app.inventory.identity[0].principal_id
  scope               = azurerm_cosmosdb_account.main.id
}

resource "azurerm_cosmosdb_sql_role_assignment" "match" {
  resource_group_name = data.azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  role_definition_id  = local.cosmos_data_contributor_role_id
  principal_id        = azurerm_linux_function_app.match.identity[0].principal_id
  scope               = azurerm_cosmosdb_account.main.id
}

# ---------------------------------------------------------------------------
# Event Grid — publish RBAC
# ---------------------------------------------------------------------------
# Only the match service publishes events. "EventGrid Data Sender" is the
# data-plane role for sending to a topic; scoped to the topic, nothing wider.
resource "azurerm_role_assignment" "match_eventgrid_sender" {
  scope                = azurerm_eventgrid_topic.main.id
  role_definition_name = "EventGrid Data Sender"
  principal_id         = azurerm_linux_function_app.match.identity[0].principal_id
}
