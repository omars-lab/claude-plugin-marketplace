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
  JS-21  filterValidPairs: noise-line (empty checkbox) match doesn't inflate movedCount → no negative lostCount
  JS-22  V-47a: composite section name ("Config Agent ARB") doesn't lock dest to wrong section
         ("## Agent Development" scores 1.0/3 tokens = 0.33 < 0.5 normalized → falls back to
         full-file additions → ARB lines found → type=move, not lost)
  JS-23  V-47a: de-pluralized stem match ("eval checks"→"## For Evals", score=1.0) must not
         lock dest for 2-token query (threshold 2×0.6=1.2 > 1.0 → fallback → type=move)
  JS-24  V-R6: breadcrumb destination mismatch — lost lines found in a different dest file
         (breadcrumb says →20260426 but lines landed in Coffee House Site.md) → modal shows
         amber "⚠ Breadcrumb destination mismatch" banner with the correct filename
  JS-25  V-R6 badge promotion: all lost lines found in other diff files → badge must be
         rb-move (not rb-lost). Only lines absent from entire diff count as truly lost.
  JS-26  V-47a removal (#82): section name matches wrong section in dest (1 line) but
         source has N tasks. Full-file must find all tasks → rb-move, not rb-lost.
         (Regression for "Home (Yara)" row where count dropped 102→1 on modal open.)
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
                stat: str = "1 file changed", pre_classification: list | None = None,
                cross_row_issues: list | None = None) -> str:
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
        pre_classification=pre_classification,
        cross_row_issues=cross_row_issues,
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
    """JS-06: Lines matching source removed appear in dest panel; unmatched lines are excluded.

    The old tab-based UI (Moved/New/Cross tabs) was removed. The dest panel now shows only
    confirmed-moved lines. 'Brand new' dest lines that have no source match are NOT shown
    in the dest panel (they surface as untraced/anomaly if unclaimed by any row).
    """
    base_url, serve_dir = http_server

    src_removed = "- [ ] task one"
    dest_added_moved = "- [ ] task one >2026-04-24"   # matches (prefix match after norm)
    dest_added_new   = "- [ ] brand new task"           # no match → not in dest panel

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Work", "summary": "tasks",
                  "destination": "[[Calendar/20260421]]"}]

    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["## Work", src_removed], "added": []},
        {"path": "Calendar/20260421.md",
         "added": [dest_added_moved, dest_added_new], "removed": []},
    ])
    page_name = _write_page(serve_dir, "js06.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    page.wait_for_function(
        "() => document.querySelectorAll('.row-badge.rb-pending').length === 0",
        timeout=10_000,
    )

    # Open modal and check dest panel shows matched line, not unmatched
    page.click(".view-btn")
    page.wait_for_selector("#modal-overlay.open")

    dest_text = page.eval_on_selector("#modal-dest-lines", "el => el.textContent")
    badge_class = page.eval_on_selector("tr[data-row-idx='0'] .row-badge", "el => el.className")
    browser.close()

    assert "task one" in dest_text, (
        f"Matched line 'task one' should appear in dest panel. dest_text={dest_text!r}"
    )
    assert "brand new task" not in dest_text, (
        f"Unmatched 'brand new task' must NOT appear in dest panel. dest_text={dest_text!r}"
    )
    assert "rb-move" in badge_class, f"Row should be rb-move. Got: {badge_class}"


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
    """JS-08: Line from file B that lands in dest doesn't inflate row A's move count.

    The old Cross tab was removed. Now cross-file lines are handled by the global
    removed map (B-13 layer 2): they are NOT counted as untraced anomalies for row A.
    Row A should classify as rb-move (its own line confirmed moved).
    """
    base_url, serve_dir = http_server

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Work", "summary": "items",
                  "destination": "[[Calendar/20260421]]"}]

    shared_task = "- [ ] shared task"
    diff = _make_diff([
        # Source A — removes unique task A
        {"path": "Calendar/20260413.md",
         "removed": ["## Work", "- [ ] unique task A"], "added": []},
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

    page.wait_for_function(
        "() => document.querySelectorAll('.row-badge.rb-pending').length === 0",
        timeout=10_000,
    )

    badge_class = page.eval_on_selector(
        "tr[data-row-idx='0'] .row-badge", "el => el.className"
    )
    browser.close()

    # Row A's unique task arrived at dest → should be rb-move, not rb-lost or rb-untraced
    assert "rb-move" in badge_class, (
        f"JS-08: Row A should be rb-move (unique task A confirmed moved). Got: {badge_class}"
    )


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
    """JS-10: Noise lines (code fences, empty checkboxes, HRs) don't inflate classification.

    The old New tab was removed. Noise lines in the dest diff should be filtered by
    isNoiseLine() and not count toward untraced/anomaly scoring. With noise filtered out,
    the dest has no real unclaimed content → row should be rb-empty (not rb-untraced).
    """
    base_url, serve_dir = http_server

    noise_lines  = ["```", "```python", "---", "- [ ]", "- [ ]  >2026-04-24"]

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Work", "summary": "items",
                  "destination": "[[Calendar/20260421]]"}]

    diff = _make_diff([
        # Source has no removed lines that match dest → total=0
        {"path": "Calendar/20260413.md", "removed": [], "added": []},
        {"path": "Calendar/20260421.md",
         "added": noise_lines, "removed": []},
    ])
    page_name = _write_page(serve_dir, "js10.html", diff, narrative)

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

    # All dest additions are noise → should be empty (or move), NOT untraced
    assert "rb-untraced" not in badge_class, (
        f"JS-10: noise lines must not count as untraced. Badge: {badge_class}"
    )


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
# JS-12  Mixed row — compound badge →1 ✗1 (blocks model), row type = lost, no sub-row
# ---------------------------------------------------------------------------

