"""Tests for the schema compliance scorer."""

import json

from arceval.core.trace_model import create_trace
from arceval.scorers.builtin.schema import SchemaScorer


class TestSchemaScorer:
    SIMPLE_SCHEMA = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "value": {"type": "number"}},
        "required": ["name", "value"],
    }

    def test_valid_output(self):
        scorer = SchemaScorer(schema=self.SIMPLE_SCHEMA)
        trace = create_trace(output_data={"name": "test", "value": 42})
        result = scorer.score_trace(trace)
        assert result.passed is True
        assert result.score == 1.0

    def test_invalid_output(self):
        scorer = SchemaScorer(schema=self.SIMPLE_SCHEMA)
        trace = create_trace(output_data={"name": "test"})  # missing "value"
        result = scorer.score_trace(trace)
        assert result.passed is False
        assert result.score == 0.0
        assert "error" in result.details

    def test_none_output(self):
        scorer = SchemaScorer(schema=self.SIMPLE_SCHEMA)
        trace = create_trace(output_data=None)
        result = scorer.score_trace(trace)
        assert result.passed is False

    def test_no_schema(self):
        scorer = SchemaScorer()
        trace = create_trace(output_data={"a": 1})
        result = scorer.score_trace(trace)
        assert result.passed is False
        assert "no schema" in result.details.get("error", "")

    def test_schema_from_file(self, tmp_path):
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps(self.SIMPLE_SCHEMA))
        scorer = SchemaScorer(schema_path=str(schema_file))
        trace = create_trace(output_data={"name": "x", "value": 1})
        result = scorer.score_trace(trace)
        assert result.passed is True

    def test_schema_from_directory(self, tmp_path):
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        (schema_dir / "search.json").write_text(json.dumps(self.SIMPLE_SCHEMA))
        scorer = SchemaScorer(schema_path=str(schema_dir))

        trace = create_trace(
            output_data={"name": "x", "value": 1},
            attributes={"tool_name": "search"},
        )
        result = scorer.score_trace(trace)
        assert result.passed is True

    def test_validate_config_no_schema(self):
        scorer = SchemaScorer()
        errors = scorer.validate_config()
        assert any("schema" in e.lower() for e in errors)

    def test_validate_config_valid(self):
        scorer = SchemaScorer(schema=self.SIMPLE_SCHEMA)
        assert scorer.validate_config() == []
