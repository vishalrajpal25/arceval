"""Adapter for DeepEval metrics as ArcEval scorers."""

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
    import deepeval
    from deepeval.metrics import (
        GEval,
        HallucinationMetric,
        FaithfulnessMetric,
    )
    from deepeval.test_case import LLMTestCase

    HAS_DEEPEVAL = True
except ImportError:
    HAS_DEEPEVAL = False


# Map of supported DeepEval metric types to their classes
_DEEPEVAL_METRICS: dict[str, str] = {
    "correctness": "GEval",
    "hallucination": "HallucinationMetric",
    "faithfulness": "FaithfulnessMetric",
    "tool_correctness": "ToolCorrectnessMetric",
    "task_completion": "TaskCompletionMetric",
}


class DeepEvalAdapter:
    """Wraps any DeepEval metric as an ArcEval Scorer.

    Supported metrics:
    - deepeval.correctness (GEval with correctness criteria)
    - deepeval.hallucination (HallucinationMetric)
    - deepeval.faithfulness (FaithfulnessMetric)
    - deepeval.tool_correctness (ToolCorrectnessMetric)
    - deepeval.task_completion (TaskCompletionMetric)

    Config:
        metric: which DeepEval metric to use (e.g. "hallucination")
        model: LLM model for judge (e.g. "gpt-4o")
        threshold: score threshold for pass/fail
    """

    def __init__(
        self,
        *,
        metric: str = "correctness",
        model: str = "gpt-4o",
        threshold: float = 0.5,
        tier: str = "t3",
        name: str = "",
        **kwargs: Any,
    ) -> None:
        if not HAS_DEEPEVAL:
            raise ScorerError(
                "DeepEval is not installed. Install with: pip install arceval[deepeval]"
            )
        self._metric_name = metric
        self._model = model
        self._threshold = threshold
        self._tier = Tier(tier)
        self._name = name or f"deepeval.{metric}"
        self._extra_config = kwargs
        self._metric_instance = self._create_metric()

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> Tier:
        return self._tier

    def score_trace(self, trace: Trace) -> ScoreResult:
        """Score a trace using the DeepEval metric."""
        try:
            test_case = LLMTestCase(
                input=str(trace.input_data or ""),
                actual_output=str(trace.output_data or ""),
            )
            self._metric_instance.measure(test_case)
            score = self._metric_instance.score
            passed = score >= self._threshold

            return ScoreResult(
                scorer_name=self._name,
                tier=self._tier,
                passed=passed,
                score=round(score, 4),
                threshold=self._threshold,
                details={
                    "metric": self._metric_name,
                    "model": self._model,
                    "reason": getattr(self._metric_instance, "reason", ""),
                },
                trace_id=trace.trace_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:
            logger.error("DeepEval scoring failed: %s", exc)
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
        """Score with golden record context for expected output."""
        try:
            test_case = LLMTestCase(
                input=str(trace.input_data or ""),
                actual_output=str(trace.output_data or ""),
                expected_output=str(golden.expected_output or ""),
                context=[str(golden.metadata)] if golden.metadata else None,
            )
            self._metric_instance.measure(test_case)
            score = self._metric_instance.score
            passed = score >= self._threshold

            return ScoreResult(
                scorer_name=self._name,
                tier=self._tier,
                passed=passed,
                score=round(score, 4),
                threshold=self._threshold,
                details={
                    "metric": self._metric_name,
                    "model": self._model,
                    "reason": getattr(self._metric_instance, "reason", ""),
                },
                trace_id=trace.trace_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:
            logger.error("DeepEval scoring with golden failed: %s", exc)
            return self.score_trace(trace)

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if self._metric_name not in _DEEPEVAL_METRICS:
            errors.append(
                f"Unknown DeepEval metric '{self._metric_name}'. "
                f"Supported: {sorted(_DEEPEVAL_METRICS.keys())}"
            )
        if self._threshold < 0 or self._threshold > 1:
            errors.append("threshold must be between 0 and 1")
        return errors

    def _create_metric(self) -> Any:
        """Instantiate the DeepEval metric."""
        if self._metric_name == "correctness":
            return GEval(
                name="Correctness",
                criteria="Determine if the actual output is correct given the input.",
                model=self._model,
                threshold=self._threshold,
            )
        elif self._metric_name == "hallucination":
            return HallucinationMetric(
                model=self._model,
                threshold=self._threshold,
            )
        elif self._metric_name == "faithfulness":
            return FaithfulnessMetric(
                model=self._model,
                threshold=self._threshold,
            )
        else:
            # Try dynamic import for other metrics
            try:
                metric_class_name = _DEEPEVAL_METRICS.get(self._metric_name, "")
                from deepeval import metrics as deepeval_metrics

                metric_cls = getattr(deepeval_metrics, metric_class_name)
                return metric_cls(model=self._model, threshold=self._threshold)
            except (AttributeError, ImportError) as exc:
                raise ScorerError(
                    f"Failed to load DeepEval metric '{self._metric_name}': {exc}"
                ) from exc
