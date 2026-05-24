"""HTTP routes for the MediSync user service (Azure Functions v2 blueprint).

Routes are grouped in a ``func.Blueprint`` and registered by ``function_app.py``.
The default ``/api`` prefix yields: ``/api/health``, ``/api/auth/signup``,
``/api/users/{user_id}``.
"""

from __future__ import annotations

import json
import logging

import azure.functions as func
from pydantic import ValidationError

from app.models import Profile, ProfileUpdate, SignupRequest
from app.repository import (
    ProfileNotFoundError,
    ProfileVersionConflictError,
    get_repository,
)

log = logging.getLogger("medisync.user")

bp = func.Blueprint()


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
    return _json({"status": "ok", "service": "user"})


@bp.route(route="auth/signup", methods=["POST"])
def signup(req: func.HttpRequest) -> func.HttpResponse:
    """Register a Hospital, Donor, Courier or Doctor.

    TODO(entra): once the Entra External ID tenant exists (future runbook),
    create the directory user here and trust the verified email from the
    OIDC token instead of the request body. See context.md §8 (RBAC).
    """
    try:
        body = req.get_json()
    except ValueError:
        return _error("Request body must be valid JSON", 400)

    try:
        signup_req = SignupRequest.model_validate(body)
    except ValidationError as exc:
        return _error("Validation failed", 422, details=exc.errors(include_url=False))

    profile = Profile.from_signup(signup_req)
    get_repository().create(profile)
    return _json(profile.model_dump(mode="json"), 201)


@bp.route(route="users/{user_id}", methods=["GET"])
def get_user(req: func.HttpRequest) -> func.HttpResponse:
    """Fetch a single profile by id."""
    user_id = req.route_params["user_id"]
    profile = get_repository().get(user_id)
    if profile is None:
        return _error("Profile not found", 404, user_id=user_id)
    return _json(profile.model_dump(mode="json"))


@bp.route(route="users/{user_id}", methods=["PATCH"])
def update_user(req: func.HttpRequest) -> func.HttpResponse:
    """Apply a partial update (e.g. a Donor toggling availability)."""
    user_id = req.route_params["user_id"]

    try:
        body = req.get_json()
    except ValueError:
        return _error("Request body must be valid JSON", 400)

    try:
        changes = ProfileUpdate.model_validate(body)
    except ValidationError as exc:
        return _error("Validation failed", 422, details=exc.errors(include_url=False))

    if changes.is_empty():
        return _error("Request body contains no updatable fields", 400)

    try:
        profile = get_repository().update(user_id, changes)
    except ProfileNotFoundError:
        return _error("Profile not found", 404, user_id=user_id)
    except ProfileVersionConflictError:
        return _error("Profile was modified concurrently — retry", 409, user_id=user_id)

    return _json(profile.model_dump(mode="json"))
