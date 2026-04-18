# ArcEval — Project Specification

> The orchestration layer for AI evaluation. Stitch eval-as-testing and eval-as-observability into one config-driven framework that works with your existing stack.

## 1. What This Is

ArcEval is an open-source Python framework that orchestrates end-to-end evaluation for AI endpoints (MCP servers, RAG pipelines, agents, chatbots, any LLM-powered service). It does NOT replace MLflow, Langfuse, DeepEval, or RAGAS. It sits above them as a unified orchestration layer that:

- Instruments your endpoint with lightweight middleware (capture)
- Routes traces to whatever backend you already use (MLflow, Langfuse, OTEL collector, file)
- Runs scorers from any ecosystem (built-in, DeepEval, RAGAS, MLflow) on those traces
- Organizes everything into prioritized tiers so teams know what to instrument first
- Works identically in CI/CD (eval-as-testing) and production (eval-as-observability)

The tagline: **"One config. Any backend. Every phase."**

## 2. Why This Exists — The Gap

The eval landscape in 2026 is fragmented:

- **DeepEval/RAGAS**: Great scorers, no orchestration or backend flexibility
- **MLflow 3**: Excellent on Databricks, locked to the Databricks ecosystem for production monitoring
- **Langfuse**: Excellent tracing UI, weak on eval orchestration and CI/CD gating
- **Braintrust**: Strong CI/CD, commercial, no self-host (meaningful), no backend choice

No tool today lets an enterprise team say: "I want T1 metrics on day one with DLT Expectations, T2 golden-set evals via DeepEval scorers stored in Langfuse, and T3 LLM-judge evals through MLflow 3 production monitoring, all declared in one YAML file, with the same scorers running in my CI pipeline and my production deployment."

ArcEval does that.

## 3. Design Principles

1. **Config-driven, not code-driven.** The primary interface is a YAML manifest (`arceval.yaml`). Code is for extending, not for basic usage.
2. **Protocols over inheritance.** Every extension point (Backend, Scorer, Capture, AlertSink) is a Python Protocol. No base classes to inherit from.
3. **Delegate, don't duplicate.** ArcEval never reimplements trace storage, dashboards, or scorer algorithms that exist elsewhere. It adapts and orchestrates.
4. **Tiers are first-class.** Every metric belongs to a tier. Tiers control what runs when, what blocks deploys, and what samples in production.
5. **Same scorer, two modes.** A scorer written once runs in both testing mode (on golden sets, blocking CI) and monitoring mode (on production traces, sampling).
6. **OTEL-native.** The internal trace model follows OpenTelemetry `gen_ai.*` semantic conventions. Custom attributes extend, never replace.
7. **Zero opinions on infra.** Works with Databricks, plain AWS, Azure, GCP, or a laptop with SQLite.

## 4. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     arceval.yaml                        │
│  (endpoints, backends, scorers, tiers, alerts)          │
└──────────────┬──────────────────────────────────────────┘
               │
    ┌──────────▼──────────┐
    │     ArcEval Core    │
    │  (config, registry, │
    │   tier engine,      │
    │   lifecycle mgr)    │
    └──┬───┬───┬───┬──────┘
       │   │   │   │
  ┌────▼┐ ┌▼───▼┐ ┌▼────────┐
  │Capture│ │Score│ │Backends │
  │      │ │     │ │         │
  │ MCP  │ │built│ │ MLflow  │
  │ RAG  │ │ in  │ │Langfuse │
  │Agent │ │deep │ │  OTEL   │
  │HTTP  │ │eval │ │  File   │
  │      │ │ragas│ │  Delta  │
  └──────┘ └─────┘ └─────────┘
