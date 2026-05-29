"""Process-wide settings, loaded from env vars only.

§8 of the spec: no secrets in env vars. Everything sensitive (KV references)
is fetched via managed identity at runtime — see `app.azure.kv`. The vars
below are *non-secret* identifiers (endpoints, deployment names, etc.).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All non-secret runtime config."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # --- Identity & environment ---
    service_name: str = Field(default="archgen-api", alias="SERVICE_NAME")
    environment_name: str = Field(default="prod", alias="ENVIRONMENT_NAME")
    azure_client_id: str | None = Field(default=None, alias="AZURE_CLIENT_ID")

    # --- Telemetry ---
    appinsights_connection_string: str | None = Field(
        default=None, alias="APPLICATIONINSIGHTS_CONNECTION_STRING"
    )

    # --- Foundry ---
    foundry_endpoint: str = Field(
        default="https://fdy-archgen-sea-01.openai.azure.com/",
        alias="FOUNDRY_ENDPOINT",
        description="Foundry account custom-subdomain root (no trailing path).",
    )
    foundry_deployment: str = Field(default="archgen-gpt54", alias="FOUNDRY_DEPLOYMENT")
    foundry_api_version: str = Field(default="2025-04-01-preview", alias="FOUNDRY_API_VERSION")

    # --- AI Search ---
    search_endpoint: str = Field(
        default="https://srch-archgen-prod-sea.search.windows.net/",
        alias="SEARCH_ENDPOINT",
    )
    search_index: str = Field(default="archgen-patterns", alias="SEARCH_INDEX")

    # --- Cosmos ---
    cosmos_endpoint: str = Field(
        default="https://cosmos-archgen-prod-sea.documents.azure.com:443/",
        alias="COSMOS_ENDPOINT",
    )
    cosmos_database: str = Field(default="archgen", alias="COSMOS_DATABASE")
    cosmos_conversations_container: str = Field(
        default="conversations", alias="COSMOS_CONVERSATIONS_CONTAINER"
    )

    # --- Storage ---
    storage_account: str = Field(default="starchgenprodsea", alias="STORAGE_ACCOUNT")
    storage_diagrams_container: str = Field(default="diagrams", alias="STORAGE_DIAGRAMS_CONTAINER")

    # --- Token budget (per session). Spec §9 revised default: 5k in + 2k out. ---
    token_budget_input: int = Field(default=5000, alias="TOKEN_BUDGET_INPUT", ge=1)
    token_budget_output: int = Field(default=2000, alias="TOKEN_BUDGET_OUTPUT", ge=1)

    # --- Icons ---
    icons_root: str = Field(
        default="/opt/archgen/icons/azure_V19",
        alias="ICONS_ROOT",
        description="Root directory of the bundled V19 icon pack.",
    )
    icons_manifest_path: str = Field(
        default="/opt/archgen/icons/manifest.json",
        alias="ICONS_MANIFEST_PATH",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()
