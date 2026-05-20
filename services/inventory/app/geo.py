"""Geohash encoding and great-circle distance — see context.md §8 (geo matching).

No external dependency: geohash is a short, well-known bit-interleaving
algorithm and haversine is a closed-form formula, so both are implemented
inline and unit-tested against known reference values (see tests/test_geo.py).
"""

from __future__ import annotations

import math

GEOHASH_PRECISION = 9  # full hash — a ~4.8 m cell
GEOHASH_PREFIX_LEN = 5  # ~4.9 km cell — used as the Cosmos partition key

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
_BITS = (16, 8, 4, 2, 1)
_EARTH_RADIUS_KM = 6371.0088  # mean Earth radius (IUGG)


def encode(lat: float, lng: float, precision: int = GEOHASH_PRECISION) -> str:
    """Encode a coordinate to a geohash of the given character precision.

    Geohash has the prefix property: ``encode(lat, lng, 5)`` always equals
    ``encode(lat, lng, 9)[:5]``, which is why a 5-char prefix can serve as a
    coarse spatial bucket / partition key.
    """
    lat_lo, lat_hi = -90.0, 90.0
    lng_lo, lng_hi = -180.0, 180.0
    out: list[str] = []
    even = True
    bit = 0
    ch = 0
    while len(out) < precision:
        if even:
            mid = (lng_lo + lng_hi) / 2
            if lng > mid:
                ch |= _BITS[bit]
                lng_lo = mid
            else:
                lng_hi = mid
        else:
            mid = (lat_lo + lat_hi) / 2
            if lat > mid:
                ch |= _BITS[bit]
                lat_lo = mid
            else:
                lat_hi = mid
        even = not even
        if bit < 4:
            bit += 1
        else:
            out.append(_BASE32[ch])
            bit = 0
            ch = 0
    return "".join(out)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two coordinates, in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))
