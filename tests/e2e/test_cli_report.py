"""End-to-end tests for the CLI report command."""

import json

from click.testing import CliRunner

from arceval.cli.main import cli


class TestCLIReport:
    def test_latest_markdown(self, tmp_path):
        reports_dir = tmp_path / "eval-reports"
        reports_dir.mkdir()
        (reports_dir / "report_20260101_120000.md").write_text("# Test Report\nAll good.")

        runner = CliRunner()
        result = runner.invoke(cli, ["report", "--latest", "--input", str(reports_dir)])
        assert result.exit_code == 0
        assert "Test Report" in result.output

    def test_latest_json(self, tmp_path):
        reports_dir = tmp_path / "eval-reports"
        reports_dir.mkdir()
        (reports_dir / "report_20260101_120000.json").write_text('{"verdict": "pass"}')

        runner = CliRunner()
        result = runner.invoke(cli, [
            "report", "--latest", "--format", "json", "--input", str(reports_dir)
        ])
        assert result.exit_code == 0
        assert "pass" in result.output

    def test_no_reports(self, tmp_path):
        reports_dir = tmp_path / "eval-reports"
        reports_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["report", "--latest", "--input", str(reports_dir)])
        assert result.exit_code == 0
        assert "No reports" in result.output

    def test_compare(self, tmp_path):
        r1 = tmp_path / "run1.json"
        r2 = tmp_path / "run2.json"
        r1.write_text(json.dumps({
            "results": [
                {"scorer_name": "latency", "score": 0.9, "passed": True},
                {"scorer_name": "error_rate", "score": 1.0, "passed": True},
            ]
        }))
        r2.write_text(json.dumps({
            "results": [
                {"scorer_name": "latency", "score": 0.5, "passed": False},
                {"scorer_name": "error_rate", "score": 1.0, "passed": True},
            ]
        }))

        runner = CliRunner()
        result = runner.invoke(cli, [
            "report", "--compare", str(r1), str(r2)
        ])
        assert result.exit_code == 0
        assert "REGRESSED" in result.output
        assert "latency" in result.output

    def test_compare_no_regression(self, tmp_path):
        r1 = tmp_path / "run1.json"
        r2 = tmp_path / "run2.json"
        r1.write_text(json.dumps({"results": [{"scorer_name": "a", "score": 0.8}]}))
        r2.write_text(json.dumps({"results": [{"scorer_name": "a", "score": 0.9}]}))

        runner = CliRunner()
        result = runner.invoke(cli, ["report", "--compare", str(r1), str(r2)])
        assert result.exit_code == 0
        assert "No regressions" in result.output

    def test_report_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["report", "--help"])
        assert result.exit_code == 0
        assert "--compare" in result.output
        assert "--latest" in result.output
