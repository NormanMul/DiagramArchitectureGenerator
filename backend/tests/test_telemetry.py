"""Telemetry wiring — exercises the no-op branches (no APPINSIGHTS connection
string, double-configure idempotency, failure-swallow). Full Azure Monitor
integration is out of scope for unit tests.
"""

from __future__ import annotations

import logging
import sys

from app.settings import Settings, get_settings
from app.telemetry import _state, configure_telemetry


def _reset_state() -> None:
    _state["configured"] = False


class TestConfigureTelemetry:
    def test_no_connection_string_disables_silently(
        self, caplog: logging.LogCaptureFixture, monkeypatch
    ) -> None:
        monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
        get_settings.cache_clear()
        _reset_state()
        s = Settings()
        with caplog.at_level(logging.WARNING):
            configure_telemetry(s)
        assert any("telemetry disabled" in r.message for r in caplog.records)
        assert _state["configured"] is True

    def test_double_call_is_idempotent(self, monkeypatch) -> None:
        monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
        get_settings.cache_clear()
        _reset_state()
        s = Settings()
        configure_telemetry(s)
        configure_telemetry(s)  # should no-op
        assert _state["configured"] is True

    def test_failure_during_setup_is_swallowed(
        self, monkeypatch, caplog: logging.LogCaptureFixture
    ) -> None:
        """If the Azure Monitor SDK raises, we must not break the app."""
        monkeypatch.setenv(
            "APPLICATIONINSIGHTS_CONNECTION_STRING",
            "InstrumentationKey=00000000-0000-0000-0000-000000000000",
        )
        get_settings.cache_clear()
        _reset_state()
        s = Settings()

        # Force the lazy import to blow up by injecting a broken module.
        class _Broken:
            @staticmethod
            def configure_azure_monitor(**_kwargs: object) -> None:
                raise RuntimeError("simulated upstream failure")

        monkeypatch.setitem(sys.modules, "azure.monitor.opentelemetry", _Broken())
        with caplog.at_level(logging.ERROR):
            configure_telemetry(s)  # must not raise
        assert any("Failed to configure telemetry" in r.message for r in caplog.records)
        assert _state["configured"] is True
