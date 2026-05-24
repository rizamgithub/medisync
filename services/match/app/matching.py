"""Blood-type compatibility and inventory selection — pure domain logic.

Kept dependency-free and side-effect-free so the matching rules can be unit
tested directly (see tests/test_matching.py).
"""

from __future__ import annotations

from app.models import BloodType

# Recipient blood type -> donor blood types it can safely receive (red cells).
_COMPATIBLE_DONORS: dict[BloodType, frozenset[BloodType]] = {
    BloodType.O_NEGATIVE: frozenset({BloodType.O_NEGATIVE}),
    BloodType.O_POSITIVE: frozenset({BloodType.O_NEGATIVE, BloodType.O_POSITIVE}),
    BloodType.A_NEGATIVE: frozenset({BloodType.O_NEGATIVE, BloodType.A_NEGATIVE}),
    BloodType.A_POSITIVE: frozenset(
        {
            BloodType.O_NEGATIVE,
            BloodType.O_POSITIVE,
            BloodType.A_NEGATIVE,
            BloodType.A_POSITIVE,
        }
    ),
    BloodType.B_NEGATIVE: frozenset({BloodType.O_NEGATIVE, BloodType.B_NEGATIVE}),
    BloodType.B_POSITIVE: frozenset(
        {
            BloodType.O_NEGATIVE,
            BloodType.O_POSITIVE,
            BloodType.B_NEGATIVE,
            BloodType.B_POSITIVE,
        }
    ),
    BloodType.AB_NEGATIVE: frozenset(
        {
            BloodType.O_NEGATIVE,
            BloodType.A_NEGATIVE,
            BloodType.B_NEGATIVE,
            BloodType.AB_NEGATIVE,
        }
    ),
    BloodType.AB_POSITIVE: frozenset(BloodType),  # universal recipient
}


def compatible_donor_types(recipient: BloodType) -> frozenset[BloodType]:
    """Donor blood types a recipient can safely receive (red-cell compatibility)."""
    return _COMPATIBLE_DONORS[recipient]


def select_best_unit(recipient: BloodType, units: list[dict]) -> dict | None:
    """Pick the nearest Available, blood-compatible unit from an inventory result.

    ``units`` is the inventory service's region-query response — already
    filtered to Available stock and sorted ascending by ``distance_km`` — so
    the first compatible unit encountered is the nearest one.
    """
    compatible = {bt.value for bt in compatible_donor_types(recipient)}
    for unit in units:
        if unit.get("status") == "Available" and unit.get("sub_type") in compatible:
            return unit
    return None
