"""Generate delivery automation metadata for the Back Office dashboard.

Ported from scripts/generate-delivery-data.py. Accepts paths as function
arguments / Config object instead of env-var-only lookups, and uses
structured logging instead of print().
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (identical to original)
# ---------------------------------------------------------------------------

WORKFLOW_FILE_GLOBS = ("*.yml", "*.yaml")
SAFE_EFFORTS = {"tiny", "small", "low", "medium"}
SAFE_SEVERITIES = {"info", "low", "medium"}
RISKY_KEYWORDS = (
    "auth",
    "login",
    "register",
    "password",
    "token",
    "jwt",
    "payment",
    "billing",
    "subscription",
    "privacy",
    "consent",
    "gdpr",
    "security",
    "iam",
    "terraform",
    "cloudfront",
    "database migration",
    "dynamodb",
)
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
DEPARTMENT_FILES = {
    "qa": "findings.json",
    "seo": "seo-findings.json",
    "ada": "ada-findings.json",
    "compliance": "compliance-findings.json",
    "privacy": "privacy-findings.json",
    "monetization": "monetization-findings.json",
    "product": "product-findings.json",
}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def iso_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path):
    """Load a YAML file, returning an empty dict on missing/empty file."""
    with path.open() as handle:
        return yaml.safe_load(handle) or {}


def load_json(path: Path):
    """Load a JSON file, returning None on missing file or parse error."""
    try:
        with path.open() as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def load_targets_config(
    config_path: Path | None = None,
    example_config_path: Path | None = None,
):
    """Load the targets configuration from YAML.

    Tries *config_path* first, falls back to *example_config_path*, and
    returns ``{"targets": []}`` if neither exists.
    """
    if config_path is None:
        root = Path(os.environ.get("BACK_OFFICE_ROOT", Path(__file__).resolve().parents[1]))
        config_path = Path(
            os.environ.get("BACK_OFFICE_TARGETS_CONFIG", root / "config" / "targets.yaml")
        )
    if example_config_path is None:
        root = Path(os.environ.get("BACK_OFFICE_ROOT", Path(__file__).resolve().parents[1]))
        example_config_path = root / "config" / "targets.example.yaml"

    if config_path.exists():
        return load_yaml(config_path)
    if example_config_path.exists():
        return load_yaml(example_config_path)
    return {"targets": []}


# ---------------------------------------------------------------------------
# Workflow detection
# ---------------------------------------------------------------------------

def list_workflows(repo_path: Path) -> list[dict]:
    """Return a list of parsed workflow dicts from .github/workflows/."""
    workflow_dir = repo_path / ".github" / "workflows"
    files: list[Path] = []
    if not workflow_dir.exists():
        return files
    for pattern in WORKFLOW_FILE_GLOBS:
        files.extend(sorted(workflow_dir.glob(pattern)))

    workflows = []
    for file_path in files:
        content = file_path.read_text()
        try:
            parsed = yaml.safe_load(content) or {}
        except yaml.YAMLError:
            parsed = {}
        workflows.append(
            {
                "file": file_path.name,
                "name": parsed.get("name") or file_path.stem,
                "on": parsed.get("on"),
                "jobs": list((parsed.get("jobs") or {}).keys()),
                "content": content,
            }
        )
    return workflows


def contains_schedule(trigger) -> bool:
    """Return True if the workflow trigger includes a schedule."""
    if isinstance(trigger, dict):
        return "schedule" in trigger
    if isinstance(trigger, list):
        return "schedule" in trigger
    return trigger == "schedule"


def contains_pull_request(trigger) -> bool:
    """Return True if the workflow trigger includes pull_request."""
    if isinstance(trigger, dict):
        return "pull_request" in trigger
    if isinstance(trigger, list):
        return "pull_request" in trigger
    return trigger == "pull_request"


def contains_push_main(trigger) -> bool:
    """Return True if the workflow trigger includes a push to main."""
    if not isinstance(trigger, dict):
        return False
    push = trigger.get("push")
    if push is True:
        return True
    if isinstance(push, dict):
        branches = push.get("branches") or []
        return "main" in branches or not branches
    return False


def detect_workflow_status(workflows: list[dict]) -> dict:
    """Classify a list of workflow dicts into ci/preview/cd/nightly status."""
    statuses = {
        "ci": {"configured": False, "workflow": "", "status": "missing"},
        "preview": {"configured": False, "workflow": "", "status": "missing"},
        "cd": {"configured": False, "workflow": "", "status": "missing"},
        "nightly": {"configured": False, "workflow": "", "status": "missing"},
    }

    for workflow in workflows:
        file_name = workflow["file"].lower()
        name = workflow["name"].lower()
        content = workflow["content"].lower()
        trigger = workflow["on"]

        if (
            contains_pull_request(trigger)
            or "ci" in file_name
            or "validate" in name
            or "test" in name
        ) and not statuses["ci"]["configured"]:
            statuses["ci"] = {
                "configured": True,
                "workflow": workflow["file"],
                "status": "configured",
            }

        if (
            "preview" in file_name
            or "preview" in name
            or "staging" in name
            or "environment: staging" in content
            or "environment: preview" in content
            or "preview-url" in content
        ) and not statuses["preview"]["configured"]:
            statuses["preview"] = {
                "configured": True,
                "workflow": workflow["file"],
                "status": "configured",
            }

        if (
            contains_push_main(trigger)
            or "deploy" in file_name
            or "deploy" in name
            or "environment: production" in content
        ) and not statuses["cd"]["configured"]:
            statuses["cd"] = {
                "configured": True,
                "workflow": workflow["file"],
                "status": "configured",
            }

        if (
            contains_schedule(trigger)
            or "nightly" in file_name
            or "nightly" in name
            or "schedule:" in content
            or "backoffice" in file_name
        ) and not statuses["nightly"]["configured"]:
            statuses["nightly"] = {
                "configured": True,
                "workflow": workflow["file"],
                "status": "configured",
            }

    return statuses


# ---------------------------------------------------------------------------
# Command coverage detection
# ---------------------------------------------------------------------------

def read_package_scripts(repo_path: Path) -> dict:
    """Return the ``scripts`` dict from package.json, or {} if absent."""
    package_json = load_json(repo_path / "package.json")
    if not package_json:
        return {}
    scripts = package_json.get("scripts")
    return scripts if isinstance(scripts, dict) else {}


def detect_command_coverage(target: dict, repo_path: Path) -> dict:
    """Return lint/test/build/coverage coverage status for a target."""
    package_scripts = read_package_scripts(repo_path) if repo_path.exists() else {}

    def has_script(*names: str) -> bool:
        return any(name in package_scripts for name in names)

    return {
        "lint": {
            "configured": bool(target.get("lint_command")),
            "status": "configured" if target.get("lint_command") else "missing",
            "command": target.get("lint_command", ""),
            "script_detected": has_script("lint", "check"),
        },
        "test": {
            "configured": bool(target.get("test_command")),
            "status": "configured" if target.get("test_command") else "missing",
            "command": target.get("test_command", ""),
            "script_detected": has_script("test"),
        },
        "build": {
            "configured": bool(target.get("deploy_command")),
            "status": "configured" if target.get("deploy_command") else "missing",
            "command": target.get("deploy_command", ""),
            "script_detected": has_script("build"),
        },
        "coverage": {
            "configured": bool(target.get("coverage_command")),
            "status": "configured" if target.get("coverage_command") else "missing",
            "command": target.get("coverage_command", ""),
            "script_detected": has_script("test:coverage", "coverage"),
        },
    }


# ---------------------------------------------------------------------------
# Findings + candidate logic
# ---------------------------------------------------------------------------

def find_product_key(repo_name: str, products: list[dict]) -> str:
    """Return the product key for a repo, defaulting to ``'all'``."""
    for product in products:
        if repo_name in (product.get("repos") or []):
            return product.get("key", "all")
    return "all"


def read_findings(repo_name: str, results_dir: Path) -> dict:
    """Load all department findings for *repo_name* from *results_dir*."""
    repo_dir = results_dir / repo_name
    findings: dict[str, list] = {}
    for department, filename in DEPARTMENT_FILES.items():
        payload = load_json(repo_dir / filename)
        if payload:
            findings[department] = payload.get("findings") or []
    return findings


def is_safe_candidate(department: str, finding: dict) -> bool:
    """Return True if *finding* is safe for unattended overnight fixing."""
    severity = str(finding.get("severity", "info")).lower()
    effort = str(finding.get("effort", "")).lower()
    status = str(finding.get("status", "open")).lower()
    title = " ".join(
        str(finding.get(field, "")).lower()
        for field in ("title", "category", "description", "fix", "file")
    )
    fixable = bool(finding.get("fixable") or finding.get("fixable_by_agent"))

    if department in {"compliance", "privacy"}:
        return False
    if status not in {"open", "in-progress", ""}:
        return False
    if not fixable:
        return False
    if severity not in SAFE_SEVERITIES:
        return False
    if effort and effort not in SAFE_EFFORTS:
        return False
    return not any(keyword in title for keyword in RISKY_KEYWORDS)


def overnight_bucket(finding: dict) -> str:
    """Classify a finding into an overnight scheduling bucket."""
    severity = str(finding.get("severity", "info")).lower()
    effort = str(finding.get("effort", "")).lower()
    if severity in {"low", "info"} and effort in {"tiny", "small", "low"}:
        return "Overnight Now"
    if severity == "medium" and effort in {"small", "medium", "low"}:
        return "Next Overnight"
    return "Needs Review"


def sprint_bucket(finding: dict) -> str:
    """Classify a product finding into a sprint scheduling bucket."""
    phase = str(finding.get("priority_phase", "")).lower()
    if phase == "must-have":
        return "Sprint Now"
    if phase == "should-have":
        return "Next Sprint"
    if phase == "nice-to-have":
        return "Later Sprint"
    severity = str(finding.get("severity", "info")).lower()
    if severity in {"critical", "high"}:
        return "Sprint Now"
    if severity == "medium":
        return "Next Sprint"
    return "Backlog"


def summarize_candidates(repo_name: str, findings_by_department: dict) -> dict:
    """Build safe-candidate and sprint-lane summaries from all department findings."""
    candidates: list[dict] = []
    sprint_map: dict[str, list[dict]] = {}

    for department, findings in findings_by_department.items():
        for finding in findings:
            if is_safe_candidate(department, finding):
                candidate = {
                    "repo": repo_name,
                    "department": department,
                    "id": finding.get("id", ""),
                    "title": finding.get("title", "Untitled finding"),
                    "severity": str(finding.get("severity", "info")).lower(),
                    "effort": str(finding.get("effort", "unknown")).lower(),
                    "file": finding.get("file", ""),
                    "reason": "Low-risk, fixable, and testable for unattended work.",
                    "bucket": overnight_bucket(finding),
                }
                candidates.append(candidate)

            if department == "product":
                lane = sprint_bucket(finding)
                sprint_map.setdefault(lane, []).append(
                    {
                        "repo": repo_name,
                        "title": finding.get("title", "Untitled finding"),
                        "severity": str(finding.get("severity", "info")).lower(),
                        "effort": str(finding.get("effort", "unknown")).lower(),
                        "status": str(finding.get("status", "open")).lower(),
                    }
                )

    candidates.sort(key=lambda item: (SEVERITY_ORDER.get(item["severity"], 9), item["title"]))
    ordered_lanes = []
    for lane in ("Sprint Now", "Next Sprint", "Later Sprint", "Backlog"):
        items = sprint_map.get(lane, [])
        if not items:
            continue
        items.sort(key=lambda item: (SEVERITY_ORDER.get(item["severity"], 9), item["title"]))
        ordered_lanes.append({"lane": lane, "items": items[:6]})

    return {
        "safe_candidate_count": len(candidates),
        "safe_candidates": candidates[:12],
        "sprint_lanes": ordered_lanes,
    }


# ---------------------------------------------------------------------------
# Readiness scoring
# ---------------------------------------------------------------------------

def delivery_readiness(workflows: dict, commands: dict, candidate_count: int) -> int:
    """Compute a 0–100 delivery readiness score."""
    score = 0
    score += 30 if workflows["ci"]["configured"] else 0
    score += 20 if commands["test"]["configured"] else 0
    score += 15 if commands["lint"]["configured"] else 0
    score += 15 if commands["build"]["configured"] else 0
    score += 10 if workflows["preview"]["configured"] else 0
    score += 5 if workflows["cd"]["configured"] else 0
    score += 5 if workflows["nightly"]["configured"] else 0
    if candidate_count:
        score += 5
    return min(score, 100)


# ---------------------------------------------------------------------------
# Per-target summary
# ---------------------------------------------------------------------------

def target_summary(target: dict, products: list[dict], results_dir: Path) -> dict:
    """Build the full delivery summary dict for a single target."""
    repo_name = target["name"]
    repo_path = Path(target["path"])
    workflows = (
        detect_workflow_status(list_workflows(repo_path))
        if repo_path.exists()
        else detect_workflow_status([])
    )
    commands = detect_command_coverage(target, repo_path)
    findings_by_department = read_findings(repo_name, results_dir)
    candidate_summary = summarize_candidates(repo_name, findings_by_department)
    readiness = delivery_readiness(workflows, commands, candidate_summary["safe_candidate_count"])

    return {
        "repo": repo_name,
        "path": str(repo_path),
        "product_key": find_product_key(repo_name, products),
        "language": target.get("language", ""),
        "workflows": workflows,
        "commands": commands,
        "delivery_readiness": readiness,
        "overnight": {
            "safe_candidate_count": candidate_summary["safe_candidate_count"],
            "safe_candidates": candidate_summary["safe_candidates"],
        },
        "sprints": candidate_summary["sprint_lanes"],
        "pr_status": "pr-required" if workflows["ci"]["configured"] else "workflow-missing",
        "preview_status": "configured" if workflows["preview"]["configured"] else "missing",
        "production_status": "approval-gated" if workflows["cd"]["configured"] else "missing",
        "nightly_status": "scheduled" if workflows["nightly"]["configured"] else "missing",
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(config=None) -> int:
    """Generate automation-data.json from targets config and results.

    Args:
        config: Optional ``backoffice.config.Config`` instance. When provided
            its ``root`` path is used to resolve default directory locations.
            Explicit path keyword arguments take precedence.

    Returns:
        0 on success.
    """
    # Resolve root from config object or env/default
    if config is not None:
        default_root = config.root
    else:
        default_root = Path(
            os.environ.get("BACK_OFFICE_ROOT", Path(__file__).resolve().parents[1])
        )

    results_dir = Path(os.environ.get("BACK_OFFICE_RESULTS_DIR", default_root / "results"))
    dashboard_dir = Path(
        os.environ.get("BACK_OFFICE_DASHBOARD_DIR", default_root / "dashboard")
    )
    output_path = Path(
        os.environ.get("BACK_OFFICE_DELIVERY_OUTPUT", dashboard_dir / "automation-data.json")
    )

    # Use new Config.targets if available, otherwise fall back to targets.yaml
    if config is not None and config.targets:
        raw_targets = [
            {
                "name": name,
                "path": target.path,
                "language": target.language,
                "lint_command": target.lint_command,
                "test_command": target.test_command,
                "deploy_command": target.deploy_command,
                "coverage_command": target.coverage_command,
            }
            for name, target in config.targets.items()
        ]
    else:
        targets_config = load_targets_config()
        raw_targets = targets_config.get("targets") or []

    org_data = load_json(dashboard_dir / "org-data.json") or {"products": []}
    products = org_data.get("products") or []

    payload = {
        "generated_at": iso_now(),
        "targets": [
            target_summary(target, products, results_dir) for target in raw_targets
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")

    logger.info(
        "Delivery data written to %s (%d targets)",
        output_path,
        len(payload["targets"]),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
