"""
test_sweep_review_js.py — Browser-side regression tests for sweep_review.py JS.

Uses pytest-playwright with a local http.server fixture to load generated HTML
and assert JavaScript function behaviour in a real Chromium context.

Run with the bundled venv:
    cd plugins/noteplan-manager/bin
    .venv/bin/python -m pytest noteplan_sweep/tests/test_sweep_review_js.py -v

Bug index:
  JS-01  parseDiff: deleted-file block gets filename from --- a/ line
  JS-02  parseDiff: new-file block gets filename from +++ b/ line
  JS-03  parseDiff: emoji filenames decoded correctly in sidebar
  JS-04  isSepRow: all-dash rows excluded from rendered narrative table
  JS-05  NARRATIVE empty → auto-switch to Diff tab
  JS-06  classifyDestLines: lines matching source → Moved, no-match → New
  JS-07  extractDestWithContext: +# Header line sets section context
  JS-08  cross-move: line in global removed map from another file → Cross tab
  JS-09  lost/moved badges appear on Diff view deleted lines
"""

import http.server
import json
import re
import sys
import tempfile
import textwrap
import threading
from pathlib import Path
from typing import Generator

import pytest

_BIN = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BIN))

from noteplan_sweep.sweep_review import _build_snapshot_html

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def http_server(tmp_path_factory) -> Generator[str, None, None]:
    """Serve a temp directory over HTTP for the duration of the session."""
    serve_dir = tmp_path_factory.mktemp("html_serve")

    class SilentHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(serve_dir), **kwargs)
        def log_message(self, *args):
            pass  # suppress request logs

    server = http.server.HTTPServer(("127.0.0.1", 0), SilentHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}", serve_dir
    server.shutdown()


def _write_page(serve_dir: Path, name: str, diff: str, narrative: list,
                stat: str = "1 file changed") -> str:
    """Build + write a review HTML page, return its filename."""
    html = _build_snapshot_html(
        run_id="test-01",
        date_str="2026-04-21",
        sha="abc1234",
        stat_text=stat,
        diff_text=diff,
        seed_comments=[],
        narrative=narrative,
        changed_calendar_files=[f for f in re.findall(r'b/(Calendar/\S+\.md)', diff)],
    )
    path = serve_dir / name
    path.write_text(html, encoding="utf-8")
    return name


# ---------------------------------------------------------------------------
# Synthetic diff helpers
# ---------------------------------------------------------------------------

