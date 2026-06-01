"""Genesis backend — FastAPI entrypoint.

Exposes a thin HTTP API that the Next.js BFF calls:
  * GET  /healthz                   — liveness probe
  * GET  /readyz                    — readiness probe (checks Foundry + Cosmos reachability)
  * POST /api/generate              — generate a diagram from a natural-language prompt
  * POST /api/refine                — iterate on an existing diagram
  * GET  /api/diagrams/{id}.{ext}   — download SVG / PNG / drawio / py

Auth: the API runs behind Front Door over Private Link; the ACA env is
internal-only. We do not authenticate users in v1 — the AFD WAF custom rule
rate-limits /api/generate to 60 req/min/IP.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from app.routers import generate as generate_router
from app.settings import Settings, get_settings
from app.telemetry import configure_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks. Wires telemetry once per process."""
    settings = get_settings()
    configure_telemetry(settings)
    yield


app = FastAPI(
    title="Genesis — Azure Architecture Diagram Generator",
    description=(
        "Backend API for the Genesis diagram generator. "
        "See docs/architecture.md for the system design."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)


@app.get("/healthz", tags=["health"], summary="Liveness probe")
async def healthz() -> JSONResponse:
    """Always 200 if the process is running. Used by ACA liveness probe."""
    return JSONResponse({"status": "ok"})


@app.get("/readyz", tags=["health"], summary="Readiness probe")
async def readyz(settings: Annotated[Settings, Depends(get_settings)]) -> JSONResponse:
    """Lightweight readiness check; does NOT call out to Foundry/Cosmos.

    Real connectivity checks happen on first request — failing fast on a
    transient dependency hiccup would cause unnecessary cold-start churn given
    the scale-to-zero topology.
    """
    return JSONResponse(
        {
            "status": "ready",
            "service": settings.service_name,
            "env": settings.environment_name,
        }
    )


app.include_router(generate_router.router)
# app.include_router(generate_router.router)
