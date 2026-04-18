"""Tests for the MLflow scorer adapter."""

import pytest

from arceval.core.exceptions import ScorerError
from arceval.scorers.adapters.mlflow_scorers import HAS_MLFLOW, MLflowScorerAdapter


@pytest.mark.skipif(HAS_MLFLOW, reason="Tests import gating when mlflow is NOT installed")
class TestMLflowScorerAdapterNoMLflow:
    def test_raises_without_mlflow(self):
        with pytest.raises(ScorerError, match="MLflow is not installed"):
            MLflowScorerAdapter(metric="correctness")


@pytest.mark.skipif(not HAS_MLFLOW, reason="Requires mlflow installed")
class TestMLflowScorerAdapterWithMLflow:
    def test_instantiate(self):
        adapter = MLflowScorerAdapter(metric="correctness")
        assert adapter.name == "mlflow.correctness"

    def test_validate_config_valid(self):
        adapter = MLflowScorerAdapter(metric="correctness")
        assert adapter.validate_config() == []
