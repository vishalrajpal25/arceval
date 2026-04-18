"""Test runner: orchestrates scoring against golden sets and produces reports."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arceval.core.config import ArcEvalConfig
from arceval.core.protocols import GoldenRecord, ScoreResult, Scorer
from arceval.core.tier import Tier, filter_tiers
from arceval.core.trace_model import Trace
from arceval.testing.gates import GateResult, evaluate_gates


@dataclass
class TestRunResult:
    """Complete results from a test run."""

    project: str
    timestamp: str
    results: list[ScoreResult] = field(default_factory=list)
    gate_result: GateResult | None = None
    traces_scored: int = 0
    duration_ms: float = 0.0

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.passed) / len(self.results)


class EvalTestRunner:
    """Orchestrates eval-as-testing: runs scorers against traces, applies gates."""

    def __init__(
        self,
        scorers: list[Scorer],
        config: ArcEvalConfig | None = None,
    ) -> None:
        self._scorers = scorers
        self._config = config

    def run(
        self,
        traces: list[Trace],
        golden_records: list[GoldenRecord] | None = None,
        tiers: list[str] | None = None,
        fail_on: str = "t1",
        warn_on: str = "t2",
    ) -> TestRunResult:
        """Run all applicable scorers against traces.

        Args:
            traces: traces to score
            golden_records: optional golden records for comparison scoring.
                           If provided, must be same length as traces (paired).
            tiers: optional tier filter (e.g. ["t1", "t2"])
            fail_on: tier that causes CI failure
            warn_on: tier that causes CI warning

        Returns:
            TestRunResult with all scores and gate verdict.
        """
        start = datetime.now(timezone.utc)
        requested_tiers = filter_tiers(tiers)
        active_scorers = [s for s in self._scorers if s.tier in requested_tiers]

        all_results: list[ScoreResult] = []

        for i, trace in enumerate(traces):
            golden = golden_records[i] if golden_records and i < len(golden_records) else None
            for scorer in active_scorers:
                if golden is not None:
                    result = scorer.score_with_golden(trace, golden)
                else:
                    result = scorer.score_trace(trace)
                all_results.append(result)

        end = datetime.now(timezone.utc)
        duration_ms = (end - start).total_seconds() * 1000

        gate_result = evaluate_gates(all_results, fail_on=fail_on, warn_on=warn_on)

        project = self._config.project if self._config else ""
        return TestRunResult(
            project=project,
            timestamp=start.isoformat(),
            results=all_results,
            gate_result=gate_result,
            traces_scored=len(traces),
            duration_ms=round(duration_ms, 2),
        )


def generate_report(run_result: TestRunResult, format: str = "markdown") -> str:
    """Generate a human-readable report from a test run result."""
    if format == "json":
        return _generate_json_report(run_result)
    return _generate_markdown_report(run_result)


def _generate_markdown_report(result: TestRunResult) -> str:
    """Generate a markdown report."""
    lines: list[str] = []
    gate = result.gate_result

    lines.append(f"# ArcEval Test Report")
    lines.append("")
    lines.append(f"**Project:** {result.project}")
    lines.append(f"**Timestamp:** {result.timestamp}")
    lines.append(f"**Traces scored:** {result.traces_scored}")
    lines.append(f"**Duration:** {result.duration_ms}ms")
    if gate:
        verdict_emoji = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}
        lines.append(f"**Verdict:** {verdict_emoji.get(gate.verdict.value, gate.verdict.value)}")
    lines.append("")

    # Tier summaries
    if gate and gate.tier_summaries:
        lines.append("## Tier Summary")
        lines.append("")
        lines.append("| Tier | Total | Passed | Failed | Pass Rate |")
        lines.append("|------|-------|--------|--------|-----------|")
        for tier_key in sorted(gate.tier_summaries.keys()):
            s = gate.tier_summaries[tier_key]
            rate = f"{s.pass_rate:.1%}"
            lines.append(f"| {tier_key.upper()} | {s.total} | {s.passed} | {s.failed} | {rate} |")
        lines.append("")

    # Failures
    if gate and gate.failures:
        lines.append("## Failures (blocking)")
        lines.append("")
        for f in gate.failures:
            lines.append(f"- {f}")
        lines.append("")

    # Warnings
    if gate and gate.warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in gate.warnings:
            lines.append(f"- {w}")
        lines.append("")

    # Detailed results
    lines.append("## Detailed Results")
    lines.append("")
    lines.append("| Scorer | Tier | Passed | Score | Threshold | Trace ID |")
    lines.append("|--------|------|--------|-------|-----------|----------|")
    for r in result.results:
        passed_str = "PASS" if r.passed else "FAIL"
        score_str = f"{r.score:.4f}" if r.score is not None else "N/A"
        threshold_str = str(r.threshold) if r.threshold is not None else "N/A"
        trace_short = r.trace_id[:8] if r.trace_id else "N/A"
        lines.append(
            f"| {r.scorer_name} | {r.tier.value.upper()} | {passed_str} | "
            f"{score_str} | {threshold_str} | {trace_short} |"
        )
    lines.append("")

    return "\n".join(lines)


def _generate_json_report(result: TestRunResult) -> str:
    """Generate a JSON report."""
    gate = result.gate_result
    data = {
        "project": result.project,
        "timestamp": result.timestamp,
        "traces_scored": result.traces_scored,
        "duration_ms": result.duration_ms,
        "pass_rate": result.pass_rate,
        "verdict": gate.verdict.value if gate else None,
        "results": [
            {
                "scorer_name": r.scorer_name,
                "tier": r.tier.value,
                "passed": r.passed,
                "score": r.score,
                "threshold": r.threshold,
                "trace_id": r.trace_id,
                "details": r.details,
            }
            for r in result.results
        ],
        "failures": gate.failures if gate else [],
        "warnings": gate.warnings if gate else [],
    }
    return json.dumps(data, indent=2)


def save_report(report: str, output_dir: str, format: str = "markdown") -> Path:
    """Save a report to disk."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    ext = {"markdown": "md", "json": "json", "html": "html"}.get(format, "txt")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    file_path = output_path / f"report_{timestamp}.{ext}"
    file_path.write_text(report)
    return file_path