def test_js12_mixed_row_badge_and_modal(playwright, http_server):
    """JS-12: Some lines moved, some lost → compound badge →1 ✗1 (rb-lost), no sub-row."""
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
    badge_text = page.eval_on_selector(
        "tr[data-row-idx='0'] .row-badge", "el => el.textContent"
    )
    modal_text = page.eval_on_selector("#modal-body", "el => el.textContent")
    # Blocks model: no sub-row — the compound badge carries both counts
    sub_row = page.query_selector("tr[data-mixed-lost-for='0']")
    browser.close()

    # Compound badge: rb-lost class (Mixed collapsed into Lost), text shows →N ✗M
    assert "rb-lost" in badge_class, (
        f"Expected rb-lost badge on compound row (Mixed merged into Lost), got: {badge_class}"
    )
    assert "→" in badge_text and "✗" in badge_text, (
        f"Expected compound →N ✗M badge text, got: {badge_text!r}"
    )
    assert sub_row is None, "Expected no sub-row injection (blocks model replaces sub-row)"
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
# JS-19  Full-file: source-empty + dest has unrelated additions → anomaly
# ---------------------------------------------------------------------------

def test_js19_source_empty_dest_has_additions_is_anomaly(playwright, http_server):
    """JS-19 (post V-47a removal, #82): Source section has no removed lines.
    Dest file has an addition under a different section ('## Other Work').

    With full-file (V-47a removed): addedLines includes '- some other task'.
    Source empty → newContent not attributable to any sweep → trueNewCount=1 → anomaly.

    This is the correct classification: something appeared in dest with no corresponding
    breadcrumb row — a genuine anomaly.
    """
    base_url, serve_dir = http_server

    narrative = [{"date": "2026-04-16", "source_file": "Calendar/20260416.md",
                  "section": "## Anthropic GitHub refs", "summary": "github refs section",
                  "destination": "[[plan]]"}]

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

    assert "rb-untraced" in badge_class, (
        f"V-47a removed: source-empty + dest has unrelated addition → should be rb-untraced (anomaly). "
        f"Got: {badge_class!r}"
    )


# ---------------------------------------------------------------------------
# JS-20  #37: compound-badge Lost row (→N ✗M) has data-row-type=lost,
#         appears under ✗ Lost filter, disappears under → Move / ⚡ Mixed filters
# ---------------------------------------------------------------------------

def test_js20_compound_lost_row_filter_visibility(playwright, http_server):
    """JS-20: Compound row (some moved, some lost) → data-row-type=lost, visible in Lost filter."""
    base_url, serve_dir = http_server

    moved_task = "- [ ] task that arrives"
    lost_task  = "- [ ] task that gets lost"
    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Work", "summary": "compound lost",
                  "destination": "[[Calendar/20260421]]"}]
    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["## Work", moved_task, lost_task], "added": []},
        {"path": "Calendar/20260421.md",
         "added": ["## Work", f"{moved_task} >2026-04-24"], "removed": []},
    ])
    page_name = _write_page(serve_dir, "js20.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    page.click(".view-btn")
    page.wait_for_selector("#modal-overlay.open")
    page.keyboard.press("Escape")

    row_type = page.eval_on_selector(
        "tr[data-row-idx='0']", "el => el.dataset.rowType"
    )

    # Filter by Lost — compound row must be visible
    page.eval_on_selector("button[data-type='lost']", "el => el.click()")
    visible_after_lost = page.eval_on_selector(
        "tr[data-row-idx='0']", "el => el.style.display !== 'none'"
    )

    # Filter by Move — compound row must be hidden
    page.eval_on_selector("button[data-type='move']", "el => el.click()")
    visible_after_move = page.eval_on_selector(
        "tr[data-row-idx='0']", "el => el.style.display !== 'none'"
    )

    browser.close()

    assert row_type == "lost", (
        f"Compound row (some moved, some lost) must have data-row-type=lost, got: {row_type!r}"
    )
    assert visible_after_lost, "Compound row must be visible when filtering by ✗ Lost"
    assert not visible_after_move, "Compound row must be hidden when filtering by → Move"


# ---------------------------------------------------------------------------
# JS-21  filterValidPairs: noise-line match doesn't inflate movedCount
#         → lostCount must never be negative
# ---------------------------------------------------------------------------

def test_js21_noise_line_match_no_negative_lostcount(playwright, http_server):
    """JS-21: Empty checkbox in both source and dest shouldn't inflate movedCount → lostCount >= 0."""
    base_url, serve_dir = http_server

    real_task   = "- [ ] Review Jeff Charts"
    noise_line  = "- [ ] "          # empty checkbox — normLine = ""
    arrived     = "- [x] Review Jeff Charts >2026-04-24"
    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Jeff goals", "summary": "Get goals for Jeff",
                  "destination": "[[🏢260318 Understanding Org Goals]]"}]
    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["## Jeff goals", real_task, noise_line], "added": []},
        {"path": "🏢260318 Understanding Org Goals.md",
         "added": ["## Jeff goals", arrived, noise_line], "removed": []},
    ])
    page_name = _write_page(serve_dir, "js21.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")

    page.wait_for_function(
        "() => document.querySelectorAll('.row-badge.rb-pending').length === 0",
        timeout=10_000,
    )

    count_text = page.eval_on_selector(
        "tr[data-row-idx='0'] .count-col", "el => el.textContent"
    )
    badge_class = page.eval_on_selector(
        "tr[data-row-idx='0'] .row-badge", "el => el.className"
    )
    browser.close()

    # lostCount must not be negative — noise match inflating movedCount is the bug
    count_val = count_text.strip().lstrip('+')
    try:
        numeric = int(count_val.split('+')[0].split('-')[0] or '0')
    except ValueError:
        numeric = 0
    assert '-' not in count_text or count_text.strip() == '·', (
        f"lostCount must not be negative — got count: {count_text!r}, badge: {badge_class}"
    )
    # Row must be move (real_task arrived) or at most lost with count >= 0
    assert 'rb-pending' not in badge_class, f"Badge not updated: {badge_class}"


