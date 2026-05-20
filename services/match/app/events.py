"""Event Grid event contracts for MediSync (context.md §6).

These Pydantic models type the ``data`` payload of each custom Event Grid
event. Event types are namespaced + PascalCase past-tense per context.md §6.

NOTE: when the user/inventory services start producing or consuming events
too, these schemas should move to a shared ``packages/shared/`` package
(context.md §5, §9). They are kept local to the match service for now — it is
the only event producer/consumer so far.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models import BloodType, GeoLocation, Urgency

EVENT_DATA_VERSION = "1.0"


class EventType(StrEnum):
    EMERGENCY_REQUEST_CREATED = "MediSync.EmergencyRequestCreated"
    MATCH_FOUND = "MediSync.MatchFound"
    MATCH_FAILED = "MediSync.MatchFailed"
    RESERVATION_RELEASED = "MediSync.ReservationReleased"


class EmergencyRequestData(BaseModel):
    """``data`` of a ``MediSync.EmergencyRequestCreated`` event."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    hospital_id: str
    location: GeoLocation
    blood_type: BloodType
    units: int = Field(ge=1)
    urgency: Urgency


class MatchFoundData(BaseModel):
    """``data`` of a ``MediSync.MatchFound`` event."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    inventory_id: str
    hospital_id: str


class MatchFailedData(BaseModel):
    """``data`` of a ``MediSync.MatchFailed`` event."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    reason: str


class ReservationReleasedData(BaseModel):
    """``data`` of a ``MediSync.ReservationReleased`` event (Saga compensation)."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    inventory_id: str
    reason: str
