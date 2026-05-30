"""
work_board.py — Personal Work Board generation for noteplan-sweep.

Extends the Idea Dashboard with living artifact panes:
  Accomplishments (Brag Sheet), Observations, Gaps & Growth, Impact Timeline, AI Usage summary.

Commands:
  work-board-generate    Extract living artifacts + plans → write dashboard/work-board.html
  work-board-open        Open dashboard/work-board.html in browser
"""

import json
import re
import sys
from datetime import datetime, date
from pathlib import Path

import noteplan_sweep.utils as utils
from noteplan_sweep.dashboard import (
    scan_plans, scan_tasks_and_ideas, build_html as build_ideas_html,
    parse_frontmatter, _derive_project, _derive_workstream,
    STATUS_LABELS, stem_to_date, mtime_date,
)


# ---------------------------------------------------------------------------
# Living artifact locators
# ---------------------------------------------------------------------------

def _notes_root() -> Path:
    return utils.notes_root()

def find_brag_sheet(notes_root: Path) -> Path | None:
    candidates = list(notes_root.rglob("*Brag Sheet*.md"))
    candidates = [p for p in candidates if "@Trash" not in str(p) and "@Archive" not in str(p)]
    return candidates[0] if candidates else None

def find_observations(notes_root: Path) -> Path | None:
    candidates = list(notes_root.rglob("Observations.md"))
    candidates = [p for p in candidates if "@Trash" not in str(p)]
    return candidates[0] if candidates else None

def find_gaps(notes_root: Path) -> Path | None:
    candidates = list(notes_root.rglob("Gaps.md"))
    candidates = [p for p in candidates if "@Trash" not in str(p)]
    return candidates[0] if candidates else None

def find_superpowers(notes_root: Path) -> Path | None:
    candidates = list(notes_root.rglob("Superpowers.md"))
    candidates = [p for p in candidates if "@Trash" not in str(p)]
    return candidates[0] if candidates else None

def find_impact_timeline(notes_root: Path) -> Path | None:
    candidates = list(notes_root.rglob("*Impact Timeline*.md"))
    candidates = [p for p in candidates if "@Trash" not in str(p)]
    return candidates[0] if candidates else None


# ---------------------------------------------------------------------------
# Brag Sheet extractor
# Format: ## YYYY QN  →  ### YYYY-MM-DD Sweep  →  bullet list
# ---------------------------------------------------------------------------

_QUARTER_RE = re.compile(r'^##\s+(\d{4})\s+(Q[1-4])\s*$')
_SWEEP_DATE_RE = re.compile(r'^###\s+(\d{4}-\d{2}-\d{2}(?:[^\n]*)?)\s*$')
_BULLET_RE = re.compile(r'^[-*]\s+(.+)$')


def extract_brag_sheet(path: Path) -> list[dict]:
    """Return list of {quarter, sweep_date, text, tags} achievement entries."""
    entries: list[dict] = []
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return entries

    current_quarter = ""
    current_sweep = ""

    for line in content.splitlines():
        qm = _QUARTER_RE.match(line)
        if qm:
            current_quarter = f"{qm.group(1)} {qm.group(2)}"
            continue

        sm = _SWEEP_DATE_RE.match(line)
        if sm:
            current_sweep = sm.group(1).strip()
            continue

        bm = _BULLET_RE.match(line.strip())
        if bm and current_quarter:
            text = bm.group(1).strip()
            # Extract inline **bold** as title
            title_m = re.match(r'\*\*([^*]+)\*\*:?\s*(.*)', text)
            title = title_m.group(1) if title_m else ""
            body = title_m.group(2) if title_m else text
            entries.append({
                "quarter": current_quarter,
                "sweep_date": current_sweep,
                "title": title,
                "text": body or text,
                "full_text": text,
            })

    return entries


# ---------------------------------------------------------------------------
# Observations extractor
# Format: ## YYYY-MM-DD Sweep  →  bullet list with optional **bold** labels
# ---------------------------------------------------------------------------

_SECTION_DATE_RE = re.compile(r'^##\s+(\d{4}-\d{2}-\d{2}(?:[^\n]*)?)\s*$')


