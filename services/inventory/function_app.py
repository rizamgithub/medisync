"""MediSync inventory service — Azure Functions Python v2 entry point.

Responsibility: blood/organ stock units, geohash-bucketed region search, and
the ETag-guarded reserve transition consumed by the match service's Saga.

HTTP auth level is ANONYMOUS by design — request authorization belongs to
Entra External ID JWT validation (context.md §8), wired in a later runbook.
"""

from __future__ import annotations

import azure.functions as func

from app.routes import bp
from app.telemetry import configure_telemetry

configure_telemetry()

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
app.register_blueprint(bp)
