# ArcEval

**One config. Any backend. Every phase.**

ArcEval is an open-source Python framework that orchestrates end-to-end evaluation for AI endpoints -- MCP servers, RAG pipelines, agents, chatbots, and any LLM-powered service.

It does not replace MLflow, Langfuse, DeepEval, or RAGAS. It sits above them as a unified orchestration layer that:

- **Instruments** your endpoint with lightweight middleware (capture)
- **Routes** traces to whatever backend you already use (MLflow, Langfuse, OTEL, file)
- **Scores** traces using any ecosystem (built-in, DeepEval, RAGAS, MLflow)
- **Organizes** everything into prioritized tiers so teams know what to instrument first
- **Unifies** CI/CD (eval-as-testing) and production (eval-as-observability) in one config

## Architecture

```
              arceval.yaml
                   |
          +--------v--------+
          |   ArcEval Core   |
          |  config, registry |
          |  tiers, lifecycle  |
          +--+----+----+-----+
             |    |    |
        +----+  +-+-+  +-------+
        |Capture| |Score|  |Backends|
        | MCP   | |built|  | MLflow |
        | RAG   | | in  |  |Langfuse|
        | Agent | |deep |  |  OTEL  |
        | HTTP  | |eval |  |  File  |
        +-------+ |ragas|  | Delta  |
                   +-----+  +--------+
```

## Quick Start

### Install

```bash
pip install arceval
```

With optional backends and scorer adapters:

```bash
pip install arceval[mlflow]       # MLflow 3 backend
pip install arceval[langfuse]     # Langfuse backend
pip install arceval[deepeval]     # DeepEval scorer adapter
pip install arceval[all]          # Everything
```

### Create a Config

```yaml
# arceval.yaml
version: "1"
project: "my-project"

endpoint:
  type: http
  name: "My LLM Service"

backends:
  dev:
    type: file
    path: "./traces/"

tiers:
  t1:
    name: "Must-Have"
    mode: always
    block_deploy: true

scorers:
  - name: latency_p95
    type: builtin.latency
    tier: t1
    config:
      percentile: 95
      threshold_ms: 2000

  - name: error_rate
    type: builtin.error_rate
    tier: t1
    config:
      threshold_pct: 0.5
```

### Validate

```bash
arceval validate
```

### Run Evals (coming in Phase 2)

```bash
arceval test                    # eval-as-testing (CI/CD)
arceval monitor                 # eval-as-observability (production)
```

## Tiered Evaluation

ArcEval organizes metrics into three tiers:

| Tier | Name | What | When |
|------|------|------|------|
| **T1** | Must-Have | Latency, error rate, schema compliance, availability | Day one. Rule-based. No dependencies. |
| **T2** | Operational | Golden-set comparison, data freshness, token anomalies | When golden sets exist. |
| **T3** | Advanced | LLM-as-judge (hallucination, faithfulness, correctness) | When judge endpoints are configured. |

Tiers control what runs when, what blocks deploys, and what samples in production.

## Built-in Scorers

| Scorer | Tier | Description |
|--------|------|-------------|
| `builtin.latency` | T1 | P50/P95/P99 latency against thresholds |
| `builtin.error_rate` | T1 | Error rate by type against threshold |
| `builtin.availability` | T1 | Uptime / success rate |
| `builtin.schema` | T1 | Response JSON schema compliance |
| `builtin.completeness` | T1 | Required fields present in response |
| `builtin.freshness` | T2 | Data timestamp within SLA |
| `builtin.token_usage` | T2 | Token count anomaly detection |

## Scorer Adapters

Use scorers from existing ecosystems through ArcEval:

```yaml
# DeepEval
- name: hallucination
  type: deepeval.hallucination
  tier: t3
  config:
    model: "gpt-4o"
    threshold: 0.05

# RAGAS
- name: faithfulness
  type: ragas.faithfulness
  tier: t3

# MLflow 3
- name: correctness
  type: mlflow.correctness
  tier: t3
```

## Supported Backends

| Backend | Description |
|---------|-------------|
| `file` | Local JSONL files (dev/testing) |
| `mlflow` | MLflow 3 with `mlflow.genai` namespace |
| `langfuse` | Langfuse v3 SDK |
| `otel` | Any OpenTelemetry OTLP-compatible collector |
| `delta` | Databricks Delta Lake tables |

Multiple backends can be active simultaneously.

## Design Principles

1. **Config-driven, not code-driven.** YAML manifest is the primary interface.
2. **Protocols over inheritance.** Every extension point is a Python Protocol.
3. **Delegate, don't duplicate.** Orchestrate existing tools, don't reimplement them.
4. **Tiers are first-class.** Every metric belongs to a tier.
5. **Same scorer, two modes.** One scorer runs in both CI and production.
6. **OTEL-native.** Internal trace model follows `gen_ai.*` semantic conventions.
7. **Zero opinions on infra.** Works anywhere Python runs.

## Development

```bash
# Clone and install
git clone https://github.com/vishalrajpal25/arceval.git
cd arceval
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run tests
pytest

# Validate example config
arceval validate --config examples/quickstart/arceval.yaml
```

## Roadmap

- [x] **Phase 1: Core** -- Protocols, config, registry, file backend, latency/error_rate scorers, CLI validate
- [x] **Phase 2: Testing Mode** -- Golden sets, test runner, CI/CD gates, `arceval test`
- [x] **Phase 3: Monitoring Mode** -- Sampling, continuous scoring, alerts, `arceval monitor`
- [x] **Phase 4: Backend Adapters** -- MLflow, Langfuse, OTEL, Delta
- [x] **Phase 5: Scorer Adapters** -- DeepEval, RAGAS, MLflow scorers, custom callable
- [x] **Phase 6: Capture Middleware** -- MCP, FastAPI, LangChain, OpenAI
- [x] **Phase 7: Polish** -- Regression detection, drift detection, pytest plugin, `arceval init`, `arceval report`

## License

MIT
