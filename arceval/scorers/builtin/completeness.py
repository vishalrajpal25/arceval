"""Field completeness scorer: checks that required fields are present in response."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arceval.core.protocols import GoldenRecord, ScoreResult
from arceval.core.tier import Tier
from arceval.core.trace_model import Trace


class CompletenessScorer:
    """Checks that required fields are present and non-null in trace output_data.

    Required fields can be specified inline or loaded from a manifest file.
    When required_fields_path is a directory, looks for {tool_name}.json.

    Config:
        required_fields: inline list of field names
        required_fields_path: path to manifest file or directory
        threshold_pct: minimum completeness percentage (for aggregate use)
    """

    def __init__(
        self,
        *,
        required_fields: list[str] | None = None,
        required_fields_path: str | None = None,
        threshold_pct: float = 99.5,
        tier: str = "t1",
        name: str = "field_completeness",
    ) -> None:
        self._name = name
        self._tier = Tier(tier)
        self._required_fields = required_fields
        self._required_fields_path = Path(required_fields_path) if required_fields_path else None
        self._threshold_pct = threshold_pct
        self._manifest_cache: dict[str, list[str]] = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> Tier:
        return self._tier

    def score_trace(self, trace: Trace) -> ScoreResult:
        """Check that all required fields are present in output_data."""
        if trace.output_data is None:
            return self._result(trace, passed=False, score=0.0, details={"error": "output_data is None"})

        if not isinstance(trace.output_data, dict):
            return self._result(
                trace, passed=False, score=0.0,
                details={"error": f"output_data is {type(trace.output_data).__name__}, expected dict"},
            )

        fields = self._resolve_fields(trace)
        if not fields:
            return self._result(trace, passed=True, score=1.0, details={"required_fields": [], "missing": []})

        missing = [f for f in fields if f not in trace.output_data or trace.output_data[f] is None]
        present_count = len(fields) - len(missing)
        score = present_count / len(fields) if fields else 1.0
        passed = len(missing) == 0

        return self._result(
            trace,
            passed=passed,
            score=round(score, 4),
            details={
                "required_fields": fields,
                "missing": missing,
                "present_count": present_count,
                "total_count": len(fields),
            },
        )

    def score_with_golden(self, trace: Trace, golden: GoldenRecord) -> ScoreResult:
        return self.score_trace(trace)

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if self._required_fields is None and self._required_fields_path is None:
            errors.append("Either 'required_fields' or 'required_fields_path' must be provided")
        if self._required_fields_path and not self._required_fields_path.exists():
            errors.append(f"required_fields_path does not exist: {self._required_fields_path}")
        if not 0.0 <= self._threshold_pct <= 100.0:
            errors.append("threshold_pct must be between 0 and 100")
        return errors

    def _resolve_fields(self, trace: Trace) -> list[str]:
        """Resolve required fields from inline config or manifest file."""
        if self._required_fields is not None:
            return self._required_fields

        if self._required_fields_path is None:
            return []

        if self._required_fields_path.is_file():
            return self._load_manifest(self._required_fields_path)

        if self._required_fields_path.is_dir():
            tool_name = trace.attributes.get("tool_name")
            if tool_name:
                manifest_file = self._required_fields_path / f"{tool_name}.json"
                if manifest_file.exists():
                    return self._load_manifest(manifest_file)
            return []

        return []

    def _load_manifest(self, path: Path) -> list[str]:
        """Load and cache a field manifest file (JSON array of field names)."""
        key = str(path)
        if key not in self._manifest_cache:
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, list):
                self._manifest_cache[key] = data
            elif isinstance(data, dict) and "fields" in data:
                self._manifest_cache[key] = data["fields"]
            else:
                self._manifest_cache[key] = []
        return self._manifest_cache[key]

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
            threshold=self._threshold_pct,
            details=details or {},
            trace_id=trace.trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
