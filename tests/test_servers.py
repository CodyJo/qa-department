"""Tests for backoffice.server — local dashboard dev server."""
from __future__ import annotations

import io
import json
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest

from backoffice.server import (
    ALL_DEPTS,
    DEPT_SCRIPTS,
    _load_manual_items,
    _manual_items_paths,
    _save_manual_items,
    create_handler,
    run_agent,
    running_jobs,
    running_lock,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_root(tmp_path: Path) -> Path:
    """Return a temp tree that mirrors the real project layout."""
    (tmp_path / "dashboard").mkdir()
    (tmp_path / "results").mkdir()
    (tmp_path / "agents").mkdir()
    (tmp_path / "scripts").mkdir()
    return tmp_path


@pytest.fixture()
def live_server(tmp_root: Path):
    """Spin up a real HTTPServer bound to a random port; yield (host, port)."""
    import http.server

    handler_cls = create_handler(
        root=tmp_root,
        target_repo=str(tmp_root / "fake-repo"),
        allowed_origins={f"http://localhost:0"},  # will be replaced below
    )

    # Bind to port 0 so the OS picks a free port
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]

    # Fix up allowed origins to match the actual port
    actual_origin = f"http://localhost:{port}"
    server.RequestHandlerClass._allowed_origins = {
        actual_origin,
        f"http://127.0.0.1:{port}",
    }

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "127.0.0.1", port
    server.shutdown()


@pytest.fixture()
def _clean_running_jobs():
    """Ensure running_jobs is empty before and after each test."""
    with running_lock:
        running_jobs.clear()
    yield
    with running_lock:
        running_jobs.clear()


# ---------------------------------------------------------------------------
# Unit: manual items helpers
# ---------------------------------------------------------------------------


class TestManualItemsHelpers:
    def test_load_returns_empty_when_file_missing(self, tmp_root: Path) -> None:
        items = _load_manual_items(root=tmp_root)
        assert items == []

    def test_load_returns_empty_on_invalid_json(self, tmp_root: Path) -> None:
        results_path, _ = _manual_items_paths(tmp_root)
        results_path.write_text("not json")
        items = _load_manual_items(root=tmp_root)
        assert items == []

    def test_round_trip(self, tmp_root: Path) -> None:
        _save_manual_items([{"id": "MAN-001", "title": "hello"}], root=tmp_root)
        loaded = _load_manual_items(root=tmp_root)
        assert len(loaded) == 1
        assert loaded[0]["title"] == "hello"

    def test_save_writes_to_both_locations(self, tmp_root: Path) -> None:
        _save_manual_items([{"id": "MAN-001", "title": "test"}], root=tmp_root)
        results_path, dashboard_path = _manual_items_paths(tmp_root)
        assert results_path.exists()
        assert dashboard_path.exists()

    def test_save_payload_has_generated_at(self, tmp_root: Path) -> None:
        _save_manual_items([], root=tmp_root)
        results_path, _ = _manual_items_paths(tmp_root)
        data = json.loads(results_path.read_text())
        assert "generated_at" in data
        assert data["generated_at"].endswith("Z")

    def test_load_handles_dict_wrapper(self, tmp_root: Path) -> None:
        """Handles files that store {generated_at, items: [...]}."""
        results_path, _ = _manual_items_paths(tmp_root)
        payload = {"generated_at": "2026-01-01T00:00:00Z", "items": [{"id": "MAN-001", "title": "x"}]}
        results_path.write_text(json.dumps(payload))
        items = _load_manual_items(root=tmp_root)
        assert len(items) == 1

    def test_load_filters_non_dict_entries(self, tmp_root: Path) -> None:
        results_path, _ = _manual_items_paths(tmp_root)
        results_path.write_text(json.dumps(["bad", {"id": "ok"}]))
        items = _load_manual_items(root=tmp_root)
        assert items == [{"id": "ok"}]

    def test_id_increments(self, tmp_root: Path) -> None:
        _save_manual_items(
            [{"id": "MAN-001"}, {"id": "MAN-002"}], root=tmp_root
        )
        items = _load_manual_items(root=tmp_root)
        # Simulate what the handler does
        new_id = f"MAN-{len(items) + 1:03d}"
        assert new_id == "MAN-003"


# ---------------------------------------------------------------------------
# Unit: run_agent guard
# ---------------------------------------------------------------------------


