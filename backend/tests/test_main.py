"""Lightweight smoke tests for app.main — exercises only the dependency-free
health endpoints; full integration tests live under tests/integration/."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.settings import get_settings


class TestHealthEndpoints:
    def test_healthz_returns_ok(self) -> None:
        with TestClient(app) as client:
            resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_readyz_returns_metadata(self, monkeypatch) -> None:
        monkeypatch.setenv("SERVICE_NAME", "archgen-api")
        monkeypatch.setenv("ENVIRONMENT_NAME", "test")
        # Reset cached settings so the monkeypatch takes effect.
        get_settings.cache_clear()
        with TestClient(app) as client:
            resp = client.get("/readyz")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"
        assert body["service"] == "archgen-api"
        assert body["env"] == "test"
