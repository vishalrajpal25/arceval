"""Schema compliance scorer: validates response data against JSON schemas."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

from arceval.core.protocols import GoldenRecord, ScoreResult
from arceval.core.tier import Tier
from arceval.core.trace_model import Trace


class SchemaScorer:
    """Checks that trace output_data conforms to a JSON schema.

    The schema can be provided directly or loaded from a file path.
    When schema_path is a directory, the scorer looks for a file named
    {tool_name}.json based on the trace's attributes.

    Config:
        schema: inline JSON schema dict
        schema_path: path to schema file or directory
        threshold_pct: minimum compliance percentage (for aggregate use)
    """

    def __init__(
        self,
        *,
        schema: dict[str, Any] | None = None,
        schema_path: str | None = None,
        threshold_pct: float = 99.9,
        tier: str = "t1",
        name: str = "schema_compliance",
    ) -> None:
        self._name = name
        self._tier = Tier(tier)
        self._schema = schema
        self._schema_path = Path(schema_path) if schema_path else None
        self._threshold_pct = threshold_pct
        self._schema_cache: dict[str, dict[str, Any]] = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> Tier:
        return self._tier

    def score_trace(self, trace: Trace) -> ScoreResult:
        """Validate trace output_data against the configured schema."""
        if trace.output_data is None:
            return self._result(trace, passed=False, details={"error": "output_data is None"})

        schema = self._resolve_schema(trace)
        if schema is None:
            return self._result(trace, passed=False, details={"error": "no schema found"})

        try:
            jsonschema.validate(instance=trace.output_data, schema=schema)
            return self._result(trace, passed=True, score=1.0, details={"valid": True})
        except jsonschema.ValidationError as exc:
            return self._result(
                trace,
                passed=False,
                score=0.0,
                details={"valid": False, "error": exc.message, "path": list(exc.absolute_path)},
            )

    def score_with_golden(self, trace: Trace, golden: GoldenRecord) -> ScoreResult:
        return self.score_trace(trace)

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if self._schema is None and self._schema_path is None:
            errors.append("Either 'schema' or 'schema_path' must be provided")
        if self._schema_path and not self._schema_path.exists():
            errors.append(f"schema_path does not exist: {self._schema_path}")
        if not 0.0 <= self._threshold_pct <= 100.0:
            errors.append("threshold_pct must be between 0 and 100")
        return errors

    def _resolve_schema(self, trace: Trace) -> dict[str, Any] | None:
        """Resolve schema from inline config, file, or directory."""
        if self._schema is not None:
            return self._schema

        if self._schema_path is None:
            return None

        if self._schema_path.is_file():
            return self._load_schema_file(self._schema_path)

        if self._schema_path.is_dir():
            tool_name = trace.attributes.get("tool_name")
            if tool_name:
                schema_file = self._schema_path / f"{tool_name}.json"
                if schema_file.exists():
                    return self._load_schema_file(schema_file)
            return None

        return None

    def _load_schema_file(self, path: Path) -> dict[str, Any]:
        """Load and cache a JSON schema file."""
        key = str(path)
        if key not in self._schema_cache:
            with open(path) as f:
                self._schema_cache[key] = json.load(f)
        return self._schema_cache[key]

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
