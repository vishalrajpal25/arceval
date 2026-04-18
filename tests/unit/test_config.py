"""Tests for arceval.core.config."""

import os
import textwrap

import pytest

from arceval.core.config import (
    ArcEvalConfig,
    BackendConfig,
    EndpointConfig,
    ScorerConfig,
    TierConfig,
    load_config,
    validate_config,
    _resolve_env_vars,
)
from arceval.core.exceptions import ConfigFileNotFoundError, ConfigValidationError


class TestEndpointConfig:
    def test_valid_types(self):
        for t in ("mcp", "rag", "agent", "chatbot", "http"):
            cfg = EndpointConfig(type=t, name="test")
            assert cfg.type == t

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="endpoint.type"):
            EndpointConfig(type="invalid")


class TestBackendConfig:
    def test_valid_type(self):
        cfg = BackendConfig(type="file", path="./traces/")
        assert cfg.type == "file"

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="backend.type"):
            BackendConfig(type="redis")

    def test_extra_fields_allowed(self):
        cfg = BackendConfig(type="file", path="./traces/", format="jsonl")
        assert cfg.type == "file"


class TestTierConfig:
    def test_defaults(self):
        cfg = TierConfig()
        assert cfg.mode == "always"
        assert cfg.in_testing is True
        assert cfg.sample_rate == 1.0

    def test_invalid_mode(self):
        with pytest.raises(ValueError, match="tier.mode"):
            TierConfig(mode="never")

    def test_invalid_sample_rate(self):
        with pytest.raises(ValueError, match="sample_rate"):
            TierConfig(sample_rate=1.5)

    def test_negative_sample_rate(self):
        with pytest.raises(ValueError, match="sample_rate"):
            TierConfig(sample_rate=-0.1)


class TestScorerConfig:
    def test_tier_normalized(self):
        cfg = ScorerConfig(name="test", type="builtin.latency", tier="T1")
        assert cfg.tier == "t1"

    def test_invalid_tier(self):
        with pytest.raises(ValueError, match="scorer.tier"):
            ScorerConfig(name="test", type="builtin.latency", tier="t4")


class TestArcEvalConfig:
    def test_minimal_valid(self):
        cfg = ArcEvalConfig(
            endpoint=EndpointConfig(type="http"),
        )
        assert cfg.version == "1"
        assert cfg.endpoint.type == "http"

    def test_duplicate_scorer_names(self):
        with pytest.raises(ValueError, match="Duplicate scorer"):
            ArcEvalConfig(
                endpoint=EndpointConfig(type="http"),
                tiers={"t1": TierConfig()},
                scorers=[
                    ScorerConfig(name="dup", type="builtin.latency", tier="t1"),
                    ScorerConfig(name="dup", type="builtin.error_rate", tier="t1"),
                ],
            )

    def test_scorer_references_undefined_tier(self):
        with pytest.raises(ValueError, match="undefined tier"):
            ArcEvalConfig(
                endpoint=EndpointConfig(type="http"),
                tiers={"t1": TierConfig()},
                scorers=[
                    ScorerConfig(name="test", type="builtin.latency", tier="t2"),
                ],
            )

    def test_scorer_tier_valid_when_defined(self):
        cfg = ArcEvalConfig(
            endpoint=EndpointConfig(type="http"),
            tiers={"t1": TierConfig(), "t2": TierConfig()},
            scorers=[
                ScorerConfig(name="lat", type="builtin.latency", tier="t1"),
                ScorerConfig(name="err", type="builtin.error_rate", tier="t2"),
            ],
        )
        assert len(cfg.scorers) == 2


class TestResolveEnvVars:
    def test_resolves_env_var(self, monkeypatch):
        monkeypatch.setenv("MY_KEY", "secret123")
        assert _resolve_env_vars("${MY_KEY}") == "secret123"

    def test_missing_env_var_kept(self):
        result = _resolve_env_vars("${NONEXISTENT_VAR_XYZ}")
        assert result == "${NONEXISTENT_VAR_XYZ}"

    def test_recursive_dict(self, monkeypatch):
        monkeypatch.setenv("DB_HOST", "localhost")
        data = {"host": "${DB_HOST}", "port": 5432}
        result = _resolve_env_vars(data)
        assert result == {"host": "localhost", "port": 5432}

    def test_recursive_list(self, monkeypatch):
        monkeypatch.setenv("ITEM", "val")
        assert _resolve_env_vars(["${ITEM}", "static"]) == ["val", "static"]

    def test_non_string_passthrough(self):
        assert _resolve_env_vars(42) == 42
        assert _resolve_env_vars(None) is None


class TestLoadConfig:
    def test_file_not_found(self):
        with pytest.raises(ConfigFileNotFoundError):
            load_config("/nonexistent/arceval.yaml")

    def test_valid_file(self, tmp_path):
        cfg_file = tmp_path / "arceval.yaml"
        cfg_file.write_text(textwrap.dedent("""\
            version: "1"
            project: "test"
            endpoint:
              type: http
              name: "Test"
            backends:
              dev:
                type: file
                path: "./traces/"
            tiers:
              t1:
                name: "Must-Have"
                mode: always
            scorers:
              - name: latency
                type: builtin.latency
                tier: t1
                config:
                  threshold_ms: 2000
        """))
        config = load_config(cfg_file)
        assert config.project == "test"
        assert config.endpoint.type == "http"
        assert len(config.scorers) == 1
        assert "dev" in config.backends

    def test_invalid_yaml_content(self, tmp_path):
        cfg_file = tmp_path / "arceval.yaml"
        cfg_file.write_text("just a string, not a mapping")
        with pytest.raises(ConfigValidationError, match="YAML mapping"):
            load_config(cfg_file)


class TestValidateConfig:
    def test_returns_errors_for_missing_file(self):
        errors = validate_config("/nonexistent/arceval.yaml")
        assert len(errors) > 0

    def test_returns_empty_for_valid(self, tmp_path):
        cfg_file = tmp_path / "arceval.yaml"
        cfg_file.write_text(textwrap.dedent("""\
            version: "1"
            project: "test"
            endpoint:
              type: http
        """))
        errors = validate_config(cfg_file)
        assert errors == []
