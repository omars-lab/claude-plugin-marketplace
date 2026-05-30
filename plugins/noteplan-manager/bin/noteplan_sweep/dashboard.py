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

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Idea Dashboard</title>
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

  /* ── Gantt placeholder ── */
  .gantt-ph {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 40px; text-align: center; color: #484f58; }}
  .gantt-ph p {{ margin-top: 8px; font-size: 12px; }}
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
      <strong>Gantt View — coming in Phase C</strong>
      <p>Will use Frappe Gantt to render plan timelines.<br>
      Start = filename YYMMDD · End = <code>completed:</code> frontmatter (set by conversation-mine)</p>
    </div>
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

</div>

<script>
const DATA = {data_json};

// ── Filter state ──────────────────────────────────────────────────────────
// Multi-select per facet (empty set = "all")
const sel = {{ status: new Set(), project: new Set(), plantype: new Set() }};

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
  const names = ['plans','gantt','tasks','ideas'];
  document.querySelectorAll('.tab').forEach((el, i) => el.classList.toggle('active', names[i] === tab));
  document.querySelectorAll('.pane').forEach(el => el.classList.remove('active'));
  document.getElementById('pane-' + tab).classList.add('active');
}}

// ── Renderers ─────────────────────────────────────────────────────────────
const sClass = {{active:'s-active',paused:'s-paused',done:'s-done',backlog:'s-backlog'}};

function renderPlans() {{
  const q2 = (document.getElementById('plan-search').value || '').toLowerCase();
  const plans = DATA.plans.filter(p => matchesPlan(p) && (
    !q2 || p.title.toLowerCase().includes(q2) || p.description.toLowerCase().includes(q2)
  ));
  document.getElementById('plan-count').textContent = plans.length + ' plans';
  document.getElementById('tab-plans-n').textContent = '(' + plans.length + ')';
  document.getElementById('plans-body').innerHTML = plans.map(p => `
    <tr>
      <td><span class="status-dot ${{sClass[p.status]||'s-unknown'}}"></span></td>
      <td><a class="np-link" href="${{esc(p.xcallback)}}">${{esc(p.title)}}</a></td>
      <td style="color:#8b949e;white-space:nowrap">${{esc(p.project||'')}}</td>
      <td style="color:#8b949e">${{esc(p.workstream||'')}}</td>
      <td style="font-size:15px">${{esc(p.plantype||'')}}</td>
      <td style="color:#484f58;white-space:nowrap">${{esc(p.start_date||'')}}</td>
      <td><div class="task-bar"><span class="td">✓${{p.done_tasks}}</span>&nbsp;<span class="to">◦${{p.open_tasks}}</span></div></td>
      <td style="color:#8b949e;max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
          title="${{esc(p.description||'')}}">${{esc(p.description||'')}}</td>
    </tr>`).join('');
}}

function renderTasks() {{
  const q2 = (document.getElementById('task-search').value || '').toLowerCase();
  const tasks = DATA.tasks.filter(t => matchesCard(t) && (!q2 || t.text.toLowerCase().includes(q2)));
  document.getElementById('task-count').textContent = tasks.length + ' tasks';
  document.getElementById('tab-tasks-n').textContent = '(' + tasks.length + ')';
  document.getElementById('task-list').innerHTML = tasks.slice(0,300).map(t => `
    <div class="card">
      <div class="card-text">◦ ${{esc(t.text)}}</div>
      <div class="card-meta">${{esc((t.source||'').split('/').pop())}}${{t.section ? ' · ' + esc(t.section) : ''}}</div>
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

function rerender() {{
  renderPlans();
  renderTasks();
  renderIdeas();
}}

window.addEventListener('DOMContentLoaded', rerender);
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
