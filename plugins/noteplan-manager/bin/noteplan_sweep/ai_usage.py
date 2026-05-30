"""
ai_usage.py — AI usage mining for noteplan-sweep.

Commands:
  ai-usage-mine       Index all Claude transcripts → dashboard/ai-usage.json
  ai-usage-generate   Read ai-usage.json → write dashboard/ai-usage.html
  ai-usage-open       Open dashboard/ai-usage.html in browser
"""

import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import noteplan_sweep.utils as utils


# ---------------------------------------------------------------------------
# Path utilities
# ---------------------------------------------------------------------------

def _claude_projects_dir() -> Path:
    return Path.home() / ".claude" / "projects"


def _workspace_dirs() -> list[Path]:
    """Return candidate workspace root directories."""
    candidates = [
        Path.home() / "workspace",
        Path.home() / "Library" / "CloudStorage" / "OneDrive-ServiceNow" / "workspace",
    ]
    return [p for p in candidates if p.exists()]


def _label_from_key(key: str, workspace_dirs: list[Path]) -> str:
    """Derive a readable project label from a sanitized Claude project key.

    Strategy: try to match the key suffix against known workspace directory names.
    Falls back to stripping known path prefixes and taking the last meaningful segment.
    """
    # Build reverse map: sanitized_dir_name → readable_name
    for ws in workspace_dirs:
        try:
            for d in ws.iterdir():
                if d.is_dir():
                    sanitized = re.sub(r'[^A-Za-z0-9_\-]', '-', str(d))
                    sanitized = re.sub(r'-+', '-', sanitized).lstrip('-')
                    # Check if the key ends with the sanitized version of this repo
                    if key.endswith('-' + d.name) or key.endswith(d.name):
                        return d.name
        except Exception:
            pass

    # Fallback: strip common path prefixes, return last segment
    clean = key.lstrip('-')
    # Remove known prefixes
    for prefix in [
        'Users-omar-eid-Library-CloudStorage-OneDrive-ServiceNow-workspace-',
        'Users-omar-eid-workspace-',
        'Users-omar-eid--claude-',
        'Users-omar-eid-Desktop-',
        'Users-omar-eid-Downloads-',
        'Users-omar-eid-',
    ]:
        if clean.startswith(prefix):
            remainder = clean[len(prefix):]
            if remainder:
                return remainder
            break

    # Last resort: take last 2 dash-separated tokens (usually repo name)
    parts = clean.split('-')
    return '-'.join(parts[-2:]) if len(parts) >= 2 else clean


def _domain_from_label(label: str) -> str:
    """Map a project label to a domain (ServiceNow / Personal / EarlBear / Other)."""
    label_lower = label.lower()
    if any(x in label_lower for x in ('ceg-', 'ceg_', 'sn-', 'servicenow', 'snow', 'arch-kit',
                                        'expert', 'docintel', 'nowassist', 'foundry', 'glide',
                                        'anthropic-eval', 'eval-harness')):
        return 'ServiceNow'
    if any(x in label_lower for x in ('earlbear', 'earl-bear', 'earl_bear')):
        return 'EarlBear'
    if any(x in label_lower for x in ('noteplan', 'oeid', 'bikar', 'prayer', 'quran',
                                        'personal', 'scripts', 'plans')):
        return 'Personal'
    return 'Other'


# ---------------------------------------------------------------------------
# Lightweight JSONL reader (reads only first few lines for metadata)
# ---------------------------------------------------------------------------

def _read_first_lines(path: Path, n: int = 10) -> list[dict]:
    results = []
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(json.loads(line))
                except Exception:
                    pass
                if len(results) >= n:
                    break
    except Exception:
        pass
    return results


