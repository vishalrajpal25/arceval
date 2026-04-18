"""Tests for the completeness scorer."""

import json

from arceval.core.trace_model import create_trace
from arceval.scorers.builtin.completeness import CompletenessScorer


class TestCompletenessScorer:
    def test_all_fields_present(self):
        scorer = CompletenessScorer(required_fields=["name", "value"])
        trace = create_trace(output_data={"name": "test", "value": 42})
        result = scorer.score_trace(trace)
        assert result.passed is True
        assert result.score == 1.0

    def test_missing_field(self):
        scorer = CompletenessScorer(required_fields=["name", "value", "extra"])
        trace = create_trace(output_data={"name": "test", "value": 42})
        result = scorer.score_trace(trace)
        assert result.passed is False
        assert result.details["missing"] == ["extra"]
        assert result.score < 1.0

    def test_null_field_counts_as_missing(self):
        scorer = CompletenessScorer(required_fields=["name", "value"])
        trace = create_trace(output_data={"name": "test", "value": None})
        result = scorer.score_trace(trace)
        assert result.passed is False
        assert "value" in result.details["missing"]

    def test_none_output(self):
        scorer = CompletenessScorer(required_fields=["name"])
        trace = create_trace(output_data=None)
        result = scorer.score_trace(trace)
        assert result.passed is False

    def test_non_dict_output(self):
        scorer = CompletenessScorer(required_fields=["name"])
        trace = create_trace(output_data="just a string")
        result = scorer.score_trace(trace)
        assert result.passed is False

    def test_no_required_fields(self):
        scorer = CompletenessScorer(required_fields=[])
        trace = create_trace(output_data={"anything": "goes"})
        result = scorer.score_trace(trace)
        assert result.passed is True

    def test_from_manifest_file(self, tmp_path):
        manifest = tmp_path / "fields.json"
        manifest.write_text(json.dumps(["name", "value"]))
        scorer = CompletenessScorer(required_fields_path=str(manifest))
        trace = create_trace(output_data={"name": "x", "value": 1})
        result = scorer.score_trace(trace)
        assert result.passed is True

    def test_from_manifest_directory(self, tmp_path):
        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()
        (manifest_dir / "search.json").write_text(json.dumps(["title", "url"]))
        scorer = CompletenessScorer(required_fields_path=str(manifest_dir))
        trace = create_trace(
            output_data={"title": "Test", "url": "http://example.com"},
            attributes={"tool_name": "search"},
        )
        result = scorer.score_trace(trace)
        assert result.passed is True

    def test_validate_config_no_fields(self):
        scorer = CompletenessScorer()
        errors = scorer.validate_config()
        assert any("required_fields" in e for e in errors)

    def test_validate_config_valid(self):
        scorer = CompletenessScorer(required_fields=["a"])
        assert scorer.validate_config() == []

    def test_score_partial(self):
        scorer = CompletenessScorer(required_fields=["a", "b", "c", "d"])
        trace = create_trace(output_data={"a": 1, "b": 2})
        result = scorer.score_trace(trace)
        assert result.score == 0.5
