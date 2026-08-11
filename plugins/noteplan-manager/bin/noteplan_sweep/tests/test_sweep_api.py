"""Tests for sweep_api pure handlers + a live-server smoke test."""

import json
import subprocess
import threading
import urllib.request
from http.server import HTTPServer
from pathlib import Path

import pytest

import noteplan_sweep.sweep_api as api
import noteplan_sweep.sweep_manifest as sm
import noteplan_sweep.sweep_session as ss


def _git(args, root):
    return subprocess.run(["git"] + args, cwd=str(root), capture_output=True, text=True)


@pytest.fixture
def session(tmp_path):
    """A git repo + a written manifest with 2 moves (a: normal, b: another)."""
    root = tmp_path
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@t"], root)
    _git(["config", "user.name", "t"], root)
    (root / "Calendar").mkdir()
    (root / "Notes").mkdir()
    (root / "sweeps").mkdir()
    (root / "Calendar" / "20260709.md").write_text(
        "# Work\n- [ ] alpha\n- [ ] beta\n- [ ] gamma\n", encoding="utf-8")
    (root / "Notes" / "Plan.md").write_text(
        "# Plan\n\n# Next Steps\n", encoding="utf-8")
    _git(["add", "-A"], root)
    _git(["commit", "-q", "-m", "base"], root)
    base = _git(["rev-parse", "HEAD"], root).stdout.strip()

    def mv(mid, start, texts):
        content = [sm.content_line(t, "verbatim", source_n=start + i)
                   for i, t in enumerate(texts)]
        return sm.build_move(mid, "Calendar/20260709.md", "# Work", start,
                             list(texts), "Notes/Plan.md", "# Next Steps", content,
                             breadcrumb={"section": "Work", "summary": "s",
                                         "destination": "[[Plan]]"})

    manifest = {
        "schema_version": sm.SCHEMA_VERSION, "run_id": "2026-07-09-01",
        "base_sha": base, "created_at": "2026-07-09T00:00:00Z", "mode": "work",
        "source_files": [{"file": "Calendar/20260709.md",
                          "cleanup": {"clear_source": True, "keep_completed": True}}],
        "moves": [mv("a", 2, ["- [ ] alpha"]), mv("b", 3, ["- [ ] beta"])],
    }
    ss.manifest_path(root, "2026-07-09-01").write_text(
        json.dumps(manifest), encoding="utf-8")
    ss.ensure_session_created(root, "2026-07-09-01")
    return root, "2026-07-09-01"


# ---------------------------------------------------------------------------
# Read handlers
# ---------------------------------------------------------------------------

def test_list_and_get_session(session):
    root, run = session
    code, data = api.list_sessions(root)
    assert code == 200 and any(s["run_id"] == run for s in data["sessions"])
    code, data = api.get_session(root, run)
    assert code == 200
    assert len(data["state"]["moves"]) == 2


def test_get_file_slice(session):
    root, _ = session
    code, data = api.get_file(root, {"path": "Calendar/20260709.md",
                                     "start": "2", "end": "3"})
    assert code == 200 and data["lines"] == ["- [ ] alpha", "- [ ] beta"]


def test_get_file_rejects_traversal(session):
    root, _ = session
    code, data = api.get_file(root, {"path": "../../../etc/passwd"})
    assert code == 400
    code, data = api.get_file(root, {"path": "secrets.txt"})
    assert code == 400  # non-.md rejected


def test_get_file_sections(session):
    root, _ = session
    code, data = api.get_file(root, {"path": "Notes/Plan.md", "sections": "1"})
    assert code == 200
    texts = [s["text"] for s in data["sections"]]
    assert "# Plan" in texts and "# Next Steps" in texts


# ---------------------------------------------------------------------------
# Mutating handlers
# ---------------------------------------------------------------------------

def test_decision_skip_then_status(session):
    root, run = session
    code, data = api.post_decision(root, run, {"move_id": "a", "action": "skip"})
    assert code == 200
    by_id = {m["id"]: m for m in data["state"]["moves"]}
    assert by_id["a"]["status"] == "skipped"


