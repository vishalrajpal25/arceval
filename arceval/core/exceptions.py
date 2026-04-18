"""Custom exceptions for ArcEval."""


class ArcEvalError(Exception):
    """Base exception for all ArcEval errors."""


class ConfigError(ArcEvalError):
    """Raised when arceval.yaml is invalid or missing."""


class ConfigFileNotFoundError(ConfigError):
    """Raised when the config file cannot be found."""


class ConfigValidationError(ConfigError):
    """Raised when config fails schema validation."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        msg = f"Config validation failed with {len(errors)} error(s):\n"
        msg += "\n".join(f"  - {e}" for e in errors)
        super().__init__(msg)


class RegistryError(ArcEvalError):
    """Raised on registry lookup or registration failures."""


class BackendError(ArcEvalError):
    """Raised when a backend operation fails."""


class ScorerError(ArcEvalError):
    """Raised when a scorer operation fails."""


class CaptureError(ArcEvalError):
    """Raised when trace capture fails."""


class GoldenSetError(ArcEvalError):
    """Raised when golden set loading or validation fails."""


class GateError(ArcEvalError):
    """Raised when CI/CD gate evaluation fails."""
