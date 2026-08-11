"""End-to-end: real NoteplanHandler server + Chromium driving the review UI.

Asserts that clicking Approve actually mutates disk + flips the queue chip, and
that an out-of-band edit makes the move stale in the UI with Rebase recovering it.
"""

import json
import subprocess
import sys
import threading
import time
from http.server import HTTPServer
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BIN))

import noteplan_sweep.sweep_manifest as sm
import noteplan_sweep.sweep_session as ss


def _git(args, root):
    return subprocess.run(["git"] + args, cwd=str(root), capture_output=True, text=True)


@pytest.fixture
def server(tmp_path):
    root = tmp_path
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@t"], root)
    _git(["config", "user.name", "t"], root)
    (root / "Calendar").mkdir()
    (root / "Notes").mkdir()
    (root / "sweeps").mkdir()
    (root / "Calendar" / "20260709.md").write_text(
        "# Work\n- [ ] alpha\n- [ ] beta\n- [ ] gamma\n", encoding="utf-8")
    (root / "Notes" / "Plan.md").write_text("# Plan\n\n# Next Steps\n", encoding="utf-8")
    _git(["add", "-A"], root)
    _git(["commit", "-q", "-m", "base"], root)
    base = _git(["rev-parse", "HEAD"], root).stdout.strip()

    def mv(mid, start, texts):
        content = [sm.content_line(t, "verbatim", source_n=start + i)
                   for i, t in enumerate(texts)]
        return sm.build_move(mid, "Calendar/20260709.md", "# Work", start,
                             list(texts), "Notes/Plan.md", "# Next Steps", content,
                             confidence="high", rationale="clearly work",
                             breadcrumb={"section": "Work", "summary": "s",
                                         "destination": "[[Plan]]"})

    manifest = {
        "schema_version": sm.SCHEMA_VERSION, "run_id": "2026-07-09-01",
        "base_sha": base, "created_at": "2026-07-09T00:00:00Z", "mode": "work",
        "source_files": [{"file": "Calendar/20260709.md",
                          "cleanup": {"clear_source": True, "keep_completed": True}}],
        "moves": [mv("a", 2, ["- [ ] alpha"]), mv("b", 3, ["- [ ] beta"])],
    }
    ss.manifest_path(root, "2026-07-09-01").write_text(json.dumps(manifest), encoding="utf-8")
    ss.ensure_session_created(root, "2026-07-09-01")

    from noteplan_sweep.server import NoteplanHandler
    NoteplanHandler.noteplan_root = root
    NoteplanHandler.dashboard_dir = root / "dashboard"
    srv = HTTPServer(("127.0.0.1", 0), NoteplanHandler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield root, f"http://127.0.0.1:{port}", "2026-07-09-01"
    srv.shutdown()


def test_approve_mutates_disk_and_updates_chip(playwright, server):
    root, base_url, run = server
    browser = playwright.chromium.launch()
    page = browser.new_page()
    try:
        page.goto(f"{base_url}/review/{run}")
        page.wait_for_selector(".q-move")
        # Approve the currently-selected (first) move
        page.click("button:has-text('Approve')")
        # Wait for disk to change
        cal = root / "Calendar/20260709.md"
        for _ in range(50):
            if "- [ ] alpha" not in cal.read_text():
                break
            time.sleep(0.1)
        assert "- [ ] alpha" not in cal.read_text()
        assert "- [ ] alpha" in (root / "Notes/Plan.md").read_text()
        # queue shows an applied chip
        page.wait_for_selector(".chip.c-applied")
    finally:
        browser.close()


def test_out_of_band_edit_goes_stale_then_rebases(playwright, server):
    root, base_url, run = server
    browser = playwright.chromium.launch()
    page = browser.new_page()
    try:
        page.goto(f"{base_url}/review/{run}")
        page.wait_for_selector(".q-move")
        # Out-of-band: NotePlan adds a date tag to beta (cosmetic drift)
        cal = root / "Calendar/20260709.md"
        cal.write_text(cal.read_text().replace("- [ ] beta", "- [ ] beta >2026-07-20"),
                       encoding="utf-8")
        # Select move b (second queue item) and approve → should go stale
        page.locator(".q-move").nth(1).click()
        page.click("button:has-text('Approve')")
        page.wait_for_selector(".banner.stale")
        # Rebase recovers it (cosmetic drift is refreshable)
        page.click("button:has-text('Rebase')")
        # After rebase, approve succeeds and disk changes
        page.wait_for_selector("button:has-text('Approve'):not([disabled])")
        page.click("button:has-text('Approve')")
        for _ in range(50):
            if "- [ ] beta" not in cal.read_text():
                break
            time.sleep(0.1)
        assert "beta" not in cal.read_text()
        assert "- [ ] beta >2026-07-20" in (root / "Notes/Plan.md").read_text()
    finally:
        browser.close()
