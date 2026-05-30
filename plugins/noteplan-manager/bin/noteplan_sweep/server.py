"""
server.py — Local HTTP server for interactive dashboard editing.

Commands:
  serve    Start a local server that hosts dashboards + REST API for writing
           back to NotePlan .md files (drag Kanban, toggle tasks, frontmatter edits).
"""

import json
import mimetypes
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

import noteplan_sweep.utils as utils
from noteplan_sweep.dashboard import parse_frontmatter, scan_plans


# ---------------------------------------------------------------------------
# Frontmatter write-back
# ---------------------------------------------------------------------------

def _rebuild_frontmatter(fm: dict, body: str) -> str:
    """Reconstruct a file from a (possibly-mutated) frontmatter dict + body."""
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


def update_frontmatter(path: Path, updates: dict) -> tuple[bool, str]:
    """Patch specific frontmatter keys on a .md file. Returns (ok, error_msg)."""
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return False, str(e)

    fm, body = parse_frontmatter(content)

    # Reject empty-value updates (don't wipe fields)
    for k, v in updates.items():
        if v == "" or v is None:
            fm.pop(k, None)
        else:
            fm[k] = str(v).strip()

    new_content = _rebuild_frontmatter(fm, body)
    try:
        path.write_text(new_content, encoding="utf-8")
        return True, ""
    except Exception as e:
        return False, str(e)


def toggle_task(path: Path, line_num: int, checked: bool) -> tuple[bool, str]:
    """Flip [ ] ↔ [x] on the given 1-based line number."""
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return False, str(e)

    lines = content.splitlines(keepends=True)
    if line_num < 1 or line_num > len(lines):
        return False, f"Line {line_num} out of range (file has {len(lines)} lines)"

    line = lines[line_num - 1]
    if checked:
        new_line = re.sub(r'^(\s*[-*]\s+)\[ \]', r'\1[x]', line)
    else:
        new_line = re.sub(r'^(\s*[-*]\s+)\[x\]', r'\1[ ]', line, flags=re.IGNORECASE)

    if new_line == line:
        return False, "No task marker found on that line"

    lines[line_num - 1] = new_line
    try:
        path.write_text("".join(lines), encoding="utf-8")
        return True, ""
    except Exception as e:
        return False, str(e)


def find_plan_path(notes_root: Path, stem: str) -> Path | None:
    """Find a plan file by its filename stem."""
    for p in notes_root.rglob("*.md"):
        if p.stem == stem:
            return p
    return None


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

_STATUS_CYCLE = ["🔵", "🟢", "🟡", "✅"]


