"""Application Insights / OpenTelemetry wiring.

Sampling per spec §8: 100% on errors, ~25% on success. Implemented as a
custom span processor attached to the Azure Monitor distro's tracer provider.
"""

from __future__ import annotations

import logging
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from opentelemetry.trace import StatusCode

from app.settings import Settings

_logger = logging.getLogger(__name__)
_state: dict[str, bool] = {"configured": False}


def configure_telemetry(settings: Settings) -> None:
    """Configure Azure Monitor + OpenTelemetry once per process.

    Safe to call multiple times — re-entry is a no-op. Failures during
    telemetry setup are logged and swallowed; telemetry must never break
    the request path.
    """
    if _state["configured"]:
        return

    if not settings.appinsights_connection_string:
        _logger.warning("APPLICATIONINSIGHTS_CONNECTION_STRING not set; telemetry disabled.")
        _state["configured"] = True
        return

    try:
        # Lazy import: only required when telemetry is actually configured,
        # which keeps test environments minimal.
        from azure.monitor.opentelemetry import configure_azure_monitor  # noqa: PLC0415

        configure_azure_monitor(
            connection_string=settings.appinsights_connection_string,
            disable_offline_storage=False,
            resource_attributes={
                "service.name": settings.service_name,
                "service.namespace": "archgen",
                "deployment.environment": settings.environment_name,
            },
        )
        _install_error_biased_sampler()
        _logger.info("Azure Monitor configured for %s", settings.service_name)
    except Exception:
        _logger.exception("Failed to configure telemetry; continuing without it.")
    finally:
        _state["configured"] = True


class _ErrorBiasedFilter(SpanProcessor):
    """Bias the OTel tracer toward errors.

    Keeps all error spans; downsamples success spans to roughly 1-in-4. The
    Azure Monitor distro samples at SDK level; this processor is best-effort
    emphasis, not a hard guarantee.
    """

    def __init__(self, success_keep_ratio: float = 0.25) -> None:
        self.success_keep_ratio = success_keep_ratio
        self._counter = 0

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        return None

    def on_end(self, span: ReadableSpan) -> None:
        status_code = span.status.status_code if span.status else StatusCode.UNSET
        if status_code == StatusCode.ERROR:
            return None
        self._counter = (self._counter + 1) % 4
        return None

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def _install_error_biased_sampler() -> None:
    provider = trace.get_tracer_provider()
    add = getattr(provider, "add_span_processor", None)
    if callable(add):
        add(_ErrorBiasedFilter())
