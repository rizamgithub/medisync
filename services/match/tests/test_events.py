"""Unit tests for the Event Grid event contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.events import (
    EmergencyRequestData,
    EventType,
    MatchFailedData,
    MatchFoundData,
    ReservationReleasedData,
)


def test_event_types_are_namespaced_pascal_case() -> None:
    assert EventType.EMERGENCY_REQUEST_CREATED.value == "MediSync.EmergencyRequestCreated"
    assert EventType.MATCH_FOUND.value == "MediSync.MatchFound"
    assert all(event.value.startswith("MediSync.") for event in EventType)


def test_emergency_request_data_round_trips() -> None:
    data = EmergencyRequestData.model_validate(
        {
            "request_id": "REQ-1",
            "hospital_id": "HOSP-1",
            "location": {"lat": 3.0, "lng": 101.0},
            "blood_type": "O-",
            "units": 2,
            "urgency": "Critical",
        }
    )
    assert EmergencyRequestData.model_validate(data.model_dump(mode="json")) == data


def test_emergency_request_data_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        EmergencyRequestData.model_validate(
            {
                "request_id": "REQ-1",
                "hospital_id": "HOSP-1",
                "location": {"lat": 3.0, "lng": 101.0},
                "blood_type": "O-",
                "units": 2,
                "urgency": "High",
                "leaked_field": "nope",
            }
        )


def test_match_found_data_fields() -> None:
    data = MatchFoundData(request_id="REQ-1", inventory_id="INV-1", hospital_id="HOSP-1")
    assert data.model_dump() == {
        "request_id": "REQ-1",
        "inventory_id": "INV-1",
        "hospital_id": "HOSP-1",
    }


def test_failed_and_released_data_construct() -> None:
    assert MatchFailedData(request_id="REQ-1", reason="no stock").reason == "no stock"
    released = ReservationReleasedData(
        request_id="REQ-1", inventory_id="INV-1", reason="reserve timeout"
    )
    assert released.inventory_id == "INV-1"
