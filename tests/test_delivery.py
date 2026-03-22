"""Tests for backoffice.delivery."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest
import yaml

from backoffice.delivery import (
    DEPARTMENT_FILES,
    RISKY_KEYWORDS,
    SAFE_EFFORTS,
    SAFE_SEVERITIES,
    SEVERITY_ORDER,
    contains_pull_request,
    contains_push_main,
    contains_schedule,
    delivery_readiness,
    detect_command_coverage,
    detect_workflow_status,
    find_product_key,
    is_safe_candidate,
    iso_now,
    list_workflows,
    load_json,
    load_targets_config,
    load_yaml,
    main,
    overnight_bucket,
    read_findings,
    read_package_scripts,
    sprint_bucket,
    summarize_candidates,
    target_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f)


def _write_yaml(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.dump(data, f)


def _workflow(tmp_path: Path, filename: str, content: str) -> Path:
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    p = wf_dir / filename
    p.write_text(content)
    return p


def _make_finding(
    *,
    id="F1",
    severity="low",
    effort="small",
    status="open",
    fixable=True,
    title="Fix something",
    category="test",
    description="",
    fix="",
    file="app.py",
    priority_phase="",
):
    return {
        "id": id,
        "severity": severity,
        "effort": effort,
        "status": status,
        "fixable_by_agent": fixable,
        "title": title,
        "category": category,
        "description": description,
        "fix": fix,
        "file": file,
        "priority_phase": priority_phase,
    }


# ---------------------------------------------------------------------------
# iso_now
# ---------------------------------------------------------------------------

class TestIsoNow:
    def test_returns_string(self):
        assert isinstance(iso_now(), str)

    def test_ends_with_utc_offset(self):
        ts = iso_now()
        # ISO 8601 UTC either ends with +00:00 or Z
        assert "+" in ts or ts.endswith("Z")


# ---------------------------------------------------------------------------
# load_yaml / load_json
# ---------------------------------------------------------------------------

class TestLoadYaml:
    def test_loads_valid_yaml(self, tmp_path):
        p = tmp_path / "data.yaml"
        p.write_text("key: value\n")
        result = load_yaml(p)
        assert result == {"key": "value"}

    def test_empty_yaml_returns_empty_dict(self, tmp_path):
        p = tmp_path / "empty.yaml"
        p.write_text("")
        result = load_yaml(p)
        assert result == {}


class TestLoadJson:
    def test_loads_valid_json(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text('{"a": 1}')
        assert load_json(p) == {"a": 1}

    def test_missing_file_returns_none(self, tmp_path):
        assert load_json(tmp_path / "missing.json") is None

    def test_malformed_json_returns_none(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{broken")
        assert load_json(p) is None


# ---------------------------------------------------------------------------
# load_targets_config
# ---------------------------------------------------------------------------

class TestLoadTargetsConfig:
    def test_returns_empty_targets_when_no_files(self, tmp_path):
        result = load_targets_config(
            config_path=tmp_path / "nonexistent.yaml",
            example_config_path=tmp_path / "nonexistent-example.yaml",
        )
        assert result == {"targets": []}

    def test_loads_config_path_when_exists(self, tmp_path):
        p = tmp_path / "targets.yaml"
        _write_yaml(p, {"targets": [{"name": "repo-a", "path": "/tmp/repo-a"}]})
        result = load_targets_config(config_path=p)
        assert len(result["targets"]) == 1
        assert result["targets"][0]["name"] == "repo-a"

    def test_falls_back_to_example_when_config_missing(self, tmp_path):
        example = tmp_path / "targets.example.yaml"
        _write_yaml(example, {"targets": [{"name": "example-repo", "path": "/tmp/ex"}]})
        result = load_targets_config(
            config_path=tmp_path / "nonexistent.yaml",
            example_config_path=example,
        )
        assert result["targets"][0]["name"] == "example-repo"

    def test_config_path_takes_precedence_over_example(self, tmp_path):
        config = tmp_path / "targets.yaml"
        example = tmp_path / "targets.example.yaml"
        _write_yaml(config, {"targets": [{"name": "real"}]})
        _write_yaml(example, {"targets": [{"name": "example"}]})
        result = load_targets_config(config_path=config, example_config_path=example)
        assert result["targets"][0]["name"] == "real"


# ---------------------------------------------------------------------------
# list_workflows
# ---------------------------------------------------------------------------

class TestListWorkflows:
    def test_no_workflows_dir_returns_empty(self, tmp_path):
        result = list_workflows(tmp_path)
        assert result == []

    def test_parses_workflow_name_and_trigger(self, tmp_path):
        content = "name: CI\non:\n  pull_request:\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps: []\n"
        _workflow(tmp_path, "ci.yml", content)
        result = list_workflows(tmp_path)
        assert len(result) == 1
        assert result[0]["name"] == "CI"
        assert result[0]["file"] == "ci.yml"

    def test_falls_back_to_stem_when_no_name(self, tmp_path):
        _workflow(tmp_path, "my-workflow.yml", "on: push\njobs: {}\n")
        result = list_workflows(tmp_path)
        assert result[0]["name"] == "my-workflow"

    def test_lists_yml_and_yaml_extensions(self, tmp_path):
        _workflow(tmp_path, "a.yml", "name: A\non: push\njobs: {}\n")
        _workflow(tmp_path, "b.yaml", "name: B\non: push\njobs: {}\n")
        result = list_workflows(tmp_path)
        names = {w["file"] for w in result}
        assert "a.yml" in names
        assert "b.yaml" in names

    def test_invalid_yaml_results_in_empty_parsed(self, tmp_path):
        _workflow(tmp_path, "broken.yml", ": :\n  bad: [yaml")
        result = list_workflows(tmp_path)
        assert result[0]["jobs"] == []

    def test_jobs_extracted_as_keys(self, tmp_path):
        content = (
            "name: Full\non: push\njobs:\n  build:\n    steps: []\n  test:\n    steps: []\n"
        )
        _workflow(tmp_path, "full.yml", content)
        result = list_workflows(tmp_path)
        assert set(result[0]["jobs"]) == {"build", "test"}


# ---------------------------------------------------------------------------
# contains_schedule / contains_pull_request / contains_push_main
# ---------------------------------------------------------------------------

class TestContainsSchedule:
    def test_dict_with_schedule_key(self):
        assert contains_schedule({"schedule": [{"cron": "0 0 * * *"}]}) is True

    def test_dict_without_schedule_key(self):
        assert contains_schedule({"push": {}}) is False

    def test_list_containing_schedule_string(self):
        assert contains_schedule(["schedule", "push"]) is True

    def test_list_without_schedule(self):
        assert contains_schedule(["push", "pull_request"]) is False

    def test_bare_schedule_string(self):
        assert contains_schedule("schedule") is True

    def test_other_string(self):
        assert contains_schedule("push") is False

    def test_none_returns_false(self):
        assert contains_schedule(None) is False


class TestContainsPullRequest:
    def test_dict_with_pull_request_key(self):
        assert contains_pull_request({"pull_request": {}}) is True

    def test_dict_without_pull_request(self):
        assert contains_pull_request({"push": {}}) is False

    def test_list_containing_pull_request(self):
        assert contains_pull_request(["push", "pull_request"]) is True

    def test_list_without_pull_request(self):
        assert contains_pull_request(["push"]) is False

    def test_bare_pull_request_string(self):
        assert contains_pull_request("pull_request") is True

    def test_other_string(self):
        assert contains_pull_request("push") is False


class TestContainsPushMain:
    def test_push_with_main_in_branches(self):
        trigger = {"push": {"branches": ["main"]}}
        assert contains_push_main(trigger) is True

    def test_push_with_no_branches_filter(self):
        trigger = {"push": {}}
        assert contains_push_main(trigger) is True

    def test_push_true_matches(self):
        trigger = {"push": True}
        assert contains_push_main(trigger) is True

    def test_push_without_main_branch(self):
        trigger = {"push": {"branches": ["develop"]}}
        assert contains_push_main(trigger) is False

    def test_non_dict_trigger_returns_false(self):
        assert contains_push_main("push") is False
        assert contains_push_main(["push"]) is False
        assert contains_push_main(None) is False

    def test_no_push_key_returns_false(self):
        assert contains_push_main({"pull_request": {}}) is False


# ---------------------------------------------------------------------------
# detect_workflow_status
# ---------------------------------------------------------------------------

class TestDetectWorkflowStatus:
    def test_empty_workflows_all_missing(self):
        result = detect_workflow_status([])
        for key in ("ci", "preview", "cd", "nightly"):
            assert result[key]["configured"] is False
            assert result[key]["status"] == "missing"

    def test_ci_detected_via_pull_request_trigger(self):
        workflow = {
            "file": "check.yml",
            "name": "check",
            "on": {"pull_request": {}},
            "content": "",
        }
        result = detect_workflow_status([workflow])
        assert result["ci"]["configured"] is True
        assert result["ci"]["workflow"] == "check.yml"

    def test_ci_detected_via_filename(self):
        workflow = {"file": "ci.yml", "name": "build", "on": "push", "content": ""}
        result = detect_workflow_status([workflow])
        assert result["ci"]["configured"] is True

    def test_ci_detected_via_name_containing_test(self):
        workflow = {"file": "build.yml", "name": "run tests", "on": "push", "content": ""}
        result = detect_workflow_status([workflow])
        assert result["ci"]["configured"] is True

    def test_ci_detected_via_name_containing_validate(self):
        workflow = {"file": "check.yml", "name": "validate config", "on": "push", "content": ""}
        result = detect_workflow_status([workflow])
        assert result["ci"]["configured"] is True

    def test_preview_detected_via_filename(self):
        workflow = {"file": "preview.yml", "name": "deploy", "on": "push", "content": ""}
        result = detect_workflow_status([workflow])
        assert result["preview"]["configured"] is True

    def test_preview_detected_via_content(self):
        workflow = {
            "file": "deploy.yml",
            "name": "deploy",
            "on": "push",
            "content": "environment: preview\n",
        }
        result = detect_workflow_status([workflow])
        assert result["preview"]["configured"] is True

    def test_preview_detected_via_preview_url_in_content(self):
        workflow = {
            "file": "pr.yml",
            "name": "pr",
            "on": {"pull_request": {}},
            "content": "preview-url: https://example.com\n",
        }
        result = detect_workflow_status([workflow])
        assert result["preview"]["configured"] is True

    def test_cd_detected_via_push_main_trigger(self):
        workflow = {
            "file": "release.yml",
            "name": "release",
            "on": {"push": {"branches": ["main"]}},
            "content": "",
        }
        result = detect_workflow_status([workflow])
        assert result["cd"]["configured"] is True

    def test_cd_detected_via_deploy_in_filename(self):
        workflow = {"file": "deploy.yml", "name": "build", "on": "push", "content": ""}
        result = detect_workflow_status([workflow])
        assert result["cd"]["configured"] is True

    def test_cd_detected_via_production_environment_in_content(self):
        workflow = {
            "file": "ship.yml",
            "name": "ship",
            "on": "push",
            "content": "environment: production\n",
        }
        result = detect_workflow_status([workflow])
        assert result["cd"]["configured"] is True

    def test_nightly_detected_via_schedule_trigger(self):
        workflow = {
            "file": "audit.yml",
            "name": "audit",
            "on": {"schedule": [{"cron": "0 2 * * *"}]},
            "content": "",
        }
        result = detect_workflow_status([workflow])
        assert result["nightly"]["configured"] is True

    def test_nightly_detected_via_filename(self):
        workflow = {"file": "nightly.yml", "name": "build", "on": "push", "content": ""}
        result = detect_workflow_status([workflow])
        assert result["nightly"]["configured"] is True

    def test_nightly_detected_via_backoffice_in_filename(self):
        workflow = {"file": "backoffice-scan.yml", "name": "scan", "on": "push", "content": ""}
        result = detect_workflow_status([workflow])
        assert result["nightly"]["configured"] is True

    def test_nightly_detected_via_schedule_in_content(self):
        workflow = {
            "file": "scan.yml",
            "name": "scan",
            "on": "push",
            "content": "schedule:\n  - cron: '0 0 * * *'\n",
        }
        result = detect_workflow_status([workflow])
        assert result["nightly"]["configured"] is True

    def test_first_matching_workflow_wins(self):
        """Only the first CI workflow should be recorded."""
        w1 = {"file": "ci-first.yml", "name": "CI First", "on": {"pull_request": {}}, "content": ""}
        w2 = {"file": "ci-second.yml", "name": "CI Second", "on": {"pull_request": {}}, "content": ""}
        result = detect_workflow_status([w1, w2])
        assert result["ci"]["workflow"] == "ci-first.yml"


# ---------------------------------------------------------------------------
# read_package_scripts
# ---------------------------------------------------------------------------

class TestReadPackageScripts:
    def test_returns_scripts_from_package_json(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps({"scripts": {"test": "jest", "build": "vite build"}}))
        result = read_package_scripts(tmp_path)
        assert result["test"] == "jest"

    def test_missing_package_json_returns_empty(self, tmp_path):
        result = read_package_scripts(tmp_path)
        assert result == {}

    def test_malformed_package_json_returns_empty(self, tmp_path):
        (tmp_path / "package.json").write_text("{bad json")
        result = read_package_scripts(tmp_path)
        assert result == {}

    def test_scripts_not_a_dict_returns_empty(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({"scripts": ["array"]}))
        result = read_package_scripts(tmp_path)
        assert result == {}


# ---------------------------------------------------------------------------
# detect_command_coverage
# ---------------------------------------------------------------------------

class TestDetectCommandCoverage:
    def test_all_configured_when_commands_present(self, tmp_path):
        target = {
            "lint_command": "npm run lint",
            "test_command": "npm test",
            "deploy_command": "npm run build",
            "coverage_command": "npm run coverage",
        }
        result = detect_command_coverage(target, tmp_path)
        assert result["lint"]["configured"] is True
        assert result["test"]["configured"] is True
        assert result["build"]["configured"] is True
        assert result["coverage"]["configured"] is True

    def test_all_missing_when_no_commands(self, tmp_path):
        result = detect_command_coverage({}, tmp_path)
        for key in ("lint", "test", "build", "coverage"):
            assert result[key]["configured"] is False
            assert result[key]["status"] == "missing"

    def test_script_detected_from_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"scripts": {"test": "jest", "lint": "eslint ."}})
        )
        result = detect_command_coverage({}, tmp_path)
        assert result["test"]["script_detected"] is True
        assert result["lint"]["script_detected"] is True
        assert result["build"]["script_detected"] is False

    def test_coverage_script_detected_via_test_coverage(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"scripts": {"test:coverage": "jest --coverage"}})
        )
        result = detect_command_coverage({}, tmp_path)
        assert result["coverage"]["script_detected"] is True

    def test_nonexistent_repo_path_returns_no_scripts_detected(self, tmp_path):
        fake_path = tmp_path / "does-not-exist"
        result = detect_command_coverage({}, fake_path)
        for key in ("lint", "test", "build", "coverage"):
            assert result[key]["script_detected"] is False

    def test_command_stored_in_result(self, tmp_path):
        target = {"lint_command": "ruff check ."}
        result = detect_command_coverage(target, tmp_path)
        assert result["lint"]["command"] == "ruff check ."

    def test_check_script_counts_as_lint(self, tmp_path):
        (tmp_path / "package.json").write_text(
            json.dumps({"scripts": {"check": "svelte-check"}})
        )
        result = detect_command_coverage({}, tmp_path)
        assert result["lint"]["script_detected"] is True


# ---------------------------------------------------------------------------
# find_product_key
# ---------------------------------------------------------------------------

class TestFindProductKey:
    def test_returns_matching_product_key(self):
        products = [{"key": "blog", "repos": ["my-blog", "blog-theme"]}]
        assert find_product_key("my-blog", products) == "blog"

    def test_returns_all_when_no_match(self):
        products = [{"key": "blog", "repos": ["other"]}]
        assert find_product_key("unknown-repo", products) == "all"

    def test_empty_products_returns_all(self):
        assert find_product_key("any-repo", []) == "all"

    def test_product_without_key_defaults_to_all(self):
        products = [{"repos": ["my-repo"]}]
        assert find_product_key("my-repo", products) == "all"

    def test_product_with_missing_repos_skipped(self):
        products = [{"key": "x"}]
        assert find_product_key("my-repo", products) == "all"


# ---------------------------------------------------------------------------
# read_findings
# ---------------------------------------------------------------------------

class TestReadFindings:
    def test_loads_findings_by_department(self, tmp_path):
        repo_dir = tmp_path / "my-repo"
        repo_dir.mkdir()
        _write_json(
            repo_dir / "findings.json",
            {"findings": [{"id": "Q1", "severity": "high", "title": "XSS"}]},
        )
        result = read_findings("my-repo", tmp_path)
        assert "qa" in result
        assert result["qa"][0]["id"] == "Q1"

    def test_missing_department_files_skipped(self, tmp_path):
        (tmp_path / "my-repo").mkdir()
        result = read_findings("my-repo", tmp_path)
        assert result == {}

    def test_empty_repo_dir_returns_empty(self, tmp_path):
        result = read_findings("nonexistent-repo", tmp_path)
        assert result == {}


# ---------------------------------------------------------------------------
# is_safe_candidate
# ---------------------------------------------------------------------------

class TestIsSafeCandidate:
    def test_safe_finding_returns_true(self):
        finding = _make_finding(severity="low", effort="small", fixable=True)
        assert is_safe_candidate("qa", finding) is True

    def test_compliance_department_always_rejected(self):
        finding = _make_finding(severity="info", effort="tiny", fixable=True)
        assert is_safe_candidate("compliance", finding) is False

    def test_privacy_department_always_rejected(self):
        finding = _make_finding(severity="info", effort="tiny", fixable=True)
        assert is_safe_candidate("privacy", finding) is False

    def test_non_open_status_rejected(self):
        finding = _make_finding(status="fixed")
        assert is_safe_candidate("qa", finding) is False

    def test_in_progress_status_allowed(self):
        finding = _make_finding(status="in-progress", severity="low", effort="small")
        assert is_safe_candidate("qa", finding) is True

    def test_not_fixable_rejected(self):
        finding = _make_finding(fixable=False)
        assert is_safe_candidate("qa", finding) is False

    def test_fixable_via_fixable_field(self):
        finding = _make_finding(fixable=False)
        finding["fixable"] = True
        del finding["fixable_by_agent"]
        assert is_safe_candidate("qa", finding) is True

    def test_high_severity_rejected(self):
        finding = _make_finding(severity="high")
        assert is_safe_candidate("qa", finding) is False

    def test_critical_severity_rejected(self):
        finding = _make_finding(severity="critical")
        assert is_safe_candidate("qa", finding) is False

    def test_large_effort_rejected(self):
        finding = _make_finding(effort="large")
        assert is_safe_candidate("qa", finding) is False

    def test_risky_keyword_in_title_rejected(self):
        for keyword in ("auth", "payment", "password", "terraform"):
            finding = _make_finding(title=f"Update {keyword} flow")
            assert is_safe_candidate("qa", finding) is False, f"keyword {keyword!r} not rejected"

    def test_risky_keyword_in_description_rejected(self):
        finding = _make_finding(description="This touches login logic")
        assert is_safe_candidate("qa", finding) is False

    def test_risky_keyword_in_category_rejected(self):
        finding = _make_finding(category="security-audit")
        assert is_safe_candidate("qa", finding) is False

    def test_medium_severity_allowed(self):
        finding = _make_finding(severity="medium", effort="small")
        assert is_safe_candidate("qa", finding) is True

    def test_info_severity_allowed(self):
        finding = _make_finding(severity="info", effort="tiny")
        assert is_safe_candidate("qa", finding) is True

    def test_blank_effort_not_rejected(self):
        """Effort field being empty should not disqualify the finding."""
        finding = _make_finding(effort="", severity="low")
        assert is_safe_candidate("qa", finding) is True

    def test_safe_severities_constant(self):
        assert SAFE_SEVERITIES == {"info", "low", "medium"}

    def test_safe_efforts_constant(self):
        assert "tiny" in SAFE_EFFORTS
        assert "large" not in SAFE_EFFORTS

    def test_risky_keywords_is_tuple_of_strings(self):
        assert isinstance(RISKY_KEYWORDS, tuple)
        assert all(isinstance(k, str) for k in RISKY_KEYWORDS)


# ---------------------------------------------------------------------------
# overnight_bucket
# ---------------------------------------------------------------------------

class TestOvernightBucket:
    def test_low_severity_tiny_effort_is_overnight_now(self):
        assert overnight_bucket({"severity": "low", "effort": "tiny"}) == "Overnight Now"

    def test_info_severity_small_effort_is_overnight_now(self):
        assert overnight_bucket({"severity": "info", "effort": "small"}) == "Overnight Now"

    def test_info_severity_low_effort_is_overnight_now(self):
        assert overnight_bucket({"severity": "info", "effort": "low"}) == "Overnight Now"

    def test_medium_severity_small_effort_is_next_overnight(self):
        assert overnight_bucket({"severity": "medium", "effort": "small"}) == "Next Overnight"

    def test_medium_severity_medium_effort_is_next_overnight(self):
        assert overnight_bucket({"severity": "medium", "effort": "medium"}) == "Next Overnight"

    def test_medium_severity_low_effort_is_next_overnight(self):
        assert overnight_bucket({"severity": "medium", "effort": "low"}) == "Next Overnight"

    def test_low_severity_large_effort_is_needs_review(self):
        assert overnight_bucket({"severity": "low", "effort": "large"}) == "Needs Review"

    def test_high_severity_falls_to_needs_review(self):
        assert overnight_bucket({"severity": "high", "effort": "small"}) == "Needs Review"

    def test_missing_fields_default_to_needs_review(self):
        # info severity + empty effort does not match 'tiny'|'small'|'low'
        result = overnight_bucket({})
        assert result == "Needs Review"


# ---------------------------------------------------------------------------
# sprint_bucket
# ---------------------------------------------------------------------------

class TestSprintBucket:
    def test_must_have_phase_is_sprint_now(self):
        assert sprint_bucket({"priority_phase": "must-have"}) == "Sprint Now"

    def test_should_have_phase_is_next_sprint(self):
        assert sprint_bucket({"priority_phase": "should-have"}) == "Next Sprint"

    def test_nice_to_have_phase_is_later_sprint(self):
        assert sprint_bucket({"priority_phase": "nice-to-have"}) == "Later Sprint"

    def test_critical_severity_falls_back_to_sprint_now(self):
        assert sprint_bucket({"severity": "critical"}) == "Sprint Now"

    def test_high_severity_falls_back_to_sprint_now(self):
        assert sprint_bucket({"severity": "high"}) == "Sprint Now"

    def test_medium_severity_falls_back_to_next_sprint(self):
        assert sprint_bucket({"severity": "medium"}) == "Next Sprint"

    def test_low_severity_falls_to_backlog(self):
        assert sprint_bucket({"severity": "low"}) == "Backlog"

    def test_info_severity_falls_to_backlog(self):
        assert sprint_bucket({"severity": "info"}) == "Backlog"

    def test_empty_finding_falls_to_backlog(self):
        assert sprint_bucket({}) == "Backlog"

    def test_phase_takes_precedence_over_severity(self):
        """must-have phase should win even if severity is info."""
        finding = {"priority_phase": "must-have", "severity": "info"}
        assert sprint_bucket(finding) == "Sprint Now"


# ---------------------------------------------------------------------------
# summarize_candidates
# ---------------------------------------------------------------------------

class TestSummarizeCandidates:
    def _safe_finding(self, id="F1", title="Fix lint", severity="low", effort="small"):
        return _make_finding(
            id=id, title=title, severity=severity, effort=effort, fixable=True
        )

    def test_safe_candidate_counted(self):
        findings = {"qa": [self._safe_finding()]}
        result = summarize_candidates("my-repo", findings)
        assert result["safe_candidate_count"] == 1

    def test_unsafe_finding_excluded(self):
        findings = {"qa": [_make_finding(fixable=False)]}
        result = summarize_candidates("my-repo", findings)
        assert result["safe_candidate_count"] == 0

    def test_compliance_findings_excluded(self):
        findings = {"compliance": [self._safe_finding()]}
        result = summarize_candidates("my-repo", findings)
        assert result["safe_candidate_count"] == 0

    def test_candidates_capped_at_12(self):
        findings = {
            "qa": [self._safe_finding(id=f"F{i}", title=f"Fix {i}") for i in range(20)]
        }
        result = summarize_candidates("my-repo", findings)
        assert len(result["safe_candidates"]) == 12

    def test_candidates_sorted_by_severity_then_title(self):
        findings = {
            "qa": [
                self._safe_finding(id="A", title="Z low", severity="low"),
                self._safe_finding(id="B", title="A low", severity="low"),
                self._safe_finding(id="C", title="A medium", severity="medium"),
            ]
        }
        result = summarize_candidates("my-repo", findings)
        titles = [c["title"] for c in result["safe_candidates"]]
        # SEVERITY_ORDER: medium=2, low=3 — lower index = higher severity = sorts first.
        # So medium findings sort before low findings.
        # Within the same severity, title is the tiebreaker (alphabetical).
        assert titles[0] == "A medium"
        assert titles[1] == "A low"
        assert titles[2] == "Z low"

    def test_candidate_has_required_fields(self):
        findings = {"qa": [self._safe_finding()]}
        result = summarize_candidates("my-repo", findings)
        candidate = result["safe_candidates"][0]
        for field in ("repo", "department", "id", "title", "severity", "effort", "file", "reason", "bucket"):
            assert field in candidate

    def test_sprint_lanes_populated_for_product_findings(self):
        product_finding = _make_finding(
            id="P1",
            title="Add onboarding",
            severity="high",
            effort="medium",
            priority_phase="must-have",
            fixable=False,
        )
        findings = {"product": [product_finding]}
        result = summarize_candidates("my-repo", findings)
        assert len(result["sprint_lanes"]) >= 1
        sprint_now = next(l for l in result["sprint_lanes"] if l["lane"] == "Sprint Now")
        assert len(sprint_now["items"]) == 1

    def test_sprint_lane_items_capped_at_6(self):
        product_findings = [
            _make_finding(
                id=f"P{i}",
                title=f"Feature {i}",
                severity="high",
                priority_phase="must-have",
                fixable=False,
            )
            for i in range(10)
        ]
        findings = {"product": product_findings}
        result = summarize_candidates("my-repo", findings)
        sprint_now = next(l for l in result["sprint_lanes"] if l["lane"] == "Sprint Now")
        assert len(sprint_now["items"]) <= 6

    def test_empty_sprint_lanes_omitted(self):
        findings = {"product": [_make_finding(severity="low", fixable=False)]}
        result = summarize_candidates("my-repo", findings)
        lanes = {l["lane"] for l in result["sprint_lanes"]}
        assert "Sprint Now" not in lanes

    def test_overnight_bucket_assigned_to_candidate(self):
        finding = _make_finding(severity="info", effort="tiny", fixable=True)
        result = summarize_candidates("repo", {"qa": [finding]})
        assert result["safe_candidates"][0]["bucket"] == "Overnight Now"


# ---------------------------------------------------------------------------
# delivery_readiness
# ---------------------------------------------------------------------------

class TestDeliveryReadiness:
    def _make_workflows(self, ci=False, preview=False, cd=False, nightly=False):
        def _wf(configured):
            return {"configured": configured, "workflow": "", "status": "configured" if configured else "missing"}
        return {"ci": _wf(ci), "preview": _wf(preview), "cd": _wf(cd), "nightly": _wf(nightly)}

    def _make_commands(self, lint=False, test=False, build=False, coverage=False):
        def _cmd(configured):
            return {"configured": configured, "status": "", "command": "", "script_detected": False}
        return {"lint": _cmd(lint), "test": _cmd(test), "build": _cmd(build), "coverage": _cmd(coverage)}

    def test_zero_when_nothing_configured(self):
        score = delivery_readiness(self._make_workflows(), self._make_commands(), 0)
        assert score == 0

    def test_ci_adds_30(self):
        score = delivery_readiness(self._make_workflows(ci=True), self._make_commands(), 0)
        assert score == 30

    def test_test_command_adds_20(self):
        score = delivery_readiness(self._make_workflows(), self._make_commands(test=True), 0)
        assert score == 20

    def test_lint_command_adds_15(self):
        score = delivery_readiness(self._make_workflows(), self._make_commands(lint=True), 0)
        assert score == 15

    def test_build_command_adds_15(self):
        score = delivery_readiness(self._make_workflows(), self._make_commands(build=True), 0)
        assert score == 15

    def test_preview_workflow_adds_10(self):
        score = delivery_readiness(self._make_workflows(preview=True), self._make_commands(), 0)
        assert score == 10

    def test_cd_workflow_adds_5(self):
        score = delivery_readiness(self._make_workflows(cd=True), self._make_commands(), 0)
        assert score == 5

    def test_nightly_workflow_adds_5(self):
        score = delivery_readiness(self._make_workflows(nightly=True), self._make_commands(), 0)
        assert score == 5

    def test_safe_candidates_add_5(self):
        score = delivery_readiness(self._make_workflows(), self._make_commands(), 1)
        assert score == 5

    def test_zero_candidates_adds_nothing(self):
        score = delivery_readiness(self._make_workflows(), self._make_commands(), 0)
        assert score == 0

    def test_perfect_score_is_100(self):
        score = delivery_readiness(
            self._make_workflows(ci=True, preview=True, cd=True, nightly=True),
            self._make_commands(lint=True, test=True, build=True),
            1,
        )
        assert score == 100

    def test_score_capped_at_100(self):
        """Score must never exceed 100 regardless of inputs."""
        score = delivery_readiness(
            self._make_workflows(ci=True, preview=True, cd=True, nightly=True),
            self._make_commands(lint=True, test=True, build=True, coverage=True),
            99,
        )
        assert score <= 100


# ---------------------------------------------------------------------------
# target_summary
# ---------------------------------------------------------------------------

class TestTargetSummary:
    def _make_target(self, tmp_path, name="my-repo"):
        return {"name": name, "path": str(tmp_path), "language": "python"}

    def test_returns_expected_keys(self, tmp_path):
        target = self._make_target(tmp_path)
        result = target_summary(target, [], tmp_path / "results")
        expected = {
            "repo", "path", "product_key", "language", "workflows", "commands",
            "delivery_readiness", "overnight", "sprints", "pr_status",
            "preview_status", "production_status", "nightly_status",
        }
        assert set(result.keys()) == expected

    def test_pr_status_when_no_ci(self, tmp_path):
        target = self._make_target(tmp_path)
        result = target_summary(target, [], tmp_path / "results")
        assert result["pr_status"] == "workflow-missing"

    def test_pr_status_when_ci_configured(self, tmp_path):
        _workflow(tmp_path, "ci.yml", "name: CI\non:\n  pull_request: {}\njobs: {}\n")
        target = self._make_target(tmp_path)
        result = target_summary(target, [], tmp_path / "results")
        assert result["pr_status"] == "pr-required"

    def test_preview_status_missing_by_default(self, tmp_path):
        target = self._make_target(tmp_path)
        result = target_summary(target, [], tmp_path / "results")
        assert result["preview_status"] == "missing"

    def test_production_status_missing_by_default(self, tmp_path):
        target = self._make_target(tmp_path)
        result = target_summary(target, [], tmp_path / "results")
        assert result["production_status"] == "missing"

    def test_nightly_status_missing_by_default(self, tmp_path):
        target = self._make_target(tmp_path)
        result = target_summary(target, [], tmp_path / "results")
        assert result["nightly_status"] == "missing"

    def test_product_key_resolved(self, tmp_path):
        target = self._make_target(tmp_path, name="my-app")
        products = [{"key": "main", "repos": ["my-app"]}]
        result = target_summary(target, products, tmp_path / "results")
        assert result["product_key"] == "main"

    def test_nonexistent_path_produces_no_workflows(self, tmp_path):
        target = {"name": "ghost", "path": str(tmp_path / "ghost"), "language": ""}
        result = target_summary(target, [], tmp_path / "results")
        assert result["workflows"]["ci"]["configured"] is False

    def test_language_preserved(self, tmp_path):
        target = {"name": "myrepo", "path": str(tmp_path), "language": "typescript"}
        result = target_summary(target, [], tmp_path / "results")
        assert result["language"] == "typescript"

    def test_overnight_section_present(self, tmp_path):
        target = self._make_target(tmp_path)
        result = target_summary(target, [], tmp_path / "results")
        assert "safe_candidate_count" in result["overnight"]
        assert "safe_candidates" in result["overnight"]


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain:
    def test_writes_automation_data_json(self, tmp_path, monkeypatch):
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        dashboard_dir = tmp_path / "dashboard"
        dashboard_dir.mkdir()
        output_path = dashboard_dir / "automation-data.json"

        monkeypatch.setenv("BACK_OFFICE_RESULTS_DIR", str(results_dir))
        monkeypatch.setenv("BACK_OFFICE_DASHBOARD_DIR", str(dashboard_dir))
        monkeypatch.setenv("BACK_OFFICE_DELIVERY_OUTPUT", str(output_path))

        # Provide empty targets config
        config_path = tmp_path / "targets.yaml"
        _write_yaml(config_path, {"targets": []})
        monkeypatch.setenv("BACK_OFFICE_TARGETS_CONFIG", str(config_path))

        exit_code = main()
        assert exit_code == 0
        assert output_path.exists()

        data = json.loads(output_path.read_text())
        assert "generated_at" in data
        assert "targets" in data

    def test_output_is_valid_json_with_newline(self, tmp_path, monkeypatch):
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        dashboard_dir = tmp_path / "dashboard"
        dashboard_dir.mkdir()
        output_path = dashboard_dir / "automation-data.json"

        monkeypatch.setenv("BACK_OFFICE_RESULTS_DIR", str(results_dir))
        monkeypatch.setenv("BACK_OFFICE_DASHBOARD_DIR", str(dashboard_dir))
        monkeypatch.setenv("BACK_OFFICE_DELIVERY_OUTPUT", str(output_path))
        monkeypatch.setenv("BACK_OFFICE_TARGETS_CONFIG", str(tmp_path / "missing.yaml"))

        main()
        raw = output_path.read_text()
        assert raw.endswith("\n")
        json.loads(raw)  # must be valid JSON

    def test_creates_output_parent_dirs(self, tmp_path, monkeypatch):
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        deep_output = tmp_path / "nested" / "deep" / "automation-data.json"

        monkeypatch.setenv("BACK_OFFICE_RESULTS_DIR", str(results_dir))
        monkeypatch.setenv("BACK_OFFICE_DASHBOARD_DIR", str(tmp_path / "dashboard"))
        monkeypatch.setenv("BACK_OFFICE_DELIVERY_OUTPUT", str(deep_output))
        monkeypatch.setenv("BACK_OFFICE_TARGETS_CONFIG", str(tmp_path / "missing.yaml"))

        main()
        assert deep_output.exists()

    def test_target_appears_in_output(self, tmp_path, monkeypatch):
        target_path = tmp_path / "my-app"
        target_path.mkdir()
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        dashboard_dir = tmp_path / "dashboard"
        dashboard_dir.mkdir()
        output_path = dashboard_dir / "automation-data.json"

        config_path = tmp_path / "targets.yaml"
        _write_yaml(
            config_path,
            {"targets": [{"name": "my-app", "path": str(target_path)}]},
        )

        monkeypatch.setenv("BACK_OFFICE_TARGETS_CONFIG", str(config_path))
        monkeypatch.setenv("BACK_OFFICE_RESULTS_DIR", str(results_dir))
        monkeypatch.setenv("BACK_OFFICE_DASHBOARD_DIR", str(dashboard_dir))
        monkeypatch.setenv("BACK_OFFICE_DELIVERY_OUTPUT", str(output_path))

        main()
        data = json.loads(output_path.read_text())
        assert any(t["repo"] == "my-app" for t in data["targets"])

    def test_logs_info_after_write(self, tmp_path, monkeypatch, caplog):
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        dashboard_dir = tmp_path / "dashboard"
        dashboard_dir.mkdir()
        output_path = dashboard_dir / "automation-data.json"

        monkeypatch.setenv("BACK_OFFICE_RESULTS_DIR", str(results_dir))
        monkeypatch.setenv("BACK_OFFICE_DASHBOARD_DIR", str(dashboard_dir))
        monkeypatch.setenv("BACK_OFFICE_DELIVERY_OUTPUT", str(output_path))
        monkeypatch.setenv("BACK_OFFICE_TARGETS_CONFIG", str(tmp_path / "missing.yaml"))

        with caplog.at_level(logging.INFO, logger="backoffice.delivery"):
            main()
        assert any("Delivery data" in r.message for r in caplog.records)
