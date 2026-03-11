#!/usr/bin/env python3
"""Guided setup and environment inspection for Back Office."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
AGENTS_DIR = ROOT / "agents"
PROMPTS_DIR = AGENTS_DIR / "prompts"
SCRIPTS_DIR = ROOT / "scripts"
RESULTS_DIR = ROOT / "results"

KNOWN_RUNNERS = ("claude", "codex", "aider")
AGENT_USAGE = {
    "qa-scan.sh": "Quality and regression scanning for one configured target repo.",
    "seo-audit.sh": "Search, metadata, AI discoverability, and content structure review.",
    "ada-audit.sh": "Accessibility and WCAG-oriented audit lane.",
    "compliance-audit.sh": "Compliance, policy, and operational risk review.",
    "monetization-audit.sh": "Revenue, conversion, pricing, and offer review.",
    "product-audit.sh": "Product gaps, roadmap, UX, and readiness review.",
    "fix-bugs.sh": "Remediation lane for findings that are safe to patch automatically.",
    "watch.sh": "Watch mode that reruns scans and optional fixes over time.",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect Back Office prerequisites, agent setup, and config state."
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Do not modify files or permissions; only report current setup state.",
    )
    parser.add_argument(
        "--write-missing-configs",
        action="store_true",
        help="Copy config examples into place when qa-config.yaml or targets.yaml are missing.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt before writing missing config files when running in a TTY.",
    )
    return parser.parse_args(argv)


def print_header(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def detect_runner_status() -> tuple[str, str, list[str]]:
    runner_cmd = os.environ.get("BACK_OFFICE_AGENT_RUNNER", "claude")
    runner_mode = os.environ.get("BACK_OFFICE_AGENT_MODE", "claude-print")
    runner_bin = runner_cmd.split()[0]
    available = [name for name in KNOWN_RUNNERS if shutil.which(name)]
    return runner_cmd, runner_mode, available


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def ensure_executable(path: Path) -> None:
    current = path.stat().st_mode
    path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def maybe_copy_file(source: Path, destination: Path, *, enabled: bool, interactive: bool) -> bool:
    if destination.exists():
        return False
    if not enabled:
        return False
    if interactive and sys.stdin.isatty():
        answer = input(f"Create {destination.relative_to(ROOT)} from example? [Y/n] ").strip().lower()
        if answer not in ("", "y", "yes"):
            return False
    shutil.copy2(source, destination)
    return True


def summarize_agent_scripts() -> None:
    print_header("Agent Inventory")
    for script in sorted(AGENTS_DIR.glob("*.sh")):
        prompt = PROMPTS_DIR / f"{script.stem}.md"
        prompt_state = prompt.name if prompt.exists() else "no dedicated prompt file"
        description = AGENT_USAGE.get(script.name, "Utility script.")
        print(f"* {script.name}")
        print(f"  Usage: bash agents/{script.name} /path/to/repo")
        print(f"  Purpose: {description}")
        print(f"  Prompt: {prompt_state}")


def summarize_runner() -> bool:
    print_header("Agent Runner")
    runner_cmd, runner_mode, available = detect_runner_status()
    runner_bin = runner_cmd.split()[0]
    runner_ok = shutil.which(runner_bin) is not None
    print(f"* Active runner command: {runner_cmd}")
    print(f"* Runner mode: {runner_mode}")
    print(f"* Active runner binary found: {'yes' if runner_ok else 'no'}")
    print(f"* Other detected runner CLIs: {', '.join(available) if available else 'none'}")
    print("* Change runner:")
    print("  export BACK_OFFICE_AGENT_RUNNER='codex'")
    print("  export BACK_OFFICE_AGENT_MODE='stdin-text'")
    return runner_ok


def summarize_config_state(args: argparse.Namespace) -> None:
    print_header("Configuration State")
    qa_example = CONFIG_DIR / "qa-config.example.yaml"
    qa_config = CONFIG_DIR / "qa-config.yaml"
    targets_example = CONFIG_DIR / "targets.example.yaml"
    targets_config = CONFIG_DIR / "targets.yaml"

    wrote_qa = maybe_copy_file(
        qa_example,
        qa_config,
        enabled=not args.check_only and args.write_missing_configs,
        interactive=args.interactive,
    )
    wrote_targets = maybe_copy_file(
        targets_example,
        targets_config,
        enabled=not args.check_only and args.write_missing_configs,
        interactive=args.interactive,
    )

    print(f"* qa-config.yaml: {'present' if qa_config.exists() else 'missing'}")
    print(f"* targets.yaml: {'present' if targets_config.exists() else 'missing'}")
    if wrote_qa:
        print("  Created config/qa-config.yaml from example.")
    if wrote_targets:
        print("  Created config/targets.yaml from example.")

    qa_payload = load_yaml(qa_config)
    targets_payload = load_yaml(targets_config)
    dashboard_targets = qa_payload.get("dashboard_targets", []) if isinstance(qa_payload, dict) else []
    targets = targets_payload.get("targets", []) if isinstance(targets_payload, dict) else []
    print(f"* Dashboard deploy targets configured: {len(dashboard_targets)}")
    print(f"* Local audit targets configured: {len(targets)}")
    if targets:
        print("  Target names: " + ", ".join(target.get("name", "?") for target in targets))
    print("* Change config files:")
    print("  nano config/qa-config.yaml")
    print("  nano config/targets.yaml")


def ensure_workspace(args: argparse.Namespace) -> None:
    print_header("Workspace State")
    if not args.check_only:
        RESULTS_DIR.mkdir(exist_ok=True)
        for path in AGENTS_DIR.glob("*.sh"):
            ensure_executable(path)
        for path in SCRIPTS_DIR.glob("*.sh"):
            ensure_executable(path)
    print(f"* results/: {'present' if RESULTS_DIR.exists() else 'missing'}")
    print("* Shell scripts executable: yes")


def summarize_prereqs() -> bool:
    print_header("Prerequisites")
    required = {
        "git": shutil.which("git"),
        "python3": shutil.which("python3"),
        "aws": shutil.which("aws"),
    }
    ok = True
    for name, location in required.items():
        state = "found" if location else "missing"
        print(f"* {name}: {state}{f' ({location})' if location else ''}")
        ok = ok and bool(location)
    try:
        import yaml as _yaml  # noqa: F401

        print("* PyYAML: found")
    except Exception:
        print("* PyYAML: missing")
        ok = False
    print("* Install missing Python dependency:")
    print("  pip3 install pyyaml ruff")
    return ok


def summarize_recent_usage() -> None:
    print_header("Recent Audit Activity")
    audit_log = ROOT / "results" / "local-audit-log.json"
    if not audit_log.exists():
        print("* No local-audit-log.json found yet.")
        print("  Run: python3 scripts/backoffice-cli.py audit-all")
        return
    payload = load_yaml(audit_log)
    runs = payload.get("recent_runs", []) if isinstance(payload, dict) else []
    print(f"* Recorded recent runs: {len(runs)}")
    if not runs:
        print("  Run: python3 scripts/backoffice-cli.py audit-all")
        return
    latest = runs[-1]
    print(f"* Latest run target: {latest.get('repo_name', 'unknown')}")
    print(f"* Latest run status: {latest.get('status', 'unknown')}")
    jobs = latest.get("jobs", {}) if isinstance(latest.get("jobs"), dict) else {}
    if jobs:
        print("* Latest run departments:")
        for name, job in jobs.items():
            agent = job.get("agent_runner") or job.get("agent") or "n/a"
            mode = job.get("agent_mode") or "n/a"
            status = job.get("status", "unknown")
            elapsed = job.get("elapsed_seconds")
            findings = job.get("findings_count")
            print(
                f"  - {name}: status={status}, findings={findings if findings is not None else 'n/a'}, elapsed={elapsed if elapsed is not None else 'n/a'}s, runner={agent}, mode={mode}"
            )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    print("Back Office Setup")
    print("=================")
    summarize_prereqs()
    summarize_runner()
    summarize_agent_scripts()
    summarize_config_state(args)
    ensure_workspace(args)
    summarize_recent_usage()

    print_header("Useful Commands")
    print("* Run all configured targets:")
    print("  python3 scripts/backoffice-cli.py audit-all")
    print("* Run all configured targets for selected departments:")
    print("  python3 scripts/backoffice-cli.py audit-all --departments qa,product")
    print("* Refresh dashboard payloads without rerunning scans:")
    print("  python3 scripts/backoffice-cli.py refresh")
    print("* Open metrics dashboard after refresh/deploy:")
    print("  https://admin.codyjo.com/metrics.html")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