def _extract_session_meta(jsonl_path: Path) -> dict | None:
    """Extract session metadata from a transcript JSONL using only the first few lines."""
    messages = _read_first_lines(jsonl_path, n=15)
    if not messages:
        return None

    session_id = jsonl_path.stem
    cwd = None
    first_date = None

    for msg in messages:
        if not cwd and msg.get('cwd'):
            cwd = msg['cwd']
        if not first_date and msg.get('timestamp'):
            try:
                first_date = msg['timestamp'][:10]  # YYYY-MM-DD
            except Exception:
                pass
        if cwd and first_date:
            break

    # Fall back to file mtime for date
    if not first_date:
        mtime = datetime.fromtimestamp(jsonl_path.stat().st_mtime, tz=timezone.utc)
        first_date = mtime.strftime('%Y-%m-%d')

    # File size as proxy for session complexity
    file_size = jsonl_path.stat().st_size

    return {
        'session_id': session_id,
        'cwd': cwd or '',
        'date': first_date,
        'file_size': file_size,
        'transcript_path': str(jsonl_path),
    }


# ---------------------------------------------------------------------------
# Cursor management
# ---------------------------------------------------------------------------

def _load_cursor(dashboard_dir: Path) -> dict:
    p = dashboard_dir / 'ai-usage-cursor.json'
    if p.exists():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'processed': {}}  # {session_id: True}


def _save_cursor(dashboard_dir: Path, cursor: dict):
    p = dashboard_dir / 'ai-usage-cursor.json'
    p.write_text(json.dumps(cursor, indent=2), encoding='utf-8')


# ---------------------------------------------------------------------------
# ai-usage-mine
# ---------------------------------------------------------------------------

