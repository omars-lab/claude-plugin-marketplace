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


# ---------------------------------------------------------------------------
# JS-10  Noise lines excluded from New tab
# ---------------------------------------------------------------------------

def test_js10_noise_lines_excluded_from_new(playwright, http_server):
    """JS-10: Code fences, empty checkboxes, and HRs are not shown in New tab."""
    base_url, serve_dir = http_server

    real_task    = "- [ ] a genuine new task"
    noise_lines  = ["```", "```python", "---", "- [ ]", "- [ ]  >2026-04-24"]

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Work", "summary": "items",
                  "destination": "[[Calendar/20260421]]"}]

    diff = _make_diff([
        {"path": "Calendar/20260413.md", "removed": ["- [ ] source task"], "added": []},
        {"path": "Calendar/20260421.md",
         "added": [real_task] + noise_lines, "removed": []},
    ])
    page_name = _write_page(serve_dir, "js10.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")
    page.click(".view-btn")
    page.wait_for_selector("#modal-overlay.open")

    # Click New tab
    page.click(".mpanel-tab.new-tab")
    new_count = page.eval_on_selector(
        ".mpanel-tab.new-tab",
        "el => parseInt(el.textContent.match(/\\d+/)[0])"
    )
    new_text = page.eval_on_selector("#modal-dest-lines", "el => el.textContent")
    browser.close()

    # Only the real task should count; noise lines should be absent
    assert new_count == 1, f"Expected 1 new line (real task only), got {new_count}"
    assert real_task.replace("- [ ] ", "").strip() in new_text
    assert "```" not in new_text, "Code fence leaked into New tab"


# ---------------------------------------------------------------------------
# JS-11  Move row — badge shows →, modal confirms lines moved (no tabs)
# ---------------------------------------------------------------------------

