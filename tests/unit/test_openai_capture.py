"""Tests for OpenAI client wrapper capture."""

from arceval.backends.file import FileBackend
from arceval.capture.openai_wrapper import HAS_OPENAI, OpenAICapture


class FakeUsage:
    prompt_tokens = 10
    completion_tokens = 20


class FakeMessage:
    content = "Hello back!"


class FakeChoice:
    message = FakeMessage()


class FakeResponse:
    usage = FakeUsage()
    model = "gpt-4o-2026"
    choices = [FakeChoice()]


class FakeCompletions:
    def create(self, **kwargs):
        return FakeResponse()


class FakeChat:
    completions = FakeCompletions()


class FakeOpenAIClient:
    chat = FakeChat()


class TestOpenAICapture:
    def test_wrap_and_capture(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        capture = OpenAICapture()
        capture.set_backend(backend)

        client = FakeOpenAIClient()
        wrapped = capture.wrap(client)

        response = wrapped.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert response.choices[0].message.content == "Hello back!"
        assert response.usage.prompt_tokens == 10

        traces = backend.query()
        assert len(traces) == 1
        assert traces[0].gen_ai_system == "openai"
        assert traces[0].gen_ai_operation == "chat"
        assert traces[0].gen_ai_request_model == "gpt-4o"
        assert traces[0].gen_ai_usage_input_tokens == 10
        assert traces[0].gen_ai_usage_output_tokens == 20
        assert traces[0].status_code == 200

    def test_wrap_captures_error(self, tmp_path):
        backend = FileBackend(path=str(tmp_path / "traces"))
        capture = OpenAICapture()
        capture.set_backend(backend)

        class FailingCompletions:
            def create(self, **kwargs):
                raise ConnectionError("API down")

        class FailingChat:
            completions = FailingCompletions()

        class FailingClient:
            chat = FailingChat()

        wrapped = capture.wrap(FailingClient())
        try:
            wrapped.chat.completions.create(model="gpt-4o", messages=[])
        except ConnectionError:
            pass

        traces = backend.query()
        assert len(traces) == 1
        assert traces[0].error_type == "ConnectionError"
        assert traces[0].status_code == 500

    def test_no_backend_no_error(self):
        capture = OpenAICapture()
        client = FakeOpenAIClient()
        wrapped = capture.wrap(client)
        response = wrapped.chat.completions.create(model="gpt-4o", messages=[])
        assert response is not None

    def test_wrap_non_openai_object(self):
        capture = OpenAICapture()
        obj = {"not": "openai"}
        result = capture.wrap(obj)
        assert result is obj
