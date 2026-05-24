"""Event Grid subscriber — the inventory side of the match Saga's compensation.

The match service publishes ``MediSync.ReservationReleased`` whenever it must
undo a reservation (a Saga step failed *after* a unit was reserved). This
handler reacts to that event and flips the unit back to ``Available`` so it can
be matched again — closing the Saga's compensation loop (context.md §6, §8).

Event Grid delivers **at-least-once**, so the handler is idempotent: a unit
already Available — or reserved by a different request — is left untouched
(``repository.release`` returns ``False``). A genuine ETag race raises
``InventoryVersionConflictError``; it is left to propagate so Event Grid
redelivers the event.
"""

from __future__ import annotations

import logging

import azure.functions as func
from pydantic import ValidationError

from app.repository import get_repository
from medisync_shared.events import ReservationReleasedData

log = logging.getLogger("medisync.inventory")

bp = func.Blueprint()


@bp.event_grid_trigger(arg_name="event")
def on_reservation_released(event: func.EventGridEvent) -> None:
    """Compensation handler — return a released unit to Available."""
    try:
        data = ReservationReleasedData.model_validate(event.get_json())
    except ValidationError:
        # A malformed event will never succeed on retry — drop it.
        log.exception("discarding malformed ReservationReleased event id=%s", event.id)
        return

    released = get_repository().release(
        item_id=data.inventory_id,
        geohash_prefix=data.geohash_prefix,
        request_id=data.request_id,
    )
    if released:
        log.info(
            "compensation: inventory %s returned to Available (request=%s reason=%s)",
            data.inventory_id,
            data.request_id,
            data.reason,
        )
    else:
        log.info(
            "compensation no-op: inventory %s not reserved by request %s",
            data.inventory_id,
            data.request_id,
        )
