"""LangChain callback handler for capturing chain/LLM traces."""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from arceval.core.protocols import TraceBackend
from arceval.core.trace_model import create_trace

logger = logging.getLogger(__name__)

try:
    from langchain_core.callbacks import BaseCallbackHandler

    HAS_LANGCHAIN = True
except ImportError:
    try:
        from langchain.callbacks.base import BaseCallbackHandler

        HAS_LANGCHAIN = True
    except ImportError:
        HAS_LANGCHAIN = False


if HAS_LANGCHAIN:
    class _LangChainHandler(BaseCallbackHandler):
        """LangChain callback handler that emits ArcEval traces."""

        def __init__(self, backend: TraceBackend | None = None) -> None:
            super().__init__()
            self._backend = backend
            self._start_times: dict[str, float] = {}

        def on_llm_start(
            self, serialized: dict[str, Any], prompts: list[str], *, run_id: UUID, **kwargs: Any
        ) -> None:
            self._start_times[str(run_id)] = time.monotonic()

        def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
            start = self._start_times.pop(str(run_id), time.monotonic())
            latency_ms = (time.monotonic() - start) * 1000

            output_text = ""
            if hasattr(response, "generations") and response.generations:
                first_gen = response.generations[0]
                if first_gen:
                    output_text = first_gen[0].text if hasattr(first_gen[0], "text") else str(first_gen[0])

            token_usage = {}
            if hasattr(response, "llm_output") and response.llm_output:
                token_usage = response.llm_output.get("token_usage", {})

            trace = create_trace(
                gen_ai_system="langchain",
                gen_ai_operation="llm_call",
                latency_ms=latency_ms,
                status_code=200,
                output_data=output_text,
                gen_ai_usage_input_tokens=token_usage.get("prompt_tokens"),
                gen_ai_usage_output_tokens=token_usage.get("completion_tokens"),
                attributes={"run_id": str(run_id)},
            )
            if self._backend:
                try:
                    self._backend.emit([trace])
                except Exception as exc:
                    logger.error("Failed to emit LangChain trace: %s", exc)

        def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
            start = self._start_times.pop(str(run_id), time.monotonic())
            latency_ms = (time.monotonic() - start) * 1000

            trace = create_trace(
                gen_ai_system="langchain",
                gen_ai_operation="llm_call",
                latency_ms=latency_ms,
                status_code=500,
                error_type=type(error).__name__,
                attributes={"run_id": str(run_id), "error_message": str(error)},
            )
            if self._backend:
                try:
                    self._backend.emit([trace])
                except Exception as exc:
                    logger.error("Failed to emit LangChain error trace: %s", exc)

        def on_chain_start(
            self, serialized: dict[str, Any], inputs: dict[str, Any], *, run_id: UUID, **kwargs: Any
        ) -> None:
            self._start_times[str(run_id)] = time.monotonic()

        def on_chain_end(self, outputs: dict[str, Any], *, run_id: UUID, **kwargs: Any) -> None:
            start = self._start_times.pop(str(run_id), time.monotonic())
            latency_ms = (time.monotonic() - start) * 1000

            trace = create_trace(
                gen_ai_system="langchain",
                gen_ai_operation="chain",
                latency_ms=latency_ms,
                status_code=200,
                output_data=outputs,
                attributes={"run_id": str(run_id)},
            )
            if self._backend:
                try:
                    self._backend.emit([trace])
                except Exception as exc:
                    logger.error("Failed to emit LangChain chain trace: %s", exc)

        def on_tool_start(
            self, serialized: dict[str, Any], input_str: str, *, run_id: UUID, **kwargs: Any
        ) -> None:
            self._start_times[str(run_id)] = time.monotonic()

        def on_tool_end(self, output: str, *, run_id: UUID, **kwargs: Any) -> None:
            start = self._start_times.pop(str(run_id), time.monotonic())
            latency_ms = (time.monotonic() - start) * 1000

            trace = create_trace(
                gen_ai_system="langchain",
                gen_ai_operation="tool_call",
                latency_ms=latency_ms,
                status_code=200,
                output_data=output,
                attributes={"run_id": str(run_id)},
            )
            if self._backend:
                try:
                    self._backend.emit([trace])
                except Exception as exc:
                    logger.error("Failed to emit LangChain tool trace: %s", exc)


class LangChainCapture:
    """Capture middleware for LangChain using callback handlers.

    Usage:
        capture = LangChainCapture()
        capture.set_backend(backend)
        handler = capture.get_handler()

        # Use with any LangChain component
        chain.invoke(input, config={"callbacks": [handler]})
    """

    def __init__(self) -> None:
        self._backend: TraceBackend | None = None

    def set_backend(self, backend: TraceBackend) -> None:
        """Set the backend where captured traces are emitted."""
        self._backend = backend

    def wrap(self, endpoint: Any) -> Any:
        """Wrap a LangChain runnable with the callback handler.

        If the endpoint has a `with_config` method, attaches the callback.
        Otherwise returns the endpoint unchanged.
        """
        if not HAS_LANGCHAIN:
            logger.warning("LangChain not installed; returning endpoint unwrapped")
            return endpoint

        handler = self.get_handler()
        if hasattr(endpoint, "with_config"):
            return endpoint.with_config(callbacks=[handler])
        return endpoint

    def get_handler(self) -> Any:
        """Return a LangChain callback handler.

        Raises ImportError if LangChain is not installed.
        """
        if not HAS_LANGCHAIN:
            raise ImportError(
                "LangChain is not installed. Install with: pip install langchain-core"
            )
        return _LangChainHandler(backend=self._backend)
