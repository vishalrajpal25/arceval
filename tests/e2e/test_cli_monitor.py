"""End-to-end tests for the CLI monitor command."""

import textwrap

from click.testing import CliRunner

from arceval.backends.file import FileBackend
from arceval.cli.main import cli
from arceval.core.trace_model import create_trace


class TestCLIMonitor:
    def _write_config(self, tmp_path):
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()

        cfg_file = tmp_path / "arceval.yaml"
        cfg_file.write_text(textwrap.dedent(f"""\
            version: "1"
            project: "monitor-test"
            endpoint:
              type: http
              name: "Test"
            backends:
              dev:
                type: file
                path: "{traces_dir}"
            tiers:
              t1:
                name: "Must-Have"
                mode: always
                in_monitoring: true
                sample_rate: 1.0
            scorers:
              - name: latency
                type: builtin.latency
                tier: t1
                config:
                  threshold_ms: 2000
                  percentile: 95
            monitoring:
              poll_interval_seconds: 1
              batch_size: 50
              storage:
                results_backend: dev
        """))
        return cfg_file, traces_dir

    def test_monitor_once_no_traces(self, tmp_path):
        cfg_file, _ = self._write_config(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["monitor", "--config", str(cfg_file), "--once"])
        assert result.exit_code == 0
        assert "0 traces queried" in result.output

    def test_monitor_once_with_traces(self, tmp_path):
        cfg_file, traces_dir = self._write_config(tmp_path)

        # Pre-populate traces
        backend = FileBackend(path=str(traces_dir))
        backend.emit([
            create_trace(latency_ms=100.0, status_code=200),
            create_trace(latency_ms=200.0, status_code=200),
        ])

        runner = CliRunner()
        result = runner.invoke(cli, ["monitor", "--config", str(cfg_file), "--once"])
        assert result.exit_code == 0
        assert "2 traces queried" in result.output
        assert "2 sampled" in result.output

    def test_monitor_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["monitor", "--help"])
        assert result.exit_code == 0
        assert "--once" in result.output
        assert "--poll-interval" in result.output
