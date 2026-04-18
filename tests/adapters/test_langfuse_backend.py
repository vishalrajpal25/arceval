"""Tests for the Langfuse backend adapter.

These tests verify import gating. Full integration tests require langfuse installed.
"""

import pytest

from arceval.backends.langfuse import HAS_LANGFUSE, LangfuseBackend
from arceval.core.exceptions import BackendError


@pytest.mark.skipif(HAS_LANGFUSE, reason="Tests import gating when langfuse is NOT installed")
class TestLangfuseBackendNoLangfuse:
    def test_raises_without_langfuse(self):
        with pytest.raises(BackendError, match="Langfuse is not installed"):
            LangfuseBackend()


@pytest.mark.skipif(not HAS_LANGFUSE, reason="Requires langfuse installed")
class TestLangfuseBackendWithLangfuse:
    def test_instantiate(self):
        # Would need valid credentials for full test
        pass
