"""Tests for /api/generate, /api/refine, /api/diagrams/{id}.{ext}.

The architect agent and Azure SDK clients are monkeypatched out — we don't
hit Foundry or Blob Storage in unit tests. Render path uses the real
drawio_export + a stub for the graphviz-dependent diagrams_render.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agents.architect import GenerationResult, RefinementResult
from app.renderer.diagrams_render import RenderResult
from app.renderer.icon_catalog import IconCatalog
from app.renderer.models import Edge, Node, PopulatedPattern


def _example_pattern() -> PopulatedPattern:
    return PopulatedPattern(
        pattern_name="basic-web-app",
        title="Basic Web App",
        source_url="https://learn.microsoft.com/azure/architecture/x",
        tiers=["edge", "data"],
        nodes=[
            Node(id="a", label="A", icon_id="app-services", tier="edge"),
            Node(id="b", label="B", icon_id="azure-sql", tier="data"),
        ],
        edges=[Edge(source="a", target="b", label="HTTPS")],
    )


@pytest.fixture
def client_with_stubs(monkeypatch: pytest.MonkeyPatch, catalog: IconCatalog) -> TestClient:
    """Build a FastAPI TestClient with all external collaborators stubbed."""

    # Force the icon catalog to our 6-icon fixture.
    from app.renderer import icon_catalog as ic

    monkeypatch.setattr(ic, "get_catalog", lambda *a, **kw: catalog)
    from app.routers import generate as g

    monkeypatch.setattr(g, "get_catalog", lambda *a, **kw: catalog)

    # Stub the architect agent.
    pattern = _example_pattern()

    class _StubAgent:
        async def generate(self, prompt: str, *, budget: Any, top_k: int = 3) -> GenerationResult:
            return GenerationResult(
                pattern=pattern,
                candidate_pattern_names=["basic-web-app", "hub-spoke", "aks-baseline"],
                justification="Looks like a basic web app.",
                tokens_input=500,
                tokens_output=200,
            )

        async def refine(
            self,
            current: PopulatedPattern,
            instruction: str,
            *,
            budget: Any,
        ) -> RefinementResult:
            return RefinementResult(
                pattern=pattern,
                summary="Added a node.",
                tokens_input=300,
                tokens_output=100,
            )

    monkeypatch.setattr(g, "build_architect", lambda settings: _StubAgent())
    g._agent_holder.clear()  # clear cached agent

    # Stub the renderer (graphviz-dependent code path).
    def _stub_render(pattern: PopulatedPattern, output_dir: Path, **kwargs: Any) -> RenderResult:
        basename = kwargs.get("basename", "diagram")
        svg = output_dir / f"{basename}.svg"
        png = output_dir / f"{basename}.png"
        py = output_dir / f"{basename}.py"
        svg.write_text("<svg></svg>", encoding="utf-8")
        png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        py.write_text("# generated\n", encoding="utf-8")
        return RenderResult(svg_path=svg, png_path=png, py_script_path=py)

    monkeypatch.setattr(g, "render_pattern", _stub_render)

    # Stub Azure Blob.
    uploaded: list[tuple[str, str, int]] = []

    async def _stub_upload(container: str, blob: str, data: bytes, ctype: str, **kw: Any) -> str:
        uploaded.append((container, blob, len(data)))
        return f"https://fake.blob.core.windows.net/{container}/{blob}"

    async def _stub_ensure(container: str, **kw: Any) -> None:
        return None

    monkeypatch.setattr(g, "upload_blob", _stub_upload)
    monkeypatch.setattr(g, "ensure_container", _stub_ensure)

    # Force settings to defaults (no AZ env required for the test).
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    from app.settings import get_settings

    get_settings.cache_clear()

    from app.main import app

    return TestClient(app)


class TestGenerateRoute:
    def test_returns_201_with_artifacts(self, client_with_stubs: TestClient) -> None:
        resp = client_with_stubs.post(
            "/api/generate",
            json={"prompt": "basic web app with sql"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pattern"]["pattern_name"] == "basic-web-app"
        kinds = {a["kind"] for a in body["artifacts"]}
        assert kinds == {"svg", "png", "drawio", "py"}
        for a in body["artifacts"]:
            assert a["url"].startswith("https://fake.blob.core.windows.net/")
            assert a["bytes_size"] > 0

    def test_session_id_is_assigned_when_missing(self, client_with_stubs: TestClient) -> None:
        resp = client_with_stubs.post("/api/generate", json={"prompt": "basic web app"})
        assert resp.status_code == 200
        assert resp.json()["session_id"]

    def test_session_id_is_preserved(self, client_with_stubs: TestClient) -> None:
        resp = client_with_stubs.post(
            "/api/generate",
            json={"prompt": "basic web app", "session_id": "abc12345"},
        )
        assert resp.json()["session_id"] == "abc12345"

    def test_short_prompt_rejected(self, client_with_stubs: TestClient) -> None:
        resp = client_with_stubs.post("/api/generate", json={"prompt": "hi"})
        assert resp.status_code == 422


class TestRefineRoute:
    def test_round_trip(self, client_with_stubs: TestClient) -> None:
        pattern = _example_pattern()
        resp = client_with_stubs.post(
            "/api/refine",
            json={
                "session_id": "abc12345",
                "instruction": "add a private endpoint to sql",
                "current_pattern": pattern.model_dump(),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "abc12345"
        assert body["summary"] == "Added a node."
        assert len(body["artifacts"]) == 4


class TestDiagramRoute:
    def test_redirects_to_blob(self, client_with_stubs: TestClient) -> None:
        resp = client_with_stubs.get("/api/diagrams/abcdef1234.svg", follow_redirects=False)
        assert resp.status_code == 302
        assert "abcdef1234.svg" in resp.headers["location"]

    def test_unknown_extension_rejected(self, client_with_stubs: TestClient) -> None:
        resp = client_with_stubs.get("/api/diagrams/abcdef1234.exe", follow_redirects=False)
        assert resp.status_code == 422
