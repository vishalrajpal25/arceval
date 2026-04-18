"""Tests for the latency scorer."""

from arceval.core.tier import Tier
from arceval.core.trace_model import Trace, create_trace
from arceval.scorers.builtin.latency import LatencyScorer


class TestLatencyScorer:
    def test_pass_under_threshold(self):
        scorer = LatencyScorer(threshold_ms=2000.0)
        trace = create_trace(latency_ms=500.0)
        result = scorer.score_trace(trace)
        assert result.passed is True
        assert result.score == 1.0
        assert result.details["latency_ms"] == 500.0

    def test_fail_over_threshold(self):
        scorer = LatencyScorer(threshold_ms=1000.0)
        trace = create_trace(latency_ms=1500.0)
        result = scorer.score_trace(trace)
        assert result.passed is False
        assert result.score < 1.0
        assert result.details["latency_ms"] == 1500.0

    def test_exact_threshold_passes(self):
        scorer = LatencyScorer(threshold_ms=1000.0)
        trace = create_trace(latency_ms=1000.0)
        result = scorer.score_trace(trace)
        assert result.passed is True

    def test_missing_latency_fails(self):
        scorer = LatencyScorer(threshold_ms=2000.0)
        trace = create_trace()  # no latency_ms
        result = scorer.score_trace(trace)
        assert result.passed is False
        assert result.score is None
        assert "error" in result.details

    def test_name_and_tier(self):
        scorer = LatencyScorer(name="my_latency", tier="t2")
        assert scorer.name == "my_latency"
        assert scorer.tier == Tier.T2

    def test_default_tier_is_t1(self):
        scorer = LatencyScorer()
        assert scorer.tier == Tier.T1

    def test_score_with_golden_delegates(self):
        from arceval.core.protocols import GoldenRecord
        scorer = LatencyScorer(threshold_ms=2000.0)
        trace = create_trace(latency_ms=100.0)
        golden = GoldenRecord()
        result = scorer.score_with_golden(trace, golden)
        assert result.passed is True

    def test_validate_config_valid(self):
        scorer = LatencyScorer(threshold_ms=1000.0, percentile=95)
        assert scorer.validate_config() == []

    def test_validate_config_bad_threshold(self):
        scorer = LatencyScorer(threshold_ms=-1.0)
        errors = scorer.validate_config()
        assert any("threshold_ms" in e for e in errors)

    def test_validate_config_bad_percentile(self):
        scorer = LatencyScorer(percentile=75)
        errors = scorer.validate_config()
        assert any("percentile" in e for e in errors)

    def test_score_at_double_threshold_is_zero(self):
        scorer = LatencyScorer(threshold_ms=1000.0)
        trace = create_trace(latency_ms=2000.0)
        result = scorer.score_trace(trace)
        assert result.score == 0.0

    def test_score_beyond_double_threshold(self):
        scorer = LatencyScorer(threshold_ms=1000.0)
        trace = create_trace(latency_ms=5000.0)
        result = scorer.score_trace(trace)
        assert result.score == 0.0
