"""
sweep_review.py — Sweep commit + HTML review commands.

Commands:
  sweep-commit             Stage modified .md files and create a structured sweep commit
  sweep-review-generate    Generate immutable snapshot HTML from sweep commit diff
  sweep-review-compile     Merge snapshot + comment rounds → review.html
  sweep-review-squash      Squash all rN comment files for a run into r1
  sweep-review-list        List all runs grouped by date
  sweep-review-open        Open compiled review (or snapshot) in browser
"""

import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import noteplan_sweep.utils as utils


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _git(args: list, cwd: Path, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, timeout=timeout,
        cwd=str(cwd)
    )


def _np_root() -> Path:
    return utils.noteplan_root()


def _sweeps_dir(root: Path) -> Path:
    d = root / "sweeps"
    d.mkdir(exist_ok=True)
    return d


def _run_counter(sweeps: Path, date_str: str) -> int:
    """Return next available run counter NN for the given date."""
    existing = sorted(sweeps.glob(f"{date_str}-*.snapshot.html"))
    if not existing:
        return 1
    last = existing[-1].stem  # e.g. "2026-04-20-03.snapshot"
    m = re.search(r'-(\d+)\.snapshot$', last)
    return int(m.group(1)) + 1 if m else 1


def _latest_run(sweeps: Path, date_str: str | None = None) -> tuple[str | None, int | None]:
    """Return (date_str, run_N) of the most recent snapshot, or (None, None)."""
    pattern = f"{date_str}-*.snapshot.html" if date_str else "*.snapshot.html"
    snapshots = sorted(sweeps.glob(pattern))
    if not snapshots:
        return None, None
    stem = snapshots[-1].stem  # e.g. "2026-04-20-02.snapshot"
    m = re.match(r'(\d{4}-\d{2}-\d{2})-(\d+)\.snapshot', stem)
    if not m:
        return None, None
    return m.group(1), int(m.group(2))


# ---------------------------------------------------------------------------
# sweep-commit
# ---------------------------------------------------------------------------

def cmd_sweep_commit(args):
    root = _np_root()
    r = _git(["status", "--porcelain"], cwd=root)
    if r.returncode != 0:
        utils.err(f"git status failed: {r.stderr.strip()}")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    modified_md = []
    untracked_md = []
    for line in r.stdout.splitlines():
        if len(line) < 4:
            continue
        xy = line[:2]
        path_str = line[3:].strip().strip('"')
        if not path_str.endswith(".md"):
            continue
        if "??" in xy:
            untracked_md.append(path_str)
        else:
            modified_md.append(path_str)

    all_md = modified_md + untracked_md

    if not all_md:
        utils.log("Nothing to commit — working tree is clean.")
        return

    today = date.today().strftime("%Y-%m-%d")

    # Compute stats
    calendar_files = [p for p in all_md if p.startswith("Calendar/")]
    plan_files = [p for p in all_md if "Plans/" in p or "Lists/" in p]
    other_files = [p for p in all_md if p not in calendar_files and p not in plan_files]

    # Count task lines moved (rough heuristic: [x] lines in calendar files)
    task_count = 0
    for rel in calendar_files:
        abs_path = root / rel
        try:
            content = abs_path.read_text(encoding="utf-8")
            task_count += content.count("- [x]")
        except Exception:
            pass

    n_files = len(all_md)
    stats_line = f"{n_files} file{'s' if n_files != 1 else ''} changed"
    if task_count:
        stats_line += f", {task_count} task{'s' if task_count != 1 else ''} completed"

    subject = f"sweep({today}): {stats_line}"

    body_lines = []
    if calendar_files:
        body_lines.append("Sources swept:")
        for p in sorted(calendar_files):
            body_lines.append(f"  {p}")
    if plan_files:
        body_lines.append("Plans/lists touched:")
        for p in sorted(plan_files):
            body_lines.append(f"  {p}")
    if other_files:
        body_lines.append("Other files:")
        for p in sorted(other_files):
            body_lines.append(f"  {p}")

    commit_msg = subject + "\n\n" + "\n".join(body_lines)

    if args.dry_run:
        utils.log(f"[dry-run] Would stage {n_files} .md files and commit:")
        utils.log(f"  {subject}")
        for line in body_lines:
            utils.log(f"  {line}")
        return

    # Stage all modified + untracked .md files
    stage_result = _git(["add", "--"] + all_md, cwd=root)
    if stage_result.returncode != 0:
        utils.err(f"git add failed: {stage_result.stderr.strip()}")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    commit_result = _git(["commit", "-m", commit_msg], cwd=root)
    if commit_result.returncode != 0:
        utils.err(f"git commit failed: {commit_result.stderr.strip()}")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    # Extract commit SHA
    sha_r = _git(["rev-parse", "--short", "HEAD"], cwd=root)
    sha = sha_r.stdout.strip() if sha_r.returncode == 0 else "?"

    utils.log(f"sweep-commit: {sha} — {subject}")


