# Observability — Log Analytics workspace + Application Insights workspace-based.
#
# Planned resources (not yet implemented):
#   - azurerm_log_analytics_workspace.main     (PerGB2018, 30-day retention)
#   - azurerm_application_insights.main        (workspace_id => main)
#   - azurerm_monitor_diagnostic_setting.*     (per Function App, Cosmos)
#
# Register before adding: Microsoft.OperationalInsights, Microsoft.Insights