# JS-22  V-47a threshold normalisation: composite section name must not lock dest
#        to a weakly-matching section and misclassify a clean move as Lost.
# ---------------------------------------------------------------------------

def test_js22_v47a_composite_section_name_fallback(playwright, http_server):
    """JS-22: "Config Agent ARB" (3-token query) should not match "## Agent Development"
    (1/3 tokens = 0.33 normalized, below 0.5 threshold) — must fall back to full-file
    additions and find the ARB lines under ## Next Steps → type=move, badge rb-move."""
    base_url, serve_dir = http_server

    arb_task1 = "- [ ] Omar Eid I'm putting you in charge with ARB."
    arb_task2 = "- [ ] What do I need to do for ARB"
    arb_task3 = "- [ ] Make a detailed diagram of the security model"

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Config Agent ARB", "summary": "ARB governance tasks",
                  "destination": "[[Hardening A2A POC]]"}]
    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["## Config Agent ARB", arb_task1, arb_task2, arb_task3],
         "added": []},
        {"path": "Hardening A2A POC.md",
         "added": [
             # ARB tasks land under ## Next Steps — not a section matching the query
             "## Next Steps",
             arb_task1 + " >2026-04-26",
             arb_task2 + " >2026-04-26",
             arb_task3 + " >2026-04-26",
             # Unrelated section that shares "agent" token — the old bug would lock here
             "## Agent Development",
             "- [ ] Setup CLI tools",
             "- [ ] Implement story tasks",
         ],
         "removed": []},
    ])
    page_name = _write_page(serve_dir, "js22.html", diff, narrative)

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

    assert "rb-move" in badge_class, (
        f"Expected rb-move (ARB lines in full-file dest additions) but got: {badge_class!r}. "
        "V-47a likely locked destination to '## Agent Development' (1-token match) instead of "
        "falling back to full-file additions."
    )


# JS-23  V-47a: de-pluralized stem match must not lock dest for 2-token query.
#        "eval checks" → "## For Evals": "evals" de-pluralizes to "eval" = qtS → score 1.0.
#        Old threshold 0.5 (flat): 1.0 ≥ 0.5 → wrongly locks to ## For Evals.
#        New threshold 2×0.6=1.2: 1.0 < 1.2 → fallback → eval lines in full-file → move.
# ---------------------------------------------------------------------------

def test_js23_v47a_deplural_stem_match_fallback(playwright, http_server):
    """JS-23: 'eval checks' vs '## For Evals' — de-plural stem gives score 1.0 which
    must NOT pass threshold 1.2 (2 tokens × 0.6). Must fallback → rb-move."""
    base_url, serve_dir = http_server

    eval_task1 = "- [ ] Add deterministic grader vs llm in eval report"
    eval_task2 = "- [ ] Claude is not taking a straight line from a/b"
    eval_task3 = "straight light check"

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Eval checks", "summary": "Quality benchmarks",
                  "destination": "[[Hardening A2A POC]]"}]
    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["# Eval checks", eval_task1, eval_task2, eval_task3],
         "added": []},
        {"path": "Hardening A2A POC.md",
         "added": [
             # Eval tasks land under ## Collaborators — unrelated section name
             "## Collaborators",
             eval_task1 + " >2026-04-26",
             eval_task2 + " >2026-04-26",
             eval_task3,
             # The de-plural trap: "For Evals" de-pluralizes "evals"→"eval" = "eval" in query
             # Old code: score 1.0 ≥ 0.5 → locks here (wrong). New: 1.0 < 1.2 → fallback.
             "## For Evals",
             "- [ ] Unrelated eval framework task",
             "- [ ] Another unrelated evals task",
         ],
         "removed": []},
    ])
    page_name = _write_page(serve_dir, "js23.html", diff, narrative)

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

    assert "rb-move" in badge_class, (
        f"Expected rb-move (eval lines in ## Collaborators, full-file fallback) but got: {badge_class!r}. "
        "V-47a likely locked to '## For Evals' via de-plural stem match (score=1.0 ≥ old threshold 0.5)."
    )


# JS-24  V-R6: breadcrumb destination mismatch banner.
#        Breadcrumb says destination=20260426 but source lines were added to a plan file instead.
#        Portal should show rb-lost (lines not in the breadcrumb dest) AND an amber
#        "⚠ Breadcrumb destination mismatch" banner naming the file where the lines landed.
# ---------------------------------------------------------------------------

