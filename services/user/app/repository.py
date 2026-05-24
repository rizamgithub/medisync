"""Cosmos DB data access for user profiles.

Auth uses ``DefaultAzureCredential`` (context.md §3): a Managed Identity in
Azure, the developer's ``az login`` identity locally. No connection strings
or account keys ever touch the code or config.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from azure.core import MatchConditions
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential

from app.config import get_settings
from app.models import Profile, ProfileUpdate

log = logging.getLogger("medisync.user")


class ProfileNotFoundError(Exception):
    """Raised when a profile id does not exist."""


class ProfileVersionConflictError(Exception):
    """Raised when an optimistic-concurrency (ETag) check fails."""


class ProfileRepository:
    """Thin wrapper over the Cosmos `profiles` container."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = CosmosClient(
            url=settings.cosmos_endpoint,
            credential=DefaultAzureCredential(),
        )
        database = self._client.get_database_client(settings.cosmos_db)
        self._container = database.get_container_client(settings.cosmos_container)

    def create(self, profile: Profile) -> Profile:
        self._container.create_item(body=profile.model_dump(mode="json"))
        log.info("profile created id=%s role=%s", profile.id, profile.role.value)
        return profile

    def get(self, profile_id: str) -> Profile | None:
        try:
            item = self._container.read_item(item=profile_id, partition_key=profile_id)
        except exceptions.CosmosResourceNotFoundError:
            return None
        return Profile.model_validate(item)

    def update(self, profile_id: str, changes: ProfileUpdate) -> Profile:
        """Read-modify-write guarded by an ETag If-Match (context.md §8).

        A concurrent writer changing the item between our read and write
        invalidates the ETag, surfacing as ``ProfileVersionConflictError``
        (HTTP 409) rather than a silent lost update.
        """
        try:
            item = self._container.read_item(item=profile_id, partition_key=profile_id)
        except exceptions.CosmosResourceNotFoundError as exc:
            raise ProfileNotFoundError(profile_id) from exc

        updated = Profile.model_validate(item).apply(changes)
        try:
            self._container.replace_item(
                item=profile_id,
                body=updated.model_dump(mode="json"),
                etag=item["_etag"],
                match_condition=MatchConditions.IfNotModified,
            )
        except exceptions.CosmosAccessConditionFailedError as exc:
            raise ProfileVersionConflictError(profile_id) from exc
        return updated


@lru_cache(maxsize=1)
def get_repository() -> ProfileRepository:
    """Process-wide singleton — reuses one Cosmos client across invocations."""
    return ProfileRepository()
