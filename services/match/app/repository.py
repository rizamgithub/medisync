"""Cosmos DB data access for match requests.

Auth uses ``DefaultAzureCredential`` (context.md §3): a Managed Identity in
Azure, the developer's ``az login`` identity locally — no keys in code/config.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from azure.core import MatchConditions
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential

from app.config import get_settings
from app.models import MatchRecord, MatchStatus

log = logging.getLogger("medisync.match")


class MatchRecordNotFoundError(Exception):
    """Raised when a request id does not exist."""


class MatchRecordVersionConflictError(Exception):
    """Raised when an optimistic-concurrency (ETag) check fails."""


class MatchRepository:
    """Thin wrapper over the Cosmos `requests` container."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = CosmosClient(
            url=settings.cosmos_endpoint,
            credential=DefaultAzureCredential(),
        )
        database = self._client.get_database_client(settings.cosmos_db)
        self._container = database.get_container_client(settings.cosmos_container)

    def create(self, record: MatchRecord) -> MatchRecord:
        self._container.create_item(body=record.model_dump(mode="json"))
        log.info("match request created id=%s", record.id)
        return record

    def get(self, request_id: str) -> MatchRecord | None:
        try:
            raw = self._container.read_item(item=request_id, partition_key=request_id)
        except exceptions.CosmosResourceNotFoundError:
            return None
        return MatchRecord.model_validate(raw)

    def finalize(
        self,
        request_id: str,
        status: MatchStatus,
        *,
        inventory_id: str | None = None,
        reason: str | None = None,
    ) -> MatchRecord:
        """Write the Saga's final outcome onto the request, ETag-guarded."""
        try:
            raw = self._container.read_item(item=request_id, partition_key=request_id)
        except exceptions.CosmosResourceNotFoundError as exc:
            raise MatchRecordNotFoundError(request_id) from exc

        updated = MatchRecord.model_validate(raw).with_status(
            status, matched_inventory_id=inventory_id, failure_reason=reason
        )
        try:
            self._container.replace_item(
                item=request_id,
                body=updated.model_dump(mode="json"),
                etag=raw["_etag"],
                match_condition=MatchConditions.IfNotModified,
            )
        except exceptions.CosmosAccessConditionFailedError as exc:
            raise MatchRecordVersionConflictError(request_id) from exc
        log.info("match request finalized id=%s status=%s", request_id, status.value)
        return updated


@lru_cache(maxsize=1)
def get_repository() -> MatchRepository:
    """Process-wide singleton — reuses one Cosmos client across invocations."""
    return MatchRepository()
