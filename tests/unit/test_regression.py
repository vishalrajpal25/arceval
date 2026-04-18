"""Tests for regression detection."""

from arceval.core.protocols import ScoreResult
from arceval.core.tier import Tier
from arceval.core.trace_model import create_trace
from arceval.scorers.builtin.latency import LatencyScorer
from arceval.scorers.builtin.error_rate import ErrorRateScorer
from arceval.testing.regression import detect_regressions, format_regression_report
from arceval.testing.runner import EvalTestRunner


def _make_run(latency_values: list[float], project: str = "test") -> "TestRunResult":
    scorers = [LatencyScorer(threshold_ms=2000.0, name="latency")]
    traces = [create_trace(latency_ms=v) for v in latency_values]
    runner = EvalTestRunner(scorers)
    return runner.run(traces)


class TestDetectRegressions:
    def test_no_regression(self):
        baseline = _make_run([100.0, 200.0])
        current = _make_run([100.0, 150.0])
        result = detect_regressions(baseline, current)
        assert not result.has_regressions

    def test_regression_pass_to_fail(self):
        baseline = _make_run([100.0, 200.0])  # all pass
        current = _make_run([3000.0, 4000.0])  # all fail
        result = detect_regressions(baseline, current)
        assert result.has_regressions
        assert len(result.regressions) == 1
        assert result.regressions[0].scorer_name == "latency"

    def test_regression_score_drop(self):
        baseline = _make_run([100.0, 200.0])
        current = _make_run([1500.0, 1800.0])  # still pass but score drops
        result = detect_regressions(baseline, current, threshold=0.0)
        # Score dropped, may or may not be regression depending on pass/fail
        assert len(result.diffs) == 1

    def test_improvement(self):
        # Use a tight threshold so baseline scores are lower
        scorers = [LatencyScorer(threshold_ms=1000.0, name="latency")]
        baseline_traces = [create_trace(latency_ms=1500.0), create_trace(latency_ms=1800.0)]
        current_traces = [create_trace(latency_ms=100.0), create_trace(latency_ms=200.0)]
        runner = EvalTestRunner(scorers)
        baseline = runner.run(baseline_traces)
        current = runner.run(current_traces)
        result = detect_regressions(baseline, current)
        assert not result.has_regressions
        assert len(result.improvements) > 0

    def test_format_report(self):
        baseline = _make_run([100.0])
        current = _make_run([3000.0])
        result = detect_regressions(baseline, current)
        report = format_regression_report(result)
        assert "Regression" in report
        assert "latency" in report

    def test_empty_runs(self):
        baseline = _make_run([])
        current = _make_run([])
        result = detect_regressions(baseline, current)
        assert not result.has_regressions
        assert len(result.diffs) == 0
