"""Pytest plugin for ArcEval: run evals as pytest tests.

Usage:
    pytest --arceval --arceval-config=arceval.yaml --arceval-tier=t1

Or programmatically:
    def test_evals(arceval_runner):
        results = arceval_runner.test(golden_set="fundamentals", tiers=["t1"])
        assert results.t1.all_passed
"""

from __future__ import annotations

from typing import Any

import pytest


def pytest_addoption(parser: Any) -> None:
    """Add ArcEval CLI options to pytest."""
    group = parser.getgroup("arceval", "ArcEval evaluation options")
    group.addoption(
        "--arceval",
        action="store_true",
        default=False,
        help="Enable ArcEval evaluation tests.",
    )
    group.addoption(
        "--arceval-config",
        default="arceval.yaml",
        help="Path to arceval.yaml config file.",
    )
    group.addoption(
        "--arceval-tier",
        default=None,
        help="Comma-separated tiers to run (e.g. t1,t2).",
    )


class ArcEvalRunner:
    """Pytest fixture providing access to ArcEval test runner."""

    def __init__(self, config_path: str, tiers: list[str] | None = None) -> None:
        self._config_path = config_path
        self._tiers = tiers

    def test(
        self,
        golden_set: str | None = None,
        tiers: list[str] | None = None,
        fail_on: str = "t1",
        warn_on: str = "t2",
    ) -> Any:
        """Run ArcEval scorers and return results.

        Args:
            golden_set: name of golden set to test (None = all)
            tiers: tier filter override
            fail_on: tier that causes assertion failure
            warn_on: tier that causes warning

        Returns:
            TestRunResult from the test runner.
        """
        from arceval.core.config import load_config
        from arceval.core.registry import default_registry
        from arceval.testing.golden_sets import load_golden_set
        from arceval.testing.runner import EvalTestRunner
        from arceval.core.trace_model import create_trace

        config = load_config(self._config_path)

        # Load scorers
        scorers = []
        for scorer_cfg in config.scorers:
            try:
                scorer = default_registry.get_scorer(
                    scorer_cfg.type,
                    {**scorer_cfg.config, "tier": scorer_cfg.tier, "name": scorer_cfg.name},
                )
                scorers.append(scorer)
            except Exception:
                continue

        # Load golden sets
        effective_tiers = tiers or self._tiers
        traces = []
        golden_records = []

        if config.golden_sets and config.golden_sets.sets:
            sets_to_load = config.golden_sets.sets
            if golden_set:
                sets_to_load = [s for s in sets_to_load if s.name == golden_set]

            for gs_entry in sets_to_load:
                gs_path = f"{config.golden_sets.path}/{gs_entry.file}"
                try:
                    records = load_golden_set(gs_path, format=config.golden_sets.format)
                    for record in records:
                        golden_records.append(record)
                        trace = create_trace(
                            input_data=record.input_data,
                            output_data=record.expected_output,
                            status_code=200,
                            latency_ms=record.metadata.get("latency_ms"),
                            attributes=record.metadata,
                        )
                        traces.append(trace)
                except Exception:
                    continue

        runner = EvalTestRunner(scorers, config=config)
        return runner.run(
            traces=traces,
            golden_records=golden_records if golden_records else None,
            tiers=effective_tiers,
            fail_on=fail_on,
            warn_on=warn_on,
        )


@pytest.fixture
def arceval_runner(request: Any) -> ArcEvalRunner:
    """Pytest fixture that provides an ArcEval test runner."""
    config_path = request.config.getoption("--arceval-config", default="arceval.yaml")
    tiers_str = request.config.getoption("--arceval-tier", default=None)
    tiers = [t.strip() for t in tiers_str.split(",")] if tiers_str else None
    return ArcEvalRunner(config_path=config_path, tiers=tiers)
