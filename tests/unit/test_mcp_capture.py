"""Tests for MCP capture middleware."""

import asyncio

from arceval.backends.file import FileBackend
from arceval.capture.mcp import MCPCapture


class TestMCPCapture:
    def test_wrap_handler_success(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        capture = MCPCapture()
        capture.set_backend(backend)

        def my_tool(query: str) -> dict:
            return {"result": query.upper()}

        wrapped = capture.wrap_handler(my_tool, "my_tool")
        result = wrapped("hello")

        assert result == {"result": "HELLO"}
        traces = backend.query()
        assert len(traces) == 1
        assert traces[0].attributes["tool_name"] == "my_tool"
        assert traces[0].gen_ai_system == "mcp"
        assert traces[0].gen_ai_operation == "tool_call"
        assert traces[0].status_code == 200
        assert traces[0].latency_ms > 0

    def test_wrap_handler_error(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        capture = MCPCapture()
        capture.set_backend(backend)

        def failing_tool() -> None:
            raise ValueError("boom")

        wrapped = capture.wrap_handler(failing_tool, "failing_tool")
        try:
            wrapped()
        except ValueError:
            pass

        traces = backend.query()
        assert len(traces) == 1
        assert traces[0].error_type == "ValueError"
        assert traces[0].status_code == 500

    def test_wrap_async_handler(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        capture = MCPCapture()
        capture.set_backend(backend)

        async def async_tool(x: int) -> int:
            return x * 2

        wrapped = capture.wrap_async_handler(async_tool, "async_tool")
        result = asyncio.get_event_loop().run_until_complete(wrapped(5))

        assert result == 10
        traces = backend.query()
        assert len(traces) == 1
        assert traces[0].attributes["tool_name"] == "async_tool"

    def test_no_backend_no_error(self):
        capture = MCPCapture()

        def tool() -> str:
            return "ok"

        wrapped = capture.wrap_handler(tool, "tool")
        assert wrapped() == "ok"

    def test_wrap_object_with_call_tool(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        capture = MCPCapture()
        capture.set_backend(backend)

        class FakeMCPServer:
            async def call_tool(self, name: str, arguments: dict | None = None) -> dict:
                return {"result": f"called {name}"}

        server = FakeMCPServer()
        wrapped = capture.wrap(server)

        result = asyncio.get_event_loop().run_until_complete(
            wrapped.call_tool("test_tool", {"arg": "val"})
        )
        assert result == {"result": "called test_tool"}
        traces = backend.query()
        assert len(traces) == 1
        assert traces[0].attributes["tool_name"] == "test_tool"
