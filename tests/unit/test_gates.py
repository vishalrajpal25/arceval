"""Tests for arceval.testing.gates."""

from arceval.core.protocols import ScoreResult
from arceval.core.tier import Tier
from arceval.testing.gates import GateVerdict, TierSummary, evaluate_gates


def _result(scorer: str, tier: Tier, passed: bool, score: float = 1.0) -> ScoreResult:
    return ScoreResult(
        scorer_name=scorer,
        tier=tier,
        passed=passed,
        score=score,
        threshold=None,
        trace_id="test",
        timestamp="2026-01-01",
    )


class TestTierSummary:
    def test_all_passed(self):
        s = TierSummary(tier=Tier.T1, total=3, passed=3, failed=0)
        assert s.all_passed is True
        assert s.pass_rate == 1.0

    def test_some_failed(self):
        s = TierSummary(tier=Tier.T1, total=4, passed=3, failed=1)
        assert s.all_passed is False
        assert s.pass_rate == 0.75

    def test_empty(self):
        s = TierSummary(tier=Tier.T1)
        assert s.all_passed is False
        assert s.pass_rate == 0.0


class TestEvaluateGates:
    def test_all_pass(self):
        results = [
            _result("latency", Tier.T1, True),
            _result("error_rate", Tier.T1, True),
        ]
        gate = evaluate_gates(results)
        assert gate.verdict == GateVerdict.PASS
        assert gate.exit_code == 0
        assert gate.failures == []
        assert gate.warnings == []

    def test_t1_failure(self):
        results = [
            _result("latency", Tier.T1, False, 0.5),
            _result("error_rate", Tier.T1, True),
        ]
        gate = evaluate_gates(results, fail_on="t1")
        assert gate.verdict == GateVerdict.FAIL
        assert gate.exit_code == 1
        assert len(gate.failures) == 1
        assert "latency" in gate.failures[0]

    def test_t2_warning(self):
        results = [
            _result("latency", Tier.T1, True),
            _result("freshness", Tier.T2, False, 0.3),
        ]
        gate = evaluate_gates(results, fail_on="t1", warn_on="t2")
        assert gate.verdict == GateVerdict.WARN
        assert gate.exit_code == 0
        assert len(gate.warnings) == 1

    def test_t1_fail_overrides_t2_warn(self):
        results = [
            _result("latency", Tier.T1, False, 0.5),
            _result("freshness", Tier.T2, False, 0.3),
        ]
        gate = evaluate_gates(results, fail_on="t1", warn_on="t2")
        assert gate.verdict == GateVerdict.FAIL
        assert len(gate.failures) == 1
        assert len(gate.warnings) == 1

    def test_empty_results(self):
        gate = evaluate_gates([])
        assert gate.verdict == GateVerdict.PASS
        assert gate.exit_code == 0

    def test_tier_summaries(self):
        results = [
            _result("a", Tier.T1, True),
            _result("b", Tier.T1, False),
            _result("c", Tier.T2, True),
        ]
        gate = evaluate_gates(results)
        assert "t1" in gate.tier_summaries
        assert gate.tier_summaries["t1"].total == 2
        assert gate.tier_summaries["t1"].passed == 1
        assert gate.tier_summaries["t2"].total == 1
