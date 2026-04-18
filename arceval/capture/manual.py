"""Manual trace creation API for testing without a live endpoint."""

from __future__ import annotations

from typing import Any, Sequence

from arceval.core.protocols import TraceBackend
from arceval.core.trace_model import Trace, create_trace


class ManualCapture:
    """Creates traces manually from golden set inputs and endpoint responses.

    Used in testing mode when you want to call the endpoint yourself and
    record the results as traces.
    """

    def __init__(self) -> None:
        self._backend: TraceBackend | None = None

    def set_backend(self, backend: TraceBackend) -> None:
        """Set the backend where captured traces are emitted."""
        self._backend = backend

    def wrap(self, endpoint: Any) -> Any:
        """No-op for manual capture. Returns endpoint unchanged."""
        return endpoint

    def record(
        self,
        *,
        input_data: Any,
        output_data: Any,
        latency_ms: float | None = None,
        status_code: int | None = None,
        error_type: str | None = None,
        gen_ai_system: str | None = None,
        gen_ai_operation: str | None = None,
        gen_ai_request_model: str | None = None,
        gen_ai_usage_input_tokens: int | None = None,
        gen_ai_usage_output_tokens: int | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Trace:
        """Record a single request/response pair as a trace.

        Returns the created Trace. If a backend is set, the trace is
        also emitted to it.
        """
        trace = create_trace(
            input_data=input_data,
            output_data=output_data,
            latency_ms=latency_ms,
            status_code=status_code,
            error_type=error_type,
            gen_ai_system=gen_ai_system,
            gen_ai_operation=gen_ai_operation,
            gen_ai_request_model=gen_ai_request_model,
            gen_ai_usage_input_tokens=gen_ai_usage_input_tokens,
            gen_ai_usage_output_tokens=gen_ai_usage_output_tokens,
            attributes=attributes,
        )

        if self._backend is not None:
            self._backend.emit([trace])

        return trace

    def record_batch(self, records: Sequence[dict[str, Any]]) -> list[Trace]:
        """Record multiple request/response pairs as traces.

        Each dict in records should have the same keys as the `record` method.
        Returns the list of created Traces.
        """
        traces = [self.record(**r) for r in records]
        return traces