def test_js11_move_row_badge_and_modal(playwright, http_server):
    """JS-11: All source lines arrive in dest → badge → after scan, modal shows ✓ N confirmed."""
    base_url, serve_dir = http_server

    task = "- [ ] implement feature X"
    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Work", "summary": "tasks",
                  "destination": "[[Calendar/20260421]]"}]
    diff = _make_diff([
        # Include section header so extractSectionLines can scope the lines
        {"path": "Calendar/20260413.md", "removed": ["## Work", task], "added": []},
        {"path": "Calendar/20260421.md",
         "added": ["## Work", f"{task} >2026-04-24"], "removed": []},
    ])
    page_name = _write_page(serve_dir, "js11.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    # Open modal to trigger classification
    page.click(".view-btn")
    page.wait_for_selector("#modal-overlay.open")

    # Badge should now show → (move)
    badge_class = page.eval_on_selector(
        "tr[data-row-idx='0'] .row-badge", "el => el.className"
    )
    modal_text = page.eval_on_selector("#modal-body", "el => el.textContent")
    browser.close()

    assert "rb-move" in badge_class, f"Expected rb-move badge, got: {badge_class}"
    assert "confirmed" in modal_text.lower(), (
        f"Expected 'confirmed' in modal body, got: {modal_text!r}"
    )


# ---------------------------------------------------------------------------
# JS-12  Mixed row — badge shows ⚡, modal has moved header + lost section
# ---------------------------------------------------------------------------

def test_js12_mixed_row_badge_and_modal(playwright, http_server):
    """JS-12: Some lines moved, some lost → badge ⚡ (mixed), modal shows both sections."""
    base_url, serve_dir = http_server

    moved_task = "- [ ] task that arrives"
    lost_task  = "- [ ] task that gets lost"
    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Work", "summary": "mixed tasks",
                  "destination": "[[Calendar/20260421]]"}]
    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["## Work", moved_task, lost_task], "added": []},
        # Only moved_task arrives in dest
        {"path": "Calendar/20260421.md",
         "added": ["## Work", f"{moved_task} >2026-04-24"], "removed": []},
    ])
    page_name = _write_page(serve_dir, "js12.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    page.click(".view-btn")
    page.wait_for_selector("#modal-overlay.open")

    badge_class = page.eval_on_selector(
        "tr[data-row-idx='0'] .row-badge", "el => el.className"
    )
    modal_text = page.eval_on_selector("#modal-body", "el => el.textContent")
    # Mixed rows: parent badge shows → move (lost portion injected as a sub-row)
    sub_row = page.query_selector("tr[data-mixed-lost-for='0']")
    browser.close()

    # Parent badge shows → (move) because some lines arrived; sub-row carries ✗ (lost)
    assert "rb-move" in badge_class, (
        f"Expected rb-move badge on mixed row parent, got: {badge_class}"
    )
    assert sub_row is not None, "Expected mixed-lost sub-row to be injected after modal open"
    # Modal should show the moved task
    assert "task that arrives" in modal_text, (
        f"Expected moved task in modal body, got: {modal_text!r}"
    )


# ---------------------------------------------------------------------------
# JS-13  Lost row — badge shows ✗, modal in focusLost single-panel mode
# ---------------------------------------------------------------------------

def test_js13_lost_row_modal(playwright, http_server):
    """JS-13: No source lines arrive → badge ✗, modal shows focusLost single panel (no dest panel)."""
    base_url, serve_dir = http_server

    lost_task = "- [ ] this task never arrives"
    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Work", "summary": "lost items",
                  "destination": "[[Calendar/20260421]]"}]
    diff = _make_diff([
        # Section header scopes the removed lines to "Work"
        {"path": "Calendar/20260413.md", "removed": ["## Work", lost_task], "added": []},
        # Dest gets unrelated content under a different section — lost_task doesn't arrive
        {"path": "Calendar/20260421.md",
         "added": ["## Other", "- [ ] completely different task >2026-04-24"], "removed": []},
    ])
    page_name = _write_page(serve_dir, "js13.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    page.click(".view-btn")
    page.wait_for_selector("#modal-overlay.open")

    badge_class = page.eval_on_selector(
        "tr[data-row-idx='0'] .row-badge", "el => el.className"
    )
    # In focusLost mode, modal-body has grid-template-columns: 1fr (single column)
    grid_cols = page.eval_on_selector(
        "#modal-body", "el => el.style.gridTemplateColumns"
    )
    src_text = page.eval_on_selector("#modal-body", "el => el.textContent")
    browser.close()

    assert "rb-lost" in badge_class, f"Expected rb-lost badge, got: {badge_class}"
    assert grid_cols == "1fr", f"Expected single-column focusLost layout, got: {grid_cols!r}"
    assert "never arrives" in src_text, f"Lost task not shown in source panel: {src_text!r}"


# ---------------------------------------------------------------------------
# JS-14  Anomaly row — badge shows +, anomaly modal shows unexpected additions
# ---------------------------------------------------------------------------

def test_js14_anomaly_row_modal(playwright, http_server):
    """JS-14: Dest has additions, source removed nothing → badge +, anomaly modal single panel."""
    base_url, serve_dir = http_server

    unexpected_line = "- [ ] mystery task appeared in dest"
    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Work", "summary": "anomaly",
                  "destination": "[[Calendar/20260421]]"}]
    diff = _make_diff([
        # Source has NO removed lines for this section (in diff only added)
        {"path": "Calendar/20260413.md", "removed": [], "added": ["- [ ] unrelated addition"]},
        {"path": "Calendar/20260421.md", "added": [unexpected_line], "removed": []},
    ])
    page_name = _write_page(serve_dir, "js14.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    page.click(".view-btn")
    page.wait_for_selector("#modal-overlay.open")

    badge_class = page.eval_on_selector(
        "tr[data-row-idx='0'] .row-badge", "el => el.className"
    )
    grid_cols = page.eval_on_selector(
        "#modal-body", "el => el.style.gridTemplateColumns"
    )
    modal_text = page.eval_on_selector("#modal-body", "el => el.textContent")
    browser.close()

    assert "rb-untraced" in badge_class, f"Expected rb-untraced badge (Track C rename), got: {badge_class}"
    assert grid_cols == "1fr", f"Expected single-column anomaly layout, got: {grid_cols!r}"
    assert "mystery task" in modal_text or "unexpected" in modal_text.lower(), (
        f"Anomaly content not shown in modal: {modal_text!r}"
    )


# ---------------------------------------------------------------------------
# JS-15  Background scan — all badges populated without opening modals
# ---------------------------------------------------------------------------

def test_js15_background_scan_populates_badges(playwright, http_server):
    """JS-15: requestIdleCallback background scan classifies all rows and updates badges."""
    base_url, serve_dir = http_server

    moved_task = "- [ ] clean move task"
    lost_task  = "- [ ] task that is lost"
    narrative = [
        {"date": "2026-04-13", "source_file": "Calendar/20260413.md",
         "section": "Work", "summary": "moves",
         "destination": "[[Calendar/20260421]]"},
        {"date": "2026-04-13", "source_file": "Calendar/20260413.md",
         "section": "Backlog", "summary": "lost items",
         "destination": "[[Calendar/20260421]]"},
    ]
    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": [moved_task, f"## Work", lost_task, "## Backlog"], "added": []},
        {"path": "Calendar/20260421.md",
         "added": [f"{moved_task} >2026-04-24"], "removed": []},
    ])
    page_name = _write_page(serve_dir, "js15.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    # Wait for background scan to finish — badges should leave rb-pending state
    page.wait_for_function(
        "() => document.querySelectorAll('.row-badge.rb-pending').length === 0",
        timeout=10_000
    )

    badge_classes = page.eval_on_selector_all(
        "tr[data-row-idx] .row-badge",
        "els => els.map(e => e.className)"
    )
    browser.close()

    assert len(badge_classes) >= 1, "No badges found after background scan"
    assert all("rb-pending" not in c for c in badge_classes), (
        f"Some badges still pending after scan: {badge_classes}"
    )


# ---------------------------------------------------------------------------
# JS-16  B-14: new-file dest — frontmatter not classified as anomaly
# ---------------------------------------------------------------------------

def test_js16_new_file_frontmatter_not_anomaly(playwright, http_server):
    """JS-16 (B-14): When dest file is 'new file mode', its frontmatter lines
    (---, doctype:, status:, started:, etc.) must NOT trigger an anomaly badge.
    The row should be classified as 'empty' (source had no countable removed lines)
    rather than 'anomaly' (dest has untraced additions)."""
    base_url, serve_dir = http_server

    frontmatter_lines = [
        "---",
        "doctype: 📆",
        "status: 🟢",
        "started: 2026-04-21",
        "namespace: 🏡",
        "plantype: 👨🏻‍💻",
        "description: A brand-new plan file created during the sweep.",
        "---",
        "# 🏡260421👨🏻‍💻 My New Plan",
    ]
    narrative = [{"date": "2026-04-21", "source_file": "Calendar/20260421.md",
                  "section": "New Plan Section", "summary": "created new plan",
                  "destination": "[[🏡260421👨🏻‍💻 My New Plan]]"}]
    diff = _make_diff([
        # Source: a breadcrumb section with a task that moved
        {"path": "Calendar/20260421.md",
         "removed": ["- [ ] ## New Plan Section", "- [ ] plan task here"],
         "added": []},
        # Dest: newly created file (new file mode) with only frontmatter + H1
        {"path": "Notes/🏡 Personal/🏡📆 Plans/Present/👨🏻‍💻 Development/🏡260421👨🏻‍💻 My New Plan.md",
         "added": frontmatter_lines,
         "new": True},
    ])
    page_name = _write_page(serve_dir, "js16.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    page.wait_for_function(
        "() => document.querySelectorAll('.row-badge.rb-pending').length === 0",
        timeout=10_000,
    )

    badge_class = page.eval_on_selector(
        "tr[data-row-idx='0'] .row-badge", "el => el.className"
    )
    browser.close()

    assert "rb-anomaly" not in badge_class, (
        f"B-14: new-file frontmatter should NOT be classified as anomaly. Badge: {badge_class}"
    )


# ---------------------------------------------------------------------------
# JS-17  B-13: cross-row anomaly — sibling row claims dest additions
# ---------------------------------------------------------------------------

def test_js17_cross_row_anomaly_cleared_by_sibling(playwright, http_server):
    """JS-17 (B-13): When two rows share the same dest, and row B has no source removed
    lines but the dest's additions are all claimed by row A's removed norms, row B must
    be classified as 'empty', NOT 'anomaly'."""
    base_url, serve_dir = http_server

    shared_task = "- [ ] shared content that row A moved"

    narrative = [
        {"date": "2026-04-13", "source_file": "Calendar/20260413.md",
         "section": "Work", "summary": "row A moves content",
         "destination": "[[Calendar/20260421]]"},
        {"date": "2026-04-14", "source_file": "Calendar/20260414.md",
         "section": "NonExistentSection", "summary": "row B — no source match",
         "destination": "[[Calendar/20260421]]"},
    ]
    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["## Work", shared_task], "added": []},
        {"path": "Calendar/20260414.md",
         "removed": [], "added": []},
        {"path": "Calendar/20260421.md",
         "added": [f"{shared_task} >2026-04-24"], "removed": []},
    ])
    page_name = _write_page(serve_dir, "js17.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    page.wait_for_function(
        "() => document.querySelectorAll('.row-badge.rb-pending').length === 0",
        timeout=10_000,
    )

    badge_classes = page.eval_on_selector_all(
        "tr[data-row-idx] .row-badge", "els => els.map(e => e.className)"
    )
    browser.close()

    assert len(badge_classes) == 2, f"Expected 2 badge rows, got {len(badge_classes)}"
    row_a_badge, row_b_badge = badge_classes[0], badge_classes[1]

    assert "rb-move" in row_a_badge, (
        f"Row A should be rb-move (source lines matched). Got: {row_a_badge}"
    )
    assert "rb-anomaly" not in row_b_badge, (
        f"B-13: Row B's dest additions claimed by Row A — should NOT be anomaly. "
        f"Got: {row_b_badge}"
    )


