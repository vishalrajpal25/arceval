"""arceval test -- run eval-as-testing against golden sets."""

from __future__ import annotations

import sys

import click

from arceval.core.config import load_config
from arceval.core.registry import default_registry
from arceval.core.tier import Tier
from arceval.testing.golden_sets import load_golden_set
from arceval.testing.runner import EvalTestRunner, generate_report, save_report


@click.command()
@click.option(
    "--config",
    "config_path",
    default="arceval.yaml",
    help="Path to arceval.yaml config file.",
    type=click.Path(exists=True),
)
@click.option(
    "--tier",
    "tiers",
    default=None,
    help="Comma-separated tiers to run (e.g. t1,t2). Default: all.",
)
@click.option(
    "--golden-set",
    "golden_set_name",
    default=None,
    help="Name of a specific golden set to run.",
)
@click.option(
    "--report",
    "report_format",
    default=None,
    help="Report format: markdown, json. Overrides config.",
)
@click.option(
    "--fail-on",
    default=None,
    help="Tier that causes exit 1 on failure. Overrides config.",
)
@click.option(
    "--warn-on",
    default=None,
    help="Tier that causes warning. Overrides config.",
)
def test(
    config_path: str,
    tiers: str | None,
    golden_set_name: str | None,
    report_format: str | None,
    fail_on: str | None,
    warn_on: str | None,
) -> None:
    """Run eval-as-testing: score traces against golden sets."""
    config = load_config(config_path)

    # Parse tier filter
    tier_list = [t.strip() for t in tiers.split(",")] if tiers else None

    # Resolve gate settings
    effective_fail_on = fail_on or config.testing.fail_on
    effective_warn_on = warn_on or config.testing.warn_on
    effective_format = report_format or config.testing.report_format

    # Instantiate scorers from config
    scorers = []
    for scorer_cfg in config.scorers:
        try:
            scorer = default_registry.get_scorer(
                scorer_cfg.type,
                {**scorer_cfg.config, "tier": scorer_cfg.tier, "name": scorer_cfg.name},
            )
            scorers.append(scorer)
        except Exception as exc:
            click.secho(f"Warning: failed to load scorer '{scorer_cfg.name}': {exc}", fg="yellow")

    if not scorers:
        click.secho("No scorers loaded. Check your config.", fg="red")
        sys.exit(1)

    click.echo(f"Loaded {len(scorers)} scorer(s)")

    # Load golden sets
    from arceval.core.protocols import GoldenRecord
    from arceval.core.trace_model import create_trace

    golden_records: list[GoldenRecord] = []
    traces: list = []

    if config.golden_sets and config.golden_sets.sets:
        sets_to_load = config.golden_sets.sets
        if golden_set_name:
            sets_to_load = [s for s in sets_to_load if s.name == golden_set_name]
            if not sets_to_load:
                click.secho(f"Golden set '{golden_set_name}' not found in config.", fg="red")
                sys.exit(1)

        for gs_entry in sets_to_load:
            gs_path = f"{config.golden_sets.path}/{gs_entry.file}"
            try:
                records = load_golden_set(gs_path, format=config.golden_sets.format)
                click.echo(f"Loaded {len(records)} records from golden set '{gs_entry.name}'")
                for record in records:
                    golden_records.append(record)
                    # Create a synthetic trace from golden set input/output
                    trace = create_trace(
                        input_data=record.input_data,
                        output_data=record.expected_output,
                        status_code=200,
                        latency_ms=record.metadata.get("latency_ms"),
                        attributes=record.metadata,
                    )
                    traces.append(trace)
            except Exception as exc:
                click.secho(f"Warning: failed to load golden set '{gs_entry.name}': {exc}", fg="yellow")

    if not traces:
        click.secho("No traces to score. Add golden sets or provide traces.", fg="yellow")
        # Still run scorers with empty list for validation purposes
        # but create a dummy trace for basic validation
        click.echo("Running scorers in validation-only mode (no traces).")

    # Run
    runner = EvalTestRunner(scorers, config=config)
    run_result = runner.run(
        traces=traces,
        golden_records=golden_records if golden_records else None,
        tiers=tier_list,
        fail_on=effective_fail_on,
        warn_on=effective_warn_on,
    )

    # Generate report
    report = generate_report(run_result, format=effective_format)

    # Save report
    report_path = save_report(report, config.testing.output_dir, format=effective_format)
    click.echo(f"Report saved to: {report_path}")

    # Print summary
    click.echo("")
    gate = run_result.gate_result
    if gate:
        if gate.failures:
            click.secho("FAILURES:", fg="red", bold=True)
            for f in gate.failures:
                click.echo(f"  {f}")

        if gate.warnings:
            click.secho("WARNINGS:", fg="yellow", bold=True)
            for w in gate.warnings:
                click.echo(f"  {w}")

        verdict_colors = {"pass": "green", "warn": "yellow", "fail": "red"}
        click.echo("")
        click.secho(
            f"Verdict: {gate.verdict.value.upper()} "
            f"({run_result.traces_scored} traces, {len(run_result.results)} scores, "
            f"{run_result.pass_rate:.1%} pass rate)",
            fg=verdict_colors.get(gate.verdict.value, "white"),
            bold=True,
        )

    sys.exit(gate.exit_code if gate else 0)