```

### 4.1 Core Modules

```
arceval/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── protocols.py          # All Protocol definitions
│   ├── config.py             # YAML config parsing and validation (Pydantic models)
│   ├── registry.py           # Global registry for backends, scorers, capture adapters
│   ├── tier.py               # Tier definitions, metric-to-tier mapping
│   ├── lifecycle.py          # Orchestrator: testing mode vs monitoring mode
│   ├── trace_model.py        # Internal trace model (OTEL gen_ai.* aligned)
│   └── exceptions.py         # Custom exceptions
├── capture/
│   ├── __init__.py
│   ├── base.py               # CaptureMiddleware protocol
│   ├── mcp.py                # MCP server middleware (intercepts tool calls)
│   ├── fastapi.py            # FastAPI middleware (generic HTTP/REST)
│   ├── langchain.py          # LangChain callback handler
│   ├── openai_wrapper.py     # OpenAI client wrapper
│   └── manual.py             # Manual trace creation API (for custom endpoints)
├── backends/
│   ├── __init__.py
│   ├── base.py               # TraceBackend protocol
│   ├── mlflow.py             # MLflow 3 (mlflow.genai namespace)
│   ├── langfuse.py           # Langfuse v3 SDK
│   ├── otel.py               # OpenTelemetry OTLP exporter
│   ├── file.py               # Local JSON/JSONL file (dev/testing)
│   └── delta.py              # Databricks Delta tables via spark or delta-rs
├── scorers/
│   ├── __init__.py
│   ├── base.py               # Scorer protocol
│   ├── builtin/
│   │   ├── __init__.py
│   │   ├── latency.py        # P50/P95/P99 latency thresholds
│   │   ├── error_rate.py     # Error rate by type
│   │   ├── availability.py   # Uptime / success rate
│   │   ├── schema.py         # Response schema compliance
│   │   ├── token_usage.py    # Token count anomaly detection
│   │   ├── completeness.py   # Field completeness (required fields present)
│   │   └── freshness.py      # Data freshness SLA check
│   └── adapters/
│       ├── __init__.py
│       ├── deepeval.py       # Adapter for DeepEval metrics (GEval, ToolCorrectness, etc.)
│       ├── ragas.py          # Adapter for RAGAS metrics (faithfulness, relevancy)
│       ├── mlflow_scorers.py # Adapter for MLflow 3 built-in scorers (Correctness, Safety)
│       └── custom.py         # User-defined scorer from a Python callable
├── testing/
│   ├── __init__.py
│   ├── runner.py             # Test runner: load golden sets, run scorers, produce report
│   ├── golden_sets.py        # Golden set management (load, version, diff)
│   ├── gates.py              # CI/CD gate logic (pass/fail thresholds per tier)
│   ├── regression.py         # Regression detection (compare runs)
│   └── pytest_plugin.py      # pytest plugin: `pytest --arceval`
├── monitoring/
│   ├── __init__.py
│   ├── sampler.py            # Production trace sampling (rate-based, stratified)
│   ├── continuous.py         # Continuous scorer execution on sampled traces
│   ├── drift.py              # Metric drift detection (statistical)
│   └── alerts.py             # Alert routing (Slack, PagerDuty, webhook, log)
├── cli/
│   ├── __init__.py
│   ├── main.py               # CLI entry point (click or typer)
│   ├── init_cmd.py           # `arceval init` — scaffold arceval.yaml
│   ├── test_cmd.py           # `arceval test` — run eval-as-testing
│   ├── monitor_cmd.py        # `arceval monitor` — start eval-as-observability
│   ├── report_cmd.py         # `arceval report` — generate eval report
│   └── validate_cmd.py       # `arceval validate` — validate config
└── config/
    ├── __init__.py
    ├── schema.py             # Pydantic models for arceval.yaml
    └── templates/            # Template YAML configs per endpoint type
        ├── mcp.yaml
        ├── rag.yaml
        ├── agent.yaml
        └── chatbot.yaml
```

### 4.2 Config Structure (`arceval.yaml`)

This is the primary user interface. Everything is declared here.

```yaml
# arceval.yaml — complete example for an MCP service
version: "1"
project: "findata-mcp-eval"

# ─── Endpoint Under Evaluation ───────────────────────────────────────────
endpoint:
  type: mcp                          # mcp | rag | agent | chatbot | http
  name: "Financial Data MCP Service"
  # Type-specific config
  mcp:
    server_command: "python -m findata_mcp.server"
    # OR connect to running server:
    # url: "http://localhost:8080/mcp"
    tools:                            # optional: scope to specific tools
      - get_fundamentals
      - get_pricing
      - get_estimates

# ─── Backends (where traces go) ──────────────────────────────────────────
backends:
  # Multiple backends can be active simultaneously
  primary:
    type: mlflow
    tracking_uri: "databricks"
    experiment_name: "/findata-mcp/eval"
  
  secondary:
    type: langfuse
    public_key: "${LANGFUSE_PUBLIC_KEY}"
    secret_key: "${LANGFUSE_SECRET_KEY}"
    host: "https://langfuse.internal.company.com"
  
  dev:
    type: file
    path: "./traces/"
    format: jsonl

