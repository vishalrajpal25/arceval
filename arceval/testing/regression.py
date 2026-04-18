"""Regression detection: compare two test runs and flag regressions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from arceval.core.protocols import ScoreResult
from arceval.testing.runner import TestRunResult


@dataclass
class ScorerDiff:
    """Difference in a single scorer between two runs."""

    scorer_name: str
    tier: str
    baseline_score: float | None
    current_score: float | None
    baseline_passed: bool
    current_passed: bool
    delta: float | None = None
    regressed: bool = False

    @property
    def improved(self) -> bool:
        return (
            self.delta is not None
            and self.delta > 0
            and not self.regressed
        )


@dataclass
class RegressionResult:
    """Result of comparing two test runs."""

    baseline_timestamp: str
    current_timestamp: str
    diffs: list[ScorerDiff] = field(default_factory=list)

    @property
    def has_regressions(self) -> bool:
        return any(d.regressed for d in self.diffs)

    @property
    def regressions(self) -> list[ScorerDiff]:
        return [d for d in self.diffs if d.regressed]

    @property
    def improvements(self) -> list[ScorerDiff]:
        return [d for d in self.diffs if d.improved]


def detect_regressions(
    baseline: TestRunResult,
    current: TestRunResult,
    threshold: float = 0.0,
) -> RegressionResult:
    """Compare two test runs and detect regressions.

    A regression is detected when:
    - A scorer that previously passed now fails
    - A scorer's score dropped by more than `threshold`

    Args:
        baseline: the previous (reference) test run
        current: the new test run to compare
        threshold: minimum score drop to flag as regression (0.0 = any drop)

    Returns:
        RegressionResult with per-scorer diffs.
    """
    # Aggregate scores per scorer: average score across traces
    baseline_scores = _aggregate_by_scorer(baseline.results)
    current_scores = _aggregate_by_scorer(current.results)

    all_scorers = sorted(set(baseline_scores.keys()) | set(current_scores.keys()))
    diffs: list[ScorerDiff] = []

    for scorer_name in all_scorers:
        b = baseline_scores.get(scorer_name)
        c = current_scores.get(scorer_name)

        b_score = b["avg_score"] if b else None
        c_score = c["avg_score"] if c else None
        b_passed = b["all_passed"] if b else True
        c_passed = c["all_passed"] if c else True
        tier = (c or b or {}).get("tier", "t1")

        delta = None
        if b_score is not None and c_score is not None:
            delta = round(c_score - b_score, 4)

        regressed = False
        # Regression: was passing, now failing
        if b_passed and not c_passed:
            regressed = True
        # Regression: score dropped beyond threshold
        elif delta is not None and delta < -threshold:
            regressed = True

        diffs.append(ScorerDiff(
            scorer_name=scorer_name,
            tier=tier,
            baseline_score=b_score,
            current_score=c_score,
            baseline_passed=b_passed,
            current_passed=c_passed,
            delta=delta,
            regressed=regressed,
        ))

    return RegressionResult(
        baseline_timestamp=baseline.timestamp,
        current_timestamp=current.timestamp,
        diffs=diffs,
    )


def format_regression_report(result: RegressionResult) -> str:
    """Format a regression comparison as markdown."""
    lines: list[str] = []
    lines.append("# Regression Report")
    lines.append("")
    lines.append(f"**Baseline:** {result.baseline_timestamp}")
    lines.append(f"**Current:** {result.current_timestamp}")
    lines.append("")

    if result.has_regressions:
        lines.append(f"## Regressions ({len(result.regressions)})")
        lines.append("")
        for d in result.regressions:
            delta_str = f"{d.delta:+.4f}" if d.delta is not None else "N/A"
            lines.append(
                f"- **{d.scorer_name}** [{d.tier.upper()}]: "
                f"{d.baseline_score} -> {d.current_score} ({delta_str})"
            )
        lines.append("")

    if result.improvements:
        lines.append(f"## Improvements ({len(result.improvements)})")
        lines.append("")
        for d in result.improvements:
            delta_str = f"{d.delta:+.4f}" if d.delta is not None else "N/A"
            lines.append(
                f"- **{d.scorer_name}** [{d.tier.upper()}]: "
                f"{d.baseline_score} -> {d.current_score} ({delta_str})"
            )
        lines.append("")

    if not result.has_regressions and not result.improvements:
        lines.append("No regressions or improvements detected.")
        lines.append("")

    lines.append("## All Scorers")
    lines.append("")
    lines.append("| Scorer | Tier | Baseline | Current | Delta | Status |")
    lines.append("|--------|------|----------|---------|-------|--------|")
    for d in result.diffs:
        b_str = f"{d.baseline_score:.4f}" if d.baseline_score is not None else "N/A"
        c_str = f"{d.current_score:.4f}" if d.current_score is not None else "N/A"
        delta_str = f"{d.delta:+.4f}" if d.delta is not None else "N/A"
        status = "REGRESSED" if d.regressed else ("IMPROVED" if d.improved else "OK")
        lines.append(f"| {d.scorer_name} | {d.tier.upper()} | {b_str} | {c_str} | {delta_str} | {status} |")
    lines.append("")

    return "\n".join(lines)


def _aggregate_by_scorer(results: list[ScoreResult]) -> dict[str, dict[str, Any]]:
    """Aggregate score results by scorer name."""
    agg: dict[str, dict[str, Any]] = {}

    for r in results:
        if r.scorer_name not in agg:
            agg[r.scorer_name] = {
                "scores": [],
                "passed": [],
                "tier": r.tier.value,
            }
        if r.score is not None:
            agg[r.scorer_name]["scores"].append(r.score)
        agg[r.scorer_name]["passed"].append(r.passed)

    for name, data in agg.items():
        scores = data["scores"]
        data["avg_score"] = round(sum(scores) / len(scores), 4) if scores else None
        data["all_passed"] = all(data["passed"])

    return agg
