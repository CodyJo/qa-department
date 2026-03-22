"""Local dashboard server with scan API.

Serves dashboard files from the ``dashboard/`` directory and provides POST
endpoints for triggering agent scans and managing manual backlog items.

Usage::

    python -m backoffice serve [--port 8070]

    # Or via make:
    make jobs TARGET=/path/to/repo
"""
from __future__ import annotations

import http.server
import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Department registry
# ---------------------------------------------------------------------------

DEPT_SCRIPTS: dict[str, str] = {
    "qa": "agents/qa-scan.sh",
    "seo": "agents/seo-audit.sh",
    "ada": "agents/ada-audit.sh",
    "compliance": "agents/compliance-audit.sh",
    "monetization": "agents/monetization-audit.sh",
    "product": "agents/product-audit.sh",
}

ALL_DEPTS: list[str] = list(DEPT_SCRIPTS.keys())

# ---------------------------------------------------------------------------
# Module-level state (overridden by main())
# ---------------------------------------------------------------------------

_root: Path = Path(__file__).resolve().parents[1]
_dashboard_dir: Path = _root / "dashboard"
_target_repo: str = ""
_allowed_origins: set[str] = {"http://localhost:8070", "http://127.0.0.1:8070"}

# Track running processes to prevent double-starts
running_jobs: set[str] = set()
running_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Manual items helpers
# ---------------------------------------------------------------------------

def _manual_items_paths(root: Path) -> tuple[Path, Path]:
    """Return (results_path, dashboard_path) for manual-items.json."""
    return (
        root / "results" / "manual-items.json",
        root / "dashboard" / "manual-items.json",
    )


def _load_manual_items(root: Path | None = None) -> list[dict]:
    """Load manual items list from the results file."""
    results_path, _ = _manual_items_paths(root or _root)
    try:
        with open(results_path) as f:
            raw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    if isinstance(raw, dict):
        items = raw.get("items", [])
    else:
        items = raw

    return [item for item in items if isinstance(item, dict)]


def _save_manual_items(items: list[dict], root: Path | None = None) -> None:
    """Persist manual items to both results/ and dashboard/."""
    results_path, dashboard_path = _manual_items_paths(root or _root)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "items": items,
    }
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    # Mirror into dashboard directory so the front-end can fetch it directly.
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dashboard_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# Agent runner helpers
# ---------------------------------------------------------------------------

def run_agent(dept: str, target: str, *, sync: bool = False,
              root: Path | None = None) -> bool:
    """Launch an agent script in a background thread.

    Returns ``True`` when the job was accepted, ``False`` if it was already
    running.
    """
    r = root or _root
    script = str(r / DEPT_SCRIPTS[dept])
    args = [script, target]
    if sync:
        args.append("--sync")

    def _run() -> None:
        try:
            subprocess.run(["bash"] + args, cwd=str(r))
        finally:
            with running_lock:
                running_jobs.discard(dept)

    with running_lock:
        if dept in running_jobs:
            return False  # Already running
        running_jobs.add(dept)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    logger.info("Started agent dept=%s target=%s", dept, target)
    return True


