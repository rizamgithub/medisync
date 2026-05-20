"""MediSync match service — Azure Functions Python v2 entry point.

Responsibility: emergency match requests and the **Durable Functions Saga**
that finds, reserves, notifies and completes a match (with compensation on
failure). Uses ``df.DFApp`` so the durable orchestration/activity decorators
are available.

HTTP auth level is ANONYMOUS by design — request authorization belongs to
Entra External ID JWT validation (context.md §8), wired in a later runbook.
"""

from __future__ import annotations

import azure.durable_functions as df
import azure.functions as func

from app.routes import bp as http_bp
from app.saga import bp as saga_bp
from app.telemetry import configure_telemetry

configure_telemetry()

app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)
app.register_blueprint(http_bp)
app.register_blueprint(saga_bp)
