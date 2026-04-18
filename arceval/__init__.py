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

from arceval.scorers.adapters.deepeval import DeepEvalAdapter
from arceval.scorers.adapters.ragas import RAGASAdapter
from arceval.scorers.adapters.mlflow_scorers import MLflowScorerAdapter
from arceval.scorers.adapters.custom import CustomScorer

default_registry.register_scorer("deepeval.correctness", DeepEvalAdapter)
default_registry.register_scorer("deepeval.hallucination", DeepEvalAdapter)
default_registry.register_scorer("deepeval.faithfulness", DeepEvalAdapter)
default_registry.register_scorer("deepeval.tool_correctness", DeepEvalAdapter)
default_registry.register_scorer("deepeval.task_completion", DeepEvalAdapter)
default_registry.register_scorer("ragas.faithfulness", RAGASAdapter)
default_registry.register_scorer("ragas.answer_relevancy", RAGASAdapter)
default_registry.register_scorer("ragas.context_precision", RAGASAdapter)
default_registry.register_scorer("ragas.context_recall", RAGASAdapter)
default_registry.register_scorer("mlflow.correctness", MLflowScorerAdapter)
default_registry.register_scorer("mlflow.safety", MLflowScorerAdapter)
default_registry.register_scorer("mlflow.conversation_completeness", MLflowScorerAdapter)
default_registry.register_scorer("mlflow.user_frustration", MLflowScorerAdapter)
default_registry.register_scorer("custom", CustomScorer)

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
