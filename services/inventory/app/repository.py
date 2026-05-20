"""Cosmos DB data access for inventory items.

Auth uses ``DefaultAzureCredential`` (context.md §3): a Managed Identity in
Azure, the developer's ``az login`` identity locally — no keys in code/config.
The container is partitioned by ``geohash_prefix`` so a region query touches a
single partition.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from azure.core import MatchConditions
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential

from app.config import get_settings
from app.models import InventoryItem, InventoryStatus

log = logging.getLogger("medisync.inventory")


class InventoryNotFoundError(Exception):
    """Raised when an inventory id (in the given partition) does not exist."""


class InventoryNotAvailableError(Exception):
    """Raised when reserving an item that is not in the Available state."""


class InventoryVersionConflictError(Exception):
    """Raised when an optimistic-concurrency (ETag) check fails."""


class InventoryRepository:
    """Thin wrapper over the Cosmos `inventory` container."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = CosmosClient(
            url=settings.cosmos_endpoint,
            credential=DefaultAzureCredential(),
        )
        database = self._client.get_database_client(settings.cosmos_db)
        self._container = database.get_container_client(settings.cosmos_container)

    def add(self, item: InventoryItem) -> InventoryItem:
        self._container.create_item(body=item.model_dump(mode="json"))
        log.info("inventory added id=%s prefix=%s", item.id, item.geohash_prefix)
        return item

    def query_region(self, geohash_prefix: str, sub_type: str | None = None) -> list[InventoryItem]:
        """Return Available items in one geohash-prefix partition.

        Note: this queries the single prefix cell only. A point near a cell
        boundary can miss stock in an adjacent cell; expanding to the 8
        neighbour cells is a known refinement, deferred for the scaffold.
        """
        query = "SELECT * FROM c WHERE c.geohash_prefix = @gh AND c.status = @st"
        params: list[dict[str, object]] = [
            {"name": "@gh", "value": geohash_prefix},
            {"name": "@st", "value": InventoryStatus.AVAILABLE.value},
        ]
        if sub_type is not None:
            query += " AND c.sub_type = @sub"
            params.append({"name": "@sub", "value": sub_type})

        items = self._container.query_items(
            query=query,
            parameters=params,
            partition_key=geohash_prefix,
        )
        return [InventoryItem.model_validate(raw) for raw in items]

    def reserve(self, item_id: str, geohash_prefix: str, request_id: str) -> InventoryItem:
        """Transition an item Available → Reserved under an ETag If-Match guard.

        Two callers racing for the same unit: the first wins, the second's
        ETag is stale and surfaces as ``InventoryVersionConflictError`` (409)
        rather than a double-booked unit (context.md §8).
        """
        try:
            raw = self._container.read_item(item=item_id, partition_key=geohash_prefix)
        except exceptions.CosmosResourceNotFoundError as exc:
            raise InventoryNotFoundError(item_id) from exc

        item = InventoryItem.model_validate(raw)
        if item.status is not InventoryStatus.AVAILABLE:
            raise InventoryNotAvailableError(item.status.value)

        reserved = item.reserve(request_id)
        try:
            self._container.replace_item(
                item=item_id,
                body=reserved.model_dump(mode="json"),
                etag=raw["_etag"],
                match_condition=MatchConditions.IfNotModified,
            )
        except exceptions.CosmosAccessConditionFailedError as exc:
            raise InventoryVersionConflictError(item_id) from exc
        log.info("inventory reserved id=%s request=%s", item_id, request_id)
        return reserved


@lru_cache(maxsize=1)
def get_repository() -> InventoryRepository:
    """Process-wide singleton — reuses one Cosmos client across invocations."""
    return InventoryRepository()
