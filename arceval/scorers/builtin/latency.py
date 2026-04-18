"""Latency scorer: checks P50/P95/P99 latency against thresholds."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from arceval.core.protocols import GoldenRecord, ScoreResult
from arceval.core.tier import Tier
from arceval.core.trace_model import Trace


class LatencyScorer:
    """Checks that trace latency is within a configured threshold.

    Config:
        percentile: which percentile to check (not used for single-trace scoring)
        threshold_ms: maximum acceptable latency in milliseconds
        segment_by: optional list of attribute keys for grouping (informational)
    """

    def __init__(
        self,
        *,
        threshold_ms: float = 2000.0,
        percentile: int = 95,
        segment_by: list[str] | None = None,
        tier: str = "t1",
        name: str = "latency",
    ) -> None:
        self._name = name
        self._tier = Tier(tier)
        self._threshold_ms = threshold_ms
        self._percentile = percentile
        self._segment_by = segment_by or []

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> Tier:
        return self._tier

    def score_trace(self, trace: Trace) -> ScoreResult:
        """Score a single trace's latency against the threshold."""
        latency = trace.latency_ms
        if latency is None:
            return ScoreResult(
                scorer_name=self._name,
                tier=self._tier,
                passed=False,
                score=None,
                threshold=self._threshold_ms,
                details={"error": "latency_ms not present on trace"},
                trace_id=trace.trace_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        passed = latency <= self._threshold_ms
        # Score: 1.0 when at 0ms, 0.0 when at 2x threshold, clamped
        ratio = latency / self._threshold_ms if self._threshold_ms > 0 else 1.0
        score = max(0.0, min(1.0, 1.0 - (ratio - 1.0))) if ratio <= 2.0 else 0.0

        return ScoreResult(
            scorer_name=self._name,
            tier=self._tier,
            passed=passed,
            score=round(score, 4),
            threshold=self._threshold_ms,
            details={
                "latency_ms": latency,
                "threshold_ms": self._threshold_ms,
                "percentile": self._percentile,
            },
            trace_id=trace.trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def score_with_golden(self, trace: Trace, golden: GoldenRecord) -> ScoreResult:
        """Latency scoring does not use golden records; delegates to score_trace."""
        return self.score_trace(trace)

    def validate_config(self) -> list[str]:
        """Validate scorer configuration."""
        errors: list[str] = []
        if self._threshold_ms <= 0:
            errors.append("threshold_ms must be positive")
        if self._percentile not in (50, 90, 95, 99):
            errors.append(f"percentile should be 50, 90, 95, or 99, got {self._percentile}")
        return errors
