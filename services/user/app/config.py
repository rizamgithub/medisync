"""Runtime configuration for the user service, sourced from env vars.

Values come from the Function App's Application Settings in Azure (which in
turn use Key Vault references — context.md §5, §7) and from
``local.settings.json`` when running under ``func start`` locally.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, Field


class Settings(BaseModel):
    service_name: str = "user"
    env: str = "dev"
    log_level: str = "INFO"
    cosmos_endpoint: str = Field(min_length=1)
    cosmos_db: str = "medisync"
    cosmos_container: str = "profiles"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Parse env vars once per process; raises if COSMOS_ENDPOINT is missing."""
    return Settings(
        service_name=os.environ.get("SERVICE_NAME", "user"),
        env=os.environ.get("ENV", "dev"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        cosmos_endpoint=os.environ.get("COSMOS_ENDPOINT", ""),
        cosmos_db=os.environ.get("COSMOS_USER_DB", "medisync"),
        cosmos_container=os.environ.get("COSMOS_USER_CONTAINER", "profiles"),
    )