# ---------------------------------------------------------------------------
# JS-18  B-15: redirect-stub — lost lines rechecked against linked plan
# ---------------------------------------------------------------------------

def test_js18_redirect_stub_fp(playwright, http_server):
    """JS-18 (B-15): When the dest file is a redirect stub containing
    '> Migrated: see [[NewPlan]]' as a context line in the diff, lost lines
    should be rechecked against the linked NewPlan's diff additions.

    Setup:
      Source 20260313.md: removes '- [ ] task from Bikar'
      OldPlan.md: in diff with '> Migrated: see [[NewPlan]]' as context line (no additions)
      NewPlan.md: in diff with '- [ ] task from Bikar' as an addition

    Without B-15: addedLines = OldPlan's additions = [] → lost.
    With B-15:    addedLines = NewPlan's additions = ['- [ ] task from Bikar'] → move.

    The row should be classified as 'rb-move', NOT 'rb-lost'.
    """
    base_url, serve_dir = http_server

    task_line = "- [ ] task from Bikar"
    narrative = [{"date": "2026-03-13", "source_file": "Calendar/20260313.md",
                  "section": "## Developing Bikar", "summary": "bikar tasks",
                  "destination": "[[OldPlan]]"}]

    # Manual diff: OldPlan has context line with redirect; NewPlan has the actual addition.
    diff = textwrap.dedent("""\
        diff --git a/Calendar/20260313.md b/Calendar/20260313.md
        index 000000..abc123 100644
        --- a/Calendar/20260313.md
        +++ b/Calendar/20260313.md
        @@ -1,3 +1,2 @@
         ## Developing Bikar
        -""" + task_line + """
        diff --git a/Notes/OldPlan.md b/Notes/OldPlan.md
        index abc123..def456 100644
        --- a/Notes/OldPlan.md
        +++ b/Notes/OldPlan.md
        @@ -1,2 +1,2 @@
         # Old Plan
         > Migrated: see [[NewPlan]]
        diff --git a/Notes/NewPlan.md b/Notes/NewPlan.md
        index 000000..abc123 100644
        --- a/Notes/NewPlan.md
        +++ b/Notes/NewPlan.md
        @@ -1,1 +1,2 @@
         # New Plan
        +""" + task_line + """
    """)

    page_name = _write_page(serve_dir, "js18.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    page.wait_for_function(
        "() => document.querySelectorAll('.row-badge.rb-pending').length === 0",
        timeout=10_000,
    )

    badge_class = page.eval_on_selector(
        "tr[data-row-idx='0'] .row-badge", "el => el.className"
    )
    browser.close()

    assert "rb-lost" not in badge_class, (
        f"B-15: redirect stub OldPlan → should follow redirect to NewPlan and classify "
        f"as move, not lost. Badge: {badge_class}"
    )
    assert "rb-move" in badge_class, (
        f"B-15: redirect stub OldPlan → should be rb-move after following redirect. "
        f"Badge: {badge_class}"
    )