def cmd_ai_usage_mine(args):
    root = utils.noteplan_root()
    dash_dir = root / 'dashboard'
    dash_dir.mkdir(exist_ok=True)

    gitkeep = dash_dir / '.gitkeep'
    if not gitkeep.exists():
        gitkeep.touch()

    projects_dir = _claude_projects_dir()
    if not projects_dir.exists():
        utils.err(f"Claude projects directory not found: {projects_dir}")
        sys.exit(utils.EXIT_NOT_FOUND)

    workspace_dirs = _workspace_dirs()
    full_mode = getattr(args, 'full', False)

    cursor = {} if full_mode else _load_cursor(dash_dir)
    already_processed: set = set(cursor.get('processed', {}).keys())

    # --since filter
    since_dt = None
    if hasattr(args, 'since') and args.since:
        try:
            since_dt = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
        except ValueError:
            utils.err(f"Invalid --since date: {args.since}")
            sys.exit(utils.EXIT_VALIDATION_FAILURE)

    utils.log(f"Scanning {projects_dir} ...")

    # Load existing ai-usage.json to merge
    existing_path = dash_dir / 'ai-usage.json'
    existing_data: dict = {}
    if existing_path.exists() and not full_mode:
        try:
            existing_data = json.loads(existing_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    existing_sessions: dict = {s['session_id']: s for s in existing_data.get('sessions', [])}

    # Walk all project directories
    project_dirs = [d for d in projects_dir.iterdir() if d.is_dir()]
    utils.log(f"Found {len(project_dirs)} project directories")

    new_count = 0
    for project_dir in sorted(project_dirs):
        key = project_dir.name
        label = _label_from_key(key, workspace_dirs)
        domain = _domain_from_label(label)

        jsonl_files = sorted(project_dir.glob('*.jsonl'))
        for jf in jsonl_files:
            session_id = jf.stem
            if session_id in already_processed and not full_mode:
                continue
            if since_dt:
                mtime = datetime.fromtimestamp(jf.stat().st_mtime, tz=timezone.utc)
                if mtime < since_dt:
                    continue

            meta = _extract_session_meta(jf)
            if not meta:
                continue

            meta['project_key'] = key
            meta['project_label'] = label
            meta['domain'] = domain

            existing_sessions[session_id] = meta
            already_processed.add(session_id)
            new_count += 1

        # Also check root-level JSONL (flat format sessions)
        for jf in project_dir.parent.glob(f'{project_dir.name}*.jsonl'):
            session_id = jf.stem
            if session_id in already_processed and not full_mode:
                continue

    utils.log(f"Indexed {new_count} new session(s), {len(existing_sessions)} total")

    sessions = list(existing_sessions.values())

    # Build per-project aggregates
    by_project: dict[str, dict] = {}
    now = datetime.now(tz=timezone.utc)
    thirty_days_ago = (now - timedelta(days=30)).strftime('%Y-%m-%d')

    for s in sessions:
        lbl = s.get('project_label', 'unknown')
        if lbl not in by_project:
            by_project[lbl] = {
                'label': lbl,
                'domain': s.get('domain', 'Other'),
                'session_count': 0,
                'last_30_days': 0,
                'first_date': s.get('date', ''),
                'last_date': s.get('date', ''),
                'total_size_bytes': 0,
            }
        p = by_project[lbl]
        p['session_count'] += 1
        p['total_size_bytes'] += s.get('file_size', 0)
        if s.get('date', '') > p['last_date']:
            p['last_date'] = s['date']
        if s.get('date', '') < p['first_date'] or not p['first_date']:
            p['first_date'] = s['date']
        if s.get('date', '') >= thirty_days_ago:
            p['last_30_days'] += 1

    projects_list = sorted(by_project.values(), key=lambda x: -x['session_count'])

    # Sessions per day (last 90 days)
    ninety_days_ago = (now - timedelta(days=90)).strftime('%Y-%m-%d')
    daily_counts: dict[str, int] = {}
    for s in sessions:
        d = s.get('date', '')
        if d >= ninety_days_ago:
            daily_counts[d] = daily_counts.get(d, 0) + 1

    # Summary for Work Board tile
    last_30 = sum(1 for s in sessions if s.get('date', '') >= thirty_days_ago)
    top_project = projects_list[0]['label'] if projects_list else ''

    summary = {
        'total_sessions': len(sessions),
        'total_projects': len(by_project),
        'last_30_days': last_30,
        'top_project': top_project,
        'total_files_written': 0,  # populated by --deep mode (AUD-B)
        'indexed_at': now.isoformat(),
    }

    output = {
        'summary': summary,
        'projects': projects_list,
        'sessions': sessions,
        'daily_counts': daily_counts,
        'generated_at': now.isoformat(),
    }

    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would write {existing_path} ({len(sessions)} sessions, {len(projects_list)} projects)")
        return

    existing_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    utils.log(f"ai-usage-mine: wrote {existing_path}")
    utils.log(f"  {len(sessions)} sessions · {len(projects_list)} projects · {last_30} in last 30 days · top: {top_project}")

    _save_cursor(dash_dir, {'processed': {sid: True for sid in already_processed}})


# ---------------------------------------------------------------------------
# ai-usage-generate (Phase D stub — full HTML in AUD-D)
# ---------------------------------------------------------------------------

def cmd_ai_usage_generate(args):
    root = utils.noteplan_root()
    dash_dir = root / 'dashboard'
    data_path = dash_dir / 'ai-usage.json'

    if not data_path.exists():
        utils.err("dashboard/ai-usage.json not found. Run ai-usage-mine first.")
        sys.exit(utils.EXIT_NOT_FOUND)

    data = json.loads(data_path.read_text(encoding='utf-8'))
    summary = data.get('summary', {})
    projects = data.get('projects', [])
    daily = data.get('daily_counts', {})
    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Sort daily counts for chart
    sorted_days = sorted(daily.items())
    chart_labels = json.dumps([d for d, _ in sorted_days])
    chart_data   = json.dumps([c for _, c in sorted_days])

    # Top 10 projects by session count
    top_projects = projects[:10]
    proj_labels = json.dumps([p['label'] for p in top_projects])
    proj_counts = json.dumps([p['session_count'] for p in top_projects])

    data_json = json.dumps(data, indent=2, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AI Usage Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f0f0f; --surface: #1a1a1a; --border: #2a2a2a;
    --accent: #d97757; --accent2: #c4622d; --text: #ececec;
    --muted: #6b6b6b; --purple: #8b5cf6; --green: #3fb950;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 13px; background: var(--bg); color: var(--text); }}

  #header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 14px 24px; display: flex; align-items: center; gap: 16px; position: sticky; top: 0; z-index: 100; }}
  #header h1 {{ font-size: 16px; font-weight: 700; color: var(--accent); }}
  #header .sub {{ font-size: 12px; color: var(--muted); }}
  #gen-time {{ font-size: 11px; color: var(--muted); margin-left: auto; }}

  #tabs {{ background: var(--surface); border-bottom: 1px solid var(--border); display: flex; }}
  .tab {{ padding: 10px 18px; cursor: pointer; font-size: 13px; color: var(--muted); border-bottom: 2px solid transparent; }}
  .tab.active {{ color: var(--text); border-bottom-color: var(--accent); }}

  #content {{ padding: 20px 24px; }}
  .pane {{ display: none; }}
  .pane.active {{ display: block; }}

  /* Summary tiles */
  .tile-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .tile {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; text-align: center; }}
  .tile .num {{ font-size: 32px; font-weight: 700; color: var(--accent); }}
  .tile .lbl {{ font-size: 11px; color: var(--muted); margin-top: 4px; }}

  /* Charts */
  .chart-row {{ display: grid; grid-template-columns: 2fr 1fr; gap: 20px; margin-bottom: 24px; }}
  .chart-box {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }}
  .chart-box h3 {{ font-size: 13px; color: var(--muted); margin-bottom: 12px; }}

  /* Project table */
  .proj-table {{ width: 100%; border-collapse: collapse; }}
  .proj-table th {{ text-align: left; padding: 7px 10px; font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); }}
  .proj-table td {{ padding: 7px 10px; border-bottom: 1px solid #1f1f1f; font-size: 12px; }}
  .proj-table tr:hover td {{ background: #1f1f1f; }}
  .domain-badge {{ display: inline-block; font-size: 10px; padding: 1px 6px; border-radius: 3px; }}
  .d-sn {{ background: #1a2a3a; color: #58a6ff; }}
  .d-personal {{ background: #2a1a3a; color: #d2a8ff; }}
  .d-earlbear {{ background: #1a3a2a; color: #3fb950; }}
  .d-other {{ background: #2a2a1a; color: var(--muted); }}

  /* Skill cards (Phase E placeholder) */
  .skill-ph {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 40px; text-align: center; color: var(--muted); }}
  .skill-ph p {{ margin-top: 8px; font-size: 12px; }}
</style>
</head>
<body>
<div id="header">
  <h1>🤖 AI Usage Dashboard</h1>
  <span class="sub">{summary.get('total_sessions', 0):,} sessions · {summary.get('total_projects', 0)} projects</span>
  <div id="gen-time">Generated {generated_at}</div>
</div>
<div id="tabs">
  <div class="tab active" onclick="showTab('stats')">Usage Stats</div>
  <div class="tab"        onclick="showTab('projects')">App Catalog ({len(projects)})</div>
  <div class="tab"        onclick="showTab('skills')">Prompt Library</div>
  <div class="tab"        onclick="showTab('graph')">Prompt Graph</div>
</div>
<div id="content">

  <div class="pane active" id="pane-stats">
    <div class="tile-grid">
      <div class="tile"><div class="num">{summary.get('total_sessions', 0):,}</div><div class="lbl">Total Sessions</div></div>
      <div class="tile"><div class="num">{summary.get('last_30_days', 0)}</div><div class="lbl">Last 30 Days</div></div>
      <div class="tile"><div class="num">{summary.get('total_projects', 0)}</div><div class="lbl">Projects</div></div>
      <div class="tile"><div class="num" style="font-size:14px;padding-top:6px">{summary.get('top_project', '—')}</div><div class="lbl">Top Project</div></div>
    </div>
    <div class="chart-row">
      <div class="chart-box">
        <h3>Sessions per day — last 90 days</h3>
        <canvas id="chart-daily" height="120"></canvas>
      </div>
      <div class="chart-box">
        <h3>Top 10 projects by sessions</h3>
        <canvas id="chart-projects" height="120"></canvas>
      </div>
    </div>
  </div>

  <div class="pane" id="pane-projects">
    <div style="margin-bottom:12px;display:flex;gap:8px">
      <input id="proj-search" style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:6px;padding:5px 10px;color:#ececec;font-size:13px;width:200px" placeholder="Filter projects…" oninput="renderProjects()">
    </div>
    <table class="proj-table">
      <thead><tr><th>Project</th><th>Domain</th><th>Sessions</th><th>Last 30d</th><th>First</th><th>Last</th><th>Size</th></tr></thead>
      <tbody id="proj-body"></tbody>
    </table>
  </div>

  <div class="pane" id="pane-skills">
    <div class="skill-ph">
      <div style="font-size:32px">📚</div>
      <strong>Prompt Library — coming in AUD-E</strong>
      <p>Monaco Editor viewer for all SKILL.md files across<br><code>~/workspace/oeid-claude-plugin-marketplace</code></p>
    </div>
  </div>

  <div class="pane" id="pane-graph">
    <div class="skill-ph">
      <div style="font-size:32px">🕸</div>
      <strong>Prompt Graph — coming in AUD-F</strong>
      <p>D3 force-directed graph of sessions → repos → skills</p>
    </div>
  </div>

</div>

<script>
const DATA = {data_json};

function showTab(tab) {{
  const names = ['stats','projects','skills','graph'];
  document.querySelectorAll('.tab').forEach((el, i) => el.classList.toggle('active', names[i] === tab));
  document.querySelectorAll('.pane').forEach(el => el.classList.remove('active'));
  document.getElementById('pane-' + tab).classList.add('active');
}}

function esc(s) {{ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }}

const domainClass = {{ServiceNow:'d-sn', Personal:'d-personal', EarlBear:'d-earlbear', Other:'d-other'}};

function renderProjects() {{
  const q = (document.getElementById('proj-search').value||'').toLowerCase();
  const rows = DATA.projects.filter(p => !q || p.label.toLowerCase().includes(q) || p.domain.toLowerCase().includes(q));
  document.getElementById('proj-body').innerHTML = rows.map(p => `
    <tr>
      <td style="font-weight:600">${{esc(p.label)}}</td>
      <td><span class="domain-badge ${{domainClass[p.domain]||'d-other'}}">${{esc(p.domain)}}</span></td>
      <td style="color:var(--accent)">${{p.session_count}}</td>
      <td style="color:var(--green)">${{p.last_30_days}}</td>
      <td style="color:var(--muted)">${{esc(p.first_date||'')}}</td>
      <td style="color:var(--muted)">${{esc(p.last_date||'')}}</td>
      <td style="color:var(--muted)">${{(p.total_size_bytes/1024/1024).toFixed(1)}}MB</td>
    </tr>`).join('');
}}

window.addEventListener('DOMContentLoaded', () => {{
  renderProjects();

  // Daily sessions chart
  new Chart(document.getElementById('chart-daily'), {{
    type: 'bar',
    data: {{
      labels: {chart_labels},
      datasets: [{{ data: {chart_data}, backgroundColor: '#d97757', borderRadius: 2 }}]
    }},
    options: {{
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#6b6b6b', maxTicksLimit: 10 }}, grid: {{ color: '#1f1f1f' }} }},
        y: {{ ticks: {{ color: '#6b6b6b' }}, grid: {{ color: '#1f1f1f' }} }}
      }}
    }}
  }});

  // Top projects chart
  new Chart(document.getElementById('chart-projects'), {{
    type: 'bar',
    data: {{
      labels: {proj_labels},
      datasets: [{{ data: {proj_counts}, backgroundColor: '#8b5cf6', borderRadius: 2 }}]
    }},
    options: {{
      indexAxis: 'y',
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#6b6b6b' }}, grid: {{ color: '#1f1f1f' }} }},
        y: {{ ticks: {{ color: '#6b6b6b', font: {{ size: 11 }} }}, grid: {{ display: false }} }}
      }}
    }}
  }});
}});
</script>
</body>
</html>"""

    out = dash_dir / 'ai-usage.html'
    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would write {out}")
        return
    out.write_text(html, encoding='utf-8')
    utils.log(f"ai-usage-generate: wrote {out}")


def cmd_ai_usage_open(args):
    path = utils.noteplan_root() / 'dashboard' / 'ai-usage.html'
    if not path.exists():
        utils.err("dashboard/ai-usage.html not found. Run ai-usage-generate first.")
        sys.exit(utils.EXIT_NOT_FOUND)
    import subprocess as sp
    sp.run(['open', str(path)])
    utils.log(f"ai-usage-open: opened {path}")
