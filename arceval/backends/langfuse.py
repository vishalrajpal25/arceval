"""Langfuse v3 backend."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Sequence

from arceval.core.exceptions import BackendError
from arceval.core.protocols import ScoreResult
from arceval.core.trace_model import Trace

logger = logging.getLogger(__name__)

try:
    from langfuse import Langfuse

    HAS_LANGFUSE = True
except ImportError:
    HAS_LANGFUSE = False


class LangfuseBackend:
    """Stores traces and scores via Langfuse v3 SDK.

    emit(): logs traces via langfuse.trace()
    query(): reads via Langfuse API
    store_scores(): attaches scores via langfuse.score()

    Config:
        public_key: Langfuse public key
        secret_key: Langfuse secret key
        host: Langfuse host URL
    """

    def __init__(
        self,
        public_key: str = "",
        secret_key: str = "",
        host: str = "https://cloud.langfuse.com",
        **kwargs: Any,
    ) -> None:
        if not HAS_LANGFUSE:
            raise BackendError(
                "Langfuse is not installed. Install with: pip install arceval[langfuse]"
            )
        self._client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )

    def emit(self, traces: Sequence[Trace]) -> None:
        """Log traces to Langfuse."""
        for trace in traces:
            try:
                lf_trace = self._client.trace(
                    name=trace.gen_ai_operation or "trace",
                    input=trace.input_data,
                    output=trace.output_data,
                    metadata={
                        "gen_ai_system": trace.gen_ai_system,
                        "gen_ai_request_model": trace.gen_ai_request_model,
                        "latency_ms": trace.latency_ms,
                        "status_code": trace.status_code,
                        "trace_id_original": trace.trace_id,
                        **trace.attributes,
                    },
                )
                if trace.gen_ai_operation:
                    lf_trace.span(
                        name=trace.gen_ai_operation,
                        input=trace.input_data,
                        output=trace.output_data,
                        metadata={"latency_ms": trace.latency_ms},
                    )
            except Exception as exc:
                logger.error("Failed to emit trace to Langfuse: %s", exc)

    def query(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> Sequence[Trace]:
        """Query traces from Langfuse."""
        try:
            lf_traces = self._client.fetch_traces(limit=limit)
            results: list[Trace] = []
            for lt in lf_traces.data:
                trace = Trace(
                    trace_id=lt.id,
                    span_id="",
                    timestamp_start=str(lt.timestamp) if hasattr(lt, "timestamp") else "",
                    input_data=getattr(lt, "input", None),
                    output_data=getattr(lt, "output", None),
                    attributes=getattr(lt, "metadata", {}) or {},
                )
                results.append(trace)
            return results[:limit]
        except Exception as exc:
            logger.error("Failed to query Langfuse traces: %s", exc)
            return []

    def store_scores(self, scores: Sequence[ScoreResult]) -> None:
        """Attach scores to traces in Langfuse."""
        for score in scores:
            try:
                self._client.score(
                    trace_id=score.trace_id,
                    name=score.scorer_name,
                    value=score.score if score.score is not None else 0.0,
                    comment=f"tier={score.tier.value}, passed={score.passed}",
                )
            except Exception as exc:
                logger.error("Failed to store score in Langfuse: %s", exc)

    def health_check(self) -> bool:
        """Verify Langfuse connectivity."""
        try:
            self._client.auth_check()
            return True
        except Exception:
            return False

    def flush(self) -> None:
        """Flush pending events to Langfuse."""
        try:
            self._client.flush()
        except Exception as exc:
            logger.error("Failed to flush Langfuse client: %s", exc)
