"""Tests for the DeepEval scorer adapter."""

import pytest

from arceval.core.exceptions import ScorerError
from arceval.scorers.adapters.deepeval import HAS_DEEPEVAL, DeepEvalAdapter


@pytest.mark.skipif(HAS_DEEPEVAL, reason="Tests import gating when deepeval is NOT installed")
class TestDeepEvalAdapterNoDeepEval:
    def test_raises_without_deepeval(self):
        with pytest.raises(ScorerError, match="DeepEval is not installed"):
            DeepEvalAdapter(metric="correctness")


@pytest.mark.skipif(not HAS_DEEPEVAL, reason="Requires deepeval installed")
class TestDeepEvalAdapterWithDeepEval:
    def test_instantiate_correctness(self):
        adapter = DeepEvalAdapter(metric="correctness", model="gpt-4o")
        assert adapter.name == "deepeval.correctness"

    def test_validate_config_valid(self):
        adapter = DeepEvalAdapter(metric="correctness")
        assert adapter.validate_config() == []

    def test_validate_config_unknown_metric(self):
        adapter = DeepEvalAdapter(metric="nonexistent")
        errors = adapter.validate_config()
        assert any("Unknown" in e for e in errors)
