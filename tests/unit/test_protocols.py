"""Tests for arceval.core.protocols."""

from arceval.core.protocols import (
    AlertSink,
    CaptureMiddleware,
    GoldenRecord,
    ScoreResult,
    Scorer,
    ScorerMode,
    TraceBackend,
)
from arceval.core.tier import Tier
from arceval.core.trace_model import Trace


class TestScoreResult:
    def test_create(self):
        r = ScoreResult(
            scorer_name="latency",
            tier=Tier.T1,
            passed=True,
            score=0.95,
            threshold=2000.0,
            trace_id="abc",
            timestamp="2026-01-01T00:00:00Z",
        )
        assert r.scorer_name == "latency"
        assert r.passed is True
        assert r.score == 0.95
        assert r.details == {}

    def test_with_details(self):
        r = ScoreResult(
            scorer_name="error_rate",
            tier=Tier.T1,
            passed=False,
            score=0.0,
            threshold=0.5,
            details={"is_error": True, "error_type": "timeout"},
        )
        assert r.details["is_error"] is True


class TestGoldenRecord:
    def test_defaults(self):
        g = GoldenRecord()
        assert g.input_data == {}
        assert g.expected_output is None
        assert g.metadata == {}

    def test_with_data(self):
        g = GoldenRecord(
            input_data={"query": "AAPL"},
            expected_output={"price": 150.0},
            metadata={"tool_name": "get_pricing"},
        )
        assert g.input_data["query"] == "AAPL"


class TestScorerMode:
    def test_values(self):
        assert ScorerMode.TESTING == "testing"
        assert ScorerMode.MONITORING == "monitoring"


class TestProtocolsAreRuntimeCheckable:
    def test_trace_backend_protocol(self):
        class FakeBackend:
            def emit(self, traces): ...
            def query(self, **kw): ...
            def store_scores(self, scores): ...
            def health_check(self): ...

        assert isinstance(FakeBackend(), TraceBackend)

    def test_alert_sink_protocol(self):
        class FakeAlert:
            def send(self, alert): ...

        assert isinstance(FakeAlert(), AlertSink)
