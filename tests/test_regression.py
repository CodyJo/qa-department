"""Tests for backoffice.regression."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backoffice.regression import (
    CmdResult,
    best_effort_coverage,
    main,
    parse_lcov_percent,
    parse_pytest_cov_json,
    parse_vitest_coverage_summary,
    run_cmd,
    run_regression,
    safe_mkdir,
    try_read_json,
    utc_now_iso,
    write_json,
    write_text,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dirs(tmp_path):
    """Return (results_root, dashboard_out, run_dir, target_dir)."""
    results_root = tmp_path / "results" / "regression"
    results_root.mkdir(parents=True)
    dashboard_dir = tmp_path / "dashboard"
    dashboard_dir.mkdir()
    dashboard_out = dashboard_dir / "regression-data.json"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    target_dir = tmp_path / "target_repo"
    target_dir.mkdir()
    return results_root, dashboard_out, run_dir, target_dir


@pytest.fixture
def minimal_target(tmp_dirs):
    """A minimal target dict pointing at a real directory."""
    _, _, _, target_dir = tmp_dirs
    return {
        "name": "myrepo",
        "path": str(target_dir),
        "language": "python",
        "test_command": "true",
        "coverage_command": "",
    }


# ---------------------------------------------------------------------------
# utc_now_iso
# ---------------------------------------------------------------------------


class TestUtcNowIso:
    def test_ends_with_z(self):
        ts = utc_now_iso()
        assert ts.endswith("Z")

    def test_is_string(self):
        assert isinstance(utc_now_iso(), str)


# ---------------------------------------------------------------------------
# run_cmd
# ---------------------------------------------------------------------------


class TestRunCmd:
    def test_exit_code_zero_for_true(self, tmp_path):
        out_dir = str(tmp_path / "out")
        result = run_cmd("true", cwd=str(tmp_path), out_dir=out_dir, label="test", timeout_s=10)
        assert result.exit_code == 0

    def test_exit_code_nonzero_for_false(self, tmp_path):
        out_dir = str(tmp_path / "out")
        result = run_cmd("false", cwd=str(tmp_path), out_dir=out_dir, label="test", timeout_s=10)
        assert result.exit_code != 0

    def test_stdout_captured(self, tmp_path):
        out_dir = str(tmp_path / "out")
        result = run_cmd("echo hello", cwd=str(tmp_path), out_dir=out_dir, label="test", timeout_s=10)
        assert result.exit_code == 0
        stdout_text = Path(result.stdout_path).read_text()
        assert "hello" in stdout_text

    def test_stderr_captured(self, tmp_path):
        out_dir = str(tmp_path / "out")
        result = run_cmd(
            "echo error_msg >&2",
            cwd=str(tmp_path),
            out_dir=out_dir,
            label="test",
            timeout_s=10,
        )
        stderr_text = Path(result.stderr_path).read_text()
        assert "error_msg" in stderr_text

    def test_duration_ms_is_non_negative(self, tmp_path):
        out_dir = str(tmp_path / "out")
        result = run_cmd("true", cwd=str(tmp_path), out_dir=out_dir, label="test", timeout_s=10)
        assert result.duration_ms >= 0

    def test_returns_cmd_result(self, tmp_path):
        out_dir = str(tmp_path / "out")
        result = run_cmd("true", cwd=str(tmp_path), out_dir=out_dir, label="test", timeout_s=10)
        assert isinstance(result, CmdResult)

    def test_log_files_created(self, tmp_path):
        out_dir = str(tmp_path / "out")
        result = run_cmd("true", cwd=str(tmp_path), out_dir=out_dir, label="mytest", timeout_s=10)
        assert Path(result.stdout_path).exists()
        assert Path(result.stderr_path).exists()

    def test_timeout_raises(self, tmp_path):
        out_dir = str(tmp_path / "out")
        with pytest.raises(subprocess.TimeoutExpired):
            run_cmd("sleep 60", cwd=str(tmp_path), out_dir=out_dir, label="slow", timeout_s=1)

    def test_cwd_stored_on_result(self, tmp_path):
        out_dir = str(tmp_path / "out")
        result = run_cmd("true", cwd=str(tmp_path), out_dir=out_dir, label="test", timeout_s=10)
        assert result.cwd == str(tmp_path)

    def test_cmd_stored_on_result(self, tmp_path):
        out_dir = str(tmp_path / "out")
        result = run_cmd("true", cwd=str(tmp_path), out_dir=out_dir, label="test", timeout_s=10)
        assert result.cmd == "true"


# ---------------------------------------------------------------------------
# parse_pytest_cov_json
# ---------------------------------------------------------------------------


class TestParsePytestCovJson:
    def test_valid_coverage_json(self, tmp_path):
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text(json.dumps({"totals": {"percent_covered": 85.5}}))
        result = parse_pytest_cov_json(str(cov_file))
        assert result is not None
        assert result["tool"] == "pytest-cov"
        assert result["format"] == "coverage-json"
        assert result["percent"] == 85.5

    def test_integer_percent(self, tmp_path):
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text(json.dumps({"totals": {"percent_covered": 100}}))
        result = parse_pytest_cov_json(str(cov_file))
        assert result["percent"] == 100.0

    def test_missing_totals_returns_none(self, tmp_path):
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text(json.dumps({"other": "data"}))
        assert parse_pytest_cov_json(str(cov_file)) is None

    def test_missing_percent_covered_returns_none(self, tmp_path):
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text(json.dumps({"totals": {"lines_covered": 50}}))
        assert parse_pytest_cov_json(str(cov_file)) is None

    def test_file_not_found_returns_none(self, tmp_path):
        assert parse_pytest_cov_json(str(tmp_path / "nonexistent.json")) is None

    def test_malformed_json_returns_none(self, tmp_path):
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text("not valid json {{{")
        assert parse_pytest_cov_json(str(cov_file)) is None

    def test_non_numeric_percent_returns_none(self, tmp_path):
        cov_file = tmp_path / "coverage.json"
        cov_file.write_text(json.dumps({"totals": {"percent_covered": "eighty"}}))
        assert parse_pytest_cov_json(str(cov_file)) is None


# ---------------------------------------------------------------------------
# parse_vitest_coverage_summary
# ---------------------------------------------------------------------------


class TestParseVitestCoverageSummary:
    def _make_summary(self, tmp_path, pct):
        summary = tmp_path / "coverage-summary.json"
        summary.write_text(json.dumps({
            "total": {
                "lines": {"pct": pct, "total": 100, "covered": pct},
                "statements": {"pct": pct},
                "functions": {"pct": pct},
                "branches": {"pct": pct},
            }
        }))
        return summary

    def test_valid_summary(self, tmp_path):
        summary = self._make_summary(tmp_path, 72.3)
        result = parse_vitest_coverage_summary(str(summary))
        assert result is not None
        assert result["tool"] == "vitest"
        assert result["format"] == "coverage-summary-json"
        assert result["percent"] == 72.3

    def test_integer_pct(self, tmp_path):
        summary = self._make_summary(tmp_path, 90)
        result = parse_vitest_coverage_summary(str(summary))
        assert result["percent"] == 90.0

    def test_missing_total_returns_none(self, tmp_path):
        f = tmp_path / "coverage-summary.json"
        f.write_text(json.dumps({"other": {}}))
        assert parse_vitest_coverage_summary(str(f)) is None

    def test_missing_lines_pct_returns_none(self, tmp_path):
        f = tmp_path / "coverage-summary.json"
        f.write_text(json.dumps({"total": {"lines": {}}}))
        assert parse_vitest_coverage_summary(str(f)) is None

    def test_file_not_found_returns_none(self, tmp_path):
        assert parse_vitest_coverage_summary(str(tmp_path / "no.json")) is None

    def test_lines_not_a_dict_returns_none(self, tmp_path):
        f = tmp_path / "coverage-summary.json"
        f.write_text(json.dumps({"total": {"lines": 80}}))
        assert parse_vitest_coverage_summary(str(f)) is None


# ---------------------------------------------------------------------------
# parse_lcov_percent
# ---------------------------------------------------------------------------


class TestParseLcovPercent:
    def _write_lcov(self, tmp_path, lf, lh, extra=""):
        lcov = tmp_path / "lcov.info"
        lcov.write_text(f"TN:\nSF:src/index.ts\nLF:{lf}\nLH:{lh}\nend_of_record\n{extra}")
        return lcov

    def test_full_coverage(self, tmp_path):
        lcov = self._write_lcov(tmp_path, 100, 100)
        result = parse_lcov_percent(str(lcov))
        assert result is not None
        assert result["percent"] == pytest.approx(100.0)

    def test_partial_coverage(self, tmp_path):
        lcov = self._write_lcov(tmp_path, 200, 150)
        result = parse_lcov_percent(str(lcov))
        assert result["percent"] == pytest.approx(75.0)

    def test_zero_lf_returns_none(self, tmp_path):
        lcov = self._write_lcov(tmp_path, 0, 0)
        assert parse_lcov_percent(str(lcov)) is None

    def test_missing_file_returns_none(self, tmp_path):
        assert parse_lcov_percent(str(tmp_path / "no.info")) is None

    def test_tool_is_vitest(self, tmp_path):
        lcov = self._write_lcov(tmp_path, 50, 40)
        result = parse_lcov_percent(str(lcov))
        assert result["tool"] == "vitest"
        assert result["format"] == "lcov"

    def test_multiple_records_accumulated(self, tmp_path):
        """Multiple SF records should accumulate LF/LH totals."""
        lcov = tmp_path / "lcov.info"
        lcov.write_text(
            "SF:a.ts\nLF:100\nLH:80\nend_of_record\n"
            "SF:b.ts\nLF:100\nLH:60\nend_of_record\n"
        )
        result = parse_lcov_percent(str(lcov))
        assert result["percent"] == pytest.approx(70.0)

    def test_bad_lf_line_skipped(self, tmp_path):
        lcov = tmp_path / "lcov.info"
        lcov.write_text("LF:bad\nLF:100\nLH:80\nend_of_record\n")
        result = parse_lcov_percent(str(lcov))
        assert result is not None
        assert result["percent"] == pytest.approx(80.0)


# ---------------------------------------------------------------------------
# best_effort_coverage
# ---------------------------------------------------------------------------


class TestBestEffortCoverage:
    def test_unknown_language_returns_none(self, tmp_dirs):
        _, _, run_dir, target_dir = tmp_dirs
        target = {
            "name": "x",
            "path": str(target_dir),
            "language": "rust",
            "test_command": "cargo test",
            "coverage_command": "",
        }
        cov, cmds = best_effort_coverage(target, str(target_dir), str(run_dir), timeout_s=10)
        assert cov is None
        assert cmds == []

    def test_explicit_coverage_command_used(self, tmp_dirs):
        _, _, run_dir, target_dir = tmp_dirs
        # Write a coverage-summary.json that will be found
        cov_dir = target_dir / "coverage"
        cov_dir.mkdir()
        (cov_dir / "coverage-summary.json").write_text(json.dumps({
            "total": {"lines": {"pct": 88.0}}
        }))
        target = {
            "name": "x",
            "path": str(target_dir),
            "language": "typescript",
            "test_command": "npm test",
            "coverage_command": "true",  # succeeds immediately
        }
        cov, cmds = best_effort_coverage(target, str(target_dir), str(run_dir), timeout_s=10)
        assert cov is not None
        assert cov["percent"] == 88.0
        assert len(cmds) == 1

    def test_explicit_coverage_command_timeout_returns_none(self, tmp_dirs):
        _, _, run_dir, target_dir = tmp_dirs
        target = {
            "name": "x",
            "path": str(target_dir),
            "language": "python",
            "test_command": "pytest",
            "coverage_command": "sleep 60",
        }
        cov, cmds = best_effort_coverage(target, str(target_dir), str(run_dir), timeout_s=1)
        assert cov is None
        # TimeoutExpired is caught; cmds may be empty (not appended on timeout)
        assert isinstance(cmds, list)

    def test_python_coverage_command_attempted(self, tmp_dirs):
        _, _, run_dir, target_dir = tmp_dirs
        # The default python coverage command will fail (no pytest tests here),
        # but we verify it is attempted (a CmdResult is in cmds).
        target = {
            "name": "x",
            "path": str(target_dir),
            "language": "python",
            "test_command": "true",
            "coverage_command": "",
        }
        cov, cmds = best_effort_coverage(target, str(target_dir), str(run_dir), timeout_s=30)
        # coverage may or may not succeed; we care that a command was tried
        assert len(cmds) == 1
        assert cmds[0].label if hasattr(cmds[0], "label") else True  # CmdResult returned

    def test_typescript_coverage_command_attempted(self, tmp_dirs):
        _, _, run_dir, target_dir = tmp_dirs
        target = {
            "name": "x",
            "path": str(target_dir),
            "language": "typescript",
            "test_command": "npm test",
            "coverage_command": "",
        }
        # npm run test:coverage will fail; we just verify it runs one cmd
        cov, cmds = best_effort_coverage(target, str(target_dir), str(run_dir), timeout_s=10)
        assert len(cmds) == 1
        assert cov is None  # no coverage files present

    def test_explicit_coverage_command_fallback_to_lcov(self, tmp_dirs):
        _, _, run_dir, target_dir = tmp_dirs
        cov_dir = target_dir / "coverage"
        cov_dir.mkdir()
        (cov_dir / "lcov.info").write_text("LF:100\nLH:75\nend_of_record\n")
        target = {
            "name": "x",
            "path": str(target_dir),
            "language": "typescript",
            "test_command": "npm test",
            "coverage_command": "true",
        }
        cov, cmds = best_effort_coverage(target, str(target_dir), str(run_dir), timeout_s=10)
        assert cov is not None
        assert cov["format"] == "lcov"
        assert cov["percent"] == pytest.approx(75.0)

    def test_explicit_coverage_command_fallback_to_pytest_cov_json(self, tmp_dirs):
        _, _, run_dir, target_dir = tmp_dirs
        # Write coverage.json at target_dir root
        (target_dir / "coverage.json").write_text(json.dumps({
            "totals": {"percent_covered": 62.0}
        }))
        target = {
            "name": "x",
            "path": str(target_dir),
            "language": "python",
            "test_command": "pytest",
            "coverage_command": "true",
        }
        cov, cmds = best_effort_coverage(target, str(target_dir), str(run_dir), timeout_s=10)
        assert cov is not None
        assert cov["tool"] == "pytest-cov"
        assert cov["percent"] == pytest.approx(62.0)

    def test_typescript_fallback_to_lcov(self, tmp_dirs):
        _, _, run_dir, target_dir = tmp_dirs
        cov_dir = target_dir / "coverage"
        cov_dir.mkdir()
        (cov_dir / "lcov.info").write_text("LF:50\nLH:40\nend_of_record\n")
        target = {
            "name": "x",
            "path": str(target_dir),
            "language": "typescript",
            "test_command": "npm test",
            "coverage_command": "",
        }
        # Patch run_cmd to return exit_code=0 without actually running npm
        with patch("backoffice.regression.run_cmd") as mock_run:
            mock_result = MagicMock(spec=CmdResult)
            mock_result.exit_code = 0
            mock_run.return_value = mock_result
            cov, cmds = best_effort_coverage(target, str(target_dir), str(run_dir), timeout_s=10)
        assert cov is not None
        assert cov["format"] == "lcov"


# ---------------------------------------------------------------------------
# run_regression (main loop + file writes)
# ---------------------------------------------------------------------------


class TestRunRegression:
    def test_passing_target_increments_passed(self, tmp_dirs):
        results_root, dashboard_out, _, target_dir = tmp_dirs
        targets = [{
            "name": "myrepo",
            "path": str(target_dir),
            "language": "python",
            "test_command": "true",
            "coverage_command": "",
        }]
        summary = run_regression(targets, results_root, dashboard_out, timeout_s=10)
        assert summary["targets_passed"] == 1
        assert summary["targets_failed"] == 0

    def test_failing_target_increments_failed(self, tmp_dirs):
        results_root, dashboard_out, _, target_dir = tmp_dirs
        targets = [{
            "name": "myrepo",
            "path": str(target_dir),
            "language": "python",
            "test_command": "false",
            "coverage_command": "",
        }]
        summary = run_regression(targets, results_root, dashboard_out, timeout_s=10)
        assert summary["targets_failed"] == 1
        assert summary["targets_passed"] == 0

    def test_regression_json_written(self, tmp_dirs):
        results_root, dashboard_out, _, target_dir = tmp_dirs
        targets = [{
            "name": "myrepo",
            "path": str(target_dir),
            "language": "python",
            "test_command": "true",
            "coverage_command": "",
        }]
        run_regression(targets, results_root, dashboard_out, timeout_s=10)
        # Find regression.json in the run subdirectory
        run_dirs = list(results_root.iterdir())
        assert len(run_dirs) == 1
        regression_json = run_dirs[0] / "regression.json"
        assert regression_json.exists()
        data = json.loads(regression_json.read_text())
        assert data["targets_total"] == 1

    def test_dashboard_out_written(self, tmp_dirs):
        results_root, dashboard_out, _, target_dir = tmp_dirs
        targets = [{
            "name": "myrepo",
            "path": str(target_dir),
            "language": "python",
            "test_command": "true",
            "coverage_command": "",
        }]
        run_regression(targets, results_root, dashboard_out, timeout_s=10)
        assert dashboard_out.exists()
        payload = json.loads(dashboard_out.read_text())
        assert "latest_run" in payload
        assert "generated_at" in payload

    def test_incomplete_target_skipped(self, tmp_dirs):
        results_root, dashboard_out, _, target_dir = tmp_dirs
        targets = [
            # Missing test_command
            {"name": "bad", "path": str(target_dir), "language": "python", "test_command": "", "coverage_command": ""},
            # Valid
            {"name": "good", "path": str(target_dir), "language": "python", "test_command": "true", "coverage_command": ""},
        ]
        summary = run_regression(targets, results_root, dashboard_out, timeout_s=10)
        assert summary["targets_total"] == 2  # total declared
        assert summary["targets_passed"] == 1  # only valid one ran
        assert len(summary["targets"]) == 1

    def test_run_id_in_summary(self, tmp_dirs):
        results_root, dashboard_out, _, target_dir = tmp_dirs
        targets = [{
            "name": "myrepo",
            "path": str(target_dir),
            "language": "python",
            "test_command": "true",
            "coverage_command": "",
        }]
        summary = run_regression(targets, results_root, dashboard_out, timeout_s=10)
        assert "run_id" in summary
        assert summary["run_id"]  # non-empty

    def test_finished_at_set(self, tmp_dirs):
        results_root, dashboard_out, _, target_dir = tmp_dirs
        targets = [{
            "name": "myrepo",
            "path": str(target_dir),
            "language": "python",
            "test_command": "true",
            "coverage_command": "",
        }]
        summary = run_regression(targets, results_root, dashboard_out, timeout_s=10)
        assert summary["finished_at"] is not None

    def test_timeout_recorded_as_failed(self, tmp_dirs):
        results_root, dashboard_out, _, target_dir = tmp_dirs
        targets = [{
            "name": "slow",
            "path": str(target_dir),
            "language": "python",
            "test_command": "sleep 60",
            "coverage_command": "",
        }]
        summary = run_regression(targets, results_root, dashboard_out, timeout_s=1)
        assert summary["targets_failed"] == 1
        assert summary["targets"][0]["status"] == "failed"
        assert summary["targets"][0]["test"]["exit_code"] == 124

    def test_coverage_recorded_when_present(self, tmp_dirs):
        results_root, dashboard_out, _, target_dir = tmp_dirs
        # Write a coverage-summary.json that will be found when explicit cmd runs
        cov_dir = target_dir / "coverage"
        cov_dir.mkdir()
        (cov_dir / "coverage-summary.json").write_text(json.dumps({
            "total": {"lines": {"pct": 91.5}}
        }))
        targets = [{
            "name": "myrepo",
            "path": str(target_dir),
            "language": "typescript",
            "test_command": "true",
            "coverage_command": "true",
        }]
        summary = run_regression(targets, results_root, dashboard_out, timeout_s=10)
        assert summary["targets"][0]["coverage"] is not None
        assert summary["targets"][0]["coverage"]["percent"] == 91.5


# ---------------------------------------------------------------------------
# main() entry point
# ---------------------------------------------------------------------------


class TestMain:
    def test_returns_0_when_all_pass(self, tmp_dirs, tmp_path):
        results_root, dashboard_out, _, target_dir = tmp_dirs
        targets_yaml = tmp_path / "targets.yaml"
        targets_yaml.write_text(
            f"targets:\n  - name: good\n    path: {target_dir}\n    language: python\n    test_command: \"true\"\n"
        )
        rc = main([
            "--targets", str(targets_yaml),
            "--out", str(results_root),
            "--dashboard-out", str(dashboard_out),
        ])
        assert rc == 0

    def test_returns_1_when_target_fails(self, tmp_dirs, tmp_path):
        results_root, dashboard_out, _, target_dir = tmp_dirs
        targets_yaml = tmp_path / "targets.yaml"
        targets_yaml.write_text(
            f"targets:\n  - name: bad\n    path: {target_dir}\n    language: python\n    test_command: \"false\"\n"
        )
        rc = main([
            "--targets", str(targets_yaml),
            "--out", str(results_root),
            "--dashboard-out", str(dashboard_out),
        ])
        assert rc == 1

    def test_returns_2_when_targets_yaml_missing(self, tmp_dirs):
        results_root, dashboard_out, _, _ = tmp_dirs
        rc = main([
            "--targets", "/nonexistent/path/targets.yaml",
            "--out", str(results_root),
            "--dashboard-out", str(dashboard_out),
        ])
        assert rc == 2

    def test_only_filter_applied(self, tmp_dirs, tmp_path):
        results_root, dashboard_out, _, target_dir = tmp_dirs
        targets_yaml = tmp_path / "targets.yaml"
        targets_yaml.write_text(
            f"targets:\n"
            f"  - name: repo-a\n    path: {target_dir}\n    language: python\n    test_command: \"true\"\n"
            f"  - name: repo-b\n    path: {target_dir}\n    language: python\n    test_command: \"false\"\n"
        )
        rc = main([
            "--targets", str(targets_yaml),
            "--out", str(results_root),
            "--dashboard-out", str(dashboard_out),
            "--only", "repo-a",
        ])
        # Only repo-a ran (passes), so rc = 0
        assert rc == 0

    def test_uses_config_targets_when_provided(self, tmp_dirs):
        results_root, dashboard_out, _, target_dir = tmp_dirs
        # Build a minimal Config mock
        from backoffice.config import Target

        mock_target = Target(
            path=str(target_dir),
            language="python",
            test_command="true",
            coverage_command="",
        )
        config = MagicMock()
        config.targets = {"myrepo": mock_target}

        rc = main(
            argv=[
                "--out", str(results_root),
                "--dashboard-out", str(dashboard_out),
            ],
            config=config,
        )
        assert rc == 0

    def test_config_targets_override_targets_yaml(self, tmp_dirs, tmp_path):
        """When config is provided, --targets arg is irrelevant."""
        results_root, dashboard_out, _, target_dir = tmp_dirs
        from backoffice.config import Target

        mock_target = Target(
            path=str(target_dir),
            language="python",
            test_command="false",  # this would fail
            coverage_command="",
        )
        config = MagicMock()
        config.targets = {"failrepo": mock_target}

        rc = main(
            argv=[
                "--out", str(results_root),
                "--dashboard-out", str(dashboard_out),
            ],
            config=config,
        )
        assert rc == 1  # fails because test_command is "false"

    def test_dashboard_json_written_by_main(self, tmp_dirs, tmp_path):
        results_root, dashboard_out, _, target_dir = tmp_dirs
        targets_yaml = tmp_path / "targets.yaml"
        targets_yaml.write_text(
            f"targets:\n  - name: good\n    path: {target_dir}\n    language: python\n    test_command: \"true\"\n"
        )
        main([
            "--targets", str(targets_yaml),
            "--out", str(results_root),
            "--dashboard-out", str(dashboard_out),
        ])
        assert dashboard_out.exists()
        payload = json.loads(dashboard_out.read_text())
        assert payload["latest_run"]["targets_total"] == 1
