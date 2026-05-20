"""Durable Functions Saga for the match service (context.md §8).

Flow: an Event Grid ``MediSync.EmergencyRequestCreated`` event starts the
``match_orchestrator``, which drives the activities

    find_inventory → reserve_inventory → notify_parties → complete_match

If any step fails *after* a unit was reserved, the orchestrator compensates
by calling ``release_reservation`` (which publishes a
``MediSync.ReservationReleased`` event for auditability), then records the
failure on the request.

The orchestrator itself must be deterministic and free of I/O — every side
effect lives in an activity function.
"""

from __future__ import annotations

import logging
from typing import Any

import azure.durable_functions as df
import azure.functions as func

from app.events import (
    EventType,
    MatchFailedData,
    MatchFoundData,
    ReservationReleasedData,
)
from app.inventory_client import get_inventory_client
from app.matching import select_best_unit
from app.models import BloodType, MatchStatus
from app.publisher import get_publisher
from app.repository import get_repository

log = logging.getLogger("medisync.match")

bp = df.Blueprint()

ORCHESTRATOR_NAME = "match_orchestrator"
DEFAULT_SEARCH_RADIUS_KM = 25.0


@bp.event_grid_trigger(arg_name="event")
@bp.durable_client_input(client_name="client")
async def on_emergency_request(
    event: func.EventGridEvent, client: df.DurableOrchestrationClient
) -> None:
    """Event Grid starter — kicks off the Saga for each EmergencyRequestCreated."""
    data = event.get_json()
    instance_id = await client.start_new(ORCHESTRATOR_NAME, client_input=data)
    log.info(
        "match Saga started instance=%s request=%s",
        instance_id,
        data.get("request_id"),
    )


@bp.orchestration_trigger(context_name="context")
def match_orchestrator(context: df.DurableOrchestrationContext):
    """The Saga orchestrator — deterministic; all I/O happens in activities."""
    request: dict[str, Any] = context.get_input()
    request_id = request["request_id"]
    reserved_inventory_id: str | None = None

    try:
        unit = yield context.call_activity("find_inventory", request)
        if unit is None:
            yield context.call_activity(
                "complete_match",
                {
                    "request_id": request_id,
                    "status": MatchStatus.NO_MATCH.value,
                    "reason": "no compatible stock within range",
                },
            )
            return {"request_id": request_id, "status": MatchStatus.NO_MATCH.value}

        yield context.call_activity("reserve_inventory", {"request": request, "unit": unit})
        reserved_inventory_id = unit["id"]

        yield context.call_activity("notify_parties", {"request": request, "unit": unit})
        yield context.call_activity(
            "complete_match",
            {
                "request_id": request_id,
                "status": MatchStatus.MATCHED.value,
                "inventory_id": reserved_inventory_id,
            },
        )
        return {
            "request_id": request_id,
            "status": MatchStatus.MATCHED.value,
            "inventory_id": reserved_inventory_id,
        }
    except Exception as exc:
        # Saga compensation path: undo the reservation if one was made.
        reason = str(exc) or exc.__class__.__name__
        if reserved_inventory_id is not None:
            yield context.call_activity(
                "release_reservation",
                {
                    "request_id": request_id,
                    "inventory_id": reserved_inventory_id,
                    "reason": reason,
                },
            )
        yield context.call_activity(
            "complete_match",
            {
                "request_id": request_id,
                "status": MatchStatus.FAILED.value,
                "reason": reason,
            },
        )
        return {
            "request_id": request_id,
            "status": MatchStatus.FAILED.value,
            "reason": reason,
        }


@bp.activity_trigger(input_name="request")
def find_inventory(request: dict[str, Any]) -> dict[str, Any] | None:
    """Query the inventory service and pick the nearest compatible unit."""
    location = request["location"]
    units = get_inventory_client().find_available(
        lat=location["lat"],
        lng=location["lng"],
        radius_km=DEFAULT_SEARCH_RADIUS_KM,
    )
    return select_best_unit(BloodType(request["blood_type"]), units)


@bp.activity_trigger(input_name="payload")
def reserve_inventory(payload: dict[str, Any]) -> dict[str, Any]:
    """Reserve the chosen unit via the inventory service (raises on a 409)."""
    request, unit = payload["request"], payload["unit"]
    return get_inventory_client().reserve(
        item_id=unit["id"],
        geohash_prefix=unit["geohash_prefix"],
        request_id=request["request_id"],
    )


@bp.activity_trigger(input_name="payload")
def notify_parties(payload: dict[str, Any]) -> None:
    """Publish MatchFound and notify the hospital."""
    request, unit = payload["request"], payload["unit"]
    get_publisher().publish(
        EventType.MATCH_FOUND,
        subject=f"requests/{request['request_id']}",
        data=MatchFoundData(
            request_id=request["request_id"],
            inventory_id=unit["id"],
            hospital_id=request["hospital_id"],
        ),
    )
    # TODO(acs-email): send the hospital a confirmation email via Azure
    # Communication Services — pending the ACS Email domain runbook.


@bp.activity_trigger(input_name="payload")
def complete_match(payload: dict[str, Any]) -> None:
    """Persist the final Saga outcome; emit MatchFailed when unsuccessful."""
    status = MatchStatus(payload["status"])
    get_repository().finalize(
        payload["request_id"],
        status,
        inventory_id=payload.get("inventory_id"),
        reason=payload.get("reason"),
    )
    if status in (MatchStatus.FAILED, MatchStatus.NO_MATCH):
        get_publisher().publish(
            EventType.MATCH_FAILED,
            subject=f"requests/{payload['request_id']}",
            data=MatchFailedData(
                request_id=payload["request_id"],
                reason=payload.get("reason") or status.value,
            ),
        )


@bp.activity_trigger(input_name="payload")
def release_reservation(payload: dict[str, Any]) -> None:
    """Saga compensation — publish ReservationReleased for auditability.

    The inventory service should subscribe to this event to flip the unit
    back to Available (TODO: inventory-side ReservationReleased handler).
    """
    get_publisher().publish(
        EventType.RESERVATION_RELEASED,
        subject=f"requests/{payload['request_id']}",
        data=ReservationReleasedData(
            request_id=payload["request_id"],
            inventory_id=payload["inventory_id"],
            reason=payload["reason"],
        ),
    )
