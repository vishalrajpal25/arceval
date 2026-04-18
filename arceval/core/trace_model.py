"""Internal trace model aligned with OpenTelemetry gen_ai.* semantic conventions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Trace:
    """Universal trace representation passed between capture, backends, and scorers.

    Attribute names follow OTEL gen_ai.* semantic conventions.
    """

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    timestamp_start: str = ""  # ISO 8601
    timestamp_end: str | None = None

    # gen_ai.* standard attributes
    gen_ai_system: str | None = None
    gen_ai_operation: str | None = None
    gen_ai_request_model: str | None = None
    gen_ai_response_model: str | None = None
    gen_ai_usage_input_tokens: int | None = None
    gen_ai_usage_output_tokens: int | None = None

    # Common operational attributes
    status_code: int | None = None
    error_type: str | None = None
    latency_ms: float | None = None

    # Endpoint-specific attributes
    attributes: dict[str, Any] = field(default_factory=dict)

    # Request/response content (optional, may be redacted)
    input_data: Any | None = None
    output_data: Any | None = None


def create_trace(
    *,
    gen_ai_system: str | None = None,
    gen_ai_operation: str | None = None,
    gen_ai_request_model: str | None = None,
    latency_ms: float | None = None,
    status_code: int | None = None,
    error_type: str | None = None,
    input_data: Any | None = None,
    output_data: Any | None = None,
    attributes: dict[str, Any] | None = None,
    gen_ai_usage_input_tokens: int | None = None,
    gen_ai_usage_output_tokens: int | None = None,
    parent_span_id: str | None = None,
) -> Trace:
    """Factory for creating a Trace with auto-generated IDs and timestamps."""
    now = datetime.now(timezone.utc).isoformat()
    return Trace(
        trace_id=uuid.uuid4().hex,
        span_id=uuid.uuid4().hex[:16],
        parent_span_id=parent_span_id,
        timestamp_start=now,
        timestamp_end=now,
        gen_ai_system=gen_ai_system,
        gen_ai_operation=gen_ai_operation,
        gen_ai_request_model=gen_ai_request_model,
        gen_ai_usage_input_tokens=gen_ai_usage_input_tokens,
        gen_ai_usage_output_tokens=gen_ai_usage_output_tokens,
        latency_ms=latency_ms,
        status_code=status_code,
        error_type=error_type,
        attributes=attributes or {},
        input_data=input_data,
        output_data=output_data,
    )
