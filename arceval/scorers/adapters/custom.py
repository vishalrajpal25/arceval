"""Custom scorer adapter: wraps a user-defined Python callable as an ArcEval scorer."""

from __future__ import annotations

import importlib
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from arceval.core.exceptions import ScorerError
from arceval.core.protocols import GoldenRecord, ScoreResult
from arceval.core.tier import Tier
from arceval.core.trace_model import Trace

logger = logging.getLogger(__name__)


class CustomScorer:
    """Wraps a user-defined callable as an ArcEval Scorer.

    The callable should accept a dict with keys "input", "output", and
    optionally "expected_output", and return a float score between 0 and 1.

    The callable can be provided directly or loaded from a dotted path
    (e.g. "my_module.my_scorer_function").

    Config:
        callable: the scorer function (or dotted import path string)
        threshold: score threshold for pass/fail
    """

    def __init__(
        self,
        *,
        callable: Callable[..., float] | str | None = None,
        threshold: float = 0.5,
        tier: str = "t3",
        name: str = "custom",
        **kwargs: Any,
    ) -> None:
        self._tier = Tier(tier)
        self._name = name
        self._threshold = threshold

        if callable is None:
            raise ScorerError("CustomScorer requires a 'callable' parameter")

        if isinstance(callable, str):
            self._fn = self._import_callable(callable)
        else:
            self._fn = callable

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> Tier:
        return self._tier

    def score_trace(self, trace: Trace) -> ScoreResult:
        """Score a trace using the custom callable."""
        try:
            score = self._fn({
                "input": trace.input_data,
                "output": trace.output_data,
                "attributes": trace.attributes,
                "latency_ms": trace.latency_ms,
                "status_code": trace.status_code,
            })

            if not isinstance(score, (int, float)):
                raise ScorerError(
                    f"Custom scorer must return a float, got {type(score).__name__}"
                )

            score = float(score)
            passed = score >= self._threshold

            return ScoreResult(
                scorer_name=self._name,
                tier=self._tier,
                passed=passed,
                score=round(score, 4),
                threshold=self._threshold,
                details={},
                trace_id=trace.trace_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except ScorerError:
            raise
        except Exception as exc:
            logger.error("Custom scorer failed: %s", exc)
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
            score = self._fn({
                "input": trace.input_data,
                "output": trace.output_data,
                "expected_output": golden.expected_output,
                "attributes": trace.attributes,
                "latency_ms": trace.latency_ms,
                "status_code": trace.status_code,
                "metadata": golden.metadata,
            })

            if not isinstance(score, (int, float)):
                raise ScorerError(
                    f"Custom scorer must return a float, got {type(score).__name__}"
                )

            score = float(score)
            passed = score >= self._threshold

            return ScoreResult(
                scorer_name=self._name,
                tier=self._tier,
                passed=passed,
                score=round(score, 4),
                threshold=self._threshold,
                details={},
                trace_id=trace.trace_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except ScorerError:
            raise
        except Exception as exc:
            logger.error("Custom scorer with golden failed: %s", exc)
            return self.score_trace(trace)

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        if self._fn is None:
            errors.append("No callable provided")
        if self._threshold < 0 or self._threshold > 1:
            errors.append("threshold must be between 0 and 1")
        return errors

    @staticmethod
    def _import_callable(dotted_path: str) -> Callable[..., float]:
        """Import a callable from a dotted path like 'my_module.my_function'."""
        try:
            module_path, func_name = dotted_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            fn = getattr(module, func_name)
            if not callable(fn):
                raise ScorerError(f"'{dotted_path}' is not callable")
            return fn
        except (ValueError, ImportError, AttributeError) as exc:
            raise ScorerError(
                f"Failed to import callable '{dotted_path}': {exc}"
            ) from exc
