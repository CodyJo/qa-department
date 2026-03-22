# DX Overhaul Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate scattered Python scripts into a unified `backoffice/` package with single config, structured logging, provider-agnostic sync, and consistent error handling.

**Architecture:** All Python scripts move into a `backoffice/` package imported via `python -m backoffice <command>`. Config merges into one YAML file parsed into frozen dataclasses. Storage/CDN operations go through abstract provider interfaces. Logging uses stdlib `logging` to stderr in all modules.

**Tech Stack:** Python 3.12, PyYAML, boto3 (optional, for AWS provider), stdlib logging, dataclasses, argparse

**Spec:** `docs/superpowers/specs/2026-03-22-dx-overhaul-design.md`

**Important notes:**
- Agent shell scripts (`agents/*.sh`) call `scripts/parse-config.py` to read target fields. Since the spec says agent scripts are untouched, `parse-config.py` survives as a thin wrapper delegating to `backoffice.config`. It is NOT deleted in Phase 3.
- `backoffice/cli.py` is absorbed into `backoffice/__main__.py` — the __main__ dispatcher handles all subcommand routing, making a separate cli.py unnecessary.
- Provider `upload_file` receives a `bucket` parameter (part of the interface) since multi-bucket deployments are the norm.
- A `pyproject.toml` with `[tool.pytest]` config is created in Task 1 to ensure pytest can find the package.

---

## File Structure

### New Files to Create

```
backoffice/
  __init__.py              — Package marker, exports __version__
  __main__.py              — Entry point dispatcher: python -m backoffice <cmd>
  config.py                — Unified config loader + frozen dataclass hierarchy
  log_config.py            — setup_logging() + JSONFormatter
  aggregate.py             — Port from scripts/aggregate-results.py (478 LOC)
  delivery.py              — Port from scripts/generate-delivery-data.py (426 LOC)
  tasks.py                 — Port from scripts/task-queue.py (528 LOC)
  regression.py            — Port from scripts/regression-runner.py (362 LOC)
  setup.py                 — Port from scripts/backoffice_setup.py (324 LOC)
  server.py                — Port from scripts/dashboard-server.py (384 LOC)
  api_server.py            — Port from scripts/api-server.py (396 LOC)
  workflow.py              — Port from scripts/local_audit_workflow.py (439 LOC)
  scaffolding.py           — Port from scripts/scaffold-github-workflows.py (99 LOC)
  sync/
    __init__.py            — Package marker
    engine.py              — SyncEngine class (replaces sync-dashboard.sh + quick-sync.sh)
    manifest.py            — DASHBOARD_FILES, DEPT_DATA_MAP, etc. constants
    providers/
      __init__.py          — get_providers() factory
      base.py              — StorageProvider + CDNProvider ABCs
      aws.py               — S3 + CloudFront implementation

pyproject.toml             — pytest config, package metadata

tests/
  __init__.py
  conftest.py              — Shared fixtures
  test_config.py           — Config loading, validation, shell-export
  test_log_config.py       — Logging setup, JSON formatter
  test_aggregate.py        — Aggregation logic
  test_delivery.py         — Delivery data generation
  test_tasks.py            — Task queue operations
  test_regression.py       — Regression runner
  test_setup.py            — Setup wizard
  test_scaffolding.py      — Workflow scaffolding
  test_sync_engine.py      — Sync engine orchestration
  test_sync_manifest.py    — File manifest constants
  test_sync_providers.py   — Provider abstraction + AWS impl
  test_workflow.py         — Local audit workflow
  test_servers.py          — Dashboard + API server

config/
  backoffice.yaml          — NEW unified config (replaces 4 files)
  backoffice.example.yaml  — NEW example config
```

### Files to Modify

```
Makefile                   — Update targets to use python -m backoffice
.github/workflows/ci.yml  — Update test paths and validation
scripts/run-agent.sh       — Use eval $(python -m backoffice config shell-export)
scripts/sync-dashboard.sh  — Becomes 3-line wrapper
scripts/quick-sync.sh      — Becomes 3-line wrapper
```

### Files to Delete (Phase 3)

```
scripts/aggregate-results.py
scripts/generate-delivery-data.py
scripts/task-queue.py
scripts/regression-runner.py
scripts/backoffice_setup.py
scripts/dashboard-server.py
scripts/api-server.py
scripts/backoffice-cli.py
scripts/local_audit_workflow.py
scripts/scaffold-github-workflows.py
config/qa-config.yaml
config/api-config.yaml
config/agent-runner.env
```

### Files to Keep as Wrappers (NOT deleted)

```
scripts/parse-config.py    — Agent scripts (agents/*.sh) call this; becomes thin wrapper
                             delegating to backoffice.config for target field lookups.
                             Preserves the null-delimited output interface.
                             Reads from backoffice.yaml (not targets.yaml).
```

---

## Chunk 1: Foundation — Config, Logging, Package Skeleton

### Task 1: Package skeleton and log_config

**Files:**
- Create: `backoffice/__init__.py`
- Create: `backoffice/log_config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_log_config.py`

- [ ] **Step 1: Create package skeleton and pytest config**

```python
# backoffice/__init__.py
"""Back Office — unified Python package."""
__version__ = "1.0.0"
```

```toml
# pyproject.toml
[project]
name = "backoffice"
version = "1.0.0"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.coverage.run]
source = ["backoffice"]

[tool.coverage.report]
show_missing = true
```

```python
# tests/conftest.py
"""Shared test fixtures."""
```

- [ ] **Step 2: Write failing test for setup_logging**

