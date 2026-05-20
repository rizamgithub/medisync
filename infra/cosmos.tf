# Cosmos DB for NoSQL — serverless account, one database, per-entity containers.
#
# PREREQUISITE: the Microsoft.DocumentDB resource provider must be registered on
# the subscription before `terraform apply`. Our medisync-admin SP only has
# Contributor on rg-medisync-prod and cannot self-register providers — register
# it once as Global Admin. See runbook 06, Step 1.

# ---------------------------------------------------------------------------
# Globally-unique name suffix
# ---------------------------------------------------------------------------
# A Cosmos DB account name must be unique across *all* of Azure. "medisync-prod"
# would likely collide. This 6-char random suffix makes the name unique. It is
# generated once and kept stable in state, so the name never churns on re-apply.
# functions.tf will reuse this same suffix for the storage account later.
resource "random_string" "suffix" {
  length  = 6
  lower   = true
  upper   = false
  numeric = true
  special = false
}

# ---------------------------------------------------------------------------
# Cosmos DB account — serverless
# ---------------------------------------------------------------------------
resource "azurerm_cosmosdb_account" "main" {
  name                = "cosmos-${local.name_prefix}-${random_string.suffix.result}"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB" # NoSQL / Core (SQL) API

  # Serverless: no provisioned RU/s to pay for. Billed per request consumed
  # plus storage. Idle cost is genuinely $0 — the right fit for a portfolio
  # project. (Serverless and the free tier are mutually exclusive; serverless
  # wins here because free tier is provisioned-throughput only.)
  capabilities {
    name = "EnableServerless"
  }

  # Session consistency: the default, and the right trade-off for almost every
  # app — strong guarantees within a client session, cheaper than Strong.
  consistency_policy {
    consistency_level = "Session"
  }

  # Single region (no geo-replication) to keep cost and complexity down.
  geo_location {
    location          = data.azurerm_resource_group.main.location
    failover_priority = 0
  }

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# SQL database
# ---------------------------------------------------------------------------
resource "azurerm_cosmosdb_sql_database" "main" {
  name                = var.project_name
  resource_group_name = data.azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  # No `throughput` / `autoscale_settings`: serverless accounts bill per
  # request, so provisioned throughput cannot (and must not) be set here.
}

# ---------------------------------------------------------------------------
# Containers — one per service
# ---------------------------------------------------------------------------
# WARNING: a container's partition key is IMMUTABLE. Changing `partition_key_paths`
# forces Terraform to destroy and recreate the container (losing its data).
#
# These three containers replace the placeholder set from runbook 06 (donors,
# requests, matches — all guessed before the application code existed). The
# partition keys below are the ones the scaffolded services actually use; the
# first apply after this change destroys the old containers and creates these.

# Profiles — user service. Partition key /id: a profile is always read by its
# own id, giving even key distribution and single-RU point reads.
resource "azurerm_cosmosdb_sql_container" "profiles" {
  name                = "profiles"
  resource_group_name = data.azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/id"]
}

# Inventory — inventory service. Partition key /geohash_prefix: a region search
# resolves the 5-char geohash prefix and queries exactly one partition
# (context.md §8).
resource "azurerm_cosmosdb_sql_container" "inventory" {
  name                = "inventory"
  resource_group_name = data.azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/geohash_prefix"]
}

# Requests — match service. Partition key /id: the Saga orchestrator and the
# status endpoint both address a request by its id.
resource "azurerm_cosmosdb_sql_container" "requests" {
  name                = "requests"
  resource_group_name = data.azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/id"]
}
