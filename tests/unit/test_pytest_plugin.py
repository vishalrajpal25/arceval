"""Tests for the pytest plugin."""

import textwrap

from arceval.testing.pytest_plugin import ArcEvalRunner


class TestArcEvalRunner:
    def test_run_with_config(self, tmp_path):
        gs_dir = tmp_path / "golden_sets"
        gs_dir.mkdir()
        (gs_dir / "sample.jsonl").write_text(
            '{"input": {"q": "test"}, "expected_output": "ok", "metadata": {"latency_ms": 100}}\n'
        )

        cfg_file = tmp_path / "arceval.yaml"
        cfg_file.write_text(textwrap.dedent(f"""\
            version: "1"
            project: "pytest-test"
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
                  threshold_ms: 2000
                  percentile: 95
            golden_sets:
              path: "{gs_dir}"
              format: jsonl
              sets:
                - name: sample
                  file: "sample.jsonl"
        """))

        runner = ArcEvalRunner(config_path=str(cfg_file))
        result = runner.test()
        assert result.all_passed is True
        assert result.traces_scored == 1

    def test_run_with_tier_filter(self, tmp_path):
        gs_dir = tmp_path / "golden_sets"
        gs_dir.mkdir()
        (gs_dir / "sample.jsonl").write_text(
            '{"input": {"q": "test"}, "expected_output": "ok", "metadata": {"latency_ms": 100}}\n'
        )

        cfg_file = tmp_path / "arceval.yaml"
        cfg_file.write_text(textwrap.dedent(f"""\
            version: "1"
            project: "pytest-test"
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
              t2:
                name: "Operational"
                mode: on_golden_set
            scorers:
              - name: latency
                type: builtin.latency
                tier: t1
                config:
                  threshold_ms: 2000
                  percentile: 95
              - name: error_rate
                type: builtin.error_rate
                tier: t2
                config:
                  threshold_pct: 1.0
            golden_sets:
              path: "{gs_dir}"
              format: jsonl
              sets:
                - name: sample
                  file: "sample.jsonl"
        """))

        runner = ArcEvalRunner(config_path=str(cfg_file), tiers=["t1"])
        result = runner.test()
        # Only t1 scorers should run
        assert all(r.tier.value == "t1" for r in result.results)
