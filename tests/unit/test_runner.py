"""Tests for arceval.testing.runner."""

import json

from arceval.core.protocols import GoldenRecord
from arceval.core.trace_model import create_trace
from arceval.scorers.builtin.latency import LatencyScorer
from arceval.scorers.builtin.error_rate import ErrorRateScorer
from arceval.testing.gates import GateVerdict
from arceval.testing.runner import EvalTestRunner, generate_report, save_report


class TestEvalTestRunner:
    def test_run_basic(self):
        scorers = [
            LatencyScorer(threshold_ms=2000.0, name="latency"),
            ErrorRateScorer(name="error_rate"),
        ]
        traces = [
            create_trace(latency_ms=500.0, status_code=200),
            create_trace(latency_ms=100.0, status_code=200),
        ]
        runner = EvalTestRunner(scorers)
        result = runner.run(traces)

        assert result.traces_scored == 2
        assert len(result.results) == 4  # 2 traces * 2 scorers
        assert result.all_passed is True
        assert result.gate_result is not None
        assert result.gate_result.verdict == GateVerdict.PASS

    def test_run_with_failures(self):
        scorers = [LatencyScorer(threshold_ms=100.0, name="latency")]
        traces = [create_trace(latency_ms=500.0)]
        runner = EvalTestRunner(scorers)
        result = runner.run(traces)

        assert result.all_passed is False
        assert result.gate_result.verdict == GateVerdict.FAIL

    def test_run_with_tier_filter(self):
        scorers = [
            LatencyScorer(threshold_ms=2000.0, name="latency", tier="t1"),
            ErrorRateScorer(name="error_rate", tier="t2"),
        ]
        traces = [create_trace(latency_ms=500.0, status_code=200)]
        runner = EvalTestRunner(scorers)
        result = runner.run(traces, tiers=["t1"])

        assert len(result.results) == 1  # only t1 scorer ran
        assert result.results[0].scorer_name == "latency"

    def test_run_with_golden_records(self):
        scorers = [LatencyScorer(threshold_ms=2000.0, name="latency")]
        traces = [create_trace(latency_ms=100.0)]
        golden = [GoldenRecord(input_data={"q": "test"}, expected_output="answer")]

        runner = EvalTestRunner(scorers)
        result = runner.run(traces, golden_records=golden)

        assert len(result.results) == 1
        assert result.all_passed is True

    def test_pass_rate(self):
        scorers = [LatencyScorer(threshold_ms=200.0, name="latency")]
        traces = [
            create_trace(latency_ms=100.0),
            create_trace(latency_ms=300.0),
        ]
        runner = EvalTestRunner(scorers)
        result = runner.run(traces)
        assert result.pass_rate == 0.5

    def test_empty_traces(self):
        scorers = [LatencyScorer(threshold_ms=2000.0, name="latency")]
        runner = EvalTestRunner(scorers)
        result = runner.run([])
        assert result.traces_scored == 0
        assert result.results == []


class TestGenerateReport:
    def _run_result(self):
        scorers = [
            LatencyScorer(threshold_ms=2000.0, name="latency"),
            ErrorRateScorer(name="error_rate"),
        ]
        traces = [
            create_trace(latency_ms=500.0, status_code=200),
            create_trace(latency_ms=3000.0, status_code=500),
        ]
        runner = EvalTestRunner(scorers)
        return runner.run(traces)

    def test_markdown_report(self):
        result = self._run_result()
        report = generate_report(result, format="markdown")
        assert "# ArcEval Test Report" in report
        assert "Tier Summary" in report
        assert "latency" in report
        assert "PASS" in report or "FAIL" in report

    def test_json_report(self):
        result = self._run_result()
        report = generate_report(result, format="json")
        data = json.loads(report)
        assert "results" in data
        assert "verdict" in data
        assert len(data["results"]) > 0


class TestSaveReport:
    def test_save_markdown(self, tmp_path):
        path = save_report("# Test", str(tmp_path), format="markdown")
        assert path.exists()
        assert path.suffix == ".md"
        assert path.read_text() == "# Test"

    def test_save_json(self, tmp_path):
        path = save_report('{"a": 1}', str(tmp_path), format="json")
        assert path.exists()
        assert path.suffix == ".json"
