"""arceval init -- scaffold a new arceval.yaml project."""

from __future__ import annotations

import sys
from pathlib import Path

import click


TEMPLATES: dict[str, str] = {
    "mcp": """\
version: "1"
project: "{project}"

endpoint:
  type: mcp
  name: "{project} MCP Service"

backends:
  dev:
    type: file
    path: "./traces/"
    format: jsonl

tiers:
  t1:
    name: "Must-Have"
    description: "Instrument on day one. Rule-based."
    mode: always
    in_testing: true
    in_monitoring: true
    sample_rate: 1.0
    block_deploy: true
  t2:
    name: "Operational"
    description: "Requires golden sets."
    mode: on_golden_set
    in_testing: true
    in_monitoring: true
    sample_rate: 1.0
    block_deploy: false
  t3:
    name: "Advanced"
    description: "LLM-as-judge. Async, sampled."
    mode: on_judge
    in_testing: true
    in_monitoring: true
    sample_rate: 0.1
    block_deploy: false

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

  - name: availability
    type: builtin.availability
    tier: t1
    config:
      threshold_pct: 99.9

golden_sets:
  path: "./golden_sets/"
  format: jsonl
  sets: []

testing:
  report_format: markdown
  output_dir: "./eval-reports/"
  fail_on: t1
  warn_on: t2
  compare_to: latest

monitoring:
  poll_interval_seconds: 30
  batch_size: 100
""",
    "rag": """\
version: "1"
project: "{project}"

endpoint:
  type: rag
  name: "{project} RAG Pipeline"

backends:
  dev:
    type: file
    path: "./traces/"

tiers:
  t1:
    name: "Must-Have"
    mode: always
    block_deploy: true
  t2:
    name: "Operational"
    mode: on_golden_set
  t3:
    name: "Advanced"
    mode: on_judge
    sample_rate: 0.1

scorers:
  - name: latency_p95
    type: builtin.latency
    tier: t1
    config:
      percentile: 95
      threshold_ms: 3000

  - name: error_rate
    type: builtin.error_rate
    tier: t1
    config:
      threshold_pct: 1.0

golden_sets:
  path: "./golden_sets/"
  format: jsonl
  sets: []

testing:
  report_format: markdown
  output_dir: "./eval-reports/"
  fail_on: t1
""",
    "agent": """\
version: "1"
project: "{project}"

endpoint:
  type: agent
  name: "{project} Agent"

backends:
  dev:
    type: file
    path: "./traces/"

tiers:
  t1:
    name: "Must-Have"
    mode: always
    block_deploy: true
  t2:
    name: "Operational"
    mode: on_golden_set

scorers:
  - name: latency_p95
    type: builtin.latency
    tier: t1
    config:
      percentile: 95
      threshold_ms: 5000

  - name: error_rate
    type: builtin.error_rate
    tier: t1
    config:
      threshold_pct: 1.0

golden_sets:
  path: "./golden_sets/"
  format: jsonl
  sets: []

testing:
  report_format: markdown
  output_dir: "./eval-reports/"
  fail_on: t1
""",
    "http": """\
version: "1"
project: "{project}"

endpoint:
  type: http
  name: "{project} HTTP Service"

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

testing:
  report_format: markdown
  output_dir: "./eval-reports/"
  fail_on: t1
""",
}


@click.command()
@click.option(
    "--type",
    "endpoint_type",
    type=click.Choice(["mcp", "rag", "agent", "http"]),
    default=None,
    help="Endpoint type for the template.",
)
@click.option(
    "--project",
    default=None,
    help="Project name. Defaults to current directory name.",
)
def init(endpoint_type: str | None, project: str | None) -> None:
    """Initialize a new ArcEval project with arceval.yaml and directory structure."""
    config_path = Path("arceval.yaml")

    if config_path.exists():
        click.secho("arceval.yaml already exists. Aborting.", fg="yellow")
        sys.exit(1)

    if project is None:
        project = Path.cwd().name

    if endpoint_type is None:
        endpoint_type = click.prompt(
            "Endpoint type",
            type=click.Choice(["mcp", "rag", "agent", "http"]),
            default="http",
        )

    template = TEMPLATES.get(endpoint_type, TEMPLATES["http"])
    config_content = template.format(project=project)

    # Write config
    config_path.write_text(config_content)
    click.echo(f"Created arceval.yaml (type={endpoint_type})")

    # Create directories
    dirs = ["golden_sets", "eval-reports", "schemas"]
    for d in dirs:
        Path(d).mkdir(exist_ok=True)
        click.echo(f"Created {d}/")

    click.echo("")
    click.secho("Project initialized!", fg="green")
    click.echo("")
    click.echo("Next steps:")
    click.echo("  1. Edit arceval.yaml to configure your endpoint and scorers")
    click.echo("  2. Add golden set files to golden_sets/")
    click.echo("  3. Run: arceval validate")
    click.echo("  4. Run: arceval test")
