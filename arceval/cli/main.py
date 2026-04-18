"""CLI entry point for ArcEval."""

import click

from arceval.cli.validate_cmd import validate
from arceval.cli.test_cmd import test
from arceval.cli.monitor_cmd import monitor
from arceval.cli.init_cmd import init
from arceval.cli.report_cmd import report


@click.group()
@click.version_option(version="0.1.0", prog_name="arceval")
def cli() -> None:
    """ArcEval: The orchestration layer for AI evaluation."""


cli.add_command(validate)
cli.add_command(test)
cli.add_command(monitor)
cli.add_command(init)
cli.add_command(report)
