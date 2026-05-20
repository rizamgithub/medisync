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
# Containers — one per core entity
# ---------------------------------------------------------------------------
# WARNING: a container's partition key is IMMUTABLE. Changing `partition_key_paths`
# forces Terraform to destroy and recreate the container (losing its data).
# Pick deliberately. See runbook 06 "Concepts" for the rationale below.

# Donors — partitioned by blood type. The dominant query in matching is
# "find available donors of blood type X". Trade-off: ABO/Rh has only 8 values
# (low cardinality), so this risks hot partitions at very large scale.
# Acceptable for Phase 1 / portfolio scale; flagged in the runbook.
resource "azurerm_cosmosdb_sql_container" "donors" {
  name                = "donors"
  resource_group_name = data.azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/bloodType"]
}

# Requests — also partitioned by blood type, for the same matching query path.
resource "azurerm_cosmosdb_sql_container" "requests" {
  name                = "requests"
  resource_group_name = data.azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/bloodType"]
}

# Matches — partitioned by the request they belong to. Reads are almost always
# "all matches for request X", which then stay single-partition.
resource "azurerm_cosmosdb_sql_container" "matches" {
  name                = "matches"
  resource_group_name = data.azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/requestId"]
}
