"""OpenAI client wrapper for capturing chat/completion traces."""

from __future__ import annotations

import logging
import time
from typing import Any

from arceval.core.protocols import TraceBackend
from arceval.core.trace_model import create_trace

logger = logging.getLogger(__name__)

try:
    import openai

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class OpenAICapture:
    """Wraps an OpenAI client to capture chat completion traces.

    Usage:
        from openai import OpenAI
        from arceval.capture.openai_wrapper import OpenAICapture

        client = OpenAI()
        capture = OpenAICapture()
        capture.set_backend(backend)
        wrapped_client = capture.wrap(client)

        # Use wrapped_client normally; traces are captured automatically
        response = wrapped_client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": "Hello"}]
        )
    """

    def __init__(self) -> None:
        self._backend: TraceBackend | None = None

    def set_backend(self, backend: TraceBackend) -> None:
        """Set the backend where captured traces are emitted."""
        self._backend = backend

    def wrap(self, endpoint: Any) -> Any:
        """Wrap an OpenAI client with trace capture.

        Patches the `chat.completions.create` method to capture traces.
        Returns the client with instrumented methods.
        """
        if hasattr(endpoint, "chat") and hasattr(endpoint.chat, "completions"):
            original_create = endpoint.chat.completions.create
            backend = self._backend

            def instrumented_create(*args: Any, **kwargs: Any) -> Any:
                start = time.monotonic()
                error_type = None
                status_code = 200
                output = None
                model = kwargs.get("model", "unknown")
                messages = kwargs.get("messages", [])

                try:
                    output = original_create(*args, **kwargs)
                    return output
                except Exception as exc:
                    error_type = type(exc).__name__
                    status_code = 500
                    raise
                finally:
                    latency_ms = (time.monotonic() - start) * 1000

                    # Extract token usage from response
                    input_tokens = None
                    output_tokens = None
                    output_text = None
                    response_model = None

                    if output and hasattr(output, "usage") and output.usage:
                        input_tokens = getattr(output.usage, "prompt_tokens", None)
                        output_tokens = getattr(output.usage, "completion_tokens", None)

                    if output and hasattr(output, "model"):
                        response_model = output.model

                    if output and hasattr(output, "choices") and output.choices:
                        first = output.choices[0]
                        if hasattr(first, "message") and hasattr(first.message, "content"):
                            output_text = first.message.content

                    trace = create_trace(
                        gen_ai_system="openai",
                        gen_ai_operation="chat",
                        gen_ai_request_model=model,
                        gen_ai_usage_input_tokens=input_tokens,
                        gen_ai_usage_output_tokens=output_tokens,
                        input_data=messages,
                        output_data=output_text,
                        latency_ms=latency_ms,
                        status_code=status_code,
                        error_type=error_type,
                        attributes={"response_model": response_model},
                    )
                    if backend:
                        try:
                            backend.emit([trace])
                        except Exception as emit_exc:
                            logger.error("Failed to emit OpenAI trace: %s", emit_exc)

            endpoint.chat.completions.create = instrumented_create

        return endpoint
