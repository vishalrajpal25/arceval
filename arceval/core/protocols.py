"""Core protocols for ArcEval. All extension points are Protocols, not ABCs."""

from __future__ import annotations

from typing import Any, Protocol, Sequence, runtime_checkable

from arceval.core.tier import Tier
from arceval.core.trace_model import Trace


class ScorerMode:
    """Constants for scorer execution modes."""

    TESTING = "testing"
    MONITORING = "monitoring"


@runtime_checkable
class TraceBackend(Protocol):
    """Where traces are stored and retrieved.

    Implementations: MLflow, Langfuse, OTEL collector, file, Delta.
    """

    def emit(self, traces: Sequence[Trace]) -> None:
        """Send traces to the backend."""
        ...

    def query(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> Sequence[Trace]:
        """Retrieve traces from the backend for scoring."""
        ...

    def store_scores(self, scores: Sequence[ScoreResult]) -> None:
        """Attach scorer results back to the backend."""
        ...

    def health_check(self) -> bool:
        """Verify backend connectivity."""
        ...


@runtime_checkable
class Scorer(Protocol):
    """Evaluates traces and produces scores.

    Must work in BOTH testing mode (golden sets) and monitoring mode (production traces).
    """

    @property
    def name(self) -> str:
        """Unique scorer name."""
        ...

    @property
    def tier(self) -> Tier:
        """Which tier this scorer belongs to."""
        ...

    def score_trace(self, trace: Trace) -> ScoreResult:
        """Score a single trace.

        For rule-based scorers (T1), this is deterministic.
        For LLM-judge scorers (T3), this may call an external model.
        """
        ...

    def score_with_golden(self, trace: Trace, golden: GoldenRecord) -> ScoreResult:
        """Score a trace against a golden set record (eval-as-testing).

        Default implementation: delegates to score_trace, ignoring golden.
        Override for scorers that need reference data.
        """
        ...

    def validate_config(self) -> list[str]:
        """Return a list of config validation errors (empty = valid).

        Called at startup to fail fast on misconfiguration.
        """
        ...


@runtime_checkable
class CaptureMiddleware(Protocol):
    """Instruments an endpoint to produce Traces."""

    def wrap(self, endpoint: Any) -> Any:
        """Wrap the endpoint with instrumentation. Returns the wrapped endpoint."""
        ...

    def set_backend(self, backend: TraceBackend) -> None:
        """Set the backend where captured traces are emitted."""
        ...


@runtime_checkable
class AlertSink(Protocol):
    """Where alerts are sent when thresholds are breached."""

    def send(self, alert: dict[str, Any]) -> None:
        """Send an alert."""
        ...


from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScoreResult:
    """Result from a single scorer execution."""

    scorer_name: str
    tier: Tier
    passed: bool
    score: float | None
    threshold: float | None
    details: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    timestamp: str = ""


@dataclass(frozen=True)
class GoldenRecord:
    """A single golden set record for eval-as-testing."""

    input_data: dict[str, Any] = field(default_factory=dict)
    expected_output: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
