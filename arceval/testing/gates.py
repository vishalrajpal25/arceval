"""CI/CD gate logic: determines pass/fail/warn based on tier thresholds."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from arceval.core.protocols import ScoreResult
from arceval.core.tier import Tier


class GateVerdict(Enum):
    """Outcome of a gate check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class TierSummary:
    """Aggregated results for a single tier."""

    tier: Tier
    total: int = 0
    passed: int = 0
    failed: int = 0
    results: list[ScoreResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return self.failed == 0 and self.total > 0

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0


@dataclass
class GateResult:
    """Overall gate evaluation result."""

    verdict: GateVerdict
    tier_summaries: dict[str, TierSummary] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        """Return 0 for pass/warn, 1 for fail."""
        return 1 if self.verdict == GateVerdict.FAIL else 0


def evaluate_gates(
    results: list[ScoreResult],
    fail_on: str = "t1",
    warn_on: str = "t2",
) -> GateResult:
    """Evaluate gate logic on a set of score results.

    Args:
        results: all ScoreResults from a test run
        fail_on: tier that causes CI failure (e.g. "t1")
        warn_on: tier that causes CI warning (e.g. "t2")

    Returns:
        GateResult with verdict, summaries, failures, and warnings.
    """
    fail_tier = Tier(fail_on)
    warn_tier = Tier(warn_on)

    summaries: dict[str, TierSummary] = {}
    for result in results:
        tier_key = result.tier.value
        if tier_key not in summaries:
            summaries[tier_key] = TierSummary(tier=result.tier)
        summary = summaries[tier_key]
        summary.total += 1
        summary.results.append(result)
        if result.passed:
            summary.passed += 1
        else:
            summary.failed += 1

    failures: list[str] = []
    warnings: list[str] = []

    # Check fail tier
    fail_summary = summaries.get(fail_tier.value)
    if fail_summary and not fail_summary.all_passed:
        for r in fail_summary.results:
            if not r.passed:
                failures.append(
                    f"[{fail_tier.value.upper()}] {r.scorer_name}: "
                    f"score={r.score}, threshold={r.threshold}"
                )

    # Check warn tier
    warn_summary = summaries.get(warn_tier.value)
    if warn_summary and not warn_summary.all_passed:
        for r in warn_summary.results:
            if not r.passed:
                warnings.append(
                    f"[{warn_tier.value.upper()}] {r.scorer_name}: "
                    f"score={r.score}, threshold={r.threshold}"
                )

    # Determine verdict
    if failures:
        verdict = GateVerdict.FAIL
    elif warnings:
        verdict = GateVerdict.WARN
    else:
        verdict = GateVerdict.PASS

    return GateResult(
        verdict=verdict,
        tier_summaries=summaries,
        failures=failures,
        warnings=warnings,
    )