def test_js24_v_r6_breadcrumb_destination_mismatch(playwright, http_server):
    """JS-24: Lost lines found in a different destination file → V-R6 banner shown in modal.
    Scenario mirrors the real 20260414 Coffee House row: breadcrumb points to 20260426
    but lines landed in the NaqshCoffee Coffee House Site plan instead."""
    base_url, serve_dir = http_server

    line1 = "https://coffee-house.bytesofpurpose.com/ needs a lot of work"
    line2 = "Omar@naqshcoffee.com"
    line3 = "Make a coffee cup animation"

    narrative = [{"date": "2026-04-14", "source_file": "Calendar/20260414.md",
                  "section": "NaqshCoffee site + emails + Facebook dashboard",
                  "summary": "Coffee House tasks",
                  "destination": "[[20260426]]"}]
    diff = _make_diff([
        # Source: calendar removes the section header + three lines
        {"path": "Calendar/20260414.md",
         "removed": ["## NaqshCoffee site + emails + Facebook dashboard", line1, line2, line3],
         "added": []},
        # Breadcrumb destination (20260426): no additions — lines didn't land here
        {"path": "Calendar/20260426.md",
         "removed": [],
         "added": ["## Rolled-over tasks"]},
        # Actual landing file: the plan file got the lines (sweep routed here instead)
        {"path": "Notes/NaqshCoffee/Plans/Coffee House Site.md",
         "removed": [],
         "added": [line1 + " >2026-04-26", line2, line3 + " >2026-04-26"]},
    ])
    page_name = _write_page(serve_dir, "js24.html", diff, narrative)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")
    page.wait_for_function(
        "() => document.querySelectorAll('.row-badge.rb-pending').length === 0",
        timeout=10_000,
    )

    # Row should be rb-went-to: all 3 lines found in another diff file (went elsewhere, not truly absent).
    badge_class = page.eval_on_selector(
        "tr[data-row-idx='0'] .row-badge", "el => el.className"
    )
    assert "rb-went-to" in badge_class, (
        f"Expected rb-went-to (all lines found in Coffee House Site.md — went elsewhere) "
        f"but got: {badge_class!r}. V-R6 went-to classification not firing."
    )

    # Open modal — ⇢ banner should appear naming the actual destination
    page.click("tr[data-row-idx='0'] button.view-btn")
    page.wait_for_selector(".v-r6-banner")

    banner_text = page.eval_on_selector(".v-r6-banner", "el => el.textContent")
    assert "Coffee House Site" in banner_text, (
        f"V-R6 banner should name the file where lines landed. Got: {banner_text!r}"
    )
    assert "Content arrived at a different destination" in banner_text, (
        f"V-R6 banner should say 'Content arrived at a different destination'. Got: {banner_text!r}"
    )
    browser.close()


# JS-25  V-R6 badge promotion: all lost lines found in other diff files → rb-move.
#        Scenario: "References" breadcrumb says →20260424, but lines landed in
#        References[AI-Tools].md and Policies.md. Portal must show rb-move, not rb-lost.
# ---------------------------------------------------------------------------

def test_js25_v_r6_badge_promotion_misrouted_all_found(playwright, http_server):
    """JS-25: When ALL reported-lost lines are found in other diff files, the badge
    must be classified as rb-went-to. Only lines absent from the entire
    diff count as genuinely absent (rb-lost)."""
    base_url, serve_dir = http_server

    line1 = "React DevTools: https://reactjs.org/link/react-devtools"
    line2 = "Privacy by Design SP: https://rustici.nowlearning.servicenow.com/policy.pdf"
    line3 = "https://www.anthropic.com/glasswing"

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "References",
                  "summary": "React DevTools, Privacy SP, Anthropic glasswing",
                  "destination": "[[20260424]]"}]
    diff = _make_diff([
        # Source: calendar removes 3 reference lines under ## References
        {"path": "Calendar/20260413.md",
         "removed": ["## References", line1, line2, line3],
         "added": []},
        # Breadcrumb destination (20260424): no relevant additions — lines didn't land here
        {"path": "Calendar/20260424.md",
         "removed": [],
         "added": ["## Rolled over tasks"]},
        # Lines actually landed in two reference files
        {"path": "Notes/ServiceNow/Lists/References-AI-Tools.md",
         "removed": [],
         "added": [line1]},
        {"path": "Notes/ServiceNow/Lists/Policies.md",
         "removed": [],
         "added": [line2]},
        {"path": "Notes/ServiceNow/Lists/References-AI.md",
         "removed": [],
         "added": [line3]},
    ])
    page_name = _write_page(serve_dir, "js25.html", diff, narrative)

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

    assert "rb-went-to" in badge_class, (
        f"Expected rb-went-to — all 3 lines found in other diff files (went elsewhere, not truly absent). "
        f"Got: {badge_class!r}. V-R6 went-to classification not firing in classifyRow."
    )


# JS-26  V-47a removal (#82): wrong-section lock caused count to drop N→1 on badge.
#        Source removes N tasks under "Home (Yara)". Dest file has:
#          - ## Home  (1 added line — would trap V-47a via "home" token match)
#          - ## Planning (all N tasks land here)
#        Full-file (post V-47a removal): finds all N tasks → rb-move.
# ---------------------------------------------------------------------------

def test_js26_v47a_removal_wrong_section_lock(playwright, http_server):
    """JS-26: 'Home (Yara)' section name could match '## Home' via single-token overlap.
    V-47a would lock addedLines to ## Home (1 task) and miss the 5 tasks under ## Planning,
    producing lostCount=4 and badge rb-lost. After V-47a removal, full-file is always used
    → all 5 tasks found → rb-move.

    Regression test for the real portal bug where row count dropped 102→1 on modal open.
    """
    base_url, serve_dir = http_server

    task1 = "- [ ] Withdraw Yara from ballet class next term is quite long"
    task2 = "- [ ] Book dentist appointment for Yara in the spring"
    task3 = "- [ ] Organise play date with Sofia and Yara is happening"
    task4 = "- [ ] Buy school supplies for Yara upcoming year starts soon"
    task5 = "- [ ] Review afterschool schedule for Yara this semester long"

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Home (Yara)", "summary": "Yara home tasks",
                  "destination": "[[Family Planning]]"}]

    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["## Home (Yara)", task1, task2, task3, task4, task5],
         "added": []},
        {"path": "Family Planning.md",
         "added": [
             # Trap section: V-47a would lock here via "home" token match (1 task only)
             "## Home",
             "- [ ] Unrelated home maintenance task goes here",
             # Actual destination: all 5 Yara tasks land here
             "## Planning",
             task1 + " >2026-04-30",
             task2 + " >2026-04-30",
             task3 + " >2026-04-30",
             task4 + " >2026-04-30",
             task5 + " >2026-04-30",
         ],
         "removed": []},
    ])

    page_name = _write_page(serve_dir, "js26.html", diff, narrative)

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

    assert "rb-move" in badge_class, (
        f"Expected rb-move — all 5 Yara tasks found under ## Planning (full-file). "
        f"Got: {badge_class!r}. V-47a may still be locking dest to '## Home' (1 task)."
    )


