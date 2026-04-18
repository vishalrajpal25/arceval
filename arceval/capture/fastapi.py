"""FastAPI middleware for capturing HTTP request/response traces."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from arceval.core.protocols import TraceBackend
from arceval.core.trace_model import create_trace

logger = logging.getLogger(__name__)

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    HAS_STARLETTE = True
except ImportError:
    HAS_STARLETTE = False


class FastAPICapture:
    """ASGI middleware that captures HTTP request/response traces.

    Usage with FastAPI:
        from arceval.capture.fastapi import FastAPICapture
        from arceval.backends.file import FileBackend

        capture = FastAPICapture()
        capture.set_backend(FileBackend(path="./traces/"))

        app = FastAPI()
        app.add_middleware(capture.middleware_class())

    Usage without FastAPI (wraps any ASGI app):
        capture = FastAPICapture()
        capture.set_backend(backend)
        wrapped = capture.wrap(app)
    """

    def __init__(self) -> None:
        self._backend: TraceBackend | None = None

    def set_backend(self, backend: TraceBackend) -> None:
        """Set the backend where captured traces are emitted."""
        self._backend = backend

    def wrap(self, endpoint: Any) -> Any:
        """Wrap an ASGI application with trace capture middleware.

        Returns the wrapped ASGI app.
        """
        backend = self._backend

        async def asgi_wrapper(scope: dict, receive: Callable, send: Callable) -> None:
            if scope["type"] != "http":
                await endpoint(scope, receive, send)
                return

            start = time.monotonic()
            status_code = 500
            error_type = None

            original_send = send

            async def capture_send(message: dict) -> None:
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message.get("status", 200)
                await original_send(message)

            try:
                await endpoint(scope, receive, capture_send)
            except Exception as exc:
                error_type = type(exc).__name__
                raise
            finally:
                latency_ms = (time.monotonic() - start) * 1000
                path = scope.get("path", "/")
                method = scope.get("method", "GET")

                trace = create_trace(
                    gen_ai_system="http",
                    gen_ai_operation=f"{method} {path}",
                    latency_ms=latency_ms,
                    status_code=status_code,
                    error_type=error_type,
                    attributes={
                        "http.method": method,
                        "http.path": path,
                        "http.scheme": scope.get("scheme", "http"),
                    },
                )
                if backend:
                    try:
                        backend.emit([trace])
                    except Exception as exc:
                        logger.error("Failed to emit FastAPI trace: %s", exc)

        return asgi_wrapper

    def middleware_class(self) -> type | None:
        """Return a Starlette BaseHTTPMiddleware class for use with app.add_middleware().

        Returns None if starlette is not installed.
        """
        if not HAS_STARLETTE:
            return None

        backend = self._backend

        class ArcEvalMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next: Callable) -> Response:
                start = time.monotonic()
                error_type = None
                status_code = 500

                try:
                    response = await call_next(request)
                    status_code = response.status_code
                    return response
                except Exception as exc:
                    error_type = type(exc).__name__
                    raise
                finally:
                    latency_ms = (time.monotonic() - start) * 1000
                    trace = create_trace(
                        gen_ai_system="http",
                        gen_ai_operation=f"{request.method} {request.url.path}",
                        latency_ms=latency_ms,
                        status_code=status_code,
                        error_type=error_type,
                        attributes={
                            "http.method": request.method,
                            "http.path": request.url.path,
                            "http.scheme": request.url.scheme,
                        },
                    )
                    if backend:
                        try:
                            backend.emit([trace])
                        except Exception as emit_exc:
                            logger.error("Failed to emit FastAPI trace: %s", emit_exc)

        return ArcEvalMiddleware