def _extract_bulleted_sections(path: Path, tag_prefix: str = "") -> list[dict]:
    """Generic extractor for files with ## date headers + bullet entries."""
    entries: list[dict] = []
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return entries

    current_section = ""
    for line in content.splitlines():
        sm = _SECTION_DATE_RE.match(line)
        if sm:
            current_section = sm.group(1).strip()
            continue

        # Also handle non-date section headers
        if line.startswith("## "):
            current_section = line[3:].strip()
            continue

        bm = _BULLET_RE.match(line.strip())
        if bm:
            text = bm.group(1).strip()
            title_m = re.match(r'\*\*([^*]+)\*\*:?\s*(.*)', text)
            title = title_m.group(1) if title_m else ""
            body = title_m.group(2) if title_m else text

            # Extract inline #tags
            tags = re.findall(r'#(\w+)', text)

            entries.append({
                "section": current_section,
                "title": title,
                "text": body or text,
                "full_text": text,
                "tags": tags,
                "tag_prefix": tag_prefix,
            })

    return entries


def extract_observations(path: Path) -> list[dict]:
    return _extract_bulleted_sections(path, "observation")

def extract_gaps(path: Path) -> list[dict]:
    return _extract_bulleted_sections(path, "gap")

def extract_superpowers(path: Path) -> list[dict]:
    return _extract_bulleted_sections(path, "superpower")


# ---------------------------------------------------------------------------
# Impact Timeline extractor
# Format: ## QN YYYY  →  | Initiative | Delivered | Signals | Evidence |
# ---------------------------------------------------------------------------

_TABLE_ROW_RE = re.compile(r'^\|(.+)\|$')
_SIGNAL_TAG_RE = re.compile(r'\[([A-Z+]+)\]')


def extract_impact_timeline(path: Path) -> list[dict]:
    entries: list[dict] = []
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return entries

    current_quarter = ""
    headers: list[str] = []

    for line in content.splitlines():
        # Quarter headers
        if line.startswith("## "):
            current_quarter = line[3:].strip()
            headers = []
            continue

        row_m = _TABLE_ROW_RE.match(line.strip())
        if not row_m:
            continue

        cells = [c.strip() for c in line.strip().strip("|").split("|")]

        # Header row
        if all(c == "" or re.match(r'^[-:]+$', c) for c in cells):
            continue
        if not headers or all(re.match(r'^[-:]+$', c or '') for c in cells):
            # Treat as header if first table row in section
            if not headers:
                headers = cells
            continue

        if not headers or len(cells) < 2:
            continue

        # Skip separator rows
        if all(re.match(r'^[-: ]*$', c) for c in cells):
            continue

        row: dict = {"quarter": current_quarter}
        for i, h in enumerate(headers):
            row[h.lower().replace(" ", "_")] = cells[i] if i < len(cells) else ""

        # Extract signal tags from the signals column
        signals_text = row.get("signals", "")
        row["signal_tags"] = _SIGNAL_TAG_RE.findall(signals_text)

        # Skip empty rows (table placeholders)
        if not any(v for k, v in row.items() if k not in ("quarter", "signal_tags")):
            continue

        entries.append(row)

    return entries


# ---------------------------------------------------------------------------
# HTML builder (Work Board — 8 panes)
# ---------------------------------------------------------------------------