```python
# tests/test_log_config.py
"""Tests for backoffice.log_config."""
import logging

from backoffice.log_config import setup_logging


def test_setup_logging_configures_backoffice_logger():
    setup_logging()
    logger = logging.getLogger("backoffice")
    assert logger.level == logging.INFO
    assert len(logger.handlers) >= 1


def test_setup_logging_verbose_sets_debug():
    setup_logging(verbose=True)
    logger = logging.getLogger("backoffice")
    assert logger.level == logging.DEBUG


def test_setup_logging_json_mode():
    setup_logging(json_output=True)
    logger = logging.getLogger("backoffice")
    handler = logger.handlers[-1]
    # JSONFormatter should be set
    assert "JSONFormatter" in type(handler.formatter).__name__


def test_logger_outputs_to_stderr(capsys):
    setup_logging()
    logger = logging.getLogger("backoffice.test")
    logger.info("test message")
    captured = capsys.readouterr()
    assert captured.out == ""  # nothing on stdout
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_log_config.py -v`
Expected: FAIL (ImportError — module doesn't exist yet)

- [ ] **Step 4: Implement log_config.py**

```python
# backoffice/log_config.py
"""Structured logging configuration for the backoffice package.

All log output goes to stderr. Stdout is reserved for data output
(JSON, shell-export) so pipes and redirects work cleanly.
"""
import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def setup_logging(*, verbose: bool = False, json_output: bool = False) -> None:
    """Configure the backoffice logger. Call once at entry point."""
    root = logging.getLogger("backoffice")

    # Remove existing handlers to avoid duplicates on repeated calls
    root.handlers.clear()

    level = logging.DEBUG if verbose else logging.INFO
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))

    root.addHandler(handler)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_log_config.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 6: Commit**

```bash
git add backoffice/__init__.py backoffice/log_config.py tests/__init__.py tests/conftest.py tests/test_log_config.py pyproject.toml
git commit -m "feat: add backoffice package skeleton and structured logging"
```

---

### Task 2: Unified config loader

**Files:**
- Create: `backoffice/config.py`
- Create: `tests/test_config.py`
- Create: `config/backoffice.yaml`
- Create: `config/backoffice.example.yaml`

- [ ] **Step 1: Write failing tests for config dataclasses and loading**

```python
# tests/test_config.py
"""Tests for backoffice.config."""
import os
import textwrap
from pathlib import Path

import pytest

from backoffice.config import (
    Config,
    ConfigError,
    Target,
    load_config,
)


@pytest.fixture
def minimal_config(tmp_path):
    """Write a minimal valid config file and return its path."""
    cfg = tmp_path / "backoffice.yaml"
    cfg.write_text(textwrap.dedent("""\
        runner:
          command: "claude --model haiku"
          mode: claude-print
        api:
          port: 8070
          api_key: ""
          allowed_origins: []
        deploy:
          provider: aws
          aws:
            region: us-west-2
            dashboard_targets: []
        scan:
          max_findings: 200
        fix:
          auto_commit: true
        notifications:
          sync_to_s3: true
        targets:
          demo:
            path: /tmp/demo
            language: python
            default_departments: [qa]
    """))
    return cfg


def test_load_config_returns_frozen_config(minimal_config):
    cfg = load_config(minimal_config)
    assert isinstance(cfg, Config)
    assert cfg.runner.command == "claude --model haiku"
    assert cfg.runner.mode == "claude-print"


def test_target_has_defaults(minimal_config):
    cfg = load_config(minimal_config)
    t = cfg.targets["demo"]
    assert isinstance(t, Target)
    assert t.lint_command == ""
    assert t.deploy_command == ""
    assert t.context == ""


def test_config_is_frozen(minimal_config):
    cfg = load_config(minimal_config)
    with pytest.raises(AttributeError):
        cfg.runner = None  # type: ignore


def test_missing_config_raises():
    with pytest.raises(ConfigError, match="Config not found"):
        load_config(Path("/nonexistent/backoffice.yaml"))


def test_malformed_yaml_raises(tmp_path):
    bad = tmp_path / "backoffice.yaml"
    bad.write_text(": : : not valid yaml [")
    with pytest.raises(ConfigError, match="malformed"):
        load_config(bad)


def test_missing_required_field_raises(tmp_path):
    cfg = tmp_path / "backoffice.yaml"
    cfg.write_text("runner:\n  command: claude\n")
    with pytest.raises(ConfigError, match="missing"):
        load_config(cfg)


def test_nonexistent_target_path_warns(minimal_config, caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="backoffice"):
        load_config(minimal_config)
    assert any("/tmp/demo" in r.message for r in caplog.records)


def test_back_office_root_override(minimal_config, monkeypatch):
    monkeypatch.setenv("BACK_OFFICE_ROOT", "/custom/root")
    cfg = load_config(minimal_config)
    assert cfg.root == Path("/custom/root")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Write config.py with dataclass hierarchy and loader**

```python
# backoffice/config.py
"""Unified configuration loader for the backoffice package.

Loads config/backoffice.yaml into a frozen dataclass hierarchy.
Replaces: config/targets.yaml, config/qa-config.yaml,
          config/api-config.yaml, config/agent-runner.env
"""
from __future__ import annotations

import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when config is missing, malformed, or incomplete."""


# ── Dataclass hierarchy ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class RunnerConfig:
    command: str = "claude"
    mode: str = "claude-print"


@dataclass(frozen=True)
class ApiConfig:
    port: int = 8070
    api_key: str = ""
    allowed_origins: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DashboardTarget:
    bucket: str = ""
    base_path: str = ""
    distribution_id: str = ""
    subdomain: str = ""
    filter_repo: str | None = None
    allow_public_read: bool = False


@dataclass(frozen=True)
class AWSConfig:
    region: str = "us-east-1"
    dashboard_targets: list[DashboardTarget] = field(default_factory=list)


@dataclass(frozen=True)
class DeployConfig:
    provider: str = "aws"
    aws: AWSConfig = field(default_factory=AWSConfig)


@dataclass(frozen=True)
class ScanConfig:
    run_linter: bool = True
    run_tests: bool = True
    security_audit: bool = True
    performance_review: bool = True
    code_quality: bool = True
    min_severity: str = "low"
    max_findings: int = 200
    exclude_patterns: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FixConfig:
    auto_fix_severity: str = "high"
    run_tests_after_fix: bool = True
    run_linter_after_fix: bool = True
    max_parallel_fixes: int = 4
    auto_commit: bool = True
    auto_push: bool = False


@dataclass(frozen=True)
class NotificationsConfig:
    sync_to_s3: bool = True


@dataclass(frozen=True)
class Target:
    path: str = ""
    language: str = ""
    default_departments: list[str] = field(default_factory=list)
    lint_command: str = ""
    test_command: str = ""
    coverage_command: str = ""
    deploy_command: str = ""
    context: str = ""


@dataclass(frozen=True)
class Config:
    root: Path = field(default_factory=lambda: Path.cwd())
    runner: RunnerConfig = field(default_factory=RunnerConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    deploy: DeployConfig = field(default_factory=DeployConfig)
    scan: ScanConfig = field(default_factory=ScanConfig)
    fix: FixConfig = field(default_factory=FixConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    targets: dict[str, Target] = field(default_factory=dict)


# ── Loader ───────────────────────────────────────────────────────────────────

REQUIRED_SECTIONS = ("runner", "deploy", "targets")


def _build_targets(raw: dict) -> dict[str, Target]:
    """Parse targets section into dict of Target dataclasses."""
    targets = {}
    for name, data in (raw or {}).items():
        if not isinstance(data, dict):
            continue
        deps = data.get("default_departments", [])
        if isinstance(deps, str):
            deps = [d.strip() for d in deps.split(",")]
        targets[name] = Target(
            path=str(data.get("path", "")),
            language=str(data.get("language", "")),
            default_departments=deps,
            lint_command=str(data.get("lint_command", "")),
            test_command=str(data.get("test_command", "")),
            coverage_command=str(data.get("coverage_command", "")),
            deploy_command=str(data.get("deploy_command", "")),
            context=str(data.get("context", "")),
        )
    return targets


def _build_dashboard_targets(raw: list | None) -> list[DashboardTarget]:
    """Parse dashboard_targets list into DashboardTarget dataclasses."""
    if not raw:
        return []
    return [
        DashboardTarget(
            bucket=str(t.get("bucket", "")),
            base_path=str(t.get("base_path", "")),
            distribution_id=str(t.get("distribution_id", "")),
            subdomain=str(t.get("subdomain", "")),
            filter_repo=t.get("filter_repo"),
            allow_public_read=bool(t.get("allow_public_read", False)),
        )
        for t in raw
        if isinstance(t, dict)
    ]


def load_config(path: Path | None = None) -> Config:
    """Load and validate config from YAML file.

    Args:
        path: Explicit path to config file. If None, uses
              <project_root>/config/backoffice.yaml.

    Returns:
        Frozen Config dataclass.

    Raises:
        ConfigError: If file is missing, malformed, or missing required fields.
    """
    if path is None:
        root = Path(os.environ.get("BACK_OFFICE_ROOT", Path(__file__).resolve().parents[1]))
        path = root / "config" / "backoffice.yaml"

    if not path.exists():
        raise ConfigError(
            f"Config not found at {path} — run 'python -m backoffice setup' to create one"
        )

    try:
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Config at {path} is malformed YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"Config at {path} is malformed — expected a YAML mapping")

    # Check required sections
    missing = [s for s in REQUIRED_SECTIONS if s not in raw]
    if missing:
        raise ConfigError(
            f"Config at {path} is missing required sections: {', '.join(missing)}"
        )

    # Build config tree
    runner_raw = raw.get("runner", {}) or {}
    api_raw = raw.get("api", {}) or {}
    deploy_raw = raw.get("deploy", {}) or {}
    aws_raw = deploy_raw.get("aws", {}) or {}
    scan_raw = raw.get("scan", {}) or {}
    fix_raw = raw.get("fix", {}) or {}
    notif_raw = raw.get("notifications", {}) or {}

    root = Path(os.environ.get(
        "BACK_OFFICE_ROOT",
        str(path.resolve().parents[1]),
    ))

    targets = _build_targets(raw.get("targets"))

    # Warn about nonexistent target paths
    for name, target in targets.items():
        if target.path and not Path(target.path).exists():
            logger.warning("Target '%s' path does not exist: %s", name, target.path)

    return Config(
        root=root,
        runner=RunnerConfig(
            command=str(runner_raw.get("command", "claude")),
            mode=str(runner_raw.get("mode", "claude-print")),
        ),
        api=ApiConfig(
            port=int(api_raw.get("port", 8070)),
            api_key=str(api_raw.get("api_key", "")),
            allowed_origins=list(api_raw.get("allowed_origins", [])),
        ),
        deploy=DeployConfig(
            provider=str(deploy_raw.get("provider", "aws")),
            aws=AWSConfig(
                region=str(aws_raw.get("region", "us-east-1")),
                dashboard_targets=_build_dashboard_targets(
                    aws_raw.get("dashboard_targets")
                ),
            ),
        ),
        scan=ScanConfig(
            run_linter=bool(scan_raw.get("run_linter", True)),
            run_tests=bool(scan_raw.get("run_tests", True)),
            security_audit=bool(scan_raw.get("security_audit", True)),
            performance_review=bool(scan_raw.get("performance_review", True)),
            code_quality=bool(scan_raw.get("code_quality", True)),
            min_severity=str(scan_raw.get("min_severity", "low")),
            max_findings=int(scan_raw.get("max_findings", 200)),
            exclude_patterns=list(scan_raw.get("exclude_patterns", [])),
        ),
        fix=FixConfig(
            auto_fix_severity=str(fix_raw.get("auto_fix_severity", "high")),
            run_tests_after_fix=bool(fix_raw.get("run_tests_after_fix", True)),
            run_linter_after_fix=bool(fix_raw.get("run_linter_after_fix", True)),
            max_parallel_fixes=int(fix_raw.get("max_parallel_fixes", 4)),
            auto_commit=bool(fix_raw.get("auto_commit", True)),
            auto_push=bool(fix_raw.get("auto_push", False)),
        ),
        notifications=NotificationsConfig(
            sync_to_s3=bool(notif_raw.get("sync_to_s3", True)),
        ),
        targets=targets,
    )


# ── Shell export ─────────────────────────────────────────────────────────────

_SHELL_UNSAFE = re.compile(r'[;|&`$(){}!\\\n\r]')