# ---------------------------------------------------------------------------
# JS-27  Mental model invariant: went-to badge (#86/#87)
#         Source lines removed, breadcrumb dest empty, lines found in OTHER file.
#         Badge must be rb-went-to, not rb-move or rb-lost.
# ---------------------------------------------------------------------------

def test_js27_went_to_badge(playwright, http_server):
    """JS-27: Source removed, nothing at breadcrumb dest, lines found in another diff file
    → badge must be rb-went-to (⇢), not rb-move (→) or rb-lost (✗)."""
    base_url, serve_dir = http_server

    task1 = "- [ ] Design the NaqshCoffee logo for the coffee packaging"
    task2 = "- [ ] Write brand guidelines document for Bikar project"

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "NaqshCoffee",
                  "summary": "NaqshCoffee tasks",
                  "destination": "[[NaqshCoffee/Plans/Bikar Plan]]"}]
    diff = _make_diff([
        # Source: tasks removed from calendar
        {"path": "Calendar/20260413.md",
         "removed": ["## NaqshCoffee", task1, task2], "added": []},
        # Breadcrumb dest (Bikar Plan): no additions — lines didn't land here
        {"path": "NaqshCoffee/Plans/Bikar Plan.md",
         "removed": [], "added": ["## Overview"]},
        # Actual landing file: lines found here instead
        {"path": "NaqshCoffee/Plans/Coffee House Design.md",
         "removed": [], "added": [task1, task2]},
    ])
    page_name = _write_page(serve_dir, "js27.html", diff, narrative)

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

    assert "rb-went-to" in badge_class, (
        f"Expected rb-went-to — both lines found in Coffee House Design.md, not Bikar Plan. "
        f"Got: {badge_class!r}."
    )
    assert "rb-move" not in badge_class, "rb-move must NOT appear when lines went to a different file"
    assert "rb-lost" not in badge_class, "rb-lost must NOT appear when lines are found in diff"


# ---------------------------------------------------------------------------
# JS-28  Mental model invariant: absent badge (#86)
#         Source lines removed, NOT found in any diff addition anywhere.
#         Badge must be rb-lost (✗ Absent).
# ---------------------------------------------------------------------------

def test_js28_absent_not_anywhere(playwright, http_server):
    """JS-28: Source removed, line not in ANY diff addition → badge must be rb-lost (✗ Absent)."""
    base_url, serve_dir = http_server

    task1 = "- [ ] A task that simply vanished from all diff additions"
    task2 = "- [ ] Another task with no trace in any added line"

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Work",
                  "summary": "Missing tasks",
                  "destination": "[[Notes/Work/Backlog]]"}]
    diff = _make_diff([
        # Source: tasks removed from calendar
        {"path": "Calendar/20260413.md",
         "removed": ["## Work", task1, task2], "added": []},
        # Breadcrumb dest: no additions at all
        {"path": "Notes/Work/Backlog.md",
         "removed": [], "added": ["## Someday"]},
        # Other files: completely unrelated additions
        {"path": "Notes/Work/Projects.md",
         "removed": [], "added": ["- [ ] Totally unrelated project task here"]},
    ])
    page_name = _write_page(serve_dir, "js28.html", diff, narrative)

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

    assert "rb-lost" in badge_class, (
        f"Expected rb-lost — both tasks absent from all diff additions. "
        f"Got: {badge_class!r}."
    )
    assert "rb-went-to" not in badge_class, "rb-went-to must NOT appear when lines are absent from diff"
    assert "rb-move" not in badge_class, "rb-move must NOT appear when lines didn't arrive"


# ---------------------------------------------------------------------------
# JS-29  PRE_CLASSIFICATION fallback: Python says moved but JS re-classification
#         fails (e.g. B-15 redirect). Modal must show source lines with a
#         "confirmed by sweep engine" note instead of "0 lines confirmed moved".
# ---------------------------------------------------------------------------

