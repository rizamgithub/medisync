"""Pydantic v2 schemas for the MediSync match service.

A match request enters via ``POST /api/request/emergency`` and is stored in
the Cosmos `requests` container as a ``MatchRecord``; the Saga later updates
that record with its outcome.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


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


class MatchStatus(StrEnum):
    PENDING = "Pending"
    MATCHED = "Matched"
    NO_MATCH = "NoMatch"
    FAILED = "Failed"


class GeoLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)


class EmergencyRequestCreate(BaseModel):
    """Payload accepted by ``POST /api/request/emergency``."""

    model_config = ConfigDict(extra="forbid")

    hospital_id: str = Field(min_length=1, max_length=80)
    blood_type: BloodType
    units: int = Field(ge=1, le=100)
    urgency: Urgency = Urgency.HIGH
    location: GeoLocation


class MatchRecord(BaseModel):
    """A match request and its Saga outcome (Cosmos `requests` container).

    ``id`` (the request id) doubles as the partition key (``/id``): the
    orchestrator and the status endpoint both address a request by its id.
    ``extra="ignore"`` lets ``model_validate`` accept Cosmos system fields.
    """

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: uuid4().hex)
    hospital_id: str
    blood_type: BloodType
    units: int
    urgency: Urgency
    location: GeoLocation
    status: MatchStatus = MatchStatus.PENDING
    matched_inventory_id: str | None = None
    failure_reason: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @classmethod
    def from_request(cls, req: EmergencyRequestCreate) -> MatchRecord:
        now = _utcnow()
        return cls(
            hospital_id=req.hospital_id,
            blood_type=req.blood_type,
            units=req.units,
            urgency=req.urgency,
            location=req.location,
            created_at=now,
            updated_at=now,
        )

    def with_status(
        self,
        status: MatchStatus,
        *,
        matched_inventory_id: str | None = None,
        failure_reason: str | None = None,
    ) -> MatchRecord:
        """Return a copy with a new status/outcome and ``updated_at`` bumped."""
        return self.model_copy(
            update={
                "status": status,
                "matched_inventory_id": (
                    matched_inventory_id
                    if matched_inventory_id is not None
                    else self.matched_inventory_id
                ),
                "failure_reason": (
                    failure_reason if failure_reason is not None else self.failure_reason
                ),
                "updated_at": _utcnow(),
            }
        )