def is_shell_safe(value: str) -> bool:
    """Reject values containing shell metacharacters."""
    if not value:
        return True
    return not _SHELL_UNSAFE.search(value)


def shell_export(config: Config, target_name: str | None = None,
                 fields: list[str] | None = None) -> str:
    """Generate shell variable assignments from config.

    Used by run-agent.sh:
        eval $(python -m backoffice config shell-export)

    When target_name and fields are provided, outputs null-delimited
    values (replacing scripts/parse-config.py).
    """
    if target_name and fields:
        # Null-delimited field output for backward compat with agent scripts
        target = config.targets.get(target_name)
        if not target:
            return "\0".join([""] * len(fields))
        values = []
        for f in fields:
            raw = getattr(target, f, "")
            val = str(raw) if raw else ""
            if not is_shell_safe(val):
                logger.warning("Rejected unsafe config value for field %s: %r", f, val)
                val = ""
            values.append(val)
        return "\0".join(values)

    # Default: shell variable assignments for runner config
    lines = [
        f'BACK_OFFICE_AGENT_RUNNER="{config.runner.command}"',
        f'BACK_OFFICE_AGENT_MODE="{config.runner.mode}"',
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (all 8 tests)

- [ ] **Step 5: Write the unified config file**

Create `config/backoffice.yaml` by merging the existing config files. Port all values from `config/targets.yaml`, `config/qa-config.yaml`, `config/api-config.yaml`, and `config/agent-runner.env` into the schema defined in the spec (Section 2). Use the field name mapping table for renames. Convert targets from list format to dict-keyed format.

Also create `config/backoffice.example.yaml` with placeholder values.

- [ ] **Step 6: Write tests for shell_export**

```python
# Add to tests/test_config.py

def test_shell_export_runner_vars(minimal_config):
    cfg = load_config(minimal_config)
    output = shell_export(cfg)
    assert 'BACK_OFFICE_AGENT_RUNNER="claude --model haiku"' in output
    assert 'BACK_OFFICE_AGENT_MODE="claude-print"' in output


def test_shell_export_target_fields(minimal_config):
    cfg = load_config(minimal_config)
    output = shell_export(cfg, target_name="demo", fields=["path", "language"])
    parts = output.split("\0")
    assert parts[0] == "/tmp/demo"
    assert parts[1] == "python"


def test_shell_export_rejects_unsafe_values(tmp_path):
    """Config values with shell metacharacters are sanitized to empty."""
    from backoffice.config import is_shell_safe
    assert is_shell_safe("/tmp/demo") is True
    assert is_shell_safe("echo $(whoami)") is False
    assert is_shell_safe("safe-value") is True
    assert is_shell_safe("rm; cat /etc/passwd") is False


def test_shell_export_missing_target(minimal_config):
    cfg = load_config(minimal_config)
    output = shell_export(cfg, target_name="nonexistent", fields=["path"])
    assert output == ""
```

- [ ] **Step 7: Run all config tests**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backoffice/config.py tests/test_config.py config/backoffice.yaml config/backoffice.example.yaml
git commit -m "feat: add unified config loader with frozen dataclasses and shell-export"
```

---

### Task 3: Entry point dispatcher

**Files:**
- Create: `backoffice/__main__.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write failing test for __main__.py dispatch**

```python
# tests/test_main.py
"""Tests for backoffice.__main__ dispatch."""
import subprocess
import sys


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_main.py -v`
Expected: FAIL

- [ ] **Step 3: Implement __main__.py**

```python
# backoffice/__main__.py
"""Entry point: python -m backoffice <command>

Dispatches to subcommand modules. Each module exposes a main(argv) function.
"""
from __future__ import annotations

import argparse
import sys

from backoffice.log_config import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backoffice",
        description="Back Office CLI — unified management commands",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    parser.add_argument("--json-log", action="store_true", help="JSON log output")

    sub = parser.add_subparsers(dest="command")

    # Config
    cfg = sub.add_parser("config", help="Config operations")
    cfg_sub = cfg.add_subparsers(dest="config_command")
    cfg_sub.add_parser("show", help="Dump resolved config")
    sh = cfg_sub.add_parser("shell-export", help="Output shell vars for agent scripts")
    sh.add_argument("--target", help="Target name")
    sh.add_argument("--fields", nargs="*", help="Fields to export")

    # Sync
    sync = sub.add_parser("sync", help="Dashboard sync")
    sync.add_argument("--dept", help="Quick-sync single department")
    sync.add_argument("--dry-run", action="store_true", help="Log uploads without executing")

    # Audit
    audit = sub.add_parser("audit", help="Run audit on a target")
    audit.add_argument("target", help="Target name")
    audit.add_argument("--departments", "-d", help="Comma-separated departments")
    audit.add_argument("--deploy", action="store_true", help="Sync dashboard after audit")

    # Audit all
    audit_all = sub.add_parser("audit-all", help="Run audits on all targets")
    audit_all.add_argument("--departments", "-d", help="Comma-separated departments")
    audit_all.add_argument("--targets", help="Comma-separated target names")

    # Tasks
    tasks = sub.add_parser("tasks", help="Task queue operations")
    tasks.add_argument("action", nargs="?", default="list",
                       choices=["list", "show", "create", "start", "block",
                                "review", "complete", "cancel", "sync",
                                "seed-etheos"])
    tasks.add_argument("--id", help="Task ID")
    tasks.add_argument("--repo", help="Repository filter")
    tasks.add_argument("--status", help="Status filter")
    tasks.add_argument("--title", help="Task title (for create)")
    tasks.add_argument("--note", help="Note for status change")

    # Regression
    sub.add_parser("regression", help="Run regression suite")

    # Scaffold
    scaffold = sub.add_parser("scaffold", help="Scaffold GitHub Actions workflows")
    scaffold.add_argument("--target", required=True, help="Target name")
    scaffold.add_argument("--workflows", default="ci,preview,cd,nightly")
    scaffold.add_argument("--force", action="store_true")

    # Setup
    setup = sub.add_parser("setup", help="Setup wizard")
    setup.add_argument("--check-only", action="store_true")

    # Refresh
    sub.add_parser("refresh", help="Refresh dashboard artifacts")

    # List targets
    sub.add_parser("list-targets", help="List configured targets")

    # Servers
    serve = sub.add_parser("serve", help="Local dashboard dev server")
    serve.add_argument("--port", type=int, default=8070)

    api = sub.add_parser("api-server", help="Production API server")
    api.add_argument("--port", type=int)
    api.add_argument("--bind", default="0.0.0.0")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(verbose=args.verbose, json_output=args.json_log)

    if not args.command:
        parser.print_help()
        return 0

    # Lazy imports to keep startup fast
    if args.command == "config":
        from backoffice.config import load_config, shell_export
        import json

        cfg = load_config()
        if args.config_command == "shell-export":
            print(shell_export(cfg, args.target, args.fields))
        else:
            # show: dump as YAML-like summary
            print(json.dumps({
                "root": str(cfg.root),
                "runner": {"command": cfg.runner.command, "mode": cfg.runner.mode},
                "targets": list(cfg.targets.keys()),
            }, indent=2))
        return 0

    if args.command == "sync":
        from backoffice.sync.engine import SyncEngine
        engine = SyncEngine.from_config()
        return engine.run(department=args.dept, dry_run=args.dry_run)

    if args.command in ("audit", "audit-all", "list-targets", "refresh"):
        from backoffice.workflow import main as workflow_main
        return workflow_main(sys.argv[1:])

    if args.command == "tasks":
        from backoffice.tasks import main as tasks_main
        return tasks_main(sys.argv[1:])

    if args.command == "regression":
        from backoffice.regression import main as regression_main
        return regression_main()

    if args.command == "scaffold":
        from backoffice.scaffolding import main as scaffold_main
        return scaffold_main(sys.argv[1:])

    if args.command == "setup":
        from backoffice.setup import main as setup_main
        return setup_main(sys.argv[1:])

    if args.command == "serve":
        from backoffice.server import main as server_main
        return server_main(port=args.port)

    if args.command == "api-server":
        from backoffice.api_server import main as api_main
        return api_main(sys.argv[1:])

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_main.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backoffice/__main__.py tests/test_main.py
git commit -m "feat: add __main__.py entry point dispatcher"
```

---

## Chunk 2: Sync Layer — Manifest, Providers, Engine

### Task 4: Sync manifest constants

**Files:**
- Create: `backoffice/sync/__init__.py`
- Create: `backoffice/sync/manifest.py`
- Create: `tests/test_sync_manifest.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_sync_manifest.py
"""Tests for backoffice.sync.manifest."""
from backoffice.sync.manifest import (
    DASHBOARD_FILES,
    DEPT_DATA_MAP,
    JOB_STATUS_FILES,
    SHARED_META_FILES,
    content_type_for,
)


def test_dashboard_files_contains_key_files():
    assert "index.html" in DASHBOARD_FILES
    assert "department-context.js" in DASHBOARD_FILES
    assert "favicon.svg" in DASHBOARD_FILES


def test_dept_data_map_has_all_departments():
    assert "qa" in DEPT_DATA_MAP
    assert "seo" in DEPT_DATA_MAP
    assert "self-audit" in DEPT_DATA_MAP
    assert len(DEPT_DATA_MAP) == 8


def test_content_type_for_html():
    assert content_type_for("index.html") == "text/html"


def test_content_type_for_js():
    assert content_type_for("site-branding.js") == "application/javascript"


def test_content_type_for_json():
    assert content_type_for("qa-data.json") == "application/json"


def test_content_type_for_svg():
    assert content_type_for("favicon.svg") == "image/svg+xml"


def test_content_type_for_markdown():
    assert content_type_for("local-audit-log.md") == "text/markdown"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sync_manifest.py -v`
Expected: FAIL

- [ ] **Step 3: Implement manifest.py**

```python
# backoffice/sync/manifest.py
"""Canonical file manifest for dashboard sync.

Single source of truth for which files get uploaded and their
content types. Resolves discrepancies between the old
sync-dashboard.sh and quick-sync.sh file lists.
"""

# Dashboard HTML/JS/CSS files (full sync uploads all of these)
DASHBOARD_FILES: list[str] = [
    "index.html", "qa.html", "backoffice.html",
    "seo.html", "ada.html", "compliance.html", "privacy.html",
    "monetization.html", "product.html",
    "jobs.html", "faq.html", "self-audit.html", "admin.html", "regression.html",
    "selah.html", "analogify.html", "chromahaus.html", "tnbm-tarot.html",
    "back-office-hq.html",
    "documentation.html", "documentation-github.html",
    "documentation-cicd.html", "documentation-cli.html",
    "site-branding.js", "department-context.js", "favicon.svg",
]

# Department findings -> dashboard data file mapping
# Key: department name
# Value: (raw findings filename, dashboard data filename)
DEPT_DATA_MAP: dict[str, tuple[str, str]] = {
    "qa":           ("findings.json",             "qa-data.json"),
    "seo":          ("seo-findings.json",         "seo-data.json"),
    "ada":          ("ada-findings.json",         "ada-data.json"),
    "compliance":   ("compliance-findings.json",  "compliance-data.json"),
    "privacy":      ("privacy-findings.json",     "privacy-data.json"),
    "monetization": ("monetization-findings.json", "monetization-data.json"),
    "product":      ("product-findings.json",     "product-data.json"),
    "self-audit":   ("findings.json",             "self-audit-data.json"),
}

# Aggregated data files (used when no repo filter is set)
AGG_DATA_MAP: dict[str, str] = {
    "data.json":              "qa-data.json",
    "seo-data.json":          "seo-data.json",
    "ada-data.json":          "ada-data.json",
    "compliance-data.json":   "compliance-data.json",
    "privacy-data.json":      "privacy-data.json",
    "monetization-data.json": "monetization-data.json",
    "product-data.json":      "product-data.json",
}

# Shared metadata files (uploaded for both repo-scoped and aggregated targets)
SHARED_META_FILES: list[str] = [
    "automation-data.json",
    "org-data.json",
    "local-audit-log.json",
    "local-audit-log.md",
    "regression-data.json",
]

# Job status files
JOB_STATUS_FILES: list[str] = [".jobs.json", ".jobs-history.json"]

# Content type mapping by extension
_CONTENT_TYPES: dict[str, str] = {
    ".html": "text/html",
    ".js":   "application/javascript",
    ".json": "application/json",
    ".svg":  "image/svg+xml",
    ".md":   "text/markdown",
    ".css":  "text/css",
}


def content_type_for(filename: str) -> str:
    """Return the content type for a file based on extension."""
    for ext, ct in _CONTENT_TYPES.items():
        if filename.endswith(ext):
            return ct
    return "application/octet-stream"
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_sync_manifest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backoffice/sync/__init__.py backoffice/sync/manifest.py tests/test_sync_manifest.py
git commit -m "feat: add canonical sync file manifest"
```

---

### Task 5: Provider abstraction (base + AWS)

**Files:**
- Create: `backoffice/sync/providers/__init__.py`
- Create: `backoffice/sync/providers/base.py`
- Create: `backoffice/sync/providers/aws.py`
- Create: `tests/test_sync_providers.py`

- [ ] **Step 1: Write failing tests for provider interfaces**

```python
# tests/test_sync_providers.py
"""Tests for backoffice.sync.providers."""
import pytest

from backoffice.sync.providers.base import CDNProvider, StorageProvider


def test_storage_provider_is_abstract():
    with pytest.raises(TypeError):
        StorageProvider()  # type: ignore


def test_cdn_provider_is_abstract():
    with pytest.raises(TypeError):
        CDNProvider()  # type: ignore


class FakeStorage(StorageProvider):
    def __init__(self):
        self.uploads = []

    def upload_file(self, bucket, local_path, remote_key, content_type, cache_control):
        self.uploads.append((bucket, local_path, remote_key, content_type))

    def upload_files(self, file_mappings):
        for m in file_mappings:
            self.upload_file(m["bucket"], m["local_path"], m["remote_key"],
                           m["content_type"], m["cache_control"])

    def sync_directory(self, bucket, local_dir, remote_prefix, delete=False):
        pass


class FakeCDN(CDNProvider):
    def __init__(self):
        self.invalidations = []

    def invalidate(self, distribution_id, paths):
        self.invalidations.append({"dist": distribution_id, "paths": paths})


def test_fake_storage_satisfies_interface():
    s = FakeStorage()
    s.upload_file("my-bucket", "/tmp/a.html", "a.html", "text/html", "no-cache")
    assert len(s.uploads) == 1


def test_fake_cdn_satisfies_interface():
    c = FakeCDN()
    c.invalidate("EXXXXX", ["/index.html"])
    assert len(c.invalidations) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sync_providers.py -v`
Expected: FAIL

- [ ] **Step 3: Implement base.py**

```python
# backoffice/sync/providers/base.py
"""Abstract base classes for storage and CDN providers."""
from abc import ABC, abstractmethod


class StorageProvider(ABC):
    """Interface for uploading files to a remote storage service."""

    @abstractmethod
    def upload_file(self, bucket: str, local_path: str, remote_key: str,
                    content_type: str, cache_control: str) -> None:
        """Upload a single file to a bucket/container."""

    @abstractmethod
    def upload_files(self, file_mappings: list[dict]) -> None:
        """Upload multiple files. Each mapping has: bucket, local_path,
        remote_key, content_type, cache_control."""

    @abstractmethod
    def sync_directory(self, bucket: str, local_dir: str,
                       remote_prefix: str, delete: bool = False) -> None:
        """Sync a local directory to a remote prefix. Used for regression logs."""


class CDNProvider(ABC):
    """Interface for invalidating CDN cache."""

    @abstractmethod
    def invalidate(self, distribution_id: str, paths: list[str]) -> None:
        """Invalidate the given paths for a specific distribution/zone."""
```

- [ ] **Step 4: Implement aws.py**

```python
# backoffice/sync/providers/aws.py
"""AWS S3 + CloudFront provider implementation."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from backoffice.sync.providers.base import CDNProvider, StorageProvider

logger = logging.getLogger(__name__)

# Application-level retry on top of boto3's built-in retry
MAX_RETRIES = 3
BACKOFF_BASE = 1  # seconds


def _retry(fn, *args, **kwargs):
    """Retry fn up to MAX_RETRIES times with exponential backoff."""
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                wait = BACKOFF_BASE * (2 ** attempt)
                logger.warning("Retry %d/%d after %.1fs: %s",
                             attempt + 1, MAX_RETRIES, wait, exc)
                time.sleep(wait)
    raise last_exc  # type: ignore


class AWSStorage(StorageProvider):
    """S3 storage provider using boto3."""

    def __init__(self, region: str):
        import boto3
        self._s3 = boto3.client("s3", region_name=region)

    def upload_file(self, bucket: str, local_path: str, remote_key: str,
                    content_type: str, cache_control: str) -> None:
        """Upload a single file to an S3 bucket with retry."""
        def _do_upload():
            self._s3.upload_file(
                local_path, bucket, remote_key,
                ExtraArgs={
                    "ContentType": content_type,
                    "CacheControl": cache_control,
                },
            )
        _retry(_do_upload)
        logger.info("Uploaded %s -> s3://%s/%s", Path(local_path).name, bucket, remote_key)

    def upload_files(self, file_mappings: list[dict]) -> None:
        for m in file_mappings:
            self.upload_file(
                m["bucket"], m["local_path"], m["remote_key"],
                m["content_type"], m["cache_control"],
            )

    def sync_directory(self, bucket: str, local_dir: str,
                       remote_prefix: str, delete: bool = False) -> None:
        """Sync a local directory to S3. Used for regression logs."""
        import subprocess
        s3_uri = f"s3://{bucket}/{remote_prefix}" if remote_prefix else f"s3://{bucket}"
        cmd = ["aws", "s3", "sync", local_dir, s3_uri]
        if delete:
            cmd.append("--delete")
        cmd.extend(["--cache-control", "no-cache, no-store, must-revalidate"])
        logger.info("Syncing %s -> %s", local_dir, s3_uri)
        subprocess.run(cmd, check=True)


class AWSCloudFront(CDNProvider):
    """CloudFront CDN provider using boto3."""

    def __init__(self, region: str):
        import boto3
        self._cf = boto3.client("cloudfront", region_name=region)

    def invalidate(self, distribution_id: str, paths: list[str]) -> None:
        """Invalidate specific paths on a CloudFront distribution."""
        if not distribution_id or not paths:
            return
        import time as _time
        caller_ref = str(int(_time.time() * 1000))
        try:
            self._cf.create_invalidation(
                DistributionId=distribution_id,
                InvalidationBatch={
                    "Paths": {"Quantity": len(paths), "Items": paths},
                    "CallerReference": caller_ref,
                },
            )
            logger.info("Invalidated %d paths on %s", len(paths), distribution_id)
        except Exception as exc:
            logger.warning("CloudFront invalidation failed for %s: %s",
                         distribution_id, exc)
```

- [ ] **Step 5: Implement providers/__init__.py factory**

```python
# backoffice/sync/providers/__init__.py
"""Provider factory."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backoffice.config import Config

from backoffice.sync.providers.base import CDNProvider, StorageProvider


def get_providers(config: "Config") -> tuple[StorageProvider, CDNProvider]:
    """Create storage and CDN providers from config."""
    provider = config.deploy.provider
    if provider == "aws":
        from backoffice.sync.providers.aws import AWSCloudFront, AWSStorage
        region = config.deploy.aws.region
        return AWSStorage(region), AWSCloudFront(region)
    raise ValueError(f"Unknown deploy provider: {provider}")
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_sync_providers.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backoffice/sync/providers/ tests/test_sync_providers.py
git commit -m "feat: add provider abstraction with AWS S3/CloudFront implementation"
```

---

### Task 6: Sync engine

**Files:**
- Create: `backoffice/sync/engine.py`
- Create: `tests/test_sync_engine.py`

- [ ] **Step 1: Write failing tests for sync engine**

```python
# tests/test_sync_engine.py
"""Tests for backoffice.sync.engine."""
import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backoffice.sync.engine import SyncEngine
from backoffice.sync.providers.base import CDNProvider, StorageProvider


class MemoryStorage(StorageProvider):
    """In-memory storage for testing."""
    def __init__(self):
        self.uploads = []

    def upload_file(self, bucket, local_path, remote_key, content_type, cache_control):
        self.uploads.append({"bucket": bucket, "local_path": local_path,
                            "remote_key": remote_key, "content_type": content_type})

    def upload_files(self, file_mappings):
        for m in file_mappings:
            self.upload_file(m["bucket"], m["local_path"], m["remote_key"],
                           m["content_type"], m["cache_control"])

    def sync_directory(self, bucket, local_dir, remote_prefix, delete=False):
        self.uploads.append({"sync": local_dir, "bucket": bucket, "prefix": remote_prefix})


class MemoryCDN(CDNProvider):
    def __init__(self):
        self.invalidations = []

    def invalidate(self, distribution_id, paths):
        self.invalidations.append({"dist": distribution_id, "paths": paths})


@pytest.fixture
def dashboard_dir(tmp_path):
    d = tmp_path / "dashboard"
    d.mkdir()
    (d / "index.html").write_text("<html>test</html>")
    (d / "qa.html").write_text("<html>qa</html>")
    (d / "qa-data.json").write_text('{"findings":[]}')
    (d / "org-data.json").write_text('{}')
    (d / ".jobs.json").write_text('[]')
    return d


@pytest.fixture
def results_dir(tmp_path):
    r = tmp_path / "results"
    r.mkdir()
    repo = r / "demo"
    repo.mkdir()
    (repo / "findings.json").write_text('{"findings":[]}')
    return r


def test_dry_run_does_not_upload(dashboard_dir, results_dir):
    storage = MemoryStorage()
    cdn = MemoryCDN()
    engine = SyncEngine(
        storage=storage, cdn=cdn,
        dashboard_dir=dashboard_dir, results_dir=results_dir,
        dashboard_targets=[], skip_gate=True,
    )
    engine.run(dry_run=True)
    assert len(storage.uploads) == 0


def test_allow_public_read_false_skips_public_target(dashboard_dir, results_dir):
    from backoffice.config import DashboardTarget
    target = DashboardTarget(
        bucket="www.example.com",
        subdomain="www.example.com",
        allow_public_read=False,
    )
    storage = MemoryStorage()
    cdn = MemoryCDN()
    engine = SyncEngine(
        storage=storage, cdn=cdn,
        dashboard_dir=dashboard_dir, results_dir=results_dir,
        dashboard_targets=[target], skip_gate=True,
    )
    engine.run()
    assert len(storage.uploads) == 0  # public target skipped


def test_aggregated_target_uploads_all_file_types(dashboard_dir, results_dir):
    """Aggregated targets (no filter_repo) must upload HTML + AGG_DATA + SHARED + JOBS."""
    from backoffice.config import DashboardTarget
    # Create shared/job files that the engine expects
    (dashboard_dir / "automation-data.json").write_text("{}")
    (dashboard_dir / ".jobs-history.json").write_text("[]")
    (dashboard_dir / "data.json").write_text("{}")
    target = DashboardTarget(
        bucket="admin.example.com",
        subdomain="admin.example.com",
        filter_repo=None,  # aggregated
    )
    storage = MemoryStorage()
    cdn = MemoryCDN()
    engine = SyncEngine(
        storage=storage, cdn=cdn,
        dashboard_dir=dashboard_dir, results_dir=results_dir,
        dashboard_targets=[target], skip_gate=True,
    )
    engine.run()
    keys = [u[2] if len(u) > 2 else u.get("remote_key", "") for u in storage.uploads]
    # Should include HTML files
    assert any("index.html" in str(k) for k in keys)
    # Should include aggregated data
    assert any("qa-data.json" in str(k) for k in keys)
    # Should include shared metadata
    assert any("org-data.json" in str(k) for k in keys)
    # Should include job status
    assert any(".jobs.json" in str(k) for k in keys)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sync_engine.py -v`
Expected: FAIL

- [ ] **Step 3: Implement sync/engine.py**

Port the logic from `scripts/sync-dashboard.sh` (lines 40-235) and `scripts/quick-sync.sh` into a Python class. The engine should:

1. `run(department=None, dry_run=False)` — main entry point
2. `run_pre_deploy_gate()` — run scoring tests (skip in quick-sync mode)
3. `_aggregate()` — call aggregate + delivery modules directly (not subprocess)
4. `_upload_full_sync(target)` — upload HTML + data + shared files
5. `_upload_quick_sync(target, department)` — upload only dept data + jobs + shared
6. `_resolve_data_files(target)` — per-repo vs aggregated data
7. `_sync_regression_logs(target)` — sync results/regression/ directory
8. Uses `DashboardTarget.allow_public_read` safety gate

**Critical: Upload file list composition:**
- **Full sync, per-repo target:** `DASHBOARD_FILES` + per-repo findings via `DEPT_DATA_MAP` + `SHARED_META_FILES` + `JOB_STATUS_FILES` + regression directory sync
- **Full sync, aggregated target (no filter_repo):** `DASHBOARD_FILES` + `AGG_DATA_MAP` + `SHARED_META_FILES` + `JOB_STATUS_FILES` + regression directory sync
- **Quick-sync (`--dept`):** single department from `DEPT_DATA_MAP` + `SHARED_META_FILES` + `JOB_STATUS_FILES` (no HTML, no regression sync)

This matches the existing behavior where `sync-dashboard.sh` combines `dashboard_files + dept_data_map/agg_data_files + shared_meta_files + job_status_files`. Test this explicitly.

Key: the engine accepts storage/cdn providers via constructor (dependency injection), enabling testing with `MemoryStorage`/`MemoryCDN`.

Reference `scripts/sync-dashboard.sh:40-235` for the full upload logic, target iteration, `allow_public_read` gate, and CloudFront invalidation. Reference `scripts/quick-sync.sh:41-209` for quick-sync flow.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_sync_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backoffice/sync/engine.py tests/test_sync_engine.py
git commit -m "feat: add sync engine with full/quick sync and dry-run mode"
```

---

## Chunk 3: Data Modules — Aggregate, Delivery, Tasks

### Task 7: Aggregate module

**Files:**
- Create: `backoffice/aggregate.py`
- Create: `tests/test_aggregate.py`

- [ ] **Step 1: Write failing tests**

Write tests that cover the core aggregation behavior: loading findings JSON, counting severities, handling malformed JSON gracefully (log + skip), producing dashboard payloads per department. Test the privacy keyword filtering and score calculation.

Reference `scripts/test-scoring.py` for existing test patterns and `scripts/aggregate-results.py` for the logic to port.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_aggregate.py -v`
Expected: FAIL

- [ ] **Step 3: Port aggregate-results.py into backoffice/aggregate.py**

Port all functions from `scripts/aggregate-results.py` (478 LOC). Key changes:
- Replace `print()` with `logger.info()` / `logger.warning()`
- Accept config paths via function args instead of CLI args
- Use `backoffice.config.Config` to resolve paths
- Add `main()` function that accepts `results_dir` and `output_path` args
- Keep all scoring/privacy logic identical

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_aggregate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backoffice/aggregate.py tests/test_aggregate.py
git commit -m "feat: port aggregation logic to backoffice.aggregate"
```

---

### Task 8: Delivery module

**Files:**
- Create: `backoffice/delivery.py`
- Create: `tests/test_delivery.py`

- [ ] **Step 1: Write failing tests**

Test delivery data generation: loading targets, scanning workflows, detecting commands, calculating readiness scores, filtering safe candidates. Reference `scripts/generate-delivery-data.py` for logic.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_delivery.py -v`
Expected: FAIL

- [ ] **Step 3: Port generate-delivery-data.py into backoffice/delivery.py**

Port all functions from `scripts/generate-delivery-data.py` (426 LOC). Key changes:
- Replace env var lookups with `Config` object access
- Replace `print()` with structured logging
- Add `main(config: Config | None = None)` entry point

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_delivery.py -v`
Expected: PASS

```bash
git add backoffice/delivery.py tests/test_delivery.py
git commit -m "feat: port delivery data generation to backoffice.delivery"
```

---

### Task 9: Tasks module

**Files:**
- Create: `backoffice/tasks.py`
- Create: `tests/test_tasks.py`

- [ ] **Step 1: Write failing tests**

Test task queue operations: create, list, show, status transitions, gate checking, YAML ↔ JSON sync. Reference `scripts/task-queue.py` for logic.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tasks.py -v`
Expected: FAIL

- [ ] **Step 3: Port task-queue.py into backoffice/tasks.py**

Port all functions from `scripts/task-queue.py` (528 LOC). Key changes:
- Replace env var lookups with `Config` object access
- Replace `print()` with structured logging
- Keep `config/task-queue.yaml` as the operational state file (not merged into backoffice.yaml)
- Add `main(argv: list[str])` entry point

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_tasks.py -v`
Expected: PASS

```bash
git add backoffice/tasks.py tests/test_tasks.py
git commit -m "feat: port task queue to backoffice.tasks"
```

---

## Chunk 4: Runner Modules — Regression, Scaffolding, Setup

### Task 10: Regression module

**Files:**
- Create: `backoffice/regression.py`
- Create: `tests/test_regression.py`

- [ ] **Step 1: Write failing tests**

Test regression runner: loading targets, running commands with timeout, parsing coverage output (pytest-cov JSON, vitest summary, LCOV), handling failures gracefully. Reference `scripts/regression-runner.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_regression.py -v`

- [ ] **Step 3: Port regression-runner.py into backoffice/regression.py**

Port from `scripts/regression-runner.py` (362 LOC). Key changes:
- Use `Config.targets` instead of loading `targets.yaml` directly
- Replace `print()` with structured logging
- Use `Config.root` for output paths
- Add `main(config: Config | None = None)` entry point

- [ ] **Step 4: Run tests and commit**

```bash
git add backoffice/regression.py tests/test_regression.py
git commit -m "feat: port regression runner to backoffice.regression"
```

---

### Task 11: Scaffolding module

**Files:**
- Create: `backoffice/scaffolding.py`
- Create: `tests/test_scaffolding.py`

- [ ] **Step 1: Write failing tests**

Test workflow scaffolding: template loading, placeholder replacement, file writing with force/skip logic. Reference `scripts/scaffold-github-workflows.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scaffolding.py -v`

- [ ] **Step 3: Port scaffold-github-workflows.py into backoffice/scaffolding.py**

Port from `scripts/scaffold-github-workflows.py` (99 LOC). Key changes:
- Use `Config.targets` instead of loading `targets.yaml`
- Add `main(argv: list[str])` entry point

- [ ] **Step 4: Run tests and commit**

```bash
git add backoffice/scaffolding.py tests/test_scaffolding.py
git commit -m "feat: port workflow scaffolding to backoffice.scaffolding"
```

---

### Task 12: Setup module

**Files:**
- Create: `backoffice/setup.py`
- Create: `tests/test_setup.py`

- [ ] **Step 1: Write failing tests**

Test setup wizard: prerequisite checks, runner detection, config file creation. Reference `scripts/backoffice_setup.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_setup.py -v`

- [ ] **Step 3: Port backoffice_setup.py into backoffice/setup.py**

Port from `scripts/backoffice_setup.py` (324 LOC). Key changes:
- Write `config/backoffice.yaml` instead of `config/agent-runner.env`
- Use new config schema for runner persistence
- Add `main(argv: list[str])` entry point

- [ ] **Step 4: Run tests and commit**

```bash
git add backoffice/setup.py tests/test_setup.py
git commit -m "feat: port setup wizard to backoffice.setup"
```

---

## Chunk 5: Servers — Dashboard Server, API Server

### Task 13: Dashboard server

**Files:**
- Create: `backoffice/server.py`
- Create: `tests/test_servers.py`

- [ ] **Step 1: Write failing tests**

Test dashboard server: serves files from dashboard dir, handles API endpoints (run-scan, manual-item), CORS headers. Reference `scripts/dashboard-server.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_servers.py -v`

- [ ] **Step 3: Port dashboard-server.py into backoffice/server.py**

Port from `scripts/dashboard-server.py` (384 LOC). Key changes:
- Use `Config` for paths and allowed origins
- Replace `print()` with structured logging
- Add `main(port: int = 8070)` entry point

- [ ] **Step 4: Run tests and commit**

```bash
git add backoffice/server.py tests/test_servers.py
git commit -m "feat: port dashboard server to backoffice.server"
```

---

### Task 14: API server

**Files:**
- Create: `backoffice/api_server.py`

- [ ] **Step 1: Write failing tests**

Add API server tests to `tests/test_servers.py`. Test: health endpoint, auth enforcement, target resolution, CORS. Reference `scripts/api-server.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_servers.py -v`

- [ ] **Step 3: Port api-server.py into backoffice/api_server.py**

Port from `scripts/api-server.py` (396 LOC). Key changes:
- Use `Config.api` for port, API key, origins
- Use `Config.targets` for target resolution (eliminating separate `api-config.yaml` targets)
- Replace `print()` with structured logging
- Keep `hmac.compare_digest()` for timing-safe auth
- Add `main(argv: list[str])` entry point

- [ ] **Step 4: Run tests and commit**

```bash
git add backoffice/api_server.py tests/test_servers.py
git commit -m "feat: port API server to backoffice.api_server"
```

---

## Chunk 6: Orchestration — Workflow, CLI

### Task 15: Workflow module

**Files:**
- Create: `backoffice/workflow.py`
- Create: `tests/test_workflow.py`

- [ ] **Step 1: Write failing tests**

Test local audit workflow: target loading, department resolution, refresh logic (calls aggregate + delivery + tasks sync), audit log generation, file locking. Reference `scripts/local_audit_workflow.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_workflow.py -v`

- [ ] **Step 3: Port local_audit_workflow.py into backoffice/workflow.py**

Port from `scripts/local_audit_workflow.py` (439 LOC). Key changes:
- Use `Config.targets` instead of loading `targets.yaml`
- Call `backoffice.aggregate.main()` and `backoffice.delivery.main()` directly instead of spawning subprocesses
- Call `backoffice.tasks.command_sync()` directly
- Replace env var script paths with direct function calls
- Keep `fcntl` file locking for exclusive run prevention
- Add `main(argv: list[str])` entry point

- [ ] **Step 4: Run tests and commit**

```bash
git add backoffice/workflow.py tests/test_workflow.py
git commit -m "feat: port local audit workflow to backoffice.workflow"
```

---

### ~~Task 16: CLI module~~ (REMOVED)

`backoffice/cli.py` is not needed. The `__main__.py` dispatcher (Task 3) absorbs all subcommand routing from `scripts/backoffice-cli.py`. The old `backoffice-cli.py` becomes a thin wrapper calling `python -m backoffice` in Phase 1.

---

## Chunk 7: Migration — Wrappers, Makefile, CI, Cleanup

### Task 17: Phase 1 — Wrapper scripts

**Files:**
- Modify: `scripts/aggregate-results.py`
- Modify: `scripts/generate-delivery-data.py`
- Modify: `scripts/task-queue.py`
- Modify: `scripts/regression-runner.py`
- Modify: `scripts/backoffice_setup.py`
- Modify: `scripts/dashboard-server.py`
- Modify: `scripts/api-server.py`
- Modify: `scripts/backoffice-cli.py`
- Modify: `scripts/local_audit_workflow.py`
- Modify: `scripts/scaffold-github-workflows.py`

- [ ] **Step 1: Replace each script with a thin wrapper**

Each script becomes ~3 lines that import from the package:

```python
#!/usr/bin/env python3
"""Thin wrapper — delegates to backoffice package. Will be removed in Phase 3."""
from backoffice.aggregate import main
import sys
sys.exit(main() or 0)
```

Do this for all 10 scripts listed above. Map each to its package module:
- `aggregate-results.py` → `backoffice.aggregate`
- `generate-delivery-data.py` → `backoffice.delivery`
- `task-queue.py` → `backoffice.tasks`
- `regression-runner.py` → `backoffice.regression`
- `backoffice_setup.py` → `backoffice.setup`
- `dashboard-server.py` → `backoffice.server`
- `api-server.py` → `backoffice.api_server`
- `backoffice-cli.py` → wraps `python -m backoffice` (runs __main__.py)
- `local_audit_workflow.py` → `backoffice.workflow`
- `scaffold-github-workflows.py` → `backoffice.scaffolding`

**Special case: `scripts/parse-config.py`** — This script is called by all 7 agent scripts in `agents/`. It stays as a thin wrapper that delegates to `backoffice.config`:

```python
#!/usr/bin/env python3
"""Thin wrapper — agent scripts call this for target field lookups.
Delegates to backoffice.config.shell_export with null-delimited output.
"""
import sys
from pathlib import Path

def main():
    if len(sys.argv) < 4:
        print("Usage: parse-config.py <config_path> <repo_name> <target_repo> <field1> [field2 ...]",
              file=sys.stderr)
        sys.exit(1)

    repo_name = sys.argv[2]
    target_repo = sys.argv[3]
    fields = sys.argv[4:] if len(sys.argv) > 4 else []
    if not fields:
        sys.exit(0)

    from backoffice.config import load_config, shell_export
    try:
        cfg = load_config()
    except Exception:
        # Graceful degradation: output empty values if config unavailable
        sys.stdout.write("\0".join([""] * len(fields)))
        sys.exit(0)

    # Find target by name or path (matching old lookup behavior)
    target_name = None
    for name, target in cfg.targets.items():
        if name == repo_name or target.path == target_repo:
            target_name = name
            break

    sys.stdout.write(shell_export(cfg, target_name=target_name, fields=fields))

if __name__ == "__main__":
    main()
```

This preserves the null-delimited output interface that agent scripts expect, and keeps the agents completely untouched.

- [ ] **Step 2: Run existing tests to verify wrappers work**

Run: `make test`
Expected: PASS (all existing tests should pass through the wrappers)

- [ ] **Step 3: Commit**

```bash
git add scripts/*.py
git commit -m "refactor: replace scripts with thin wrappers delegating to backoffice package"
```

---

### Task 18: Phase 2 — Makefile and CI updates

**Files:**
- Modify: `Makefile`
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/run-agent.sh`
- Modify: `scripts/sync-dashboard.sh`
- Modify: `scripts/quick-sync.sh`

- [ ] **Step 1: Update Makefile targets**

Change Python script invocations to use `python -m backoffice`:

```makefile
# Key changes:
# regression target
regression:
	python3 -m backoffice regression

# local workflow targets
local-targets:
	python3 -m backoffice list-targets

local-refresh:
	python3 -m backoffice refresh

local-audit:
	python3 -m backoffice audit $(TARGET_NAME)

# dashboard target
dashboard:
	python3 -m backoffice sync

# quick-sync target
quick-sync:
	python3 -m backoffice sync --dept $(DEPT)

# test target — point to tests/ directory
test:
	python3 -m pytest tests/ -v
```

Keep shell script invocations for agent scripts (they're untouched).

- [ ] **Step 2: Update scripts/sync-dashboard.sh to 3-line wrapper**

```bash
#!/usr/bin/env bash
set -euo pipefail
exec python3 -m backoffice sync "$@"
```

- [ ] **Step 3: Update scripts/quick-sync.sh to 3-line wrapper**

```bash
#!/usr/bin/env bash
set -euo pipefail
exec python3 -m backoffice sync --dept "$@"
```

- [ ] **Step 4: Update scripts/run-agent.sh config loading**

Replace the `source` of `agent-runner.env` with:

```bash
# Load runner config from unified config
if command -v python3 &>/dev/null; then
    eval "$(python3 -m backoffice config shell-export 2>/dev/null)" || true
fi
```

Keep the fallback to `agent-runner.env` during transition:

```bash
# Fallback: source legacy env file if package not available
if [ -z "${BACK_OFFICE_AGENT_RUNNER:-}" ]; then
    RUNNER_CONFIG="${BACK_OFFICE_RUNNER_CONFIG:-$ROOT_DIR/config/agent-runner.env}"
    [ -f "$RUNNER_CONFIG" ] && source "$RUNNER_CONFIG"
fi
```

- [ ] **Step 5: Update CI workflow and coverage config**

Update `.github/workflows/ci.yml`:
- Change test step to: `python3 -m pytest tests/ --cov=backoffice --cov-report=term --cov-report=xml`
- Add `backoffice/` to Python syntax validation
- Keep shell script validation unchanged

Update `Makefile` `test-coverage` target to use the new paths:
```makefile
test-coverage:
	python3 -m pytest tests/ --cov=backoffice --cov-report=term --cov-report=xml --cov-report=json:coverage.json
```

Note: `pyproject.toml` already has `[tool.coverage.run] source = ["backoffice"]` from Task 1, so any existing `.coveragerc` can be deleted.

- [ ] **Step 6: Run tests**

Run: `make test`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add Makefile .github/workflows/ci.yml scripts/run-agent.sh scripts/sync-dashboard.sh scripts/quick-sync.sh
git commit -m "refactor: update Makefile, CI, and shell wrappers to use backoffice package"
```

---

### Task 19: Phase 3 — Delete old scripts and configs

**Files:**
- Delete: 10 Python scripts from `scripts/` (NOT parse-config.py — it stays as a wrapper)
- Delete: 4 config files (targets.yaml is safe to delete — parse-config.py wrapper reads from backoffice.yaml)
- Update: `config/*.example.yaml`

- [ ] **Step 1: Delete old scripts**

```bash
git rm scripts/aggregate-results.py scripts/generate-delivery-data.py \
  scripts/task-queue.py scripts/regression-runner.py scripts/backoffice_setup.py \
  scripts/dashboard-server.py scripts/api-server.py scripts/backoffice-cli.py \
  scripts/local_audit_workflow.py scripts/scaffold-github-workflows.py
```

Note: `scripts/parse-config.py` is kept — it was converted to a thin wrapper in Task 17 and is called by all 7 agent scripts.

- [ ] **Step 2: Delete old config files**

```bash
git rm config/targets.yaml config/qa-config.yaml config/api-config.yaml config/agent-runner.env
```

- [ ] **Step 3: Update example configs**

Replace `config/targets.example.yaml`, `config/qa-config.example.yaml`, `config/api-config.example.yaml`, `config/agent-runner.env.example` with a single `config/backoffice.example.yaml` that matches the new schema.

```bash
git rm config/targets.example.yaml config/qa-config.example.yaml \
  config/api-config.example.yaml config/agent-runner.env.example
```

- [ ] **Step 4: Delete old test files**

```bash
git rm scripts/test-scoring.py scripts/test-local-audit-workflow.py \
  scripts/test-cli-and-scaffolding.py scripts/test-servers-and-setup.py
```

- [ ] **Step 5: Remove run-agent.sh legacy fallback**

Remove the fallback `source agent-runner.env` block added in Task 18, keeping only the `python -m backoffice config shell-export` path.

- [ ] **Step 6: Run full test suite**

Run: `make test`
Expected: PASS (all tests run from `tests/` directory)

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "cleanup: remove old scripts and config files, complete migration to backoffice package"
```

---

### Task 20: Final verification

- [ ] **Step 1: Run full test suite with coverage**

Run: `python -m pytest tests/ --cov=backoffice --cov-report=term -v`
Expected: PASS, coverage >= 55.8% (floor from old suite)

- [ ] **Step 2: Verify key Makefile targets work**

```bash
make help          # Should show all targets
make local-targets # Should list configured targets
make test          # Should run tests from tests/ directory
```

- [ ] **Step 3: Verify sync dry-run**

Run: `python -m backoffice sync --dry-run`
Expected: Logs every file that would be uploaded without actually uploading.

- [ ] **Step 4: Verify config commands**

```bash
python -m backoffice config show
python -m backoffice config shell-export
```

- [ ] **Step 5: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final verification and cleanup"
```
