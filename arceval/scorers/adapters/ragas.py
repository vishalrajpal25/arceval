"""Adapter for RAGAS metrics as ArcEval scorers."""

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
    from ragas import evaluate as ragas_evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )
    from datasets import Dataset

    HAS_RAGAS = True
except ImportError:
    HAS_RAGAS = False


_RAGAS_METRICS = {
    "faithfulness": "faithfulness",
    "answer_relevancy": "answer_relevancy",
    "context_precision": "context_precision",
    "context_recall": "context_recall",
}


class RAGASAdapter:
    """Wraps RAGAS metrics as ArcEval scorers.

    Supported: ragas.faithfulness, ragas.answer_relevancy,
    ragas.context_precision, ragas.context_recall

    Config:
        metric: which RAGAS metric (e.g. "faithfulness")
        model: LLM model for evaluation
        threshold: score threshold for pass/fail
    """

    def __init__(
        self,
        *,
        metric: str = "faithfulness",
        model: str = "gpt-4o",
        threshold: float = 0.5,
        tier: str = "t3",
        name: str = "",
        **kwargs: Any,
    ) -> None:
        if not HAS_RAGAS:
            raise ScorerError(
                "RAGAS is not installed. Install with: pip install arceval[ragas]"
            )
        self._metric_name = metric
        self._model = model
        self._threshold = threshold
        self._tier = Tier(tier)
        self._name = name or f"ragas.{metric}"
        self._ragas_metric = self._resolve_metric()

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> Tier:
        return self._tier

    def score_trace(self, trace: Trace) -> ScoreResult:
        """Score a trace using RAGAS."""
        try:
            question = str(trace.input_data or "")
            answer = str(trace.output_data or "")
            contexts = trace.attributes.get("contexts", [])
            if isinstance(contexts, str):
                contexts = [contexts]

            dataset = Dataset.from_dict({
                "question": [question],
                "answer": [answer],
                "contexts": [contexts],
            })

            result = ragas_evaluate(dataset, metrics=[self._ragas_metric])
            score = result[self._metric_name]
            passed = score >= self._threshold

            return ScoreResult(
                scorer_name=self._name,
                tier=self._tier,
                passed=passed,
                score=round(float(score), 4),
                threshold=self._threshold,
                details={"metric": self._metric_name, "model": self._model},
                trace_id=trace.trace_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:
            logger.error("RAGAS scoring failed: %s", exc)
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
        """Score with golden record providing ground truth and contexts."""
        try:
            question = str(trace.input_data or "")
            answer = str(trace.output_data or "")
            ground_truth = str(golden.expected_output or "")
            contexts = golden.metadata.get("contexts", [])
            if isinstance(contexts, str):
                contexts = [contexts]

            dataset = Dataset.from_dict({
                "question": [question],
                "answer": [answer],
                "contexts": [contexts],
                "ground_truth": [ground_truth],
            })

            result = ragas_evaluate(dataset, metrics=[self._ragas_metric])
            score = result[self._metric_name]
            passed = score >= self._threshold

            return ScoreResult(
                scorer_name=self._name,
                tier=self._tier,
                passed=passed,
                score=round(float(score), 4),
                threshold=self._threshold,
                details={"metric": self._metric_name, "model": self._model},
                trace_id=trace.trace_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:
            logger.error("RAGAS scoring with golden failed: %s", exc)
            return self.score_trace(trace)

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if self._metric_name not in _RAGAS_METRICS:
            errors.append(
                f"Unknown RAGAS metric '{self._metric_name}'. "
                f"Supported: {sorted(_RAGAS_METRICS.keys())}"
            )
        if self._threshold < 0 or self._threshold > 1:
            errors.append("threshold must be between 0 and 1")
        return errors

    def _resolve_metric(self) -> Any:
        """Resolve the RAGAS metric object."""
        metric_map = {
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "context_precision": context_precision,
            "context_recall": context_recall,
        }
        metric = metric_map.get(self._metric_name)
        if metric is None:
            raise ScorerError(f"Unknown RAGAS metric: {self._metric_name}")
        return metric