# ─── Tiers ───────────────────────────────────────────────────────────────
# Tiers control what runs when. T1 always runs. T2 runs when golden sets
# exist. T3 runs when LLM judge endpoints are configured.
tiers:
  t1:
    name: "Must-Have"
    description: "Instrument on day one. Rule-based. No dependencies."
    mode: always                      # always | on_golden_set | on_judge
    in_testing: true                  # run in CI/CD
    in_monitoring: true               # run in production
    sample_rate: 1.0                  # score every trace
    block_deploy: true                # fail CI if thresholds breached

  t2:
    name: "Operational"
    description: "Requires golden sets or reference data."
    mode: on_golden_set
    in_testing: true
    in_monitoring: true
    sample_rate: 1.0
    block_deploy: false               # warn, don't fail

  t3:
    name: "Advanced"
    description: "LLM-as-judge. Async, sampled."
    mode: on_judge
    in_testing: true
    in_monitoring: true
    sample_rate: 0.1                  # score 10% of production traces
    block_deploy: false

# ─── Scorers ─────────────────────────────────────────────────────────────
scorers:
  # T1 — built-in, rule-based
  - name: latency_p95
    type: builtin.latency
    tier: t1
    config:
      percentile: 95
      threshold_ms: 2000
      segment_by: [tool_name, dataset]

  - name: error_rate
    type: builtin.error_rate
    tier: t1
    config:
      threshold_pct: 0.5
      segment_by: [tool_name, error_type]

  - name: schema_compliance
    type: builtin.schema
    tier: t1
    config:
      schema_path: "./schemas/"       # JSON schemas per tool
      threshold_pct: 99.9

  - name: availability
    type: builtin.availability
    tier: t1
    config:
      threshold_pct: 99.9
      window_minutes: 60

  - name: field_completeness
    type: builtin.completeness
    tier: t1
    config:
      required_fields_path: "./field_manifests/"
      threshold_pct: 99.5

  # T2 — golden set comparison
  - name: answer_accuracy
    type: deepeval.correctness
    tier: t2
    config:
      golden_set_path: "./golden_sets/"
      model: "gpt-4o"                # judge model for DeepEval
      threshold: 0.95

  - name: data_freshness
    type: builtin.freshness
    tier: t2
    config:
      sla_config_path: "./sla.yaml"   # per-dataset SLA definitions
      alert_on_breach: true

  - name: token_anomaly
    type: builtin.token_usage
    tier: t2
    config:
      baseline_window_days: 7
      anomaly_multiplier: 3.0         # flag if > 3x median

  # T3 — LLM judge
  - name: hallucination
    type: deepeval.hallucination
    tier: t3
    config:
      model: "gpt-4o"
      threshold: 0.05                 # < 5% hallucination rate

  - name: faithfulness
    type: ragas.faithfulness
    tier: t3
    config:
      model: "gpt-4o"
      threshold: 0.90

  - name: response_correctness
    type: mlflow.correctness
    tier: t3
    config:
      model: "databricks/databricks-claude-sonnet-4"

  - name: task_completion
    type: deepeval.task_completion
    tier: t3
    config:
      model: "gpt-4o"
      threshold: 0.90

# ─── Golden Sets ─────────────────────────────────────────────────────────
golden_sets:
  path: "./golden_sets/"
  format: jsonl                       # jsonl | csv | parquet
  versioned: true                     # track versions for regression
  sets:
    - name: fundamentals
      file: "fundamentals_v2.jsonl"
      tools: [get_fundamentals]
    - name: pricing
      file: "pricing_v1.jsonl"
      tools: [get_pricing]

# ─── Alerting ────────────────────────────────────────────────────────────
alerts:
  - type: slack
    channel: "#eval-alerts"
    webhook_url: "${SLACK_WEBHOOK_URL}"
    on: [t1.fail, t2.threshold_breach]

  - type: pagerduty
    routing_key: "${PD_ROUTING_KEY}"
    on: [t1.fail]

  - type: webhook
    url: "https://internal.company.com/eval-webhook"
    on: [t3.regression]

# ─── Testing Mode Config ────────────────────────────────────────────────
testing:
  report_format: markdown             # markdown | html | json
  output_dir: "./eval-reports/"
  fail_on: t1                        # fail CI if any T1 threshold breached
  warn_on: t2                        # warn if T2 thresholds breached
  compare_to: latest                  # compare to latest passing run

# ─── Monitoring Mode Config ──────────────────────────────────────────────
monitoring:
  poll_interval_seconds: 30
  batch_size: 100
  max_concurrent_judges: 4            # limit async LLM judge calls
  storage:
    results_backend: primary          # store scorer results in primary backend
```

## 5. Protocol Definitions

These are the extension points. Everything is pluggable.

### 5.1 `protocols.py`

```python
"""Core protocols for ArcEval. All extension points are Protocols, not ABCs."""

