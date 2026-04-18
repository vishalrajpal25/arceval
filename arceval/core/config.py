"""YAML config parsing and validation via Pydantic models."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator, model_validator

from arceval.core.exceptions import ConfigFileNotFoundError, ConfigValidationError


# ── Endpoint config ──────────────────────────────────────────────────────


class EndpointConfig(BaseModel):
    """Configuration for the endpoint under evaluation."""

    type: str  # mcp | rag | agent | chatbot | http
    name: str = ""
    mcp: dict[str, Any] | None = None
    rag: dict[str, Any] | None = None
    agent: dict[str, Any] | None = None
    chatbot: dict[str, Any] | None = None
    http: dict[str, Any] | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"mcp", "rag", "agent", "chatbot", "http"}
        if v not in allowed:
            raise ValueError(f"endpoint.type must be one of {allowed}, got '{v}'")
        return v


# ── Backend config ───────────────────────────────────────────────────────


class BackendConfig(BaseModel):
    """Configuration for a single trace backend."""

    type: str  # mlflow | langfuse | otel | file | delta
    model_config = {"extra": "allow"}

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"mlflow", "langfuse", "otel", "file", "delta"}
        if v not in allowed:
            raise ValueError(f"backend.type must be one of {allowed}, got '{v}'")
        return v


# ── Tier config ──────────────────────────────────────────────────────────


class TierConfig(BaseModel):
    """Configuration for a single tier."""

    name: str = ""
    description: str = ""
    mode: str = "always"  # always | on_golden_set | on_judge
    in_testing: bool = True
    in_monitoring: bool = True
    sample_rate: float = 1.0
    block_deploy: bool = False

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        allowed = {"always", "on_golden_set", "on_judge"}
        if v not in allowed:
            raise ValueError(f"tier.mode must be one of {allowed}, got '{v}'")
        return v

    @field_validator("sample_rate")
    @classmethod
    def validate_sample_rate(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"sample_rate must be between 0.0 and 1.0, got {v}")
        return v


# ── Scorer config ────────────────────────────────────────────────────────


class ScorerConfig(BaseModel):
    """Configuration for a single scorer."""

    name: str
    type: str
    tier: str  # t1 | t2 | t3
    config: dict[str, Any] = {}

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        allowed = {"t1", "t2", "t3"}
        normalized = v.strip().lower()
        if normalized not in allowed:
            raise ValueError(f"scorer.tier must be one of {allowed}, got '{v}'")
        return normalized


# ── Golden set config ────────────────────────────────────────────────────


class GoldenSetEntryConfig(BaseModel):
    """A single golden set file entry."""

    name: str
    file: str
    tools: list[str] = []


class GoldenSetsConfig(BaseModel):
    """Configuration for golden sets."""

    path: str = "./golden_sets/"
    format: str = "jsonl"
    versioned: bool = False
    sets: list[GoldenSetEntryConfig] = []


# ── Alert config ─────────────────────────────────────────────────────────


class AlertConfig(BaseModel):
    """Configuration for a single alert sink."""

    type: str  # slack | pagerduty | webhook
    on: list[str] = []
    model_config = {"extra": "allow"}


# ── Testing config ───────────────────────────────────────────────────────


class TestingConfig(BaseModel):
    """Configuration for eval-as-testing mode."""

    report_format: str = "markdown"
    output_dir: str = "./eval-reports/"
    fail_on: str = "t1"
    warn_on: str = "t2"
    compare_to: str = "latest"


# ── Monitoring config ────────────────────────────────────────────────────


class MonitoringStorageConfig(BaseModel):
    """Storage sub-config for monitoring."""

    results_backend: str = "primary"


class MonitoringConfig(BaseModel):
    """Configuration for eval-as-observability mode."""

    poll_interval_seconds: int = 30
    batch_size: int = 100
    max_concurrent_judges: int = 4
    storage: MonitoringStorageConfig = MonitoringStorageConfig()


# ── Root config ──────────────────────────────────────────────────────────


class ArcEvalConfig(BaseModel):
    """Root configuration model for arceval.yaml."""

    version: str = "1"
    project: str = ""
    endpoint: EndpointConfig
    backends: dict[str, BackendConfig] = {}
    tiers: dict[str, TierConfig] = {}
    scorers: list[ScorerConfig] = []
    golden_sets: GoldenSetsConfig | None = None
    alerts: list[AlertConfig] = []
    testing: TestingConfig = TestingConfig()
    monitoring: MonitoringConfig = MonitoringConfig()

    @model_validator(mode="after")
    def validate_scorer_tiers(self) -> "ArcEvalConfig":
        """Ensure every scorer references a defined tier."""
        defined_tiers = set(self.tiers.keys()) if self.tiers else {"t1", "t2", "t3"}
        for scorer in self.scorers:
            if scorer.tier not in defined_tiers:
                raise ValueError(
                    f"Scorer '{scorer.name}' references undefined tier '{scorer.tier}'. "
                    f"Defined tiers: {defined_tiers}"
                )
        return self

    @model_validator(mode="after")
    def validate_scorer_names_unique(self) -> "ArcEvalConfig":
        """Ensure scorer names are unique."""
        names = [s.name for s in self.scorers]
        dupes = [n for n in names if names.count(n) > 1]
        if dupes:
            raise ValueError(f"Duplicate scorer names: {set(dupes)}")
        return self


def _resolve_env_vars(data: Any) -> Any:
    """Recursively resolve ${ENV_VAR} references in config values."""
    if isinstance(data, str) and data.startswith("${") and data.endswith("}"):
        var_name = data[2:-1]
        return os.environ.get(var_name, data)
    if isinstance(data, dict):
        return {k: _resolve_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_env_vars(v) for v in data]
    return data


def load_config(path: str | Path = "arceval.yaml") -> ArcEvalConfig:
    """Load and validate an arceval.yaml config file.

    Raises ConfigFileNotFoundError if the file does not exist.
    Raises ConfigValidationError if the file fails validation.
    """
    path = Path(path)
    if not path.exists():
        raise ConfigFileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ConfigValidationError(["Config file must be a YAML mapping"])

    resolved = _resolve_env_vars(raw)

    try:
        return ArcEvalConfig(**resolved)
    except Exception as exc:
        raise ConfigValidationError([str(exc)]) from exc


def validate_config(path: str | Path = "arceval.yaml") -> list[str]:
    """Validate a config file and return a list of errors (empty = valid)."""
    errors: list[str] = []
    try:
        load_config(path)
    except ConfigFileNotFoundError as exc:
        errors.append(str(exc))
    except ConfigValidationError as exc:
        errors.extend(exc.errors)
    except Exception as exc:
        errors.append(f"Unexpected error: {exc}")
    return errors