def test_js29_py_move_confirmed_fallback(playwright, http_server):
    """JS-29: B-15 redirect row — Python-primary modal shows moved_lines from Python,
    not 'No source lines matched'. JS can't follow the redirect but Python can.
    The modal renders from PRE_CLASSIFICATION.moved_lines (Python-primary path)."""
    base_url, serve_dir = http_server

    task = "- [ ] Design a Bikar pattern plugin for Figma with palette generation"

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Bikar",
                  "summary": "Bikar Figma plugin",
                  "destination": "[[Notes/Plans/Developing Bikar]]"}]
    # Diff: source has task removed; breadcrumb dest has only a redirect stub (no task line)
    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["# Bikar", task], "added": []},
        # Breadcrumb dest: only a redirect stub — no matching task line
        {"path": "Notes/Plans/Developing Bikar.md",
         "removed": [], "added": ["status: done", "> Migrated: see [[Notes/Plans/New Bikar]]"]},
        # Actual landing (linked plan) — task IS here but JS won't follow the redirect
        {"path": "Notes/Plans/New Bikar.md",
         "removed": [], "added": [task]},
    ])
    # Python PRE_CLASSIFICATION: followed the B-15 redirect and confirmed the move.
    # Includes moved_lines so the Python-primary modal path is triggered (#91).
    pre_class = [{"idx": 0, "type": "move", "moved_count": 1, "lost_count": 0,
                  "truly_lost_lines": [], "moved_lines": [task], "dest_lines": [task],
                  "went_to_details": {}, "line_statuses": {task.strip().lower(): "move"},
                  "misrouted_count": 0, "went_to_files": [], "issues": ["b15_redirect"]}]
    page_name = _write_page(serve_dir, "js29.html", diff, narrative, pre_classification=pre_class)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")
    page.wait_for_function(
        "() => document.querySelectorAll('.row-badge.rb-pending').length === 0",
        timeout=10_000,
    )

    # Badge should show → (move) from PRE_CLASSIFICATION
    badge_class = page.eval_on_selector(
        "tr[data-row-idx='0'] .row-badge", "el => el.className"
    )
    assert "rb-move" in badge_class, f"Expected rb-move from PRE_CLASSIFICATION, got: {badge_class!r}"

    # Open modal
    page.click("tr[data-row-idx='0'] button.view-btn")
    page.wait_for_selector("#modal-overlay.open")

    modal_text = page.eval_on_selector("#modal-body", "el => el.textContent")
    # Python-primary path: dest panel exists and shows the dest task (from pc.dest_lines).
    # The old _pyMoveConfirmed fallback showed "0 lines confirmed moved" — no task in dest panel.
    dest_panel = page.query_selector("#modal-dest-lines")
    dest_text = dest_panel.text_content() if dest_panel else ""
    browser.close()

    # Python-primary path: source line visible (from moved_lines), "confirmed moved" in count label
    assert "confirmed" in modal_text.lower(), (
        f"Modal must show 'confirmed moved' count label from Python-primary path. Got: {modal_text!r}"
    )
    assert "No source lines matched" not in modal_text, (
        f"Modal must NOT show 'No source lines matched' when Python confirmed the move"
    )
    # Source task line must appear in the modal
    clean_task = "Design a Bikar pattern plugin for Figma with palette generation"
    assert clean_task.lower() in modal_text.lower(), (
        f"Source task line must be visible in modal. Got: {modal_text!r}"
    )
    assert clean_task.lower() in dest_text.lower(), (
        f"Dest panel must show matched task from Python pc.dest_lines. Got: {dest_text!r}"
    )


# JS-30  PRE_CLASSIFICATION: moved_lines and dest_lines embedded and accessible
#         from _rowClassifications after Phase E seeding.
# ---------------------------------------------------------------------------

def test_js30_pre_classification_has_line_content(playwright, http_server):
    """JS-30: After Phase E seeding, _rowClassifications entry has movedLines and
    destLines arrays derived from Python PRE_CLASSIFICATION moved_lines/dest_lines."""
    base_url, serve_dir = http_server

    task = "- [ ] Implement Bikar palette generation feature in Figma plugin"

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Design", "summary": "Bikar palette",
                  "destination": "[[Notes/Plans/Bikar]]"}]
    diff = _make_diff([
        {"path": "Calendar/20260413.md", "removed": [task], "added": []},
        {"path": "Notes/Plans/Bikar.md", "removed": [], "added": [task]},
    ])
    clean = "Implement Bikar palette generation feature in Figma plugin"
    pre_class = [{"idx": 0, "type": "move", "moved_count": 1, "lost_count": 0,
                  "truly_lost_lines": [], "moved_lines": [task], "dest_lines": [task],
                  "went_to_details": {}, "line_statuses": {task.strip().lower(): "move"},
                  "misrouted_count": 0, "went_to_files": [], "issues": []}]
    page_name = _write_page(serve_dir, "js30.html", diff, narrative, pre_classification=pre_class)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")
    page.wait_for_function(
        "() => document.querySelectorAll('.row-badge.rb-pending').length === 0",
        timeout=10_000,
    )

    # Check that PRE_CLASSIFICATION constant has moved_lines and dest_lines embedded
    moved_lines_len = page.evaluate(
        "() => { const pc = PRE_CLASSIFICATION && PRE_CLASSIFICATION.find(p => p.idx === 0); "
        "return pc ? (pc.moved_lines || []).length : -1; }"
    )
    assert moved_lines_len == 1, (
        f"PRE_CLASSIFICATION[0].moved_lines must have 1 entry, got {moved_lines_len}"
    )

    dest_lines_len = page.evaluate(
        "() => { const pc = PRE_CLASSIFICATION && PRE_CLASSIFICATION.find(p => p.idx === 0); "
        "return pc ? (pc.dest_lines || []).length : -1; }"
    )
    assert dest_lines_len == 1, (
        f"PRE_CLASSIFICATION[0].dest_lines must have 1 entry, got {dest_lines_len}"
    )

    # Open modal — source line must appear
    page.click("tr[data-row-idx='0'] button.view-btn")
    page.wait_for_selector("#modal-overlay.open")
    modal_text = page.eval_on_selector("#modal-body", "el => el.textContent")
    browser.close()

    assert clean.lower() in modal_text.lower(), (
        f"Source task must appear in modal body. Got: {modal_text!r}"
    )


# JS-31  Python-primary modal path: renders from PRE_CLASSIFICATION.moved_lines even
#         when JS section extraction would fail (section name not in diff).
# ---------------------------------------------------------------------------

