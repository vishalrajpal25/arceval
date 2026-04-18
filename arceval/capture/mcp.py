"""MCP server middleware: intercepts tool calls and produces traces."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from arceval.core.protocols import TraceBackend
from arceval.core.trace_model import Trace, create_trace

logger = logging.getLogger(__name__)


class MCPCapture:
    """Instruments an MCP server to capture tool call traces.

    Wraps MCP tool handlers to record input/output, latency, and errors
    as ArcEval traces.

    Usage:
        capture = MCPCapture()
        capture.set_backend(file_backend)

        # Wrap individual tool handlers
        original_handler = server.get_handler("get_pricing")
        server.set_handler("get_pricing", capture.wrap_handler(original_handler, "get_pricing"))

        # Or wrap the entire server object (if it follows the MCP protocol)
        wrapped_server = capture.wrap(server)
    """

    def __init__(self) -> None:
        self._backend: TraceBackend | None = None

    def set_backend(self, backend: TraceBackend) -> None:
        """Set the backend where captured traces are emitted."""
        self._backend = backend

    def wrap(self, endpoint: Any) -> Any:
        """Wrap an MCP server object with instrumentation.

        Looks for a `call_tool` or `handle_request` method to wrap.
        Returns the server with instrumented methods.
        """
        if hasattr(endpoint, "call_tool"):
            original_call_tool = endpoint.call_tool

            async def instrumented_call_tool(name: str, arguments: dict | None = None, **kwargs: Any) -> Any:
                return await self._capture_async(
                    func=original_call_tool,
                    args=(name,),
                    kwargs={"arguments": arguments, **kwargs},
                    tool_name=name,
                    input_data=arguments,
                )

            endpoint.call_tool = instrumented_call_tool

        elif hasattr(endpoint, "handle_request"):
            original_handle = endpoint.handle_request

            async def instrumented_handle(request: Any, **kwargs: Any) -> Any:
                tool_name = getattr(request, "method", "unknown")
                return await self._capture_async(
                    func=original_handle,
                    args=(request,),
                    kwargs=kwargs,
                    tool_name=tool_name,
                    input_data=getattr(request, "params", None),
                )

            endpoint.handle_request = instrumented_handle

        return endpoint

    def wrap_handler(
        self, handler: Callable, tool_name: str
    ) -> Callable:
        """Wrap a single sync tool handler with trace capture."""
        def instrumented(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            error_type = None
            status_code = 200
            output = None

            try:
                output = handler(*args, **kwargs)
                return output
            except Exception as exc:
                error_type = type(exc).__name__
                status_code = 500
                raise
            finally:
                latency_ms = (time.monotonic() - start) * 1000
                self._emit_trace(
                    tool_name=tool_name,
                    input_data={"args": args, "kwargs": kwargs} if args or kwargs else kwargs,
                    output_data=output,
                    latency_ms=latency_ms,
                    status_code=status_code,
                    error_type=error_type,
                )

        return instrumented

    def wrap_async_handler(
        self, handler: Callable, tool_name: str
    ) -> Callable:
        """Wrap a single async tool handler with trace capture."""
        async def instrumented(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            error_type = None
            status_code = 200
            output = None

            try:
                output = await handler(*args, **kwargs)
                return output
            except Exception as exc:
                error_type = type(exc).__name__
                status_code = 500
                raise
            finally:
                latency_ms = (time.monotonic() - start) * 1000
                self._emit_trace(
                    tool_name=tool_name,
                    input_data={"args": args, "kwargs": kwargs} if args or kwargs else kwargs,
                    output_data=output,
                    latency_ms=latency_ms,
                    status_code=status_code,
                    error_type=error_type,
                )

        return instrumented

    async def _capture_async(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        tool_name: str,
        input_data: Any,
    ) -> Any:
        """Capture an async call with timing and error handling."""
        start = time.monotonic()
        error_type = None
        status_code = 200
        output = None

        try:
            output = await func(*args, **kwargs)
            return output
        except Exception as exc:
            error_type = type(exc).__name__
            status_code = 500
            raise
        finally:
            latency_ms = (time.monotonic() - start) * 1000
            self._emit_trace(
                tool_name=tool_name,
                input_data=input_data,
                output_data=output,
                latency_ms=latency_ms,
                status_code=status_code,
                error_type=error_type,
            )

    def _emit_trace(
        self,
        tool_name: str,
        input_data: Any,
        output_data: Any,
        latency_ms: float,
        status_code: int,
        error_type: str | None,
    ) -> None:
        """Create and emit a trace."""
        trace = create_trace(
            gen_ai_system="mcp",
            gen_ai_operation="tool_call",
            input_data=input_data,
            output_data=output_data,
            latency_ms=latency_ms,
            status_code=status_code,
            error_type=error_type,
            attributes={"tool_name": tool_name},
        )
        if self._backend:
            try:
                self._backend.emit([trace])
            except Exception as exc:
                logger.error("Failed to emit MCP trace: %s", exc)
