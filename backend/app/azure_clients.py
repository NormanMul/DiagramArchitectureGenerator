"""Azure SDK helpers — managed-identity-based clients for Blob, Cosmos, etc.

All clients here use `DefaultAzureCredential` so they work locally
(developer's Azure CLI / VS Code login) and in ACA (the user-assigned MI).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from functools import lru_cache
from typing import Any

from app.settings import Settings, get_settings

_logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _credential(settings: Settings | None = None) -> Any:
    """Singleton DefaultAzureCredential with MI client id wired in.

    Sync version — used by sync clients (azure.cosmos, azure.storage.blob sync).
    """
    s = settings or get_settings()
    from azure.identity import DefaultAzureCredential  # noqa: PLC0415

    return DefaultAzureCredential(
        managed_identity_client_id=s.azure_client_id,
    )


@lru_cache(maxsize=1)
def _credential_async(settings: Settings | None = None) -> Any:
    """Singleton aio DefaultAzureCredential."""
    s = settings or get_settings()
    from azure.identity.aio import DefaultAzureCredential  # noqa: PLC0415

    return DefaultAzureCredential(
        managed_identity_client_id=s.azure_client_id,
    )


@lru_cache(maxsize=1)
def blob_service_client(settings: Settings | None = None) -> Any:
    """Async BlobServiceClient bound to the configured storage account."""
    s = settings or get_settings()
    from azure.storage.blob.aio import BlobServiceClient  # noqa: PLC0415

    return BlobServiceClient(
        account_url=f"https://{s.storage_account}.blob.core.windows.net",
        credential=_credential_async(s),
    )


async def upload_blob(
    container: str,
    blob_name: str,
    data: bytes,
    content_type: str,
    *,
    settings: Settings | None = None,
) -> str:
    """Upload `data` and return the canonical blob URL (no SAS)."""
    s = settings or get_settings()
    svc = blob_service_client(s)
    container_client = svc.get_container_client(container)
    blob_client = container_client.get_blob_client(blob_name)
    await blob_client.upload_blob(
        data,
        overwrite=True,
        content_settings={"content_type": content_type},  # SDK takes dict-like
    )
    return f"https://{s.storage_account}.blob.core.windows.net/{container}/{blob_name}"


async def ensure_container(container: str, settings: Settings | None = None) -> None:
    """Create the blob container if it doesn't exist. Idempotent."""
    s = settings or get_settings()
    svc = blob_service_client(s)
    try:
        await svc.create_container(container)
    except Exception as exc:
        msg = str(exc).lower()
        if "exists" not in msg and "conflict" not in msg:
            _logger.warning("ensure_container failed: %s", exc)


async def _flush_credentials() -> None:
    """Close the async credential — called from FastAPI shutdown."""
    cred = _credential_async.cache_info()
    if cred.currsize > 0:
        with contextlib.suppress(Exception):
            await _credential_async().close()


def run_sync(coro: Any) -> Any:
    """Tiny helper for tests that need to await an async function."""
    return asyncio.get_event_loop().run_until_complete(coro)
