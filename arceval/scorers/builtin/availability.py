"""Availability scorer: checks whether a trace represents a successful response."""

from __future__ import annotations

from datetime import datetime, timezone

from arceval.core.protocols import GoldenRecord, ScoreResult
from arceval.core.tier import Tier
from arceval.core.trace_model import Trace


class AvailabilityScorer:
    """Checks per-trace availability (success vs failure).

    A trace is considered available/successful if it has no error_type
    and its status_code (if present) is < 500. Aggregate availability
    percentage computation is handled by the runner.

    Config:
        threshold_pct: minimum availability percentage (for aggregate use)
        window_minutes: rolling window for monitoring mode (informational)
    """

    def __init__(
        self,
        *,
        threshold_pct: float = 99.9,
        window_minutes: int = 60,
        tier: str = "t1",
        name: str = "availability",
    ) -> None:
        self._name = name
        self._tier = Tier(tier)
        self._threshold_pct = threshold_pct
        self._window_minutes = window_minutes

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> Tier:
        return self._tier

    def score_trace(self, trace: Trace) -> ScoreResult:
        """Score a single trace: pass if the request was successfully served."""
        available = self._is_available(trace)
        return ScoreResult(
            scorer_name=self._name,
            tier=self._tier,
            passed=available,
            score=1.0 if available else 0.0,
            threshold=self._threshold_pct,
            details={
                "available": available,
                "status_code": trace.status_code,
                "error_type": trace.error_type,
            },
            trace_id=trace.trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def score_with_golden(self, trace: Trace, golden: GoldenRecord) -> ScoreResult:
        return self.score_trace(trace)

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if not 0.0 <= self._threshold_pct <= 100.0:
            errors.append("threshold_pct must be between 0 and 100")
        if self._window_minutes <= 0:
            errors.append("window_minutes must be positive")
        return errors

    @staticmethod
    def _is_available(trace: Trace) -> bool:
        """A trace is available if there's no server error."""
        if trace.error_type is not None:
            return False
        if trace.status_code is not None and trace.status_code >= 500:
            return False
        return True
