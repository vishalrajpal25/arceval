"""Delta Lake backend for direct Delta table storage."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any, Sequence

from arceval.core.exceptions import BackendError
from arceval.core.protocols import ScoreResult
from arceval.core.trace_model import Trace

logger = logging.getLogger(__name__)

try:
    import deltalake

    HAS_DELTALAKE = True
except ImportError:
    HAS_DELTALAKE = False

try:
    from pyspark.sql import SparkSession

    HAS_SPARK = True
except ImportError:
    HAS_SPARK = False


class DeltaBackend:
    """Direct Delta Lake table storage for traces and scores.

    Supports two connection modes:
    - delta-rs: uses the deltalake Python library (no Spark needed)
    - databricks: uses PySpark with Databricks Unity Catalog

    Config:
        catalog: Unity Catalog name
        schema: database/schema name
        traces_table: table name for traces
        scores_table: table name for scores
        connection: "delta-rs" or "databricks"
        storage_path: local path for delta-rs mode (default: /tmp/arceval_delta)
    """

    def __init__(
        self,
        catalog: str = "eval_catalog",
        schema: str = "bronze",
        traces_table: str = "mcp_traces",
        scores_table: str = "eval_scores",
        connection: str = "delta-rs",
        storage_path: str = "/tmp/arceval_delta",
        **kwargs: Any,
    ) -> None:
        self._catalog = catalog
        self._schema = schema
        self._traces_table = traces_table
        self._scores_table = scores_table
        self._connection = connection
        self._storage_path = storage_path

        if connection == "delta-rs":
            if not HAS_DELTALAKE:
                raise BackendError(
                    "deltalake is not installed. Install with: pip install arceval[delta]"
                )
            self._traces_path = f"{storage_path}/{traces_table}"
            self._scores_path = f"{storage_path}/{scores_table}"
        elif connection == "databricks":
            if not HAS_SPARK:
                raise BackendError(
                    "PySpark is not installed. Required for Databricks connection."
                )
            self._full_traces_table = f"{catalog}.{schema}.{traces_table}"
            self._full_scores_table = f"{catalog}.{schema}.{scores_table}"
            self._spark = SparkSession.builder.getOrCreate()
        else:
            raise BackendError(
                f"Unknown connection type '{connection}'. Use 'delta-rs' or 'databricks'."
            )

    def emit(self, traces: Sequence[Trace]) -> None:
        """Write traces to the Delta table."""
        import pyarrow as pa

        records = []
        for trace in traces:
            record = {
                "trace_id": trace.trace_id,
                "span_id": trace.span_id,
                "timestamp_start": trace.timestamp_start,
                "timestamp_end": trace.timestamp_end or "",
                "gen_ai_system": trace.gen_ai_system or "",
                "gen_ai_operation": trace.gen_ai_operation or "",
                "gen_ai_request_model": trace.gen_ai_request_model or "",
                "latency_ms": trace.latency_ms or 0.0,
                "status_code": trace.status_code or 0,
                "error_type": trace.error_type or "",
                "attributes_json": json.dumps(trace.attributes, default=str),
                "input_json": json.dumps(trace.input_data, default=str),
                "output_json": json.dumps(trace.output_data, default=str),
            }
            records.append(record)

        if self._connection == "delta-rs":
            table = pa.Table.from_pylist(records)
            try:
                deltalake.write_deltalake(
                    self._traces_path, table, mode="append"
                )
            except Exception as exc:
                logger.error("Failed to write traces to Delta: %s", exc)
        elif self._connection == "databricks":
            df = self._spark.createDataFrame(records)
            df.write.format("delta").mode("append").saveAsTable(
                self._full_traces_table
            )

    def query(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> Sequence[Trace]:
        """Read traces from the Delta table."""
        if self._connection == "delta-rs":
            try:
                dt = deltalake.DeltaTable(self._traces_path)
                df = dt.to_pyarrow_table()
                records = df.to_pylist()
            except Exception:
                return []
        elif self._connection == "databricks":
            try:
                df = self._spark.read.table(self._full_traces_table)
                records = [row.asDict() for row in df.limit(limit).collect()]
            except Exception:
                return []
        else:
            return []

        traces: list[Trace] = []
        for record in records[:limit]:
            trace = Trace(
                trace_id=record.get("trace_id", ""),
                span_id=record.get("span_id", ""),
                timestamp_start=record.get("timestamp_start", ""),
                timestamp_end=record.get("timestamp_end") or None,
                gen_ai_system=record.get("gen_ai_system") or None,
                gen_ai_operation=record.get("gen_ai_operation") or None,
                gen_ai_request_model=record.get("gen_ai_request_model") or None,
                latency_ms=record.get("latency_ms"),
                status_code=record.get("status_code"),
                error_type=record.get("error_type") or None,
                attributes=json.loads(record.get("attributes_json", "{}")),
                input_data=json.loads(record.get("input_json", "null")),
                output_data=json.loads(record.get("output_json", "null")),
            )
            if start_time and trace.timestamp_start < start_time:
                continue
            if end_time and trace.timestamp_start > end_time:
                continue
            traces.append(trace)

        return traces[:limit]

    def store_scores(self, scores: Sequence[ScoreResult]) -> None:
        """Write score results to the scores Delta table."""
        import pyarrow as pa

        records = []
        for score in scores:
            records.append({
                "scorer_name": score.scorer_name,
                "tier": score.tier.value,
                "passed": score.passed,
                "score": score.score or 0.0,
                "threshold": score.threshold or 0.0,
                "trace_id": score.trace_id,
                "timestamp": score.timestamp,
                "details_json": json.dumps(score.details, default=str),
            })

        if self._connection == "delta-rs":
            table = pa.Table.from_pylist(records)
            try:
                deltalake.write_deltalake(
                    self._scores_path, table, mode="append"
                )
            except Exception as exc:
                logger.error("Failed to write scores to Delta: %s", exc)
        elif self._connection == "databricks":
            df = self._spark.createDataFrame(records)
            df.write.format("delta").mode("append").saveAsTable(
                self._full_scores_table
            )

    def health_check(self) -> bool:
        """Verify Delta backend is operational."""
        if self._connection == "delta-rs":
            return HAS_DELTALAKE
        elif self._connection == "databricks":
            try:
                self._spark.sql("SELECT 1")
                return True
            except Exception:
                return False
        return False
