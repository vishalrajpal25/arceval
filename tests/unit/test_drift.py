"""Tests for metric drift detection."""

from arceval.core.protocols import ScoreResult
from arceval.core.tier import Tier
from arceval.monitoring.drift import detect_drift, format_drift_report


def _scores(scorer: str, values: list[float]) -> list[ScoreResult]:
    return [
        ScoreResult(
            scorer_name=scorer,
            tier=Tier.T1,
            passed=True,
            score=v,
            threshold=None,
            trace_id=f"t{i}",
            timestamp="2026-01-01",
        )
        for i, v in enumerate(values)
    ]


class TestDetectDrift:
    def test_no_drift(self):
        baseline = _scores("latency", [0.9, 0.91, 0.89, 0.9, 0.92])
        current = _scores("latency", [0.9, 0.91, 0.89])
        results = detect_drift(baseline, current)
        assert len(results) == 1
        assert not results[0].drifted

    def test_drift_detected(self):
        baseline = _scores("latency", [0.9, 0.91, 0.89, 0.9, 0.92])
        current = _scores("latency", [0.5, 0.51, 0.49])  # big drop
        results = detect_drift(baseline, current)
        assert len(results) == 1
        assert results[0].drifted is True
        assert results[0].z_score is not None

    def test_no_variance_same_mean(self):
        baseline = _scores("latency", [1.0, 1.0, 1.0])
        current = _scores("latency", [1.0, 1.0])
        results = detect_drift(baseline, current)
        assert not results[0].drifted

    def test_no_variance_different_mean(self):
        baseline = _scores("latency", [1.0, 1.0, 1.0])
        current = _scores("latency", [0.5, 0.5])
        results = detect_drift(baseline, current)
        assert results[0].drifted is True

    def test_multiple_scorers(self):
        baseline = _scores("a", [0.9, 0.9]) + _scores("b", [0.8, 0.8])
        current = _scores("a", [0.9]) + _scores("b", [0.3])
        results = detect_drift(baseline, current)
        assert len(results) == 2
        drifted = [r for r in results if r.drifted]
        assert len(drifted) == 1
        assert drifted[0].scorer_name == "b"

    def test_empty_baseline(self):
        baseline: list[ScoreResult] = []
        current = _scores("latency", [0.9])
        results = detect_drift(baseline, current)
        assert len(results) == 1
        assert not results[0].drifted

    def test_custom_threshold(self):
        baseline = _scores("latency", [0.9, 0.91, 0.89, 0.9])
        current = _scores("latency", [0.85, 0.86])  # slight drop
        results_strict = detect_drift(baseline, current, z_threshold=1.0)
        results_lenient = detect_drift(baseline, current, z_threshold=10.0)
        # Strict should flag, lenient should not
        assert results_strict[0].drifted is True
        assert results_lenient[0].drifted is False

    def test_format_report(self):
        baseline = _scores("latency", [0.9, 0.9, 0.9])
        current = _scores("latency", [0.5, 0.5])
        results = detect_drift(baseline, current)
        report = format_drift_report(results)
        assert "Drift" in report
        assert "latency" in report
