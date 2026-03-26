"""Tests for backoffice.__main__ dispatch."""
import types
import subprocess
import sys

from backoffice import __main__ as backoffice_main


def test_help_shows_available_commands():
    result = subprocess.run(
        [sys.executable, "-m", "backoffice", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "sync" in result.stdout
    assert "config" in result.stdout
    assert "audit" in result.stdout


def test_unknown_command_exits_nonzero():
    result = subprocess.run(
        [sys.executable, "-m", "backoffice", "nonexistent"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0


def test_audit_all_dispatches_to_workflow_run_all(monkeypatch):
    captured = {}

    def fake_workflow_main(argv):
        captured["argv"] = argv
        return 0

    monkeypatch.setitem(
        sys.modules,
        "backoffice.workflow",
        types.SimpleNamespace(main=fake_workflow_main),
    )

    result = backoffice_main.main(["audit-all", "--targets", "fuel,selah", "--departments", "qa,product"])
    assert result == 0
    assert captured["argv"] == ["run-all", "--targets", "fuel,selah", "--departments", "qa,product"]
