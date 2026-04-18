"""Golden set management: load, validate, and version golden set files."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from arceval.core.exceptions import GoldenSetError
from arceval.core.protocols import GoldenRecord


def load_golden_set(path: str | Path, format: str = "jsonl") -> list[GoldenRecord]:
    """Load a golden set file into a list of GoldenRecords.

    Supported formats: jsonl, csv, json.
    """
    path = Path(path)
    if not path.exists():
        raise GoldenSetError(f"Golden set file not found: {path}")

    loaders = {
        "jsonl": _load_jsonl,
        "csv": _load_csv,
        "json": _load_json,
    }

    loader = loaders.get(format)
    if loader is None:
        raise GoldenSetError(
            f"Unsupported golden set format '{format}'. Supported: {sorted(loaders.keys())}"
        )

    records = loader(path)
    if not records:
        raise GoldenSetError(f"Golden set file is empty: {path}")

    return records


def validate_golden_set(records: list[GoldenRecord]) -> list[str]:
    """Validate a list of golden records and return errors (empty = valid)."""
    errors: list[str] = []
    if not records:
        errors.append("Golden set is empty")
        return errors

    for i, record in enumerate(records):
        if not record.input_data:
            errors.append(f"Record {i}: input_data is empty")

    return errors


def load_golden_sets_from_config(
    sets_config: list[dict[str, Any]],
    base_path: str | Path,
    format: str = "jsonl",
) -> dict[str, list[GoldenRecord]]:
    """Load multiple golden sets based on config entries.

    Returns a dict mapping golden set name to list of records.
    """
    base_path = Path(base_path)
    result: dict[str, list[GoldenRecord]] = {}

    for entry in sets_config:
        name = entry["name"]
        file_path = base_path / entry["file"]
        file_format = entry.get("format", format)
        result[name] = load_golden_set(file_path, format=file_format)

    return result


def _load_jsonl(path: Path) -> list[GoldenRecord]:
    """Load golden records from a JSONL file."""
    records: list[GoldenRecord] = []
    try:
        with open(path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise GoldenSetError(
                        f"Invalid JSON on line {line_num} of {path}: {exc}"
                    ) from exc
                records.append(_dict_to_record(data))
    except OSError as exc:
        raise GoldenSetError(f"Failed to read golden set: {exc}") from exc
    return records


def _load_json(path: Path) -> list[GoldenRecord]:
    """Load golden records from a JSON array file."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise GoldenSetError(f"Failed to read golden set {path}: {exc}") from exc

    if not isinstance(data, list):
        raise GoldenSetError(f"JSON golden set must be an array, got {type(data).__name__}")

    return [_dict_to_record(item) for item in data]


def _load_csv(path: Path) -> list[GoldenRecord]:
    """Load golden records from a CSV file.

    Expects columns: input (JSON string), expected_output (JSON string),
    plus any additional columns as metadata.
    """
    records: list[GoldenRecord] = []
    try:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                input_str = row.pop("input", "{}")
                expected_str = row.pop("expected_output", "null")
                try:
                    input_data = json.loads(input_str)
                except json.JSONDecodeError:
                    input_data = {"raw": input_str}
                try:
                    expected_output = json.loads(expected_str)
                except json.JSONDecodeError:
                    expected_output = expected_str
                records.append(GoldenRecord(
                    input_data=input_data if isinstance(input_data, dict) else {"raw": input_data},
                    expected_output=expected_output,
                    metadata=dict(row),
                ))
    except OSError as exc:
        raise GoldenSetError(f"Failed to read golden set: {exc}") from exc
    return records


def _dict_to_record(data: dict[str, Any]) -> GoldenRecord:
    """Convert a dict to a GoldenRecord."""
    return GoldenRecord(
        input_data=data.get("input", data.get("input_data", {})),
        expected_output=data.get("expected_output", data.get("output")),
        metadata=data.get("metadata", {}),
    )
