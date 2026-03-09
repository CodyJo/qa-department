#!/usr/bin/env python3
"""Aggregate all results/ subdirectories into a single dashboard JSON payload."""

import json
import os
import sys
from datetime import datetime, timezone


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def aggregate(results_dir, output_path):
    repos = []
    totals = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0,
              "total_findings": 0, "total_fixed": 0, "total_failed": 0,
              "total_skipped": 0, "total_in_progress": 0}

    if not os.path.isdir(results_dir):
        print(f"Results directory not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    for repo_name in sorted(os.listdir(results_dir)):
        repo_dir = os.path.join(results_dir, repo_name)
        if not os.path.isdir(repo_dir):
            continue

        findings_data = load_json(os.path.join(repo_dir, "findings.json"))
        fixes_data = load_json(os.path.join(repo_dir, "fixes.json"))

        if not findings_data:
            continue

        summary = findings_data.get("summary", {})
        findings = findings_data.get("findings", [])

        # Build fix status lookup
        fix_map = {}
        if fixes_data:
            for fix in fixes_data.get("fixes", []):
                fix_map[fix["finding_id"]] = fix

        # Enrich findings with fix status
        enriched = []
        for f in findings:
            fid = f["id"]
            fix_info = fix_map.get(fid, {})
            enriched.append({
                "id": fid,
                "severity": f["severity"],
                "category": f["category"],
                "title": f["title"],
                "file": f.get("file", ""),
                "line": f.get("line"),
                "effort": f.get("effort", "unknown"),
                "fixable": f.get("fixable_by_agent", False),
                "status": fix_info.get("status", "open"),
                "commit": fix_info.get("commit_hash", ""),
                "fixed_at": fix_info.get("fixed_at", ""),
            })

        # Count statuses
        fixed = sum(1 for e in enriched if e["status"] == "fixed")
        failed = sum(1 for e in enriched if e["status"] == "failed")
        skipped = sum(1 for e in enriched if e["status"] == "skipped")
        in_progress = sum(1 for e in enriched if e["status"] == "in-progress")

        totals["critical"] += summary.get("critical", 0)
        totals["high"] += summary.get("high", 0)
        totals["medium"] += summary.get("medium", 0)
        totals["low"] += summary.get("low", 0)
        totals["info"] += summary.get("info", 0)
        totals["total_findings"] += summary.get("total", 0)
        totals["total_fixed"] += fixed
        totals["total_failed"] += failed
        totals["total_skipped"] += skipped
        totals["total_in_progress"] += in_progress

        repos.append({
            "name": repo_name,
            "scanned_at": findings_data.get("scanned_at", ""),
            "summary": summary,
            "fix_summary": {
                "fixed": fixed,
                "failed": failed,
                "skipped": skipped,
                "in_progress": in_progress,
                "open": len(enriched) - fixed - failed - skipped - in_progress,
            },
            "lint": findings_data.get("lint_results", {}),
            "tests": findings_data.get("test_results", {}),
            "findings": enriched,
        })

    dashboard = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": totals,
        "repos": repos,
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(dashboard, f, indent=2)

    print(f"Dashboard data: {totals['total_findings']} findings across "
          f"{len(repos)} repos, {totals['total_fixed']} fixed")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: aggregate-results.py <results-dir> <output.json>",
              file=sys.stderr)
        sys.exit(1)
    aggregate(sys.argv[1], sys.argv[2])
