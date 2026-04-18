"""Tests for arceval.core.exceptions."""

from arceval.core.exceptions import (
    ArcEvalError,
    BackendError,
    CaptureError,
    ConfigError,
    ConfigFileNotFoundError,
    ConfigValidationError,
    GateError,
    GoldenSetError,
    RegistryError,
    ScorerError,
)


def test_hierarchy():
    """All custom exceptions inherit from ArcEvalError."""
    assert issubclass(ConfigError, ArcEvalError)
    assert issubclass(ConfigFileNotFoundError, ConfigError)
    assert issubclass(ConfigValidationError, ConfigError)
    assert issubclass(RegistryError, ArcEvalError)
    assert issubclass(BackendError, ArcEvalError)
    assert issubclass(ScorerError, ArcEvalError)
    assert issubclass(CaptureError, ArcEvalError)
    assert issubclass(GoldenSetError, ArcEvalError)
    assert issubclass(GateError, ArcEvalError)


def test_config_validation_error_stores_errors():
    errors = ["field missing", "bad type"]
    exc = ConfigValidationError(errors)
    assert exc.errors == errors
    assert "2 error(s)" in str(exc)
    assert "field missing" in str(exc)
    assert "bad type" in str(exc)


def test_config_validation_error_single():
    exc = ConfigValidationError(["one issue"])
    assert exc.errors == ["one issue"]
    assert "1 error(s)" in str(exc)
