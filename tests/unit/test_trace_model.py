"""Tests for arceval.core.trace_model."""

from arceval.core.trace_model import Trace, create_trace


class TestTrace:
    def test_create_minimal(self):
        t = Trace(trace_id="abc", span_id="def")
        assert t.trace_id == "abc"
        assert t.span_id == "def"
        assert t.parent_span_id is None
        assert t.latency_ms is None
        assert t.attributes == {}

    def test_frozen(self):
        t = Trace(trace_id="abc", span_id="def")
        import pytest
        with pytest.raises(AttributeError):
            t.trace_id = "xyz"  # type: ignore[misc]

    def test_full_attributes(self):
        t = Trace(
            trace_id="abc",
            span_id="def",
            gen_ai_system="openai",
            gen_ai_operation="chat",
            latency_ms=150.0,
            status_code=200,
            attributes={"tool_name": "search"},
            input_data={"query": "test"},
            output_data={"result": "ok"},
        )
        assert t.gen_ai_system == "openai"
        assert t.latency_ms == 150.0
        assert t.attributes["tool_name"] == "search"


class TestCreateTrace:
    def test_auto_generates_ids(self):
        t = create_trace(latency_ms=100.0)
        assert len(t.trace_id) == 32
        assert len(t.span_id) == 16
        assert t.timestamp_start != ""
        assert t.latency_ms == 100.0

    def test_unique_ids(self):
        t1 = create_trace()
        t2 = create_trace()
        assert t1.trace_id != t2.trace_id
        assert t1.span_id != t2.span_id

    def test_with_attributes(self):
        t = create_trace(
            gen_ai_system="anthropic",
            attributes={"tool_name": "calculator"},
        )
        assert t.gen_ai_system == "anthropic"
        assert t.attributes["tool_name"] == "calculator"
