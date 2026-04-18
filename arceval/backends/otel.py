"""OpenTelemetry OTLP backend for any OTEL-compatible collector."""

from __future__ import annotations

import logging
from typing import Any, Sequence

from arceval.core.exceptions import BackendError
from arceval.core.protocols import ScoreResult
from arceval.core.trace_model import Trace

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    HAS_OTEL_SDK = True
except ImportError:
    HAS_OTEL_SDK = False

try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    HAS_OTLP_HTTP = True
except ImportError:
    HAS_OTLP_HTTP = False

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter as OTLPGrpcSpanExporter,
    )

    HAS_OTLP_GRPC = True
except ImportError:
    HAS_OTLP_GRPC = False


class OTELBackend:
    """Emits traces as OTLP spans to any OpenTelemetry-compatible collector.

    Uses gen_ai.* semantic conventions for attribute names.

    Config:
        endpoint: OTLP collector endpoint (e.g. "http://localhost:4318")
        protocol: "http" or "grpc"
        headers: optional HTTP headers for authentication
        service_name: OTEL service name
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:4318",
        protocol: str = "http",
        headers: dict[str, str] | None = None,
        service_name: str = "arceval",
        **kwargs: Any,
    ) -> None:
        if not HAS_OTEL_SDK:
            raise BackendError(
                "OpenTelemetry SDK is not installed. "
                "Install with: pip install arceval[otel]"
            )

        self._endpoint = endpoint
        self._protocol = protocol
        self._headers = headers or {}
        self._traces_buffer: list[Trace] = []

        # Set up OTEL tracer
        if protocol == "grpc" and HAS_OTLP_GRPC:
            exporter = OTLPGrpcSpanExporter(
                endpoint=endpoint,
                headers=list(self._headers.items()) if self._headers else None,
            )
        elif HAS_OTLP_HTTP:
            exporter = OTLPSpanExporter(
                endpoint=f"{endpoint}/v1/traces",
                headers=self._headers,
            )
        else:
            raise BackendError(
                f"OTLP exporter for protocol '{protocol}' is not installed. "
                "Install with: pip install opentelemetry-exporter-otlp"
            )

        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        self._provider = provider
        self._tracer = provider.get_tracer("arceval")

    def emit(self, traces: Sequence[Trace]) -> None:
        """Export traces as OTEL spans."""
        for trace in traces:
            try:
                with self._tracer.start_as_current_span(
                    name=trace.gen_ai_operation or "arceval.trace"
                ) as span:
                    if trace.gen_ai_system:
                        span.set_attribute("gen_ai.system", trace.gen_ai_system)
                    if trace.gen_ai_operation:
                        span.set_attribute("gen_ai.operation", trace.gen_ai_operation)
                    if trace.gen_ai_request_model:
                        span.set_attribute("gen_ai.request.model", trace.gen_ai_request_model)
                    if trace.gen_ai_response_model:
                        span.set_attribute("gen_ai.response.model", trace.gen_ai_response_model)
                    if trace.gen_ai_usage_input_tokens is not None:
                        span.set_attribute(
                            "gen_ai.usage.input_tokens", trace.gen_ai_usage_input_tokens
                        )
                    if trace.gen_ai_usage_output_tokens is not None:
                        span.set_attribute(
                            "gen_ai.usage.output_tokens", trace.gen_ai_usage_output_tokens
                        )
                    if trace.latency_ms is not None:
                        span.set_attribute("arceval.latency_ms", trace.latency_ms)
                    if trace.status_code is not None:
                        span.set_attribute("http.status_code", trace.status_code)
                    if trace.error_type:
                        span.set_attribute("error.type", trace.error_type)

                    span.set_attribute("arceval.trace_id", trace.trace_id)

                    for key, value in trace.attributes.items():
                        if isinstance(value, (str, int, float, bool)):
                            span.set_attribute(f"arceval.{key}", value)

            except Exception as exc:
                logger.error("Failed to emit trace to OTEL: %s", exc)

        self._traces_buffer.extend(traces)

    def query(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> Sequence[Trace]:
        """Return buffered traces. OTEL collectors are write-only;
        query returns traces emitted in this session."""
        result = self._traces_buffer[:limit]
        return result

    def store_scores(self, scores: Sequence[ScoreResult]) -> None:
        """Emit score results as OTEL span events."""
        for score in scores:
            try:
                with self._tracer.start_as_current_span(
                    name=f"arceval.score.{score.scorer_name}"
                ) as span:
                    span.set_attribute("arceval.scorer_name", score.scorer_name)
                    span.set_attribute("arceval.tier", score.tier.value)
                    span.set_attribute("arceval.passed", score.passed)
                    if score.score is not None:
                        span.set_attribute("arceval.score", score.score)
                    if score.threshold is not None:
                        span.set_attribute("arceval.threshold", score.threshold)
                    span.set_attribute("arceval.trace_id", score.trace_id)
            except Exception as exc:
                logger.error("Failed to store score in OTEL: %s", exc)

    def health_check(self) -> bool:
        """Check that the tracer provider is configured."""
        return self._provider is not None

    def shutdown(self) -> None:
        """Flush and shut down the OTEL provider."""
        try:
            self._provider.shutdown()
        except Exception as exc:
            logger.error("Failed to shut down OTEL provider: %s", exc)
