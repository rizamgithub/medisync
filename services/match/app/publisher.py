"""Azure Event Grid publishing for MediSync custom events.

Auth uses ``DefaultAzureCredential`` (context.md §3) — the Function App's
Managed Identity needs the ``EventGrid Data Sender`` role on the topic; no
topic access keys in code or config.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from azure.eventgrid import EventGridEvent, EventGridPublisherClient
from azure.identity import DefaultAzureCredential
from pydantic import BaseModel

from app.config import get_settings
from medisync_shared.events import EVENT_DATA_VERSION, EventType

log = logging.getLogger("medisync.match")


class EventPublisher:
    """Thin wrapper over an Event Grid topic publisher."""

    def __init__(self) -> None:
        endpoint = get_settings().eventgrid_topic_endpoint
        self._client = EventGridPublisherClient(endpoint, DefaultAzureCredential())

    def publish(self, event_type: EventType, subject: str, data: BaseModel) -> None:
        self._client.send(
            EventGridEvent(
                event_type=event_type.value,
                subject=subject,
                data=data.model_dump(mode="json"),
                data_version=EVENT_DATA_VERSION,
            )
        )
        log.info("published event type=%s subject=%s", event_type.value, subject)


@lru_cache(maxsize=1)
def get_publisher() -> EventPublisher:
    """Process-wide singleton — reuses one publisher client across invocations."""
    return EventPublisher()
