"""Metric drift detection using statistical methods."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from arceval.core.protocols import ScoreResult


@dataclass
class DriftResult:
    """Result of drift detection for a single scorer."""

    scorer_name: str
    drifted: bool
    baseline_mean: float
    current_mean: float
    baseline_stddev: float
    current_stddev: float
    z_score: float | None = None
    details: dict[str, Any] = field(default_factory=dict)


def detect_drift(
    baseline_results: list[ScoreResult],
    current_results: list[ScoreResult],
    z_threshold: float = 2.0,
) -> list[DriftResult]:
    """Detect metric drift between baseline and current score distributions.

    Uses a z-test approach: compares the current mean against the baseline
    distribution. If the z-score exceeds the threshold, drift is flagged.

    Args:
        baseline_results: historical score results (the reference distribution)
        current_results: recent score results to check for drift
        z_threshold: z-score threshold for flagging drift (default 2.0 = ~95%)

    Returns:
        List of DriftResult, one per scorer.
    """
    baseline_by_scorer = _group_scores(baseline_results)
    current_by_scorer = _group_scores(current_results)

    all_scorers = sorted(set(baseline_by_scorer.keys()) | set(current_by_scorer.keys()))
    results: list[DriftResult] = []

    for scorer_name in all_scorers:
        b_scores = baseline_by_scorer.get(scorer_name, [])
        c_scores = current_by_scorer.get(scorer_name, [])

        if not b_scores or not c_scores:
            results.append(DriftResult(
                scorer_name=scorer_name,
                drifted=False,
                baseline_mean=_mean(b_scores),
                current_mean=_mean(c_scores),
                baseline_stddev=_stddev(b_scores),
                current_stddev=_stddev(c_scores),
                details={"reason": "insufficient data"},
            ))
            continue

        b_mean = _mean(b_scores)
        b_std = _stddev(b_scores)
        c_mean = _mean(c_scores)
        c_std = _stddev(c_scores)

        # Compute z-score of current mean relative to baseline distribution
        if b_std > 0:
            # Standard error of the current mean
            se = b_std / math.sqrt(len(c_scores))
            z = (c_mean - b_mean) / se
        else:
            # No variance in baseline; any difference is significant
            z = 0.0 if abs(c_mean - b_mean) < 1e-9 else float("inf")

        drifted = abs(z) > z_threshold

        results.append(DriftResult(
            scorer_name=scorer_name,
            drifted=drifted,
            baseline_mean=round(b_mean, 4),
            current_mean=round(c_mean, 4),
            baseline_stddev=round(b_std, 4),
            current_stddev=round(c_std, 4),
            z_score=round(z, 4) if not math.isinf(z) else None,
            details={
                "baseline_n": len(b_scores),
                "current_n": len(c_scores),
                "z_threshold": z_threshold,
            },
        ))

    return results


def format_drift_report(results: list[DriftResult]) -> str:
    """Format drift results as markdown."""
    lines: list[str] = []
    lines.append("# Drift Detection Report")
    lines.append("")

    drifted = [r for r in results if r.drifted]
    if drifted:
        lines.append(f"## Drift Detected ({len(drifted)} scorer(s))")
        lines.append("")
        for d in drifted:
            z_str = f"{d.z_score:.2f}" if d.z_score is not None else "inf"
            lines.append(
                f"- **{d.scorer_name}**: "
                f"mean {d.baseline_mean:.4f} -> {d.current_mean:.4f} "
                f"(z={z_str})"
            )
        lines.append("")

    lines.append("## All Scorers")
    lines.append("")
    lines.append("| Scorer | Baseline Mean | Current Mean | Baseline Std | Z-Score | Drifted |")
    lines.append("|--------|--------------|-------------|-------------|---------|---------|")
    for d in results:
        z_str = f"{d.z_score:.2f}" if d.z_score is not None else "N/A"
        status = "YES" if d.drifted else "no"
        lines.append(
            f"| {d.scorer_name} | {d.baseline_mean:.4f} | {d.current_mean:.4f} | "
            f"{d.baseline_stddev:.4f} | {z_str} | {status} |"
        )
    lines.append("")

    return "\n".join(lines)


def _group_scores(results: list[ScoreResult]) -> dict[str, list[float]]:
    """Group score values by scorer name."""
    groups: dict[str, list[float]] = {}
    for r in results:
        if r.score is not None:
            groups.setdefault(r.scorer_name, []).append(r.score)
    return groups


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)
