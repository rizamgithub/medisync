"""HTTP client for the MediSync inventory service (service-to-service call).

The match service never touches the inventory Cosmos container directly —
service boundaries are respected (context.md §1, §6); it calls the inventory
service's HTTP API instead.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import httpx

from app.config import get_settings

log = logging.getLogger("medisync.match")

_TIMEOUT = httpx.Timeout(10.0)


class InventoryClient:
    """Calls the inventory service's region-query and reserve endpoints."""

    def __init__(self) -> None:
        self._base_url = get_settings().inventory_api_base_url.rstrip("/")

    def find_available(self, lat: float, lng: float, radius_km: float) -> list[dict]:
        """GET /api/inventory — Available stock near a point, nearest first."""
        resp = httpx.get(
            f"{self._base_url}/api/inventory",
            params={"lat": lat, "lng": lng, "radius_km": radius_km},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("items", [])

    def reserve(self, item_id: str, geohash_prefix: str, request_id: str) -> dict:
        """POST /api/inventory/{id}/reserve — raises on a 409 (already taken)."""
        resp = httpx.post(
            f"{self._base_url}/api/inventory/{item_id}/reserve",
            json={"request_id": request_id, "geohash_prefix": geohash_prefix},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()


@lru_cache(maxsize=1)
def get_inventory_client() -> InventoryClient:
    """Process-wide singleton."""
    return InventoryClient()
