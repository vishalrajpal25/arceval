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

default_registry.register_backend("file", FileBackend)
default_registry.register_scorer("builtin.latency", LatencyScorer)
default_registry.register_scorer("builtin.error_rate", ErrorRateScorer)

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
