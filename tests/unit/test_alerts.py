"""Tests for arceval.monitoring.alerts."""

from arceval.core.protocols import ScoreResult
from arceval.core.tier import Tier
from arceval.monitoring.alerts import AlertRouter, LogAlertSink


class FakeAlertSink:
    """Captures alerts for testing."""

    def __init__(self) -> None:
        self.alerts: list[dict] = []

    def send(self, alert: dict) -> None:
        self.alerts.append(alert)


def _result(scorer: str, tier: Tier, passed: bool, score: float = 1.0) -> ScoreResult:
    return ScoreResult(
        scorer_name=scorer,
        tier=tier,
        passed=passed,
        score=score,
        threshold=0.5,
        trace_id="test123",
        timestamp="2026-01-01",
    )


class TestAlertRouter:
    def test_no_alerts_on_pass(self):
        sink = FakeAlertSink()
        router = AlertRouter()
        router.add_rule(on=["t1.fail"], sink=sink)

        fired = router.check_and_alert([_result("latency", Tier.T1, True)])
        assert fired == []
        assert sink.alerts == []

    def test_alert_on_t1_fail(self):
        sink = FakeAlertSink()
        router = AlertRouter()
        router.add_rule(on=["t1.fail"], sink=sink)

        fired = router.check_and_alert([_result("latency", Tier.T1, False, 0.3)])
        assert len(fired) == 1
        assert fired[0]["scorer_name"] == "latency"
        assert fired[0]["score"] == 0.3
        assert len(sink.alerts) == 1

    def test_no_alert_when_pattern_doesnt_match(self):
        sink = FakeAlertSink()
        router = AlertRouter()
        router.add_rule(on=["t2.fail"], sink=sink)

        fired = router.check_and_alert([_result("latency", Tier.T1, False)])
        assert fired == []

    def test_multiple_rules(self):
        t1_sink = FakeAlertSink()
        t2_sink = FakeAlertSink()
        router = AlertRouter()
        router.add_rule(on=["t1.fail"], sink=t1_sink)
        router.add_rule(on=["t2.fail"], sink=t2_sink)

        results = [
            _result("latency", Tier.T1, False, 0.5),
            _result("freshness", Tier.T2, False, 0.3),
        ]
        fired = router.check_and_alert(results)
        assert len(fired) == 2
        assert len(t1_sink.alerts) == 1
        assert len(t2_sink.alerts) == 1

    def test_partial_pattern_match(self):
        sink = FakeAlertSink()
        router = AlertRouter()
        router.add_rule(on=["t1"], sink=sink)  # matches any t1 event

        fired = router.check_and_alert([_result("latency", Tier.T1, False)])
        assert len(fired) == 1

    def test_wildcard_pattern(self):
        sink = FakeAlertSink()
        router = AlertRouter()
        router.add_rule(on=["t1.*"], sink=sink)

        fired = router.check_and_alert([_result("latency", Tier.T1, False)])
        assert len(fired) == 1

    def test_mixed_pass_fail(self):
        sink = FakeAlertSink()
        router = AlertRouter()
        router.add_rule(on=["t1.fail"], sink=sink)

        results = [
            _result("latency", Tier.T1, True),
            _result("error_rate", Tier.T1, False, 0.1),
            _result("schema", Tier.T1, True),
        ]
        fired = router.check_and_alert(results)
        assert len(fired) == 1
        assert fired[0]["scorer_name"] == "error_rate"


class TestLogAlertSink:
    def test_send_does_not_raise(self):
        sink = LogAlertSink()
        sink.send({"scorer_name": "test", "tier": "t1", "score": 0.5})
