"""Tests for arceval.core.tier."""

import pytest

from arceval.core.tier import Tier, TierMode, filter_tiers, parse_tier


class TestParseTier:
    def test_lowercase(self):
        assert parse_tier("t1") == Tier.T1
        assert parse_tier("t2") == Tier.T2
        assert parse_tier("t3") == Tier.T3

    def test_uppercase(self):
        assert parse_tier("T1") == Tier.T1
        assert parse_tier("T2") == Tier.T2

    def test_whitespace(self):
        assert parse_tier("  t1  ") == Tier.T1

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid tier"):
            parse_tier("t4")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_tier("")


class TestFilterTiers:
    def test_none_returns_all(self):
        result = filter_tiers(None)
        assert result == [Tier.T1, Tier.T2, Tier.T3]

    def test_none_with_available(self):
        result = filter_tiers(None, available=[Tier.T1, Tier.T2])
        assert result == [Tier.T1, Tier.T2]

    def test_specific_tiers(self):
        result = filter_tiers(["t1", "t3"])
        assert result == [Tier.T1, Tier.T3]

    def test_filtered_by_available(self):
        result = filter_tiers(["t1", "t3"], available=[Tier.T1])
        assert result == [Tier.T1]

    def test_empty_list_returns_empty(self):
        result = filter_tiers([])
        assert result == []


class TestTierMode:
    def test_values(self):
        assert TierMode.ALWAYS.value == "always"
        assert TierMode.ON_GOLDEN_SET.value == "on_golden_set"
        assert TierMode.ON_JUDGE.value == "on_judge"
