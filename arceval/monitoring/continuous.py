"""Continuous scorer execution on production traces via polling loop."""

from __future__ import annotations

import logging
import signal
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

from arceval.core.protocols import ScoreResult, Scorer, TraceBackend
from arceval.core.trace_model import Trace
from arceval.monitoring.alerts import AlertRouter
from arceval.monitoring.sampler import Sampler

logger = logging.getLogger(__name__)


@dataclass
class MonitorState:
    """Tracks state of the monitoring loop."""

    last_checkpoint: str | None = None
    total_traces_processed: int = 0
    total_scores_produced: int = 0
    total_alerts_fired: int = 0
    cycles: int = 0


@dataclass
class MonitorCycleResult:
    """Result of a single monitoring cycle."""

    traces_queried: int = 0
    traces_sampled: int = 0
    scores_produced: int = 0
    alerts_fired: int = 0
    results: list[ScoreResult] = field(default_factory=list)
    duration_ms: float = 0.0


class ContinuousMonitor:
    """Polls a backend for new traces, runs scorers, stores results, fires alerts.

    This is the core monitoring loop for eval-as-observability.
    """

    def __init__(
        self,
        backend: TraceBackend,
        scorers: list[Scorer],
        sampler: Sampler | None = None,
        alert_router: AlertRouter | None = None,
        results_backend: TraceBackend | None = None,
        poll_interval_seconds: int = 30,
        batch_size: int = 100,
    ) -> None:
        self._backend = backend
        self._scorers = scorers
        self._sampler = sampler or Sampler(rate=1.0)
        self._alert_router = alert_router or AlertRouter()
        self._results_backend = results_backend or backend
        self._poll_interval = poll_interval_seconds
        self._batch_size = batch_size
        self._state = MonitorState()
        self._running = False

    @property
    def state(self) -> MonitorState:
        return self._state

    def run_once(self) -> MonitorCycleResult:
        """Execute a single poll-score-alert cycle.

        Queries the backend for traces since last checkpoint, samples them,
        runs scorers, stores results, and fires alerts.
        """
        start = time.monotonic()

        # Query new traces
        traces = self._backend.query(
            start_time=self._state.last_checkpoint,
            limit=self._batch_size,
        )

        if not traces:
            return MonitorCycleResult()

        # Sample
        sampled = self._sampler.sample(list(traces))

        # Score
        all_results: list[ScoreResult] = []
        for trace in sampled:
            for scorer in self._scorers:
                result = scorer.score_trace(trace)
                all_results.append(result)

        # Store results
        if all_results:
            self._results_backend.store_scores(all_results)

        # Alert
        alerts_fired = self._alert_router.check_and_alert(all_results)

        # Update checkpoint to latest trace timestamp
        latest = max(traces, key=lambda t: t.timestamp_start)
        self._state.last_checkpoint = latest.timestamp_start
        self._state.total_traces_processed += len(traces)
        self._state.total_scores_produced += len(all_results)
        self._state.total_alerts_fired += len(alerts_fired)
        self._state.cycles += 1

        elapsed = (time.monotonic() - start) * 1000

        return MonitorCycleResult(
            traces_queried=len(traces),
            traces_sampled=len(sampled),
            scores_produced=len(all_results),
            alerts_fired=len(alerts_fired),
            results=all_results,
            duration_ms=round(elapsed, 2),
        )

    def run(self, max_cycles: int | None = None) -> MonitorState:
        """Run the monitoring loop.

        Args:
            max_cycles: if set, stop after this many cycles (for testing).
                       If None, run until SIGTERM/SIGINT.
        """
        self._running = True

        def _handle_signal(sig: int, frame: Any) -> None:
            logger.info("Received signal %s, shutting down gracefully", sig)
            self._running = False

        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)

        logger.info(
            "Starting monitoring loop (poll_interval=%ds, batch_size=%d, scorers=%d)",
            self._poll_interval,
            self._batch_size,
            len(self._scorers),
        )

        cycles_run = 0
        while self._running:
            try:
                cycle_result = self.run_once()
                if cycle_result.traces_queried > 0:
                    logger.info(
                        "Cycle %d: queried=%d, sampled=%d, scored=%d, alerts=%d (%.1fms)",
                        self._state.cycles,
                        cycle_result.traces_queried,
                        cycle_result.traces_sampled,
                        cycle_result.scores_produced,
                        cycle_result.alerts_fired,
                        cycle_result.duration_ms,
                    )
                else:
                    logger.debug("Cycle %d: no new traces", self._state.cycles)
            except Exception as exc:
                logger.error("Error in monitoring cycle: %s", exc)

            cycles_run += 1
            if max_cycles is not None and cycles_run >= max_cycles:
                break

            if self._running:
                time.sleep(self._poll_interval)

        logger.info(
            "Monitoring stopped. Total: %d traces, %d scores, %d alerts over %d cycles",
            self._state.total_traces_processed,
            self._state.total_scores_produced,
            self._state.total_alerts_fired,
            self._state.cycles,
        )
        return self._state

    def stop(self) -> None:
        """Signal the monitoring loop to stop."""
        self._running = False
