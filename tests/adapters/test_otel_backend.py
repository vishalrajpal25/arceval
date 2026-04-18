"""Tests for the OTEL backend adapter.

Tests verify OTEL SDK integration. The SDK is a core dependency so it's always available.
"""

import pytest

from arceval.backends.otel import HAS_OTEL_SDK, HAS_OTLP_HTTP, OTELBackend
from arceval.core.exceptions import BackendError
from arceval.core.trace_model import create_trace
from arceval.core.protocols import ScoreResult
from arceval.core.tier import Tier


@pytest.mark.skipif(
    not HAS_OTEL_SDK or not HAS_OTLP_HTTP,
    reason="Requires opentelemetry SDK and OTLP HTTP exporter",
)
class TestOTELBackend:
    def test_instantiate(self):
        # Uses localhost; won't connect but shouldn't crash
        backend = OTELBackend(endpoint="http://localhost:4318")
        assert backend.health_check() is True

    def test_emit_buffers_traces(self):
        backend = OTELBackend(endpoint="http://localhost:4318")
        trace = create_trace(
            latency_ms=100.0,
            gen_ai_system="openai",
            gen_ai_operation="chat",
            attributes={"tool_name": "search"},
        )
        backend.emit([trace])
        # Query returns buffered traces
        results = backend.query(limit=10)
        assert len(results) == 1
        assert results[0].trace_id == trace.trace_id

    def test_store_scores(self):
        backend = OTELBackend(endpoint="http://localhost:4318")
        score = ScoreResult(
            scorer_name="latency",
            tier=Tier.T1,
            passed=True,
            score=0.95,
            threshold=2000.0,
            trace_id="abc",
            timestamp="2026-01-01",
        )
        # Should not raise
        backend.store_scores([score])

    def test_shutdown(self):
        backend = OTELBackend(endpoint="http://localhost:4318")
        backend.shutdown()  # should not raise


@pytest.mark.skipif(HAS_OTEL_SDK, reason="Tests import gating when OTEL SDK is NOT installed")
class TestOTELBackendNoSDK:
    def test_raises_without_sdk(self):
        with pytest.raises(BackendError, match="not installed"):
            OTELBackend()
