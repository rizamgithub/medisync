"""Unit tests for the match-service Pydantic schemas (no Azure deps)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import (
    BloodType,
    EmergencyRequestCreate,
    MatchRecord,
    MatchStatus,
    Urgency,
)


def _request(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "hospital_id": "HOSP-01",
        "blood_type": "AB-",
        "units": 3,
        "urgency": "Critical",
        "location": {"lat": 3.04, "lng": 101.45},
    }
    data.update(overrides)
    return data


def test_emergency_request_parses() -> None:
    req = EmergencyRequestCreate.model_validate(_request())
    assert req.blood_type is BloodType.AB_NEGATIVE
    assert req.urgency is Urgency.CRITICAL
    assert req.units == 3


def test_units_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        EmergencyRequestCreate.model_validate(_request(units=0))


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EmergencyRequestCreate.model_validate(_request(patient_name="Aisha"))


def test_urgency_defaults_to_high() -> None:
    data = _request()
    del data["urgency"]
    assert EmergencyRequestCreate.model_validate(data).urgency is Urgency.HIGH


def test_match_record_from_request_starts_pending() -> None:
    record = MatchRecord.from_request(EmergencyRequestCreate.model_validate(_request()))
    assert record.status is MatchStatus.PENDING
    assert record.matched_inventory_id is None
    assert record.failure_reason is None
    assert record.id
    assert record.created_at == record.updated_at


def test_match_record_with_status_matched() -> None:
    record = MatchRecord.from_request(EmergencyRequestCreate.model_validate(_request()))
    done = record.with_status(MatchStatus.MATCHED, matched_inventory_id="INV-9")
    assert done.status is MatchStatus.MATCHED
    assert done.matched_inventory_id == "INV-9"
    assert done.updated_at >= record.updated_at
    assert done.id == record.id
    assert done.created_at == record.created_at


def test_match_record_with_status_failed_keeps_reason() -> None:
    record = MatchRecord.from_request(EmergencyRequestCreate.model_validate(_request()))
    done = record.with_status(MatchStatus.FAILED, failure_reason="reserve 409")
    assert done.status is MatchStatus.FAILED
    assert done.failure_reason == "reserve 409"


def test_match_record_tolerates_cosmos_system_fields() -> None:
    record = MatchRecord.from_request(EmergencyRequestCreate.model_validate(_request()))
    raw = record.model_dump(mode="json")
    raw.update({"_etag": '"abc"', "_rid": "xyz", "_ts": 1717000000})
    assert MatchRecord.model_validate(raw).id == record.id
