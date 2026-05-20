"""Unit tests for blood-type compatibility and inventory selection."""

from __future__ import annotations

from app.matching import compatible_donor_types, select_best_unit
from app.models import BloodType


def test_o_negative_recipient_accepts_only_o_negative() -> None:
    assert compatible_donor_types(BloodType.O_NEGATIVE) == frozenset({BloodType.O_NEGATIVE})


def test_ab_positive_recipient_is_universal() -> None:
    compatible = compatible_donor_types(BloodType.AB_POSITIVE)
    assert compatible == frozenset(BloodType)
    assert len(compatible) == 8


def test_a_positive_recipient_compatibility() -> None:
    assert compatible_donor_types(BloodType.A_POSITIVE) == frozenset(
        {
            BloodType.O_NEGATIVE,
            BloodType.O_POSITIVE,
            BloodType.A_NEGATIVE,
            BloodType.A_POSITIVE,
        }
    )


def test_o_negative_is_universal_donor() -> None:
    # Every recipient can receive O- red cells.
    for recipient in BloodType:
        assert BloodType.O_NEGATIVE in compatible_donor_types(recipient)


def _unit(**overrides: object) -> dict:
    unit: dict = {
        "id": "INV-1",
        "sub_type": "O-",
        "status": "Available",
        "distance_km": 1.0,
    }
    unit.update(overrides)
    return unit


def test_select_best_unit_picks_only_compatible() -> None:
    units = [
        _unit(id="incompatible", sub_type="A+"),
        _unit(id="compatible", sub_type="O-"),
    ]
    chosen = select_best_unit(BloodType.O_NEGATIVE, units)
    assert chosen is not None and chosen["id"] == "compatible"


def test_select_best_unit_respects_distance_order() -> None:
    # Inventory is pre-sorted by distance; first compatible unit wins.
    units = [_unit(id="nearest", sub_type="O-"), _unit(id="farther", sub_type="O+")]
    chosen = select_best_unit(BloodType.AB_POSITIVE, units)
    assert chosen is not None and chosen["id"] == "nearest"


def test_select_best_unit_returns_none_when_incompatible() -> None:
    units = [_unit(sub_type="A+"), _unit(sub_type="B+")]
    assert select_best_unit(BloodType.O_NEGATIVE, units) is None


def test_select_best_unit_skips_non_available() -> None:
    units = [
        _unit(id="reserved", sub_type="O-", status="Reserved"),
        _unit(id="free", sub_type="O-", status="Available"),
    ]
    chosen = select_best_unit(BloodType.O_NEGATIVE, units)
    assert chosen is not None and chosen["id"] == "free"


def test_select_best_unit_handles_empty_inventory() -> None:
    assert select_best_unit(BloodType.O_POSITIVE, []) is None
