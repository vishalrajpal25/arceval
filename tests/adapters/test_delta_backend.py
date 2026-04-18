"""Tests for the Delta Lake backend adapter.

These tests verify import gating. Full integration tests require deltalake installed.
"""

import pytest

from arceval.backends.delta import HAS_DELTALAKE, DeltaBackend
from arceval.core.exceptions import BackendError


@pytest.mark.skipif(HAS_DELTALAKE, reason="Tests import gating when deltalake is NOT installed")
class TestDeltaBackendNoDeltalake:
    def test_raises_without_deltalake(self):
        with pytest.raises(BackendError, match="deltalake is not installed"):
            DeltaBackend(connection="delta-rs")


class TestDeltaBackendBadConnection:
    def test_unknown_connection_type(self):
        with pytest.raises(BackendError, match="Unknown connection type"):
            DeltaBackend(connection="unknown")


@pytest.mark.skipif(not HAS_DELTALAKE, reason="Requires deltalake installed")
class TestDeltaBackendWithDeltalake:
    def test_health_check(self, tmp_path):
        backend = DeltaBackend(
            connection="delta-rs",
            storage_path=str(tmp_path / "delta"),
        )
        assert backend.health_check() is True

    def test_emit_and_query(self, tmp_path):
        from arceval.core.trace_model import create_trace

        backend = DeltaBackend(
            connection="delta-rs",
            storage_path=str(tmp_path / "delta"),
        )
        traces = [
            create_trace(latency_ms=100.0, gen_ai_system="openai"),
            create_trace(latency_ms=200.0, gen_ai_system="anthropic"),
        ]
        backend.emit(traces)
        results = backend.query()
        assert len(results) == 2
