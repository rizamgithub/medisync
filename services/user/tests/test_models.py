"""Unit tests for the user-service Pydantic schemas (no Azure dependencies)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import BloodType, Profile, ProfileUpdate, Role, SignupRequest


def _donor_signup(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "email": "donor@example.com",
        "display_name": "Aisha Donor",
        "role": "Donor",
        "blood_type": "O-",
        "location": {"lat": 3.04, "lng": 101.45},
    }
    data.update(overrides)
    return data


def test_donor_signup_requires_blood_type() -> None:
    with pytest.raises(ValidationError, match="blood_type is required"):
        SignupRequest.model_validate(_donor_signup(blood_type=None))


def test_non_donor_rejects_blood_type() -> None:
    with pytest.raises(ValidationError, match="blood_type may only be set"):
        SignupRequest.model_validate(_donor_signup(role="Hospital", blood_type="O-"))


def test_hospital_signup_ok_without_blood_type() -> None:
    req = SignupRequest.model_validate(
        {
            "email": "ward@hospital.org",
            "display_name": "Klang General",
            "role": "Hospital",
        }
    )
    assert req.role is Role.HOSPITAL
    assert req.blood_type is None


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SignupRequest.model_validate(_donor_signup(is_admin=True))


def test_geo_bounds_are_enforced() -> None:
    with pytest.raises(ValidationError):
        SignupRequest.model_validate(_donor_signup(location={"lat": 999, "lng": 0}))


def test_profile_from_signup_marks_donor_available() -> None:
    profile = Profile.from_signup(SignupRequest.model_validate(_donor_signup()))
    assert profile.role is Role.DONOR
    assert profile.blood_type is BloodType.O_NEGATIVE
    assert profile.is_available is True
    assert profile.id  # uuid generated
    assert profile.created_at == profile.updated_at


def test_profile_from_signup_hospital_not_available() -> None:
    req = SignupRequest.model_validate(
        {"email": "ops@hospital.org", "display_name": "Klang General", "role": "Hospital"}
    )
    assert Profile.from_signup(req).is_available is False


def test_profile_apply_update_bumps_timestamp() -> None:
    profile = Profile.from_signup(SignupRequest.model_validate(_donor_signup()))
    updated = profile.apply(ProfileUpdate(is_available=False))
    assert updated.is_available is False
    assert updated.updated_at >= profile.updated_at
    assert updated.id == profile.id
    assert updated.created_at == profile.created_at


def test_profile_tolerates_cosmos_system_fields() -> None:
    profile = Profile.from_signup(SignupRequest.model_validate(_donor_signup()))
    raw = profile.model_dump(mode="json")
    raw.update({"_etag": '"abc"', "_rid": "xyz", "_ts": 1717000000})
    assert Profile.model_validate(raw).id == profile.id


def test_profile_update_empty_detection() -> None:
    assert ProfileUpdate().is_empty() is True
    assert ProfileUpdate(is_available=True).is_empty() is False
