"""HTTP routes for the MediSync inventory service (Azure Functions v2 blueprint).

Default ``/api`` prefix yields: ``/api/health``, ``/api/inventory`` (POST add,
GET region query), ``/api/inventory/{item_id}/reserve``.
"""

from __future__ import annotations

import json
import logging

import azure.functions as func
from pydantic import ValidationError

from app.geo import GEOHASH_PREFIX_LEN, encode, haversine_km
from app.models import InventoryCreate, InventoryItem, ReserveRequest
from app.repository import (
    InventoryNotAvailableError,
    InventoryNotFoundError,
    InventoryVersionConflictError,
    get_repository,
)

log = logging.getLogger("medisync.inventory")

bp = func.Blueprint()

_MAX_RADIUS_KM = 50.0


def _json(payload: object, status: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps(payload, default=str),
        status_code=status,
        mimetype="application/json",
    )


def _error(message: str, status: int, **extra: object) -> func.HttpResponse:
    return _json({"error": message, **extra}, status)


@bp.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Liveness probe — does not touch Cosmos."""
    return _json({"status": "ok", "service": "inventory"})


@bp.route(route="inventory", methods=["POST"])
def add_inventory(req: func.HttpRequest) -> func.HttpResponse:
    """Register a unit of stock; the geohash is computed from its location."""
    try:
        body = req.get_json()
    except ValueError:
        return _error("Request body must be valid JSON", 400)

    try:
        create_req = InventoryCreate.model_validate(body)
    except ValidationError as exc:
        return _error("Validation failed", 422, details=exc.errors(include_url=False))

    item = InventoryItem.from_create(create_req)
    get_repository().add(item)
    return _json(item.model_dump(mode="json"), 201)


@bp.route(route="inventory", methods=["GET"])
def query_inventory(req: func.HttpRequest) -> func.HttpResponse:
    """Find Available stock near a point.

    Query params: ``lat`` & ``lng`` (required), ``radius_km`` (default 5),
    ``sub_type`` (optional, e.g. ``O-``). Hits the one geohash-prefix
    partition, then filters by exact haversine distance.
    """
    try:
        lat = float(req.params["lat"])
        lng = float(req.params["lng"])
    except (KeyError, ValueError):
        return _error("Query params 'lat' and 'lng' are required numbers", 400)

    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return _error("'lat'/'lng' are out of range", 400)

    try:
        radius_km = float(req.params.get("radius_km", "5"))
    except ValueError:
        return _error("'radius_km' must be a number", 400)
    if not 0.0 < radius_km <= _MAX_RADIUS_KM:
        return _error(f"'radius_km' must be between 0 and {_MAX_RADIUS_KM}", 400)

    sub_type = req.params.get("sub_type")
    prefix = encode(lat, lng)[:GEOHASH_PREFIX_LEN]

    results: list[dict[str, object]] = []
    for item in get_repository().query_region(prefix, sub_type):
        distance = haversine_km(lat, lng, item.location.lat, item.location.lng)
        if distance <= radius_km:
            payload = item.model_dump(mode="json")
            payload["distance_km"] = round(distance, 3)
            results.append(payload)

    results.sort(key=lambda r: r["distance_km"])
    return _json({"count": len(results), "geohash_prefix": prefix, "items": results})


@bp.route(route="inventory/{item_id}/reserve", methods=["POST"])
def reserve_inventory(req: func.HttpRequest) -> func.HttpResponse:
    """Reserve a unit for a request — ETag-guarded Available → Reserved."""
    item_id = req.route_params["item_id"]

    try:
        body = req.get_json()
    except ValueError:
        return _error("Request body must be valid JSON", 400)

    try:
        reserve_req = ReserveRequest.model_validate(body)
    except ValidationError as exc:
        return _error("Validation failed", 422, details=exc.errors(include_url=False))

    try:
        item = get_repository().reserve(item_id, reserve_req.geohash_prefix, reserve_req.request_id)
    except InventoryNotFoundError:
        return _error("Inventory item not found", 404, item_id=item_id)
    except InventoryNotAvailableError as exc:
        return _error(f"Inventory item is not available ({exc})", 409, item_id=item_id)
    except InventoryVersionConflictError:
        return _error("Item was modified concurrently — retry", 409, item_id=item_id)

    return _json(item.model_dump(mode="json"))
