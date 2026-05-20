# Azure Functions — Python 3.12 on a Linux Consumption (Y1) plan.
# One Function App per bounded context (user / inventory / match). They share
# one consumption plan, one storage account, and one Application Insights so
# the cross-service Application Map shows the whole Saga end to end.
#
# PREREQUISITE: register Microsoft.Web, Microsoft.Insights and
# Microsoft.OperationalInsights as Global Admin before `terraform apply`
# (runbook 09, Step 1). Microsoft.Storage / Microsoft.DocumentDB were already
# registered in runbooks 07 / 06.

# ---------------------------------------------------------------------------
# Shared platform — observability
# ---------------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "main" {
  name                = "${local.name_prefix}-logs"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30 # first 5 GB/month is free
  tags                = local.common_tags
}

# One workspace-based Application Insights, shared by all three Function Apps,
# so the end-to-end transaction view spans the whole match Saga (context.md §8).
resource "azurerm_application_insights" "main" {
  name                = "${local.name_prefix}-appi"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  application_type    = "web"
  workspace_id        = azurerm_log_analytics_workspace.main.id
  tags                = local.common_tags
}

# ---------------------------------------------------------------------------
# Shared platform — storage account + consumption plan
# ---------------------------------------------------------------------------
# One storage account backs all three Function Apps (runtime state plus the
# match service's Durable Functions task hub). Billed per use — idle cost is
# negligible. Reuses the random suffix minted in cosmos.tf.
resource "azurerm_storage_account" "functions" {
  name                     = "${var.project_name}func${random_string.suffix.result}"
  resource_group_name      = data.azurerm_resource_group.main.name
  location                 = data.azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  tags                     = local.common_tags
}

# Y1 = the Linux Consumption SKU: scales to zero, 1M free executions/month.
resource "azurerm_service_plan" "functions" {
  name                = "${local.name_prefix}-func-plan"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "Y1"
  tags                = local.common_tags
}

# ---------------------------------------------------------------------------
# App settings shared by every Function App
# ---------------------------------------------------------------------------
locals {
  common_app_settings = {
    ENV                                   = var.environment
    LOG_LEVEL                             = "INFO"
    COSMOS_ENDPOINT                       = azurerm_cosmosdb_account.main.endpoint
    APPLICATIONINSIGHTS_CONNECTION_STRING = azurerm_application_insights.main.connection_string
  }
}

# ---------------------------------------------------------------------------
# Function App — user service
# ---------------------------------------------------------------------------
resource "azurerm_linux_function_app" "user" {
  name                       = "${local.name_prefix}-user-func-${random_string.suffix.result}"
  resource_group_name        = data.azurerm_resource_group.main.name
  location                   = data.azurerm_resource_group.main.location
  service_plan_id            = azurerm_service_plan.functions.id
  storage_account_name       = azurerm_storage_account.functions.name
  storage_account_access_key = azurerm_storage_account.functions.primary_access_key
  https_only                 = true

  # System-assigned identity — the app authenticates to Cosmos as itself
  # (context.md §4); the data-plane role is granted in identity.tf.
  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      python_version = "3.12"
    }
  }

  app_settings = merge(local.common_app_settings, {
    SERVICE_NAME          = "user"
    COSMOS_USER_DB        = azurerm_cosmosdb_sql_database.main.name
    COSMOS_USER_CONTAINER = azurerm_cosmosdb_sql_container.profiles.name
  })

  # `func azure functionapp publish` deploys code via run-from-package and
  # adds WEBSITE_RUN_FROM_PACKAGE itself — ignore it so it is not flagged as
  # drift on the next plan.
  lifecycle {
    ignore_changes = [app_settings["WEBSITE_RUN_FROM_PACKAGE"]]
  }

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Function App — inventory service
# ---------------------------------------------------------------------------
resource "azurerm_linux_function_app" "inventory" {
  name                       = "${local.name_prefix}-inventory-func-${random_string.suffix.result}"
  resource_group_name        = data.azurerm_resource_group.main.name
  location                   = data.azurerm_resource_group.main.location
  service_plan_id            = azurerm_service_plan.functions.id
  storage_account_name       = azurerm_storage_account.functions.name
  storage_account_access_key = azurerm_storage_account.functions.primary_access_key
  https_only                 = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      python_version = "3.12"
    }
  }

  app_settings = merge(local.common_app_settings, {
    SERVICE_NAME               = "inventory"
    COSMOS_INVENTORY_DB        = azurerm_cosmosdb_sql_database.main.name
    COSMOS_INVENTORY_CONTAINER = azurerm_cosmosdb_sql_container.inventory.name
  })

  lifecycle {
    ignore_changes = [app_settings["WEBSITE_RUN_FROM_PACKAGE"]]
  }

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Function App — match service (Durable Functions Saga)
# ---------------------------------------------------------------------------
resource "azurerm_linux_function_app" "match" {
  name                       = "${local.name_prefix}-match-func-${random_string.suffix.result}"
  resource_group_name        = data.azurerm_resource_group.main.name
  location                   = data.azurerm_resource_group.main.location
  service_plan_id            = azurerm_service_plan.functions.id
  storage_account_name       = azurerm_storage_account.functions.name
  storage_account_access_key = azurerm_storage_account.functions.primary_access_key
  https_only                 = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      python_version = "3.12"
    }
  }

  app_settings = merge(local.common_app_settings, {
    SERVICE_NAME             = "match"
    COSMOS_REQUEST_DB        = azurerm_cosmosdb_sql_database.main.name
    COSMOS_REQUEST_CONTAINER = azurerm_cosmosdb_sql_container.requests.name
    EVENTGRID_TOPIC_ENDPOINT = azurerm_eventgrid_topic.main.endpoint
    # Match calls the inventory service over HTTP — never its database.
    INVENTORY_API_BASE_URL = "https://${azurerm_linux_function_app.inventory.default_hostname}"
  })

  lifecycle {
    ignore_changes = [app_settings["WEBSITE_RUN_FROM_PACKAGE"]]
  }

  tags = local.common_tags
}