def init_jobs(target: str, departments: list[str], root: Path | None = None) -> None:
    """Initialize the jobs file for a set of departments."""
    r = root or _root
    subprocess.run(
        [
            "bash",
            str(r / "scripts" / "job-status.sh"),
            "init",
            target,
            " ".join(departments),
        ],
        cwd=str(r),
    )


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler serving the dashboard directory with a lightweight scan API."""

    # Instance attributes injected by create_handler()
    _root: Path
    _target_repo: str
    _allowed_origins: set[str]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(self._dashboard_dir), **kwargs)

    # Override so subclasses built by create_handler() can supply their own dir
    @property
    def _dashboard_dir(self) -> str:
        return str(self._root / "dashboard")

    # ------------------------------------------------------------------
    # CORS helpers
    # ------------------------------------------------------------------

    def _origin_allowed(self) -> str | None | bool:
        """Return the origin string if allowed, None if absent, False if blocked."""
        origin = self.headers.get("Origin")
        if not origin:
            return None
        return origin if origin in self._allowed_origins else False

    def _set_cors_headers(self) -> None:
        origin = self._origin_allowed()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    # ------------------------------------------------------------------
    # Request parsing helpers
    # ------------------------------------------------------------------

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            return {}

    def _json_response(self, code: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight."""
        if self._origin_allowed() is False:
            self.send_response(403)
            self.end_headers()
            return

        self.send_response(200)
        self._set_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/run-scan":
            self._handle_run_scan()
        elif path == "/api/run-all":
            self._handle_run_all()
        elif path == "/api/run-regression":
            self._handle_run_regression()
        elif path == "/api/manual-item":
            self._handle_manual_item()
        else:
            self.send_error(404, "Not found")

    # ------------------------------------------------------------------
    # POST handlers
    # ------------------------------------------------------------------

    def _handle_run_scan(self) -> None:
        if not self._target_repo:
            self._json_response(400, {
                "error": "No TARGET set. Start server with: make jobs TARGET=/path/to/repo"
            })
            return

        body = self._read_body()
        dept = body.get("department", "")

        if dept not in DEPT_SCRIPTS:
            self._json_response(400, {
                "error": f"Unknown department: {dept}",
                "valid": ALL_DEPTS,
            })
            return

        with running_lock:
            if dept in running_jobs:
                self._json_response(409, {
                    "error": f"{dept} is already running",
                    "status": "running",
                })
                return

        # Merge into an existing jobs file if present; otherwise init fresh.
        jobs_file = self._root / "results" / ".jobs.json"
        if jobs_file.exists():
            try:
                with open(jobs_file) as f:
                    jobs_data = json.load(f)
                if dept not in jobs_data.get("jobs", {}):
                    subprocess.run(
                        [
                            "bash",
                            str(self._root / "scripts" / "job-status.sh"),
                            "start",
                            dept,
                        ],
                        cwd=str(self._root),
                    )
            except (json.JSONDecodeError, OSError):
                pass
        else:
            init_jobs(self._target_repo, [dept], root=self._root)

        started = run_agent(dept, self._target_repo, sync=True, root=self._root)
        if started:
            self._json_response(200, {
                "status": "started",
                "department": dept,
                "target": self._target_repo,
            })
        else:
            self._json_response(409, {"error": f"{dept} is already running"})

    def _handle_run_all(self) -> None:
        if not self._target_repo:
            self._json_response(400, {
                "error": "No TARGET set. Start server with: make jobs TARGET=/path/to/repo"
            })
            return

        body = self._read_body()
        parallel = body.get("parallel", False)

        with running_lock:
            already = [d for d in ALL_DEPTS if d in running_jobs]
        if already:
            self._json_response(409, {
                "error": f"Jobs already running: {', '.join(already)}",
                "running": already,
            })
            return

        init_jobs(self._target_repo, ALL_DEPTS, root=self._root)

        if parallel:
            for dept in ALL_DEPTS:
                run_agent(dept, self._target_repo, sync=True, root=self._root)
        else:
            root_snapshot = self._root

            def _run_sequential() -> None:
                for dept in ALL_DEPTS:
                    run_agent(dept, self._target_repo, sync=True, root=root_snapshot)
                    while True:
                        with running_lock:
                            if dept not in running_jobs:
                                break
                        time.sleep(1)
                subprocess.run(
                    [
                        "bash",
                        str(root_snapshot / "scripts" / "job-status.sh"),
                        "finalize",
                    ],
                    cwd=str(root_snapshot),
                )

            t = threading.Thread(target=_run_sequential, daemon=True)
            t.start()

        self._json_response(200, {
            "status": "started",
            "departments": ALL_DEPTS,
            "target": self._target_repo,
            "parallel": parallel,
        })

    def _handle_run_regression(self) -> None:
        """Run portfolio regression in the background."""
        if self._origin_allowed() is False:
            self.send_error(403, "Origin not allowed")
            return

        runner = self._root / "scripts" / "regression-runner.py"
        if not runner.exists():
            self._json_response(500, {"error": "regression-runner.py not found"})
            return

        def _run() -> None:
            try:
                subprocess.run(["python3", str(runner)], cwd=str(self._root))
            except Exception:
                pass

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        self._json_response(200, {"status": "started"})

    def _handle_manual_item(self) -> None:
        """Append a manual backlog item and mirror to the dashboard directory."""
        if self._origin_allowed() is False:
            self.send_error(403, "Origin not allowed")
            return

        body = self._read_body()
        title = (body.get("title") or "").strip()
        if not title:
            self._json_response(400, {"error": "title is required"})
            return

        repo = (body.get("repo") or "").strip()
        department = (body.get("department") or "").strip()
        severity = (body.get("severity") or "medium").strip().lower()
        category = (body.get("category") or "").strip()
        bucket = (body.get("bucket") or "").strip()
        notes = (body.get("notes") or "").strip()
        product_key = (body.get("product_key") or "").strip()
        categories = body.get("categories") or []
        if isinstance(categories, str):
            categories = [c.strip() for c in categories.split(",") if c.strip()]

        items = _load_manual_items(root=self._root)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        new_id = f"MAN-{len(items) + 1:03d}"
        item = {
            "id": new_id,
            "title": title,
            "repo": repo,
            "department": department,
            "severity": severity,
            "category": category,
            "categories": categories,
            "bucket": bucket,
            "notes": notes,
            "product_key": product_key,
            "created_at": now,
        }
        items.append(item)
        _save_manual_items(items, root=self._root)
        logger.info("Manual item added id=%s title=%r", new_id, title)
        self._json_response(200, {"ok": True, "items": items})

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        """Suppress noisy polling logs for .jobs.json."""
        first_arg = str(args[0]) if args else ""
        if ".jobs.json" in first_arg:
            return
        logger.debug("HTTP %s", format % args)


