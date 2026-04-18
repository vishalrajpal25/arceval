"""End-to-end tests for the CLI validate command."""

import textwrap

from click.testing import CliRunner

from arceval.cli.main import cli


class TestCLIValidate:
    def test_valid_config(self, tmp_path):
        cfg_file = tmp_path / "arceval.yaml"
        cfg_file.write_text(textwrap.dedent("""\
            version: "1"
            project: "test"
            endpoint:
              type: http
              name: "Test Endpoint"
            backends:
              dev:
                type: file
                path: "./traces/"
            tiers:
              t1:
                name: "Must-Have"
                mode: always
            scorers:
              - name: latency
                type: builtin.latency
                tier: t1
        """))
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--config", str(cfg_file)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_missing_config(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--config", str(tmp_path / "missing.yaml")])
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_invalid_config(self, tmp_path):
        cfg_file = tmp_path / "arceval.yaml"
        cfg_file.write_text(textwrap.dedent("""\
            version: "1"
            project: "test"
            endpoint:
              type: invalid_type
        """))
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--config", str(cfg_file)])
        assert result.exit_code == 1

    def test_version_flag(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output
