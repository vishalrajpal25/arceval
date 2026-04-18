"""Production trace sampling: rate-based and stratified."""

from __future__ import annotations

import hashlib
import random
from typing import Any, Sequence

from arceval.core.trace_model import Trace


class Sampler:
    """Samples traces for scoring based on configured rate.

    Supports two modes:
    - Random: sample each trace independently with probability = rate
    - Deterministic: hash-based sampling for reproducibility (same trace always
      gets same decision)

    Config:
        rate: sampling rate between 0.0 and 1.0
        deterministic: if True, use hash-based sampling for reproducibility
        stratify_by: optional attribute key to stratify sampling
    """

    def __init__(
        self,
        rate: float = 1.0,
        deterministic: bool = False,
        stratify_by: str | None = None,
        seed: int | None = None,
    ) -> None:
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"Sampling rate must be between 0.0 and 1.0, got {rate}")
        self._rate = rate
        self._deterministic = deterministic
        self._stratify_by = stratify_by
        self._rng = random.Random(seed)

    @property
    def rate(self) -> float:
        return self._rate

    def should_sample(self, trace: Trace) -> bool:
        """Decide whether to sample a single trace."""
        if self._rate >= 1.0:
            return True
        if self._rate <= 0.0:
            return False

        if self._deterministic:
            return self._hash_sample(trace)
        return self._rng.random() < self._rate

    def sample(self, traces: Sequence[Trace]) -> list[Trace]:
        """Filter a batch of traces, returning only sampled ones."""
        return [t for t in traces if self.should_sample(t)]

    def sample_stratified(self, traces: Sequence[Trace]) -> list[Trace]:
        """Sample traces stratified by an attribute.

        Ensures proportional representation across strata.
        Falls back to simple sampling if stratify_by is not set.
        """
        if not self._stratify_by:
            return self.sample(traces)

        strata: dict[Any, list[Trace]] = {}
        for trace in traces:
            key = trace.attributes.get(self._stratify_by, "__default__")
            strata.setdefault(key, []).append(trace)

        result: list[Trace] = []
        for stratum_traces in strata.values():
            result.extend(self.sample(stratum_traces))

        return result

    def _hash_sample(self, trace: Trace) -> bool:
        """Deterministic sampling based on trace_id hash."""
        h = hashlib.md5(trace.trace_id.encode()).hexdigest()
        # Use first 8 hex chars as a fraction of the hash space
        hash_value = int(h[:8], 16) / 0xFFFFFFFF
        return hash_value < self._rate
