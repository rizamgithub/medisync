"""Unit tests for geohash encoding and haversine distance."""

from __future__ import annotations

from app.geo import GEOHASH_PRECISION, GEOHASH_PREFIX_LEN, encode, haversine_km


def test_encode_known_reference_vector() -> None:
    # Canonical example: (42.6, -5.6) → "ezs42" at precision 5.
    assert encode(42.6, -5.6, 5) == "ezs42"


def test_encode_longer_reference_vector() -> None:
    # (57.64911, 10.40744) → "u4pruydqqvj"; first 9 chars at precision 9.
    assert encode(57.64911, 10.40744, 9) == "u4pruydqq"


def test_encode_default_precision_length() -> None:
    assert len(encode(3.04, 101.45)) == GEOHASH_PRECISION


def test_geohash_prefix_property() -> None:
    # encode(.., 5) must equal the first 5 chars of the full-precision hash.
    full = encode(42.6, -5.6)
    assert full[:GEOHASH_PREFIX_LEN] == encode(42.6, -5.6, GEOHASH_PREFIX_LEN)


def test_haversine_zero_distance() -> None:
    assert haversine_km(3.04, 101.45, 3.04, 101.45) == 0.0


def test_haversine_one_degree_latitude() -> None:
    # One degree of latitude is ~111.19 km anywhere on the globe.
    assert abs(haversine_km(0.0, 0.0, 1.0, 0.0) - 111.19) < 0.5


def test_haversine_is_symmetric() -> None:
    a = haversine_km(3.0, 101.0, 3.5, 101.6)
    b = haversine_km(3.5, 101.6, 3.0, 101.0)
    assert a == b