def _make_diff(files: list[dict]) -> str:
    """
    Build a synthetic unified diff string.
    Each file dict: {path, added: [str], removed: [str], deleted=False, new=False}
    """
    lines = []
    for f in files:
        p = f["path"]
        added   = f.get("added", [])
        removed = f.get("removed", [])
        is_del  = f.get("deleted", False)
        is_new  = f.get("new", False)

        a_path = "/dev/null" if is_new  else f"a/{p}"
        b_path = "/dev/null" if is_del  else f"b/{p}"

        lines.append(f"diff --git a/{p} b/{p}")
        if is_new:
            lines.append("new file mode 100644")
        if is_del:
            lines.append("deleted file mode 100644")
        lines.append(f"index 000000..abc123 100644")
        lines.append(f"--- {a_path}")
        lines.append(f"+++ {b_path}")
        n_add = len(added)
        n_rem = len(removed)
        lines.append(f"@@ -1,{n_rem} +1,{n_add} @@")
        for l in removed:
            lines.append(f"-{l}")
        for l in added:
            lines.append(f"+{l}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# JS-01  parseDiff: deleted-file filename from --- a/ line
# ---------------------------------------------------------------------------

def test_js01_deleted_file_filename(playwright, http_server):
    """JS-01: Deleted file ('+++ /dev/null') gets its name from '--- a/' line."""
    base_url, serve_dir = http_server
    diff = _make_diff([{"path": "Calendar/20260413.md", "removed": ["- [ ] task"], "deleted": True}])
    page_name = _write_page(serve_dir, "js01.html", diff, [])

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.click("button:has-text('Diff')")
    page.wait_for_selector(".fi")

    names = page.eval_on_selector_all(".fi .name", "els => els.map(e => e.textContent)")
    browser.close()

    assert any("20260413.md" in n for n in names), f"Deleted file name not found. Got: {names}"
    assert not any("unknown" in n.lower() for n in names), f"(unknown) still present: {names}"


# ---------------------------------------------------------------------------
# JS-02  parseDiff: new-file filename from +++ b/ line
# ---------------------------------------------------------------------------

def test_js02_new_file_filename(playwright, http_server):
    """JS-02: New file (--- /dev/null) gets filename from '+++ b/' line."""
    base_url, serve_dir = http_server
    diff = _make_diff([{"path": "Notes/plans/NewPlan.md", "added": ["# New Plan"], "new": True}])
    page_name = _write_page(serve_dir, "js02.html", diff, [])

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.click("button:has-text('Diff')")
    page.wait_for_selector(".fi")

    names = page.eval_on_selector_all(".fi .name", "els => els.map(e => e.textContent)")
    browser.close()

    assert any("NewPlan.md" in n for n in names), f"New file name not found. Got: {names}"


# ---------------------------------------------------------------------------
# JS-03  parseDiff: emoji filename in sidebar
# ---------------------------------------------------------------------------

def test_js03_emoji_filename(playwright, http_server):
    """JS-03: Emoji-named file (already decoded in DIFF_TEXT) shows in sidebar."""
    base_url, serve_dir = http_server
    diff = _make_diff([{"path": "Notes/☕️ NaqshCoffee/test.md", "added": ["# Test"], "new": True}])
    page_name = _write_page(serve_dir, "js03.html", diff, [])

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.click("button:has-text('Diff')")
    page.wait_for_selector(".fi")

    names = page.eval_on_selector_all(".fi .name", "els => els.map(e => e.textContent)")
    browser.close()

    assert any("test.md" in n for n in names), f"Emoji-path file not found. Got: {names}"
    assert not any("(unknown)" in n for n in names), f"(unknown) present: {names}"


# ---------------------------------------------------------------------------
# JS-04  isSepRow: all-dash rows excluded from narrative table
# ---------------------------------------------------------------------------

def test_js04_sep_rows_excluded(playwright, http_server):
    """JS-04: Rows with section='-------' must not render in the narrative table."""
    base_url, serve_dir = http_server
    narrative = [
        {"date": "2026-04-13", "source_file": "Calendar/20260413.md",
         "section": "-------", "summary": "-------", "destination": "-----------"},
        {"date": "2026-04-13", "source_file": "Calendar/20260413.md",
         "section": "I Owe", "summary": "IOUs (3)", "destination": "[[20260421]]"},
    ]
    diff = _make_diff([{"path": "Calendar/20260413.md",
                        "removed": ["- [ ] task"], "added": ["- [ ] task >2026-04-24"]}])
    page_name = _write_page(serve_dir, "js04.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    rows = page.eval_on_selector_all(".nav-tbl tr[data-row-idx]",
                                     "els => els.map(e => e.textContent)")
    browser.close()

    assert len(rows) == 1, f"Expected 1 row (sep filtered), got {len(rows)}: {rows}"
    assert "I Owe" in rows[0]


# ---------------------------------------------------------------------------
# JS-05  NARRATIVE empty → auto-switch to Diff tab
# ---------------------------------------------------------------------------

def test_js05_empty_narrative_shows_diff(playwright, http_server):
    """JS-05: No NARRATIVE rows → portal opens in Diff view (sidebar visible)."""
    base_url, serve_dir = http_server
    diff = _make_diff([{"path": "CLAUDE.md", "added": ["# heading"], "new": True}])
    page_name = _write_page(serve_dir, "js05.html", diff, [])

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector("#sidebar")

    sidebar_display = page.eval_on_selector("#sidebar", "el => el.style.display")
    browser.close()

    assert sidebar_display != "none", "Sidebar should be visible in Diff mode"


# ---------------------------------------------------------------------------
# JS-06  classifyDestLines: Moved vs New
# ---------------------------------------------------------------------------

def test_js06_classify_moved_vs_new(playwright, http_server):
    """JS-06: Lines matching source removed → Moved; unmatched → New."""
    base_url, serve_dir = http_server

    src_removed = "- [ ] task one"
    dest_added_moved = "- [ ] task one >2026-04-24"   # matches (prefix match after norm)
    dest_added_new   = "- [ ] brand new task"           # no match

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Work", "summary": "tasks",
                  "destination": "[[Calendar/20260421]]"}]

    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": [src_removed], "added": []},
        {"path": "Calendar/20260421.md",
         "added": [dest_added_moved, dest_added_new], "removed": []},
    ])
    page_name = _write_page(serve_dir, "js06.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    # Click the section modal
    page.click(".view-btn")
    page.wait_for_selector("#modal-overlay.open")

    moved_count = page.eval_on_selector(
        ".mpanel-tab:has-text('Moved')",
        "el => parseInt(el.textContent.match(/\\d+/)[0])"
    )
    new_count = page.eval_on_selector(
        ".mpanel-tab.new-tab",
        "el => parseInt(el.textContent.match(/\\d+/)[0])"
    )
    browser.close()

    assert moved_count >= 1, f"Expected >=1 Moved, got {moved_count}"
    assert new_count >= 1,   f"Expected >=1 New, got {new_count}"


# ---------------------------------------------------------------------------
# JS-07  extractDestWithContext: +# Header detected as section context
# ---------------------------------------------------------------------------

def test_js07_header_context_in_dest_panel(playwright, http_server):
    """JS-07: +# Section header line appears as blue context header, not as content."""
    base_url, serve_dir = http_server

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Tasks", "summary": "items",
                  "destination": "[[Calendar/20260421]]"}]

    # Dest file adds a header then content underneath
    diff = _make_diff([
        {"path": "Calendar/20260413.md", "removed": ["- [ ] task one"], "added": []},
        {"path": "Calendar/20260421.md",
         "added": ["# I Owe", "- [ ] task one >2026-04-24", "- [ ] task two >2026-04-24"],
         "removed": []},
    ])
    page_name = _write_page(serve_dir, "js07.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    page.click(".view-btn")
    page.wait_for_selector("#modal-overlay.open")

    # The # I Owe header should appear as a .diff-ctx-hdr element, not a .diff-line
    ctx_headers = page.eval_on_selector_all(
        ".diff-ctx-hdr", "els => els.map(e => e.textContent.trim())"
    )
    # The header line should NOT appear as a diff-line (it would be in the content if detection failed)
    dest_lines_text = page.eval_on_selector(
        "#modal-dest-lines", "el => el.textContent"
    )
    browser.close()

    assert any("I Owe" in h for h in ctx_headers), (
        f"# I Owe not found as context header. ctx_headers={ctx_headers}"
    )
    # The raw "# I Owe" should be in the header, not duplicated as a plain line
    plain_owe_count = dest_lines_text.count("I Owe")
    assert plain_owe_count <= 1, (
        f"# I Owe appeared as both header and content line ({plain_owe_count}x)"
    )


# ---------------------------------------------------------------------------
# JS-08  cross-move: line in another source file → Cross tab
# ---------------------------------------------------------------------------

def test_js08_cross_move_tab(playwright, http_server):
    """JS-08: Line removed from file B but present in dest shown as Cross in file A's modal."""
    base_url, serve_dir = http_server

    # Source A has one task; Source B also has one task; both land in dest
    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Work", "summary": "items",
                  "destination": "[[Calendar/20260421]]"}]

    shared_task = "- [ ] shared task"
    diff = _make_diff([
        # Source A (this row's source) — removes "unique task"
        {"path": "Calendar/20260413.md",
         "removed": ["- [ ] unique task A"], "added": []},
        # Source B (different file) — removes the shared task
        {"path": "Calendar/20260414.md",
         "removed": [shared_task], "added": []},
        # Dest gets both
        {"path": "Calendar/20260421.md",
         "added": ["- [ ] unique task A >2026-04-24", f"{shared_task} >2026-04-24"],
         "removed": []},
    ])
    page_name = _write_page(serve_dir, "js08.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    page.click(".view-btn")
    page.wait_for_selector("#modal-overlay.open")

    cross_btn = page.query_selector(".mpanel-tab.cross-tab")
    assert cross_btn is not None, "Cross tab button not found"

    cross_count = page.eval_on_selector(
        ".mpanel-tab.cross-tab",
        "el => parseInt(el.textContent.match(/\\d+/)[0])"
    )
    browser.close()

    assert cross_count >= 1, f"Expected >=1 Cross-moved line, got {cross_count}"


# ---------------------------------------------------------------------------
# JS-09  Diff view: ✗ lost and → moved badges on del rows
# ---------------------------------------------------------------------------

def test_js09_diff_view_lost_badge(playwright, http_server):
    """JS-09: Deleted line with no matching add anywhere gets ✗ lost badge."""
    base_url, serve_dir = http_server

    diff = _make_diff([{
        "path": "Calendar/20260413.md",
        "removed": ["- [ ] truly deleted task"],
        "added":   ["- [ ] unrelated new task"],
    }])
    page_name = _write_page(serve_dir, "js09_lost.html", diff, [])

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    # Already in Diff mode (NARRATIVE empty → auto-switch)
    page.wait_for_selector(".fd")

    lost_badges = page.eval_on_selector_all(
        ".lost-badge", "els => els.map(e => e.textContent.trim())"
    )
    browser.close()

    assert any("lost" in b for b in lost_badges), (
        f"No ✗ lost badge found on deleted line. badges={lost_badges}"
    )


def test_js09_diff_view_moved_badge(playwright, http_server):
    """JS-09: Deleted line that reappears in another file gets → moved badge."""
    base_url, serve_dir = http_server

    task = "- [ ] task that moves"
    diff = _make_diff([
        {"path": "Calendar/20260413.md", "removed": [task], "added": []},
        {"path": "Calendar/20260421.md", "added": [f"{task} >2026-04-24"], "removed": []},
    ])
    page_name = _write_page(serve_dir, "js09_moved.html", diff, [])

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".fd")

    moved_badges = page.eval_on_selector_all(
        ".move-badge", "els => els.map(e => e.textContent.trim())"
    )
    browser.close()

    assert len(moved_badges) >= 1, (
        f"No → moved badge found on moved line. badges={moved_badges}"
    )
