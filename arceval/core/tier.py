"""Tier definitions and filtering logic."""

from __future__ import annotations

from enum import Enum


class Tier(Enum):
    """Evaluation tiers controlling what runs when."""

    T1 = "t1"
    T2 = "t2"
    T3 = "t3"


class TierMode(Enum):
    """When a tier's scorers are activated."""

    ALWAYS = "always"
    ON_GOLDEN_SET = "on_golden_set"
    ON_JUDGE = "on_judge"


def parse_tier(value: str) -> Tier:
    """Parse a tier string like 't1' or 'T1' into a Tier enum."""
    normalized = value.strip().lower()
    try:
        return Tier(normalized)
    except ValueError:
        valid = ", ".join(t.value for t in Tier)
        raise ValueError(f"Invalid tier '{value}'. Valid tiers: {valid}")


def filter_tiers(requested: list[str] | None, available: list[Tier] | None = None) -> list[Tier]:
    """Filter tiers based on a requested list.

    If requested is None, returns all tiers.
    If available is provided, only returns tiers present in both lists.
    """
    if requested is None:
        return list(available) if available else list(Tier)

    parsed = [parse_tier(t) for t in requested]

    if available is not None:
        return [t for t in parsed if t in available]

    return parsed
