"""End-to-end tests for the CLI test command."""

import textwrap

from click.testing import CliRunner

from arceval.cli.main import cli


class TestCLITest:
    def _write_config_and_golden(self, tmp_path):
        """Create a valid config + golden set for testing."""
        gs_dir = tmp_path / "golden_sets"
        gs_dir.mkdir()
        (gs_dir / "sample.jsonl").write_text(
            '{"input": {"query": "AAPL"}, "expected_output": {"price": 150}, "metadata": {"latency_ms": 100}}\n'
            '{"input": {"query": "MSFT"}, "expected_output": {"price": 300}, "metadata": {"latency_ms": 200}}\n'
        )

        reports_dir = tmp_path / "eval-reports"
        reports_dir.mkdir()

        cfg_file = tmp_path / "arceval.yaml"
        cfg_file.write_text(textwrap.dedent(f"""\
            version: "1"
            project: "test-project"
            endpoint:
              type: http
              name: "Test"
            backends:
              dev:
                type: file
                path: "{tmp_path / 'traces'}"
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
                  threshold_ms: 2000
                  percentile: 95
              - name: error_rate
                type: builtin.error_rate
                tier: t1
                config:
                  threshold_pct: 0.5
            golden_sets:
              path: "{gs_dir}"
              format: jsonl
              sets:
                - name: sample
                  file: "sample.jsonl"
            testing:
              report_format: markdown
              output_dir: "{reports_dir}"
              fail_on: t1
              warn_on: t2
        """))
        return cfg_file, reports_dir

    def test_all_pass(self, tmp_path):
        cfg_file, reports_dir = self._write_config_and_golden(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--config", str(cfg_file)])
        assert result.exit_code == 0
        assert "PASS" in result.output
        # Report should have been saved
        report_files = list(reports_dir.glob("*.md"))
        assert len(report_files) == 1

    def test_tier_filter(self, tmp_path):
        cfg_file, _ = self._write_config_and_golden(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--config", str(cfg_file), "--tier", "t1"])
        assert result.exit_code == 0

    def test_json_report(self, tmp_path):
        cfg_file, reports_dir = self._write_config_and_golden(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--config", str(cfg_file), "--report", "json"])
        assert result.exit_code == 0
        report_files = list(reports_dir.glob("*.json"))
        assert len(report_files) == 1

    def test_failure_exits_1(self, tmp_path):
        gs_dir = tmp_path / "golden_sets"
        gs_dir.mkdir()
        (gs_dir / "sample.jsonl").write_text(
            '{"input": {"q": "test"}, "expected_output": "ok", "metadata": {"latency_ms": 5000}}\n'
        )

        reports_dir = tmp_path / "eval-reports"
        reports_dir.mkdir()

        cfg_file = tmp_path / "arceval.yaml"
        cfg_file.write_text(textwrap.dedent(f"""\
            version: "1"
            project: "test-fail"
            endpoint:
              type: http
            backends:
              dev:
                type: file
                path: "{tmp_path / 'traces'}"
            tiers:
              t1:
                name: "Must-Have"
                mode: always
            scorers:
              - name: latency
                type: builtin.latency
                tier: t1
                config:
                  threshold_ms: 100
            golden_sets:
              path: "{gs_dir}"
              format: jsonl
              sets:
                - name: sample
                  file: "sample.jsonl"
            testing:
              output_dir: "{reports_dir}"
              fail_on: t1
        """))

        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--config", str(cfg_file)])
        assert result.exit_code == 1
        assert "FAIL" in result.output
