"""Tests for the availability scorer."""

from arceval.core.trace_model import create_trace
from arceval.scorers.builtin.availability import AvailabilityScorer


class TestAvailabilityScorer:
    def test_success_200(self):
        scorer = AvailabilityScorer()
        trace = create_trace(status_code=200)
        result = scorer.score_trace(trace)
        assert result.passed is True
        assert result.score == 1.0

    def test_server_error_500(self):
        scorer = AvailabilityScorer()
        trace = create_trace(status_code=500)
        result = scorer.score_trace(trace)
        assert result.passed is False
        assert result.score == 0.0

    def test_client_error_400_is_available(self):
        scorer = AvailabilityScorer()
        trace = create_trace(status_code=400)
        result = scorer.score_trace(trace)
        assert result.passed is True  # 4xx is not a server outage

    def test_error_type_is_unavailable(self):
        scorer = AvailabilityScorer()
        trace = create_trace(error_type="connection_refused")
        result = scorer.score_trace(trace)
        assert result.passed is False

    def test_no_status_no_error(self):
        scorer = AvailabilityScorer()
        trace = create_trace()
        result = scorer.score_trace(trace)
        assert result.passed is True

    def test_validate_config_valid(self):
        scorer = AvailabilityScorer()
        assert scorer.validate_config() == []

    def test_validate_config_bad_threshold(self):
        scorer = AvailabilityScorer(threshold_pct=150.0)
        errors = scorer.validate_config()
        assert len(errors) > 0

    def test_validate_config_bad_window(self):
        scorer = AvailabilityScorer(window_minutes=-1)
        errors = scorer.validate_config()
        assert len(errors) > 0