def test_js31_python_primary_modal_renders_moved_lines(playwright, http_server):
    """JS-31: When PRE_CLASSIFICATION has moved_lines, the modal renders from Python data.
    The task is removed under a section whose header is NOT in the diff, so JS would
    find no removed lines — but the Python-primary path shows the task from moved_lines."""
    base_url, serve_dir = http_server

    task = "- [ ] Configure ESGenius scoring pipeline for batch processing workflows"
    dest_task = "- [ ] Configure ESGenius scoring pipeline for batch processing workflows >2026-04-30"

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "ESGenius",   # section header NOT in diff → JS finds nothing
                  "summary": "ESGenius config", "destination": "[[Notes/Plans/ESGenius]]"}]
    diff = _make_diff([
        # Source removes the task but with NO section header — JS extractSectionLines returns []
        {"path": "Calendar/20260413.md", "removed": [task], "added": []},
        {"path": "Notes/Plans/ESGenius.md", "removed": [], "added": [dest_task]},
    ])
    # Python PRE_CLASSIFICATION has moved_lines (Python uses disk content + section inference)
    pre_class = [{"idx": 0, "type": "move", "moved_count": 1, "lost_count": 0,
                  "truly_lost_lines": [], "moved_lines": [task], "dest_lines": [dest_task],
                  "went_to_details": {}, "line_statuses": {task.strip().lower(): "move"},
                  "misrouted_count": 0, "went_to_files": [], "issues": []}]
    page_name = _write_page(serve_dir, "js31.html", diff, narrative, pre_classification=pre_class)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")
    page.wait_for_function(
        "() => document.querySelectorAll('.row-badge.rb-pending').length === 0",
        timeout=10_000,
    )

    page.click("tr[data-row-idx='0'] button.view-btn")
    page.wait_for_selector("#modal-overlay.open")
    modal_text = page.eval_on_selector("#modal-body", "el => el.textContent")
    dest_panel = page.query_selector("#modal-dest-lines")
    dest_text = dest_panel.text_content() if dest_panel else ""
    browser.close()

    clean = "Configure ESGenius scoring pipeline for batch processing workflows"
    assert clean.lower() in modal_text.lower(), (
        f"Source task must appear in modal from Python moved_lines, not JS extraction. Got: {modal_text!r}"
    )
    assert "No source lines matched" not in modal_text, (
        "Python-primary path must not show 'No source lines matched'"
    )
    assert "confirmed" in modal_text.lower(), (
        f"Count label must show 'confirmed moved' from Python-primary path. Got: {modal_text!r}"
    )
    # Dest panel must show the dest task from pc.dest_lines (includes due date suffix)
    assert "2026-04-30" in dest_text, (
        f"Dest panel must show dest_task (with due date) from Python pc.dest_lines. Got: {dest_text!r}"
    )


# JS-32  toggleSectionItems: per-line badges from PRE_CLASSIFICATION.line_statuses
# ---------------------------------------------------------------------------

def test_js32_toggle_section_items_line_statuses(playwright, http_server):
    """JS-32: Expanding a row shows per-line badges from line_statuses (Python-primary).
    B-15 redirect case: task was moved but only the redirect stub is in the breadcrumb dest.
    JS classifyDestLines would mark the task as ✗ (not in breadcrumb additions), but
    Python line_statuses says 'move' (Python followed the redirect). Badge must be → ."""
    base_url, serve_dir = http_server

    moved_task = "- [ ] Build ESGenius scoring API for integration test pipeline runs"

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "ESGenius", "summary": "ESGenius work",
                  "destination": "[[Notes/Plans/ESGenius]]"}]
    diff = _make_diff([
        {"path": "Calendar/20260413.md",
         "removed": ["## ESGenius", moved_task], "added": []},
        # Breadcrumb dest: only redirect stub — task NOT here (JS can't see it)
        {"path": "Notes/Plans/ESGenius.md",
         "removed": [], "added": ["> Migrated: see [[Notes/Plans/ESGenius2]]"]},
        # Actual dest after B-15 redirect — Python sees it, JS doesn't follow the link
        {"path": "Notes/Plans/ESGenius2.md",
         "removed": [], "added": [moved_task]},
    ])
    moved_norm = moved_task.strip().lower()
    # Python followed B-15: classifies as 'move', line_statuses maps task → 'move'
    pre_class = [{"idx": 0, "type": "move", "moved_count": 1, "lost_count": 0,
                  "truly_lost_lines": [], "moved_lines": [moved_task], "dest_lines": [moved_task],
                  "went_to_details": {}, "line_statuses": {moved_norm: "move"},
                  "misrouted_count": 0, "went_to_files": [], "issues": ["b15_redirect"]}]
    page_name = _write_page(serve_dir, "js32.html", diff, narrative, pre_classification=pre_class)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")
    page.wait_for_function(
        "() => document.querySelectorAll('.row-badge.rb-pending').length === 0",
        timeout=10_000,
    )

    # Click the ▶ expand button on row 0
    page.click("tr[data-row-idx='0'] .sec-toggle")
    page.wait_for_selector("tr.item-row")

    item_rows = page.eval_on_selector_all(
        "tr.item-row",
        """els => els.map(r => ({
            text: r.querySelector('.item-text')?.textContent?.trim() || '',
            badge: (r.querySelector('span') || {}).style?.color || ''
        }))"""
    )
    browser.close()

    assert len(item_rows) >= 1, f"Expected ≥1 item row, got {item_rows}"
    moved_row = next((r for r in item_rows if "scoring api" in r["text"].lower()), None)
    assert moved_row is not None, f"Moved task row not found: {item_rows}"

    # Python line_statuses says 'move' → green → badge (rgb(63, 185, 80) = #3fb950)
    # Without Python-primary, JS classifyDestLines would see only redirect stub → red ✗
    moved_badge = moved_row["badge"].lower()
    assert ("3fb950" in moved_badge or "63, 185, 80" in moved_badge or "→" in moved_row["text"]), (
        f"B-15 moved task must show green → from Python line_statuses. Got: {moved_row}"
    )


