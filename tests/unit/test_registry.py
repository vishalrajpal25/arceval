"""Tests for arceval.core.registry."""

import pytest

from arceval.core.exceptions import RegistryError
from arceval.core.registry import Registry


class FakeBackend:
    def __init__(self, path: str = "/tmp") -> None:
        self.path = path

    def emit(self, traces): ...
    def query(self, **kw): ...
    def store_scores(self, scores): ...
    def health_check(self): return True


class FakeScorer:
    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    @property
    def name(self): return "fake"
    @property
    def tier(self): ...
    def score_trace(self, trace): ...
    def score_with_golden(self, trace, golden): ...
    def validate_config(self): return []


class TestRegistry:
    def setup_method(self):
        self.registry = Registry()

    def test_register_and_get_backend(self):
        self.registry.register_backend("fake", FakeBackend)
        backend = self.registry.get_backend("fake", {"path": "/data"})
        assert backend.path == "/data"

    def test_register_and_get_scorer(self):
        self.registry.register_scorer("fake.scorer", FakeScorer)
        scorer = self.registry.get_scorer("fake.scorer", {"threshold": 0.9})
        assert scorer.threshold == 0.9

    def test_get_unknown_backend_raises(self):
        with pytest.raises(RegistryError, match="No backend"):
            self.registry.get_backend("nonexistent")

    def test_get_unknown_scorer_raises(self):
        with pytest.raises(RegistryError, match="No scorer"):
            self.registry.get_scorer("nonexistent")

    def test_list_backends(self):
        self.registry.register_backend("b", FakeBackend)
        self.registry.register_backend("a", FakeBackend)
        assert self.registry.list_backends() == ["a", "b"]

    def test_list_scorers(self):
        self.registry.register_scorer("z", FakeScorer)
        self.registry.register_scorer("a", FakeScorer)
        assert self.registry.list_scorers() == ["a", "z"]

    def test_get_backend_no_config(self):
        self.registry.register_backend("fake", FakeBackend)
        backend = self.registry.get_backend("fake")
        assert backend.path == "/tmp"

    def test_register_capture_and_alert(self):
        class FakeCapture:
            def __init__(self): ...
            def wrap(self, ep): ...
            def set_backend(self, b): ...

        class FakeAlert:
            def __init__(self): ...
            def send(self, a): ...

        self.registry.register_capture("fake_cap", FakeCapture)
        self.registry.register_alert("fake_alert", FakeAlert)

        assert self.registry.list_captures() == ["fake_cap"]
        assert self.registry.list_alerts() == ["fake_alert"]

        cap = self.registry.get_capture("fake_cap")
        alert = self.registry.get_alert("fake_alert")
        assert cap is not None
        assert alert is not None