class NoteplanHandler(BaseHTTPRequestHandler):
    noteplan_root: Path = None  # set before server starts
    dashboard_dir: Path = None

    def log_message(self, fmt, *args):
        utils.verbose(f"[serve] {fmt % args}")

    def _send_cors(self, code: int = 200, content_type: str = "application/json"):
        self.send_response(code)
        for k, v in _CORS_HEADERS.items():
            self.send_header(k, v)
        self.send_header("Content-Type", content_type)
        self.end_headers()

    def _json_ok(self, data: dict = None):
        self._send_cors(200)
        self.wfile.write(json.dumps(data or {"ok": True}).encode())

    def _json_err(self, msg: str, code: int = 400):
        self._send_cors(code)
        self.wfile.write(json.dumps({"ok": False, "error": msg}).encode())

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except Exception:
            return {}

    # ── OPTIONS (CORS preflight) ──────────────────────────────────────────

    def do_OPTIONS(self):
        self._send_cors(204, "text/plain")

    # ── GET ───────────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        # Route mappings
        route_map = {
            "/": self.dashboard_dir / "insights.html",
            "/insights": self.dashboard_dir / "insights.html",
            "/plans": self.dashboard_dir / "plans.html",
            "/contributions": self.dashboard_dir / "contributions.html",
            "/ai-usage": self.dashboard_dir / "ai-usage.html",
        }

        if path in route_map:
            self._serve_file(route_map[path])
            return

        if path == "/api/plans":
            self._api_get_plans()
            return

        # Static files under dashboard/
        if path.startswith("/static/") or path.startswith("/dashboard/"):
            rel = path.lstrip("/").split("/", 1)[-1] if "/" in path[1:] else path[1:]
            self._serve_file(self.dashboard_dir / rel)
            return

        # Fallback: try dashboard dir directly
        self._serve_file(self.dashboard_dir / path.lstrip("/"))

    def _serve_file(self, file_path: Path):
        if not file_path.exists():
            self._send_cors(404, "text/plain")
            self.wfile.write(b"Not found")
            return
        mime, _ = mimetypes.guess_type(str(file_path))
        mime = mime or "application/octet-stream"
        content = file_path.read_bytes()
        self._send_cors(200, mime)
        self.wfile.write(content)

    def _api_get_plans(self):
        try:
            notes = self.noteplan_root / "Notes"
            plans = scan_plans(notes)
            self._json_ok({"plans": plans})
        except Exception as e:
            self._json_err(str(e), 500)

    # ── POST ──────────────────────────────────────────────────────────────

    def do_POST(self):
        parsed = urlparse(self.path)
        body = self._read_body()

        if parsed.path == "/api/plan-status":
            self._api_plan_status(body)
        elif parsed.path == "/api/frontmatter":
            self._api_frontmatter(body)
        elif parsed.path == "/api/task":
            self._api_task(body)
        else:
            self._json_err("Unknown endpoint", 404)

    def _api_plan_status(self, body: dict):
        """POST /api/plan-status  {stem, status}"""
        stem = body.get("stem", "").strip()
        status = body.get("status", "").strip()
        if not stem or not status:
            return self._json_err("stem and status required")

        notes = self.noteplan_root / "Notes"
        plan_path = find_plan_path(notes, stem)
        if not plan_path:
            return self._json_err(f"Plan not found: {stem}", 404)

        updates = {"status": status}
        if status == "✅":
            from datetime import date
            updates["completed"] = date.today().isoformat()
        elif body.get("clear_completed"):
            updates.pop("completed", None)

        ok, err = update_frontmatter(plan_path, updates)
        if ok:
            utils.verbose(f"[serve] plan-status: {stem} → {status}")
            self._json_ok({"stem": stem, "status": status})
        else:
            self._json_err(err, 500)

    def _api_frontmatter(self, body: dict):
        """POST /api/frontmatter  {path, updates: {key: value, ...}}"""
        rel_path = body.get("path", "").strip()
        updates = body.get("updates", {})
        if not rel_path or not isinstance(updates, dict):
            return self._json_err("path and updates dict required")

        # Accept both relative (from noteplan root) and absolute paths
        if rel_path.startswith("/"):
            plan_path = Path(rel_path)
        else:
            plan_path = self.noteplan_root / rel_path

        if not plan_path.exists():
            return self._json_err(f"File not found: {rel_path}", 404)

        ok, err = update_frontmatter(plan_path, updates)
        if ok:
            utils.verbose(f"[serve] frontmatter: {plan_path.name} → {updates}")
            self._json_ok({"path": str(plan_path), "updates": updates})
        else:
            self._json_err(err, 500)

    def _api_task(self, body: dict):
        """POST /api/task  {path, line, checked}"""
        rel_path = body.get("path", "").strip()
        line_num = body.get("line")
        checked = body.get("checked", True)

        if not rel_path or line_num is None:
            return self._json_err("path and line required")

        if rel_path.startswith("/"):
            plan_path = Path(rel_path)
        else:
            plan_path = self.noteplan_root / rel_path

        if not plan_path.exists():
            return self._json_err(f"File not found: {rel_path}", 404)

        ok, err = toggle_task(plan_path, int(line_num), bool(checked))
        if ok:
            utils.verbose(f"[serve] task: {plan_path.name} line {line_num} → {'[x]' if checked else '[ ]'}")
            self._json_ok({"line": line_num, "checked": checked})
        else:
            self._json_err(err, 500)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

def cmd_serve(args):
    root = utils.noteplan_root()
    dash_dir = root / "dashboard"
    port = getattr(args, "port", 4242)

    # Auto-generate dashboards if HTML doesn't exist
    ideas_html = dash_dir / "plans.html"
    if not ideas_html.exists():
        utils.log("dashboard/plans.html not found — running dashboard-generate first...")
        try:
            from noteplan_sweep import dashboard as db
            import types
            gen_args = types.SimpleNamespace(skip_mine=True, notes_dir=None, out=None)
            db.cmd_dashboard_generate(gen_args)
        except Exception as e:
            utils.verbose(f"  dashboard-generate failed: {e} (continuing anyway)")

    # Wire class-level state
    NoteplanHandler.noteplan_root = root
    NoteplanHandler.dashboard_dir = dash_dir

    server = HTTPServer(("127.0.0.1", port), NoteplanHandler)

    url = f"http://localhost:{port}"
    utils.log(f"Serving NotePlan dashboards at {url}")
    utils.log(f"  Insights (hub)   → {url}/")
    utils.log(f"  Plans            → {url}/plans")
    utils.log(f"  Contributions    → {url}/contributions")
    utils.log(f"  AI Usage         → {url}/ai-usage")
    utils.log("Press Ctrl+C to stop.")

    if getattr(args, "open", False):
        import subprocess, time
        threading.Timer(0.3, lambda: subprocess.run(["open", url])).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        utils.log("\nServer stopped.")