def test_stale_seq_conflict(session):
    root, run = session
    # expect_seq wrong → 409 with fresh state
    code, data = api.post_decision(root, run,
                                   {"move_id": "a", "action": "skip", "expect_seq": 999})
    assert code == 409 and "state" in data


def test_approve_applies_and_persists(session):
    root, run = session
    code, data = api.post_approve(root, run, {"move_ids": ["a"]})
    assert code == 200
    assert data["results"][0]["ok"]
    by_id = {m["id"]: m for m in data["state"]["moves"]}
    assert by_id["a"]["status"] == "applied"
    # disk changed
    assert "- [ ] alpha" not in (root / "Calendar/20260709.md").read_text()
    assert "- [ ] alpha" in (root / "Notes/Plan.md").read_text()


def test_approve_stale_move_reports_without_writing(session):
    root, run = session
    # mutate source so move 'a' no longer matches
    cal = root / "Calendar/20260709.md"
    cal.write_text("# Work\n- [ ] different\n- [ ] beta\n- [ ] gamma\n", encoding="utf-8")
    code, data = api.post_approve(root, run, {"move_ids": ["a"]})
    assert code == 200
    r = data["results"][0]
    assert not r["ok"] and r["stale"]["reason"] == "content_drift"
    by_id = {m["id"]: m for m in data["state"]["moves"]}
    assert by_id["a"]["status"] == "stale"


def test_finalize_flow(session):
    root, run = session
    api.post_approve(root, run, {"move_ids": ["a"]})
    api.post_decision(root, run, {"move_id": "b", "action": "skip"})
    code, data = api.get_status(root, run)
    assert data["can_finalize"] is True
    code, data = api.post_finalize(root, run, {})
    assert code == 200 and data["commit_sha"]
    code, data = api.get_status(root, run)
    assert data["state"] == "finalized"


def test_split_creates_children(session):
    root, run = session
    # split move 'a' (1 line) isn't meaningful; use a fresh 2-line move via reroute test:
    # move 'b' has 1 line too, so split a single-line move into one part
    code, data = api.post_split(root, run, {
        "move_id": "a",
        "parts": [{"line_idxs": [0], "dest": {"file": "Notes/Plan.md",
                                              "section_header": "# Inbox"}}]})
    assert code == 200
    by_id = {m["id"]: m for m in data["state"]["moves"]}
    assert by_id["a"]["status"] == "superseded"
    # child present and pending
    children = [m for m in data["state"]["moves"] if m["id"].startswith("a-")]
    assert children and children[0]["status"] == "pending"
    assert children[0]["destination"]["section_header"] == "# Inbox"


def test_abort_restores(session):
    root, run = session
    api.post_approve(root, run, {"move_ids": ["a"]})
    code, data = api.post_abort(root, run, {})
    assert code == 200
    assert "- [ ] alpha" in (root / "Calendar/20260709.md").read_text()
    assert data["state"]["state"] == "aborted"


# ---------------------------------------------------------------------------
# Live server smoke test
# ---------------------------------------------------------------------------

def test_live_server_roundtrip(session):
    root, run = session
    from noteplan_sweep.server import NoteplanHandler
    NoteplanHandler.noteplan_root = root
    NoteplanHandler.dashboard_dir = root / "dashboard"
    srv = HTTPServer(("127.0.0.1", 0), NoteplanHandler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{port}"
        # GET session
        with urllib.request.urlopen(f"{base}/api/sweep/session/{run}") as r:
            data = json.loads(r.read())
        assert len(data["state"]["moves"]) == 2
        # POST approve
        req = urllib.request.Request(
            f"{base}/api/sweep/session/{run}/approve",
            data=json.dumps({"move_ids": ["a"]}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read())
        assert data["results"][0]["ok"]
        # review page renders
        with urllib.request.urlopen(f"{base}/review/{run}") as r:
            html = r.read().decode()
        assert run in html
    finally:
        srv.shutdown()
