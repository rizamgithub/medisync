"""Pydantic v2 schemas for the MediSync user service.

These types are the I/O boundary for every HTTP handler (see context.md §3, §6)
and the on-disk shape of a profile in the Cosmos `profiles` container.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Role(StrEnum):
    """Entra External ID app roles — mirrors context.md §8 (RBAC)."""

    HOSPITAL = "Hospital"
    DONOR = "Donor"
    COURIER = "Courier"
    DOCTOR = "Doctor"


class BloodType(StrEnum):
    O_POSITIVE = "O+"
    O_NEGATIVE = "O-"
    A_POSITIVE = "A+"
    A_NEGATIVE = "A-"
    B_POSITIVE = "B+"
    B_NEGATIVE = "B-"
    AB_POSITIVE = "AB+"
    AB_NEGATIVE = "AB-"


class GeoLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)


class SignupRequest(BaseModel):
    """Payload accepted by ``POST /api/auth/signup``."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    role: Role
    blood_type: BloodType | None = None
    location: GeoLocation | None = None

    @model_validator(mode="after")
    def _blood_type_only_for_donors(self) -> SignupRequest:
        if self.role is Role.DONOR and self.blood_type is None:
            raise ValueError("blood_type is required when role is Donor")
        if self.role is not Role.DONOR and self.blood_type is not None:
            raise ValueError("blood_type may only be set when role is Donor")
        return self


class ProfileUpdate(BaseModel):
    """Partial update accepted by ``PATCH /api/users/{user_id}``.

    Every field is optional; only fields explicitly present in the request
    body are applied (``exclude_unset``), so omission never clears a value.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    location: GeoLocation | None = None
    is_available: bool | None = None

    def is_empty(self) -> bool:
        return not self.model_dump(exclude_unset=True)


class Profile(BaseModel):
    """A user profile as stored in the Cosmos `profiles` container.

    ``id`` doubles as the Cosmos partition key (``/id``): profiles are always
    read by their own id, so a per-item partition gives even key distribution
    and single-RU point reads. ``extra="ignore"`` lets ``model_validate``
    accept Cosmos system fields (``_etag``, ``_rid``, ``_ts``) on read.
    """

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: uuid4().hex)
    email: EmailStr
    display_name: str
    role: Role
    blood_type: BloodType | None = None
    location: GeoLocation | None = None
    is_available: bool = False
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @classmethod
    def from_signup(cls, req: SignupRequest) -> Profile:
        now = _utcnow()
        return cls(
            email=req.email,
            display_name=req.display_name,
            role=req.role,
            blood_type=req.blood_type,
            location=req.location,
            is_available=req.role is Role.DONOR,
            created_at=now,
            updated_at=now,
        )

    def apply(self, changes: ProfileUpdate) -> Profile:
        """Return a copy with ``changes`` applied and ``updated_at`` bumped."""
        patch = changes.model_dump(exclude_unset=True)
        return self.model_copy(update={**patch, "updated_at": _utcnow()})
