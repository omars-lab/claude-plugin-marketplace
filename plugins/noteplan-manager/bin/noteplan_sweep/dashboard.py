"""
dashboard.py — Idea Dashboard generation for noteplan-sweep.

Commands:
  dashboard-generate    Scan NotePlan files → extract data → write dashboard/ideas.html
  dashboard-open        Open dashboard/ideas.html in browser
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

        # Derive domain from path
        domain = "🏡" if "🏡" in rel else ("🏢" if "🏢" in rel else ("👥" if "👥" in rel else ""))

        plans.append({
            "stem": stem,
            "title": title,
            "status": status,
            "status_emoji": status_raw,
            "plantype": fm.get("plantype", ""),
            "description": fm.get("description", ""),
            "start_date": start_date or mtime_date(p),
            "end_date": completed or "",
            "mtime": mtime_date(p),
            "open_tasks": open_tasks,
            "done_tasks": done_tasks,
            "xcallback": xcb,
            "domain": domain,
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


def extract_tasks_and_ideas(path: Path, rel_path: str, body: str) -> tuple[list[dict], list[dict]]:
    tasks: list[dict] = []
    ideas: list[dict] = []
    lines = body.splitlines()
    in_idea_section = False
    current_section = ""

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
                "section": current_section,
                "line": i + 1,
            })

        # Ideas: either in idea section or tagged #idea
        if in_idea_section and stripped and not stripped.startswith("#"):
            # Any content line in an idea section
            text = re.sub(r'^[-*]\s*', '', stripped)
            if text:
                ideas.append({
                    "text": text,
                    "source": rel_path,
                    "section": current_section,
                    "line": i + 1,
                    "tagged": False,
                })
        elif _IDEA_TAG_RE.search(stripped):
            text = re.sub(r'^[-*]\s*(?:\[[ x]\]\s*)?', '', stripped)
            ideas.append({
                "text": text,
                "source": rel_path,
                "section": current_section,
                "line": i + 1,
                "tagged": True,
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

    status_counts = {}
    for p in plans:
        s = p["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Idea Dashboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 13px; background: #0d1117; color: #e6edf3; }}
  #header {{ background: #161b22; border-bottom: 1px solid #30363d; padding: 12px 20px; display: flex; align-items: center; gap: 20px; position: sticky; top: 0; z-index: 100; }}
  #header h1 {{ font-size: 16px; font-weight: 700; color: #58a6ff; }}
  .pill {{ background: #21262d; border-radius: 20px; padding: 3px 10px; font-size: 12px; color: #8b949e; cursor: pointer; border: 1px solid #30363d; }}
  .pill.active {{ background: #1f4a2a; color: #3fb950; border-color: #3fb950; }}
  .pill[data-status="active"].active {{ background: #1f4a2a; color: #3fb950; border-color: #3fb950; }}
  .pill[data-status="paused"].active {{ background: #2d2a1f; color: #d29922; border-color: #d29922; }}
  .pill[data-status="done"].active {{ background: #1c2128; color: #8b949e; border-color: #8b949e; }}
  .pill[data-status="backlog"].active {{ background: #1f2d4a; color: #79c0ff; border-color: #79c0ff; }}
  #gen-time {{ font-size: 11px; color: #484f58; margin-left: auto; }}
  #tabs {{ background: #161b22; border-bottom: 1px solid #30363d; display: flex; gap: 0; }}
  .tab {{ padding: 10px 20px; cursor: pointer; font-size: 13px; color: #8b949e; border-bottom: 2px solid transparent; }}
  .tab.active {{ color: #e6edf3; border-bottom-color: #58a6ff; }}
  #content {{ padding: 20px; }}
  .pane {{ display: none; }}
  .pane.active {{ display: block; }}

  /* Plans table */
  .plans-table {{ width: 100%; border-collapse: collapse; }}
  .plans-table th {{ text-align: left; padding: 8px 10px; font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #30363d; }}
  .plans-table td {{ padding: 8px 10px; border-bottom: 1px solid #21262d; vertical-align: middle; }}
  .plans-table tr:hover td {{ background: #161b22; }}
  .status-badge {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}
  .status-active {{ background: #3fb950; }}
  .status-paused {{ background: #d29922; }}
  .status-done {{ background: #484f58; }}
  .status-backlog {{ background: #79c0ff; }}
  .status-unknown {{ background: #484f58; }}
  .np-link {{ color: #58a6ff; text-decoration: none; }}
  .np-link:hover {{ text-decoration: underline; }}
  .task-bar {{ display: flex; gap: 4px; align-items: center; font-size: 11px; color: #8b949e; }}
  .task-bar .done {{ color: #3fb950; }}
  .task-bar .open {{ color: #d29922; }}

  /* Idea inbox */
  .idea-list {{ display: flex; flex-direction: column; gap: 6px; }}
  .idea-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 10px 14px; }}
  .idea-card .idea-text {{ color: #e6edf3; margin-bottom: 4px; }}
  .idea-card .idea-meta {{ font-size: 11px; color: #484f58; }}
  .idea-card .np-link {{ font-size: 11px; }}

  /* Tasks list */
  .task-list {{ display: flex; flex-direction: column; gap: 4px; }}
  .task-item {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 8px 12px; display: flex; gap: 10px; align-items: flex-start; }}
  .task-item .task-text {{ flex: 1; }}
  .task-item .task-meta {{ font-size: 11px; color: #484f58; white-space: nowrap; }}

  /* Filter bar */
  .filter-bar {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; align-items: center; }}
  .filter-bar input {{ background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 6px 10px; color: #e6edf3; font-size: 13px; width: 220px; }}
  .filter-bar input::placeholder {{ color: #484f58; }}
  .count-badge {{ font-size: 12px; color: #8b949e; margin-left: auto; }}

  /* Gantt placeholder */
  .gantt-placeholder {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 40px; text-align: center; color: #484f58; }}
  .gantt-placeholder p {{ margin-top: 8px; font-size: 12px; }}
</style>
</head>
<body>
<div id="header">
  <h1>💡 Idea Dashboard</h1>
  <div id="filter-pills">
    <span class="pill active" data-status="all" onclick="filterStatus('all')">All</span>
    <span class="pill" data-status="active" onclick="filterStatus('active')">🟢 Active</span>
    <span class="pill" data-status="paused" onclick="filterStatus('paused')">🟡 Paused</span>
    <span class="pill" data-status="backlog" onclick="filterStatus('backlog')">🔵 Backlog</span>
    <span class="pill" data-status="done" onclick="filterStatus('done')">✅ Done</span>
  </div>
  <div id="gen-time">Generated {generated_at}</div>
</div>
<div id="tabs">
  <div class="tab active" onclick="showTab('plans')">Plans ({len(plans)})</div>
  <div class="tab" onclick="showTab('gantt')">Gantt</div>
  <div class="tab" onclick="showTab('tasks')">Open Tasks ({len([t for t in tasks if t])})</div>
  <div class="tab" onclick="showTab('ideas')">Ideas ({len(ideas)})</div>
</div>
<div id="content">
  <div class="pane active" id="pane-plans">
    <div class="filter-bar">
      <input type="text" id="plan-search" placeholder="Search plans..." oninput="renderPlans()">
      <span class="count-badge" id="plan-count"></span>
    </div>
    <table class="plans-table">
      <thead>
        <tr>
          <th></th><th>Plan</th><th>Domain</th><th>Type</th>
          <th>Started</th><th>Tasks</th><th>Description</th>
        </tr>
      </thead>
      <tbody id="plans-body"></tbody>
    </table>
  </div>

  <div class="pane" id="pane-gantt">
    <div class="gantt-placeholder">
      <div style="font-size:32px">📅</div>
      <strong>Gantt View</strong>
      <p>Coming in Phase C — will use Frappe Gantt to render plan timelines.<br>
      Start date = filename YYMMDD · End date = <code>completed:</code> frontmatter (set by conversation-mine)</p>
    </div>
  </div>

  <div class="pane" id="pane-tasks">
    <div class="filter-bar">
      <input type="text" id="task-search" placeholder="Search tasks..." oninput="renderTasks()">
      <span class="count-badge" id="task-count"></span>
    </div>
    <div class="task-list" id="task-list"></div>
  </div>

  <div class="pane" id="pane-ideas">
    <div class="filter-bar">
      <input type="text" id="idea-search" placeholder="Search ideas..." oninput="renderIdeas()">
      <span class="count-badge" id="idea-count"></span>
    </div>
    <div class="idea-list" id="idea-list"></div>
  </div>
</div>

<script>
const DATA = {data_json};

let activeStatus = 'all';
let activeTab = 'plans';

function esc(s) {{
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

function showTab(tab) {{
  document.querySelectorAll('.tab').forEach((el, i) => {{
    const tabs = ['plans','gantt','tasks','ideas'];
    el.classList.toggle('active', tabs[i] === tab);
  }});
  document.querySelectorAll('.pane').forEach(el => el.classList.remove('active'));
  document.getElementById('pane-' + tab).classList.add('active');
  activeTab = tab;
}}

function filterStatus(s) {{
  activeStatus = s;
  document.querySelectorAll('.pill').forEach(el => {{
    el.classList.toggle('active', el.dataset.status === s);
  }});
  renderPlans();
  renderTasks();
  renderIdeas();
}}

function matchesStatus(plan) {{
  if (activeStatus === 'all') return true;
  return plan.status === activeStatus;
}}

function renderPlans() {{
  const q = (document.getElementById('plan-search').value || '').toLowerCase();
  const plans = DATA.plans.filter(p => matchesStatus(p) && (
    !q || p.title.toLowerCase().includes(q) || p.description.toLowerCase().includes(q)
  ));
  document.getElementById('plan-count').textContent = plans.length + ' plans';
  const statusClass = {{active:'status-active',paused:'status-paused',done:'status-done',backlog:'status-backlog'}};
  document.getElementById('plans-body').innerHTML = plans.map(p => `
    <tr>
      <td><span class="status-badge ${{statusClass[p.status] || 'status-unknown'}}"></span></td>
      <td><a class="np-link" href="${{esc(p.xcallback)}}">${{esc(p.title)}}</a></td>
      <td>${{esc(p.domain)}}</td>
      <td style="font-size:16px">${{esc(p.plantype)}}</td>
      <td style="color:#8b949e">${{esc(p.start_date)}}</td>
      <td><div class="task-bar"><span class="done">✓${{p.done_tasks}}</span><span class="open">◦${{p.open_tasks}}</span></div></td>
      <td style="color:#8b949e;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${{esc(p.description)}}</td>
    </tr>`).join('');
}}

function renderTasks() {{
  const q = (document.getElementById('task-search').value || '').toLowerCase();
  const tasks = DATA.tasks.filter(t => !q || t.text.toLowerCase().includes(q) || t.source.toLowerCase().includes(q));
  document.getElementById('task-count').textContent = tasks.length + ' tasks';
  document.getElementById('task-list').innerHTML = tasks.slice(0, 200).map(t => `
    <div class="task-item">
      <span>◦</span>
      <span class="task-text">${{esc(t.text)}}</span>
      <span class="task-meta">${{esc(t.source.split('/').pop())}} · ${{esc(t.section || '')}}</span>
    </div>`).join('');
}}

function renderIdeas() {{
  const q = (document.getElementById('idea-search').value || '').toLowerCase();
  const ideas = DATA.ideas.filter(i => !q || i.text.toLowerCase().includes(q));
  document.getElementById('idea-count').textContent = ideas.length + ' ideas';
  document.getElementById('idea-list').innerHTML = ideas.slice(0, 200).map(i => `
    <div class="idea-card">
      <div class="idea-text">${{esc(i.text)}}</div>
      <div class="idea-meta">${{esc(i.source.split('/').pop())}} · ${{esc(i.section || '')}}${{i.tagged ? ' · #idea' : ''}}</div>
    </div>`).join('');
}}

window.addEventListener('DOMContentLoaded', () => {{
  renderPlans();
  renderTasks();
  renderIdeas();
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

    utils.verbose("Scanning plans...")
    plans = scan_plans(notes)
    utils.verbose(f"Found {len(plans)} plan files")

    utils.verbose("Extracting tasks and ideas...")
    tasks, ideas = scan_tasks_and_ideas(notes, calendar)
    utils.verbose(f"Found {len(tasks)} open tasks, {len(ideas)} ideas")

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = build_html(plans, tasks, ideas, generated_at)

    out = dash_dir / "ideas.html"
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
    path = root / "dashboard" / "ideas.html"
    if not path.exists():
        utils.err("dashboard/ideas.html not found. Run dashboard-generate first.")
        sys.exit(utils.EXIT_NOT_FOUND)
    import subprocess as sp
    sp.run(["open", str(path)])
    utils.log(f"dashboard-open: opened {path}")
