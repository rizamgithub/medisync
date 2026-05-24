"""Shared domain primitives for MediSync services.

These value types appear in the cross-service Event Grid contracts in
``events.py``, so they live in the shared package rather than in any single
service. Service-specific schemas (``MatchRecord``, ``InventoryItem``, …) stay
with their own service.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class BloodType(StrEnum):
    O_POSITIVE = "O+"
    O_NEGATIVE = "O-"
    A_POSITIVE = "A+"
    A_NEGATIVE = "A-"
    B_POSITIVE = "B+"
    B_NEGATIVE = "B-"
    AB_POSITIVE = "AB+"
    AB_NEGATIVE = "AB-"


class Urgency(StrEnum):
    CRITICAL = "Critical"
    HIGH = "High"
    STANDARD = "Standard"


class GeoLocation(BaseModel):
    """A WGS-84 latitude/longitude pair."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)