# ---------------------------------------------------------------------------
# sweep-review-generate
# ---------------------------------------------------------------------------

def cmd_sweep_review_generate(args):
    root = _np_root()
    sweeps = _sweeps_dir(root)

    date_str = args.date or date.today().strftime("%Y-%m-%d")

    # Find the sweep commit for this date
    log_r = _git(
        ["log", "--oneline", "--after", f"{date_str} 00:00:00",
         "--before", f"{date_str} 23:59:59", "--grep", f"^sweep({date_str})"],
        cwd=root
    )
    sweep_sha = None
    if log_r.returncode == 0 and log_r.stdout.strip():
        sweep_sha = log_r.stdout.strip().split()[0]

    if not sweep_sha:
        # Fall back to HEAD if it looks like a sweep commit
        head_r = _git(["log", "-1", "--oneline"], cwd=root)
        if head_r.returncode == 0 and f"sweep({date_str})" in head_r.stdout:
            sweep_sha = head_r.stdout.strip().split()[0]

    if not sweep_sha:
        utils.err(f"No sweep commit found for {date_str}. Run sweep-commit first.")
        sys.exit(utils.EXIT_NOT_FOUND)

    run_n = _run_counter(sweeps, date_str)
    run_id = f"{date_str}-{run_n:02d}"

    # Get diff stat + unified diff
    stat_r = _git(["show", "--stat", "--no-patch", sweep_sha], cwd=root)
    stat_text = stat_r.stdout if stat_r.returncode == 0 else ""

    diff_r = _git(["show", "--unified=3", sweep_sha], cwd=root)
    diff_text = diff_r.stdout if diff_r.returncode == 0 else ""

    if not diff_text:
        utils.err(f"Could not get diff for commit {sweep_sha}")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    # Check for existing comments file to carry forward
    existing_comments: list = []
    comments_files = sorted(sweeps.glob(f"{run_id}-r*.comments.jsonl"))
    for cf in comments_files:
        try:
            for line in cf.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    existing_comments.append(json.loads(line))
        except Exception:
            pass

    # Deduplicate: latest entry per anchor wins
    by_anchor: dict = {}
    for entry in existing_comments:
        anchor = entry.get("anchor", "")
        if anchor:
            by_anchor[anchor] = entry
    seed_comments = list(by_anchor.values())

    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would write {sweeps / (run_id + '.snapshot.html')}")
        return

    html = _build_snapshot_html(run_id, date_str, sweep_sha, stat_text, diff_text, seed_comments)
    out_path = sweeps / f"{run_id}.snapshot.html"
    out_path.write_text(html, encoding="utf-8")
    utils.log(f"sweep-review-generate: wrote {out_path}")