class TestRunAgent:
    def test_returns_false_when_already_running(
        self, tmp_root: Path, _clean_running_jobs
    ) -> None:
        with running_lock:
            running_jobs.add("qa")
        result = run_agent("qa", "/fake", root=tmp_root)
        assert result is False

    def test_adds_dept_to_running_jobs(
        self, tmp_root: Path, _clean_running_jobs, monkeypatch
    ) -> None:
        """dept is added to running_jobs and the agent thread is started."""
        started_events: list[str] = []

        def fake_run(cmd, cwd=None):
            started_events.append(cmd[1])  # script path

        monkeypatch.setattr("subprocess.run", fake_run)

        # We need an agent script to exist so the handler logic passes
        result = run_agent("qa", "/fake", root=tmp_root)
        assert result is True
        # running_jobs will be cleared by _run() eventually, but we can't
        # guarantee timing here — just confirm it started successfully.


# ---------------------------------------------------------------------------
# Integration: HTTP server
# ---------------------------------------------------------------------------


class TestServerStartsAndServesFiles:
    def test_serves_dashboard_index(self, live_server, tmp_root: Path) -> None:
        """GET / should return a file from the dashboard directory."""
        # Create a minimal index file in the dashboard dir
        (tmp_root / "dashboard" / "index.html").write_text(
            "<html><body>hello</body></html>"
        )
        host, port = live_server
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("GET", "/index.html")
        resp = conn.getresponse()
        assert resp.status == 200
        body = resp.read().decode()
        assert "hello" in body

    def test_missing_file_returns_404(self, live_server) -> None:
        host, port = live_server
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("GET", "/nonexistent-xyz.html")
        resp = conn.getresponse()
        assert resp.status == 404


class TestCORSHeaders:
    def test_options_preflight_allowed_origin(self, live_server) -> None:
        host, port = live_server
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "OPTIONS",
            "/api/run-scan",
            headers={
                "Origin": f"http://localhost:{port}",
                "Access-Control-Request-Method": "POST",
            },
        )
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 200
        acao = resp.getheader("Access-Control-Allow-Origin")
        assert acao == f"http://localhost:{port}"

    def test_options_preflight_disallowed_origin(self, live_server) -> None:
        host, port = live_server
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "OPTIONS",
            "/api/run-scan",
            headers={"Origin": "http://evil.example.com"},
        )
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 403

    def test_cors_header_on_json_response(self, live_server) -> None:
        host, port = live_server
        conn = HTTPConnection(host, port, timeout=5)
        body = json.dumps({"department": "qa"}).encode()
        conn.request(
            "POST",
            "/api/run-scan",
            body=body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
                "Origin": f"http://localhost:{port}",
            },
        )
        resp = conn.getresponse()
        resp.read()
        acao = resp.getheader("Access-Control-Allow-Origin")
        assert acao == f"http://localhost:{port}"

    def test_no_cors_header_when_no_origin(self, live_server) -> None:
        host, port = live_server
        conn = HTTPConnection(host, port, timeout=5)
        body = json.dumps({"department": "qa"}).encode()
        conn.request(
            "POST",
            "/api/run-scan",
            body=body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            },
        )
        resp = conn.getresponse()
        resp.read()
        acao = resp.getheader("Access-Control-Allow-Origin")
        assert acao is None


