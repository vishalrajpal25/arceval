"""Tests for the token usage scorer."""

from arceval.core.trace_model import create_trace
from arceval.scorers.builtin.token_usage import TokenUsageScorer


class TestTokenUsageScorer:
    def test_normal_usage(self):
        scorer = TokenUsageScorer(baseline_tokens=1000, anomaly_multiplier=3.0)
        trace = create_trace(
            gen_ai_usage_input_tokens=400,
            gen_ai_usage_output_tokens=300,
        )
        result = scorer.score_trace(trace)
        assert result.passed is True
        assert result.score == 1.0

    def test_anomalous_usage(self):
        scorer = TokenUsageScorer(baseline_tokens=1000, anomaly_multiplier=3.0)
        trace = create_trace(
            gen_ai_usage_input_tokens=2000,
            gen_ai_usage_output_tokens=2000,
        )  # total 4000 > 3000 threshold
        result = scorer.score_trace(trace)
        assert result.passed is False
        assert result.score == 0.0

    def test_borderline_usage(self):
        scorer = TokenUsageScorer(baseline_tokens=1000, anomaly_multiplier=3.0)
        trace = create_trace(
            gen_ai_usage_input_tokens=1500,
            gen_ai_usage_output_tokens=500,
        )  # total 2000, between 1000 and 3000
        result = scorer.score_trace(trace)
        assert result.passed is True
        assert 0.0 < result.score < 1.0

    def test_no_token_data(self):
        scorer = TokenUsageScorer(baseline_tokens=1000)
        trace = create_trace()
        result = scorer.score_trace(trace)
        assert result.passed is True
        assert result.details.get("total_tokens") == 0

    def test_exact_threshold(self):
        scorer = TokenUsageScorer(baseline_tokens=1000, anomaly_multiplier=3.0)
        trace = create_trace(
            gen_ai_usage_input_tokens=3000,
            gen_ai_usage_output_tokens=0,
        )  # total == threshold
        result = scorer.score_trace(trace)
        assert result.passed is True  # not strictly greater
        assert result.score == 0.0

    def test_validate_config_valid(self):
        scorer = TokenUsageScorer()
        assert scorer.validate_config() == []

    def test_validate_config_bad_baseline(self):
        scorer = TokenUsageScorer(baseline_tokens=-1)
        errors = scorer.validate_config()
        assert any("baseline" in e for e in errors)

    def test_validate_config_bad_multiplier(self):
        scorer = TokenUsageScorer(anomaly_multiplier=0.5)
        errors = scorer.validate_config()
        assert any("multiplier" in e for e in errors)
