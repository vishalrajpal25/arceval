"""Tests for FastAPI/ASGI capture middleware."""

import asyncio

from arceval.backends.file import FileBackend
from arceval.capture.fastapi import FastAPICapture


class TestFastAPICapture:
    def test_wrap_asgi_app(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        capture = FastAPICapture()
        capture.set_backend(backend)

        async def simple_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        wrapped = capture.wrap(simple_app)

        # Simulate ASGI request
        scope = {"type": "http", "path": "/test", "method": "GET", "scheme": "http"}
        received = []

        async def receive():
            return {"type": "http.request", "body": b""}

        async def send(msg):
            received.append(msg)

        asyncio.get_event_loop().run_until_complete(wrapped(scope, receive, send))

        assert len(received) == 2
        traces = backend.query()
        assert len(traces) == 1
        assert traces[0].gen_ai_operation == "GET /test"
        assert traces[0].status_code == 200
        assert traces[0].latency_ms > 0

    def test_non_http_scope_passthrough(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        capture = FastAPICapture()
        capture.set_backend(backend)

        called = False

        async def ws_app(scope, receive, send):
            nonlocal called
            called = True

        wrapped = capture.wrap(ws_app)
        scope = {"type": "websocket"}

        asyncio.get_event_loop().run_until_complete(
            wrapped(scope, None, None)
        )
        assert called is True
        # No trace should be emitted for non-HTTP
        traces = backend.query()
        assert len(traces) == 0

    def test_error_captures_trace(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        capture = FastAPICapture()
        capture.set_backend(backend)

        async def failing_app(scope, receive, send):
            raise RuntimeError("crash")

        wrapped = capture.wrap(failing_app)
        scope = {"type": "http", "path": "/fail", "method": "POST", "scheme": "http"}

        try:
            asyncio.get_event_loop().run_until_complete(
                wrapped(scope, None, None)
            )
        except RuntimeError:
            pass

        traces = backend.query()
        assert len(traces) == 1
        assert traces[0].error_type == "RuntimeError"

    def test_no_backend_no_error(self):
        capture = FastAPICapture()

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"OK"})

        wrapped = capture.wrap(app)
        scope = {"type": "http", "path": "/", "method": "GET", "scheme": "http"}

        async def receive():
            return {"type": "http.request", "body": b""}

        received = []

        async def send(msg):
            received.append(msg)

        asyncio.get_event_loop().run_until_complete(wrapped(scope, receive, send))
        assert len(received) == 2
