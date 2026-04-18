"""Tests for arceval.monitoring.sampler."""

import pytest

from arceval.core.trace_model import create_trace
from arceval.monitoring.sampler import Sampler


class TestSampler:
    def test_rate_1_samples_all(self):
        sampler = Sampler(rate=1.0)
        traces = [create_trace() for _ in range(10)]
        assert len(sampler.sample(traces)) == 10

    def test_rate_0_samples_none(self):
        sampler = Sampler(rate=0.0)
        traces = [create_trace() for _ in range(10)]
        assert len(sampler.sample(traces)) == 0

    def test_rate_half_approximate(self):
        sampler = Sampler(rate=0.5, seed=42)
        traces = [create_trace() for _ in range(1000)]
        sampled = sampler.sample(traces)
        # Should be roughly 50%, allow wide margin
        assert 300 < len(sampled) < 700

    def test_invalid_rate(self):
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            Sampler(rate=1.5)

    def test_negative_rate(self):
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            Sampler(rate=-0.1)

    def test_should_sample_single(self):
        sampler = Sampler(rate=1.0)
        assert sampler.should_sample(create_trace()) is True

        sampler = Sampler(rate=0.0)
        assert sampler.should_sample(create_trace()) is False

    def test_deterministic_consistent(self):
        sampler = Sampler(rate=0.5, deterministic=True)
        trace = create_trace()
        # Same trace should always get same decision
        decisions = [sampler.should_sample(trace) for _ in range(10)]
        assert len(set(decisions)) == 1

    def test_deterministic_different_traces(self):
        sampler = Sampler(rate=0.5, deterministic=True)
        traces = [create_trace() for _ in range(100)]
        sampled = sampler.sample(traces)
        # Should get some but not all
        assert 0 < len(sampled) < 100

    def test_rate_property(self):
        sampler = Sampler(rate=0.3)
        assert sampler.rate == 0.3


class TestStratifiedSampling:
    def test_stratified_by_attribute(self):
        sampler = Sampler(rate=0.5, stratify_by="tool_name", seed=42)
        traces = (
            [create_trace(attributes={"tool_name": "search"}) for _ in range(50)]
            + [create_trace(attributes={"tool_name": "calc"}) for _ in range(50)]
        )
        sampled = sampler.sample_stratified(traces)
        # Should sample from both strata
        tools = [t.attributes["tool_name"] for t in sampled]
        assert "search" in tools
        assert "calc" in tools

    def test_stratified_no_attribute_falls_back(self):
        sampler = Sampler(rate=1.0, stratify_by="nonexistent")
        traces = [create_trace() for _ in range(5)]
        sampled = sampler.sample_stratified(traces)
        assert len(sampled) == 5

    def test_no_stratify_by_uses_simple(self):
        sampler = Sampler(rate=1.0)
        traces = [create_trace() for _ in range(5)]
        sampled = sampler.sample_stratified(traces)
        assert len(sampled) == 5
