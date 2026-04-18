"""Tests for the error rate scorer."""

from arceval.core.tier import Tier
from arceval.core.trace_model import create_trace
from arceval.scorers.builtin.error_rate import ErrorRateScorer


class TestErrorRateScorer:
    def test_success_trace_passes(self):
        scorer = ErrorRateScorer()
        trace = create_trace(status_code=200)
        result = scorer.score_trace(trace)
        assert result.passed is True
        assert result.score == 1.0

    def test_error_status_code_fails(self):
        scorer = ErrorRateScorer()
        trace = create_trace(status_code=500)
        result = scorer.score_trace(trace)
        assert result.passed is False
        assert result.score == 0.0
        assert result.details["is_error"] is True

    def test_error_type_fails(self):
        scorer = ErrorRateScorer()
        trace = create_trace(error_type="timeout")
        result = scorer.score_trace(trace)
        assert result.passed is False
        assert result.details["error_type"] == "timeout"

    def test_400_is_error(self):
        scorer = ErrorRateScorer()
        trace = create_trace(status_code=400)
        result = scorer.score_trace(trace)
        assert result.passed is False

    def test_399_is_not_error(self):
        scorer = ErrorRateScorer()
        trace = create_trace(status_code=399)
        result = scorer.score_trace(trace)
        assert result.passed is True

    def test_no_status_no_error_passes(self):
        scorer = ErrorRateScorer()
        trace = create_trace()
        result = scorer.score_trace(trace)
        assert result.passed is True

    def test_name_and_tier(self):
        scorer = ErrorRateScorer(name="my_errors", tier="t2")
        assert scorer.name == "my_errors"
        assert scorer.tier == Tier.T2

    def test_default_tier_is_t1(self):
        scorer = ErrorRateScorer()
        assert scorer.tier == Tier.T1

    def test_validate_config_valid(self):
        scorer = ErrorRateScorer(threshold_pct=5.0)
        assert scorer.validate_config() == []

    def test_validate_config_out_of_range(self):
        scorer = ErrorRateScorer(threshold_pct=150.0)
        errors = scorer.validate_config()
        assert len(errors) > 0

    def test_score_with_golden_delegates(self):
        from arceval.core.protocols import GoldenRecord
        scorer = ErrorRateScorer()
        trace = create_trace(status_code=200)
        result = scorer.score_with_golden(trace, GoldenRecord())
        assert result.passed is True
