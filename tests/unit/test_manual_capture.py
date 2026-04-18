"""Tests for arceval.capture.manual."""

from arceval.backends.file import FileBackend
from arceval.capture.manual import ManualCapture


class TestManualCapture:
    def test_record_creates_trace(self):
        cap = ManualCapture()
        trace = cap.record(
            input_data={"query": "AAPL"},
            output_data={"price": 150},
            latency_ms=100.0,
            status_code=200,
        )
        assert trace.input_data == {"query": "AAPL"}
        assert trace.output_data == {"price": 150}
        assert trace.latency_ms == 100.0
        assert trace.status_code == 200
        assert trace.trace_id  # non-empty

    def test_record_emits_to_backend(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        cap = ManualCapture()
        cap.set_backend(backend)

        cap.record(input_data="hello", output_data="world")

        traces = backend.query()
        assert len(traces) == 1

    def test_record_without_backend(self):
        cap = ManualCapture()
        trace = cap.record(input_data="a", output_data="b")
        assert trace is not None  # no error even without backend

    def test_record_batch(self):
        cap = ManualCapture()
        records = [
            {"input_data": "a", "output_data": "1"},
            {"input_data": "b", "output_data": "2"},
            {"input_data": "c", "output_data": "3"},
        ]
        traces = cap.record_batch(records)
        assert len(traces) == 3

    def test_wrap_is_noop(self):
        cap = ManualCapture()
        endpoint = object()
        assert cap.wrap(endpoint) is endpoint

    def test_record_with_attributes(self):
        cap = ManualCapture()
        trace = cap.record(
            input_data="q",
            output_data="a",
            gen_ai_system="openai",
            gen_ai_operation="chat",
            attributes={"tool_name": "search"},
        )
        assert trace.gen_ai_system == "openai"
        assert trace.attributes["tool_name"] == "search"
