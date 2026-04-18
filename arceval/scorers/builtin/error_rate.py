"""Error rate scorer: checks whether a trace represents an error."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from arceval.core.protocols import GoldenRecord, ScoreResult
from arceval.core.tier import Tier
from arceval.core.trace_model import Trace


class ErrorRateScorer:
    """Checks whether a trace is an error based on status code or error_type.

    For single-trace scoring, this returns pass/fail per trace.
    Aggregate error rate computation is handled by the runner.

    Config:
        threshold_pct: maximum acceptable error rate percentage (for aggregate use)
        segment_by: optional list of attribute keys for grouping
    """

    def __init__(
        self,
        *,
        threshold_pct: float = 0.5,
        segment_by: list[str] | None = None,
        tier: str = "t1",
        name: str = "error_rate",
    ) -> None:
        self._name = name
        self._tier = Tier(tier)
        self._threshold_pct = threshold_pct
        self._segment_by = segment_by or []

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> Tier:
        return self._tier

    def score_trace(self, trace: Trace) -> ScoreResult:
        """Score a single trace: pass if no error, fail if error detected."""
        is_error = self._is_error(trace)
        return ScoreResult(
            scorer_name=self._name,
            tier=self._tier,
            passed=not is_error,
            score=0.0 if is_error else 1.0,
            threshold=self._threshold_pct,
            details={
                "is_error": is_error,
                "status_code": trace.status_code,
                "error_type": trace.error_type,
            },
            trace_id=trace.trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def score_with_golden(self, trace: Trace, golden: GoldenRecord) -> ScoreResult:
        """Error rate scoring does not use golden records; delegates to score_trace."""
        return self.score_trace(trace)

    def validate_config(self) -> list[str]:
        """Validate scorer configuration."""
        errors: list[str] = []
        if self._threshold_pct < 0 or self._threshold_pct > 100:
            errors.append("threshold_pct must be between 0 and 100")
        return errors

    @staticmethod
    def _is_error(trace: Trace) -> bool:
        """Determine if a trace represents an error."""
        if trace.error_type is not None:
            return True
        if trace.status_code is not None and trace.status_code >= 400:
            return True
        return False
