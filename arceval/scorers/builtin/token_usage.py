"""Token usage scorer: detects anomalous token counts relative to a baseline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from arceval.core.protocols import GoldenRecord, ScoreResult
from arceval.core.tier import Tier
from arceval.core.trace_model import Trace


class TokenUsageScorer:
    """Checks for anomalous token usage on a per-trace basis.

    Compares total token count (input + output) against a configured
    baseline. Flags traces where usage exceeds baseline * anomaly_multiplier.

    In monitoring mode, the baseline can be computed from historical data.
    For testing mode, a static baseline_tokens value is used.

    Config:
        baseline_tokens: expected median total token count
        anomaly_multiplier: flag if usage > baseline * multiplier
        baseline_window_days: window for computing baseline in monitoring (informational)
    """

    def __init__(
        self,
        *,
        baseline_tokens: int = 1000,
        anomaly_multiplier: float = 3.0,
        baseline_window_days: int = 7,
        tier: str = "t2",
        name: str = "token_anomaly",
    ) -> None:
        self._name = name
        self._tier = Tier(tier)
        self._baseline_tokens = baseline_tokens
        self._anomaly_multiplier = anomaly_multiplier
        self._baseline_window_days = baseline_window_days

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> Tier:
        return self._tier

    def score_trace(self, trace: Trace) -> ScoreResult:
        """Check if token usage is anomalous compared to baseline."""
        input_tokens = trace.gen_ai_usage_input_tokens or 0
        output_tokens = trace.gen_ai_usage_output_tokens or 0
        total_tokens = input_tokens + output_tokens

        if total_tokens == 0:
            return self._result(
                trace, passed=True, score=1.0,
                details={"total_tokens": 0, "note": "no token data"},
            )

        threshold = self._baseline_tokens * self._anomaly_multiplier
        is_anomalous = total_tokens > threshold

        if total_tokens <= self._baseline_tokens:
            score = 1.0
        elif total_tokens <= threshold:
            ratio = (total_tokens - self._baseline_tokens) / (threshold - self._baseline_tokens)
            score = round(1.0 - ratio, 4)
        else:
            score = 0.0

        return self._result(
            trace,
            passed=not is_anomalous,
            score=score,
            details={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "baseline_tokens": self._baseline_tokens,
                "anomaly_threshold": threshold,
                "anomaly_multiplier": self._anomaly_multiplier,
            },
        )

    def score_with_golden(self, trace: Trace, golden: GoldenRecord) -> ScoreResult:
        return self.score_trace(trace)

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if self._baseline_tokens <= 0:
            errors.append("baseline_tokens must be positive")
        if self._anomaly_multiplier <= 1.0:
            errors.append("anomaly_multiplier must be greater than 1.0")
        if self._baseline_window_days <= 0:
            errors.append("baseline_window_days must be positive")
        return errors

    def _result(
        self,
        trace: Trace,
        *,
        passed: bool,
        score: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> ScoreResult:
        return ScoreResult(
            scorer_name=self._name,
            tier=self._tier,
            passed=passed,
            score=score,
            threshold=self._baseline_tokens * self._anomaly_multiplier,
            details=details or {},
            trace_id=trace.trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
