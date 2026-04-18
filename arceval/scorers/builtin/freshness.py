"""Data freshness scorer: checks that data timestamps are within SLA bounds."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arceval.core.protocols import GoldenRecord, ScoreResult
from arceval.core.tier import Tier
from arceval.core.trace_model import Trace


class FreshnessScorer:
    """Checks that a data timestamp in the response is within the configured SLA.

    Looks for a timestamp field in output_data (configurable via timestamp_field)
    and checks that it is no older than max_age_seconds.

    Config:
        timestamp_field: field name in output_data containing an ISO 8601 timestamp
        max_age_seconds: maximum acceptable age of the data
        sla_config_path: path to per-dataset SLA definitions (optional)
        alert_on_breach: whether to flag for alerting
    """

    def __init__(
        self,
        *,
        timestamp_field: str = "data_timestamp",
        max_age_seconds: float = 3600.0,
        sla_config_path: str | None = None,
        alert_on_breach: bool = True,
        tier: str = "t2",
        name: str = "data_freshness",
    ) -> None:
        self._name = name
        self._tier = Tier(tier)
        self._timestamp_field = timestamp_field
        self._max_age_seconds = max_age_seconds
        self._sla_config_path = Path(sla_config_path) if sla_config_path else None
        self._alert_on_breach = alert_on_breach

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> Tier:
        return self._tier

    def score_trace(self, trace: Trace) -> ScoreResult:
        """Check data freshness against the SLA."""
        if not isinstance(trace.output_data, dict):
            return self._result(trace, passed=False, details={"error": "output_data is not a dict"})

        ts_value = trace.output_data.get(self._timestamp_field)
        if ts_value is None:
            return self._result(
                trace, passed=False,
                details={"error": f"field '{self._timestamp_field}' not found in output_data"},
            )

        try:
            data_time = datetime.fromisoformat(str(ts_value))
            if data_time.tzinfo is None:
                data_time = data_time.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            return self._result(
                trace, passed=False,
                details={"error": f"invalid timestamp format: {exc}"},
            )

        now = datetime.now(timezone.utc)
        age_seconds = (now - data_time).total_seconds()
        max_age = self._resolve_max_age(trace)
        passed = age_seconds <= max_age

        score = max(0.0, min(1.0, 1.0 - (age_seconds / max_age - 1.0))) if age_seconds <= max_age * 2 else 0.0
        if age_seconds <= max_age:
            score = 1.0

        return self._result(
            trace,
            passed=passed,
            score=round(score, 4),
            details={
                "age_seconds": round(age_seconds, 2),
                "max_age_seconds": max_age,
                "data_timestamp": str(ts_value),
                "alert_on_breach": self._alert_on_breach and not passed,
            },
        )

    def score_with_golden(self, trace: Trace, golden: GoldenRecord) -> ScoreResult:
        return self.score_trace(trace)

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if self._max_age_seconds <= 0:
            errors.append("max_age_seconds must be positive")
        return errors

    def _resolve_max_age(self, trace: Trace) -> float:
        """Resolve max age, potentially from SLA config per dataset."""
        if self._sla_config_path and self._sla_config_path.exists():
            dataset = trace.attributes.get("dataset")
            if dataset:
                try:
                    with open(self._sla_config_path) as f:
                        sla_data = json.load(f)
                    if dataset in sla_data:
                        return float(sla_data[dataset].get("max_age_seconds", self._max_age_seconds))
                except (OSError, json.JSONDecodeError, KeyError):
                    pass
        return self._max_age_seconds

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
            threshold=self._max_age_seconds,
            details=details or {},
            trace_id=trace.trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
