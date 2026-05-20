"""Unit tests for the inventory-service Pydantic schemas (no Azure deps)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.geo import GEOHASH_PRECISION, GEOHASH_PREFIX_LEN
from app.models import (
    InventoryCreate,
    InventoryItem,
    InventoryStatus,
    ItemType,
    ReserveRequest,
)


def _blood_item(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "hospital_id": "HOSP-01",
        "item_type": "Blood",
        "sub_type": "O+",
        "expiry_date": "2099-01-01",
        "location": {"lat": 3.04, "lng": 101.45},
    }
    data.update(overrides)
    return data


def test_blood_item_accepts_valid_blood_type() -> None:
    req = InventoryCreate.model_validate(_blood_item(sub_type="AB-"))
    assert req.item_type is ItemType.BLOOD


def test_blood_item_rejects_non_blood_sub_type() -> None:
    with pytest.raises(ValidationError, match="sub_type for Blood"):
        InventoryCreate.model_validate(_blood_item(sub_type="Kidney"))


def test_organ_item_accepts_free_text_sub_type() -> None:
    req = InventoryCreate.model_validate(_blood_item(item_type="Organ", sub_type="Kidney"))
    assert req.item_type is ItemType.ORGAN


def test_expired_item_is_rejected() -> None:
    with pytest.raises(ValidationError, match="expiry_date is in the past"):
        InventoryCreate.model_validate(_blood_item(expiry_date="2000-01-01"))


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        InventoryCreate.model_validate(_blood_item(donor_name="Aisha"))


def test_from_create_computes_geohash_and_prefix() -> None:
    item = InventoryItem.from_create(InventoryCreate.model_validate(_blood_item()))
    assert len(item.geohash) == GEOHASH_PRECISION
    assert len(item.geohash_prefix) == GEOHASH_PREFIX_LEN
    assert item.geohash.startswith(item.geohash_prefix)
    assert item.status is InventoryStatus.AVAILABLE
    assert item.reserved_by is None
    assert item.created_at == item.updated_at


def test_reserve_transitions_status_and_bumps_timestamp() -> None:
    item = InventoryItem.from_create(InventoryCreate.model_validate(_blood_item()))
    reserved = item.reserve("REQ-42")
    assert reserved.status is InventoryStatus.RESERVED
    assert reserved.reserved_by == "REQ-42"
    assert reserved.updated_at >= item.updated_at
    assert reserved.id == item.id


def test_item_tolerates_cosmos_system_fields() -> None:
    item = InventoryItem.from_create(InventoryCreate.model_validate(_blood_item()))
    raw = item.model_dump(mode="json")
    raw.update({"_etag": '"abc"', "_rid": "xyz", "_ts": 1717000000})
    assert InventoryItem.model_validate(raw).id == item.id


def test_reserve_request_requires_exact_prefix_length() -> None:
    with pytest.raises(ValidationError):
        ReserveRequest.model_validate({"request_id": "REQ-1", "geohash_prefix": "abc"})
    ok = ReserveRequest.model_validate({"request_id": "REQ-1", "geohash_prefix": "w21z9"})
    assert ok.geohash_prefix == "w21z9"
