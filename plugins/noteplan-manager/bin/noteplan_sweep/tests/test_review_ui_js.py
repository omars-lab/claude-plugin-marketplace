"""Browser-side tests for review_ui.py pure logic (window.__sweepTest).

Mirrors the test_sweep_review_js.py harness: serve the built page over a local
http.server and drive real Chromium. These tests exercise the framework-free
pure core (selection, provenance, status, split, wordDiff, finalize gating)
without needing a live API — the page's load() fetch failing is harmless because
window.__sweepTest is populated synchronously at parse time.
"""

import http.server
import sys
import threading
from pathlib import Path
from typing import Generator

import pytest

_BIN = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BIN))

from noteplan_sweep.review_ui import build_review_ui_html


@pytest.fixture(scope="session")
def http_server(tmp_path_factory) -> Generator:
    serve_dir = tmp_path_factory.mktemp("review_ui_serve")

    class SilentHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(serve_dir), **kwargs)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), SilentHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    (serve_dir / "review.html").write_text(
        build_review_ui_html("2026-07-09-01"), encoding="utf-8")
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture
def page(playwright, http_server):
    browser = playwright.chromium.launch()
    pg = browser.new_page()
    pg.goto(f"{http_server}/review.html")
    pg.wait_for_function("window.__sweepTest !== undefined")
    yield pg
    browser.close()


def ev(page, expr):
    return page.evaluate(expr)


# ---------------------------------------------------------------------------
# selectionReduce
# ---------------------------------------------------------------------------

def test_selection_click(page):
    r = ev(page, "__sweepTest.selectionReduce({anchor:null,selected:[]},{type:'click',idx:3})")
    assert r["anchor"] == 3 and r["selected"] == [3]


def test_selection_shift_range(page):
    r = ev(page, "__sweepTest.selectionReduce({anchor:2,selected:[2]},{type:'shiftClick',idx:5})")
    assert r["selected"] == [2, 3, 4, 5]


def test_selection_toggle(page):
    r = ev(page, "__sweepTest.selectionReduce({anchor:1,selected:[1,2]},{type:'toggle',idx:2})")
    assert r["selected"] == [1]


def test_selection_clear(page):
    r = ev(page, "__sweepTest.selectionReduce({anchor:1,selected:[1,2]},{type:'clear'})")
    assert r["anchor"] is None and r["selected"] == []


# ---------------------------------------------------------------------------
# provenance + status + finalize gating
# ---------------------------------------------------------------------------

def test_classify_provenance(page):
    assert ev(page, "__sweepTest.classifyProvenance('verbatim')") == "prov-verbatim"
    assert ev(page, "__sweepTest.classifyProvenance('transformed')") == "prov-transformed"
    assert ev(page, "__sweepTest.classifyProvenance('added')") == "prov-added"


def test_status_meta_resolved(page):
    assert ev(page, "__sweepTest.statusMeta('applied').resolved") is True
    assert ev(page, "__sweepTest.statusMeta('pending').resolved") is False
    assert ev(page, "__sweepTest.statusMeta('stale').glyph") == "⚠"


def test_can_finalize(page):
    assert ev(page, "__sweepTest.canFinalize({total:3,unresolved:0})") is True
    assert ev(page, "__sweepTest.canFinalize({total:3,unresolved:1})") is False
    assert ev(page, "__sweepTest.canFinalize({total:0,unresolved:0})") is False


# ---------------------------------------------------------------------------
# wordDiff
# ---------------------------------------------------------------------------

def test_word_diff_marks_change(page):
    ops = ev(page, "__sweepTest.wordDiff('call Dennis today','call Sam today')")
    dels = [o["t"] for o in ops if o["op"] == "del"]
    adds = [o["t"] for o in ops if o["op"] == "add"]
    assert "Dennis" in dels and "Sam" in adds
    assert any(o["op"] == "same" and o["t"] == "call" for o in ops)


# ---------------------------------------------------------------------------
# splitMoveClient (mirrors sweep_manifest.split_move)
# ---------------------------------------------------------------------------

_MOVE = """({
  id: 'mv-1',
  source: { file: 'Calendar/x.md', section_header:'# Work', line_start: 10, line_end: 12,
            lines: [{n:10,text:'l10',h:'a'},{n:11,text:'l11',h:'b'},{n:12,text:'l12',h:'c'}] },
  destination: { file:'Notes/P.md', section_header:'# Next', exists:true, create:null },
  content: { lines: [{text:'l10',provenance:'verbatim',source_n:10},
                     {text:'l11',provenance:'verbatim',source_n:11},
                     {text:'l12',provenance:'verbatim',source_n:12}] }
})"""


def test_split_partitions(page):
    kids = ev(page, f"__sweepTest.splitMoveClient({_MOVE}, "
                    "[{line_idxs:[0,1]},{line_idxs:[2],dest:{file:'Notes/H.md',section_header:'# E'}}])")
    assert len(kids) == 2
    assert [l["text"] for l in kids[0]["source"]["lines"]] == ["l10", "l11"]
    assert kids[1]["destination"]["file"] == "Notes/H.md"
    assert [c["text"] for c in kids[1]["content"]["lines"]] == ["l12"]


def test_split_keep_in_source_drops(page):
    kids = ev(page, f"__sweepTest.splitMoveClient({_MOVE}, "
                    "[{line_idxs:[0,2]},{line_idxs:[1],keep_in_source:true}])")
    assert len(kids) == 1
    assert [l["text"] for l in kids[0]["source"]["lines"]] == ["l10", "l12"]


def test_split_rejects_overlap(page):
    err = ev(page, f"""(() => {{
      try {{ __sweepTest.splitMoveClient({_MOVE}, [{{line_idxs:[0]}},{{line_idxs:[0,1]}}]); return null; }}
      catch(e) {{ return e.message; }}
    }})()""")
    assert err and "multiple parts" in err


def test_locate_run_exact_at_hint(page):
    pos = ev(page, "__sweepTest.locateRun(['a','b','c','d'],['b','c'],1)")
    assert pos == 1


def test_locate_run_after_shift(page):
    # earlier approved move deleted lines → target now sits above the hint
    pos = ev(page, "__sweepTest.locateRun(['x','t1','t2','y'],['t1','t2'],3)")
    assert pos == 1  # regression: was mis-highlighted when keyed on stale line numbers


def test_locate_run_absent(page):
    assert ev(page, "__sweepTest.locateRun(['a','b'],['zzz'],0)") == -1


def test_locate_run_duplicate_picks_nearest(page):
    pos = ev(page, "__sweepTest.locateRun(['dup','x','dup','y'],['dup'],2)")
    assert pos == 2  # nearest to hint=2


def test_no_console_errors_on_load(page):
    # window.__sweepTest present and page structure rendered
    assert ev(page, "typeof __sweepTest.selectionReduce") == "function"
    assert ev(page, "!!document.getElementById('queue')") is True
