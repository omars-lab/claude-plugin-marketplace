"""
contributions.py — Contributions dashboard for noteplan-sweep.

Aggregates commit history, work logs, and shipped plans into a
GitHub-style contributions view.

Commands:
  contributions-generate    Scan repos + work logs → dashboard/contributions.json + contributions.html
  contributions-open        Open dashboard/contributions.html in browser
"""

import json
import re
import subprocess
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

import noteplan_sweep.utils as utils
from noteplan_sweep.dashboard import parse_frontmatter
from noteplan_sweep.nav import hub_nav_html, ORG_CSS, ORG_JS

# ---------------------------------------------------------------------------
# Workspace roots (same as ai_usage.py)
# ---------------------------------------------------------------------------

WORKSPACE_ROOTS = [
    Path.home() / "workspace",
    Path.home() / "Library/CloudStorage/OneDrive-ServiceNow/workspace",
]

def _detect_domain(repo_name: str) -> str:
    from noteplan_sweep.config import domain_for_label
    return domain_for_label(repo_name)


# ---------------------------------------------------------------------------
# Data collectors
# ---------------------------------------------------------------------------

def _get_repo_commits(repo_path: Path, days: int = 365) -> list[dict]:
    """Return commits for the last N days from a git repo."""
    since = (date.today() - timedelta(days=days)).isoformat()
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--format=%ad|||%s|||%H", "--date=short"],
            cwd=repo_path, capture_output=True, text=True, timeout=15,
        )
        commits = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("|||", 2)
            if len(parts) < 2:
                continue
            d, msg = parts[0].strip(), parts[1].strip()
            is_ai = "Co-Authored-By: Claude" in msg or "Co-Authored-By: Claude" in (parts[2] if len(parts) > 2 else "")
            commits.append({"date": d, "message": msg[:120], "is_ai": is_ai})
        return commits
    except Exception:
        return []