from __future__ import annotations
from typing import Protocol, Any, Sequence, runtime_checkable
from dataclasses import dataclass
from enum import Enum


class Tier(Enum):
    T1 = "t1"
    T2 = "t2"
    T3 = "t3"


class ScorerMode(Enum):
    TESTING = "testing"         # Run on golden sets in CI/CD
    MONITORING = "monitoring"   # Run on production traces


@dataclass(frozen=True)
class Trace:
    """
    Internal trace model, aligned with OTEL gen_ai.* semantic conventions.
    This is the universal currency passed between capture, backends, and scorers.
    """
    trace_id: str
    span_id: str
    parent_span_id: str | None
    timestamp_start: str            # ISO 8601
    timestamp_end: str | None
    
    # gen_ai.* standard attributes
    gen_ai_system: str | None       # e.g., "openai", "anthropic", "mcp"
    gen_ai_operation: str | None    # e.g., "tool_call", "chat", "completion"
    gen_ai_request_model: str | None
    gen_ai_response_model: str | None
    gen_ai_usage_input_tokens: int | None
    gen_ai_usage_output_tokens: int | None
    
    # Common operational attributes
    status_code: int | None
    error_type: str | None
    latency_ms: float | None
    
    # Endpoint-specific attributes (flexible dict)
    attributes: dict[str, Any]      # tool_name, dataset, tenant_id, session_id, etc.
    
    # Request/response content (optional, may be redacted)
    input_data: Any | None
    output_data: Any | None


@dataclass(frozen=True)
class ScoreResult:
    """Result from a single scorer execution."""
    scorer_name: str
    tier: Tier
    passed: bool
    score: float | None             # 0.0 to 1.0 where applicable
    threshold: float | None
    details: dict[str, Any]         # scorer-specific details
    trace_id: str
    timestamp: str


@dataclass(frozen=True)
class GoldenRecord:
    """A single golden set record for eval-as-testing."""
    input_data: dict[str, Any]
    expected_output: Any
    metadata: dict[str, Any]        # tool_name, dataset, version, etc.


