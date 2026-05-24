"""Event Grid event contracts for MediSync (context.md §6).

These Pydantic models type the ``data`` payload of each custom Event Grid
event. Event types are namespaced + PascalCase past-tense per context.md §6.

This module is the single source of truth for the cross-service event schema.
It is **vendored** into each service's deploy bundle by
``scripts/sync-shared.ps1`` — see ``packages/shared/README.md``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from medisync_shared.domain import BloodType, GeoLocation, Urgency

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
    """``data`` of a ``MediSync.ReservationReleased`` event (Saga compensation).

    ``geohash_prefix`` is the released unit's Cosmos partition key. Carrying it
    on the event lets the inventory-side subscriber do a single-partition point
    read instead of a cross-partition scan to find the unit.
    """

    model_config = ConfigDict(extra="forbid")

    request_id: str
    inventory_id: str
    geohash_prefix: str
    reason: str
