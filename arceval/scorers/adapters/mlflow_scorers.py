"""Adapter for MLflow 3 built-in scorers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from arceval.core.exceptions import ScorerError
from arceval.core.protocols import GoldenRecord, ScoreResult
from arceval.core.tier import Tier
from arceval.core.trace_model import Trace

logger = logging.getLogger(__name__)

try:
    import mlflow
    from mlflow.genai import scorers as mlflow_scorers

    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False


_MLFLOW_SCORERS = {
    "correctness": "Correctness",
    "safety": "Safety",
    "conversation_completeness": "ConversationCompleteness",
    "user_frustration": "UserFrustration",
}


class MLflowScorerAdapter:
    """Wraps MLflow 3 built-in scorers (mlflow.genai.scorers).

    Supported: mlflow.correctness, mlflow.safety,
    mlflow.conversation_completeness, mlflow.user_frustration

    When the backend is also MLflow, scorer results are stored as
    MLflow assessments on the trace (native integration).

    Config:
        metric: which MLflow scorer (e.g. "correctness")
        model: judge model endpoint
        threshold: score threshold for pass/fail
    """

    def __init__(
        self,
        *,
        metric: str = "correctness",
        model: str = "",
        threshold: float = 0.5,
        tier: str = "t3",
        name: str = "",
        **kwargs: Any,
    ) -> None:
        if not HAS_MLFLOW:
            raise ScorerError(
                "MLflow is not installed. Install with: pip install arceval[mlflow]"
            )
        self._metric_name = metric
        self._model = model
        self._threshold = threshold
        self._tier = Tier(tier)
        self._name = name or f"mlflow.{metric}"
        self._scorer = self._resolve_scorer()

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> Tier:
        return self._tier

    def score_trace(self, trace: Trace) -> ScoreResult:
        """Score a trace using an MLflow built-in scorer."""
        try:
            inputs = {"input": str(trace.input_data or "")}
            outputs = {"output": str(trace.output_data or "")}

            result = mlflow.genai.evaluate(
                data=[{**inputs, **outputs}],
                scorers=[self._scorer],
            )

            # Extract score from evaluation results
            score_value = self._extract_score(result)
            passed = score_value >= self._threshold if score_value is not None else False

            return ScoreResult(
                scorer_name=self._name,
                tier=self._tier,
                passed=passed,
                score=round(score_value, 4) if score_value is not None else None,
                threshold=self._threshold,
                details={"metric": self._metric_name, "model": self._model},
                trace_id=trace.trace_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:
            logger.error("MLflow scorer failed: %s", exc)
            return ScoreResult(
                scorer_name=self._name,
                tier=self._tier,
                passed=False,
                score=None,
                threshold=self._threshold,
                details={"error": str(exc)},
                trace_id=trace.trace_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    def score_with_golden(self, trace: Trace, golden: GoldenRecord) -> ScoreResult:
        """Score with golden record providing expected output."""
        try:
            inputs = {"input": str(trace.input_data or "")}
            outputs = {"output": str(trace.output_data or "")}
            expectations = {"expected_output": str(golden.expected_output or "")}

            result = mlflow.genai.evaluate(
                data=[{**inputs, **outputs, **expectations}],
                scorers=[self._scorer],
            )

            score_value = self._extract_score(result)
            passed = score_value >= self._threshold if score_value is not None else False

            return ScoreResult(
                scorer_name=self._name,
                tier=self._tier,
                passed=passed,
                score=round(score_value, 4) if score_value is not None else None,
                threshold=self._threshold,
                details={"metric": self._metric_name, "model": self._model},
                trace_id=trace.trace_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:
            logger.error("MLflow scorer with golden failed: %s", exc)
            return self.score_trace(trace)

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if self._metric_name not in _MLFLOW_SCORERS:
            errors.append(
                f"Unknown MLflow scorer '{self._metric_name}'. "
                f"Supported: {sorted(_MLFLOW_SCORERS.keys())}"
            )
        if self._threshold < 0 or self._threshold > 1:
            errors.append("threshold must be between 0 and 1")
        return errors

    def _resolve_scorer(self) -> Any:
        """Resolve the MLflow scorer object."""
        scorer_name = _MLFLOW_SCORERS.get(self._metric_name)
        if scorer_name is None:
            raise ScorerError(f"Unknown MLflow scorer: {self._metric_name}")
        try:
            return getattr(mlflow_scorers, scorer_name)()
        except AttributeError:
            raise ScorerError(
                f"MLflow scorer '{scorer_name}' not found in mlflow.genai.scorers. "
                "Check your MLflow version."
            )

    @staticmethod
    def _extract_score(result: Any) -> float | None:
        """Extract a numeric score from MLflow evaluation results."""
        try:
            if hasattr(result, "metrics"):
                metrics = result.metrics
                for key, value in metrics.items():
                    if isinstance(value, (int, float)):
                        return float(value)
            return None
        except Exception:
            return None
