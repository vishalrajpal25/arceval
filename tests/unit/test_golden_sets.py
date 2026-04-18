"""Tests for arceval.testing.golden_sets."""

import json
import textwrap

import pytest

from arceval.core.exceptions import GoldenSetError
from arceval.testing.golden_sets import (
    load_golden_set,
    load_golden_sets_from_config,
    validate_golden_set,
)


class TestLoadGoldenSetJSONL:
    def test_load_valid(self, tmp_path):
        f = tmp_path / "test.jsonl"
        f.write_text(
            '{"input": {"query": "AAPL"}, "expected_output": {"price": 150}}\n'
            '{"input": {"query": "MSFT"}, "expected_output": {"price": 300}}\n'
        )
        records = load_golden_set(f, format="jsonl")
        assert len(records) == 2
        assert records[0].input_data == {"query": "AAPL"}
        assert records[0].expected_output == {"price": 150}

    def test_load_with_metadata(self, tmp_path):
        f = tmp_path / "test.jsonl"
        f.write_text('{"input": {"q": "test"}, "expected_output": "ok", "metadata": {"tool_name": "search"}}\n')
        records = load_golden_set(f, format="jsonl")
        assert records[0].metadata == {"tool_name": "search"}

    def test_file_not_found(self):
        with pytest.raises(GoldenSetError, match="not found"):
            load_golden_set("/nonexistent/file.jsonl")

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        with pytest.raises(GoldenSetError, match="empty"):
            load_golden_set(f, format="jsonl")

    def test_invalid_json(self, tmp_path):
        f = tmp_path / "bad.jsonl"
        f.write_text("not valid json\n")
        with pytest.raises(GoldenSetError, match="Invalid JSON"):
            load_golden_set(f, format="jsonl")

    def test_blank_lines_skipped(self, tmp_path):
        f = tmp_path / "test.jsonl"
        f.write_text('{"input": {"q": "a"}, "expected_output": 1}\n\n{"input": {"q": "b"}, "expected_output": 2}\n')
        records = load_golden_set(f, format="jsonl")
        assert len(records) == 2


class TestLoadGoldenSetJSON:
    def test_load_valid(self, tmp_path):
        f = tmp_path / "test.json"
        data = [
            {"input": {"q": "a"}, "expected_output": 1},
            {"input": {"q": "b"}, "expected_output": 2},
        ]
        f.write_text(json.dumps(data))
        records = load_golden_set(f, format="json")
        assert len(records) == 2

    def test_not_array(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"not": "an array"}')
        with pytest.raises(GoldenSetError, match="array"):
            load_golden_set(f, format="json")


class TestLoadGoldenSetCSV:
    def test_load_valid(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text(textwrap.dedent("""\
            input,expected_output,tool_name
            "{""query"": ""AAPL""}","{""price"": 150}",get_pricing
        """))
        records = load_golden_set(f, format="csv")
        assert len(records) == 1
        assert records[0].metadata.get("tool_name") == "get_pricing"


class TestLoadGoldenSetUnsupported:
    def test_unsupported_format(self, tmp_path):
        f = tmp_path / "test.parquet"
        f.write_text("dummy")
        with pytest.raises(GoldenSetError, match="Unsupported"):
            load_golden_set(f, format="parquet")


class TestValidateGoldenSet:
    def test_valid(self):
        from arceval.core.protocols import GoldenRecord
        records = [GoldenRecord(input_data={"q": "test"})]
        assert validate_golden_set(records) == []

    def test_empty(self):
        assert "empty" in validate_golden_set([])[0].lower()

    def test_empty_input_data(self):
        from arceval.core.protocols import GoldenRecord
        records = [GoldenRecord(input_data={})]
        errors = validate_golden_set(records)
        assert any("input_data" in e for e in errors)


class TestLoadFromConfig:
    def test_load_multiple(self, tmp_path):
        gs_dir = tmp_path / "golden_sets"
        gs_dir.mkdir()
        (gs_dir / "a.jsonl").write_text('{"input": {"q": "1"}, "expected_output": 1}\n')
        (gs_dir / "b.jsonl").write_text('{"input": {"q": "2"}, "expected_output": 2}\n{"input": {"q": "3"}, "expected_output": 3}\n')

        sets_config = [
            {"name": "set_a", "file": "a.jsonl"},
            {"name": "set_b", "file": "b.jsonl"},
        ]
        result = load_golden_sets_from_config(sets_config, gs_dir)
        assert len(result) == 2
        assert len(result["set_a"]) == 1
        assert len(result["set_b"]) == 2