def _check_ai_commits(repo_path: Path) -> bool:
    """Quick check: does this repo have any AI-authored commits?"""
    try:
        result = subprocess.run(
            ["git", "log", "--grep=Co-Authored-By: Claude", "--format=%H", "-1"],
            cwd=repo_path, capture_output=True, text=True, timeout=8,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def build_commit_heatmap(repo_data: list[dict]) -> list[dict]:
    """Aggregate daily commit counts across all repos."""
    by_date: dict[str, dict] = {}
    for repo in repo_data:
        for c in repo.get("commits", []):
            d = c["date"]
            if d not in by_date:
                by_date[d] = {"date": d, "count": 0, "ai_count": 0, "domains": []}
            by_date[d]["count"] += 1
            if c.get("is_ai"):
                by_date[d]["ai_count"] += 1
            domain = repo.get("domain", "work")
            if domain not in by_date[d]["domains"]:
                by_date[d]["domains"].append(domain)
    return [v for _, v in sorted(by_date.items())]


def extract_work_logs(notes_root: Path) -> list[dict]:
    """Extract ## Work Log table rows from all plan files."""
    work_logs: list[dict] = []
    _ROW_RE = re.compile(r'^\|\s*(\d{4}-\d{2}-\d{2})\s*\|([^|]+)\|([^|]+)\|([^|]*)\|')
    for md in notes_root.rglob("*.md"):
        if "@Trash" in str(md) or "@Archive" in str(md):
            continue
        try:
            content = md.read_text(encoding="utf-8")
        except Exception:
            continue
        in_work_log = False
        for line in content.splitlines():
            if line.strip() == "## Work Log":
                in_work_log = True
                continue
            if in_work_log and line.startswith("## "):
                in_work_log = False
            if in_work_log:
                m = _ROW_RE.match(line)
                if m:
                    work_logs.append({
                        "date": m.group(1).strip(),
                        "plan": md.stem,
                        "session": m.group(2).strip(),
                        "summary": m.group(3).strip(),
                    })
    return sorted(work_logs, key=lambda x: x["date"], reverse=True)


def extract_task_completions(notes_root: Path, days: int = 90) -> list[dict]:
    """Scan plan files for - [x] task lines; return daily counts for last N days."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    daily: dict[str, int] = {}
    _DONE_RE = re.compile(r'^\s*[-*]\s+\[x\]\s+', re.IGNORECASE)
    _DATE_CTX_RE = re.compile(r'(\d{4}-\d{2}-\d{2})')

    for md in notes_root.rglob("*.md"):
        if "@Trash" in str(md) or "@Archive" in str(md):
            continue
        try:
            content = md.read_text(encoding="utf-8")
        except Exception:
            continue

        # Use file mtime as proxy date if no inline date
        try:
            file_date = date.fromtimestamp(md.stat().st_mtime).isoformat()
        except Exception:
            file_date = date.today().isoformat()

        if file_date < cutoff:
            continue

        for line in content.splitlines():
            if not _DONE_RE.match(line):
                continue
            # Try to find an inline date on the line; fall back to file mtime
            dm = _DATE_CTX_RE.search(line)
            d = dm.group(1) if dm else file_date
            if d < cutoff:
                continue
            daily[d] = daily.get(d, 0) + 1

    # Return sorted list with zeros filled for the range
    result = []
    cur = date.today() - timedelta(days=days - 1)
    for _ in range(days):
        iso = cur.isoformat()
        result.append({"date": iso, "count": daily.get(iso, 0)})
        cur += timedelta(days=1)
    return result


def extract_shipped_plans(notes_root: Path) -> list[dict]:
    """Plans with completed: frontmatter and ✅ status."""
    shipped: list[dict] = []
    for md in notes_root.rglob("*.md"):
        if "@Trash" in str(md) or "@Archive" in str(md):
            continue
        try:
            content = md.read_text(encoding="utf-8")
        except Exception:
            continue
        fm, _ = parse_frontmatter(content)
        completed = fm.get("completed", "").strip()
        status = fm.get("status", "").strip()
        if completed and status in ("✅", "done", "completed"):
            shipped.append({
                "date": completed,
                "title": md.stem,
                "project": fm.get("project", ""),
                "plantype": fm.get("plantype", ""),
                "description": fm.get("description", ""),
            })
    return sorted(shipped, key=lambda x: x["date"], reverse=True)


# ---------------------------------------------------------------------------
# Command: contributions-generate
# ---------------------------------------------------------------------------

def cmd_contributions_generate(args):
    root = utils.noteplan_root()
    notes = root / "Notes"
    dash_dir = root / "dashboard"
    dash_dir.mkdir(exist_ok=True)

    # 1. Scan workspace repos
    repo_data: list[dict] = []
    repos_root_arg = getattr(args, "repos_root", None)
    scan_roots = [Path(repos_root_arg)] if repos_root_arg else WORKSPACE_ROOTS

    for ws_root in scan_roots:
        if not ws_root.exists():
            continue
        for subdir in sorted(ws_root.iterdir()):
            if not subdir.is_dir() or not (subdir / ".git").exists():
                continue
            domain = _detect_domain(subdir.name)
            utils.verbose(f"  Scanning {subdir.name} ({domain})...")
            commits = _get_repo_commits(subdir)
            repo_data.append({
                "name": subdir.name,
                "path": str(subdir),
                "domain": domain,
                "commits": commits,
                "commit_count": len(commits),
                "ai_commit_count": sum(1 for c in commits if c.get("is_ai")),
            })

    # 2. Build heatmap
    heatmap = build_commit_heatmap(repo_data)

    # 3. Work logs
    utils.verbose("Extracting work logs...")
    work_logs = extract_work_logs(notes)

    # 4. Shipped plans
    utils.verbose("Extracting shipped plans...")
    shipped = extract_shipped_plans(notes)

    # 4b. Task completion sparkline (last 90 days)
    utils.verbose("Extracting task completions...")
    task_completions = extract_task_completions(notes, days=90)

    # 5. Merge repo-audit.json (adds skill_count / has_claude_md)
    audit_by_name: dict[str, dict] = {}
    audit_path = dash_dir / "repo-audit.json"
    if audit_path.exists():
        try:
            audit_data = json.loads(audit_path.read_text(encoding="utf-8"))
            audit_by_name = {r.get("name", ""): r for r in audit_data.get("repos", [])}
        except Exception:
            pass

    # Slim repos — keep recent commits for drill-down, add audit fields
    repos_slim = []
    for r in repo_data:
        audit = audit_by_name.get(r["name"], {})
        # Mini heatmap: daily counts for last 90 days
        cutoff_90 = (date.today() - timedelta(days=89)).isoformat()
        daily_90: dict[str, int] = {}
        for c in r.get("commits", []):
            if c["date"] >= cutoff_90:
                daily_90[c["date"]] = daily_90.get(c["date"], 0) + 1
        # Last 5 commit messages
        recent_msgs = [c["message"] for c in r.get("commits", [])[:5]]
        last_active = r["commits"][0]["date"] if r.get("commits") else ""
        repos_slim.append({
            "name": r["name"],
            "domain": r["domain"],
            "commit_count": r["commit_count"],
            "ai_commit_count": r["ai_commit_count"],
            "skill_count": audit.get("skill_count", 0),
            "has_claude_md": audit.get("has_claude_md", False),
            "last_active": last_active,
            "daily_90": daily_90,
            "recent_commits": recent_msgs,
        })

    # 6. Summary
    today = date.today()
    month_start = date(today.year, today.month, 1).isoformat()
    total_commits = sum(r["commit_count"] for r in repo_data)
    total_ai = sum(r["ai_commit_count"] for r in repo_data)
    month_commits = sum(
        1 for r in repo_data
        for c in r.get("commits", [])
        if c["date"] >= month_start
    )

    data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "heatmap": heatmap,
        "work_logs": work_logs[:500],
        "shipped": shipped,
        "repos": repos_slim,
        "task_completions": task_completions,
        "summary": {
            "total_commits": total_commits,
            "total_ai_commits": total_ai,
            "month_commits": month_commits,
            "shipped_count": len(shipped),
            "work_log_count": len(work_logs),
            "repo_count": len(repo_data),
            "tasks_completed_90d": sum(t["count"] for t in task_completions),
        },
    }

    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would write dashboard/contributions.json "
                  f"({len(repo_data)} repos, {total_commits} commits, {len(shipped)} shipped)")
        return

    json_out = dash_dir / "contributions.json"
    json_out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    utils.log(f"contributions-generate: wrote {json_out}")

    html = build_contributions_html(data)
    html_out = dash_dir / "contributions.html"
    html_out.write_text(html, encoding="utf-8")
    utils.log(f"contributions-generate: wrote {html_out}")
    utils.log(f"  {len(repo_data)} repos · {total_commits} commits ({total_ai} AI-assisted) · "
              f"{len(shipped)} shipped · {len(work_logs)} work log entries")


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def build_contributions_html(data: dict) -> str:
    heatmap = data.get("heatmap", [])
    work_logs = data.get("work_logs", [])
    shipped = data.get("shipped", [])
    repos = data.get("repos", [])
    summary = data.get("summary", {})
    generated_at = data.get("generated_at", "")

    data_json = json.dumps(data, indent=2, ensure_ascii=False)

    _nav_html = hub_nav_html("contributions", [
        {"num": str(summary.get("total_commits", 0)),    "label": "commits / yr",  "title": "Total commits in the last 12 months"},
        {"num": str(summary.get("total_ai_commits", 0)), "label": "AI-assisted",   "title": "Commits with Claude co-authorship"},
        {"num": str(summary.get("shipped_count", 0)),    "label": "shipped plans", "title": "Plans marked ✅ completed"},
        {"num": str(summary.get("month_commits", 0)),    "label": "this month",    "title": "Commits in the current calendar month"},
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Contributions</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 13px; background: #0d1117; color: #e6edf3; }}

{ORG_CSS}

  /* Topbar */
  #topbar {{ background: #161b22; border-bottom: 1px solid #30363d; padding: 10px 20px; display: flex; align-items: center; gap: 12px; }}
  #topbar h1 {{ font-size: 15px; font-weight: 700; color: #58a6ff; white-space: nowrap; }}
  .domain-chip {{ background: #21262d; border-radius: 20px; padding: 2px 10px; font-size: 12px; color: #8b949e; cursor: pointer; border: 1px solid #30363d; user-select: none; }}
  .domain-chip:hover {{ background: #2d333b; }}
  .domain-chip.active {{ background: #1f4a2a; color: #3fb950; border-color: #3fb950; }}
  #gen-time {{ font-size: 11px; color: #484f58; margin-left: auto; white-space: nowrap; }}

  /* Tabs */
  #tabs {{ background: #161b22; border-bottom: 1px solid #30363d; display: flex; }}
  .tab {{ padding: 9px 16px; cursor: pointer; font-size: 12px; color: #8b949e; border-bottom: 2px solid transparent; white-space: nowrap; }}
  .tab.active {{ color: #e6edf3; border-bottom-color: #58a6ff; }}

  /* Content */
  #content {{ padding: 20px; }}
  .pane {{ display: none; }}
  .pane.active {{ display: block; }}

  /* Summary tiles */
  .tile-row {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .sum-tile {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; text-align: center; }}
  .sum-tile .tile-num {{ font-size: 28px; font-weight: 700; color: #3fb950; display: block; }}
  .sum-tile.ai .tile-num {{ color: #d97757; }}
  .sum-tile.shipped .tile-num {{ color: #58a6ff; }}
  .sum-tile.month .tile-num {{ color: #d2a8ff; }}
  .sum-tile .tile-label {{ font-size: 11px; color: #8b949e; margin-top: 4px; }}

  /* Heatmap */
  #heatmap-container {{ overflow-x: auto; padding-bottom: 8px; }}
  #heatmap-svg {{ display: block; }}
  .heatmap-legend {{ display: flex; align-items: center; gap: 4px; margin-top: 8px; font-size: 11px; color: #484f58; }}
  .legend-cell {{ width: 12px; height: 12px; border-radius: 2px; display: inline-block; }}

  /* Work logs */
  .wlog-week {{ margin-bottom: 20px; }}
  .wlog-week-header {{ font-size: 11px; font-weight: 700; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #21262d; }}
  .wlog-card {{ background: #161b22; border: 1px solid #30363d; border-left: 3px solid #58a6ff; border-radius: 6px; padding: 10px 14px; margin-bottom: 6px; display: flex; gap: 12px; align-items: flex-start; }}
  .wlog-date {{ font-size: 11px; color: #484f58; white-space: nowrap; min-width: 80px; }}
  .wlog-plan {{ font-weight: 600; color: #e6edf3; font-size: 12px; margin-bottom: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 300px; }}
  .wlog-summary {{ color: #8b949e; font-size: 12px; }}

  /* Shipped timeline */
  .timeline {{ position: relative; padding-left: 24px; }}
  .timeline::before {{ content: ''; position: absolute; left: 6px; top: 0; bottom: 0; width: 2px; background: #30363d; }}
  .tl-item {{ position: relative; margin-bottom: 16px; }}
  .tl-dot {{ position: absolute; left: -21px; top: 3px; width: 10px; height: 10px; border-radius: 50%; background: #3fb950; border: 2px solid #0d1117; }}
  .tl-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 10px 14px; }}
  .tl-title {{ font-weight: 600; color: #e6edf3; font-size: 13px; margin-bottom: 3px; }}
  .tl-meta {{ font-size: 11px; color: #484f58; }}
  .tl-desc {{ font-size: 12px; color: #8b949e; margin-top: 4px; }}

  /* Repo cards */
  .repo-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }}
  .repo-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 14px; }}
  .repo-name {{ font-weight: 600; color: #e6edf3; font-size: 13px; margin-bottom: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .repo-stats {{ display: flex; gap: 12px; font-size: 11px; color: #8b949e; }}
  .repo-stat-val {{ font-weight: 600; color: #e6edf3; }}
  .domain-badge {{ display: inline-block; font-size: 10px; border-radius: 12px; padding: 1px 8px; font-weight: 500; }}
  .d-work {{ background: #1f2d4a; color: #79c0ff; }}
  .d-personal {{ background: #2d2a1f; color: #e3b341; }}
  .d-earlbear {{ background: #2d1f4a; color: #d2a8ff; }}
  .ai-bar {{ margin-top: 8px; height: 4px; background: #21262d; border-radius: 2px; overflow: hidden; }}
  .ai-bar-fill {{ height: 100%; background: #d97757; border-radius: 2px; transition: width 0.3s; }}

  .filter-bar {{ display: flex; gap: 8px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }}
  .filter-bar input {{ background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 5px 10px; color: #e6edf3; font-size: 13px; width: 220px; }}
  .filter-bar input::placeholder {{ color: #484f58; }}
  .count-badge {{ font-size: 12px; color: #484f58; }}

  /* Sparkline tile */
  .sparkline-tile {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px 18px; margin-bottom: 20px; }}
  .sparkline-tile h3 {{ font-size: 12px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }}
  .sparkline-tile canvas {{ display: block; width: 100% !important; height: 60px !important; }}

  /* Repo drill-down */
  .repo-card {{ cursor: pointer; transition: border-color 0.15s; }}
  .repo-card:hover {{ border-color: #58a6ff; }}
  .repo-card.expanded {{ border-color: #58a6ff; }}
  .repo-expand {{ display: none; margin-top: 10px; padding-top: 10px; border-top: 1px solid #30363d; }}
  .repo-card.expanded .repo-expand {{ display: block; }}
  .repo-mini-heatmap {{ display: flex; gap: 1px; flex-wrap: nowrap; overflow-x: auto; margin-bottom: 8px; height: 14px; align-items: flex-end; }}
  .repo-mini-bar {{ background: #0e4429; flex-shrink: 0; width: 3px; border-radius: 1px; min-height: 2px; transition: height 0.2s; }}
  .repo-commits {{ font-size: 11px; color: #8b949e; line-height: 1.6; }}
  .repo-commits li {{ list-style: none; padding: 1px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
</style>
</head>
<body>

{_nav_html}

<div id="topbar">
  <h1>📦 Contributions</h1>
  <div id="gen-time">Generated {generated_at}</div>
</div>

<div id="tabs">
  <div class="tab active" onclick="showTab('heatmap')">Commit Heatmap</div>
  <div class="tab"        onclick="showTab('worklogs')">Work Logs <span id="n-wlogs"></span></div>
  <div class="tab"        onclick="showTab('shipped')">Shipped Plans <span id="n-shipped"></span></div>
  <div class="tab"        onclick="showTab('repos')">Repos <span id="n-repos"></span></div>
</div>

<div id="content">

  <div class="pane active" id="pane-heatmap">
    <div class="tile-row">
      <div class="sum-tile">
        <span class="tile-num">{summary.get("total_commits", 0)}</span>
        <div class="tile-label">Commits (last year)</div>
      </div>
      <div class="sum-tile ai">
        <span class="tile-num">{summary.get("total_ai_commits", 0)}</span>
        <div class="tile-label">AI-assisted commits</div>
      </div>
      <div class="sum-tile month">
        <span class="tile-num">{summary.get("month_commits", 0)}</span>
        <div class="tile-label">This month</div>
      </div>
      <div class="sum-tile shipped">
        <span class="tile-num">{summary.get("shipped_count", 0)}</span>
        <div class="tile-label">Plans shipped</div>
      </div>
      <div class="sum-tile" style="--c:#d2a8ff">
        <span class="tile-num" style="color:#d2a8ff">{summary.get("tasks_completed_90d", 0)}</span>
        <div class="tile-label">Tasks done (90d)</div>
      </div>
    </div>
    <div class="sparkline-tile">
      <h3>Tasks completed — last 90 days</h3>
      <canvas id="sparkline-chart"></canvas>
    </div>
    <div id="heatmap-container">
      <svg id="heatmap-svg"></svg>
    </div>
    <div class="heatmap-legend">
      Less&nbsp;
      <span class="legend-cell" style="background:#161b22;border:1px solid #30363d"></span>
      <span class="legend-cell" style="background:#0e4429"></span>
      <span class="legend-cell" style="background:#006d32"></span>
      <span class="legend-cell" style="background:#26a641"></span>
      <span class="legend-cell" style="background:#39d353"></span>
      &nbsp;More
    </div>
  </div>

  <div class="pane" id="pane-worklogs">
    <div class="filter-bar">
      <input type="text" id="wlog-search" placeholder="Filter work logs…" oninput="renderWorkLogs()">
      <span class="count-badge" id="wlog-count"></span>
    </div>
    <div id="wlog-body"></div>
  </div>

  <div class="pane" id="pane-shipped">
    <div class="filter-bar">
      <input type="text" id="shipped-search" placeholder="Filter shipped plans…" oninput="renderShipped()">
      <span class="count-badge" id="shipped-count"></span>
    </div>
    <div class="timeline" id="shipped-body"></div>
  </div>

  <div class="pane" id="pane-repos">
    <div class="filter-bar">
      <input type="text" id="repo-search" placeholder="Filter repos…" oninput="renderRepos()">
      <span class="count-badge" id="repo-count"></span>
    </div>
    <div class="repo-grid" id="repo-body"></div>
  </div>

</div>

<script>
const DATA = {data_json};
{ORG_JS}

const TAB_NAMES = ['heatmap','worklogs','shipped','repos'];

function esc(s) {{ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }}

function rerender() {{ renderHeatmap(); renderWorkLogs(); renderShipped(); renderRepos(); }}

function showTab(tab) {{
  document.querySelectorAll('.tab').forEach((el,i) => el.classList.toggle('active', TAB_NAMES[i] === tab));
  document.querySelectorAll('.pane').forEach(el => el.classList.remove('active'));
  document.getElementById('pane-' + tab).classList.add('active');
  if (tab === 'heatmap') renderHeatmap();
  if (tab === 'worklogs') renderWorkLogs();
  if (tab === 'shipped') renderShipped();
  if (tab === 'repos') renderRepos();
}}

// ── Heatmap ───────────────────────────────────────────────────────────────
function renderHeatmap() {{
  const svg = document.getElementById('heatmap-svg');
  const CELL = 13, GAP = 2, STEP = CELL + GAP;
  const LEFT_PAD = 30, TOP_PAD = 24;
  const WEEKS = 52;

  // Build date → count lookup
  const byDate = {{}};
  DATA.heatmap.forEach(h => {{
    if (activeOrg !== 'all' && !(h.domains||[]).includes(activeOrg)) return;
    byDate[h.date] = (byDate[h.date] || 0) + h.count;
  }});

  const today = new Date();
  const startDate = new Date(today);
  startDate.setDate(startDate.getDate() - WEEKS * 7 + 1);

  const cols = [];
  const monthLabels = [];
  let curDate = new Date(startDate);
  let weekIdx = 0;

  // Align to Sunday
  const dow = curDate.getDay();
  if (dow !== 0) curDate.setDate(curDate.getDate() - dow);

  for (let w = 0; w < WEEKS; w++) {{
    const col = [];
    let prevMonth = -1;
    for (let d = 0; d < 7; d++) {{
      const iso = curDate.toISOString().slice(0,10);
      const cnt = byDate[iso] || 0;
      const inRange = curDate >= startDate && curDate <= today;
      col.push({{ date: iso, count: cnt, inRange }});
      if (d === 0 && curDate.getMonth() !== prevMonth) {{
        monthLabels.push({{ week: w, month: curDate.toLocaleString('default',{{month:'short'}}) }});
        prevMonth = curDate.getMonth();
      }}
      curDate.setDate(curDate.getDate() + 1);
    }}
    cols.push(col);
  }}

  function color(n) {{
    if (n === 0) return '#161b22';
    if (n <= 2) return '#0e4429';
    if (n <= 5) return '#006d32';
    if (n <= 9) return '#26a641';
    return '#39d353';
  }}

  const W = LEFT_PAD + WEEKS * STEP;
  const H = TOP_PAD + 7 * STEP + 10;
  svg.setAttribute('width', W);
  svg.setAttribute('height', H);
  svg.setAttribute('viewBox', `0 0 ${{W}} ${{H}}`);

  let html = '';

  // Month labels
  monthLabels.forEach(ml => {{
    const x = LEFT_PAD + ml.week * STEP;
    html += `<text x="${{x}}" y="14" font-size="10" fill="#484f58" font-family="sans-serif">${{esc(ml.month)}}</text>`;
  }});

  // Day labels
  ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].forEach((lbl, i) => {{
    if (i % 2 === 1) {{
      const y = TOP_PAD + i * STEP + CELL - 2;
      html += `<text x="0" y="${{y}}" font-size="9" fill="#484f58" font-family="sans-serif">${{lbl}}</text>`;
    }}
  }});

  // Cells
  cols.forEach((col, w) => {{
    col.forEach((cell, d) => {{
      const x = LEFT_PAD + w * STEP;
      const y = TOP_PAD + d * STEP;
      const fill = cell.inRange ? color(cell.count) : '#0d1117';
      const border = cell.inRange ? '' : 'opacity="0.3"';
      html += `<rect x="${{x}}" y="${{y}}" width="${{CELL}}" height="${{CELL}}" rx="2" fill="${{fill}}" ${{border}}>
        <title>${{esc(cell.date)}}: ${{cell.count}} commit${{cell.count===1?'':'s'}}</title>
      </rect>`;
    }});
  }});

  svg.innerHTML = html;
}}

// ── Work Logs ─────────────────────────────────────────────────────────────
function renderWorkLogs() {{
  const q = (document.getElementById('wlog-search').value||'').toLowerCase();
  const logs = DATA.work_logs.filter(l =>
    (!q || l.plan.toLowerCase().includes(q) || l.summary.toLowerCase().includes(q))
  );
  document.getElementById('wlog-count').textContent = logs.length + ' entries';
  document.getElementById('n-wlogs').textContent = '(' + logs.length + ')';

  // Group by ISO week
  function isoWeek(dateStr) {{
    const d = new Date(dateStr);
    const jan4 = new Date(d.getFullYear(), 0, 4);
    const week = Math.ceil(((d - jan4) / 86400000 + jan4.getDay() + 1) / 7);
    return `${{d.getFullYear()}}-W${{String(week).padStart(2,'0')}}`;
  }}

  const byWeek = {{}};
  logs.forEach(l => {{
    const w = isoWeek(l.date);
    if (!byWeek[w]) byWeek[w] = [];
    byWeek[w].push(l);
  }});

  document.getElementById('wlog-body').innerHTML = Object.keys(byWeek).sort().reverse().slice(0,26).map(w => `
    <div class="wlog-week">
      <div class="wlog-week-header">Week ${{esc(w)}}</div>
      ${{byWeek[w].map(l => `
        <div class="wlog-card">
          <span class="wlog-date">${{esc(l.date)}}</span>
          <div style="flex:1;min-width:0">
            <div class="wlog-plan">${{esc(l.plan)}}</div>
            <div class="wlog-summary">${{esc(l.summary||l.session)}}</div>
          </div>
        </div>`).join('')}}
    </div>`).join('');
}}

// ── Shipped ───────────────────────────────────────────────────────────────
function renderShipped() {{
  const q = (document.getElementById('shipped-search').value||'').toLowerCase();
  const items = DATA.shipped.filter(s =>
    (!q || s.title.toLowerCase().includes(q) || (s.description||'').toLowerCase().includes(q))
  );
  document.getElementById('shipped-count').textContent = items.length + ' plans';
  document.getElementById('n-shipped').textContent = '(' + items.length + ')';
  document.getElementById('shipped-body').innerHTML = items.map(s => `
    <div class="tl-item">
      <div class="tl-dot"></div>
      <div class="tl-card">
        <div class="tl-title">${{esc(s.title)}}</div>
        <div class="tl-meta">${{esc(s.date)}}${{s.project ? ' · ' + esc(s.project) : ''}}${{s.plantype ? ' ' + esc(s.plantype) : ''}}</div>
        ${{s.description ? `<div class="tl-desc">${{esc(s.description)}}</div>` : ''}}
      </div>
    </div>`).join('');
}}

// ── Repos ─────────────────────────────────────────────────────────────────
function renderRepos() {{
  const q = (document.getElementById('repo-search').value||'').toLowerCase();
  let repos = DATA.repos.filter(r =>
    matchesDomain(r.domain) &&
    (!q || r.name.toLowerCase().includes(q))
  );
  repos = repos.sort((a,b) => b.commit_count - a.commit_count);
  document.getElementById('repo-count').textContent = repos.length + ' repos';
  document.getElementById('n-repos').textContent = '(' + repos.length + ')';

  const domainClass = {{ work: 'd-work', personal: 'd-personal', earlbear: 'd-earlbear' }};
  document.getElementById('repo-body').innerHTML = repos.map((r, idx) => {{
    const aiPct = r.commit_count > 0 ? Math.round(r.ai_commit_count / r.commit_count * 100) : 0;
    const daily90 = r.daily_90 || {{}};
    const maxCount = Math.max(1, ...Object.values(daily90));
    // Build 90-day mini bar chart (3px wide bars)
    const today = new Date();
    const bars = [];
    for (let i = 89; i >= 0; i--) {{
      const d = new Date(today); d.setDate(d.getDate() - i);
      const iso = d.toISOString().slice(0,10);
      const cnt = daily90[iso] || 0;
      const h = Math.max(2, Math.round((cnt / maxCount) * 12));
      const opacity = cnt > 0 ? 0.4 + (cnt / maxCount) * 0.6 : 0.15;
      bars.push(`<div class="repo-mini-bar" style="height:${{h}}px;opacity:${{opacity.toFixed(2)}}"></div>`);
    }}
    const commits = (r.recent_commits || []).slice(0, 5).map(m =>
      `<li>· ${{esc(m.slice(0,60))}}${{m.length > 60 ? '…' : ''}}</li>`).join('');
    return `
      <div class="repo-card" id="repo-${{idx}}" onclick="toggleRepo(${{idx}})">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px">
          <div class="repo-name">${{esc(r.name)}}</div>
          <span class="domain-badge ${{domainClass[r.domain]||'d-work'}}">${{esc(r.domain)}}</span>
        </div>
        <div class="repo-stats">
          <div><span class="repo-stat-val">${{r.commit_count}}</span> commits</div>
          <div><span class="repo-stat-val">${{r.ai_commit_count}}</span> AI</div>
          ${{r.skill_count > 0 ? `<div><span class="repo-stat-val">${{r.skill_count}}</span> skills</div>` : ''}}
          ${{r.last_active ? `<div style="color:#484f58;font-size:10px;margin-left:auto">${{esc(r.last_active)}}</div>` : ''}}
        </div>
        <div class="ai-bar" title="${{aiPct}}% AI-assisted">
          <div class="ai-bar-fill" style="width:${{aiPct}}%"></div>
        </div>
        <div class="repo-expand">
          <div class="repo-mini-heatmap">${{bars.join('')}}</div>
          ${{commits ? `<ul class="repo-commits">${{commits}}</ul>` : ''}}
        </div>
      </div>`;
  }}).join('');
}}

function toggleRepo(idx) {{
  const card = document.getElementById('repo-' + idx);
  if (card) card.classList.toggle('expanded');
}}

// ── Init ──────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {{
  _applyOrg();
  const SERVER_MODE = window.location.protocol === 'http:' && window.location.hostname === 'localhost';
  if (!SERVER_MODE) {{
    document.querySelectorAll('.hub-link[href]').forEach(el => {{
      el.title = 'Run: noteplan-sweep serve --open';
      el.removeAttribute('href');
      el.style.opacity = '0.35';
      el.style.cursor = 'default';
    }});
  }}
  document.getElementById('n-wlogs').textContent = '(' + DATA.work_logs.length + ')';
  document.getElementById('n-shipped').textContent = '(' + DATA.shipped.length + ')';
  document.getElementById('n-repos').textContent = '(' + DATA.repos.length + ')';
  renderHeatmap();

  // Task completion sparkline (Chart.js)
  const tc = DATA.task_completions || [];
  if (tc.length && document.getElementById('sparkline-chart')) {{
    new Chart(document.getElementById('sparkline-chart'), {{
      type: 'bar',
      data: {{
        labels: tc.map(t => t.date),
        datasets: [{{ data: tc.map(t => t.count), backgroundColor: '#3fb950', borderRadius: 1 }}]
      }},
      options: {{
        animation: false,
        plugins: {{ legend: {{ display: false }}, tooltip: {{ callbacks: {{
          title: items => items[0].label,
          label: item => item.raw + ' tasks done',
        }} }} }},
        scales: {{
          x: {{ display: false }},
          y: {{ display: false, min: 0 }},
        }},
        maintainAspectRatio: false,
      }}
    }});
  }}
}});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Command: contributions-open
# ---------------------------------------------------------------------------

def cmd_contributions_open(args):
    path = utils.noteplan_root() / "dashboard" / "contributions.html"
    if not path.exists():
        utils.err("dashboard/contributions.html not found. Run contributions-generate first.")
        sys.exit(utils.EXIT_NOT_FOUND)
    import subprocess as sp
    sp.run(["open", str(path)])
    utils.log(f"contributions-open: opened {path}")
