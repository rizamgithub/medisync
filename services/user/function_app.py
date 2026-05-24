"""MediSync user service — Azure Functions Python v2 entry point.

Responsibility: user profiles for Hospitals, Donors, Couriers and Doctors,
backed by the Cosmos DB `profiles` container.

HTTP auth level is ANONYMOUS by design — request authorization belongs to
Entra External ID JWT validation (context.md §8), wired in a later runbook;
Function host keys would be a misleading half-measure. See app/routes.py.
"""

from __future__ import annotations

import azure.functions as func

from app.routes import bp
from app.telemetry import configure_telemetry

configure_telemetry()

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
app.register_blueprint(bp)
