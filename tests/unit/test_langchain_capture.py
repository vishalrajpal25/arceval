"""Tests for LangChain capture middleware."""

import pytest

from arceval.capture.langchain import HAS_LANGCHAIN, LangChainCapture


class TestLangChainCapture:
    def test_instantiate(self):
        capture = LangChainCapture()
        assert capture._backend is None

    def test_set_backend(self, tmp_path):
        from arceval.backends.file import FileBackend

        capture = LangChainCapture()
        backend = FileBackend(path=str(tmp_path / "traces"))
        capture.set_backend(backend)
        assert capture._backend is backend

    @pytest.mark.skipif(not HAS_LANGCHAIN, reason="Requires langchain installed")
    def test_get_handler(self):
        capture = LangChainCapture()
        handler = capture.get_handler()
        assert handler is not None

    @pytest.mark.skipif(HAS_LANGCHAIN, reason="Tests error when langchain NOT installed")
    def test_get_handler_no_langchain(self):
        capture = LangChainCapture()
        with pytest.raises(ImportError, match="LangChain"):
            capture.get_handler()

    def test_wrap_no_langchain_returns_endpoint(self):
        if HAS_LANGCHAIN:
            pytest.skip("Only tests when langchain is NOT installed")
        capture = LangChainCapture()
        obj = object()
        result = capture.wrap(obj)
        assert result is obj
