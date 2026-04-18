"""ArcEval: The orchestration layer for AI evaluation."""

from arceval.core.config import ArcEvalConfig, load_config, validate_config
from arceval.core.protocols import (
    AlertSink,
    CaptureMiddleware,
    GoldenRecord,
    ScoreResult,
    Scorer,
    ScorerMode,
    TraceBackend,
)
from arceval.core.registry import Registry, default_registry
from arceval.core.tier import Tier
from arceval.core.trace_model import Trace, create_trace

# Register built-in plugins
from arceval.backends.file import FileBackend
from arceval.scorers.builtin.latency import LatencyScorer
from arceval.scorers.builtin.error_rate import ErrorRateScorer
from arceval.scorers.builtin.schema import SchemaScorer
from arceval.scorers.builtin.availability import AvailabilityScorer
from arceval.scorers.builtin.completeness import CompletenessScorer
from arceval.scorers.builtin.freshness import FreshnessScorer
from arceval.scorers.builtin.token_usage import TokenUsageScorer

from arceval.backends.mlflow import MLflowBackend
from arceval.backends.langfuse import LangfuseBackend
from arceval.backends.otel import OTELBackend
from arceval.backends.delta import DeltaBackend

default_registry.register_backend("file", FileBackend)
default_registry.register_backend("mlflow", MLflowBackend)
default_registry.register_backend("langfuse", LangfuseBackend)
default_registry.register_backend("otel", OTELBackend)
default_registry.register_backend("delta", DeltaBackend)
default_registry.register_scorer("builtin.latency", LatencyScorer)
default_registry.register_scorer("builtin.error_rate", ErrorRateScorer)
default_registry.register_scorer("builtin.schema", SchemaScorer)
default_registry.register_scorer("builtin.availability", AvailabilityScorer)
default_registry.register_scorer("builtin.completeness", CompletenessScorer)
default_registry.register_scorer("builtin.freshness", FreshnessScorer)
default_registry.register_scorer("builtin.token_usage", TokenUsageScorer)

__all__ = [
    "ArcEvalConfig",
    "AlertSink",
    "CaptureMiddleware",
    "ErrorRateScorer",
    "FileBackend",
    "GoldenRecord",
    "LatencyScorer",
    "Registry",
    "ScoreResult",
    "Scorer",
    "ScorerMode",
    "Tier",
    "Trace",
    "TraceBackend",
    "create_trace",
    "default_registry",
    "load_config",
    "validate_config",
]