# ---------------------------------------------------------------------------
# Factory — creates a handler class bound to a specific runtime config
# ---------------------------------------------------------------------------

def create_handler(
    root: Path,
    target_repo: str,
    allowed_origins: set[str],
) -> type[DashboardHandler]:
    """Return a DashboardHandler subclass pre-configured for the given runtime."""

    class _Handler(DashboardHandler):
        _root = root
        _target_repo = target_repo
        _allowed_origins = allowed_origins

    return _Handler


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(port: int = 8070, target: str | None = None) -> int:
    """Start the local dashboard dev server.

    Parameters
    ----------
    port:
        TCP port to listen on (default 8070).
    target:
        Absolute path to the target repository.  When *None* the server
        still starts but ``/api/run-scan`` will return 400 until a target
        is provided.
    """
    # Try to pull allowed_origins from the package config; fall back to
    # the built-in localhost defaults so the server works without a config.
    try:
        from backoffice.config import load_config  # noqa: PLC0415
        cfg = load_config()
        allowed_origins: set[str] = set(cfg.api.allowed_origins) or {
            f"http://localhost:{port}",
            f"http://127.0.0.1:{port}",
        }
        root = cfg.root
    except Exception:
        allowed_origins = {
            f"http://localhost:{port}",
            f"http://127.0.0.1:{port}",
        }
        root = Path(__file__).resolve().parents[1]

    target_repo = ""
    if target:
        target_repo = str(Path(target).resolve())
        logger.info("Target repo: %s", target_repo)
    else:
        logger.info(
            "No TARGET specified — Run Scan buttons will prompt for one. "
            "Usage: python -m backoffice serve --target /path/to/repo"
        )

    logger.info("Dashboard server: http://localhost:%d/", port)
    logger.info("Jobs dashboard:   http://localhost:%d/jobs.html", port)
    logger.info("HQ dashboard:     http://localhost:%d/index.html", port)

    handler_cls = create_handler(root, target_repo, allowed_origins)
    server = http.server.HTTPServer(("127.0.0.1", port), handler_cls)
    logger.info("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped.")
    return 0
