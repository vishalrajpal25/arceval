"""Registry for discovering and loading plugins."""

from __future__ import annotations

from typing import Any

from arceval.core.exceptions import RegistryError
from arceval.core.protocols import AlertSink, CaptureMiddleware, Scorer, TraceBackend


class Registry:
    """Global registry for backends, scorers, capture adapters, and alert sinks.

    Plugins are registered by type string and instantiated with config dicts.
    """

    def __init__(self) -> None:
        self._backends: dict[str, type] = {}
        self._scorers: dict[str, type] = {}
        self._captures: dict[str, type] = {}
        self._alerts: dict[str, type] = {}

    # -- Registration --

    def register_backend(self, name: str, cls: type) -> None:
        """Register a TraceBackend implementation."""
        self._backends[name] = cls

    def register_scorer(self, name: str, cls: type) -> None:
        """Register a Scorer implementation."""
        self._scorers[name] = cls

    def register_capture(self, name: str, cls: type) -> None:
        """Register a CaptureMiddleware implementation."""
        self._captures[name] = cls

    def register_alert(self, name: str, cls: type) -> None:
        """Register an AlertSink implementation."""
        self._alerts[name] = cls

    # -- Lookup --

    def get_backend(self, name: str, config: dict[str, Any] | None = None) -> TraceBackend:
        """Instantiate a registered backend by name."""
        cls = self._lookup(self._backends, "backend", name)
        return cls(**(config or {}))

    def get_scorer(self, name: str, config: dict[str, Any] | None = None) -> Scorer:
        """Instantiate a registered scorer by name."""
        cls = self._lookup(self._scorers, "scorer", name)
        return cls(**(config or {}))

    def get_capture(self, name: str, config: dict[str, Any] | None = None) -> CaptureMiddleware:
        """Instantiate a registered capture adapter by name."""
        cls = self._lookup(self._captures, "capture", name)
        return cls(**(config or {}))

    def get_alert(self, name: str, config: dict[str, Any] | None = None) -> AlertSink:
        """Instantiate a registered alert sink by name."""
        cls = self._lookup(self._alerts, "alert", name)
        return cls(**(config or {}))

    # -- Listing --

    def list_backends(self) -> list[str]:
        """Return all registered backend names."""
        return sorted(self._backends.keys())

    def list_scorers(self) -> list[str]:
        """Return all registered scorer names."""
        return sorted(self._scorers.keys())

    def list_captures(self) -> list[str]:
        """Return all registered capture adapter names."""
        return sorted(self._captures.keys())

    def list_alerts(self) -> list[str]:
        """Return all registered alert sink names."""
        return sorted(self._alerts.keys())

    # -- Internal --

    @staticmethod
    def _lookup(store: dict[str, type], kind: str, name: str) -> type:
        if name not in store:
            available = ", ".join(sorted(store.keys())) or "(none)"
            raise RegistryError(
                f"No {kind} registered with name '{name}'. Available: {available}"
            )
        return store[name]


# Module-level default registry
default_registry = Registry()
