"""Optional Application Insights wiring via OpenTelemetry (context.md §8).

``configure_telemetry`` is a no-op when no connection string is set, so the
service runs identically in local dev and in tests without App Insights. It
reads the env var directly (not via ``app.config``) so importing the Function
app never depends on Cosmos configuration being present.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("medisync.inventory")

_configured = False


def configure_telemetry() -> None:
    """Enable Azure Monitor OpenTelemetry export if a connection string is set."""
    global _configured
    if _configured:
        return
    _configured = True

    conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn:
        log.info("Application Insights not configured — telemetry export disabled")
        return

    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(connection_string=conn)
    log.info("Application Insights telemetry enabled")
