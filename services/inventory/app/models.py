"""Pydantic v2 schemas for the MediSync inventory service.

An inventory item is a single unit of blood or an organ held at a hospital.
Items are stored in the Cosmos `inventory` container partitioned by
``geohash_prefix`` so a region query hits exactly one partition (context.md §8).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.geo import GEOHASH_PREFIX_LEN, encode


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ItemType(StrEnum):
    BLOOD = "Blood"
    ORGAN = "Organ"


class InventoryStatus(StrEnum):
    AVAILABLE = "Available"
    RESERVED = "Reserved"
    DISPATCHED = "Dispatched"


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


class InventoryCreate(BaseModel):
    """Payload accepted by ``POST /api/inventory``."""

    model_config = ConfigDict(extra="forbid")

    hospital_id: str = Field(min_length=1, max_length=80)
    item_type: ItemType
    sub_type: str = Field(min_length=2, max_length=40)
    expiry_date: date
    location: GeoLocation

    @field_validator("expiry_date")
    @classmethod
    def _not_already_expired(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("expiry_date is in the past")
        return value

    @model_validator(mode="after")
    def _sub_type_matches_item_type(self) -> InventoryCreate:
        if self.item_type is ItemType.BLOOD:
            valid = sorted(bt.value for bt in BloodType)
            if self.sub_type not in valid:
                raise ValueError(f"sub_type for Blood must be one of {valid}")
        return self


class ReserveRequest(BaseModel):
    """Payload accepted by ``POST /api/inventory/{item_id}/reserve``.

    ``geohash_prefix`` is the item's Cosmos partition key — the caller (the
    match service) already has it from the region-query response, so passing
    it back enables a single-partition point read instead of a fan-out.
    """

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=80)
    geohash_prefix: str = Field(min_length=GEOHASH_PREFIX_LEN, max_length=GEOHASH_PREFIX_LEN)


class InventoryItem(BaseModel):
    """An inventory unit as stored in the Cosmos `inventory` container.

    ``extra="ignore"`` lets ``model_validate`` accept Cosmos system fields
    (``_etag``, ``_rid``, ``_ts``) on read.
    """

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: uuid4().hex)
    hospital_id: str
    item_type: ItemType
    sub_type: str
    expiry_date: date
    status: InventoryStatus = InventoryStatus.AVAILABLE
    location: GeoLocation
    geohash: str
    geohash_prefix: str
    reserved_by: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @classmethod
    def from_create(cls, req: InventoryCreate) -> InventoryItem:
        gh = encode(req.location.lat, req.location.lng)
        now = _utcnow()
        return cls(
            hospital_id=req.hospital_id,
            item_type=req.item_type,
            sub_type=req.sub_type,
            expiry_date=req.expiry_date,
            location=req.location,
            geohash=gh,
            geohash_prefix=gh[:GEOHASH_PREFIX_LEN],
            created_at=now,
            updated_at=now,
        )

    def reserve(self, request_id: str) -> InventoryItem:
        """Return a copy transitioned Available → Reserved for ``request_id``."""
        return self.model_copy(
            update={
                "status": InventoryStatus.RESERVED,
                "reserved_by": request_id,
                "updated_at": _utcnow(),
            }
        )
