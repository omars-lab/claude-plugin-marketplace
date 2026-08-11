"""
ui_common.py — Shared CSS + JS helpers for NotePlan HTML surfaces.

BASE_CSS holds the dark-theme reset, header, modal shell, side-by-side diff
grid (.sbs/.row/.ln/.lc), badges, and narrative styles. Single source of
truth for the sweep snapshot page (sweep_review.py) and the interactive
review UI (review_ui.py).

IMPORTANT: BASE_CSS is interpolated into an f-string in sweep_review.py via
{ui_common.BASE_CSS}, so it uses SINGLE braces (plain string, not f-string)
and carries NO trailing newline (the template supplies the surrounding
<style>\n ... \n</style>). Do not double the braces or add a trailing \n.

JS_HELPERS holds tiny pure helpers (esc, normLine, bodyText, xcallbackUrl)
in single-brace form for direct inclusion in review_ui.py. The snapshot
builder keeps its own inline copies for byte-stability; keep them in sync.
"""

BASE_CSS = """\
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px;background:#0d1117;color:#e6edf3;display:flex;flex-direction:column;height:100vh}
#hdr{background:#161b22;border-bottom:1px solid #30363d;padding:10px 20px;display:flex;align-items:center;gap:16px;position:sticky;top:0;z-index:100}
#hdr h1{font-size:15px;font-weight:600;color:#58a6ff}
.stat{font-size:12px;color:#8b949e}
.tabs{display:flex;gap:4px;margin-left:auto}
.tab{padding:4px 12px;border-radius:4px;cursor:pointer;font-size:12px;background:transparent;color:#8b949e;border:1px solid transparent}
.tab.active{background:#21262d;color:#e6edf3;border-color:#30363d}
#filter-bar{background:#161b22;border-bottom:1px solid #30363d;padding:6px 20px;display:flex;align-items:center;gap:8px;flex-shrink:0}
.domain-chip,.type-chip{padding:3px 10px;border-radius:12px;cursor:pointer;font-size:12px;background:#21262d;color:#8b949e;border:1px solid #30363d}
.domain-chip.active{background:#1a3a28;color:#3fb950;border-color:#3fb950}
.type-chip.active{background:#1c2128;color:#e6edf3;border-color:#58a6ff}
.toggle-chip{padding:3px 10px;border-radius:12px;cursor:pointer;font-size:11px;background:#21262d;color:#484f58;border:1px dashed #30363d}
.toggle-chip.on{color:#8b949e;border-color:#484f58}
.filter-sep{color:#30363d;font-size:14px;margin:0 2px}
.copy-btn{margin-left:auto;padding:3px 10px;border-radius:4px;cursor:pointer;font-size:12px;background:#21262d;color:#8b949e;border:1px solid #30363d}
.copy-btn:hover{color:#e6edf3}
.orphaned-block{margin-top:16px;padding:12px 16px;border:1px solid #4a2f10;border-radius:8px;background:#1a1200}
.orphaned-hdr{font-size:12px;color:#d29922;margin-bottom:6px;font-weight:600}
.orphaned-block ul{list-style:none;padding:0}
.orphaned-block li{font-size:11.5px;color:#8b949e;font-family:'SF Mono','Fira Code',monospace;padding:2px 0}
.dest-link{color:#79c0ff;text-decoration:none;font-family:'SF Mono','Fira Code',monospace;font-size:11px}
.dest-link:hover{text-decoration:underline;color:#a5d6ff}
.view-btn{padding:1px 6px;border-radius:3px;cursor:pointer;font-size:11px;background:#21262d;color:#8b949e;border:1px solid #30363d}
.view-btn:hover{color:#e6edf3;border-color:#8b949e}
#modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:1000;align-items:center;justify-content:center}
#modal-overlay.open{display:flex}
.modal{background:#161b22;border:1px solid #30363d;border-radius:10px;width:92vw;max-width:1400px;max-height:88vh;display:flex;flex-direction:column;overflow:hidden}
.modal-hdr{padding:10px 20px;border-bottom:1px solid #30363d;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;gap:12px}
.modal-title{font-size:13px;font-weight:600;color:#e6edf3;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.modal-close{background:none;border:none;color:#8b949e;cursor:pointer;font-size:18px;line-height:1;padding:0 2px;flex-shrink:0}
.modal-close:hover{color:#e6edf3}
.modal-body{flex:1;min-height:0;padding:16px;display:grid;grid-template-columns:1fr 1fr;gap:16px;overflow:hidden}
.modal-body>div{min-width:0;overflow-y:auto;overflow-x:hidden;display:flex;flex-direction:column}
.modal-panel-hdr{font-size:11px;font-weight:600;color:#8b949e;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #30363d}
.modal-empty{color:#484f58;font-size:12px;padding:16px;text-align:center}
.diff-lines{font-family:'SF Mono','Fira Code',monospace;font-size:11.5px;line-height:18px;overflow-x:auto;flex:1}
.diff-line{padding:1px 8px;white-space:pre;font-family:'SF Mono','Fira Code',monospace;font-size:11.5px;line-height:18px}
.diff-line.removed{background:#4a0f1a;color:#ffdcd7}
.diff-line.added{background:#0e4429;color:#aff5b4}
.diff-line.new-content{background:#1f1200;color:#e3b341}
.diff-line.cross-moved{background:#0d1b2a;color:#79c0ff}
.modal-panel-tabs{display:flex;gap:4px;margin-bottom:8px}
.mpanel-tab{padding:2px 10px;border-radius:4px;cursor:pointer;font-size:11px;background:#21262d;color:#8b949e;border:1px solid #30363d}
.mpanel-tab.active{background:#1a3a28;color:#3fb950;border-color:#3fb950}
.mpanel-tab.new-tab.active{background:#2d1f00;color:#e3b341;border-color:#e3b341}
.mpanel-tab.cross-tab.active{background:#0d1b2a;color:#79c0ff;border-color:#79c0ff}
#layout{display:flex;flex:1;min-height:0}
#sidebar{width:260px;min-width:160px;background:#161b22;border-right:1px solid #30363d;overflow-y:auto;flex-shrink:0;padding:8px 0}
.fi{padding:5px 12px;cursor:pointer;display:flex;align-items:center;gap:8px;border-left:3px solid transparent;font-size:12px}
.fi:hover{background:#21262d}
.fi.active{background:#21262d;border-left-color:#58a6ff}
.fi .name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
.badge{font-size:10px;font-weight:700;padding:1px 5px;border-radius:3px;flex-shrink:0}
.ba{background:#1f4a2a;color:#3fb950}.bd{background:#4a1f2a;color:#f85149}.bm{background:#1f2d4a;color:#79c0ff}
#main{flex:1;overflow-y:auto;padding:16px}
/* ── Diff panel ── */
.fd{margin-bottom:20px;border:1px solid #30363d;border-radius:8px;overflow:hidden}
.fdh{background:#161b22;padding:7px 14px;font-size:12px;color:#8b949e;border-bottom:1px solid #30363d;display:flex;justify-content:space-between}
.fdh .fn{color:#e6edf3;font-weight:600;font-family:'SF Mono','Fira Code',monospace}
.sbs{display:grid;grid-template-columns:1fr 1fr;font-family:'SF Mono','Fira Code',monospace;font-size:11.5px}
.sbs-col{overflow:hidden;border-right:1px solid #30363d}
.sbs-col:last-child{border-right:none}
.sbs-col .col-hdr{background:#1c2128;padding:3px 8px;font-size:11px;color:#8b949e;border-bottom:1px solid #30363d}
.row{display:flex;min-height:18px}
.ln{width:36px;text-align:right;padding:0 6px;color:#484f58;user-select:none;border-right:1px solid #30363d;flex-shrink:0;line-height:18px}
.lc{flex:1;padding:0 6px;white-space:pre;overflow:hidden;line-height:18px}
.row.add{background:#0e4429}.row.add .ln{background:#0a3320;color:#3fb950}.row.add .lc{color:#aff5b4}
.row.del{background:#1a0a0f}.row.del .ln{background:#120508;color:#6e3a44}.row.del .lc{color:#6b7280}
.row.ctx{background:#0d1117}
.row.hdr{background:#1c2128}.row.hdr .lc{color:#8b949e}
.diff-ctx-hdr{font-family:'SF Mono','Fira Code',monospace;font-size:11px;padding:4px 8px 2px;color:#58a6ff;font-weight:600;background:#0d1117;border-top:1px solid #21262d;margin-top:6px}
.diff-ctx-skip{font-family:'SF Mono','Fira Code',monospace;font-size:11px;padding:0 8px 4px;color:#484f58;background:#0d1117}
.line-no{color:#484f58;font-size:10px;min-width:30px;display:inline-block;text-align:right;padding-right:8px;user-select:none;flex-shrink:0}
.pair-highlight{background:rgba(255,255,255,0.06)!important;outline:1px solid rgba(255,255,255,0.15);z-index:1;position:relative}
[data-pair-id]{cursor:pointer}
.move-badge{margin-left:6px;padding:0 5px;border-radius:3px;font-size:10px;background:#1a3a28;color:#3fb950;border:1px solid #3fb950;text-decoration:none;white-space:nowrap;flex-shrink:0}
.move-badge:hover{background:#204830}
.lost-badge{margin-left:6px;padding:0 5px;border-radius:3px;font-size:10px;background:#2d0a0a;color:#f85149;border:1px solid #f85149;white-space:nowrap;flex-shrink:0}
.row.add .lc{color:#aff5b4}.row.del .lc{color:#ffdcd7}
/* ── Narrative panel ── */
#narrative{padding:16px}
.day-block{margin-bottom:24px}
.day-hdr{font-size:14px;font-weight:600;color:#58a6ff;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #30363d}
.nav-tbl{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed}
.nav-tbl th{background:#161b22;padding:6px 10px;text-align:left;color:#8b949e;font-weight:500;border-bottom:2px solid #30363d;position:sticky;top:0;z-index:1}
.nav-tbl th:nth-child(1){width:28px}.nav-tbl th:nth-child(2){width:50px}.nav-tbl th:nth-child(3){width:18%}.nav-tbl th:nth-child(4){width:22%}.nav-tbl th:nth-child(5){width:88px}.nav-tbl th:nth-child(6){width:auto}.nav-tbl th:nth-child(7){width:44px}
.src-col{color:#58a6ff;font-family:monospace;font-size:11px;white-space:nowrap}
.row-badge{display:inline-block;font-size:11px;min-width:16px;text-align:center;border-radius:3px;padding:1px 4px;font-weight:600}
.rb-move{background:#1a3a28;color:#3fb950}.rb-lost{background:#2d0a0a;color:#f85149}.rb-went-to{background:#001730;color:#58a6ff}.rb-empty{background:#1c2128;color:#484f58}.rb-pending{color:#484f58}.rb-dropped{background:#2a1a0a;color:#d29922}.rb-new{background:#1a1a00;color:#e3b341}
.nav-tbl td{padding:5px 10px;border-bottom:1px solid #21262d;vertical-align:middle;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.nav-tbl tr:hover td{background:#161b22}
.nav-tbl .section-col{color:#e6edf3;font-weight:500}
.nav-tbl .summary-col{color:#8b949e}
.day-sep-row td{background:#0d1117;padding:14px 10px 5px;font-size:13px;font-weight:600;color:#58a6ff;border-bottom:1px solid #30363d;white-space:normal;overflow:visible}
.src-sep-row td{background:#0a0f1a;padding:4px 10px 3px;font-size:10px;font-weight:500;color:#3d6a9e;border-bottom:1px solid #1c2128;font-family:monospace;white-space:nowrap;overflow:visible}
.item-row td{background:#0a0d12;padding:3px 10px;border-bottom:1px solid #161b22;font-size:11px}
.item-row:hover td{background:#0d1117}
.item-row .item-text{color:#c9d1d9;font-family:'SF Mono','Fira Code',monospace;padding-left:20px}
.sec-toggle{padding:0 5px 0 0;background:none;border:none;color:#484f58;cursor:pointer;font-size:9px;vertical-align:middle}
.sec-toggle:hover{color:#8b949e}
.empty{color:#484f58;padding:24px;text-align:center}
/* ── Validation ── */
.row-warn{display:inline-block;font-size:10px;margin-left:4px;color:#e3b341;cursor:help;vertical-align:middle}
#validation-banner{padding:6px 16px;font-size:12px;border-bottom:1px solid #30363d;display:none}
#validation-banner.ok{background:#0e2a14;color:#3fb950;display:block}
#validation-banner.warn{background:#2d1f00;color:#e3b341;display:block}"""

JS_HELPERS = r"""
// ── ui_common shared helpers (kept in sync with sweep_review.py inline copies) ──
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
// Shared normaliser: strip date tags + hashtags, collapse whitespace, lowercase.
// Used only for staleness classification / display grouping — never for hashing.
const normLine = s => s.replace(/>\d{4}-\d{2}-\d{2}/g, '').replace(/#\w+/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
const bodyText = s => s.replace(/^[-*]\s*\[[x ]\]\s*/i, '').trim();
// Build a noteplan:// deep link from a destination wikilink or filename stem.
function xcallbackUrl(dest) {
  let raw = dest.replace(/\[\[([^\]]+)\]\]/g, '$1').trim().replace(/\.md$/, '');
  if (/^\d{8}$/.test(raw)) {
    return 'noteplan://x-callback-url/openNote?filename=' + raw;
  }
  return 'noteplan://x-callback-url/openNote?noteTitle=' + encodeURIComponent(raw);
}
"""
