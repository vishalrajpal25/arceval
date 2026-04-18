"""Local file backend for development and testing."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from arceval.core.exceptions import BackendError
from arceval.core.protocols import ScoreResult
from arceval.core.trace_model import Trace


class FileBackend:
    """Store traces and scores as JSONL files on disk.

    Config:
        path: directory to write files into
        format: jsonl (default) or json
    """

    def __init__(self, path: str = "./traces/", format: str = "jsonl") -> None:
        self._path = Path(path)
        self._format = format
        self._path.mkdir(parents=True, exist_ok=True)

    @property
    def traces_file(self) -> Path:
        return self._path / f"traces.{self._format}"

    @property
    def scores_file(self) -> Path:
        return self._path / f"scores.{self._format}"

    def emit(self, traces: Sequence[Trace]) -> None:
        """Append traces to the traces file."""
        try:
            with open(self.traces_file, "a") as f:
                for trace in traces:
                    f.write(json.dumps(asdict(trace), default=str) + "\n")
        except OSError as exc:
            raise BackendError(f"Failed to write traces: {exc}") from exc

    def query(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> Sequence[Trace]:
        """Read traces from the traces file, applying optional time and attribute filters."""
        if not self.traces_file.exists():
            return []

        traces: list[Trace] = []
        with open(self.traces_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                trace = Trace(**data)

                if start_time and trace.timestamp_start < start_time:
                    continue
                if end_time and trace.timestamp_start > end_time:
                    continue
                if filters:
                    match = all(
                        trace.attributes.get(k) == v for k, v in filters.items()
                    )
                    if not match:
                        continue

                traces.append(trace)
                if len(traces) >= limit:
                    break

        return traces

    def store_scores(self, scores: Sequence[ScoreResult]) -> None:
        """Append score results to the scores file."""
        try:
            with open(self.scores_file, "a") as f:
                for score in scores:
                    data = asdict(score)
                    data["tier"] = score.tier.value
                    f.write(json.dumps(data, default=str) + "\n")
        except OSError as exc:
            raise BackendError(f"Failed to write scores: {exc}") from exc

    def health_check(self) -> bool:
        """Check that the output directory is writable."""
        try:
            self._path.mkdir(parents=True, exist_ok=True)
            return True
        except OSError:
            return False