# ---------------------------------------------------------------------------
# JS-33  validation banner reads from Python PRE_CLASSIFICATION.issues[]
#        validateRowIntegrity must NOT exist in the page (deleted in A1).
# ---------------------------------------------------------------------------

def test_js33_validation_banner_from_python(playwright, http_server):
    """JS-33: Validation banner counts warnings from Python PRE_CLASSIFICATION.issues[].
    validateRowIntegrity must be deleted — verifying it no longer exists as a function."""
    base_url, serve_dir = http_server

    task = "- [ ] Missing task that has no dest match anywhere"

    narrative = [{"date": "2026-04-13", "source_file": "Calendar/20260413.md",
                  "section": "Work", "summary": "work item",
                  "destination": "[[Plans/WorkPlan]]"}]
    diff = _make_diff([
        {"path": "Calendar/20260413.md", "removed": [task], "added": []},
        {"path": "Plans/WorkPlan.md",    "removed": [], "added": [task]},
    ])
    # Row has inferred_section warning (no section header in diff)
    pre_class = [{"idx": 0, "type": "move", "moved_count": 1, "lost_count": 0,
                  "truly_lost_lines": [], "moved_lines": [task], "dest_lines": [task],
                  "went_to_details": {}, "line_statuses": {task.strip().lower(): "move"},
                  "misrouted_count": 0, "went_to_files": [], "inferred": True,
                  "issues": ["inferred_section"]}]
    page_name = _write_page(serve_dir, "js33.html", diff, narrative, pre_classification=pre_class)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")
    page.wait_for_function(
        "() => document.querySelectorAll('.row-badge.rb-pending').length === 0",
        timeout=10_000,
    )

    # Banner must show warning (1 row with issues)
    banner_text = page.text_content("#validation-banner")
    assert banner_text is not None, "validation-banner element not found"
    assert "1 row" in banner_text and "V-R" in banner_text, (
        f"Banner must show '1 row ... (V-R)' from Python issues[]. Got: {banner_text!r}"
    )

    # ⚠ warn icon must appear on the row
    warn_icon = page.query_selector("tr[data-row-idx='0'] .row-warn")
    assert warn_icon is not None, "Row must have ⚠ warn icon from annotateRowWarnings"

    # validateRowIntegrity must NOT exist (deleted in A1)
    has_validate_row = page.evaluate("() => typeof validateRowIntegrity !== 'undefined'")
    assert not has_validate_row, "validateRowIntegrity must be deleted from JS (A1)"

    browser.close()


# ---------------------------------------------------------------------------
# JS-34  CROSS_ROW_ISSUES embedded from Python; validateCrossRowConsistency deleted
# ---------------------------------------------------------------------------

def test_js34_cross_row_issues_from_python(playwright, http_server):
    """JS-34: CROSS_ROW_ISSUES is Python-embedded; validateCrossRowConsistency must not exist.
    When cross_row_issues is non-empty, banner shows V-C count."""
    base_url, serve_dir = http_server

    task = "- [ ] Task moved by two rows simultaneously"

    narrative = [
        {"date": "2026-04-13", "source_file": "Calendar/20260413.md",
         "section": "Work", "summary": "w1", "destination": "[[Plans/WorkPlan]]"},
        {"date": "2026-04-13", "source_file": "Calendar/20260413.md",
         "section": "Work", "summary": "w2", "destination": "[[Plans/WorkPlan]]"},
    ]
    diff = _make_diff([
        {"path": "Calendar/20260413.md", "removed": [task], "added": []},
        {"path": "Plans/WorkPlan.md",    "removed": [], "added": [task]},
    ])
    pre_class = [
        {"idx": 0, "type": "move", "moved_count": 1, "lost_count": 0,
         "truly_lost_lines": [], "moved_lines": [task], "dest_lines": [task],
         "went_to_details": {}, "line_statuses": {task.strip().lower(): "move"},
         "misrouted_count": 0, "went_to_files": [], "inferred": False, "issues": []},
        {"idx": 1, "type": "move", "moved_count": 1, "lost_count": 0,
         "truly_lost_lines": [], "moved_lines": [task], "dest_lines": [task],
         "went_to_details": {}, "line_statuses": {task.strip().lower(): "move"},
         "misrouted_count": 0, "went_to_files": [], "inferred": False, "issues": []},
    ]
    cross_issues = [f"V-C2: dest line claimed by rows [0, 1]: {task.strip().lower()[:60]}"]
    page_name = _write_page(serve_dir, "js34.html", diff, narrative,
                            pre_classification=pre_class, cross_row_issues=cross_issues)

    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(f"{base_url}/{page_name}")
    page.wait_for_selector(".nav-tbl")
    page.wait_for_function(
        "() => document.querySelectorAll('.row-badge.rb-pending').length === 0",
        timeout=10_000,
    )

    # CROSS_ROW_ISSUES must be accessible and have 1 entry
    cross_count = page.evaluate("() => CROSS_ROW_ISSUES.length")
    assert cross_count == 1, f"CROSS_ROW_ISSUES must have 1 entry, got {cross_count}"

    # Banner must mention V-C
    banner_text = page.text_content("#validation-banner")
    assert banner_text is not None, "validation-banner element not found"
    assert "V-C" in banner_text, f"Banner must mention V-C from CROSS_ROW_ISSUES. Got: {banner_text!r}"

    # validateCrossRowConsistency must NOT exist (deleted in A2)
    has_validate_cross = page.evaluate("() => typeof validateCrossRowConsistency !== 'undefined'")
    assert not has_validate_cross, "validateCrossRowConsistency must be deleted from JS (A2)"

    browser.close()
