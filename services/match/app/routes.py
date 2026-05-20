"""HTTP routes for the match service — emergency request submission & status.

Default ``/api`` prefix yields: ``/api/health``, ``/api/request/emergency``
(POST), ``/api/request/{request_id}`` (GET).

Submitting a request persists it and publishes a ``MediSync.EmergencyRequestCreated``
event; the Saga (see app/saga.py) reacts to that event asynchronously. The
HTTP caller gets ``202 Accepted`` immediately and polls the status endpoint.
"""

from __future__ import annotations

import json
import logging

import azure.functions as func
from pydantic import ValidationError

from app.events import EmergencyRequestData, EventType
from app.models import EmergencyRequestCreate, MatchRecord
from app.publisher import get_publisher
from app.repository import get_repository

log = logging.getLogger("medisync.match")

bp = func.Blueprint()


def _json(payload: object, status: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps(payload, default=str),
        status_code=status,
        mimetype="application/json",
    )


def _error(message: str, status: int, **extra: object) -> func.HttpResponse:
    return _json({"error": message, **extra}, status)


@bp.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Liveness probe — does not touch Cosmos."""
    return _json({"status": "ok", "service": "match"})


@bp.route(route="request/emergency", methods=["POST"])
def create_emergency_request(req: func.HttpRequest) -> func.HttpResponse:
    """Accept an emergency request, persist it, and publish the trigger event."""
    try:
        body = req.get_json()
    except ValueError:
        return _error("Request body must be valid JSON", 400)

    try:
        create_req = EmergencyRequestCreate.model_validate(body)
    except ValidationError as exc:
        return _error("Validation failed", 422, details=exc.errors(include_url=False))

    record = MatchRecord.from_request(create_req)
    get_repository().create(record)

    get_publisher().publish(
        EventType.EMERGENCY_REQUEST_CREATED,
        subject=f"requests/{record.id}",
        data=EmergencyRequestData(
            request_id=record.id,
            hospital_id=record.hospital_id,
            location=record.location,
            blood_type=record.blood_type,
            units=record.units,
            urgency=record.urgency,
        ),
    )
    return _json({"request_id": record.id, "status": record.status.value}, 202)


@bp.route(route="request/{request_id}", methods=["GET"])
def get_request(req: func.HttpRequest) -> func.HttpResponse:
    """Return a request and its current Saga outcome."""
    request_id = req.route_params["request_id"]
    record = get_repository().get(request_id)
    if record is None:
        return _error("Request not found", 404, request_id=request_id)
    return _json(record.model_dump(mode="json"))