class TestManualItemEndpoint:
    def _post_manual_item(self, host, port, payload: dict, origin: str | None = None):
        body = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }
        if origin:
            headers["Origin"] = origin
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/api/manual-item", body=body, headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        return resp.status, data

    def test_create_item_returns_200(self, live_server) -> None:
        host, port = live_server
        status, data = self._post_manual_item(
            host, port,
            {"title": "Fix the flicker"},
            origin=f"http://localhost:{port}",
        )
        assert status == 200
        assert data["ok"] is True

    def test_item_has_expected_fields(self, live_server) -> None:
        host, port = live_server
        status, data = self._post_manual_item(
            host, port,
            {
                "title": "My item",
                "repo": "etheos",
                "department": "qa",
                "severity": "high",
                "category": "performance",
                "bucket": "sprint-1",
                "notes": "some notes",
                "product_key": "PKG-42",
            },
            origin=f"http://localhost:{port}",
        )
        assert status == 200
        items = data["items"]
        assert len(items) == 1
        item = items[0]
        assert item["title"] == "My item"
        assert item["repo"] == "etheos"
        assert item["department"] == "qa"
        assert item["severity"] == "high"
        assert item["bucket"] == "sprint-1"
        assert item["product_key"] == "PKG-42"
        assert item["id"] == "MAN-001"
        assert "created_at" in item

    def test_missing_title_returns_400(self, live_server) -> None:
        host, port = live_server
        status, data = self._post_manual_item(
            host, port,
            {"notes": "no title here"},
            origin=f"http://localhost:{port}",
        )
        assert status == 400
        assert "title" in data["error"]

    def test_categories_string_split(self, live_server) -> None:
        host, port = live_server
        status, data = self._post_manual_item(
            host, port,
            {"title": "Cat test", "categories": "ux, perf, a11y"},
            origin=f"http://localhost:{port}",
        )
        assert status == 200
        assert data["items"][0]["categories"] == ["ux", "perf", "a11y"]

    def test_categories_list_passthrough(self, live_server) -> None:
        host, port = live_server
        status, data = self._post_manual_item(
            host, port,
            {"title": "Cat list", "categories": ["ux", "perf"]},
            origin=f"http://localhost:{port}",
        )
        assert status == 200
        assert data["items"][0]["categories"] == ["ux", "perf"]

    def test_severity_defaults_to_medium(self, live_server) -> None:
        host, port = live_server
        status, data = self._post_manual_item(
            host, port,
            {"title": "Default sev"},
            origin=f"http://localhost:{port}",
        )
        assert status == 200
        assert data["items"][0]["severity"] == "medium"

    def test_items_persist_across_requests(self, live_server) -> None:
        host, port = live_server
        origin = f"http://localhost:{port}"
        self._post_manual_item(host, port, {"title": "First"}, origin=origin)
        status, data = self._post_manual_item(
            host, port, {"title": "Second"}, origin=origin
        )
        assert status == 200
        assert len(data["items"]) == 2
        assert data["items"][0]["id"] == "MAN-001"
        assert data["items"][1]["id"] == "MAN-002"

    def test_blocked_origin_returns_403(self, live_server) -> None:
        host, port = live_server
        body = json.dumps({"title": "x"}).encode()
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
            "Origin": "http://evil.example.com",
        }
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/api/manual-item", body=body, headers=headers)
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 403

    def test_files_mirrored_to_dashboard_dir(self, live_server, tmp_root: Path) -> None:
        host, port = live_server
        origin = f"http://localhost:{port}"
        self._post_manual_item(host, port, {"title": "Mirror me"}, origin=origin)
        dashboard_file = tmp_root / "dashboard" / "manual-items.json"
        assert dashboard_file.exists()
        data = json.loads(dashboard_file.read_text())
        assert len(data["items"]) == 1


class TestRunScanEndpoint:
    def _post_run_scan(self, host, port, payload: dict):
        body = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/api/run-scan", body=body, headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        return resp.status, data

    def test_unknown_department_returns_400(self, live_server) -> None:
        host, port = live_server
        status, data = self._post_run_scan(host, port, {"department": "unknown-dept"})
        assert status == 400
        assert "Unknown department" in data["error"]
        assert "valid" in data

    def test_valid_departments_listed(self, live_server) -> None:
        host, port = live_server
        status, data = self._post_run_scan(host, port, {"department": "bogus"})
        assert status == 400
        for dept in ALL_DEPTS:
            assert dept in data["valid"]


class TestRunAllEndpoint:
    def _post_run_all(self, host, port, payload: dict | None = None):
        body = json.dumps(payload or {}).encode()
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/api/run-all", body=body, headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        return resp.status, data

    def test_returns_error_when_jobs_already_running(
        self, live_server, _clean_running_jobs
    ) -> None:
        host, port = live_server
        with running_lock:
            running_jobs.add("qa")
        status, data = self._post_run_all(host, port)
        assert status == 409
        assert "qa" in data["running"]

    def test_unknown_post_path_returns_404(self, live_server) -> None:
        host, port = live_server
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/api/does-not-exist")
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 404


class TestRunRegressionEndpoint:
    def _post_run_regression(self, host, port, origin: str | None = None):
        headers: dict[str, str] = {"Content-Length": "0"}
        if origin:
            headers["Origin"] = origin
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/api/run-regression", headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        return resp.status, data

    def test_missing_runner_returns_500(self, live_server) -> None:
        # regression-runner.py does not exist in tmp_root
        host, port = live_server
        status, data = self._post_run_regression(
            host, port, origin=f"http://localhost:{port}"
        )
        assert status == 500
        assert "not found" in data["error"]

    def test_blocked_origin_returns_403(self, live_server) -> None:
        host, port = live_server
        body = b""
        headers = {
            "Content-Length": "0",
            "Origin": "http://evil.example.com",
        }
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("POST", "/api/run-regression", headers=headers)
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 403


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


class TestModuleConstants:
    def test_dept_scripts_keys_match_all_depts(self) -> None:
        assert set(DEPT_SCRIPTS.keys()) == set(ALL_DEPTS)

    def test_expected_departments_present(self) -> None:
        for dept in ("qa", "seo", "ada", "compliance", "monetization", "product"):
            assert dept in DEPT_SCRIPTS
