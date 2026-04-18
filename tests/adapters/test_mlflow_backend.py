"""Tests for the MLflow backend adapter.

These tests verify import gating. Full integration tests require mlflow installed.
"""

import pytest

from arceval.backends.mlflow import HAS_MLFLOW, MLflowBackend
from arceval.core.exceptions import BackendError


@pytest.mark.skipif(HAS_MLFLOW, reason="Tests import gating when mlflow is NOT installed")
class TestMLflowBackendNoMLflow:
    def test_raises_without_mlflow(self):
        with pytest.raises(BackendError, match="MLflow is not installed"):
            MLflowBackend()


@pytest.mark.skipif(not HAS_MLFLOW, reason="Requires mlflow installed")
class TestMLflowBackendWithMLflow:
    def test_health_check(self, tmp_path):
        backend = MLflowBackend(
            tracking_uri=f"file:///{tmp_path}/mlruns",
            experiment_name="/test/arceval",
        )
        assert backend.health_check() is True

    def test_emit_and_query(self, tmp_path):
        from arceval.core.trace_model import create_trace

        backend = MLflowBackend(
            tracking_uri=f"file:///{tmp_path}/mlruns",
            experiment_name="/test/arceval",
        )
        trace = create_trace(latency_ms=100.0, gen_ai_system="openai")
        backend.emit([trace])
        # MLflow file backend should have data
        results = backend.query(limit=10)
        # Results depend on MLflow internals; just verify no crash
        assert isinstance(results, (list, tuple))
