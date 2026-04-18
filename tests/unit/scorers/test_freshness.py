"""Tests for the freshness scorer."""

from datetime import datetime, timedelta, timezone

from arceval.core.trace_model import create_trace
from arceval.scorers.builtin.freshness import FreshnessScorer


class TestFreshnessScorer:
    def test_fresh_data(self):
        scorer = FreshnessScorer(max_age_seconds=3600)
        now = datetime.now(timezone.utc)
        trace = create_trace(output_data={"data_timestamp": now.isoformat()})
        result = scorer.score_trace(trace)
        assert result.passed is True
        assert result.score == 1.0

    def test_stale_data(self):
        scorer = FreshnessScorer(max_age_seconds=60)
        old_time = datetime.now(timezone.utc) - timedelta(hours=1)
        trace = create_trace(output_data={"data_timestamp": old_time.isoformat()})
        result = scorer.score_trace(trace)
        assert result.passed is False

    def test_custom_timestamp_field(self):
        scorer = FreshnessScorer(timestamp_field="updated_at", max_age_seconds=3600)
        now = datetime.now(timezone.utc)
        trace = create_trace(output_data={"updated_at": now.isoformat()})
        result = scorer.score_trace(trace)
        assert result.passed is True

    def test_missing_timestamp_field(self):
        scorer = FreshnessScorer()
        trace = create_trace(output_data={"no_timestamp": "here"})
        result = scorer.score_trace(trace)
        assert result.passed is False
        assert "not found" in result.details.get("error", "")

    def test_non_dict_output(self):
        scorer = FreshnessScorer()
        trace = create_trace(output_data="not a dict")
        result = scorer.score_trace(trace)
        assert result.passed is False

    def test_invalid_timestamp_format(self):
        scorer = FreshnessScorer()
        trace = create_trace(output_data={"data_timestamp": "not-a-date"})
        result = scorer.score_trace(trace)
        assert result.passed is False
        assert "invalid" in result.details.get("error", "").lower()

    def test_validate_config_valid(self):
        scorer = FreshnessScorer(max_age_seconds=60)
        assert scorer.validate_config() == []

    def test_validate_config_bad_max_age(self):
        scorer = FreshnessScorer(max_age_seconds=-1)
        errors = scorer.validate_config()
        assert len(errors) > 0
