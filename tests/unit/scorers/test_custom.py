"""Tests for the custom scorer adapter."""

import pytest

from arceval.core.exceptions import ScorerError
from arceval.core.protocols import GoldenRecord
from arceval.core.tier import Tier
from arceval.core.trace_model import create_trace
from arceval.scorers.adapters.custom import CustomScorer


def always_pass(data: dict) -> float:
    return 1.0


def always_fail(data: dict) -> float:
    return 0.0


def check_has_output(data: dict) -> float:
    return 1.0 if data.get("output") else 0.0


def bad_return(data: dict) -> str:
    return "not a float"  # type: ignore


class TestCustomScorer:
    def test_pass(self):
        scorer = CustomScorer(callable=always_pass, threshold=0.5, name="test_pass")
        trace = create_trace(input_data="hello", output_data="world")
        result = scorer.score_trace(trace)
        assert result.passed is True
        assert result.score == 1.0

    def test_fail(self):
        scorer = CustomScorer(callable=always_fail, threshold=0.5, name="test_fail")
        trace = create_trace(input_data="hello", output_data="world")
        result = scorer.score_trace(trace)
        assert result.passed is False
        assert result.score == 0.0

    def test_data_passed_correctly(self):
        def check_data(data: dict) -> float:
            assert data["input"] == "hello"
            assert data["output"] == "world"
            assert data["latency_ms"] == 100.0
            return 1.0

        scorer = CustomScorer(callable=check_data, name="data_check")
        trace = create_trace(input_data="hello", output_data="world", latency_ms=100.0)
        result = scorer.score_trace(trace)
        assert result.passed is True

    def test_with_golden(self):
        def check_golden(data: dict) -> float:
            return 1.0 if data.get("expected_output") == "expected" else 0.0

        scorer = CustomScorer(callable=check_golden, name="golden_check")
        trace = create_trace(input_data="q", output_data="a")
        golden = GoldenRecord(expected_output="expected")
        result = scorer.score_with_golden(trace, golden)
        assert result.passed is True

    def test_bad_return_type(self):
        scorer = CustomScorer(callable=bad_return, threshold=0.5, name="bad")
        trace = create_trace(input_data="hello", output_data="world")
        with pytest.raises(ScorerError, match="must return a float"):
            scorer.score_trace(trace)

    def test_no_callable_raises(self):
        with pytest.raises(ScorerError, match="requires a 'callable'"):
            CustomScorer(callable=None)

    def test_name_and_tier(self):
        scorer = CustomScorer(callable=always_pass, name="my_scorer", tier="t2")
        assert scorer.name == "my_scorer"
        assert scorer.tier == Tier.T2

    def test_validate_config(self):
        scorer = CustomScorer(callable=always_pass, threshold=0.5)
        assert scorer.validate_config() == []

    def test_validate_config_bad_threshold(self):
        scorer = CustomScorer(callable=always_pass, threshold=1.5)
        errors = scorer.validate_config()
        assert any("threshold" in e for e in errors)

    def test_import_from_dotted_path(self):
        # Import a module-level function
        scorer = CustomScorer(
            callable="tests.unit.scorers.test_custom.always_pass",
            threshold=0.0,
            name="import_test",
        )
        assert scorer._fn is not None
        trace = create_trace(input_data="x", output_data="y")
        result = scorer.score_trace(trace)
        assert result.passed is True

    def test_import_bad_path(self):
        with pytest.raises(ScorerError, match="Failed to import"):
            CustomScorer(callable="nonexistent.module.function")

    def test_exception_in_callable(self):
        def raiser(data: dict) -> float:
            raise RuntimeError("boom")

        scorer = CustomScorer(callable=raiser, name="raiser")
        trace = create_trace(input_data="x", output_data="y")
        result = scorer.score_trace(trace)
        assert result.passed is False
        assert "boom" in result.details.get("error", "")
