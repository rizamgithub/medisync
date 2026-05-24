"""MediSync shared package — cross-service domain types & event contracts.

Source of truth lives at ``packages/shared/``; a copy is vendored into each
Azure Function deploy bundle by ``scripts/sync-shared.ps1`` (see the package
README for why).
"""

from __future__ import annotations

from medisync_shared.domain import BloodType, GeoLocation, Urgency
from medisync_shared.events import (
    EVENT_DATA_VERSION,
    EmergencyRequestData,
    EventType,
    MatchFailedData,
    MatchFoundData,
    ReservationReleasedData,
)

__all__ = [
    "EVENT_DATA_VERSION",
    "BloodType",
    "EmergencyRequestData",
    "EventType",
    "GeoLocation",
    "MatchFailedData",
    "MatchFoundData",
    "ReservationReleasedData",
    "Urgency",
]