def build_work_board_html(
    plans: list, tasks: list, ideas: list,
    brag: list, observations: list, gaps: list, superpowers: list,
    impact: list, ai_summary: dict | None,
    generated_at: str,
) -> str:
    data_json = json.dumps({
        "plans": plans,
        "tasks": tasks,
        "ideas": ideas,
        "brag": brag,
        "observations": observations,
        "gaps": gaps,
        "superpowers": superpowers,
        "impact": impact,
        "ai_summary": ai_summary or {},
        "generated_at": generated_at,
    }, indent=2, ensure_ascii=False)

    projects = sorted({p["project"] for p in plans if p.get("project")})
    plantypes = sorted({p["plantype"] for p in plans if p.get("plantype")})
    quarters = sorted({e["quarter"] for e in brag if e.get("quarter")}, reverse=True)
    obs_tags = sorted({t for e in observations for t in e.get("tags", [])})

    project_chips = "".join(
        f'<span class="chip" data-facet="project" data-val="{p}" onclick="toggleChip(this)">{p}</span>'
        for p in projects
    )
    plantype_chips = "".join(
        f'<span class="chip" data-facet="plantype" data-val="{t}" onclick="toggleChip(this)" style="font-size:15px">{t}</span>'
        for t in plantypes
    )
    period_chips = (
        '<span class="chip active" data-facet="period" data-val="all"     onclick="toggleChip(this)">All time</span>'
        '<span class="chip"        data-facet="period" data-val="quarter"  onclick="toggleChip(this)">This quarter</span>'
        '<span class="chip"        data-facet="period" data-val="month"    onclick="toggleChip(this)">This month</span>'
        '<span class="chip"        data-facet="period" data-val="week"     onclick="toggleChip(this)">This week</span>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Personal Work Board</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 13px; background: #0d1117; color: #e6edf3; }}

  #topbar {{ background: #161b22; border-bottom: 1px solid #30363d; padding: 10px 20px; position: sticky; top: 0; z-index: 100; }}
  #topbar-row1 {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
  #topbar-row1 h1 {{ font-size: 15px; font-weight: 700; color: #58a6ff; white-space: nowrap; }}
  #search-global {{ background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 5px 10px; color: #e6edf3; font-size: 13px; width: 200px; }}
  #search-global::placeholder {{ color: #484f58; }}
  #gen-time {{ font-size: 11px; color: #484f58; margin-left: auto; white-space: nowrap; }}

  .facet-row {{ display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 4px; }}
  .facet-label {{ font-size: 10px; color: #484f58; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; margin-right: 2px; }}
  .chip {{ background: #21262d; border-radius: 20px; padding: 2px 10px; font-size: 12px; color: #8b949e; cursor: pointer; border: 1px solid #30363d; user-select: none; }}
  .chip:hover {{ background: #2d333b; }}
  .chip.active {{ background: #1f4a2a; color: #3fb950; border-color: #3fb950; }}
  .chip[data-facet="status"][data-val="paused"].active  {{ background: #2d2a1f; color: #d29922; border-color: #d29922; }}
  .chip[data-facet="status"][data-val="done"].active    {{ background: #1c2128; color: #8b949e; border-color: #484f58; }}
  .chip[data-facet="status"][data-val="backlog"].active {{ background: #1f2d4a; color: #79c0ff; border-color: #79c0ff; }}
  .chip[data-facet="project"].active  {{ background: #2d1f4a; color: #d2a8ff; border-color: #d2a8ff; }}
  .chip[data-facet="plantype"].active {{ background: #1f3a4a; color: #79c0ff; border-color: #79c0ff; }}
  .chip[data-facet="period"].active   {{ background: #2a1f3a; color: #c9a0ff; border-color: #c9a0ff; }}
  .facet-sep {{ width: 1px; height: 14px; background: #30363d; margin: 0 4px; flex-shrink: 0; }}

  #tabs {{ background: #161b22; border-bottom: 1px solid #30363d; display: flex; overflow-x: auto; }}
  .tab {{ padding: 9px 16px; cursor: pointer; font-size: 12px; color: #8b949e; border-bottom: 2px solid transparent; white-space: nowrap; flex-shrink: 0; }}
  .tab.active {{ color: #e6edf3; border-bottom-color: #58a6ff; }}

  #content {{ padding: 16px 20px; }}
  .pane {{ display: none; }}
  .pane.active {{ display: block; }}

  .filter-bar {{ display: flex; gap: 8px; margin-bottom: 12px; align-items: center; flex-wrap: wrap; }}
  .filter-bar input {{ background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 5px 10px; color: #e6edf3; font-size: 13px; width: 200px; }}
  .filter-bar input::placeholder {{ color: #484f58; }}
  .count-badge {{ font-size: 12px; color: #484f58; margin-left: auto; }}

  /* Plans table */
  .plans-table {{ width: 100%; border-collapse: collapse; }}
  .plans-table th {{ text-align: left; padding: 7px 10px; font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #30363d; white-space: nowrap; }}
  .plans-table td {{ padding: 7px 10px; border-bottom: 1px solid #21262d; vertical-align: middle; }}
  .plans-table tr:hover td {{ background: #161b22; }}
  .status-dot {{ display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; }}
  .s-active {{ background: #3fb950; }} .s-paused {{ background: #d29922; }}
  .s-done {{ background: #484f58; }}   .s-backlog {{ background: #79c0ff; }}
  .np-link {{ color: #58a6ff; text-decoration: none; }}
  .np-link:hover {{ text-decoration: underline; }}
  .task-bar {{ display: flex; gap: 4px; font-size: 11px; }}
  .task-bar .td {{ color: #3fb950; }} .task-bar .to {{ color: #d29922; }}

  /* Card lists (observations, gaps, superpowers, brag) */
  .card-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 10px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 11px 14px; }}
  .card.gap  {{ border-left: 3px solid #f85149; }}
  .card.superpower {{ border-left: 3px solid #3fb950; }}
  .card.brag {{ border-left: 3px solid #d97757; }}
  .card.observation {{ border-left: 3px solid #58a6ff; }}
  .card-title {{ font-weight: 600; color: #e6edf3; margin-bottom: 4px; font-size: 13px; }}
  .card-body  {{ color: #8b949e; font-size: 12px; line-height: 1.5; }}
  .card-meta  {{ font-size: 11px; color: #484f58; margin-top: 6px; }}
  .tag-chip {{ display: inline-block; font-size: 10px; background: #21262d; border-radius: 3px; padding: 1px 5px; color: #8b949e; margin-right: 3px; }}

  /* Brag groups */
  .brag-quarter {{ margin-bottom: 20px; }}
  .brag-quarter-header {{ font-size: 12px; font-weight: 700; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #21262d; }}
  .brag-sweep {{ margin-bottom: 12px; }}
  .brag-sweep-date {{ font-size: 11px; color: #484f58; margin-bottom: 6px; }}

  /* Two-column gaps/superpowers */
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .col-header {{ font-size: 13px; font-weight: 600; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 1px solid #30363d; }}
  .col-header.gaps {{ color: #f85149; }}
  .col-header.superpowers {{ color: #3fb950; }}

  /* Impact table */
  .impact-table {{ width: 100%; border-collapse: collapse; }}
  .impact-table th {{ text-align: left; padding: 7px 10px; font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #30363d; }}
  .impact-table td {{ padding: 7px 10px; border-bottom: 1px solid #21262d; vertical-align: top; font-size: 12px; }}
  .impact-table tr:hover td {{ background: #161b22; }}
  .signal-tag {{ display: inline-block; font-size: 10px; background: #1f3a4a; color: #79c0ff; border-radius: 3px; padding: 1px 5px; margin-right: 3px; white-space: nowrap; }}

  /* AI usage tile */
  .ai-tile-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; }}
  .ai-tile {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; text-align: center; }}
  .ai-tile .tile-num {{ font-size: 28px; font-weight: 700; color: #d97757; }}
  .ai-tile .tile-label {{ font-size: 11px; color: #8b949e; margin-top: 4px; }}
  .ai-open-btn {{ display: inline-block; margin-top: 12px; background: #d97757; color: #0d1117; padding: 8px 18px; border-radius: 6px; font-size: 13px; font-weight: 600; text-decoration: none; cursor: pointer; border: none; }}

  /* Gantt placeholder */
  .gantt-ph {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 40px; text-align: center; color: #484f58; }}
  .gantt-ph p {{ margin-top: 8px; font-size: 12px; }}
</style>
</head>
<body>

<div id="topbar">
  <div id="topbar-row1">
    <h1>🗂 Personal Work Board</h1>
    <input type="text" id="search-global" placeholder="Search everything…" oninput="rerender()">
    <div id="gen-time">Generated {generated_at}</div>
  </div>
  <div class="facet-row">
    <span class="facet-label">Period</span>
    {period_chips}
    <div class="facet-sep"></div>
    <span class="facet-label">Status</span>
    <span class="chip active" data-facet="status" data-val="all"    onclick="toggleChip(this)">All</span>
    <span class="chip"        data-facet="status" data-val="active"  onclick="toggleChip(this)">🟢</span>
    <span class="chip"        data-facet="status" data-val="paused"  onclick="toggleChip(this)">🟡</span>
    <span class="chip"        data-facet="status" data-val="backlog" onclick="toggleChip(this)">🔵</span>
    <span class="chip"        data-facet="status" data-val="done"    onclick="toggleChip(this)">✅</span>
    <div class="facet-sep"></div>
    <span class="facet-label">Project</span>
    {project_chips}
    <div class="facet-sep"></div>
    <span class="facet-label">Type</span>
    {plantype_chips}
  </div>
</div>

<div id="tabs">
  <div class="tab active"  onclick="showTab('plans')">Plans <span id="n-plans"></span></div>
  <div class="tab"         onclick="showTab('gantt')">Gantt</div>
  <div class="tab"         onclick="showTab('brag')">Accomplishments <span id="n-brag"></span></div>
  <div class="tab"         onclick="showTab('observations')">Observations <span id="n-obs"></span></div>
  <div class="tab"         onclick="showTab('gaps')">Gaps &amp; Growth <span id="n-gaps"></span></div>
  <div class="tab"         onclick="showTab('impact')">Impact <span id="n-impact"></span></div>
  <div class="tab"         onclick="showTab('tasks')">Tasks <span id="n-tasks"></span></div>
  <div class="tab"         onclick="showTab('ai')">AI Usage</div>
</div>

<div id="content">

  <div class="pane active" id="pane-plans">
    <div class="filter-bar">
      <input type="text" id="plan-search" placeholder="Filter plans…" oninput="renderPlans()">
      <span class="count-badge" id="plan-count"></span>
    </div>
    <table class="plans-table">
      <thead><tr>
        <th></th><th>Plan</th><th>Project</th><th>Workstream</th>
        <th>Type</th><th>Started</th><th>Tasks</th><th>Description</th>
      </tr></thead>
      <tbody id="plans-body"></tbody>
    </table>
  </div>

  <div class="pane" id="pane-gantt">
    <div class="gantt-ph">
      <div style="font-size:32px">📅</div>
      <strong>Gantt View — coming in ID-C</strong>
      <p>Frappe Gantt · Start = filename YYMMDD · End = <code>completed:</code> frontmatter</p>
    </div>
  </div>

  <div class="pane" id="pane-brag">
    <div class="filter-bar">
      <input type="text" id="brag-search" placeholder="Filter accomplishments…" oninput="renderBrag()">
      <span class="count-badge" id="brag-count"></span>
    </div>
    <div id="brag-body"></div>
  </div>

  <div class="pane" id="pane-observations">
    <div class="filter-bar">
      <input type="text" id="obs-search" placeholder="Filter observations…" oninput="renderObs()">
      <span class="count-badge" id="obs-count"></span>
    </div>
    <div class="card-grid" id="obs-body"></div>
  </div>

  <div class="pane" id="pane-gaps">
    <div class="filter-bar">
      <input type="text" id="gaps-search" placeholder="Filter…" oninput="renderGaps()">
    </div>
    <div class="two-col">
      <div>
        <div class="col-header gaps">⚠️ Gaps <span id="n-gaps-col"></span></div>
        <div class="card-grid" id="gaps-body"></div>
      </div>
      <div>
        <div class="col-header superpowers">⚡ Superpowers <span id="n-super-col"></span></div>
        <div class="card-grid" id="super-body"></div>
      </div>
    </div>
  </div>

  <div class="pane" id="pane-impact">
    <div class="filter-bar">
      <input type="text" id="impact-search" placeholder="Filter impact…" oninput="renderImpact()">
      <span class="count-badge" id="impact-count"></span>
    </div>
    <table class="impact-table">
      <thead><tr><th>Quarter</th><th>Initiative</th><th>Delivered</th><th>Signals</th><th>Evidence</th></tr></thead>
      <tbody id="impact-body"></tbody>
    </table>
  </div>

  <div class="pane" id="pane-tasks">
    <div class="filter-bar">
      <input type="text" id="task-search" placeholder="Filter tasks…" oninput="renderTasks()">
      <span class="count-badge" id="task-count"></span>
    </div>
    <div id="task-list" style="display:flex;flex-direction:column;gap:4px"></div>
  </div>

  <div class="pane" id="pane-ai">
    <div id="ai-content"></div>
  </div>

</div>

<script>
const DATA = {data_json};

// ── Filter state ──────────────────────────────────────────────────────────
const sel = {{ status: new Set(), project: new Set(), plantype: new Set(), period: new Set() }};

// Quarter ranges
const NOW = new Date();
function periodStart(p) {{
  if (p === 'week') {{
    const d = new Date(NOW); d.setDate(d.getDate() - 7); return d;
  }} else if (p === 'month') {{
    return new Date(NOW.getFullYear(), NOW.getMonth(), 1);
  }} else if (p === 'quarter') {{
    const q = Math.floor(NOW.getMonth() / 3);
    return new Date(NOW.getFullYear(), q * 3, 1);
  }}
  return null;
}}

function inPeriod(dateStr) {{
  const ps = sel.period.size ? periodStart([...sel.period][0]) : null;
  if (!ps || !dateStr) return true;
  return new Date(dateStr) >= ps;
}}

function esc(s) {{ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }}

// ── Chip toggle ───────────────────────────────────────────────────────────
function toggleChip(el) {{
  const facet = el.dataset.facet;
  const val   = el.dataset.val;
  if (facet === 'status' || facet === 'period') {{
    document.querySelectorAll(`.chip[data-facet="${{facet}}"]`).forEach(c => c.classList.remove('active'));
    if (val === 'all') {{ sel[facet].clear(); }}
    else {{ sel[facet].clear(); sel[facet].add(val); }}
    el.classList.add('active');
  }} else {{
    if (sel[facet].has(val)) {{ sel[facet].delete(val); el.classList.remove('active'); }}
    else {{ sel[facet].add(val); el.classList.add('active'); }}
  }}
  rerender();
}}

// ── Tab navigation ────────────────────────────────────────────────────────
const TAB_NAMES = ['plans','gantt','brag','observations','gaps','impact','tasks','ai'];
function showTab(tab) {{
  document.querySelectorAll('.tab').forEach((el, i) => el.classList.toggle('active', TAB_NAMES[i] === tab));
  document.querySelectorAll('.pane').forEach(el => el.classList.remove('active'));
  document.getElementById('pane-' + tab).classList.add('active');
}}

// ── Filter helpers ────────────────────────────────────────────────────────
const sClass = {{active:'s-active',paused:'s-paused',done:'s-done',backlog:'s-backlog'}};

function matchesPlan(p) {{
  const q = (document.getElementById('search-global').value||'').toLowerCase();
  if (sel.status.size  && !sel.status.has(p.status))   return false;
  if (sel.project.size && !sel.project.has(p.project))  return false;
  if (sel.plantype.size&& !sel.plantype.has(p.plantype)) return false;
  if (!inPeriod(p.start_date)) return false;
  if (q && !p.title.toLowerCase().includes(q) &&
           !p.description.toLowerCase().includes(q) &&
           !(p.project||'').toLowerCase().includes(q)) return false;
  return true;
}}

function matchesText(text, extra) {{
  const q = (document.getElementById('search-global').value||'').toLowerCase();
  if (!q) return true;
  return (text||'').toLowerCase().includes(q) || (extra||'').toLowerCase().includes(q);
}}

// ── Renderers ─────────────────────────────────────────────────────────────
function renderPlans() {{
  const q2 = (document.getElementById('plan-search').value||'').toLowerCase();
  const plans = DATA.plans.filter(p => matchesPlan(p) && (!q2 || p.title.toLowerCase().includes(q2) || p.description.toLowerCase().includes(q2)));
  document.getElementById('plan-count').textContent = plans.length + ' plans';
  document.getElementById('n-plans').textContent = '(' + plans.length + ')';
  document.getElementById('plans-body').innerHTML = plans.map(p => `
    <tr>
      <td><span class="status-dot ${{sClass[p.status]||'s-done'}}"></span></td>
      <td><a class="np-link" href="${{esc(p.xcallback)}}">${{esc(p.title)}}</a></td>
      <td style="color:#8b949e;white-space:nowrap">${{esc(p.project||'')}}</td>
      <td style="color:#8b949e">${{esc(p.workstream||'')}}</td>
      <td style="font-size:15px">${{esc(p.plantype||'')}}</td>
      <td style="color:#484f58;white-space:nowrap">${{esc(p.start_date||'')}}</td>
      <td><div class="task-bar"><span class="td">✓${{p.done_tasks}}</span>&nbsp;<span class="to">◦${{p.open_tasks}}</span></div></td>
      <td style="color:#8b949e;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${{esc(p.description||'')}}</td>
    </tr>`).join('');
}}

function renderBrag() {{
  const q2 = (document.getElementById('brag-search').value||'').toLowerCase();
  const entries = DATA.brag.filter(e =>
    inPeriod(e.sweep_date) &&
    matchesText(e.full_text, e.quarter) &&
    (!q2 || e.full_text.toLowerCase().includes(q2))
  );
  document.getElementById('brag-count').textContent = entries.length + ' entries';
  document.getElementById('n-brag').textContent = '(' + entries.length + ')';

  // Group by quarter then sweep_date
  const byQ = {{}};
  entries.forEach(e => {{
    const q = e.quarter || 'Other';
    const s = e.sweep_date || 'Unknown';
    if (!byQ[q]) byQ[q] = {{}};
    if (!byQ[q][s]) byQ[q][s] = [];
    byQ[q][s].push(e);
  }});

  document.getElementById('brag-body').innerHTML = Object.keys(byQ).sort().reverse().map(q => `
    <div class="brag-quarter">
      <div class="brag-quarter-header">${{esc(q)}}</div>
      ${{Object.keys(byQ[q]).sort().reverse().map(s => `
        <div class="brag-sweep">
          <div class="brag-sweep-date">📅 ${{esc(s)}}</div>
          <div class="card-grid">
            ${{byQ[q][s].map(e => `
              <div class="card brag">
                ${{e.title ? `<div class="card-title">${{esc(e.title)}}</div>` : ''}}
                <div class="card-body">${{esc(e.text)}}</div>
              </div>`).join('')}}
          </div>
        </div>`).join('')}}
    </div>`).join('');
}}

function renderObs() {{
  const q2 = (document.getElementById('obs-search').value||'').toLowerCase();
  const entries = DATA.observations.filter(e =>
    inPeriod(e.section) &&
    matchesText(e.full_text) &&
    (!q2 || e.full_text.toLowerCase().includes(q2))
  );
  document.getElementById('obs-count').textContent = entries.length + ' entries';
  document.getElementById('n-obs').textContent = '(' + entries.length + ')';
  document.getElementById('obs-body').innerHTML = entries.map(e => `
    <div class="card observation">
      ${{e.title ? `<div class="card-title">${{esc(e.title)}}</div>` : ''}}
      <div class="card-body">${{esc(e.text)}}</div>
      <div class="card-meta">
        ${{esc(e.section)}}
        ${{e.tags.map(t => `<span class="tag-chip">#${{esc(t)}}</span>`).join('')}}
      </div>
    </div>`).join('');
}}

function renderGaps() {{
  const q2 = (document.getElementById('gaps-search').value||'').toLowerCase();
  const gapList = DATA.gaps.filter(e => matchesText(e.full_text) && (!q2 || e.full_text.toLowerCase().includes(q2)));
  const superList = DATA.superpowers.filter(e => matchesText(e.full_text) && (!q2 || e.full_text.toLowerCase().includes(q2)));
  document.getElementById('n-gaps').textContent = '(' + (gapList.length + superList.length) + ')';
  document.getElementById('n-gaps-col').textContent = '(' + gapList.length + ')';
  document.getElementById('n-super-col').textContent = '(' + superList.length + ')';
  document.getElementById('gaps-body').innerHTML = gapList.map(e => `
    <div class="card gap">
      ${{e.title ? `<div class="card-title">${{esc(e.title)}}</div>` : ''}}
      <div class="card-body">${{esc(e.text)}}</div>
      <div class="card-meta">${{esc(e.section)}}</div>
    </div>`).join('');
  document.getElementById('super-body').innerHTML = superList.map(e => `
    <div class="card superpower">
      ${{e.title ? `<div class="card-title">${{esc(e.title)}}</div>` : ''}}
      <div class="card-body">${{esc(e.text)}}</div>
      <div class="card-meta">${{esc(e.section)}}</div>
    </div>`).join('');
}}

function renderImpact() {{
  const q2 = (document.getElementById('impact-search').value||'').toLowerCase();
  const entries = DATA.impact.filter(e =>
    (!q2 || (e.initiative||'').toLowerCase().includes(q2) || (e.delivered||'').toLowerCase().includes(q2))
  );
  document.getElementById('impact-count').textContent = entries.length + ' entries';
  document.getElementById('n-impact').textContent = '(' + entries.length + ')';
  document.getElementById('impact-body').innerHTML = entries.map(e => `
    <tr>
      <td style="color:#484f58;white-space:nowrap">${{esc(e.quarter||'')}}</td>
      <td style="font-weight:600">${{esc(e.initiative||'')}}</td>
      <td style="color:#8b949e">${{esc(e.delivered||'')}}</td>
      <td>${{(e.signal_tags||[]).map(t => `<span class="signal-tag">[${{esc(t)}}]</span>`).join(' ')}}</td>
      <td style="color:#484f58">${{esc(e.evidence||'')}}</td>
    </tr>`).join('');
}}

function renderTasks() {{
  const q2 = (document.getElementById('task-search').value||'').toLowerCase();
  const tasks = DATA.tasks.filter(t => matchesText(t.text, t.source) && (!q2 || t.text.toLowerCase().includes(q2)));
  document.getElementById('task-count').textContent = tasks.length + ' tasks';
  document.getElementById('n-tasks').textContent = '(' + tasks.length + ')';
  document.getElementById('task-list').innerHTML = tasks.slice(0,300).map(t => `
    <div style="background:#161b22;border:1px solid #30363d;border-radius:6px;padding:8px 12px;display:flex;gap:10px">
      <span style="color:#484f58">◦</span>
      <span style="flex:1">${{esc(t.text)}}</span>
      <span style="font-size:11px;color:#484f58;white-space:nowrap">${{esc((t.source||'').split('/').pop())}}</span>
    </div>`).join('');
}}

function renderAI() {{
  const s = DATA.ai_summary;
  if (!s || !s.total_sessions) {{
    document.getElementById('ai-content').innerHTML = `
      <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:40px;text-align:center;color:#484f58">
        <div style="font-size:32px">🤖</div>
        <strong>AI Usage Dashboard not yet generated</strong>
        <p style="margin-top:8px;font-size:12px">Run <code>noteplan-sweep ai-usage-mine</code> then <code>ai-usage-generate</code></p>
      </div>`;
    return;
  }}
  document.getElementById('ai-content').innerHTML = `
    <div class="ai-tile-grid">
      <div class="ai-tile"><div class="tile-num">${{s.total_sessions||0}}</div><div class="tile-label">Total Sessions</div></div>
      <div class="ai-tile"><div class="tile-num">${{s.last_30_days||0}}</div><div class="tile-label">Last 30 Days</div></div>
      <div class="ai-tile"><div class="tile-num">${{s.total_projects||0}}</div><div class="tile-label">Projects</div></div>
      <div class="ai-tile"><div class="tile-num">${{s.total_files_written||0}}</div><div class="tile-label">Files Written</div></div>
    </div>
    <p style="color:#484f58;font-size:12px;margin-bottom:12px">Top project: <strong style="color:#e6edf3">${{esc(s.top_project||'')}}</strong></p>
    <button class="ai-open-btn" onclick="window.location='dashboard/ai-usage.html'">Open Full AI Dashboard →</button>`;
}}

function rerender() {{
  renderPlans(); renderBrag(); renderObs(); renderGaps(); renderImpact(); renderTasks(); renderAI();
}}

window.addEventListener('DOMContentLoaded', rerender);
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_work_board_generate(args):
    root = utils.noteplan_root()
    notes = root / "Notes"
    calendar = root / "Calendar"
    dash_dir = root / "dashboard"
    dash_dir.mkdir(exist_ok=True)

    utils.verbose("Scanning plans...")
    plans = scan_plans(notes)

    utils.verbose("Extracting tasks and ideas...")
    tasks, ideas = scan_tasks_and_ideas(notes, calendar)

    utils.verbose("Extracting living artifacts...")
    brag_path = find_brag_sheet(notes)
    brag = extract_brag_sheet(brag_path) if brag_path else []
    utils.verbose(f"  Brag Sheet: {len(brag)} entries from {brag_path}")

    obs_path = find_observations(notes)
    observations = extract_observations(obs_path) if obs_path else []

    gaps_path = find_gaps(notes)
    gaps = extract_gaps(gaps_path) if gaps_path else []

    super_path = find_superpowers(notes)
    superpowers = extract_superpowers(super_path) if super_path else []

    impact_path = find_impact_timeline(notes)
    impact = extract_impact_timeline(impact_path) if impact_path else []

    # Load AI usage summary if it exists
    ai_summary = None
    ai_json = dash_dir / "ai-usage.json"
    if ai_json.exists():
        try:
            data = json.loads(ai_json.read_text(encoding="utf-8"))
            ai_summary = data.get("summary", {})
        except Exception:
            pass

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would write dashboard/work-board.html ({len(plans)} plans, {len(brag)} brag, {len(observations)} obs, {len(gaps)} gaps, {len(superpowers)} superpowers, {len(impact)} impact)")
        return

    html = build_work_board_html(
        plans, tasks, ideas,
        brag, observations, gaps, superpowers, impact,
        ai_summary, generated_at,
    )
    out = dash_dir / "work-board.html"
    out.write_text(html, encoding="utf-8")
    utils.log(f"work-board-generate: wrote {out}")
    utils.log(f"  {len(plans)} plans · {len(brag)} accomplishments · {len(observations)} observations · {len(gaps)} gaps · {len(superpowers)} superpowers · {len(impact)} impact entries")

    # Persist data sidecar
    sidecar = dash_dir / "work-board-data.json"
    sidecar.write_text(json.dumps({
        "plans": plans, "tasks": tasks, "brag": brag,
        "observations": observations, "gaps": gaps, "superpowers": superpowers,
        "impact": impact, "generated_at": generated_at,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_work_board_open(args):
    path = utils.noteplan_root() / "dashboard" / "work-board.html"
    if not path.exists():
        utils.err("dashboard/work-board.html not found. Run work-board-generate first.")
        sys.exit(utils.EXIT_NOT_FOUND)
    import subprocess as sp
    sp.run(["open", str(path)])
    utils.log(f"work-board-open: opened {path}")
