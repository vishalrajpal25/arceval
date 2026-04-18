"""arceval validate -- validate an arceval.yaml config file."""

from __future__ import annotations

import sys

import click

from arceval.core.config import validate_config


@click.command()
@click.option(
    "--config",
    "config_path",
    default="arceval.yaml",
    help="Path to arceval.yaml config file.",
    type=click.Path(),
)
def validate(config_path: str) -> None:
    """Validate an arceval.yaml configuration file."""
    errors = validate_config(config_path)

    if not errors:
        click.secho("Config is valid.", fg="green")
        sys.exit(0)
    else:
        click.secho(f"Config validation failed with {len(errors)} error(s):", fg="red")
        for error in errors:
            click.echo(f"  - {error}")
        sys.exit(1)
