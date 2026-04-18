"""Integration tests for the file backend."""

import json

from arceval.backends.file import FileBackend
from arceval.core.protocols import ScoreResult
from arceval.core.tier import Tier
from arceval.core.trace_model import Trace, create_trace


class TestFileBackend:
    def setup_method(self, tmp_path=None):
        pass

    def test_health_check(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        assert backend.health_check() is True

    def test_emit_and_query(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        t1 = create_trace(latency_ms=100.0, gen_ai_system="openai")
        t2 = create_trace(latency_ms=200.0, gen_ai_system="anthropic")

        backend.emit([t1, t2])

        results = backend.query()
        assert len(results) == 2
        assert results[0].latency_ms == 100.0
        assert results[1].latency_ms == 200.0

    def test_query_with_limit(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        traces = [create_trace(latency_ms=float(i)) for i in range(10)]
        backend.emit(traces)

        results = backend.query(limit=3)
        assert len(results) == 3

    def test_query_with_filters(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        t1 = create_trace(attributes={"tool_name": "search"})
        t2 = create_trace(attributes={"tool_name": "calc"})
        backend.emit([t1, t2])

        results = backend.query(filters={"tool_name": "search"})
        assert len(results) == 1
        assert results[0].attributes["tool_name"] == "search"

    def test_query_empty(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        results = backend.query()
        assert results == []

    def test_store_scores(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        score = ScoreResult(
            scorer_name="latency",
            tier=Tier.T1,
            passed=True,
            score=0.95,
            threshold=2000.0,
            trace_id="abc",
            timestamp="2026-01-01T00:00:00Z",
        )
        backend.store_scores([score])

        assert backend.scores_file.exists()
        with open(backend.scores_file) as f:
            data = json.loads(f.readline())
        assert data["scorer_name"] == "latency"
        assert data["passed"] is True
        assert data["tier"] == "t1"

    def test_emit_appends(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        backend.emit([create_trace()])
        backend.emit([create_trace()])

        results = backend.query()
        assert len(results) == 2
