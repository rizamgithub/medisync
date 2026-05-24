# Event Grid — one custom topic carries every MediSync domain event.
#
# PREREQUISITE: register Microsoft.EventGrid as Global Admin before
# `terraform apply` (runbook 09, Step 1).
#
# The match service publishes MediSync.EmergencyRequestCreated / MatchFound /
# MatchFailed / ReservationReleased to this topic (context.md §6). Two
# subscriptions route events back to functions:
#   * EmergencyRequestCreated -> match service's Durable starter (begins Saga)
#   * ReservationReleased     -> inventory service's compensation handler

resource "azurerm_eventgrid_topic" "main" {
  name                = "${local.name_prefix}-events"
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  # input_schema defaults to "EventGridSchema" — matches the EventGridEvent
  # objects sent by app/publisher.py in the match service.
  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Subscription: EmergencyRequestCreated -> match service Saga starter
# ---------------------------------------------------------------------------
# CHICKEN-AND-EGG: an Event Grid subscription to an Azure Function validates
# the endpoint at creation time, so the `on_emergency_request` function must
# already be DEPLOYED. The toggle keeps the first apply green:
#   1. first apply runs with enable_match_event_subscription = false,
#   2. `func azure functionapp publish` deploys the match service code,
#   3. flip the variable's default to true and apply again (runbook 09, Step 5).
resource "azurerm_eventgrid_event_subscription" "emergency_request_to_match" {
  count = var.enable_match_event_subscription ? 1 : 0

  name  = "emergency-request-created"
  scope = azurerm_eventgrid_topic.main.id

  included_event_types = ["MediSync.EmergencyRequestCreated"]

  azure_function_endpoint {
    function_id = "${azurerm_linux_function_app.match.id}/functions/on_emergency_request"
  }

  # Drop events that still fail after the retry window rather than letting an
  # undeliverable event keep retrying for the 24h default.
  retry_policy {
    max_delivery_attempts = 10
    event_time_to_live    = 60 # minutes
  }
}

# ---------------------------------------------------------------------------
# Subscription: ReservationReleased -> inventory service compensation handler
# ---------------------------------------------------------------------------
# Closes the match Saga's compensation loop: when the match service rolls back
# a reservation it publishes ReservationReleased, and the inventory service's
# `on_reservation_released` function flips that unit back to Available.
#
# Same chicken-and-egg as the subscription above — the function must be
# DEPLOYED before Event Grid can validate the endpoint, so it sits behind its
# own toggle (runbook 09, Step 5).
resource "azurerm_eventgrid_event_subscription" "reservation_released_to_inventory" {
  count = var.enable_inventory_event_subscription ? 1 : 0

  name  = "reservation-released"
  scope = azurerm_eventgrid_topic.main.id

  included_event_types = ["MediSync.ReservationReleased"]

  azure_function_endpoint {
    function_id = "${azurerm_linux_function_app.inventory.id}/functions/on_reservation_released"
  }

  retry_policy {
    max_delivery_attempts = 10
    event_time_to_live    = 60 # minutes
  }
}
