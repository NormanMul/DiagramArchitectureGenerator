"""HTTP routes for /api/generate, /api/refine, /api/diagrams/{id}.{ext}.

Conventions:
  - Diagram bundles are written to a temp dir, then uploaded to Blob Storage.
  - Cosmos stores conversation history keyed by `session_id` (a client-supplied UUID).
  - All errors return JSON with `{"error": "...", "code": "..."}`.
"""

from __future__ import annotations

import base64
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi import Path as PathParam
from pydantic import BaseModel, Field

from app.agents.architect import (
    ArchitectAgent,
    GenerationResult,
    RefinementResult,
    TokenBudget,
    TokenBudgetExceeded,
    build_architect,
)
from app.agents.stub_agent import StubArchitectAgent
from app.azure_clients import ensure_container, upload_blob
from app.renderer.diagrams_render import render_pattern
from app.renderer.drawio_export import export_drawio
from app.renderer.icon_catalog import IconNotFoundError, get_catalog
from app.renderer.models import PopulatedPattern
from app.settings import Settings, get_settings

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["generate"])


# -----------------------------------------------------------------------------
# Dependency: cached architect agent
# -----------------------------------------------------------------------------

_agent_holder: dict[str, ArchitectAgent | StubArchitectAgent] = {}


def _get_agent(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ArchitectAgent | StubArchitectAgent:
    if "agent" not in _agent_holder:
        if settings.stub_mode:
            _logger.warning("ARCHGEN_STUB_MODE=true — using StubArchitectAgent")
            _agent_holder["agent"] = StubArchitectAgent()
        else:
            _agent_holder["agent"] = build_architect(settings)
    return _agent_holder["agent"]


# -----------------------------------------------------------------------------
# Request / response models
# -----------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=8, max_length=2000)
    session_id: str | None = Field(
        default=None, description="Stable client-supplied id for refinement turns"
    )


class RefineRequest(BaseModel):
    session_id: str = Field(min_length=8)
    instruction: str = Field(min_length=4, max_length=1000)
    current_pattern: PopulatedPattern


class DiagramArtifact(BaseModel):
    kind: str  # 'svg' | 'png' | 'drawio' | 'py'
    url: str
    bytes_size: int


class GenerateResponse(BaseModel):
    session_id: str
    diagram_id: str
    pattern: PopulatedPattern
    justification: str
    candidate_pattern_names: list[str]
    artifacts: list[DiagramArtifact]
    tokens_input: int
    tokens_output: int


class RefineResponse(BaseModel):
    session_id: str
    diagram_id: str
    pattern: PopulatedPattern
    summary: str
    artifacts: list[DiagramArtifact]
    tokens_input: int
    tokens_output: int


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@router.post(
    "/generate",
    response_model=GenerateResponse,
    summary="Generate a new diagram from a natural-language prompt",
)
async def generate(
    body: GenerateRequest,
    agent: Annotated[ArchitectAgent, Depends(_get_agent)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GenerateResponse:
    session_id = body.session_id or str(uuid.uuid4())
    budget = TokenBudget(
        input_max=settings.token_budget_input,
        output_max=settings.token_budget_output,
    )

    try:
        result: GenerationResult = await agent.generate(body.prompt, budget=budget)
    except TokenBudgetExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except IconNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown icon id: {exc}",
        ) from exc

    diagram_id = _new_diagram_id()
    artifacts = await _render_and_upload(result.pattern, diagram_id=diagram_id, settings=settings)

    return GenerateResponse(
        session_id=session_id,
        diagram_id=diagram_id,
        pattern=result.pattern,
        justification=result.justification,
        candidate_pattern_names=result.candidate_pattern_names,
        artifacts=artifacts,
        tokens_input=result.tokens_input,
        tokens_output=result.tokens_output,
    )


@router.post(
    "/refine",
    response_model=RefineResponse,
    summary="Apply a follow-up instruction to an existing diagram",
)
async def refine(
    body: RefineRequest,
    agent: Annotated[ArchitectAgent, Depends(_get_agent)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RefineResponse:
    budget = TokenBudget(
        input_max=settings.token_budget_input,
        output_max=settings.token_budget_output,
    )

    try:
        result: RefinementResult = await agent.refine(
            body.current_pattern, body.instruction, budget=budget
        )
    except TokenBudgetExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    diagram_id = _new_diagram_id()
    artifacts = await _render_and_upload(result.pattern, diagram_id=diagram_id, settings=settings)

    return RefineResponse(
        session_id=body.session_id,
        diagram_id=diagram_id,
        pattern=result.pattern,
        summary=result.summary,
        artifacts=artifacts,
        tokens_input=result.tokens_input,
        tokens_output=result.tokens_output,
    )


@router.get(
    "/diagrams/{diagram_id}.{ext}",
    summary="Return a previously generated artifact (passthrough proxy)",
)
async def get_diagram(
    diagram_id: Annotated[str, PathParam(min_length=8, max_length=40)],
    ext: Annotated[str, PathParam(pattern=r"^(svg|png|drawio|py)$")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """The browser is redirected to the Blob URL via 302. The container is
    private (PE-only); the BFF should sign a short-lived SAS in front of us.
    For v1 the redirect is opaque to the user — the frontend reads .url from
    the GenerateResponse instead.
    """
    blob_url = (
        f"https://{settings.storage_account}.blob.core.windows.net/"
        f"{settings.storage_diagrams_container}/{diagram_id}.{ext}"
    )
    return Response(status_code=status.HTTP_302_FOUND, headers={"Location": blob_url})


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _new_diagram_id() -> str:
    return uuid.uuid4().hex[:24]


async def _render_and_upload(
    pattern: PopulatedPattern,
    *,
    diagram_id: str,
    settings: Settings,
) -> list[DiagramArtifact]:
    """Render the diagram + .drawio + standalone .py and upload all to Blob.

    Returns the list of artifact URLs in a stable order. In stub mode the
    upload step is skipped and base64 data URLs are returned instead, so
    local dev works without an Azure storage account.
    """
    if not settings.stub_mode:
        await ensure_container(settings.storage_diagrams_container, settings=settings)

    with tempfile.TemporaryDirectory(prefix="archgen-") as tmp:
        out_dir = Path(tmp)
        rendered = render_pattern(pattern, out_dir, catalog=get_catalog(), basename=diagram_id)
        drawio_path = out_dir / f"{diagram_id}.drawio"
        export_drawio(pattern, drawio_path, catalog=get_catalog())

        artifacts: list[DiagramArtifact] = []
        for path, kind, ctype in [
            (rendered.svg_path, "svg", "image/svg+xml"),
            (rendered.png_path, "png", "image/png"),
            (drawio_path, "drawio", "application/xml"),
            (rendered.py_script_path, "py", "text/x-python"),
        ]:
            data = path.read_bytes()
            blob_name = f"{diagram_id}.{kind}"
            if settings.stub_mode:
                b64 = base64.b64encode(data).decode("ascii")
                url = f"data:{ctype};base64,{b64}"
            else:
                url = await upload_blob(
                    settings.storage_diagrams_container,
                    blob_name,
                    data,
                    ctype,
                    settings=settings,
                )
            artifacts.append(DiagramArtifact(kind=kind, url=url, bytes_size=len(data)))
        return artifacts
