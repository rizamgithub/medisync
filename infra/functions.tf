# Azure Functions — Python 3.12 consumption plan, one Function App per bounded context.
#
# Planned resources (not yet implemented):
#   - azurerm_storage_account.functions        (required by Functions runtime)
#   - azurerm_service_plan.consumption         (Y1 consumption SKU)
#   - azurerm_linux_function_app.api           (HTTP triggers)
#   - azurerm_linux_function_app.matcher       (Event Grid trigger)
#   - azurerm_linux_function_app.notifier      (Durable orchestration + ACS Email)
#
# Register before adding: Microsoft.Web, Microsoft.Storage
