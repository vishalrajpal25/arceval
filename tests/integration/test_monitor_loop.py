"""Integration tests for the continuous monitoring loop."""

from arceval.backends.file import FileBackend
from arceval.core.trace_model import create_trace
from arceval.monitoring.alerts import AlertRouter
from arceval.monitoring.continuous import ContinuousMonitor
from arceval.monitoring.sampler import Sampler
from arceval.scorers.builtin.latency import LatencyScorer
from arceval.scorers.builtin.error_rate import ErrorRateScorer


class FakeSink:
    def __init__(self):
        self.alerts = []

    def send(self, alert):
        self.alerts.append(alert)


class TestContinuousMonitor:
    def test_run_once_no_traces(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        scorers = [LatencyScorer(threshold_ms=2000.0, name="latency")]
        mon = ContinuousMonitor(backend=backend, scorers=scorers)

        result = mon.run_once()
        assert result.traces_queried == 0
        assert result.scores_produced == 0

    def test_run_once_with_traces(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        # Emit some traces
        traces = [
            create_trace(latency_ms=100.0, status_code=200),
            create_trace(latency_ms=200.0, status_code=200),
        ]
        backend.emit(traces)

        scorers = [
            LatencyScorer(threshold_ms=2000.0, name="latency"),
            ErrorRateScorer(name="error_rate"),
        ]
        mon = ContinuousMonitor(backend=backend, scorers=scorers)

        result = mon.run_once()
        assert result.traces_queried == 2
        assert result.traces_sampled == 2
        assert result.scores_produced == 4  # 2 traces * 2 scorers

        # Scores should be stored
        assert backend.scores_file.exists()

    def test_run_once_with_sampling(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        traces = [create_trace(latency_ms=float(i)) for i in range(100)]
        backend.emit(traces)

        sampler = Sampler(rate=0.1, seed=42)
        scorers = [LatencyScorer(threshold_ms=2000.0, name="latency")]
        mon = ContinuousMonitor(backend=backend, scorers=scorers, sampler=sampler)

        result = mon.run_once()
        assert result.traces_queried == 100
        assert result.traces_sampled < 100
        assert result.scores_produced == result.traces_sampled

    def test_run_once_fires_alerts(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        traces = [create_trace(latency_ms=5000.0)]  # over threshold
        backend.emit(traces)

        sink = FakeSink()
        router = AlertRouter()
        router.add_rule(on=["t1.fail"], sink=sink)

        scorers = [LatencyScorer(threshold_ms=1000.0, name="latency")]
        mon = ContinuousMonitor(
            backend=backend, scorers=scorers, alert_router=router
        )

        result = mon.run_once()
        assert result.alerts_fired > 0
        assert len(sink.alerts) > 0

    def test_run_max_cycles(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        traces = [create_trace(latency_ms=100.0)]
        backend.emit(traces)

        scorers = [LatencyScorer(threshold_ms=2000.0, name="latency")]
        mon = ContinuousMonitor(
            backend=backend, scorers=scorers, poll_interval_seconds=0
        )

        state = mon.run(max_cycles=3)
        assert state.cycles == 3

    def test_state_tracks_totals(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        traces = [create_trace(latency_ms=100.0), create_trace(latency_ms=200.0)]
        backend.emit(traces)

        scorers = [LatencyScorer(threshold_ms=2000.0, name="latency")]
        mon = ContinuousMonitor(backend=backend, scorers=scorers)

        mon.run_once()
        assert mon.state.total_traces_processed == 2
        assert mon.state.total_scores_produced == 2
        assert mon.state.cycles == 1

    def test_checkpoint_advances(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        t1 = create_trace(latency_ms=100.0)
        backend.emit([t1])

        scorers = [LatencyScorer(threshold_ms=2000.0, name="latency")]
        mon = ContinuousMonitor(backend=backend, scorers=scorers)

        assert mon.state.last_checkpoint is None
        mon.run_once()
        assert mon.state.last_checkpoint is not None

    def test_stop(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        scorers = [LatencyScorer(threshold_ms=2000.0, name="latency")]
        mon = ContinuousMonitor(backend=backend, scorers=scorers)
        mon.stop()
        assert mon._running is False
