"""Tests for the RAGAS scorer adapter."""

import pytest

from arceval.core.exceptions import ScorerError
from arceval.scorers.adapters.ragas import HAS_RAGAS, RAGASAdapter


@pytest.mark.skipif(HAS_RAGAS, reason="Tests import gating when ragas is NOT installed")
class TestRAGASAdapterNoRagas:
    def test_raises_without_ragas(self):
        with pytest.raises(ScorerError, match="RAGAS is not installed"):
            RAGASAdapter(metric="faithfulness")


@pytest.mark.skipif(not HAS_RAGAS, reason="Requires ragas installed")
class TestRAGASAdapterWithRagas:
    def test_instantiate(self):
        adapter = RAGASAdapter(metric="faithfulness")
        assert adapter.name == "ragas.faithfulness"

    def test_validate_config_valid(self):
        adapter = RAGASAdapter(metric="faithfulness")
        assert adapter.validate_config() == []
