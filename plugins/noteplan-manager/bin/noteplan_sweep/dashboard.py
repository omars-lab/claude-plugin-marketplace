"""
dashboard.py — Idea Dashboard generation for noteplan-sweep.

Commands:
  dashboard-generate    Scan NotePlan files → extract data → write dashboard/plans.html
  dashboard-open        Open dashboard/plans.html in browser
"""

import json
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import noteplan_sweep.utils as utils


# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------

def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body) from markdown content."""
    fm: dict = {}
    body = content
    if not content.startswith("---"):
        return fm, body
    end = content.find("\n---", 3)
    if end == -1:
        return fm, body
    fm_block = content[3:end].strip()
    body = content[end + 4:].lstrip("\n")
    for line in fm_block.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        fm[key.strip()] = val.strip()
    return fm, body


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

_YYMMDD_RE = re.compile(r'(?:^|[^\d])(\d{6})(?:[^\d]|$)')

def stem_to_date(stem: str) -> str | None:
    """Extract YYMMDD from a plan filename stem and return YYYY-MM-DD."""
    m = _YYMMDD_RE.search(stem)
    if not m:
        return None
    raw = m.group(1)
    yy, mm, dd = raw[:2], raw[2:4], raw[4:]
    try:
        year = 2000 + int(yy)
        dt = datetime(year, int(mm), int(dd))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def mtime_date(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Plan scanner
# ---------------------------------------------------------------------------

PLAN_PATH_RE = re.compile(r'/(?:📆 Plans|Plans)/|🏡📆|Plans/')
STATUS_LABELS = {
    "🟢": "active",
    "🟡": "paused",
    "✅": "done",
    "🔵": "backlog",
    "⬜": "backlog",
}

# Strip leading emoji chars from a folder name to get a plain label
_EMOJI_PREFIX_RE = re.compile(
    r'^[\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF\U0001F300-\U0001F9FF'
    r'\U0001FA00-\U0001FA9F\u200d\ufe0f\U0001F1E0-\U0001F1FF\U00002702-\U000027B0]+'
)

def _strip_emoji(s: str) -> str:
    return _EMOJI_PREFIX_RE.sub('', s).strip()


def _derive_project(rel: str, fm: dict) -> str:
    """Return the project label for a plan file.

    Priority:
    1. `initiative:` frontmatter field (explicit override, e.g. "Naqsh", "Amazon")
    2. Top-level Notes subfolder name with emoji stripped (e.g. "ServiceNow", "Personal", "EarlBear")
    """
    if fm.get("initiative"):
        return fm["initiative"].strip()
    parts = rel.split("/")
    if parts:
        return _strip_emoji(parts[0]) or parts[0]
    return ""


def _derive_workstream(rel: str) -> str:
    """Return the workstream/activity folder name (one level above the plan file)."""
    parts = rel.split("/")
    # Walk parts to find the Plans/ dir, then take the next component
    for i, part in enumerate(parts):
        if "Plans" in part and i + 1 < len(parts) - 1:
            candidate = parts[i + 1]
            # Skip Present/Future/Past folder names
            if candidate in ("Present", "Future", "Past"):
                if i + 2 < len(parts) - 1:
                    candidate = parts[i + 2]
                else:
                    continue
            return _strip_emoji(candidate)
    return ""


def scan_plans(notes_root: Path) -> list[dict]:
    plans = []
    for p in sorted(notes_root.rglob("*.md")):
        if "@Backup" in str(p) or "@Trash" in str(p) or "@Archive" in str(p):
            continue
        if "@Templates" in str(p):
            continue
        # Only plan files (in Plans/ dirs)
        rel = str(p.relative_to(notes_root))
        if not (PLAN_PATH_RE.search(rel) or "Plans/" in rel):
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            continue
        fm, body = parse_frontmatter(content)
        stem = p.stem
        start_date = stem_to_date(stem)
        completed = fm.get("completed", "")
        status_raw = fm.get("status", "")
        status = STATUS_LABELS.get(status_raw, "unknown")

        # Count tasks
        open_tasks = len(re.findall(r'^\s*- \[ \]', body, re.MULTILINE))
        done_tasks = len(re.findall(r'^\s*- \[x\]', body, re.MULTILINE | re.IGNORECASE))

        # Build xcallback URL (percent-encode the title)
        title = fm.get("title", stem)
        from urllib.parse import quote
        xcb = "noteplan://x-callback-url/openNote?noteTitle=" + quote(title, safe="")

        project = _derive_project(rel, fm)
        workstream = _derive_workstream(rel)

        plans.append({
            "stem": stem,
            "title": title,
            "status": status,
            "status_emoji": status_raw,
            "plantype": fm.get("plantype", ""),
            "description": fm.get("description", ""),
            "initiative": fm.get("initiative", ""),
            "project": project,
            "workstream": workstream,
            "start_date": start_date or mtime_date(p),
            "end_date": completed or "",
            "mtime": mtime_date(p),
            "open_tasks": open_tasks,
            "done_tasks": done_tasks,
            "xcallback": xcb,
            "path": str(p),
        })
    return plans


# ---------------------------------------------------------------------------
# Task / idea extractor
# ---------------------------------------------------------------------------

_IDEA_SECTION_RE = re.compile(
    r'^#{1,3}\s+(?:Ideas?|Open Questions?|Inbox)\s*$',
    re.IGNORECASE | re.MULTILINE,
)
_IDEA_TAG_RE = re.compile(r'#idea\b', re.IGNORECASE)


def _source_xcallback(rel_path: str) -> tuple[str, str]:
    """Return (xcallback_url, source_type) for a relative file path."""
    from urllib.parse import quote
    if rel_path.startswith("Calendar/"):
        stem = rel_path.split("/")[-1].replace(".md", "")
        if len(stem) == 8 and stem.isdigit():
            note_date = f"{stem[:4]}-{stem[4:6]}-{stem[6:]}"
            return f"noteplan://x-callback-url/openNote?noteDate={note_date}", "daily"
        return "noteplan://x-callback-url/openNote?noteTitle=" + quote(stem, safe=""), "daily"
    stem = rel_path.split("/")[-1].replace(".md", "")
    return "noteplan://x-callback-url/openNote?noteTitle=" + quote(stem, safe=""), "plan"


def extract_tasks_and_ideas(path: Path, rel_path: str, body: str) -> tuple[list[dict], list[dict]]:
    tasks: list[dict] = []
    ideas: list[dict] = []
    lines = body.splitlines()
    in_idea_section = False
    current_section = ""
    source_xcb, source_type = _source_xcallback(rel_path)

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Track section headers
        if stripped.startswith("#"):
            current_section = stripped.lstrip("#").strip()
            in_idea_section = bool(_IDEA_SECTION_RE.match(stripped))
            continue

        # Open tasks
        if re.match(r'^-\s+\[ \]', stripped):
            task_text = re.sub(r'^-\s+\[ \]\s*', '', stripped)
            tasks.append({
                "text": task_text,
                "source": rel_path,
                "source_type": source_type,
                "section": current_section,
                "line": i + 1,
                "xcallback": source_xcb,
            })

        # Ideas: either in idea section or tagged #idea
        if in_idea_section and stripped and not stripped.startswith("#"):
            text = re.sub(r'^[-*]\s*', '', stripped)
            if text:
                ideas.append({
                    "text": text,
                    "source": rel_path,
                    "source_type": source_type,
                    "section": current_section,
                    "line": i + 1,
                    "tagged": False,
                    "xcallback": source_xcb,
                })
        elif _IDEA_TAG_RE.search(stripped):
            text = re.sub(r'^[-*]\s*(?:\[[ x]\]\s*)?', '', stripped)
            ideas.append({
                "text": text,
                "source": rel_path,
                "source_type": source_type,
                "section": current_section,
                "line": i + 1,
                "tagged": True,
                "xcallback": source_xcb,
            })

    return tasks, ideas


def scan_tasks_and_ideas(notes_root: Path, calendar_root: Path) -> tuple[list[dict], list[dict]]:
    all_tasks: list[dict] = []
    all_ideas: list[dict] = []

    # Scan plan files
    for p in sorted(notes_root.rglob("*.md")):
        if any(x in str(p) for x in ("@Backup", "@Trash", "@Archive", "@Templates")):
            continue
        rel = str(p.relative_to(notes_root))
        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            continue
        _, body = parse_frontmatter(content)
        tasks, ideas = extract_tasks_and_ideas(p, "Notes/" + rel, body)
        all_tasks.extend(tasks)
        all_ideas.extend(ideas)

    # Scan calendar / daily notes
    if calendar_root.exists():
        for p in sorted(calendar_root.glob("*.md"), reverse=True)[:90]:  # last 90 days
            rel = "Calendar/" + p.name
            try:
                content = p.read_text(encoding="utf-8")
            except Exception:
                continue
            tasks, ideas = extract_tasks_and_ideas(p, rel, content)
            all_tasks.extend(tasks)
            all_ideas.extend(ideas)

    return all_tasks, all_ideas


# ---------------------------------------------------------------------------
# HTML builder (Phase A shell — Kanban/Gantt/Inbox UI added in Phases B/C/D)
# ---------------------------------------------------------------------------

def build_html(plans: list, tasks: list, ideas: list, generated_at: str) -> str:
    data_json = json.dumps({
        "plans": plans,
        "tasks": tasks,
        "ideas": ideas,
        "generated_at": generated_at,
    }, indent=2, ensure_ascii=False)

    # Derive unique projects and plantype emojis for filter chips
    projects = sorted({p["project"] for p in plans if p.get("project")})
    plantypes = sorted({p["plantype"] for p in plans if p.get("plantype")})

    project_chips = "".join(
        f'<span class="chip" data-facet="project" data-val="{p}" onclick="toggleChip(this)">{p}</span>'
        for p in projects
    )
    plantype_chips = "".join(
        f'<span class="chip" data-facet="plantype" data-val="{t}" onclick="toggleChip(this)" style="font-size:16px">{t}</span>'
        for t in plantypes
    )

    # Gantt tasks: plans with known date ranges sorted by start
    gantt_plans = [
        p for p in plans
        if p.get("start_date") and p.get("status") != "done"
    ]
    gantt_plans_done = [p for p in plans if p.get("status") == "done" and p.get("start_date")]
    gantt_json = json.dumps([
        {
            "id": p["stem"],
            "name": p["title"],
            "start": p["start_date"],
            "end": p.get("end_date") or "",
            "progress": 100 if p["status"] == "done" else (50 if p["status"] == "active" else 10),
            "custom_class": f"gantt-{p['status']}",
        }
        for p in sorted(gantt_plans + gantt_plans_done[:20], key=lambda x: x["start_date"])
    ], ensure_ascii=False) if (gantt_plans or gantt_plans_done) else "[]"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Idea Dashboard</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.css">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 13px; background: #0d1117; color: #e6edf3; }}

  /* ── Header / facet bar ── */
  #topbar {{ background: #161b22; border-bottom: 1px solid #30363d; padding: 10px 20px; position: sticky; top: 0; z-index: 100; }}
  #topbar-row1 {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
  #topbar-row1 h1 {{ font-size: 15px; font-weight: 700; color: #58a6ff; white-space: nowrap; }}
  #search-global {{ background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 5px 10px; color: #e6edf3; font-size: 13px; width: 200px; }}
  #search-global::placeholder {{ color: #484f58; }}
  #gen-time {{ font-size: 11px; color: #484f58; margin-left: auto; white-space: nowrap; }}

  .facet-row {{ display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
  .facet-label {{ font-size: 11px; color: #484f58; text-transform: uppercase; letter-spacing: 0.5px; margin-right: 2px; white-space: nowrap; }}
  .chip {{ background: #21262d; border-radius: 20px; padding: 2px 10px; font-size: 12px; color: #8b949e; cursor: pointer; border: 1px solid #30363d; user-select: none; transition: background 0.1s; }}
  .chip:hover {{ background: #2d333b; }}
  .chip.active {{ background: #1f4a2a; color: #3fb950; border-color: #3fb950; }}
  .chip[data-facet="status"][data-val="paused"].active {{ background: #2d2a1f; color: #d29922; border-color: #d29922; }}
  .chip[data-facet="status"][data-val="done"].active {{ background: #1c2128; color: #8b949e; border-color: #484f58; }}
  .chip[data-facet="status"][data-val="backlog"].active {{ background: #1f2d4a; color: #79c0ff; border-color: #79c0ff; }}
  .chip[data-facet="project"].active {{ background: #2d1f4a; color: #d2a8ff; border-color: #d2a8ff; }}
  .chip[data-facet="plantype"].active {{ background: #1f3a4a; color: #79c0ff; border-color: #79c0ff; }}
  .facet-sep {{ width: 1px; height: 16px; background: #30363d; margin: 0 4px; flex-shrink: 0; }}

  /* ── Tabs ── */
  #tabs {{ background: #161b22; border-bottom: 1px solid #30363d; display: flex; }}
  .tab {{ padding: 9px 18px; cursor: pointer; font-size: 13px; color: #8b949e; border-bottom: 2px solid transparent; white-space: nowrap; }}
  .tab.active {{ color: #e6edf3; border-bottom-color: #58a6ff; }}

  #content {{ padding: 16px 20px; }}
  .pane {{ display: none; }}
  .pane.active {{ display: block; }}

  /* ── Filter bar (per-pane search) ── */
  .filter-bar {{ display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }}
  .filter-bar input {{ background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 5px 10px; color: #e6edf3; font-size: 13px; width: 200px; }}
  .filter-bar input::placeholder {{ color: #484f58; }}
  .count-badge {{ font-size: 12px; color: #484f58; margin-left: auto; }}

  /* ── Plans table ── */
  .plans-table {{ width: 100%; border-collapse: collapse; }}
  .plans-table th {{ text-align: left; padding: 7px 10px; font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #30363d; white-space: nowrap; }}
  .plans-table td {{ padding: 7px 10px; border-bottom: 1px solid #21262d; vertical-align: middle; }}
  .plans-table tr:hover td {{ background: #161b22; }}
  .status-dot {{ display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; flex-shrink: 0; }}
  .s-active {{ background: #3fb950; }}  .s-paused {{ background: #d29922; }}
  .s-done {{ background: #484f58; }}    .s-backlog {{ background: #79c0ff; }}
  .s-unknown {{ background: #484f58; }}
  .np-link {{ color: #58a6ff; text-decoration: none; }}
  .np-link:hover {{ text-decoration: underline; }}
  .task-bar {{ display: flex; gap: 4px; font-size: 11px; }}
  .task-bar .td {{ color: #3fb950; }} .task-bar .to {{ color: #d29922; }}
  .tag {{ display: inline-block; font-size: 10px; background: #21262d; border-radius: 3px; padding: 1px 5px; color: #8b949e; margin-left: 4px; }}

  /* ── Ideas + Tasks ── */
  .card-list {{ display: flex; flex-direction: column; gap: 5px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 9px 13px; }}
  .card .card-text {{ color: #e6edf3; margin-bottom: 3px; }}
  .card .card-meta {{ font-size: 11px; color: #484f58; }}

  /* ── Kanban ── */
  .kanban-board {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; align-items: start; }}
  .kanban-col {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px; min-height: 120px; min-width: 0; overflow: hidden; }}
  .kanban-col-header {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px solid #30363d; display: flex; justify-content: space-between; align-items: center; }}
  .kanban-card {{ background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 9px 11px; margin-bottom: 6px; min-width: 0; overflow: hidden; }}
  .kanban-card:hover {{ border-color: #58a6ff; }}
  .kanban-card .kc-title {{ font-size: 12px; font-weight: 600; color: #e6edf3; margin-bottom: 4px; line-height: 1.4; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .kanban-card .kc-meta {{ font-size: 11px; color: #484f58; display: flex; gap: 6px; flex-wrap: nowrap; align-items: center; margin-top: 4px; overflow: hidden; }}
  .kc-tasks .td {{ color: #3fb950; }} .kc-tasks .to {{ color: #d29922; }}

  /* ── Initiatives ── */
  .initiative-group {{ margin-bottom: 20px; }}
  .initiative-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; cursor: pointer; }}
  .initiative-header h3 {{ font-size: 13px; font-weight: 700; color: #d2a8ff; }}
  .initiative-header .init-count {{ font-size: 11px; color: #484f58; }}
  .initiative-cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; }}
  .init-card {{ background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 9px 11px; text-decoration: none; display: block; }}
  .init-card:hover {{ border-color: #d2a8ff; }}
  .init-card .ic-title {{ font-size: 12px; font-weight: 600; color: #e6edf3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .init-card .ic-meta {{ font-size: 11px; color: #484f58; margin-top: 3px; display: flex; gap: 6px; align-items: center; }}

  /* ── Gantt ── */
  .gantt-wrap {{ overflow-x: auto; border-radius: 8px; background: #0d1117; padding: 12px; }}
  .gantt .bar {{ fill: #1f6feb; }} .gantt .bar-progress {{ fill: #58a6ff; }}
  .gantt .bar-label {{ fill: #e6edf3 !important; font-size: 11px; }}
  .gantt .lower-text, .gantt .upper-text {{ fill: #8b949e !important; }}
  .gantt .grid-header {{ fill: #161b22 !important; }}
  .gantt .grid-row {{ fill: #0d1117 !important; }} .gantt .grid-row:nth-child(even) {{ fill: #161b22 !important; }}
  .gantt .row-line {{ stroke: #21262d !important; }} .gantt .tick {{ stroke: #30363d !important; }}
  svg.gantt {{ background: #0d1117 !important; }}
  #gantt-zoom {{ display: flex; gap: 6px; margin-bottom: 10px; }}
  #gantt-zoom button {{ background: #21262d; border: 1px solid #30363d; border-radius: 4px; padding: 3px 10px; color: #8b949e; cursor: pointer; font-size: 12px; }}
  #gantt-zoom button.active {{ background: #1f3a4a; color: #79c0ff; border-color: #79c0ff; }}
</style>
</head>
<body>

<div id="topbar">
  <div id="topbar-row1">
    <h1>💡 Idea Dashboard</h1>
    <input type="text" id="search-global" placeholder="Search everything…" oninput="rerender()">
    <div id="gen-time">Generated {generated_at}</div>
  </div>
  <div class="facet-row">
    <span class="facet-label">Status</span>
    <span class="chip active" data-facet="status" data-val="all"   onclick="toggleChip(this)">All</span>
    <span class="chip"        data-facet="status" data-val="active" onclick="toggleChip(this)">🟢 Active</span>
    <span class="chip"        data-facet="status" data-val="paused" onclick="toggleChip(this)">🟡 Paused</span>
    <span class="chip"        data-facet="status" data-val="backlog" onclick="toggleChip(this)">🔵 Backlog</span>
    <span class="chip"        data-facet="status" data-val="done"   onclick="toggleChip(this)">✅ Done</span>
    <div class="facet-sep"></div>
    <span class="facet-label">Project</span>
    {project_chips}
    <div class="facet-sep"></div>
    <span class="facet-label">Type</span>
    {plantype_chips}
  </div>
</div>

<div id="tabs">
  <div class="tab active" onclick="showTab('plans')">Plans <span id="tab-plans-n"></span></div>
  <div class="tab"        onclick="showTab('gantt')">Gantt</div>
  <div class="tab"        onclick="showTab('tasks')">Tasks <span id="tab-tasks-n"></span></div>
  <div class="tab"        onclick="showTab('ideas')">Ideas <span id="tab-ideas-n"></span></div>
  <div class="tab"        onclick="showTab('inbox')">Inbox <span id="tab-inbox-n"></span></div>
  <div class="tab"        onclick="showTab('initiatives')">Initiatives <span id="tab-init-n"></span></div>
</div>

<div id="content">

  <div class="pane active" id="pane-plans">
    <div class="filter-bar">
      <input type="text" id="plan-search" placeholder="Filter plans…" oninput="renderPlans()">
      <span class="count-badge" id="plan-count"></span>
    </div>
    <div class="kanban-board" id="kanban-board"></div>
  </div>

  <div class="pane" id="pane-gantt">
    <div id="gantt-zoom">
      <button class="active" onclick="setGanttView('Month',this)">Month</button>
      <button onclick="setGanttView('Quarter',this)">Quarter</button>
      <button onclick="setGanttView('Year',this)">Year</button>
    </div>
    <div class="gantt-wrap"><svg id="gantt-svg"></svg></div>
  </div>

  <div class="pane" id="pane-tasks">
    <div class="filter-bar">
      <input type="text" id="task-search" placeholder="Filter tasks…" oninput="renderTasks()">
      <span class="count-badge" id="task-count"></span>
    </div>
    <div class="card-list" id="task-list"></div>
  </div>

  <div class="pane" id="pane-ideas">
    <div class="filter-bar">
      <input type="text" id="idea-search" placeholder="Filter ideas…" oninput="renderIdeas()">
      <span class="count-badge" id="idea-count"></span>
    </div>
    <div class="card-list" id="idea-list"></div>
  </div>

  <div class="pane" id="pane-initiatives">
    <div class="filter-bar">
      <input type="text" id="init-search" placeholder="Filter initiatives…" oninput="renderInitiatives()">
      <span class="count-badge" id="init-count"></span>
    </div>
    <div id="initiatives-list"></div>
  </div>

  <div class="pane" id="pane-inbox">
    <div class="filter-bar">
      <input type="text" id="inbox-search" placeholder="Filter inbox…" oninput="renderInbox()">
      <span class="chip" id="inbox-filter-all"   data-ifilter="all"   onclick="setInboxFilter('all')"   style="cursor:pointer">All</span>
      <span class="chip" id="inbox-filter-idea"  data-ifilter="idea"  onclick="setInboxFilter('idea')"  style="cursor:pointer">💡 Ideas</span>
      <span class="chip" id="inbox-filter-task"  data-ifilter="task"  onclick="setInboxFilter('task')"  style="cursor:pointer">◦ Tasks</span>
      <span class="chip" id="inbox-filter-daily" data-ifilter="daily" onclick="setInboxFilter('daily')" style="cursor:pointer">📅 Daily</span>
      <span class="chip" id="inbox-filter-plan"  data-ifilter="plan"  onclick="setInboxFilter('plan')"  style="cursor:pointer">📄 Plans</span>
      <span class="count-badge" id="inbox-count"></span>
    </div>
    <div class="card-list" id="inbox-list"></div>
  </div>

</div>

<script src="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.umd.min.js"></script>
<script>
const DATA = {data_json};
const GANTT_DATA = {gantt_json};

// ── Filter state ──────────────────────────────────────────────────────────
// Multi-select per facet (empty set = "all")
const sel = {{ status: new Set(), project: new Set(), plantype: new Set() }};
let ganttChart = null;

function esc(s) {{
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

// ── Chip toggle ───────────────────────────────────────────────────────────
function toggleChip(el) {{
  const facet = el.dataset.facet;
  const val   = el.dataset.val;

  if (facet === 'status') {{
    // Status is single-select with "All" option
    document.querySelectorAll('.chip[data-facet="status"]').forEach(c => c.classList.remove('active'));
    if (val === 'all') {{
      sel.status.clear();
    }} else {{
      sel.status.clear();
      sel.status.add(val);
    }}
    el.classList.add('active');
    if (val !== 'all') {{
      // deactivate "All" chip
    }} else {{
      // "All" chip already activated above
    }}
  }} else {{
    // Project and plantype are multi-select toggle
    if (sel[facet].has(val)) {{
      sel[facet].delete(val);
      el.classList.remove('active');
    }} else {{
      sel[facet].add(val);
      el.classList.add('active');
    }}
  }}
  rerender();
}}

// ── Match helpers ─────────────────────────────────────────────────────────
function matchesPlan(p) {{
  const q = (document.getElementById('search-global').value || '').toLowerCase();
  if (sel.status.size && !sel.status.has(p.status)) return false;
  if (sel.project.size && !sel.project.has(p.project)) return false;
  if (sel.plantype.size && !sel.plantype.has(p.plantype)) return false;
  if (q && !p.title.toLowerCase().includes(q) &&
           !p.description.toLowerCase().includes(q) &&
           !(p.project || '').toLowerCase().includes(q) &&
           !(p.workstream || '').toLowerCase().includes(q)) return false;
  return true;
}}

function matchesCard(item) {{
  const q = (document.getElementById('search-global').value || '').toLowerCase();
  if (!q) return true;
  return item.text.toLowerCase().includes(q) || (item.source || '').toLowerCase().includes(q);
}}

// ── Tabs ──────────────────────────────────────────────────────────────────
function showTab(tab) {{
  const names = ['plans','gantt','tasks','ideas','inbox','initiatives'];
  document.querySelectorAll('.tab').forEach((el, i) => el.classList.toggle('active', names[i] === tab));
  document.querySelectorAll('.pane').forEach(el => el.classList.remove('active'));
  document.getElementById('pane-' + tab).classList.add('active');
}}

// ── Renderers ─────────────────────────────────────────────────────────────
const sClass = {{active:'s-active',paused:'s-paused',done:'s-done',backlog:'s-backlog'}};

const COLUMNS = [
  {{ key: 'backlog', label: '🔵 Backlog', color: '#79c0ff' }},
  {{ key: 'active',  label: '🟢 Active',  color: '#3fb950' }},
  {{ key: 'paused',  label: '🟡 Paused',  color: '#d29922' }},
  {{ key: 'done',    label: '✅ Done',    color: '#484f58' }},
];

function renderPlans() {{
  const q2 = (document.getElementById('plan-search').value || '').toLowerCase();
  const plans = DATA.plans.filter(p => matchesPlan(p) && (
    !q2 || p.title.toLowerCase().includes(q2) || p.description.toLowerCase().includes(q2)
  ));
  document.getElementById('plan-count').textContent = plans.length + ' plans';
  document.getElementById('tab-plans-n').textContent = '(' + plans.length + ')';

  const board = document.getElementById('kanban-board');
  board.innerHTML = COLUMNS.map(col => {{
    const cards = plans.filter(p => (p.status || 'backlog') === col.key);
    return `<div class="kanban-col" id="kcol-${{col.key}}">
      <div class="kanban-col-header">
        <span style="color:${{col.color}}">${{col.label}}</span>
        <span style="color:#484f58;font-weight:400">${{cards.length}}</span>
      </div>
      ${{cards.map(p => `
        <div class="kanban-card" data-stem="${{esc(p.stem)}}" style="cursor:pointer">
          <div class="kc-title" onclick="SERVER_MODE ? openSidebar(DATA.plans.find(x=>x.stem==='${{p.stem}}')) : window.location.href='${{esc(p.xcallback)}}'">${{esc(p.title)}}</div>
          <div class="kc-meta">
            <span style="color:#8b949e">${{esc(p.project||'')}}</span>
            <span style="font-size:14px">${{esc(p.plantype||'')}}</span>
            <span class="kc-tasks"><span class="td">✓${{p.done_tasks}}</span>&nbsp;<span class="to">◦${{p.open_tasks}}</span></span>
            ${{SERVER_MODE ? `<a href="${{esc(p.xcallback)}}" style="margin-left:auto;color:#484f58;font-size:10px;text-decoration:none" title="Open in NotePlan">↗</a>` : ''}}
          </div>
          ${{p.description ? `<div style="font-size:11px;color:#484f58;margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${{esc(p.description)}}</div>` : ''}}
        </div>`).join('')}}
    </div>`;
  }}).join('');

  // Wire drag-and-drop after DOM is built
  if (SERVER_MODE) {{
    COLUMNS.forEach(col => {{
      const colEl = document.getElementById('kcol-' + col.key);
      if (colEl) makeColDropTarget(colEl, col.key);
    }});
    document.querySelectorAll('.kanban-card[data-stem]').forEach(card => {{
      makeCardDraggable(card, card.dataset.stem);
    }});
  }}
}}

function initGantt() {{
  if (!GANTT_DATA || !GANTT_DATA.length) {{
    document.querySelector('.gantt-wrap').innerHTML = '<div style="padding:40px;text-align:center;color:#484f58">No plans with date ranges found.<br><small>Start = filename YYMMDD · End = <code>completed:</code> frontmatter</small></div>';
    return;
  }}
  const defaultEnd = new Date(Date.now() + 30 * 86400000).toISOString().slice(0,10);
  const tasks = GANTT_DATA.map(t => ({{ ...t, end: t.end || defaultEnd }}));
  try {{
    ganttChart = new Gantt('#gantt-svg', tasks, {{
      view_mode: 'Month',
      date_format: 'YYYY-MM-DD',
      bar_height: 20,
      padding: 18,
      on_click: task => {{ window.location.href = 'noteplan://x-callback-url/openNote?noteTitle=' + encodeURIComponent(task.name); }},
    }});
  }} catch(e) {{
    document.querySelector('.gantt-wrap').innerHTML = `<div style="padding:20px;color:#f85149">Gantt error: ${{e.message}}</div>`;
  }}
}}

function setGanttView(mode, btn) {{
  document.querySelectorAll('#gantt-zoom button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  if (ganttChart) ganttChart.change_view_mode(mode);
}}

function renderTasks() {{
  const q2 = (document.getElementById('task-search').value || '').toLowerCase();
  const tasks = DATA.tasks.filter(t => matchesCard(t) && (!q2 || t.text.toLowerCase().includes(q2)));
  document.getElementById('task-count').textContent = tasks.length + ' tasks';
  document.getElementById('tab-tasks-n').textContent = '(' + tasks.length + ')';
  document.getElementById('task-list').innerHTML = tasks.slice(0,300).map(t => `
    <div class="card" style="display:flex;gap:8px;align-items:flex-start">
      ${{SERVER_MODE && t.path ? `<input type="checkbox" ${{t._checked ? 'checked' : ''}} onchange="toggleTask('${{t.path}}', ${{t.line}}, this.checked)" style="margin-top:2px;flex-shrink:0;cursor:pointer">` : '<span style="color:#484f58;flex-shrink:0">◦</span>'}}
      <div>
        <div class="card-text">${{esc(t.text)}}</div>
        <div class="card-meta">${{esc((t.source||'').split('/').pop())}}${{t.section ? ' · ' + esc(t.section) : ''}}</div>
      </div>
    </div>`).join('');
}}

function renderIdeas() {{
  const q2 = (document.getElementById('idea-search').value || '').toLowerCase();
  const ideas = DATA.ideas.filter(i => matchesCard(i) && (!q2 || i.text.toLowerCase().includes(q2)));
  document.getElementById('idea-count').textContent = ideas.length + ' ideas';
  document.getElementById('tab-ideas-n').textContent = '(' + ideas.length + ')';
  document.getElementById('idea-list').innerHTML = ideas.slice(0,200).map(i => `
    <div class="card">
      <div class="card-text">${{esc(i.text)}}</div>
      <div class="card-meta">${{esc((i.source||'').split('/').pop())}}${{i.section ? ' · ' + esc(i.section) : ''}}${{i.tagged ? ' · <span style=\\"color:#58a6ff\\">#idea</span>' : ''}}</div>
    </div>`).join('');
}}

let inboxFilter = 'all';
function setInboxFilter(f) {{
  inboxFilter = f;
  ['all','idea','task','daily','plan'].forEach(k => {{
    const el = document.getElementById('inbox-filter-' + k);
    if (el) el.classList.toggle('active', k === f);
  }});
  renderInbox();
}}

function renderInbox() {{
  const q = (document.getElementById('inbox-search').value || '').toLowerCase();
  const qg = (document.getElementById('search-global').value || '').toLowerCase();

  // Merge ideas + tasks into one feed
  const ideas = DATA.ideas.map(i => ({{ ...i, _kind: 'idea' }}));
  const tasks = DATA.tasks.map(t => ({{ ...t, _kind: 'task' }}));
  let items = [...ideas, ...tasks];

  // Filter by inbox type
  if (inboxFilter === 'idea')  items = items.filter(x => x._kind === 'idea');
  if (inboxFilter === 'task')  items = items.filter(x => x._kind === 'task');
  if (inboxFilter === 'daily') items = items.filter(x => x.source_type === 'daily');
  if (inboxFilter === 'plan')  items = items.filter(x => x.source_type === 'plan');

  // Text filter
  items = items.filter(x => {{
    const t = (x.text || '').toLowerCase();
    const s = (x.source || '').toLowerCase();
    return (!q || t.includes(q) || s.includes(q)) && (!qg || t.includes(qg) || s.includes(qg));
  }});

  // Sort: daily first (most recent), then plan
  items.sort((a, b) => {{
    if (a.source_type !== b.source_type) return a.source_type === 'daily' ? -1 : 1;
    return (b.source || '').localeCompare(a.source || '');
  }});

  document.getElementById('inbox-count').textContent = items.length + ' items';
  document.getElementById('tab-inbox-n').textContent = '(' + items.length + ')';

  document.getElementById('inbox-list').innerHTML = items.slice(0, 400).map(item => {{
    const srcName = esc((item.source || '').split('/').pop().replace('.md',''));
    const srcBadge = item.source_type === 'daily'
      ? '<span style="color:#d29922;font-size:10px">📅 Daily</span>'
      : '<span style="color:#8b949e;font-size:10px">📄 Plan</span>';
    const kindBadge = item._kind === 'idea'
      ? '<span style="color:#58a6ff;font-size:10px">💡 idea</span>'
      : '<span style="color:#3fb950;font-size:10px">◦ task</span>';
    const tagBadge = item.tagged ? ' <span style="color:#58a6ff;font-size:10px">#idea</span>' : '';
    const openLink = item.xcallback
      ? `<a href="${{esc(item.xcallback)}}" style="margin-left:auto;font-size:11px;color:#58a6ff;text-decoration:none;flex-shrink:0" title="Open in NotePlan">↗</a>`
      : '';
    return `<div class="card">
      <div class="card-text" style="margin-bottom:5px">${{esc(item.text)}}</div>
      <div class="card-meta" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
        ${{srcBadge}} ${{kindBadge}}${{tagBadge}}
        <span style="color:#484f58">${{srcName}}${{item.section ? ' · ' + esc(item.section) : ''}}</span>
        ${{openLink}}
      </div>
    </div>`;
  }}).join('');
}}

function renderInitiatives() {{
  const q = (document.getElementById('init-search').value || '').toLowerCase();
  const qg = (document.getElementById('search-global').value || '').toLowerCase();

  let plans = DATA.plans.filter(p => matchesPlan(p));
  if (q) plans = plans.filter(p =>
    p.title.toLowerCase().includes(q) ||
    (p.initiative||'').toLowerCase().includes(q) ||
    (p.project||'').toLowerCase().includes(q)
  );
  if (qg) plans = plans.filter(p =>
    p.title.toLowerCase().includes(qg) ||
    (p.initiative||'').toLowerCase().includes(qg)
  );

  // Group by initiative (fallback to project)
  const groups = {{}};
  plans.forEach(p => {{
    const key = (p.initiative || p.project || 'Uncategorized').trim() || 'Uncategorized';
    groups[key] = groups[key] || [];
    groups[key].push(p);
  }});

  // Sort groups: those with explicit initiative: first, then by size
  const sorted = Object.entries(groups).sort((a, b) => {{
    const aHasInit = a[1].some(p => p.initiative);
    const bHasInit = b[1].some(p => p.initiative);
    if (aHasInit !== bHasInit) return aHasInit ? -1 : 1;
    return b[1].length - a[1].length;
  }});

  document.getElementById('init-count').textContent = plans.length + ' plans in ' + sorted.length + ' initiatives';
  document.getElementById('tab-init-n').textContent = '(' + sorted.length + ')';

  const sClass = {{active:'s-active',paused:'s-paused',done:'s-done',backlog:'s-backlog'}};

  document.getElementById('initiatives-list').innerHTML = sorted.map(([group, gPlans]) => {{
    const hasInit = gPlans.some(p => p.initiative);
    return `<div class="initiative-group">
      <div class="initiative-header">
        <h3>${{hasInit ? '🎯 ' : ''}}${{esc(group)}}</h3>
        <span class="init-count">${{gPlans.length}} plan${{gPlans.length === 1 ? '' : 's'}}</span>
      </div>
      <div class="initiative-cards">
        ${{gPlans.map(p => `
          <a class="init-card" href="${{esc(p.xcallback)}}">
            <div class="ic-title">${{esc(p.title)}}</div>
            <div class="ic-meta">
              <span class="status-dot ${{sClass[p.status]||'s-unknown'}}"></span>
              <span style="color:#8b949e">${{esc(p.workstream||p.project||'')}}</span>
              <span style="font-size:14px">${{esc(p.plantype||'')}}</span>
              <span style="color:#3fb950;margin-left:auto">✓${{p.done_tasks}}</span>
              <span style="color:#d29922">◦${{p.open_tasks}}</span>
            </div>
          </a>`).join('')}}
      </div>
    </div>`;
  }}).join('');
}}

function rerender() {{
  renderPlans();
  renderTasks();
  renderIdeas();
  renderInbox();
  renderInitiatives();
}}

// ── Server mode (interactive write-back when served via noteplan-sweep serve) ──
const SERVER_MODE = window.location.protocol === 'http:' && window.location.hostname === 'localhost';
const API = SERVER_MODE ? '' : null;  // base URL — empty = same origin

async function apiPost(endpoint, body) {{
  if (!API && API !== '') return null;
  try {{
    const r = await fetch(endpoint, {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(body),
    }});
    return await r.json();
  }} catch(e) {{
    console.warn('API error:', e);
    return null;
  }}
}}

function showToast(msg, ok = true) {{
  let t = document.getElementById('np-toast');
  if (!t) {{
    t = document.createElement('div');
    t.id = 'np-toast';
    t.style.cssText = 'position:fixed;bottom:20px;right:20px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 16px;font-size:12px;z-index:9999;transition:opacity 0.3s;pointer-events:none';
    document.body.appendChild(t);
  }}
  t.textContent = msg;
  t.style.color = ok ? '#3fb950' : '#f85149';
  t.style.opacity = '1';
  clearTimeout(t._to);
  t._to = setTimeout(() => t.style.opacity = '0', 2000);
}}

// Kanban drag-and-drop (server mode only)
function makeCardDraggable(cardEl, stem) {{
  if (!SERVER_MODE) return;
  cardEl.setAttribute('draggable', 'true');
  cardEl.addEventListener('dragstart', e => {{
    e.dataTransfer.setData('text/plain', stem);
    cardEl.style.opacity = '0.5';
  }});
  cardEl.addEventListener('dragend', () => cardEl.style.opacity = '');
}}

function makeColDropTarget(colEl, statusKey) {{
  if (!SERVER_MODE) return;
  colEl.addEventListener('dragover', e => {{ e.preventDefault(); colEl.style.background = '#1f4a2a22'; }});
  colEl.addEventListener('dragleave', () => colEl.style.background = '');
  colEl.addEventListener('drop', async e => {{
    e.preventDefault();
    colEl.style.background = '';
    const stem = e.dataTransfer.getData('text/plain');
    if (!stem) return;
    const statusEmoji = {{'backlog':'🔵','active':'🟢','paused':'🟡','done':'✅'}}[statusKey] || statusKey;
    const res = await apiPost('/api/plan-status', {{stem, status: statusEmoji}});
    if (res && res.ok) {{
      // Update in-memory data
      const p = DATA.plans.find(p => p.stem === stem);
      if (p) {{ p.status = statusKey; p.status_emoji = statusEmoji; }}
      renderPlans();
      showToast(`✓ Moved to ${{statusKey}}`);
    }} else {{
      showToast(`✗ ${{res ? res.error : 'Server error'}}`, false);
    }}
  }});
}}

// Frontmatter sidebar
let _sidebarPlan = null;

function openSidebar(plan) {{
  if (!SERVER_MODE) return;
  _sidebarPlan = plan;
  let sb = document.getElementById('np-sidebar');
  if (!sb) {{
    sb = document.createElement('div');
    sb.id = 'np-sidebar';
    sb.style.cssText = 'position:fixed;top:0;right:0;width:300px;height:100vh;background:#161b22;border-left:1px solid #30363d;padding:20px;z-index:200;overflow-y:auto;transition:transform 0.2s';
    sb.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <strong style="color:#e6edf3">Edit Plan</strong>
        <button onclick="closeSidebar()" style="background:none;border:none;color:#8b949e;cursor:pointer;font-size:16px">✕</button>
      </div>
      <div id="sb-title" style="font-size:12px;color:#8b949e;margin-bottom:16px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"></div>
      <label style="font-size:11px;color:#484f58;text-transform:uppercase">Status</label>
      <select id="sb-status" style="width:100%;background:#21262d;border:1px solid #30363d;border-radius:5px;padding:6px;color:#e6edf3;margin:4px 0 12px;font-size:13px">
        <option value="🔵">🔵 Backlog</option>
        <option value="🟢">🟢 Active</option>
        <option value="🟡">🟡 Paused</option>
        <option value="✅">✅ Done</option>
      </select>
      <label style="font-size:11px;color:#484f58;text-transform:uppercase">Initiative</label>
      <input id="sb-initiative" style="width:100%;background:#21262d;border:1px solid #30363d;border-radius:5px;padding:6px;color:#e6edf3;margin:4px 0 12px;font-size:13px" placeholder="e.g. Config Agent">
      <label style="font-size:11px;color:#484f58;text-transform:uppercase">Completed</label>
      <input id="sb-completed" type="date" style="width:100%;background:#21262d;border:1px solid #30363d;border-radius:5px;padding:6px;color:#e6edf3;margin:4px 0 16px;font-size:13px">
      <button onclick="saveSidebar()" style="width:100%;background:#238636;border:none;border-radius:5px;padding:8px;color:#fff;font-size:13px;cursor:pointer">Save</button>
    `;
    document.body.appendChild(sb);
  }}
  document.getElementById('sb-title').textContent = plan.title;
  document.getElementById('sb-status').value = plan.status_emoji || '🔵';
  document.getElementById('sb-initiative').value = plan.initiative || '';
  document.getElementById('sb-completed').value = plan.end_date || '';
  sb.style.transform = 'translateX(0)';
}}

function closeSidebar() {{
  const sb = document.getElementById('np-sidebar');
  if (sb) sb.style.transform = 'translateX(100%)';
  _sidebarPlan = null;
}}

async function saveSidebar() {{
  if (!_sidebarPlan) return;
  const status = document.getElementById('sb-status').value;
  const initiative = document.getElementById('sb-initiative').value.trim();
  const completed = document.getElementById('sb-completed').value;
  const updates = {{ status }};
  if (initiative) updates.initiative = initiative;
  if (completed) updates.completed = completed;
  const res = await apiPost('/api/frontmatter', {{path: _sidebarPlan.path, updates}});
  if (res && res.ok) {{
    Object.assign(_sidebarPlan, {{
      status_emoji: status,
      status: {{'🔵':'backlog','🟢':'active','🟡':'paused','✅':'done'}}[status]||'backlog',
      initiative: initiative,
      end_date: completed,
    }});
    closeSidebar();
    rerender();
    showToast('✓ Plan updated');
  }} else {{
    showToast(`✗ ${{res ? res.error : 'Server error'}}`, false);
  }}
}}

// Task toggle (server mode)
async function toggleTask(path, lineNum, checked) {{
  const res = await apiPost('/api/task', {{path, line: lineNum, checked}});
  if (res && res.ok) {{
    // Flip in DATA.tasks
    const t = DATA.tasks.find(t => t.source_path === path && t.line === lineNum);
    if (t) t._checked = checked;
    showToast(checked ? '✓ Task completed' : '○ Task reopened');
  }} else {{
    showToast(`✗ ${{res ? res.error : 'Server error'}}`, false);
  }}
}}

window.addEventListener('DOMContentLoaded', () => {{
  setInboxFilter('all');
  rerender();
  initGantt();
  if (SERVER_MODE) {{
    // Show server-mode indicator in header
    const ind = document.createElement('span');
    ind.textContent = '⚡ Live';
    ind.title = 'Server mode — edits write to NotePlan files';
    ind.style.cssText = 'font-size:11px;color:#3fb950;background:#1f4a2a;border:1px solid #238636;border-radius:4px;padding:2px 7px;';
    document.getElementById('topbar-row1').appendChild(ind);
  }}
}});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_dashboard_generate(args):
    root = utils.noteplan_root()
    notes = root / "Notes"
    calendar = root / "Calendar"
    dash_dir = root / "dashboard"
    dash_dir.mkdir(exist_ok=True)

    # Ensure .gitkeep exists (so dir is committed even when HTML is gitignored)
    gitkeep = dash_dir / ".gitkeep"
    if not gitkeep.exists() and not utils.DRY_RUN:
        gitkeep.touch()

    # CM-E: run conversation-mine as pre-step unless --skip-mine passed
    if not getattr(args, 'skip_mine', False):
        utils.verbose("Running conversation-mine pre-step...")
        try:
            from noteplan_sweep import conversation_mine as cm
            import types
            mine_args = types.SimpleNamespace(
                since=None, full=False, projects=None, no_writeback=True
            )
            cm.cmd_conversation_mine(mine_args)
        except Exception as e:
            utils.verbose(f"  conversation-mine pre-step skipped: {e}")

    utils.verbose("Scanning plans...")
    plans = scan_plans(notes)
    utils.verbose(f"Found {len(plans)} plan files")

    utils.verbose("Extracting tasks and ideas...")
    tasks, _ = scan_tasks_and_ideas(notes, calendar)

    # Use discovered_ideas.json if available (enriched by conversation-mine)
    discovered_path = dash_dir / "discovered_ideas.json"
    if discovered_path.exists():
        try:
            ideas = json.loads(discovered_path.read_text(encoding="utf-8"))
            utils.verbose(f"Found {len(tasks)} open tasks, {len(ideas)} ideas (from discovered_ideas.json)")
        except Exception:
            _, ideas = scan_tasks_and_ideas(notes, calendar)
            utils.verbose(f"Found {len(tasks)} open tasks, {len(ideas)} ideas")
    else:
        _, ideas = scan_tasks_and_ideas(notes, calendar)
        utils.verbose(f"Found {len(tasks)} open tasks, {len(ideas)} ideas")

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = build_html(plans, tasks, ideas, generated_at)

    out = dash_dir / "plans.html"
    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would write {out} ({len(plans)} plans, {len(tasks)} tasks, {len(ideas)} ideas)")
        return

    out.write_text(html, encoding="utf-8")
    utils.log(f"dashboard-generate: wrote {out} ({len(plans)} plans, {len(tasks)} tasks, {len(ideas)} ideas)")

    # Write data sidecar for conversation-mine to consume
    data_path = dash_dir / "dashboard-data.json"
    data_path.write_text(json.dumps({
        "plans": plans,
        "tasks": tasks,
        "ideas": ideas,
        "generated_at": generated_at,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_dashboard_open(args):
    root = utils.noteplan_root()
    path = root / "dashboard" / "plans.html"
    if not path.exists():
        utils.err("dashboard/plans.html not found. Run dashboard-generate first.")
        sys.exit(utils.EXIT_NOT_FOUND)
    import subprocess as sp
    sp.run(["open", str(path)])
    utils.log(f"dashboard-open: opened {path}")