# ---------------------------------------------------------------------------
# JS-19  V-47a: fuzzy section name matching scopes dest additions correctly
# ---------------------------------------------------------------------------

def test_js19_v47a_fuzzy_section_scoping(playwright, http_server):
    """JS-19 (V-47a): When the breadcrumb section name ('Anthropic GitHub refs') doesn't
    exactly match any ## header in the dest file's diff, V-47a fuzzy matching should find
    '## References' (score >= 0.5 via de-plural stem: 'refs' → 'ref' matches 'references').

    The dest file has:
      ## References   (context — no additions under it)
      ## Other Work   (context — has an added task below it)

    Without V-47a: addedLines = full-file fallback = ['- some other task'] → anomaly.
    With V-47a:    addedLines scoped to '## References' = [] → empty (section found but empty).

    The row should be classified as 'empty', NOT 'anomaly'.
    """
    base_url, serve_dir = http_server

    narrative = [{"date": "2026-04-16", "source_file": "Calendar/20260416.md",
                  "section": "## Anthropic GitHub refs", "summary": "github refs section",
                  "destination": "[[plan]]"}]

    # Diff: source calendar has no removed lines (section is only a context line).
    # Dest plan.md has ## References (no additions) and ## Other Work (one addition).
    # The context-line headers allow proper section boundary detection in the fuzzy pass.
    diff = textwrap.dedent("""\
        diff --git a/Calendar/20260416.md b/Calendar/20260416.md
        index 000000..abc123 100644
        --- a/Calendar/20260416.md
        +++ b/Calendar/20260416.md
        @@ -1,1 +1,1 @@
         ## Anthropic GitHub refs
        diff --git a/Notes/plan.md b/Notes/plan.md
        index 000000..def456 100644
        --- a/Notes/plan.md
        +++ b/Notes/plan.md
        @@ -1,2 +1,3 @@
         ## References
         ## Other Work
        +- some other task
    """)

    page_name = _write_page(serve_dir, "js19.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    page.wait_for_function(
        "() => document.querySelectorAll('.row-badge.rb-pending').length === 0",
        timeout=10_000,
    )

    badge_class = page.eval_on_selector(
        "tr[data-row-idx='0'] .row-badge", "el => el.className"
    )
    browser.close()

    assert "rb-anomaly" not in badge_class, (
        f"V-47a: fuzzy match 'Anthropic GitHub refs' → '## References' should scope "
        f"dest additions to empty References section → NOT anomaly. Badge: {badge_class}"
    )
