"""Runtime configuration for the match service, sourced from env vars.

Values come from the Function App's Application Settings in Azure (Key Vault
references — context.md §5, §7) and from ``local.settings.json`` locally.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, Field


class Settings(BaseModel):
    service_name: str = "match"
    env: str = "dev"
    log_level: str = "INFO"
    cosmos_endpoint: str = Field(min_length=1)
    cosmos_db: str = "medisync"
    cosmos_container: str = "requests"
    eventgrid_topic_endpoint: str = Field(min_length=1)
    inventory_api_base_url: str = Field(min_length=1)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Parse env vars once per process; raises if a required value is missing."""
    return Settings(
        service_name=os.environ.get("SERVICE_NAME", "match"),
        env=os.environ.get("ENV", "dev"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        cosmos_endpoint=os.environ.get("COSMOS_ENDPOINT", ""),
        cosmos_db=os.environ.get("COSMOS_REQUEST_DB", "medisync"),
        cosmos_container=os.environ.get("COSMOS_REQUEST_CONTAINER", "requests"),
        eventgrid_topic_endpoint=os.environ.get("EVENTGRID_TOPIC_ENDPOINT", ""),
        inventory_api_base_url=os.environ.get("INVENTORY_API_BASE_URL", ""),
    )
