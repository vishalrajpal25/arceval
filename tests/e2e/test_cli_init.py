"""End-to-end tests for the CLI init command."""

import os

from click.testing import CliRunner

from arceval.cli.main import cli


class TestCLIInit:
    def test_init_http(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init", "--type", "http", "--project", "myapp"])
            assert result.exit_code == 0
            assert "Created arceval.yaml" in result.output
            assert os.path.exists("arceval.yaml")
            assert os.path.isdir("golden_sets")
            assert os.path.isdir("eval-reports")
            assert os.path.isdir("schemas")

            with open("arceval.yaml") as f:
                content = f.read()
            assert "myapp" in content
            assert "type: http" in content

    def test_init_mcp(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init", "--type", "mcp", "--project", "findata"])
            assert result.exit_code == 0
            with open("arceval.yaml") as f:
                content = f.read()
            assert "type: mcp" in content
            assert "findata" in content

    def test_init_rag(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init", "--type", "rag"])
            assert result.exit_code == 0
            assert os.path.exists("arceval.yaml")

    def test_init_already_exists(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create first
            runner.invoke(cli, ["init", "--type", "http"])
            # Try again
            result = runner.invoke(cli, ["init", "--type", "http"])
            assert result.exit_code == 1
            assert "already exists" in result.output

    def test_init_validates(self, tmp_path):
        """Generated config should pass validation."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["init", "--type", "mcp", "--project", "test"])
            result = runner.invoke(cli, ["validate"])
            assert result.exit_code == 0
            assert "valid" in result.output.lower()
