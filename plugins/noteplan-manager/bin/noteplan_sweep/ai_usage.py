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
from noteplan_sweep.nav import hub_nav_html, ORG_CSS, ORG_JS


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


_AUTOMATED_FIRST_TYPES = {'queue-operation', 'remote-trigger', 'scheduled-trigger'}
_MIN_HUMAN_PROMPT_LEN = 20  # user messages shorter than this are likely scripted


def _is_automated_session(messages: list[dict]) -> bool:
    """Return True if the session was initiated programmatically, not by a human.

    Signals:
    1. First substantive message is queue-operation / remote-trigger / scheduled-trigger
    2. No user message with meaningful natural-language text (>20 chars, non-template)
    3. All user messages are very short or identical (batch/scripted pattern)
    """
    first_type = messages[0].get('type', '') if messages else ''
    if first_type in _AUTOMATED_FIRST_TYPES:
        return True

    # Check user messages for human authorship
    user_texts = []
    for msg in messages:
        if msg.get('type') == 'user':
            content = msg.get('message', {}).get('content', '')
            if isinstance(content, str):
                user_texts.append(content.strip())
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        user_texts.append(block.get('text', '').strip())

    if not user_texts:
        # No user messages at all → automated
        return True

    # If all user messages are very short, likely scripted
    long_messages = [t for t in user_texts if len(t) >= _MIN_HUMAN_PROMPT_LEN]
    if not long_messages:
        return True

    # Check for highly repetitive template patterns (same first 30 chars across messages)
    if len(user_texts) >= 3:
        prefixes = {t[:30] for t in user_texts if t}
        if len(prefixes) == 1:
            return True

    return False


def _extract_session_meta(jsonl_path: Path) -> dict | None:
    """Extract session metadata from a transcript JSONL using only the first few lines."""
    messages = _read_first_lines(jsonl_path, n=20)
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

    automated = _is_automated_session(messages)

    # File size as proxy for session complexity
    file_size = jsonl_path.stat().st_size

    return {
        'session_id': session_id,
        'cwd': cwd or '',
        'date': first_date,
        'file_size': file_size,
        'automated': automated,
        'transcript_path': str(jsonl_path),
    }


# ---------------------------------------------------------------------------
# Deep session parser (AUD-B) — reads full JSONL for tool counts + use case
# ---------------------------------------------------------------------------

_USE_CASE_PATTERNS = [
    ('Debug',       re.compile(r'\b(fix|bug|error|crash|fail|broken|exception|traceback|debug|not work)\b', re.I)),
    ('Code Gen',    re.compile(r'\b(creat|build|implement|add feature|scaffold|generat|write.*function|new.*class)\b', re.I)),
    ('Planning',    re.compile(r'\b(plan|design|architect|roadmap|strateg|approach|how should|outline)\b', re.I)),
    ('Research',    re.compile(r'\b(research|explore|find|look into|what is|explain|understand|learn|investigat)\b', re.I)),
    ('Docs',        re.compile(r'\b(document|readme|write.*doc|explain.*code|comment|describe)\b', re.I)),
    ('Review',      re.compile(r'\b(review|check|analyz|audit|evaluat|assess|look at|inspect)\b', re.I)),
    ('Refactor',    re.compile(r'\b(refactor|clean.?up|reorganiz|restructur|rename|simplif|optimiz)\b', re.I)),
]

def _classify_use_case(text: str) -> str:
    """Classify a session use case from the first user message."""
    if not text:
        return 'General'
    for label, pat in _USE_CASE_PATTERNS:
        if pat.search(text):
            return label
    return 'General'


_TOOL_TRACK = {'Write', 'Edit', 'Bash', 'Read', 'MultiEdit', 'Glob', 'Grep'}