@runtime_checkable
class TraceBackend(Protocol):
    """
    Where traces are stored and retrieved.
    Implementations: MLflow, Langfuse, OTEL collector, file, Delta.
    """
    
    def emit(self, traces: Sequence[Trace]) -> None:
        """Send traces to the backend."""
        ...
    
    def query(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> Sequence[Trace]:
        """Retrieve traces from the backend for scoring."""
        ...
    
    def store_scores(self, scores: Sequence[ScoreResult]) -> None:
        """Attach scorer results back to the backend."""
        ...
    
    def health_check(self) -> bool:
        """Verify backend connectivity."""
        ...


@runtime_checkable
class Scorer(Protocol):
    """
    Evaluates traces and produces scores.
    Must work in BOTH testing mode (golden sets) and monitoring mode (production traces).
    """
    
    @property
    def name(self) -> str:
        """Unique scorer name."""
        ...
    
    @property
    def tier(self) -> Tier:
        """Which tier this scorer belongs to."""
        ...
    
    def score_trace(self, trace: Trace) -> ScoreResult:
        """
        Score a single trace. For rule-based scorers (T1), this is deterministic.
        For LLM-judge scorers (T3), this may call an external model.
        """
        ...
    
    def score_with_golden(self, trace: Trace, golden: GoldenRecord) -> ScoreResult:
        """
        Score a trace against a golden set record (eval-as-testing).
        Default implementation: delegates to score_trace, ignoring golden.
        Override for scorers that need reference data.
        """
        ...
    
    def validate_config(self) -> list[str]:
        """
        Return a list of config validation errors (empty = valid).
        Called at startup to fail fast on misconfiguration.
        """
        ...


@runtime_checkable
class CaptureMiddleware(Protocol):
    """
    Instruments an endpoint to produce Traces.
    Implementations: MCP middleware, FastAPI middleware, LangChain callback.
    """
    
    def wrap(self, endpoint: Any) -> Any:
        """
        Wrap the endpoint with instrumentation.
        Returns the wrapped endpoint (or modifies in place).
        """
        ...
    
    def set_backend(self, backend: TraceBackend) -> None:
        """Set the backend where captured traces are emitted."""
        ...


@runtime_checkable
class AlertSink(Protocol):
    """Where alerts are sent when thresholds are breached."""
    
    def send(self, alert: dict[str, Any]) -> None:
        """Send an alert. Alert dict contains: scorer_name, tier, score, threshold, details."""
        ...
```

### 5.2 Registry Pattern

```python
"""Registry for discovering and loading plugins."""

class Registry:
    """
    Global registry. Plugins are registered by type string.
    
    Usage:
        registry = Registry()
        registry.register_backend("mlflow", MLflowBackend)
        registry.register_scorer("builtin.latency", LatencyScorer)
        registry.register_capture("mcp", MCPCapture)
        
        backend = registry.get_backend("mlflow", config={...})
    """
    
    _backends: dict[str, type[TraceBackend]]
    _scorers: dict[str, type[Scorer]]
    _captures: dict[str, type[CaptureMiddleware]]
    _alerts: dict[str, type[AlertSink]]
```

## 6. Key Flows

### 6.1 Eval-as-Testing (`arceval test`)

```
1. Parse arceval.yaml
2. Load golden sets from configured path
3. For each golden set record:
   a. Send input to endpoint (via capture middleware)
   b. Capture the trace
   c. Run all scorers whose tier is enabled for testing mode
   d. Compare against golden record where applicable
4. Aggregate results per scorer, per tier
5. Apply gate logic:
   - T1 fail = exit 1 (block deploy)
   - T2 fail = warning in report
   - T3 fail = informational
6. Generate report (markdown/html/json)
7. If --compare flag: diff against previous run, detect regressions
```

### 6.2 Eval-as-Observability (`arceval monitor`)

```
1. Parse arceval.yaml
2. Connect to backend(s)
3. Start polling loop:
   a. Query backend for new traces since last checkpoint
   b. Apply sampling rate per tier
   c. For sampled traces, run scorers (T1 sync, T3 async with concurrency limit)
   d. Store ScoreResults back to backend
   e. Check thresholds, fire alerts on breach
   f. Update checkpoint
4. On SIGTERM: flush pending scores, checkpoint, exit cleanly
```

### 6.3 Initialization (`arceval init`)

```
1. Prompt for endpoint type (mcp/rag/agent/chatbot/http)
2. Prompt for backend (mlflow/langfuse/otel/file)
3. Generate arceval.yaml from template with sensible defaults
4. Generate directory structure:
   arceval.yaml
   golden_sets/
   schemas/
   field_manifests/
   eval-reports/
5. Print next steps
```

## 7. Built-in Scorers (thin, rule-based)

These are the scorers that ship with ArcEval. They cover T1 and T2 metrics that don't require LLM judges.

| Scorer | Tier | What It Checks | Config |
|--------|------|---------------|--------|
| `builtin.latency` | T1 | P50/P95/P99 latency against thresholds | `percentile`, `threshold_ms`, `segment_by` |
| `builtin.error_rate` | T1 | Error rate by type against threshold | `threshold_pct`, `segment_by` |
| `builtin.availability` | T1 | Success rate over rolling window | `threshold_pct`, `window_minutes` |
| `builtin.schema` | T1 | Response matches JSON schema | `schema_path`, `threshold_pct` |
| `builtin.completeness` | T1 | Required fields present in response | `required_fields_path`, `threshold_pct` |
| `builtin.freshness` | T2 | Data timestamp within SLA | `sla_config_path`, `alert_on_breach` |
| `builtin.token_usage` | T2 | Token count anomaly vs baseline | `baseline_window_days`, `anomaly_multiplier` |

## 8. Adapter Scorers (bridges to ecosystem)

These adapt existing eval frameworks to work through the ArcEval scorer interface.

### 8.1 DeepEval Adapter

```python
class DeepEvalAdapter:
    """
    Wraps any DeepEval metric as an ArcEval Scorer.
    
    Supported metrics:
    - deepeval.correctness (GEval with correctness criteria)
    - deepeval.hallucination (HallucinationMetric)
    - deepeval.tool_correctness (ToolCorrectnessMetric)
    - deepeval.task_completion (TaskCompletionMetric)
    - deepeval.faithfulness (FaithfulnessMetric)
    - deepeval.mcp_use (MCPUseMetric)
    
    Usage in arceval.yaml:
      - name: hallucination
        type: deepeval.hallucination
        tier: t3
        config:
          model: "gpt-4o"
          threshold: 0.05
    """
```

### 8.2 RAGAS Adapter

```python
class RAGASAdapter:
    """
    Wraps RAGAS metrics as ArcEval Scorers.
    
    Supported: ragas.faithfulness, ragas.answer_relevancy,
    ragas.context_precision, ragas.context_recall
    """
```

### 8.3 MLflow Scorer Adapter

```python
class MLflowScorerAdapter:
    """
    Wraps MLflow 3 built-in scorers (mlflow.genai.scorers).
    
    Supported: mlflow.correctness, mlflow.safety,
    mlflow.conversation_completeness, mlflow.user_frustration
    
    When backend is also MLflow, scorer results are stored as
    MLflow assessments on the trace (native integration).
    """
```

## 9. Backend Implementations

### 9.1 MLflow Backend

```python
class MLflowBackend:
    """
    Uses MLflow 3 mlflow.genai namespace.
    
    emit(): logs traces via mlflow.tracing
    query(): reads from MLflow experiment traces
    store_scores(): attaches assessments to traces via mlflow.genai
    
    Config:
      type: mlflow
      tracking_uri: "databricks" | "http://localhost:5000" | "file:///..."
      experiment_name: "/path/to/experiment"
    
    When running on Databricks:
    - Traces stored in Unity Catalog Delta tables
    - Evaluation datasets as managed Delta tables
    - Scorer results visible in MLflow UI
    """
```

### 9.2 Langfuse Backend

```python
class LangfuseBackend:
    """
    Uses Langfuse v3 SDK.
    
    emit(): logs traces via langfuse.trace()
    query(): reads via Langfuse API
    store_scores(): attaches scores via langfuse.score()
    
    Config:
      type: langfuse
      public_key: "..."
      secret_key: "..."
      host: "https://cloud.langfuse.com"  # or self-hosted
    """
```

### 9.3 OTEL Backend

```python
class OTELBackend:
    """
    Emits traces as OTLP to any OpenTelemetry-compatible collector.
    Uses gen_ai.* semantic conventions.
    
    Config:
      type: otel
      endpoint: "http://localhost:4318"
      protocol: http | grpc
      headers:
        Authorization: "Bearer ${OTEL_TOKEN}"
    
    Notes:
    - Traces use gen_ai.* attribute namespace
    - store_scores() adds score attributes to spans
    - Compatible with: Jaeger, Grafana Tempo, Datadog, New Relic,
      OpenObserve, SigNoz, and any OTLP receiver
    """
```

### 9.4 File Backend

```python
class FileBackend:
    """
    Local file storage for development and testing.
    
    Config:
      type: file
      path: "./traces/"
      format: jsonl | json
    
    Traces stored as one JSONL line per trace.
    Scores stored alongside in separate file.
    """
```

### 9.5 Delta Backend

```python
class DeltaBackend:
    """
    Direct Delta Lake table storage (for Databricks without MLflow,
    or for custom Delta-based pipelines).
    
    Config:
      type: delta
      catalog: "eval_catalog"
      schema: "bronze"
      traces_table: "mcp_traces"
      scores_table: "eval_scores"
      connection: databricks | delta-rs
    """
```

## 10. CLI Interface

```bash
# Initialize a new project
arceval init
arceval init --type mcp --backend mlflow

# Validate configuration
arceval validate
arceval validate --config path/to/arceval.yaml

# Run eval-as-testing (CI/CD)
arceval test
arceval test --tier t1                    # only T1 scorers
arceval test --tier t1,t2                 # T1 and T2
arceval test --golden-set fundamentals    # specific golden set
arceval test --compare latest             # compare to last run
arceval test --report html                # HTML report
arceval test --fail-on t1                 # exit 1 if T1 fails

# Run eval-as-observability (production)
arceval monitor                           # start monitoring daemon
arceval monitor --daemon                  # background mode
arceval monitor --once                    # single poll cycle (for cron)

# Generate reports
arceval report                            # latest run
arceval report --format markdown          # format
arceval report --compare run-123 run-456  # compare two runs

# Utilities
arceval golden-set validate               # validate golden set format
arceval golden-set diff v1 v2             # diff golden set versions
arceval scorers list                      # list available scorers
arceval backends list                     # list available backends
```

## 11. pytest Plugin

```python
# conftest.py
import arceval

# Register the plugin
arceval.pytest_configure()

# In test files:
def test_mcp_fundamentals(arceval_runner):
    """Run ArcEval T1 + T2 scorers on fundamentals golden set."""
    results = arceval_runner.test(
        golden_set="fundamentals",
        tiers=["t1", "t2"],
    )
    assert results.t1.all_passed
    assert results.t2.pass_rate >= 0.95
```

Or via CLI:
```bash
pytest --arceval --arceval-config=arceval.yaml --arceval-tier=t1
```

## 12. Packaging and Distribution

```
pyproject.toml with optional dependencies:

[project]
name = "arceval"
version = "0.1.0"
description = "The orchestration layer for AI evaluation"
license = "MIT"
requires-python = ">=3.11"
authors = [
    { name = "Vishal Rajpal" }
]

[project.urls]
Repository = "https://github.com/vishalrajpal25/arceval"

dependencies = [
    "pydantic>=2.0",
    "click>=8.0",
    "pyyaml>=6.0",
    "structlog>=24.0",
    "opentelemetry-api>=1.20",
    "opentelemetry-sdk>=1.20",
    "jsonschema>=4.0",
]

[project.optional-dependencies]
mlflow = ["mlflow[databricks]>=3.1"]
langfuse = ["langfuse>=2.0"]
deepeval = ["deepeval>=1.0"]
ragas = ["ragas>=0.2"]
otel = ["opentelemetry-exporter-otlp>=1.20"]
delta = ["deltalake>=0.15"]
all = ["arceval[mlflow,langfuse,deepeval,ragas,otel,delta]"]

[project.scripts]
arceval = "arceval.cli.main:cli"

[project.entry-points.pytest11]
arceval = "arceval.testing.pytest_plugin"

# Dev install (pre-PyPI):
#   git clone https://github.com/vishalrajpal25/arceval.git
#   cd arceval
#   pip install -e ".[all]"
```

## 13. Demo / Quickstart

The repo must include a working demo that runs in under 5 minutes:

```
examples/
├── quickstart/
│   ├── README.md                  # 5-minute quickstart
│   ├── arceval.yaml               # Pre-configured for file backend + built-in scorers
│   ├── mock_endpoint.py           # Simple mock LLM endpoint
│   ├── golden_sets/
│   │   └── sample.jsonl
│   └── run_demo.sh                # One command to see it work
├── mcp-server/
│   ├── README.md
│   ├── arceval.yaml               # MCP-specific config
│   ├── server.py                  # Sample MCP server
│   └── golden_sets/
├── rag-pipeline/
│   ├── README.md
│   ├── arceval.yaml               # RAG-specific config
│   └── pipeline.py                # Simple RAG pipeline
└── databricks/
    ├── README.md
    ├── arceval.yaml               # MLflow backend + Delta
    └── notebook.py                # Databricks notebook example
```

## 14. Documentation Structure

```
docs/
├── index.md                       # Landing page
├── quickstart.md                  # 5-minute getting started
├── concepts/
│   ├── architecture.md            # How ArcEval works
│   ├── tiers.md                   # Tier system explained
│   ├── testing-vs-monitoring.md   # Two modes, one config
│   └── trace-model.md            # Internal trace model + OTEL alignment
├── guides/
│   ├── mcp-server.md             # Evaluating an MCP server
│   ├── rag-pipeline.md           # Evaluating a RAG pipeline
│   ├── agent.md                  # Evaluating an agent
│   ├── ci-cd-integration.md      # GitHub Actions / GitLab CI
│   ├── databricks.md             # Running on Databricks
│   └── custom-scorer.md          # Writing a custom scorer
├── reference/
│   ├── config.md                 # Full arceval.yaml reference
│   ├── protocols.md              # Protocol API reference
│   ├── scorers.md                # All scorers (built-in + adapters)
│   ├── backends.md               # All backends
│   └── cli.md                    # CLI reference
└── contributing.md                # How to contribute
```

## 15. Implementation Order (for Claude Code)

Build in this exact order. Each step should be independently testable.

### Phase 1: Core (get something running)
1. `core/protocols.py` — All Protocol and dataclass definitions
2. `core/config.py` — Pydantic models for arceval.yaml, YAML parsing
3. `core/registry.py` — Registry with register/get methods
4. `core/tier.py` — Tier enum, tier filtering logic
5. `core/trace_model.py` — Trace dataclass with OTEL alignment
6. `core/exceptions.py` — Custom exceptions
7. `backends/file.py` — File backend (simplest, for testing)
8. `scorers/builtin/latency.py` — First built-in scorer
9. `scorers/builtin/error_rate.py` — Second built-in scorer
10. `cli/main.py` + `cli/validate_cmd.py` — CLI skeleton + validate

**Milestone: `arceval validate` works on a sample arceval.yaml**

### Phase 2: Testing Mode
11. `testing/golden_sets.py` — Load and validate golden sets
12. `testing/runner.py` — Test runner (orchestrates scoring)
13. `testing/gates.py` — Pass/fail gate logic
14. `cli/test_cmd.py` — `arceval test` command
15. `capture/manual.py` — Manual trace creation (for testing without live endpoint)
16. Remaining built-in scorers: schema, availability, completeness, freshness, token_usage

**Milestone: `arceval test` runs built-in scorers against golden sets, produces report**

### Phase 3: Monitoring Mode
17. `monitoring/sampler.py` — Sampling logic
18. `monitoring/continuous.py` — Polling loop
19. `monitoring/alerts.py` — Alert routing
20. `cli/monitor_cmd.py` — `arceval monitor` command

**Milestone: `arceval monitor` polls file backend, runs scorers, logs results**

### Phase 4: Backend Adapters
21. `backends/mlflow.py` — MLflow 3 integration
22. `backends/langfuse.py` — Langfuse v3 integration
23. `backends/otel.py` — OTEL exporter
24. `backends/delta.py` — Delta Lake direct

**Milestone: Traces flow to MLflow and Langfuse**

### Phase 5: Scorer Adapters
25. `scorers/adapters/deepeval.py` — DeepEval bridge
26. `scorers/adapters/ragas.py` — RAGAS bridge
27. `scorers/adapters/mlflow_scorers.py` — MLflow scorer bridge
28. `scorers/adapters/custom.py` — User-defined callable scorer

**Milestone: DeepEval hallucination scorer runs through ArcEval**

### Phase 6: Capture Middleware
29. `capture/mcp.py` — MCP server instrumentation
30. `capture/fastapi.py` — FastAPI middleware
31. `capture/langchain.py` — LangChain callback
32. `capture/openai_wrapper.py` — OpenAI client wrapper

**Milestone: MCP server auto-instrumented, traces flowing**

### Phase 7: Polish
33. `testing/regression.py` — Regression detection
34. `monitoring/drift.py` — Drift detection
35. `testing/pytest_plugin.py` — pytest integration
36. `cli/init_cmd.py` — Project scaffolding
37. `cli/report_cmd.py` — Report generation
38. Examples and documentation

## 16. Testing Strategy

```
tests/
├── unit/
│   ├── test_config.py            # Config parsing and validation
│   ├── test_registry.py          # Registry behavior
│   ├── test_tier.py              # Tier filtering
│   ├── test_trace_model.py       # Trace creation and serialization
│   └── scorers/
│       ├── test_latency.py       # Each built-in scorer
│       ├── test_error_rate.py
│       └── ...
├── integration/
│   ├── test_file_backend.py      # File backend round-trip
│   ├── test_test_runner.py       # Full test flow with file backend
│   ├── test_monitor_loop.py      # Monitor polling with file backend
│   └── test_golden_sets.py       # Golden set loading and validation
├── adapters/
│   ├── test_deepeval_adapter.py  # Requires deepeval installed
│   ├── test_ragas_adapter.py     # Requires ragas installed
│   └── test_mlflow_adapter.py    # Requires mlflow installed
└── e2e/
    ├── test_cli_validate.py      # CLI validate command
    ├── test_cli_test.py          # CLI test command end-to-end
    └── test_cli_init.py          # CLI init scaffolding
```

Use pytest. Adapters tests are marked with `@pytest.mark.requires_deepeval` etc. so they only run when the dependency is installed.

## 17. Code Style and Conventions

- Python 3.11+
- Type hints on every function signature
- Pydantic v2 for all config models
- structlog for logging (structured JSON)
- No em-dashes in docstrings or comments
- No filler phrases ("leverage", "utilize", "drive innovation")
- Tests for every public function
- Docstrings on every Protocol method
- OTEL attribute names use `gen_ai.*` namespace
- Config keys use snake_case
- CLI commands use kebab-case (e.g., `golden-set`)

## 18. Naming and Branding

**Project name:** ArcEval (lifecycle arc + evaluation)
**GitHub repo:** `github.com/vishalrajpal25/arceval` (personal repo)
**PyPI package:** `arceval` (reserved for future, not publishing immediately)
**CLI command:** `arceval`
**Import:** `import arceval`
**Tagline:** "One config. Any backend. Every phase."
**License:** MIT
**Install (pre-PyPI):** `pip install git+https://github.com/vishalrajpal25/arceval.git`

## 19. What ArcEval Is NOT

- NOT a trace storage system (delegates to MLflow, Langfuse, OTEL backends)
- NOT a dashboard (use MLflow UI, Langfuse UI, Grafana, Databricks SQL)
- NOT a scorer library (ships thin built-ins, adapts DeepEval/RAGAS/MLflow)
- NOT a model serving platform
- NOT a prompt management tool
- NOT tied to any cloud provider or data platform

It IS the missing orchestration layer that makes all of these work together in a coherent, config-driven, tiered evaluation lifecycle.
