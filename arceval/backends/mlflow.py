"""MLflow 3 backend using mlflow.genai namespace."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Sequence

from arceval.core.exceptions import BackendError
from arceval.core.protocols import ScoreResult
from arceval.core.trace_model import Trace

logger = logging.getLogger(__name__)

try:
    import mlflow
    import mlflow.tracing

    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False


class MLflowBackend:
    """Stores traces and scores via MLflow 3.

    emit(): logs traces via mlflow.tracing
    query(): reads from MLflow experiment traces
    store_scores(): attaches assessments to traces

    Config:
        tracking_uri: MLflow tracking URI ("databricks", "http://...", "file:///...")
        experiment_name: path to the MLflow experiment
    """

    def __init__(
        self,
        tracking_uri: str = "file:///tmp/mlflow",
        experiment_name: str = "/arceval/default",
        **kwargs: Any,
    ) -> None:
        if not HAS_MLFLOW:
            raise BackendError(
                "MLflow is not installed. Install with: pip install arceval[mlflow]"
            )
        self._tracking_uri = tracking_uri
        self._experiment_name = experiment_name
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)

    def emit(self, traces: Sequence[Trace]) -> None:
        """Log traces to MLflow."""
        for trace in traces:
            try:
                with mlflow.start_span(name=trace.gen_ai_operation or "trace") as span:
                    span.set_inputs(trace.input_data or {})
                    span.set_outputs(trace.output_data or {})
                    attrs = {
                        "gen_ai.system": trace.gen_ai_system,
                        "gen_ai.operation": trace.gen_ai_operation,
                        "gen_ai.request.model": trace.gen_ai_request_model,
                        "latency_ms": trace.latency_ms,
                        "status_code": trace.status_code,
                        "trace_id_original": trace.trace_id,
                    }
                    attrs.update(trace.attributes)
                    span.set_attributes(
                        {k: v for k, v in attrs.items() if v is not None}
                    )
            except Exception as exc:
                logger.error("Failed to emit trace to MLflow: %s", exc)

    def query(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> Sequence[Trace]:
        """Query traces from MLflow. Returns stored traces as Trace objects."""
        try:
            mlflow_traces = mlflow.search_traces(
                experiment_names=[self._experiment_name],
                max_results=limit,
            )
            results: list[Trace] = []
            for mt in mlflow_traces.itertuples():
                trace = Trace(
                    trace_id=str(getattr(mt, "request_id", "")),
                    span_id="",
                    timestamp_start=str(getattr(mt, "timestamp_ms", "")),
                    attributes={},
                )
                results.append(trace)
            return results[:limit]
        except Exception as exc:
            logger.error("Failed to query MLflow traces: %s", exc)
            return []

    def store_scores(self, scores: Sequence[ScoreResult]) -> None:
        """Store score results as MLflow assessments."""
        for score in scores:
            try:
                mlflow.log_metric(
                    f"arceval.{score.scorer_name}.score",
                    score.score or 0.0,
                )
                mlflow.log_metric(
                    f"arceval.{score.scorer_name}.passed",
                    1.0 if score.passed else 0.0,
                )
            except Exception as exc:
                logger.error("Failed to store score in MLflow: %s", exc)

    def health_check(self) -> bool:
        """Verify MLflow connectivity."""
        try:
            mlflow.get_tracking_uri()
            return True
        except Exception:
            return False