def _parse_session_deep(jsonl_path: Path) -> dict:
    """Read full JSONL transcript and return tool counts + use case."""
    tool_counts: dict[str, int] = {}
    first_user_text = ''
    message_count = 0

    try:
        with open(jsonl_path, encoding='utf-8', errors='replace') as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    msg = json.loads(raw_line)
                except Exception:
                    continue
                message_count += 1

                # Capture first user message text
                if not first_user_text and msg.get('type') == 'user':
                    content = msg.get('message', {}).get('content', '')
                    if isinstance(content, str):
                        first_user_text = content.strip()
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get('type') == 'text':
                                first_user_text = block.get('text', '').strip()
                                if first_user_text:
                                    break

                # Count tool_use blocks
                content = msg.get('message', {}).get('content', [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get('type') == 'tool_use':
                            name = block.get('name', 'unknown')
                            key = name if name in _TOOL_TRACK else 'other'
                            tool_counts[key] = tool_counts.get(key, 0) + 1
    except Exception:
        pass

    use_case = _classify_use_case(first_user_text)
    files_written = tool_counts.get('Write', 0) + tool_counts.get('Edit', 0) + tool_counts.get('MultiEdit', 0)

    return {
        'tool_counts': tool_counts,
        'use_case': use_case,
        'message_count': message_count,
        'files_written': files_written,
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
# Skill scanner (AUD-E)
# ---------------------------------------------------------------------------

def _scan_skills() -> list[dict]:
    """Collect all SKILL.md files from noteplan-manager plugin."""
    skill_roots = [
        Path.home() / 'workspace' / 'oeid-claude-plugin-marketplace'
        / 'plugins' / 'noteplan-manager' / 'skills',
        Path.home() / 'Library' / 'CloudStorage' / 'OneDrive-ServiceNow' / 'workspace'
        / 'oeid-claude-plugin-marketplace' / 'plugins' / 'noteplan-manager' / 'skills',
    ]
    skills: list[dict] = []
    seen_names: set = set()
    for root in skill_roots:
        if not root.exists():
            continue
        for skill_file in sorted(root.rglob('SKILL.md')):
            # Derive hierarchy: skills/<group>[/<subskill>]/SKILL.md
            rel = skill_file.relative_to(root)
            parts = [p for p in rel.parts if p != 'SKILL.md']
            name = parts[-1] if parts else 'unknown'
            group = parts[0] if parts else name
            is_subskill = len(parts) > 1
            # Dedup by name (prefer workspace over OneDrive copy)
            if name in seen_names:
                continue
            seen_names.add(name)
            try:
                content = skill_file.read_text(encoding='utf-8')
            except Exception:
                continue
            # Extract description: first non-header line after frontmatter
            body = content
            if content.startswith('---'):
                end = content.find('\n---', 3)
                if end != -1:
                    body = content[end + 4:].lstrip('\n')
            description = ''
            for line in body.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    description = stripped[:200]
                    break
            skills.append({
                'name': name,
                'group': group,
                'is_subskill': is_subskill,
                'path': str(skill_file),
                'description': description,
                'content': content,
                'size': len(content),
            })
        break  # use first found root; don't double-load
    return skills


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
    deep_mode = getattr(args, 'deep', False)

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

            if deep_mode:
                utils.verbose(f"  deep-parsing {jf.name}")
                deep = _parse_session_deep(jf)
                meta['tool_counts'] = deep['tool_counts']
                meta['use_case'] = deep['use_case']
                meta['message_count'] = deep['message_count']
                meta['files_written'] = deep['files_written']
            else:
                meta.setdefault('tool_counts', {})
                meta.setdefault('use_case', '')
                meta.setdefault('message_count', 0)
                meta.setdefault('files_written', 0)

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
        is_auto = s.get('automated', False)
        if lbl not in by_project:
            by_project[lbl] = {
                'label': lbl,
                'domain': s.get('domain', 'Other'),
                'session_count': 0,
                'interactive_count': 0,
                'automated_count': 0,
                'last_30_days': 0,
                'last_30_days_interactive': 0,
                'first_date': s.get('date', ''),
                'last_date': s.get('date', ''),
                'total_size_bytes': 0,
                'total_files_written': 0,
                'tool_counts': {},
                'use_case_dist': {},
            }
        p = by_project[lbl]
        p['session_count'] += 1
        p['total_size_bytes'] += s.get('file_size', 0)
        p['total_files_written'] += s.get('files_written', 0)
        # Aggregate tool counts
        for tool, cnt in s.get('tool_counts', {}).items():
            p['tool_counts'][tool] = p['tool_counts'].get(tool, 0) + cnt
        # Aggregate use case distribution
        uc = s.get('use_case', '')
        if uc:
            p['use_case_dist'][uc] = p['use_case_dist'].get(uc, 0) + 1
        if is_auto:
            p['automated_count'] += 1
        else:
            p['interactive_count'] += 1
        if s.get('date', '') > p['last_date']:
            p['last_date'] = s['date']
        if s.get('date', '') < p['first_date'] or not p['first_date']:
            p['first_date'] = s['date']
        if s.get('date', '') >= thirty_days_ago:
            p['last_30_days'] += 1
            if not is_auto:
                p['last_30_days_interactive'] += 1

    projects_list = sorted(by_project.values(), key=lambda x: -x['session_count'])

    # Sessions per day (last 90 days) — split automated vs interactive
    ninety_days_ago = (now - timedelta(days=90)).strftime('%Y-%m-%d')
    daily_counts: dict[str, int] = {}
    daily_interactive: dict[str, int] = {}
    for s in sessions:
        d = s.get('date', '')
        if d >= ninety_days_ago:
            daily_counts[d] = daily_counts.get(d, 0) + 1
            if not s.get('automated', False):
                daily_interactive[d] = daily_interactive.get(d, 0) + 1

    total_automated = sum(1 for s in sessions if s.get('automated', False))
    total_interactive = len(sessions) - total_automated

    last_30 = sum(1 for s in sessions if s.get('date', '') >= thirty_days_ago)
    last_30_interactive = sum(
        1 for s in sessions
        if s.get('date', '') >= thirty_days_ago and not s.get('automated', False)
    )

    # Top project by interactive sessions
    interactive_projects = sorted(
        projects_list, key=lambda x: -x.get('interactive_count', 0)
    )
    top_project = interactive_projects[0]['label'] if interactive_projects else ''

    total_files_written = sum(s.get('files_written', 0) for s in sessions)
    # Global use case distribution (interactive sessions only)
    global_use_case_dist: dict[str, int] = {}
    for s in sessions:
        if not s.get('automated', False) and s.get('use_case'):
            uc = s['use_case']
            global_use_case_dist[uc] = global_use_case_dist.get(uc, 0) + 1

    summary = {
        'total_sessions': len(sessions),
        'total_interactive': total_interactive,
        'total_automated': total_automated,
        'total_projects': len(by_project),
        'last_30_days': last_30,
        'last_30_days_interactive': last_30_interactive,
        'top_project': top_project,
        'total_files_written': total_files_written,
        'use_case_dist': global_use_case_dist,
        'deep_indexed': deep_mode,
        'indexed_at': now.isoformat(),
    }

    output = {
        'summary': summary,
        'projects': projects_list,
        'sessions': sessions,
        'daily_counts': daily_counts,
        'daily_interactive': daily_interactive,
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

    # AUD-E: scan SKILL.md files for Prompt Library
    skills = _scan_skills()
    utils.verbose(f"Found {len(skills)} SKILL.md files for Prompt Library")
    # Strip content for the card list (include content separately for Monaco)
    skills_meta = [{k: v for k, v in s.items() if k != 'content'} for s in skills]
    skills_content = {s['path']: s['content'] for s in skills}
    skills_meta_json = json.dumps(skills_meta, ensure_ascii=False)
    skills_content_json = json.dumps(skills_content, ensure_ascii=False)

    # Sort daily counts for chart
    sorted_days = sorted(daily.get('daily_counts', {}).items()) or sorted(daily.items()) if isinstance(daily, dict) else []
    # Support both old format (flat dict) and new format with interactive split
    daily_all = data.get('daily_counts', {})
    daily_int = data.get('daily_interactive', {})
    all_days = sorted(set(list(daily_all.keys()) + list(daily_int.keys())))
    chart_labels   = json.dumps(all_days)
    chart_data_all = json.dumps([daily_all.get(d, 0) for d in all_days])
    chart_data_int = json.dumps([daily_int.get(d, 0) for d in all_days])

    # Top 10 projects by interactive sessions
    top_projects_int = sorted(projects, key=lambda p: -p.get('interactive_count', p.get('session_count', 0)))[:10]
    proj_labels = json.dumps([p['label'] for p in top_projects_int])
    proj_counts = json.dumps([p.get('interactive_count', p.get('session_count', 0)) for p in top_projects_int])

    data_json = json.dumps(data, indent=2, ensure_ascii=False)

    # CG-F: Load graph.json if available for the D3 pane
    graph_json = "null"
    graph_path = dash_dir / "graph.json"
    if graph_path.exists():
        try:
            graph_json = graph_path.read_text(encoding="utf-8")
            utils.verbose(f"Loaded graph.json ({graph_path.stat().st_size // 1024}KB) for D3 pane")
        except Exception:
            pass

    _nav_html = hub_nav_html("ai-usage", [
        {"num": f"{summary.get('total_interactive', 0):,}", "label": "my sessions",   "title": "Interactive (human-initiated) Claude sessions"},
        {"num": str(summary.get("total_projects", 0)),      "label": "projects",      "title": "Distinct project directories with sessions"},
        {"num": str(summary.get("last_30_days_interactive", 0)), "label": "last 30d", "title": "Interactive sessions in the last 30 days"},
        {"num": str(summary.get("total_skills", 0)),        "label": "skills",        "title": "Skills found across plugin repositories"},
    ])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AI Usage Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/loader.js"></script>
<style>
  :root {{
    --bg: #0f0f0f; --surface: #1a1a1a; --border: #2a2a2a;
    --accent: #d97757; --accent2: #c4622d; --text: #ececec;
    --muted: #6b6b6b; --purple: #8b5cf6; --green: #3fb950;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 13px; background: var(--bg); color: var(--text); }}

{ORG_CSS}
  #header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 8px 20px; display: flex; align-items: center; gap: 12px; }}
  #header h1 {{ font-size: 14px; font-weight: 700; color: var(--accent); }}
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

  /* Graph sidebar */
  #graph-body {{ display: flex; gap: 0; height: calc(100vh - 190px); }}
  #graph-svg-wrap {{ flex: 1; min-width: 0; background: var(--surface); border: 1px solid var(--border); border-radius: 8px 0 0 8px; overflow: hidden; position: relative; }}
  #graph-sidebar {{ width: 0; overflow: hidden; transition: width 0.2s; background: var(--surface); border: 1px solid var(--border); border-left: none; border-radius: 0 8px 8px 0; display: flex; flex-direction: column; }}
  #graph-sidebar.open {{ width: 280px; }}
  #gs-header {{ display: flex; align-items: center; padding: 10px 14px; border-bottom: 1px solid var(--border); gap: 8px; flex-shrink: 0; }}
  #gs-type-badge {{ font-size: 10px; padding: 2px 7px; border-radius: 10px; font-weight: 600; }}
  #gs-close {{ margin-left: auto; cursor: pointer; color: var(--muted); font-size: 16px; line-height: 1; background: none; border: none; padding: 0; }}
  #gs-body {{ padding: 12px 14px; overflow-y: auto; flex: 1; font-size: 12px; }}
  .gs-row {{ display: flex; gap: 6px; margin-bottom: 5px; }}
  .gs-key {{ color: var(--muted); min-width: 70px; flex-shrink: 0; }}
  .gs-val {{ color: var(--text); word-break: break-all; }}
  .gs-section {{ font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin: 10px 0 5px; padding-bottom: 3px; border-bottom: 1px solid var(--border); }}
  .gs-edge {{ padding: 3px 0; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .gs-edge strong {{ color: var(--text); font-weight: 500; }}
  #gs-xcb {{ display: block; margin-top: 12px; padding: 7px 12px; background: #1f2d4a; border: 1px solid #58a6ff44; border-radius: 6px; color: #58a6ff; font-size: 12px; text-decoration: none; text-align: center; }}
  #gs-xcb:hover {{ background: #253a5e; }}

  /* Graph toolbar extras */
  .graph-sep {{ width: 1px; height: 18px; background: var(--border); margin: 0 4px; }}
  #gdate-from, #gdate-to {{ background: #1a1a1a; border: 1px solid var(--border); border-radius: 5px; padding: 3px 7px; color: var(--text); font-size: 11px; width: 120px; }}
  #gdate-from:focus, #gdate-to:focus {{ outline: none; border-color: var(--accent); }}

  /* View toggle */
  .view-btn {{ background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 5px 12px; font-size: 12px; color: var(--muted); cursor: pointer; }}
  .view-btn.active {{ background: #1a1a2a; border-color: var(--accent); color: var(--accent); }}

  /* Automated badge */
  .auto-badge {{ display: inline-block; font-size: 10px; background: #2a1a1a; color: #f85149; border-radius: 3px; padding: 1px 5px; margin-left: 4px; }}
</style>
</head>
<body>
{_nav_html}
<div id="header">
  <h1>🤖 AI Usage</h1>
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
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
      <span style="font-size:12px;color:var(--muted)">View:</span>
      <button class="view-btn active" id="btn-interactive" onclick="setView('interactive')">👤 My sessions ({summary.get('total_interactive', 0):,})</button>
      <button class="view-btn" id="btn-all" onclick="setView('all')">All incl. automated ({summary.get('total_sessions', 0):,})</button>
    </div>
    <div class="tile-grid" id="tiles-interactive">
      <div class="tile"><div class="num">{summary.get('total_interactive', 0):,}</div><div class="lbl">My Sessions (interactive)</div></div>
      <div class="tile"><div class="num">{summary.get('last_30_days_interactive', 0)}</div><div class="lbl">Last 30 Days</div></div>
      <div class="tile"><div class="num">{summary.get('total_projects', 0)}</div><div class="lbl">Projects</div></div>
      <div class="tile"><div class="num" style="font-size:14px;padding-top:6px">{summary.get('top_project', '—')}</div><div class="lbl">Top Project</div></div>
    </div>
    <div class="tile-grid" id="tiles-all" style="display:none">
      <div class="tile"><div class="num">{summary.get('total_sessions', 0):,}</div><div class="lbl">All Sessions</div></div>
      <div class="tile"><div class="num">{summary.get('total_interactive', 0):,}</div><div class="lbl">Interactive</div></div>
      <div class="tile"><div class="num">{summary.get('total_automated', 0):,}</div><div class="lbl">Automated</div></div>
      <div class="tile"><div class="num">{summary.get('last_30_days', 0)}</div><div class="lbl">Last 30 Days (all)</div></div>
    </div>
    <div class="chart-row">
      <div class="chart-box">
        <h3 id="daily-chart-title">My sessions per day — last 90 days</h3>
        <canvas id="chart-daily" height="120"></canvas>
      </div>
      <div class="chart-box">
        <h3>Top 10 projects (interactive sessions)</h3>
        <canvas id="chart-projects" height="120"></canvas>
      </div>
    </div>
  </div>

  <div class="pane" id="pane-projects">
    <div style="margin-bottom:12px;display:flex;gap:8px">
      <input id="proj-search" style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:6px;padding:5px 10px;color:#ececec;font-size:13px;width:200px" placeholder="Filter projects…" oninput="renderProjects()">
    </div>
    <table class="proj-table">
      <thead><tr><th>Project</th><th>Domain</th><th>Interactive</th><th>Automated</th><th>Last 30d (me)</th><th>First</th><th>Last</th></tr></thead>
      <tbody id="proj-body"></tbody>
    </table>
  </div>

  <div class="pane" id="pane-skills">
    <div style="display:flex;gap:0;height:calc(100vh - 130px)">
      <!-- Left: skill card list -->
      <div style="width:260px;flex-shrink:0;background:var(--surface);border:1px solid var(--border);border-radius:8px;overflow:hidden;display:flex;flex-direction:column">
        <div style="padding:10px 12px;border-bottom:1px solid var(--border)">
          <input id="skill-search" style="width:100%;background:#111;border:1px solid var(--border);border-radius:5px;padding:5px 8px;color:var(--text);font-size:12px" placeholder="Filter skills…" oninput="renderSkillCards()">
          <div style="font-size:11px;color:var(--muted);margin-top:6px" id="skill-count"></div>
        </div>
        <div id="skill-cards" style="overflow-y:auto;flex:1"></div>
      </div>
      <!-- Right: Monaco editor -->
      <div style="flex:1;display:flex;flex-direction:column;margin-left:16px">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-shrink:0">
          <span id="skill-editor-title" style="font-size:13px;color:var(--muted)">Select a skill →</span>
          <button id="btn-copy-prompt" onclick="copyPrompt()" style="margin-left:auto;background:var(--accent);border:none;border-radius:5px;padding:5px 14px;color:#fff;font-size:12px;cursor:pointer;display:none">Copy as prompt</button>
        </div>
        <div id="monaco-container" style="flex:1;border:1px solid var(--border);border-radius:8px;overflow:hidden"></div>
      </div>
    </div>
  </div>

  <div class="pane" id="pane-graph">
    <div style="display:flex;align-items:center;gap:7px;margin-bottom:10px;flex-wrap:wrap">
      <span style="font-size:12px;color:var(--muted)">Nodes:</span>
      <button class="view-btn active" id="gn-session" onclick="toggleGNode('session',this)">Sessions</button>
      <button class="view-btn active" id="gn-plan"    onclick="toggleGNode('plan',this)">Plans</button>
      <button class="view-btn active" id="gn-repo"    onclick="toggleGNode('repo',this)">Repos</button>
      <button class="view-btn active" id="gn-skill"   onclick="toggleGNode('skill',this)">Skills</button>
      <button class="view-btn active" id="gn-usecase" onclick="toggleGNode('usecase',this)">Use Cases</button>
      <button class="view-btn"        id="gn-app"     onclick="toggleGNode('app',this)" title="App nodes from plan titles (requires graph-extract)">Apps</button>
      <div class="graph-sep"></div>
      <span style="font-size:11px;color:var(--muted)">From:</span>
      <input type="date" id="gdate-from" oninput="initGraph()" title="Filter sessions from this date">
      <span style="font-size:11px;color:var(--muted)">To:</span>
      <input type="date" id="gdate-to" oninput="initGraph()" title="Filter sessions up to this date">
      <span style="margin-left:auto;font-size:11px;color:var(--muted)" id="graph-stats"></span>
    </div>
    <div id="graph-body">
      <div id="graph-svg-wrap">
        <svg id="graph-svg" style="width:100%;height:100%"></svg>
        <div id="graph-tooltip" style="display:none;position:absolute;background:#1a1a1a;border:1px solid var(--border);border-radius:6px;padding:10px 14px;font-size:12px;max-width:280px;pointer-events:none;z-index:10"></div>
      </div>
      <div id="graph-sidebar">
        <div id="gs-header">
          <span id="gs-label" style="font-weight:600;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px"></span>
          <span id="gs-type-badge"></span>
          <button id="gs-close" onclick="closeSidebar()" title="Close">✕</button>
        </div>
        <div id="gs-body"></div>
      </div>
    </div>
  </div>

</div>

<script>
const DATA = {data_json};
const GRAPH_DATA = {graph_json};

let graphInitialized = false;

function showTab(tab) {{
  const names = ['stats','projects','skills','graph'];
  document.querySelectorAll('.tab').forEach((el, i) => el.classList.toggle('active', names[i] === tab));
  document.querySelectorAll('.pane').forEach(el => el.classList.remove('active'));
  document.getElementById('pane-' + tab).classList.add('active');
  if (tab === 'skills' && !document.getElementById('skill-count').textContent) renderSkillCards();
  if (tab === 'graph' && !graphInitialized) {{ graphInitialized = true; setTimeout(initGraph, 50); }}
}}

function esc(s) {{ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }}

const domainClass = {{ServiceNow:'d-sn', Personal:'d-personal', EarlBear:'d-earlbear', Other:'d-other'}};

let currentView = 'interactive';

function setView(v) {{
  currentView = v;
  document.getElementById('btn-interactive').classList.toggle('active', v === 'interactive');
  document.getElementById('btn-all').classList.toggle('active', v === 'all');
  document.getElementById('tiles-interactive').style.display = v === 'interactive' ? '' : 'none';
  document.getElementById('tiles-all').style.display = v === 'all' ? '' : 'none';
  document.getElementById('daily-chart-title').textContent =
    v === 'interactive' ? 'My sessions per day — last 90 days' : 'All sessions per day — last 90 days';
  // Update chart dataset
  dailyChart.data.datasets[0].data = v === 'interactive' ? CHART_INT : CHART_ALL;
  dailyChart.update();
}}

{ORG_JS}

function rerender() {{ renderProjects(); if (graphInitialized) initGraph(); }}

function renderProjects() {{
  const q = (document.getElementById('proj-search').value||'').toLowerCase();
  const rows = DATA.projects.filter(p =>
    matchesDomain(p.domain) &&
    (!q || p.label.toLowerCase().includes(q) || p.domain.toLowerCase().includes(q))
  );
  document.getElementById('proj-body').innerHTML = rows.map(p => {{
    const interactive = p.interactive_count ?? p.session_count;
    const automated = p.automated_count ?? 0;
    return `<tr>
      <td style="font-weight:600">${{esc(p.label)}}</td>
      <td><span class="domain-badge ${{domainClass[p.domain]||'d-other'}}">${{esc(p.domain)}}</span></td>
      <td style="color:var(--accent)">${{interactive}}</td>
      <td style="color:var(--muted)">${{automated > 0 ? automated + ' <span class=\\"auto-badge\\">auto</span>' : '—'}}</td>
      <td style="color:var(--green)">${{p.last_30_days_interactive ?? p.last_30_days}}</td>
      <td style="color:var(--muted)">${{esc(p.first_date||'')}}</td>
      <td style="color:var(--muted)">${{esc(p.last_date||'')}}</td>
    </tr>`;
  }}).join('');
}}

const CHART_ALL = {chart_data_all};
const CHART_INT = {chart_data_int};
let dailyChart;

window.addEventListener('DOMContentLoaded', () => {{
  _applyOrg();
  renderProjects();

  // Daily sessions chart — default to interactive
  dailyChart = new Chart(document.getElementById('chart-daily'), {{
    type: 'bar',
    data: {{
      labels: {chart_labels},
      datasets: [{{ data: CHART_INT, backgroundColor: '#d97757', borderRadius: 2 }}]
    }},
    options: {{
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#6b6b6b', maxTicksLimit: 10 }}, grid: {{ color: '#1f1f1f' }} }},
        y: {{ ticks: {{ color: '#6b6b6b' }}, grid: {{ color: '#1f1f1f' }} }}
      }}
    }}
  }});

  // Top projects chart (interactive only)
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

// ── Prompt Library (AUD-E) ────────────────────────────────────────────────
const SKILLS_META = {skills_meta_json};
const SKILLS_CONTENT = {skills_content_json};
let monacoEditor = null;
let monacoReady = false;
let pendingContent = null;

require.config({{ paths: {{ vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' }} }});
require(['vs/editor/editor.main'], function() {{
  monacoReady = true;
  monacoEditor = monaco.editor.create(document.getElementById('monaco-container'), {{
    value: '',
    language: 'markdown',
    theme: 'vs-dark',
    readOnly: false,
    automaticLayout: true,
    fontSize: 13,
    lineNumbers: 'on',
    minimap: {{ enabled: false }},
    wordWrap: 'on',
    scrollBeyondLastLine: false,
    padding: {{ top: 12, bottom: 12 }},
  }});
  if (pendingContent !== null) {{
    monacoEditor.setValue(pendingContent);
    pendingContent = null;
  }}
}});

function renderSkillCards() {{
  const q = (document.getElementById('skill-search').value || '').toLowerCase();
  const filtered = SKILLS_META.filter(s =>
    !q || s.name.toLowerCase().includes(q) || (s.group || '').toLowerCase().includes(q) ||
    (s.description || '').toLowerCase().includes(q)
  );
  document.getElementById('skill-count').textContent = filtered.length + ' skills';
  const groups = {{}};
  filtered.forEach(s => {{
    const g = s.group || s.name;
    groups[g] = groups[g] || [];
    groups[g].push(s);
  }});
  document.getElementById('skill-cards').innerHTML = Object.entries(groups).map(([group, skills]) => `
    <div style="padding:6px 10px 2px;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;border-top:1px solid var(--border)">${{esc(group)}}</div>
    ${{skills.map(s => `
      <div class="skill-card" data-path="${{esc(s.path)}}" onclick="openSkill(this)" style="padding:8px 12px;cursor:pointer;border-bottom:1px solid #1a1a1a">
        <div style="font-size:12px;font-weight:600;color:var(--text)">${{esc(s.name)}}${{s.is_subskill ? ' <span style=\\"color:var(--muted);font-weight:400\\">↳</span>' : ''}}</div>
        ${{s.description ? `<div style="font-size:11px;color:var(--muted);margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${{esc(s.description.slice(0,80))}}</div>` : ''}}
      </div>`).join('')}}
  `).join('');
}}

function openSkill(el) {{
  document.querySelectorAll('.skill-card').forEach(c => c.style.background = '');
  el.style.background = '#1a1a2a';
  const path = el.dataset.path;
  const content = SKILLS_CONTENT[path] || '# Not found';
  const meta = SKILLS_META.find(s => s.path === path) || {{}};
  document.getElementById('skill-editor-title').textContent = meta.name || path;
  document.getElementById('btn-copy-prompt').style.display = '';
  if (monacoReady && monacoEditor) {{
    monacoEditor.setValue(content);
    monacoEditor.setScrollPosition({{ scrollTop: 0 }});
  }} else {{
    pendingContent = content;
  }}
}}

function copyPrompt() {{
  const content = monacoEditor ? monacoEditor.getValue() : '';
  if (!content) return;
  navigator.clipboard.writeText(content).then(() => {{
    const btn = document.getElementById('btn-copy-prompt');
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy as prompt', 1500);
  }});
}}

// ── Prompt Graph (CG-F) ─────────────────────────────────────────────────
const UC_COLORS = {{
  'Code Gen':'#3fb950','Debug':'#f85149','Planning':'#d2a8ff','Research':'#79c0ff',
  'Docs':'#d29922','Review':'#58a6ff','Refactor':'#d97757','General':'#484f58'
}};
const DOMAIN_COLORS = {{'ServiceNow':'#1f6feb','Personal':'#8b5cf6','EarlBear':'#3fb950','Other':'#484f58'}};
const STATUS_COLORS = {{'active':'#3fb950','paused':'#d29922','done':'#484f58','backlog':'#79c0ff'}};
const REL_STROKE = {{
  'TOUCHES':'#2d3748','CLASSIFIED_AS':'#1e3a5f','IN_REPO':'#1a3a28',
  'DEFINED_IN':'#3a2a10','BUILT':'#1a3a3a'
}};

let activeGNodes = new Set(['session','plan','repo','skill','usecase']);

function toggleGNode(type, btn) {{
  if (activeGNodes.has(type)) {{ activeGNodes.delete(type); btn.classList.remove('active'); }}
  else {{ activeGNodes.add(type); btn.classList.add('active'); }}
  initGraph();
}}

// ── Graph sidebar ─────────────────────────────────────────────────────────
const TYPE_BADGE_COLORS = {{
  session:'#2d3748',plan:'#1f3a2a',repo:'#1f2d4a',
  skill:'#3a2010',usecase:'#2a1a3a',app:'#0a3a3a'
}};
const TYPE_BADGE_TEXT = {{
  session:'#8b949e',plan:'#3fb950',repo:'#58a6ff',
  skill:'#d97757',usecase:'#d2a8ff',app:'#2dd4bf'
}};

function showNodeSidebar(d) {{
  const sidebar = document.getElementById('graph-sidebar');
  sidebar.classList.add('open');
  document.getElementById('gs-label').textContent = d.label;
  const badge = document.getElementById('gs-type-badge');
  badge.textContent = d.type;
  badge.style.background = TYPE_BADGE_COLORS[d.type] || '#2d3748';
  badge.style.color = TYPE_BADGE_TEXT[d.type] || '#8b949e';

  const attrs = d.attrs || {{}};
  const rows = Object.entries(attrs)
    .filter(([k,v]) => v !== null && v !== undefined && v !== '')
    .map(([k,v]) => `<div class="gs-row"><span class="gs-key">${{esc(k)}}</span><span class="gs-val">${{esc(String(v))}}</span></div>`)
    .join('');

  // Top-5 edges from GRAPH_DATA
  let edgesHtml = '';
  if (GRAPH_DATA && GRAPH_DATA.edges) {{
    const nodeMap = new Map((GRAPH_DATA.nodes||[]).map(n=>[n.id,n]));
    const connected = GRAPH_DATA.edges
      .filter(e => e.source === d.id || e.target === d.id)
      .slice(0, 5)
      .map(e => {{
        const otherId = e.source === d.id ? e.target : e.source;
        const dir     = e.source === d.id ? '→' : '←';
        const other   = nodeMap.get(otherId);
        const lbl     = other ? other.label : otherId;
        return `<div class="gs-edge">${{esc(dir)}} <strong>${{esc(e.rel)}}</strong> ${{esc(lbl.length>36?lbl.slice(0,36)+'…':lbl)}}</div>`;
      }}).join('');
    if (connected) edgesHtml = `<div class="gs-section">Edges</div>${{connected}}`;
  }}

  // xcallback for Plan nodes
  let xcbHtml = '';
  if (d.type === 'plan') {{
    const encoded = encodeURIComponent(d.label);
    xcbHtml = `<a id="gs-xcb" href="noteplan://x-callback-url/openNote?noteTitle=${{encoded}}" title="Open in NotePlan">↗ Open in NotePlan</a>`;
  }}

  document.getElementById('gs-body').innerHTML =
    `${{rows}}${{edgesHtml}}${{xcbHtml}}`;
}}

function closeSidebar() {{
  document.getElementById('graph-sidebar').classList.remove('open');
}}

// Close sidebar on SVG background click
document.addEventListener('click', e => {{
  if (!document.getElementById('graph-sidebar').contains(e.target) &&
      !document.getElementById('graph-svg-wrap').contains(e.target)) {{
    closeSidebar();
  }}
}});

function initGraph() {{
  if (GRAPH_DATA && GRAPH_DATA.nodes && GRAPH_DATA.nodes.length > 0) {{
    initGraphFromData();
  }} else {{
    initGraphFallback();
  }}
}}

function initGraphFromData() {{
  const wrap = document.getElementById('graph-svg-wrap');
  const W = wrap.clientWidth || 900, H = wrap.clientHeight || 600;
  const svg = d3.select('#graph-svg').attr('viewBox', `0 0 ${{W}} ${{H}}`);
  svg.selectAll('*').remove();

  const CAPS = {{'session':100,'plan':50,'repo':30,'skill':15,'usecase':8,'app':20}};

  // Score plans by TOUCHES in-degree for prioritization
  const touchCounts = {{}};
  GRAPH_DATA.edges.filter(e=>e.rel==='TOUCHES').forEach(e => {{
    touchCounts[e.target] = (touchCounts[e.target]||0) + 1;
  }});

  // Group nodes by type and select with caps
  const typeGroups = {{}};
  GRAPH_DATA.nodes.forEach(n => {{
    const t = n.type.toLowerCase();
    if (!activeGNodes.has(t)) return;
    if (!typeGroups[t]) typeGroups[t] = [];
    typeGroups[t].push(n);
  }});

  const gDateFrom = (document.getElementById('gdate-from')||{{}}).value || '';
  const gDateTo   = (document.getElementById('gdate-to')||{{}}).value   || '';

  const selectedIds = new Set();
  for (const [t, gnodes] of Object.entries(typeGroups)) {{
    let sorted = gnodes;
    if (t === 'session') {{
      sorted = gnodes.filter(n => {{
        if (n.attrs.automated) return false;
        const d = n.attrs.date || '';
        if (gDateFrom && d < gDateFrom) return false;
        if (gDateTo   && d > gDateTo)   return false;
        return true;
      }}).slice(-CAPS[t]);
    }} else if (t === 'plan') {{
      sorted = [...gnodes]
        .filter(n => matchesDomain((n.attrs.domain||'').toLowerCase()))
        .sort((a,b)=>(touchCounts[b.id]||0)-(touchCounts[a.id]||0))
        .slice(0, CAPS[t]);
    }} else if (t === 'repo') {{
      sorted = gnodes
        .filter(n => matchesDomain((n.attrs.domain||'').toLowerCase()))
        .slice(0, CAPS[t] ?? gnodes.length);
    }} else {{
      sorted = gnodes.slice(0, CAPS[t] ?? gnodes.length);
    }}
    sorted.forEach(n => selectedIds.add(n.id));
  }}

  const nodes = GRAPH_DATA.nodes.filter(n => selectedIds.has(n.id)).map(n => {{
    const t = n.type.toLowerCase();
    let color = '#484f58';
    if (t === 'session')  color = UC_COLORS[n.attrs.use_case] || '#484f58';
    else if (t === 'plan') color = STATUS_COLORS[n.attrs.status] || '#58a6ff';
    else if (t === 'repo') color = DOMAIN_COLORS[n.attrs.domain] || '#484f58';
    else if (t === 'skill') color = '#d97757';
    else if (t === 'usecase') color = UC_COLORS[n.label] || '#484f58';
    else if (t === 'app') color = '#2dd4bf';
    return {{...n, type: t, color}};
  }});

  const links = GRAPH_DATA.edges
    .filter(e => selectedIds.has(e.source) && selectedIds.has(e.target));

  document.getElementById('graph-stats').textContent = `${{nodes.length}} nodes · ${{links.length}} edges (from graph.json)`;

  const g = svg.append('g');
  svg.call(d3.zoom().scaleExtent([0.1,4]).on('zoom', e => g.attr('transform', e.transform)));

  const nodeMap = new Map(nodes.map(n => [n.id, n]));
  const validLinks = links
    .filter(l => nodeMap.has(l.source) && nodeMap.has(l.target))
    .map(l => ({{...l, source: nodeMap.get(l.source), target: nodeMap.get(l.target)}}));

  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(validLinks).id(d=>d.id)
      .distance(d => {{ const r=d.rel; return r==='CLASSIFIED_AS'?55:r==='TOUCHES'?80:r==='IN_REPO'?90:110; }})
      .strength(0.25))
    .force('charge', d3.forceManyBody().strength(d => d.type==='usecase'?-200:-70))
    .force('center', d3.forceCenter(W/2, H/2))
    .force('collide', d3.forceCollide(d => d.type==='usecase'?30:14));

  const link = g.append('g').selectAll('line').data(validLinks).join('line')
    .attr('stroke', d => REL_STROKE[d.rel] || '#2d3748')
    .attr('stroke-width', d => d.rel==='IN_REPO'?1.5:d.rel==='TOUCHES'?0.8:0.6)
    .attr('stroke-opacity', 0.75)
    .attr('stroke-dasharray', d => d.rel==='DEFINED_IN'?'3,2':d.rel==='BUILT'?'2,3':null);

  const node = g.append('g').selectAll('g').data(nodes).join('g')
    .style('cursor','pointer')
    .call(d3.drag()
      .on('start',(e,d) => {{ if(!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; }})
      .on('drag', (e,d) => {{ d.fx=e.x; d.fy=e.y; }})
      .on('end',  (e,d) => {{ if(!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }}));

  node.each(function(d) {{
    const sel = d3.select(this);
    if (d.type === 'session') {{
      sel.append('circle').attr('r',5).attr('fill',d.color).attr('opacity',0.75);
    }} else if (d.type === 'plan') {{
      sel.append('rect').attr('x',-7).attr('y',-7).attr('width',14).attr('height',14)
         .attr('rx',2).attr('fill',d.color).attr('opacity',0.85);
    }} else if (d.type === 'repo') {{
      sel.append('rect').attr('x',-10).attr('y',-10).attr('width',20).attr('height',20)
         .attr('rx',3).attr('fill',d.color).attr('opacity',0.9);
    }} else if (d.type === 'skill') {{
      sel.append('polygon').attr('points','0,-11 9.5,5.5 -9.5,5.5').attr('fill',d.color).attr('opacity',0.9);
    }} else if (d.type === 'usecase') {{
      sel.append('circle').attr('r',20).attr('fill',d.color).attr('opacity',0.15)
         .attr('stroke',d.color).attr('stroke-width',1.5);
      sel.append('text').text(d.label).attr('text-anchor','middle').attr('dy','0.35em')
         .attr('font-size',10).attr('fill',d.color);
    }} else if (d.type === 'app') {{
      sel.append('polygon').attr('points','0,-9 6,9 -6,9').attr('fill',d.color).attr('opacity',0.85);
    }}
  }});

  const tip = document.getElementById('graph-tooltip');
  node.on('mouseover', function(e,d) {{
    const a = d.attrs || {{}};
    let html = `<strong>${{esc(d.label)}}</strong><br><span style="color:var(--muted)">${{d.type}}</span>`;
    if (a.use_case) html += `<br>Use case: ${{esc(a.use_case)}}`;
    if (a.date) html += `<br>${{esc(a.date)}}`;
    if (a.project) html += `<br>${{esc(a.project)}}`;
    if (a.status) html += `<br>Status: ${{esc(a.status)}}`;
    if (a.domain) html += `<br>Domain: ${{esc(a.domain)}}`;
    if (a.commit_count) html += `<br>${{a.commit_count}} commits`;
    tip.innerHTML = html;
    tip.style.display = 'block';
    tip.style.left = (e.offsetX+14)+'px';
    tip.style.top  = (e.offsetY-10)+'px';
  }}).on('mousemove', function(e) {{
    tip.style.left = (e.offsetX+14)+'px'; tip.style.top = (e.offsetY-10)+'px';
  }}).on('mouseout', () => {{ tip.style.display = 'none'; }});

  node.on('click', (e,d) => {{ e.stopPropagation(); showNodeSidebar(d); }});

  sim.on('tick', () => {{
    link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
        .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
    node.attr('transform', d=>`translate(${{d.x}},${{d.y}})`);
  }});
}}

function initGraphFallback() {{
  // Fallback when graph.json is not available: build from DATA.sessions/projects
  const wrap = document.getElementById('graph-svg-wrap');
  const W = wrap.clientWidth || 900, H = wrap.clientHeight || 600;
  const svg = d3.select('#graph-svg').attr('viewBox', `0 0 ${{W}} ${{H}}`);
  svg.selectAll('*').remove();

  const nodes = [], links = [];
  const nodeById = {{}};

  const useCases = [...new Set(DATA.sessions.filter(s=>!s.automated&&s.use_case).map(s=>s.use_case))];
  if (activeGNodes.has('usecase')) {{
    useCases.forEach(uc => {{
      const n = {{id:'uc_'+uc,type:'usecase',label:uc,color:UC_COLORS[uc]||'#484f58',r:18}};
      nodes.push(n); nodeById[n.id] = n;
    }});
  }}

  const topRepos = DATA.projects.filter(p=>p.interactive_count>0).slice(0,15);
  if (activeGNodes.has('repo')) {{
    topRepos.forEach(p => {{
      const n = {{id:'repo_'+p.label,type:'repo',label:p.label,color:DOMAIN_COLORS[p.domain]||'#484f58',count:p.interactive_count}};
      nodes.push(n); nodeById[n.id] = n;
    }});
  }}

  if (activeGNodes.has('skill')) {{
    SKILLS_META.filter(s=>!s.is_subskill).slice(0,12).forEach(s => {{
      const n = {{id:'skill_'+s.name,type:'skill',label:s.name,color:'#d97757'}};
      nodes.push(n); nodeById[n.id] = n;
    }});
    const npmId = 'repo_oeid-claude-plugin-marketplace';
    if (nodeById[npmId]) SKILLS_META.filter(s=>!s.is_subskill).slice(0,12).forEach(s =>
      links.push({{source:'skill_'+s.name,target:npmId,rel:'DEFINED_IN'}}));
  }}

  const interactiveSessions = DATA.sessions.filter(s=>!s.automated).slice(-80);
  if (activeGNodes.has('session')) {{
    interactiveSessions.forEach(s => {{
      const n = {{id:'s_'+s.session_id,type:'session',label:s.use_case||'Session',
                  color:UC_COLORS[s.use_case]||'#484f58',attrs:{{date:s.date,project:s.project_label||'',use_case:s.use_case}}}};
      nodes.push(n); nodeById[n.id] = n;
      if (s.use_case && activeGNodes.has('usecase') && nodeById['uc_'+s.use_case])
        links.push({{source:'s_'+s.session_id,target:'uc_'+s.use_case,rel:'CLASSIFIED_AS'}});
      if (activeGNodes.has('repo') && s.project_label && nodeById['repo_'+s.project_label])
        links.push({{source:'s_'+s.session_id,target:'repo_'+s.project_label,rel:'IN_REPO'}});
    }});
  }}

  document.getElementById('graph-stats').textContent = `${{nodes.length}} nodes · ${{links.length}} edges (run graph-extract for full graph)`;

  const g = svg.append('g');
  svg.call(d3.zoom().scaleExtent([0.1,4]).on('zoom', e => g.attr('transform', e.transform)));

  const nodeMap = new Map(nodes.map(n => [n.id, n]));
  const validLinks = links.filter(l => nodeMap.has(l.source) && nodeMap.has(l.target))
    .map(l => ({{...l,source:nodeMap.get(l.source),target:nodeMap.get(l.target)}}));

  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(validLinks).id(d=>d.id).distance(60).strength(0.3))
    .force('charge', d3.forceManyBody().strength(-100))
    .force('center', d3.forceCenter(W/2, H/2))
    .force('collide', d3.forceCollide(18));

  const link = g.append('g').selectAll('line').data(validLinks).join('line')
    .attr('stroke', d => REL_STROKE[d.rel]||'#2d3748')
    .attr('stroke-width', d => d.rel==='IN_REPO'?1.5:0.8)
    .attr('stroke-opacity', 0.6);

  const node = g.append('g').selectAll('g').data(nodes).join('g')
    .style('cursor','pointer')
    .call(d3.drag()
      .on('start',(e,d)=>{{ if(!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; }})
      .on('drag', (e,d)=>{{ d.fx=e.x; d.fy=e.y; }})
      .on('end',  (e,d)=>{{ if(!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }}));

  node.each(function(d) {{
    const sel = d3.select(this);
    if (d.type==='session')      sel.append('circle').attr('r',5).attr('fill',d.color).attr('opacity',0.8);
    else if (d.type==='repo')    sel.append('rect').attr('x',-10).attr('y',-10).attr('width',20).attr('height',20).attr('rx',3).attr('fill',d.color).attr('opacity',0.9);
    else if (d.type==='skill')   sel.append('polygon').attr('points','0,-12 10,6 -10,6').attr('fill',d.color).attr('opacity',0.9);
    else if (d.type==='usecase') {{
      sel.append('circle').attr('r',d.r||18).attr('fill',d.color).attr('opacity',0.25).attr('stroke',d.color).attr('stroke-width',1.5);
      sel.append('text').text(d.label).attr('text-anchor','middle').attr('dy','0.35em').attr('font-size',10).attr('fill',d.color);
    }}
  }});

  const tip = document.getElementById('graph-tooltip');
  node.on('mouseover', function(e,d) {{
    const a = d.attrs || {{}};
    let html = `<strong>${{esc(d.label)}}</strong><br><span style="color:var(--muted)">${{d.type}}</span>`;
    if (a.use_case) html += `<br>${{esc(a.use_case)}}`;
    if (a.date) html += `<br>${{esc(a.date)}}`;
    if (a.project) html += `<br>${{esc(a.project)}}`;
    tip.innerHTML = html;
    tip.style.display = 'block';
    tip.style.left = (e.offsetX+14)+'px'; tip.style.top = (e.offsetY-10)+'px';
  }}).on('mousemove', function(e) {{
    tip.style.left = (e.offsetX+14)+'px'; tip.style.top = (e.offsetY-10)+'px';
  }}).on('mouseout', ()=>{{ tip.style.display='none'; }});

  node.on('click', (e,d) => {{ e.stopPropagation(); showNodeSidebar(d); }});

  sim.on('tick', () => {{
    link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
        .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
    node.attr('transform', d=>`translate(${{d.x}},${{d.y}})`);
  }});
}}
</script>
</body>
</html>"""

    out = dash_dir / 'ai-usage.html'
    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would write {out}")
        return
    out.write_text(html, encoding='utf-8')
    utils.log(f"ai-usage-generate: wrote {out}")

    # Write summary sidecar for insights.html live tiles
    summary_out = dash_dir / 'ai-usage-summary.json'
    summary_out.write_text(json.dumps({
        "generated_at": generated_at,
        "total_sessions": summary.get("total_sessions", 0),
        "interactive_sessions": summary.get("total_interactive", 0),
        "last_30_days": summary.get("last_30_days_interactive", 0),
        "total_projects": summary.get("total_projects", 0),
        "top_project": summary.get("top_project", ""),
        "total_skills": summary.get("total_skills", 0),
    }, indent=2, ensure_ascii=False), encoding='utf-8')


def cmd_ai_usage_open(args):
    path = utils.noteplan_root() / 'dashboard' / 'ai-usage.html'
    if not path.exists():
        utils.err("dashboard/ai-usage.html not found. Run ai-usage-generate first.")
        sys.exit(utils.EXIT_NOT_FOUND)
    import subprocess as sp
    sp.run(['open', str(path)])
    utils.log(f"ai-usage-open: opened {path}")


# ---------------------------------------------------------------------------
# Repo AI artifact scanner (AUD-C)
# ---------------------------------------------------------------------------

import subprocess as _sp

_AI_ARTIFACT_FILES = {'SKILL.md', 'AGENT.md', 'AGENTS.md', 'CLAUDE.md'}
_AI_ARTIFACT_DIRS  = {'.claude', 'prompts', 'skills'}
_CLAUDE_CO_AUTHOR_PAT = re.compile(r'co-authored-by:\s*claude', re.IGNORECASE)


def _is_git_repo(path: Path) -> bool:
    return (path / '.git').is_dir()


def _git_count(cwd: Path, extra_args: list[str]) -> int:
    try:
        r = _sp.run(
            ['git', 'log', '--oneline'] + extra_args,
            cwd=str(cwd), capture_output=True, text=True, timeout=15
        )
        return len(r.stdout.strip().splitlines()) if r.returncode == 0 else 0
    except Exception:
        return 0


def _git_total_commits(cwd: Path) -> int:
    try:
        r = _sp.run(
            ['git', 'rev-list', '--count', 'HEAD'],
            cwd=str(cwd), capture_output=True, text=True, timeout=10
        )
        return int(r.stdout.strip()) if r.returncode == 0 else 0
    except Exception:
        return 0


def _scan_repo(repo_path: Path) -> dict | None:
    """Scan a git repo for AI artifact files + Co-Authored-By: Claude commits."""
    if not _is_git_repo(repo_path):
        return None

    artifacts: list[str] = []
    for name in _AI_ARTIFACT_FILES:
        if (repo_path / name).exists():
            artifacts.append(name)
    try:
        for child in repo_path.iterdir():
            if child.is_dir() and child.name in _AI_ARTIFACT_DIRS:
                artifacts.append(child.name + '/')
    except Exception:
        pass

    # Walk one level deeper for nested SKILL.md files
    skill_count = 0
    try:
        for p in repo_path.rglob('SKILL.md'):
            if '.git' not in str(p):
                skill_count += 1
    except Exception:
        pass

    ai_commits = _git_count(repo_path, ['--grep=Co-Authored-By: Claude', '--regexp-ignore-case'])
    total_commits = _git_total_commits(repo_path)

    # Only include repos with any AI signal
    if not artifacts and not skill_count and ai_commits == 0:
        return None

    ai_pct = round(ai_commits / total_commits * 100, 1) if total_commits else 0.0

    return {
        'name': repo_path.name,
        'path': str(repo_path),
        'artifacts': artifacts,
        'skill_count': skill_count,
        'ai_commits': ai_commits,
        'total_commits': total_commits,
        'ai_commit_pct': ai_pct,
        'has_claude_md': 'CLAUDE.md' in artifacts,
        'has_skills': skill_count > 0 or '.claude/' in artifacts,
    }


def cmd_repo_scan(args):
    root = utils.noteplan_root()
    dash_dir = root / 'dashboard'
    dash_dir.mkdir(exist_ok=True)

    workspace_dirs = _workspace_dirs()
    if hasattr(args, 'repos_root') and args.repos_root:
        extra = Path(args.repos_root).expanduser()
        if extra.exists():
            workspace_dirs = [extra] + workspace_dirs

    repos: list[dict] = []
    scanned = 0

    for ws in workspace_dirs:
        utils.log(f"Scanning {ws} ...")
        try:
            for child in sorted(ws.iterdir()):
                if not child.is_dir():
                    continue
                scanned += 1
                result = _scan_repo(child)
                if result:
                    repos.append(result)
        except Exception as e:
            utils.verbose(f"  Error scanning {ws}: {e}")

    repos.sort(key=lambda r: -(r['ai_commits'] + r['skill_count'] * 5))

    total_ai_commits = sum(r['ai_commits'] for r in repos)
    total_commits_all = sum(r['total_commits'] for r in repos)

    audit = {
        'repos': repos,
        'summary': {
            'repos_scanned': scanned,
            'repos_with_ai_signal': len(repos),
            'total_ai_commits': total_ai_commits,
            'total_commits': total_commits_all,
            'ai_commit_pct': round(total_ai_commits / total_commits_all * 100, 1) if total_commits_all else 0.0,
            'repos_with_skills': sum(1 for r in repos if r['has_skills']),
            'repos_with_claude_md': sum(1 for r in repos if r['has_claude_md']),
        },
        'generated_at': datetime.now().isoformat(),
    }

    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would write repo-audit.json ({len(repos)} repos with AI signal)")
        for r in repos[:10]:
            utils.log(f"  {r['name']}: {r['ai_commits']} AI commits, artifacts={r['artifacts']}")
        return

    audit_path = dash_dir / 'repo-audit.json'
    audit_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding='utf-8')
    utils.log(f"repo-scan: wrote {audit_path}")
    utils.log(f"  {len(repos)} repos with AI signal / {scanned} scanned")
    utils.log(f"  {total_ai_commits} AI-assisted commits across {total_commits_all} total")

    # Merge into ai-usage.json if it exists
    usage_path = dash_dir / 'ai-usage.json'
    if usage_path.exists():
        try:
            usage = json.loads(usage_path.read_text(encoding='utf-8'))
            usage['repos'] = audit['repos']
            usage['repo_summary'] = audit['summary']
            usage_path.write_text(json.dumps(usage, indent=2, ensure_ascii=False), encoding='utf-8')
            utils.log(f"  Merged repo audit into ai-usage.json")
        except Exception as e:
            utils.verbose(f"  Could not merge into ai-usage.json: {e}")
