"""arceval report -- generate evaluation reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click


@click.command()
@click.option(
    "--format",
    "report_format",
    type=click.Choice(["markdown", "json"]),
    default="markdown",
    help="Report output format.",
)
@click.option(
    "--input",
    "input_dir",
    default="./eval-reports/",
    help="Directory containing report files.",
)
@click.option(
    "--compare",
    "compare_runs",
    nargs=2,
    default=None,
    help="Compare two report files for regression detection.",
)
@click.option(
    "--latest",
    is_flag=True,
    default=False,
    help="Show the latest report.",
)
def report(
    report_format: str,
    input_dir: str,
    compare_runs: tuple[str, str] | None,
    latest: bool,
) -> None:
    """Generate or view evaluation reports."""
    input_path = Path(input_dir)

    if compare_runs:
        _compare_reports(compare_runs[0], compare_runs[1])
        return

    if latest or not compare_runs:
        _show_latest(input_path, report_format)
        return


def _show_latest(input_path: Path, report_format: str) -> None:
    """Show the most recent report."""
    if not input_path.exists():
        click.secho(f"Report directory not found: {input_path}", fg="red")
        sys.exit(1)

    ext = "md" if report_format == "markdown" else "json"
    reports = sorted(input_path.glob(f"*.{ext}"), reverse=True)

    if not reports:
        # Try any report file
        reports = sorted(input_path.glob("report_*"), reverse=True)

    if not reports:
        click.secho("No reports found.", fg="yellow")
        sys.exit(0)

    latest = reports[0]
    click.echo(f"Latest report: {latest}")
    click.echo("")
    click.echo(latest.read_text())


def _compare_reports(file1: str, file2: str) -> None:
    """Compare two JSON report files for regressions."""
    path1 = Path(file1)
    path2 = Path(file2)

    if not path1.exists():
        click.secho(f"Report not found: {path1}", fg="red")
        sys.exit(1)
    if not path2.exists():
        click.secho(f"Report not found: {path2}", fg="red")
        sys.exit(1)

    try:
        data1 = json.loads(path1.read_text())
        data2 = json.loads(path2.read_text())
    except json.JSONDecodeError as exc:
        click.secho(f"Invalid JSON in report: {exc}", fg="red")
        sys.exit(1)

    click.echo(f"Comparing: {path1.name} vs {path2.name}")
    click.echo("")

    results1 = {r["scorer_name"]: r for r in data1.get("results", [])}
    results2 = {r["scorer_name"]: r for r in data2.get("results", [])}

    all_scorers = sorted(set(results1.keys()) | set(results2.keys()))

    click.echo("| Scorer | Baseline | Current | Delta | Status |")
    click.echo("|--------|----------|---------|-------|--------|")

    regressions = 0
    for scorer in all_scorers:
        r1 = results1.get(scorer)
        r2 = results2.get(scorer)
        s1 = r1["score"] if r1 and r1.get("score") is not None else None
        s2 = r2["score"] if r2 and r2.get("score") is not None else None

        s1_str = f"{s1:.4f}" if s1 is not None else "N/A"
        s2_str = f"{s2:.4f}" if s2 is not None else "N/A"

        if s1 is not None and s2 is not None:
            delta = s2 - s1
            delta_str = f"{delta:+.4f}"
            if delta < 0:
                status = "REGRESSED"
                regressions += 1
            elif delta > 0:
                status = "IMPROVED"
            else:
                status = "OK"
        else:
            delta_str = "N/A"
            status = "NEW" if s1 is None else "REMOVED"

        click.echo(f"| {scorer} | {s1_str} | {s2_str} | {delta_str} | {status} |")

    click.echo("")
    if regressions:
        click.secho(f"{regressions} regression(s) detected.", fg="red")
    else:
        click.secho("No regressions detected.", fg="green")
