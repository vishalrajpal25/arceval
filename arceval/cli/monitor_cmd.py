"""arceval monitor -- start eval-as-observability monitoring."""

from __future__ import annotations

import sys

import click

from arceval.core.config import load_config
from arceval.core.registry import default_registry
from arceval.monitoring.alerts import AlertRouter, LogAlertSink, SlackAlertSink, WebhookAlertSink
from arceval.monitoring.continuous import ContinuousMonitor
from arceval.monitoring.sampler import Sampler


@click.command()
@click.option(
    "--config",
    "config_path",
    default="arceval.yaml",
    help="Path to arceval.yaml config file.",
    type=click.Path(exists=True),
)
@click.option(
    "--once",
    is_flag=True,
    default=False,
    help="Run a single poll cycle then exit (for cron-based monitoring).",
)
@click.option(
    "--poll-interval",
    default=None,
    type=int,
    help="Override poll interval in seconds.",
)
def monitor(config_path: str, once: bool, poll_interval: int | None) -> None:
    """Start eval-as-observability: poll for traces, score, and alert."""
    config = load_config(config_path)

    # Instantiate primary backend
    backend_name = config.monitoring.storage.results_backend
    backend_cfg = config.backends.get(backend_name)
    if not backend_cfg:
        # Fall back to first backend
        if config.backends:
            backend_name = next(iter(config.backends))
            backend_cfg = config.backends[backend_name]
        else:
            click.secho("No backends configured.", fg="red")
            sys.exit(1)

    backend = default_registry.get_backend(
        backend_cfg.type,
        {k: v for k, v in backend_cfg.model_dump().items() if k != "type"},
    )

    if not backend.health_check():
        click.secho(f"Backend '{backend_name}' health check failed.", fg="red")
        sys.exit(1)

    click.echo(f"Backend '{backend_name}' ({backend_cfg.type}) connected")

    # Instantiate scorers for monitoring mode
    scorers = []
    for scorer_cfg in config.scorers:
        tier_key = scorer_cfg.tier
        tier_cfg = config.tiers.get(tier_key)
        if tier_cfg and not tier_cfg.in_monitoring:
            continue
        try:
            scorer = default_registry.get_scorer(
                scorer_cfg.type,
                {**scorer_cfg.config, "tier": scorer_cfg.tier, "name": scorer_cfg.name},
            )
            scorers.append(scorer)
        except Exception as exc:
            click.secho(f"Warning: failed to load scorer '{scorer_cfg.name}': {exc}", fg="yellow")

    if not scorers:
        click.secho("No scorers loaded for monitoring.", fg="red")
        sys.exit(1)

    click.echo(f"Loaded {len(scorers)} scorer(s) for monitoring")

    # Build sampler from tier config (use min sample rate across active tiers)
    sample_rates = []
    for scorer_cfg in config.scorers:
        tier_cfg = config.tiers.get(scorer_cfg.tier)
        if tier_cfg:
            sample_rates.append(tier_cfg.sample_rate)
    sample_rate = min(sample_rates) if sample_rates else 1.0
    sampler = Sampler(rate=sample_rate)
    click.echo(f"Sampling rate: {sample_rate:.0%}")

    # Build alert router
    alert_router = AlertRouter()
    for alert_cfg in config.alerts:
        alert_type = alert_cfg.type
        on_events = alert_cfg.on
        extra = {k: v for k, v in alert_cfg.model_dump().items() if k not in ("type", "on")}

        if alert_type == "slack":
            sink = SlackAlertSink(
                webhook_url=extra.get("webhook_url", ""),
                channel=extra.get("channel", ""),
            )
        elif alert_type == "webhook":
            sink = WebhookAlertSink(
                url=extra.get("url", ""),
                headers=extra.get("headers"),
            )
        else:
            sink = LogAlertSink()

        alert_router.add_rule(on=on_events, sink=sink)

    # Always add a log sink as fallback
    alert_router.add_rule(on=["t1.fail"], sink=LogAlertSink())

    effective_interval = poll_interval or config.monitoring.poll_interval_seconds

    # Build and run monitor
    mon = ContinuousMonitor(
        backend=backend,
        scorers=scorers,
        sampler=sampler,
        alert_router=alert_router,
        results_backend=backend,
        poll_interval_seconds=effective_interval,
        batch_size=config.monitoring.batch_size,
    )

    if once:
        click.echo("Running single monitoring cycle...")
        result = mon.run_once()
        click.echo(
            f"Done: {result.traces_queried} traces queried, "
            f"{result.traces_sampled} sampled, "
            f"{result.scores_produced} scored, "
            f"{result.alerts_fired} alerts"
        )
    else:
        click.echo(f"Starting monitoring loop (interval={effective_interval}s)...")
        click.echo("Press Ctrl+C to stop.")
        state = mon.run()
        click.echo(
            f"\nStopped. Totals: {state.total_traces_processed} traces, "
            f"{state.total_scores_produced} scores, "
            f"{state.total_alerts_fired} alerts over {state.cycles} cycles"
        )