def _build_snapshot_html(
    run_id: str, date_str: str, sha: str,
    stat_text: str, diff_text: str,
    seed_comments: list
) -> str:
    seed_json = json.dumps(seed_comments, indent=2)

    # Inline diff2html + Prism.js from CDN URLs would require internet.
    # For full offline support we embed a minimal self-contained diff renderer.
    # The HTML uses vanilla JS to parse the unified diff and render side-by-side.
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Sweep Review — {run_id}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace; font-size: 13px; background: #0d1117; color: #e6edf3; }}
  #header {{ background: #161b22; border-bottom: 1px solid #30363d; padding: 12px 20px; display: flex; align-items: center; gap: 16px; position: sticky; top: 0; z-index: 100; }}
  #header h1 {{ font-size: 15px; font-weight: 600; color: #58a6ff; }}
  .stat {{ font-size: 12px; color: #8b949e; }}
  #layout {{ display: flex; height: calc(100vh - 48px); }}
  #sidebar {{ width: 260px; min-width: 180px; background: #161b22; border-right: 1px solid #30363d; overflow-y: auto; flex-shrink: 0; padding: 8px 0; }}
  #sidebar .file-item {{ padding: 6px 12px; cursor: pointer; display: flex; align-items: center; gap: 8px; border-left: 3px solid transparent; }}
  #sidebar .file-item:hover {{ background: #21262d; }}
  #sidebar .file-item.active {{ background: #21262d; border-left-color: #58a6ff; }}
  #sidebar .badge {{ font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px; }}
  .badge-add {{ background: #1f4a2a; color: #3fb950; }}
  .badge-del {{ background: #4a1f2a; color: #f85149; }}
  .badge-mod {{ background: #1f2d4a; color: #79c0ff; }}
  #main {{ flex: 1; overflow-y: auto; padding: 16px; }}
  .file-diff {{ margin-bottom: 24px; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }}
  .file-diff-header {{ background: #161b22; padding: 8px 14px; font-size: 12px; color: #8b949e; border-bottom: 1px solid #30363d; display: flex; justify-content: space-between; }}
  .file-diff-header .filename {{ color: #e6edf3; font-weight: 600; }}
  .diff-table {{ width: 100%; border-collapse: collapse; font-family: 'SF Mono', 'Fira Code', monospace; font-size: 12px; }}
  .diff-table td {{ padding: 2px 8px; white-space: pre; vertical-align: top; line-height: 1.5; }}
  .diff-table .line-num {{ width: 40px; text-align: right; color: #484f58; user-select: none; border-right: 1px solid #30363d; padding-right: 6px; }}
  .diff-table .line-add {{ background: #0e4429; }}
  .diff-table .line-add .line-num {{ background: #0a3320; color: #3fb950; }}
  .diff-table .line-del {{ background: #4a0f1a; }}
  .diff-table .line-del .line-num {{ background: #38080f; color: #f85149; }}
  .diff-table .line-ctx {{ background: #0d1117; }}
  .diff-table .line-hdr {{ background: #1c2128; color: #8b949e; }}
  .diff-table .line-content {{ color: #e6edf3; }}
  .diff-table .line-add .line-content {{ color: #aff5b4; }}
  .diff-table .line-del .line-content {{ color: #ffdcd7; }}
  .comment-btn {{ font-size: 10px; opacity: 0; cursor: pointer; background: #1f6feb; color: white; border: none; border-radius: 3px; padding: 1px 6px; margin-left: 6px; }}
  tr:hover .comment-btn {{ opacity: 1; }}
  .comment-block {{ background: #161b22; border-left: 3px solid #58a6ff; padding: 8px 12px; margin: 2px 0; font-family: -apple-system, sans-serif; }}
  .comment-block .comment-meta {{ font-size: 11px; color: #8b949e; margin-bottom: 4px; }}
  .comment-block .comment-text {{ color: #e6edf3; white-space: pre-wrap; }}
  .comment-block.resolved {{ opacity: 0.5; border-left-color: #3fb950; }}
  #comment-modal {{ display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); z-index: 200; align-items: center; justify-content: center; }}
  #comment-modal.open {{ display: flex; }}
  #comment-box {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; width: 480px; }}
  #comment-box h3 {{ font-size: 14px; margin-bottom: 12px; color: #58a6ff; }}
  #comment-box textarea {{ width: 100%; height: 100px; background: #0d1117; color: #e6edf3; border: 1px solid #30363d; border-radius: 4px; padding: 8px; font-family: inherit; font-size: 13px; resize: vertical; }}
  #comment-box .btn-row {{ display: flex; gap: 8px; margin-top: 10px; justify-content: flex-end; }}
  #comment-box button {{ padding: 6px 14px; border-radius: 4px; border: none; cursor: pointer; font-size: 13px; }}
  .btn-save {{ background: #238636; color: white; }}
  .btn-cancel {{ background: #21262d; color: #e6edf3; }}
  #save-bar {{ position: fixed; bottom: 20px; right: 20px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; display: flex; align-items: center; gap: 12px; z-index: 150; }}
  #save-bar .comment-count {{ font-size: 13px; color: #8b949e; }}
  #save-bar .btn-dl {{ background: #1f6feb; color: white; padding: 6px 14px; border-radius: 4px; border: none; cursor: pointer; font-size: 13px; }}
  #orphaned {{ margin-top: 24px; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }}
  #orphaned summary {{ padding: 10px 14px; background: #161b22; cursor: pointer; font-size: 13px; color: #8b949e; }}
  #orphaned .orphan-list {{ padding: 12px; }}
</style>
</head>
<body>
<div id="header">
  <h1>Sweep Review — {run_id}</h1>
  <span class="stat" id="stat-line"></span>
  <span class="stat" style="color:#484f58">sha: {sha}</span>
</div>
<div id="layout">
  <nav id="sidebar"></nav>
  <main id="main"></main>
</div>
<div id="save-bar">
  <span class="comment-count" id="save-count">0 comments</span>
  <button class="btn-dl" onclick="saveComments()">Save Comments</button>
</div>
<div id="comment-modal">
  <div id="comment-box">
    <h3>Add Comment</h3>
    <textarea id="comment-text" placeholder="Leave a comment..."></textarea>
    <div class="btn-row">
      <button class="btn-cancel" onclick="closeModal()">Cancel</button>
      <button class="btn-save" onclick="submitComment()">Save</button>
    </div>
  </div>
</div>

<script>
// ── Data ──────────────────────────────────────────────────────────────────
const RUN_ID = {json.dumps(run_id)};
const DIFF_TEXT = {json.dumps(diff_text)};
const STAT_TEXT = {json.dumps(stat_text)};
const SEED_COMMENTS = {seed_json};

// ── State ─────────────────────────────────────────────────────────────────
const comments = {{}};  // anchor -> [{{ts, anchor, author, text, resolved}}]
let pendingAnchor = null;

// Load seed comments
SEED_COMMENTS.forEach(c => {{
  if (!comments[c.anchor]) comments[c.anchor] = [];
  comments[c.anchor].push(c);
}});

// ── Diff parser ───────────────────────────────────────────────────────────
function parseDiff(text) {{
  const files = [];
  let cur = null;
  let leftN = 0, rightN = 0;
  const lines = text.split('\\n');

  for (let i = 0; i < lines.length; i++) {{
    const l = lines[i];
    if (l.startsWith('diff --git ')) {{
      if (cur) files.push(cur);
      cur = {{ header: l, filename: '', hunks: [], stat: '' }};
      continue;
    }}
    if (!cur) continue;
    if (l.startsWith('+++ b/')) {{ cur.filename = l.slice(6); continue; }}
    if (l.startsWith('--- ') || l.startsWith('+++ ')) continue;
    if (l.startsWith('@@')) {{
      const m = l.match(/@@ -(\\d+)(?:,\\d+)? \\+(\\d+)(?:,\\d+)? @@/);
      if (m) {{ leftN = parseInt(m[1]); rightN = parseInt(m[2]); }}
      cur.hunks.push({{ hdr: l, rows: [] }});
      continue;
    }}
    if (!cur.hunks.length) continue;
    const hunk = cur.hunks[cur.hunks.length - 1];
    if (l.startsWith('+')) {{
      hunk.rows.push({{ type: 'add', left: null, right: rightN++, content: l.slice(1) }});
    }} else if (l.startsWith('-')) {{
      hunk.rows.push({{ type: 'del', left: leftN++, right: null, content: l.slice(1) }});
    }} else {{
      hunk.rows.push({{ type: 'ctx', left: leftN++, right: rightN++, content: l.slice(1) }});
    }}
  }}
  if (cur) files.push(cur);
  return files;
}}

// ── Render ────────────────────────────────────────────────────────────────
function esc(s) {{
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

function anchorKey(filename, hunkIdx, rowIdx) {{
  return btoa(encodeURIComponent(filename + ':' + hunkIdx + ':' + rowIdx)).slice(0, 32);
}}

function renderComments(anchor) {{
  const cs = comments[anchor] || [];
  if (!cs.length) return '';
  return cs.map(c => `
    <tr><td colspan="3" style="padding:0">
      <div class="comment-block${{c.resolved ? ' resolved' : ''}}">
        <div class="comment-meta">${{c.author || 'Omar'}} &bull; ${{new Date(c.ts * 1000).toLocaleString()}}</div>
        <div class="comment-text">${{esc(c.text)}}</div>
      </div>
    </td></tr>`).join('');
}}

function buildSidebar(files) {{
  const nav = document.getElementById('sidebar');
  nav.innerHTML = files.map((f, fi) => {{
    const adds = f.hunks.flatMap(h => h.rows).filter(r => r.type === 'add').length;
    const dels = f.hunks.flatMap(h => h.rows).filter(r => r.type === 'del').length;
    const badge = adds && dels ? `<span class="badge badge-mod">~</span>` :
                  adds ? `<span class="badge badge-add">+${{adds}}</span>` :
                  `<span class="badge badge-del">-${{dels}}</span>`;
    const name = f.filename.split('/').pop() || f.filename;
    return `<div class="file-item" id="nav-${{fi}}" onclick="scrollTo('file-${{fi}}'); setActive(${{fi}})">${{badge}}<span title="${{esc(f.filename)}}">${{esc(name)}}</span></div>`;
  }}).join('');
}}

function setActive(fi) {{
  document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
  const el = document.getElementById('nav-' + fi);
  if (el) el.classList.add('active');
}}

function scrollTo(id) {{
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
}}

function renderFiles(files) {{
  const main = document.getElementById('main');
  main.innerHTML = files.map((f, fi) => {{
    const rows = f.hunks.map((h, hi) => {{
      const hdrRow = `<tr class="line-hdr"><td class="line-num"></td><td class="line-num"></td><td class="line-content">${{esc(h.hdr)}}</td></tr>`;
      const dataRows = h.rows.map((r, ri) => {{
        const anc = anchorKey(f.filename, hi, ri);
        const sign = r.type === 'add' ? '+' : r.type === 'del' ? '-' : ' ';
        const cls = 'line-' + r.type;
        const lNum = r.left || '';
        const rNum = r.right || '';
        const commentRows = renderComments(anc);
        return `<tr class="${{cls}}" data-anchor="${{anc}}">
          <td class="line-num">${{lNum}}</td>
          <td class="line-num">${{rNum}}</td>
          <td class="line-content">${{sign}}${{esc(r.content)}}<button class="comment-btn" onclick="openModal('${{anc}}')">+</button></td>
        </tr>${{commentRows}}`;
      }}).join('');
      return hdrRow + dataRows;
    }}).join('');

    const adds = f.hunks.flatMap(h => h.rows).filter(r => r.type === 'add').length;
    const dels = f.hunks.flatMap(h => h.rows).filter(r => r.type === 'del').length;

    return `<div class="file-diff" id="file-${{fi}}">
      <div class="file-diff-header">
        <span class="filename">${{esc(f.filename)}}</span>
        <span><span style="color:#3fb950">+${{adds}}</span> <span style="color:#f85149">-${{dels}}</span></span>
      </div>
      <table class="diff-table"><tbody>${{rows}}</tbody></table>
    </div>`;
  }}).join('');

  // Orphaned comments (anchors not in current diff)
  const allAnchors = new Set(
    files.flatMap((f, fi) =>
      f.hunks.flatMap((h, hi) => h.rows.map((r, ri) => anchorKey(f.filename, hi, ri)))
    )
  );
  const orphaned = Object.entries(comments).filter(([k]) => !allAnchors.has(k));
  if (orphaned.length) {{
    main.innerHTML += `<details id="orphaned"><summary>Orphaned Comments (${{orphaned.length}})</summary>
      <div class="orphan-list">${{orphaned.flatMap(([k, cs]) => cs.map(c => `
        <div class="comment-block">
          <div class="comment-meta">${{c.author || 'Omar'}} &bull; anchor: ${{k}}</div>
          <div class="comment-text">${{esc(c.text)}}</div>
        </div>`)).join('')}}</div></details>`;
  }}
}}

function updateSaveBar() {{
  const total = Object.values(comments).flat().length;
  document.getElementById('save-count').textContent = total + ' comment' + (total !== 1 ? 's' : '');
}}

// ── Comment modal ─────────────────────────────────────────────────────────
function openModal(anchor) {{
  pendingAnchor = anchor;
  document.getElementById('comment-text').value = '';
  document.getElementById('comment-modal').classList.add('open');
  setTimeout(() => document.getElementById('comment-text').focus(), 50);
}}

function closeModal() {{
  document.getElementById('comment-modal').classList.remove('open');
  pendingAnchor = null;
}}

function submitComment() {{
  const text = document.getElementById('comment-text').value.trim();
  if (!text || !pendingAnchor) {{ closeModal(); return; }}
  const entry = {{
    ts: Math.floor(Date.now() / 1000),
    anchor: pendingAnchor,
    author: 'Omar',
    text: text,
    resolved: false
  }};
  if (!comments[pendingAnchor]) comments[pendingAnchor] = [];
  comments[pendingAnchor].push(entry);
  closeModal();

  // Re-render the affected row's comments inline
  const rows = document.querySelectorAll(`[data-anchor="${{pendingAnchor}}"]`);
  rows.forEach(row => {{
    // Remove old comment rows that follow this row
    let next = row.nextElementSibling;
    while (next && next.querySelector('.comment-block')) {{
      const tmp = next.nextElementSibling;
      next.remove();
      next = tmp;
    }}
    // Insert new comment rows after
    const tmp = document.createElement('tbody');
    tmp.innerHTML = renderComments(pendingAnchor);
    Array.from(tmp.children).forEach(child => row.after(child));
  }});

  updateSaveBar();
}}

// ── Save / download ───────────────────────────────────────────────────────
function saveComments() {{
  const all = Object.values(comments).flat();
  if (!all.length) {{ alert('No comments to save.'); return; }}
  const jsonl = all.map(c => JSON.stringify(c)).join('\\n') + '\\n';
  const blob = new Blob([jsonl], {{ type: 'application/x-ndjson' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  // Figure out next round number from existing comments keys
  const existingRounds = Object.keys(sessionStorage).filter(k => k.startsWith('round-')).length;
  a.download = RUN_ID + '-r1.comments.jsonl';
  a.href = url;
  a.click();
  URL.revokeObjectURL(url);
}}

// ── Init ──────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {{
  const files = parseDiff(DIFF_TEXT);
  buildSidebar(files);
  renderFiles(files);
  updateSaveBar();

  // Parse stat for header
  const statLines = STAT_TEXT.trim().split('\\n');
  const summary = statLines[statLines.length - 1] || '';
  document.getElementById('stat-line').textContent = summary;
}});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# sweep-review-compile
# ---------------------------------------------------------------------------

def cmd_sweep_review_compile(args):
    root = _np_root()
    sweeps = _sweeps_dir(root)

    date_str = args.date or date.today().strftime("%Y-%m-%d")
    run_n = args.run

    if run_n is None:
        d, n = _latest_run(sweeps, date_str)
        if d is None:
            utils.err(f"No snapshot found for {date_str}. Run sweep-review-generate first.")
            sys.exit(utils.EXIT_NOT_FOUND)
        date_str, run_n = d, n

    run_id = f"{date_str}-{run_n:02d}"
    snapshot_path = sweeps / f"{run_id}.snapshot.html"

    if not snapshot_path.exists():
        utils.err(f"Snapshot not found: {snapshot_path}")
        sys.exit(utils.EXIT_NOT_FOUND)

    # Collect all comment rounds
    comment_rounds = sorted(sweeps.glob(f"{run_id}-r*.comments.jsonl"))
    all_comments: list = []
    for cf in comment_rounds:
        try:
            for line in cf.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    all_comments.append(json.loads(line))
        except Exception:
            pass

    if not all_comments and not comment_rounds:
        # Just copy snapshot as review
        import shutil
        review_path = sweeps / f"{run_id}.review.html"
        if utils.DRY_RUN:
            utils.log(f"[dry-run] Would copy {snapshot_path} → {review_path}")
            return
        shutil.copy2(str(snapshot_path), str(review_path))
        utils.log(f"sweep-review-compile: wrote {review_path} (no comments)")
        return

    # Deduplicate: latest entry per anchor wins
    by_anchor: dict = {}
    for entry in all_comments:
        anchor = entry.get("anchor", "")
        if anchor:
            by_anchor[anchor] = entry

    merged_comments = list(by_anchor.values())

    # Re-generate review.html by injecting comments into snapshot
    # Read snapshot to extract embedded DIFF_TEXT and RUN_ID
    snapshot_html = snapshot_path.read_text(encoding="utf-8")

    # Patch the SEED_COMMENTS constant in the HTML
    seed_json = json.dumps(merged_comments, indent=2)
    new_html = re.sub(
        r'const SEED_COMMENTS = \[.*?\];',
        f'const SEED_COMMENTS = {seed_json};',
        snapshot_html,
        flags=re.DOTALL
    )

    review_path = sweeps / f"{run_id}.review.html"
    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would write {review_path} with {len(merged_comments)} merged comment(s)")
        return

    review_path.write_text(new_html, encoding="utf-8")
    utils.log(f"sweep-review-compile: wrote {review_path} ({len(merged_comments)} comment(s) from {len(comment_rounds)} round(s))")


# ---------------------------------------------------------------------------
# sweep-review-squash
# ---------------------------------------------------------------------------

def cmd_sweep_review_squash(args):
    root = _np_root()
    sweeps = _sweeps_dir(root)

    date_str = args.date or date.today().strftime("%Y-%m-%d")
    run_n = args.run

    if run_n is None:
        d, n = _latest_run(sweeps, date_str)
        if d is None:
            utils.err(f"No snapshot found for {date_str}.")
            sys.exit(utils.EXIT_NOT_FOUND)
        date_str, run_n = d, n

    run_id = f"{date_str}-{run_n:02d}"
    rounds = sorted(sweeps.glob(f"{run_id}-r*.comments.jsonl"))

    if len(rounds) <= 1:
        utils.log(f"sweep-review-squash: only {len(rounds)} round(s) — nothing to squash.")
        return

    all_comments: list = []
    for cf in rounds:
        for line in cf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                all_comments.append(json.loads(line))

    # Deduplicate: latest wins
    by_anchor: dict = {}
    for entry in all_comments:
        by_anchor[entry.get("anchor", "")] = entry
    merged = list(by_anchor.values())

    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would squash {len(rounds)} rounds → {run_id}-r1.comments.jsonl ({len(merged)} unique comments)")
        return

    # Back up originals
    for cf in rounds:
        bak = Path(str(cf) + ".bak")
        cf.rename(bak)

    r1 = sweeps / f"{run_id}-r1.comments.jsonl"
    r1.write_text("\n".join(json.dumps(c) for c in merged) + "\n", encoding="utf-8")
    utils.log(f"sweep-review-squash: squashed {len(rounds)} rounds → {r1} ({len(merged)} unique comments)")


# ---------------------------------------------------------------------------
# sweep-review-list
# ---------------------------------------------------------------------------

def cmd_sweep_review_list(args):
    root = _np_root()
    sweeps = _sweeps_dir(root)

    date_filter = args.date

    snapshots = sorted(sweeps.glob("*.snapshot.html"))
    if not snapshots:
        utils.log("No sweep reviews found.")
        return

    # Group by date
    by_date: dict[str, list] = {}
    for s in snapshots:
        m = re.match(r'(\d{4}-\d{2}-\d{2})-(\d+)\.snapshot', s.stem)
        if not m:
            continue
        d, n = m.group(1), int(m.group(2))
        if date_filter and d != date_filter:
            continue
        by_date.setdefault(d, []).append(n)

    for d in sorted(by_date.keys(), reverse=True):
        print(f"\n{d}")
        for n in sorted(by_date[d]):
            run_id = f"{d}-{n:02d}"
            rounds = list(sweeps.glob(f"{run_id}-r*.comments.jsonl"))
            compiled = (sweeps / f"{run_id}.review.html").exists()
            compiled_mark = "✓" if compiled else "·"
            rounds_str = f"{len(rounds)} comment round(s)" if rounds else "no comments"
            print(f"  [{compiled_mark}] run {n:02d}  {run_id}  {rounds_str}")


# ---------------------------------------------------------------------------
# sweep-review-open
# ---------------------------------------------------------------------------

def cmd_sweep_review_open(args):
    root = _np_root()
    sweeps = _sweeps_dir(root)

    date_str = args.date or date.today().strftime("%Y-%m-%d")
    run_n = args.run

    if run_n is None:
        d, n = _latest_run(sweeps, date_str)
        if d is None:
            utils.err(f"No snapshot found for {date_str}.")
            sys.exit(utils.EXIT_NOT_FOUND)
        date_str, run_n = d, n

    run_id = f"{date_str}-{run_n:02d}"

    if args.snapshot:
        path = sweeps / f"{run_id}.snapshot.html"
    else:
        review = sweeps / f"{run_id}.review.html"
        path = review if review.exists() else sweeps / f"{run_id}.snapshot.html"

    if not path.exists():
        utils.err(f"File not found: {path}")
        sys.exit(utils.EXIT_NOT_FOUND)

    import subprocess as sp
    sp.run(["open", str(path)])
    utils.log(f"sweep-review-open: opened {path}")
