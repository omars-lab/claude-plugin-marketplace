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
# sweep-start  (called at Phase 2 before any sweep commits)
# ---------------------------------------------------------------------------

def cmd_sweep_start(args):
    """Record the current HEAD as the sweep base and assign a sweep ID.

    Writes two files to sweeps/:
      .sweep-base   — current HEAD SHA (used as diff base by sweep-review-generate)
      .sweep-id     — human-readable ID like "2026-04-21-01"
    """
    root = _np_root()
    sweeps = _sweeps_dir(root)

    date_str = args.date or date.today().strftime("%Y-%m-%d")
    run_n = _run_counter(sweeps, date_str)
    sweep_id = f"{date_str}-{run_n:02d}"

    head_r = _git(["rev-parse", "HEAD"], cwd=root)
    if head_r.returncode != 0:
        utils.err("Could not determine HEAD SHA.")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)
    base_sha = head_r.stdout.strip()

    base_file = sweeps / ".sweep-base"
    id_file   = sweeps / ".sweep-id"
    base_file.write_text(base_sha + "\n", encoding="utf-8")
    id_file.write_text(sweep_id + "\n", encoding="utf-8")

    utils.log(f"sweep-start: sweep ID = {sweep_id} | base = {base_sha[:7]}")


# ---------------------------------------------------------------------------
# sweep-commit
# ---------------------------------------------------------------------------

def cmd_sweep_commit(args):
    root = _np_root()
    # Use -z for NUL-terminated output: paths are unquoted (no octal escaping)
    r = subprocess.run(
        ["git", "status", "--porcelain", "-z"],
        capture_output=True, timeout=30, cwd=str(root)
    )
    if r.returncode != 0:
        utils.err(f"git status failed: {r.stderr.decode(errors='replace').strip()}")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    modified_md = []
    untracked_md = []
    # -z output: each entry is "XY PATH\0" (renames: "XY FROM\0TO\0")
    entries = r.stdout.decode("utf-8", errors="replace").split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        xy = entry[:2]
        path_str = entry[3:]
        # Renames have a second NUL-terminated path (TO) already consumed above
        if xy[0] in ("R", "C"):
            i += 1  # skip the "from" path
        if not path_str.endswith(".md"):
            continue
        if xy == "??":
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

    # Stage via --pathspec-from-file with NUL separators to handle emoji/space paths
    nul_paths = "\0".join(all_md).encode("utf-8")
    stage_result = subprocess.run(
        ["git", "add", "--pathspec-from-file=-", "--pathspec-file-nul"],
        input=nul_paths, capture_output=True, timeout=30, cwd=str(root)
    )
    if stage_result.returncode != 0:
        utils.err(f"git add failed: {stage_result.stderr.decode(errors='replace').strip()}")
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

    # Determine the base commit for the diff range.
    # Priority: --base-commit arg > .sweep-base file > auto-detect first sweep commit today
    base_commit = getattr(args, "base_commit", None)
    sweep_id = None

    base_file = sweeps / ".sweep-base"
    id_file   = sweeps / ".sweep-id"

    if base_commit:
        # Validate it exists
        check = _git(["rev-parse", "--verify", base_commit], cwd=root)
        if check.returncode != 0:
            utils.err(f"Base commit not found: {base_commit}")
            sys.exit(utils.EXIT_NOT_FOUND)
        base_commit = check.stdout.strip()
    elif base_file.exists():
        # Use sweep-start recorded base
        base_commit = base_file.read_text(encoding="utf-8").strip()
        sweep_id = id_file.read_text(encoding="utf-8").strip() if id_file.exists() else None
    else:
        # Fall back: parent of first sweep-related commit today
        log_r = _git(
            ["log", "--oneline", "--after", f"{date_str} 00:00:00",
             "--before", f"{date_str} 23:59:59",
             "--extended-regexp", "--grep",
             r"^(sweep|chore|reflect|fix|feat)\("],
            cwd=root
        )
        sweep_commits = []
        if log_r.returncode == 0 and log_r.stdout.strip():
            sweep_commits = [line.split()[0] for line in log_r.stdout.strip().splitlines()]

        if not sweep_commits:
            utils.err(f"No sweep commits found for {date_str}. Run 'sweep-start' at Phase 2 or pass --base-commit.")
            sys.exit(utils.EXIT_NOT_FOUND)

        earliest_sweep = sweep_commits[-1]
        parent_r = _git(["rev-parse", f"{earliest_sweep}^"], cwd=root)
        if parent_r.returncode != 0:
            utils.err(f"Could not find parent of {earliest_sweep}")
            sys.exit(utils.EXIT_VALIDATION_FAILURE)
        base_commit = parent_r.stdout.strip()

    head_sha = _git(["rev-parse", "HEAD"], cwd=root).stdout.strip()
    sweep_sha = (sweep_id or head_sha[:7])  # display label

    run_n = _run_counter(sweeps, date_str)
    run_id = f"{date_str}-{run_n:02d}"

    # Get diff stat + unified diff for the full range base..HEAD
    stat_r = _git(["diff", "--stat", f"{base_commit}..HEAD"], cwd=root)
    stat_text = stat_r.stdout if stat_r.returncode == 0 else ""

    diff_r = _git(["diff", "--unified=3", f"{base_commit}..HEAD"], cwd=root)
    diff_text = diff_r.stdout if diff_r.returncode == 0 else ""

    if not diff_text:
        utils.err(f"Could not get diff for range {base_commit[:7]}..HEAD")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    # Decode git-quoted octal paths so emoji filenames are readable
    diff_text = _decode_git_quoted_paths(diff_text)
    stat_text = _decode_git_quoted_paths(stat_text)

    # Extract sweep narrative from breadcrumb tables in swept Calendar files
    narrative_data = _extract_sweep_narrative(root, base_commit)
    narrative = narrative_data["rows"]
    changed_calendar_files = narrative_data["changed_calendar_files"]

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

    html = _build_snapshot_html(run_id, date_str, sweep_sha, stat_text, diff_text, seed_comments, narrative, changed_calendar_files)
    out_path = sweeps / f"{run_id}.snapshot.html"
    out_path.write_text(html, encoding="utf-8")
    utils.log(f"sweep-review-generate: wrote {out_path}")


def _decode_git_quoted_paths(text: str) -> str:
    """Replace git-quoted octal paths with decoded UTF-8 filenames.

    Git wraps paths containing non-ASCII chars in double quotes and encodes
    each byte as \\NNN (octal). This function decodes them so emoji filenames
    are human-readable in the HTML diff view.

    Examples:
      +++ "b/Notes/\\360\\237\\217\\242 ServiceNow/..."
      → +++ b/Notes/🏢 ServiceNow/...
    """
    import re as _re

    def _unescape(m: "_re.Match") -> str:
        quoted = m.group(1)  # content between the outer quotes
        # Decode C-style octal escapes (\NNN) to bytes, then UTF-8
        byte_parts = []
        i = 0
        while i < len(quoted):
            if quoted[i] == '\\' and i + 1 < len(quoted):
                # Could be \NNN (octal) or other escape
                if quoted[i+1].isdigit():
                    byte_parts.append(int(quoted[i+1:i+4], 8))
                    i += 4
                else:
                    # Other escape: keep as-is
                    byte_parts.append(ord(quoted[i+1]))
                    i += 2
            else:
                byte_parts.append(ord(quoted[i]))
                i += 1
        try:
            decoded = bytes(byte_parts).decode("utf-8", errors="replace")
        except Exception:
            decoded = quoted
        return decoded  # Return without surrounding quotes

    # Match lines like `+++ "b/..."` or `--- "a/..."` or `diff --git "a/..." "b/..."`
    # Also handles rename lines and stat lines with quoted paths.
    # Pattern: a double-quoted string that starts with a/ or b/
    pattern = _re.compile(r'"((?:[ab])/(?:[^"\\]|\\.)*)\"')

    def _replace(m: "_re.Match") -> str:
        inner = m.group(1)  # e.g. "b/Notes/\360..."
        prefix = inner[:2]  # "b/" or "a/"
        rest = inner[2:]
        decoded = _unescape(_re.match(r'(.*)', rest))
        return prefix + decoded

    # Replace all quoted path instances
    result = pattern.sub(lambda m: _replace(m), text)
    return result


def _extract_sweep_narrative(root: "Path", base_commit: str) -> list:
    """Parse breadcrumb tables from swept Calendar files and return narrative rows.

    Returns a list of dicts:
      { date, source_file, section, summary, destination }
    """
    import re as _re

    # Find Calendar/*.md files that changed since base_commit
    diff_r = _git(
        ["diff", "--name-only", f"{base_commit}..HEAD", "--", "Calendar/*.md"],
        cwd=root
    )
    changed_files: list[str] = []
    if diff_r.returncode == 0:
        changed_files = [l.strip() for l in diff_r.stdout.strip().splitlines() if l.strip()]

    rows = []
    table_re = _re.compile(
        r'^\|\s*(?P<date>[\d-]+)\s*\|\s*(?P<section>[^|]+)\s*\|\s*(?P<summary>[^|]+)\s*\|\s*(?P<dest>[^|]+)\s*\|',
        _re.MULTILINE
    )

    for rel in changed_files:
        abs_path = root / rel
        try:
            content = abs_path.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in table_re.finditer(content):
            date_val = m.group("date").strip()
            section  = m.group("section").strip()
            summary  = m.group("summary").strip()
            dest     = m.group("dest").strip()
            # Only accept rows with a valid YYYY-MM-DD date (skips headers + separator rows)
            if not _re.match(r'^\d{4}-\d{2}-\d{2}$', date_val):
                continue
            rows.append({
                "date":        date_val,
                "source_file": rel,
                "section":     section,
                "summary":     summary,
                "destination": dest,
            })

    rows.sort(key=lambda r: (r["date"], r["source_file"]))
    return {"rows": rows, "changed_calendar_files": changed_files}


def _build_snapshot_html(
    run_id: str, date_str: str, sha: str,
    stat_text: str, diff_text: str,
    seed_comments: list,
    narrative: list | None = None,
    changed_calendar_files: list | None = None,
) -> str:
    seed_json = json.dumps(seed_comments, indent=2)
    narrative_json = json.dumps(narrative or [], indent=2)
    changed_cal_json = json.dumps(changed_calendar_files or [], indent=2)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Sweep Review — {run_id}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px;background:#0d1117;color:#e6edf3;display:flex;flex-direction:column;height:100vh}}
#hdr{{background:#161b22;border-bottom:1px solid #30363d;padding:10px 20px;display:flex;align-items:center;gap:16px;position:sticky;top:0;z-index:100}}
#hdr h1{{font-size:15px;font-weight:600;color:#58a6ff}}
.stat{{font-size:12px;color:#8b949e}}
.tabs{{display:flex;gap:4px;margin-left:auto}}
.tab{{padding:4px 12px;border-radius:4px;cursor:pointer;font-size:12px;background:transparent;color:#8b949e;border:1px solid transparent}}
.tab.active{{background:#21262d;color:#e6edf3;border-color:#30363d}}
#filter-bar{{background:#161b22;border-bottom:1px solid #30363d;padding:6px 20px;display:flex;align-items:center;gap:8px;flex-shrink:0}}
.domain-chip{{padding:3px 10px;border-radius:12px;cursor:pointer;font-size:12px;background:#21262d;color:#8b949e;border:1px solid #30363d}}
.domain-chip.active{{background:#1a3a28;color:#3fb950;border-color:#3fb950}}
.copy-btn{{margin-left:auto;padding:3px 10px;border-radius:4px;cursor:pointer;font-size:12px;background:#21262d;color:#8b949e;border:1px solid #30363d}}
.copy-btn:hover{{color:#e6edf3}}
.orphaned-block{{margin-top:16px;padding:12px 16px;border:1px solid #4a2f10;border-radius:8px;background:#1a1200}}
.orphaned-hdr{{font-size:12px;color:#d29922;margin-bottom:6px;font-weight:600}}
.orphaned-block ul{{list-style:none;padding:0}}
.orphaned-block li{{font-size:11.5px;color:#8b949e;font-family:'SF Mono','Fira Code',monospace;padding:2px 0}}
.dest-link{{color:#79c0ff;text-decoration:none;font-family:'SF Mono','Fira Code',monospace;font-size:11px}}
.dest-link:hover{{text-decoration:underline;color:#a5d6ff}}
.view-btn{{padding:1px 6px;border-radius:3px;cursor:pointer;font-size:11px;background:#21262d;color:#8b949e;border:1px solid #30363d}}
.view-btn:hover{{color:#e6edf3;border-color:#8b949e}}
#modal-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:1000;align-items:center;justify-content:center}}
#modal-overlay.open{{display:flex}}
.modal{{background:#161b22;border:1px solid #30363d;border-radius:10px;width:92vw;max-width:1400px;max-height:88vh;display:flex;flex-direction:column;overflow:hidden}}
.modal-hdr{{padding:10px 20px;border-bottom:1px solid #30363d;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;gap:12px}}
.modal-title{{font-size:13px;font-weight:600;color:#e6edf3;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.modal-close{{background:none;border:none;color:#8b949e;cursor:pointer;font-size:18px;line-height:1;padding:0 2px;flex-shrink:0}}
.modal-close:hover{{color:#e6edf3}}
.modal-body{{flex:1;min-height:0;overflow-y:auto;padding:16px;display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.modal-panel-hdr{{font-size:11px;font-weight:600;color:#8b949e;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #30363d}}
.modal-empty{{color:#484f58;font-size:12px;padding:16px;text-align:center}}
.diff-lines{{font-family:'SF Mono','Fira Code',monospace;font-size:11.5px;line-height:18px;overflow-x:auto}}
.diff-line{{padding:1px 8px;white-space:pre}}
.diff-line.removed{{background:#4a0f1a;color:#ffdcd7}}
.diff-line.added{{background:#0e4429;color:#aff5b4}}
#layout{{display:flex;flex:1;min-height:0}}
#sidebar{{width:260px;min-width:160px;background:#161b22;border-right:1px solid #30363d;overflow-y:auto;flex-shrink:0;padding:8px 0}}
.fi{{padding:5px 12px;cursor:pointer;display:flex;align-items:center;gap:8px;border-left:3px solid transparent;font-size:12px}}
.fi:hover{{background:#21262d}}
.fi.active{{background:#21262d;border-left-color:#58a6ff}}
.fi .name{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}}
.badge{{font-size:10px;font-weight:700;padding:1px 5px;border-radius:3px;flex-shrink:0}}
.ba{{background:#1f4a2a;color:#3fb950}}.bd{{background:#4a1f2a;color:#f85149}}.bm{{background:#1f2d4a;color:#79c0ff}}
#main{{flex:1;overflow-y:auto;padding:16px}}
/* ── Diff panel ── */
.fd{{margin-bottom:20px;border:1px solid #30363d;border-radius:8px;overflow:hidden}}
.fdh{{background:#161b22;padding:7px 14px;font-size:12px;color:#8b949e;border-bottom:1px solid #30363d;display:flex;justify-content:space-between}}
.fdh .fn{{color:#e6edf3;font-weight:600;font-family:'SF Mono','Fira Code',monospace}}
.sbs{{display:grid;grid-template-columns:1fr 1fr;font-family:'SF Mono','Fira Code',monospace;font-size:11.5px}}
.sbs-col{{overflow:hidden;border-right:1px solid #30363d}}
.sbs-col:last-child{{border-right:none}}
.sbs-col .col-hdr{{background:#1c2128;padding:3px 8px;font-size:11px;color:#8b949e;border-bottom:1px solid #30363d}}
.row{{display:flex;min-height:18px}}
.ln{{width:36px;text-align:right;padding:0 6px;color:#484f58;user-select:none;border-right:1px solid #30363d;flex-shrink:0;line-height:18px}}
.lc{{flex:1;padding:0 6px;white-space:pre;overflow:hidden;line-height:18px}}
.row.add{{background:#0e4429}}.row.add .ln{{background:#0a3320;color:#3fb950}}
.row.del{{background:#4a0f1a}}.row.del .ln{{background:#38080f;color:#f85149}}
.row.ctx{{background:#0d1117}}
.row.hdr{{background:#1c2128}}.row.hdr .lc{{color:#8b949e}}
.row.add .lc{{color:#aff5b4}}.row.del .lc{{color:#ffdcd7}}
/* ── Narrative panel ── */
#narrative{{padding:16px}}
.day-block{{margin-bottom:24px}}
.day-hdr{{font-size:14px;font-weight:600;color:#58a6ff;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #30363d}}
.nav-tbl{{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed}}
.nav-tbl th{{background:#161b22;padding:6px 10px;text-align:left;color:#8b949e;font-weight:500;border-bottom:2px solid #30363d;position:sticky;top:0;z-index:1}}
.nav-tbl th:nth-child(1){{width:18%}}.nav-tbl th:nth-child(2){{width:37%}}.nav-tbl th:nth-child(3){{width:39%}}.nav-tbl th:nth-child(4){{width:44px}}
.nav-tbl td{{padding:5px 10px;border-bottom:1px solid #21262d;vertical-align:middle;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.nav-tbl tr:hover td{{background:#161b22}}
.nav-tbl .section-col{{color:#e6edf3;font-weight:500}}
.nav-tbl .summary-col{{color:#8b949e}}
.day-sep-row td{{background:#0d1117;padding:14px 10px 5px;font-size:13px;font-weight:600;color:#58a6ff;border-bottom:1px solid #30363d;white-space:normal;overflow:visible}}
.empty{{color:#484f58;padding:24px;text-align:center}}
</style>
</head>
<body>
<div id="hdr">
  <h1>Sweep Review — {run_id}</h1>
  <span class="stat" id="stat-line"></span>
  <span class="stat" id="date-range" style="color:#484f58"></span>
  <span class="stat" style="color:#484f58">base {sha}</span>
  <div class="tabs">
    <button class="tab active" onclick="showTab('narrative')">📋 Narrative</button>
    <button class="tab" onclick="showTab('diff')">🔀 Diff</button>
  </div>
</div>
<div id="filter-bar">
  <span style="font-size:11px;color:#484f58;margin-right:2px">Domain:</span>
  <button class="domain-chip active" data-domain="all" onclick="setDomain('all')">All</button>
  <button class="domain-chip" data-domain="work" onclick="setDomain('work')">🏢 Work</button>
  <button class="domain-chip" data-domain="personal" onclick="setDomain('personal')">🏡 Personal</button>
  <button class="domain-chip" data-domain="earlbear" onclick="setDomain('earlbear')">👥 EarlBear</button>
  <button class="domain-chip" data-domain="coffee" onclick="setDomain('coffee')">☕️ Naqsh</button>
  <button class="copy-btn" id="copy-btn" onclick="copyNarrative()">📋 Copy</button>
</div>
<div id="layout">
  <nav id="sidebar" style="display:none"></nav>
  <main id="main">
    <div id="narrative"></div>
    <div id="diff" style="display:none"></div>
  </main>
</div>

<script>
const RUN_ID = {json.dumps(run_id)};
const DIFF_TEXT = {json.dumps(diff_text)};
const STAT_TEXT = {json.dumps(stat_text)};
const SEED_COMMENTS = {seed_json};
const NARRATIVE = {narrative_json};
const CHANGED_CALENDAR_FILES = {changed_cal_json};

let allParsedFiles = [];
const MODAL_ROWS = [];

// ── xcallback links ────────────────────────────────────────────────────────
function xcallbackUrl(dest) {{
  let raw = dest.replace(/\\[\\[([^\\]]+)\\]\\]/g, '$1').trim().replace(/\\.md$/, '');
  if (/^\\d{{8}}$/.test(raw)) {{
    return 'noteplan://x-callback-url/openNote?filename=' + raw;
  }}
  return 'noteplan://x-callback-url/openNote?noteTitle=' + encodeURIComponent(raw);
}}

// ── Section diff modal ─────────────────────────────────────────────────────
function closeModal() {{
  document.getElementById('modal-overlay').classList.remove('open');
}}

document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeModal(); }});

// Extract only the + or - lines for a section from DIFF_TEXT.
// lineType: '-' for removed from source, '+' for added to destination.
// For destination, pass lineType='+' and sectionName=null to get ALL added lines.
function extractSectionLines(filename, sectionName, lineType) {{
  const lines = DIFF_TEXT.split('\\n');
  const baseName = filename.split('/').pop().toLowerCase();
  let inFile = false;
  let inSection = sectionName === null; // null means accept all
  const result = [];
  const nameLower = sectionName ? sectionName.replace(/^#+\\s*/, '').trim().toLowerCase() : null;

  for (const line of lines) {{
    if (line.startsWith('diff --git ')) {{
      inFile = line.toLowerCase().includes(baseName);
      inSection = sectionName === null;
      continue;
    }}
    if (!inFile || line.startsWith('+++') || line.startsWith('---') || line.startsWith('index') || line.startsWith('@@')) continue;

    const type = line.length ? line[0] : ' ';
    if (type !== '+' && type !== '-' && type !== ' ') continue;
    const content = line.slice(1);

    if (sectionName !== null) {{
      // Detect section start: line contains the section name (stripping leading #s)
      const stripped = content.replace(/^#+\\s*/, '').toLowerCase();
      if (stripped === nameLower || stripped.startsWith(nameLower + ' ') || stripped.startsWith(nameLower + ':')) {{
        inSection = true;
      }} else if (inSection && /^#+\\s/.test(content) && type !== '+') {{
        inSection = false; // next section header — stop
      }}
    }}

    if (inSection && type === lineType) {{
      result.push(content);
    }}
  }}
  return result;
}}

function showSectionModal(idx) {{
  const row = MODAL_ROWS[idx];
  if (!row) return;

  const sectionName = row.section.replace(/^#+\\s*/, '').trim();
  let destRaw = row.destination.replace(/\\[\\[([^\\]]+)\\]\\]/g, '$1').trim().replace(/\\.md$/, '');

  // Source: removed lines belonging to this section
  const removedLines = extractSectionLines(row.source_file, sectionName, '-');

  // Destination: all added lines (content arrived under a plan wikilink header, not original section name)
  const destFile = allParsedFiles.find(f => {{
    const stem = (f.filename || '').split('/').pop().replace(/\\.md$/, '');
    return stem === destRaw || (f.filename || '').endsWith(destRaw + '.md');
  }});
  const addedLines = destFile ? extractSectionLines(destFile.filename, null, '+') : [];

  const renderLines = (lines, cls, title, filename) => {{
    const hdr = `${{esc(title)}} — <span style="color:#e6edf3;font-family:monospace;font-size:11px">${{esc(filename)}}</span>`;
    if (!lines.length) return `<div><div class="modal-panel-hdr">${{hdr}}</div><div class="modal-empty">No matching lines found</div></div>`;
    const body = lines.map(l => `<div class="diff-line ${{cls}}">${{esc(l)}}</div>`).join('');
    return `<div><div class="modal-panel-hdr">${{hdr}}</div><div class="diff-lines">${{body}}</div></div>`;
  }};

  document.getElementById('modal-title').textContent = sectionName + ' → ' + normDest(row.destination);
  document.getElementById('modal-body').innerHTML =
    renderLines(removedLines, 'removed', 'Removed from source', row.source_file.split('/').pop()) +
    renderLines(addedLines,  'added',   'Added to destination', destFile ? destFile.filename.split('/').pop() : destRaw);
  document.getElementById('modal-overlay').classList.add('open');
}}

// ── Tab switching ──────────────────────────────────────────────────────────
function showTab(name) {{
  document.getElementById('narrative').style.display = name === 'narrative' ? '' : 'none';
  document.getElementById('diff').style.display      = name === 'diff'      ? '' : 'none';
  document.getElementById('sidebar').style.display   = name === 'diff'      ? '' : 'none';
  document.getElementById('filter-bar').style.display = name === 'narrative' ? '' : 'none';
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.textContent.includes(name === 'narrative' ? 'Narrative' : 'Diff')));
}}

// ── Domain helpers ─────────────────────────────────────────────────────────
function inferDomain(dest) {{
  if (/🏢|ServiceNow/.test(dest)) return 'work';
  if (/👥|EarlBear/.test(dest))   return 'earlbear';
  if (/☕|NaqshCoffee/.test(dest)) return 'coffee';
  if (/🏡|Personal/.test(dest))   return 'personal';
  return 'other';
}}

function normDest(dest) {{
  let s = dest.replace(/\\[\\[([^\\]]+)\\]\\]/g, '$1');
  const slash = s.lastIndexOf('/');
  if (slash >= 0) s = s.slice(slash + 1);
  return s.replace(/\\.md$/, '') || dest;
}}

let activeDomain = 'all';

function setDomain(d) {{
  activeDomain = d;
  document.querySelectorAll('.domain-chip').forEach(c =>
    c.classList.toggle('active', c.dataset.domain === d));
  renderNarrative();
}}

// ── Narrative renderer ─────────────────────────────────────────────────────
function renderNarrative() {{
  const el = document.getElementById('narrative');
  MODAL_ROWS.length = 0;

  if (!NARRATIVE.length) {{
    el.innerHTML = '<div class="empty">No sweep breadcrumb data found.<br>Breadcrumb tables are written to each swept Calendar note.</div>';
    return;
  }}

  const rows = activeDomain === 'all'
    ? NARRATIVE
    : NARRATIVE.filter(r => inferDomain(r.destination) === activeDomain);

  if (!rows.length) {{
    el.innerHTML = '<div class="empty">No sections match the selected domain filter.</div>';
    return;
  }}

  const byDate = {{}};
  rows.forEach(r => {{
    const d = r.date || 'Unknown';
    if (!byDate[d]) byDate[d] = [];
    byDate[d].push(r);
  }});

  const dayNames = {{ '1':'Mon','2':'Tue','3':'Wed','4':'Thu','5':'Fri','6':'Sat','7':'Sun' }};

  // Single table for aligned columns across all days
  let tbody = '';
  for (const [d, dayRows] of Object.entries(byDate).sort()) {{
    let label = d;
    try {{
      const dt = new Date(d + 'T12:00:00');
      const dow = dayNames[String(((dt.getDay() + 6) % 7) + 1)] || '';
      label = `${{d}} (${{dow}})`;
    }} catch(e) {{}}

    tbody += `<tr class="day-sep-row"><td colspan="4">📅 ${{esc(label)}} — ${{dayRows.length}} section${{dayRows.length !== 1 ? 's' : ''}} swept</td></tr>`;

    tbody += dayRows.map(r => {{
      const idx = MODAL_ROWS.push(r) - 1;
      return `<tr>
        <td class="section-col">${{esc(r.section)}}</td>
        <td class="summary-col">${{esc(r.summary)}}</td>
        <td class="dest-col" title="${{esc(r.destination)}}"><a class="dest-link" href="${{xcallbackUrl(r.destination)}}">${{esc(normDest(r.destination))}}</a></td>
        <td style="padding:3px 6px;text-align:center"><button class="view-btn" onclick="showSectionModal(${{idx}})">⌕</button></td>
      </tr>`;
    }}).join('');
  }}

  let html = `<table class="nav-tbl">
    <thead><tr><th>Section</th><th>Summary</th><th>Destination</th><th></th></tr></thead>
    <tbody>${{tbody}}</tbody>
  </table>`;

  // Orphaned: SOURCE Calendar files swept but with no breadcrumb rows written.
  // Exclude target notes (files that appear as destinations — content was swept INTO them).
  const sourcesWithBreadcrumbs = new Set(NARRATIVE.map(r => r.source_file));
  const destCalStems = new Set(
    NARRATIVE.map(r => normDest(r.destination)).filter(d => /^\\d{{8}}$/.test(d))
  );
  const orphaned = CHANGED_CALENDAR_FILES.filter(f => {{
    const stem = f.split('/').pop().replace(/\\.md$/, '');
    return !sourcesWithBreadcrumbs.has(f) && !destCalStems.has(stem);
  }});
  if (orphaned.length) {{
    html += `<div class="orphaned-block">
      <div class="orphaned-hdr">⚠️ ${{orphaned.length}} swept file${{orphaned.length !== 1 ? 's' : ''}} with no breadcrumb rows</div>
      <ul>${{orphaned.map(f => `<li>${{esc(f.split('/').pop())}}</li>`).join('')}}</ul>
    </div>`;
  }}

  el.innerHTML = html;
}}

// ── Copy narrative as Markdown ─────────────────────────────────────────────
function copyNarrative() {{
  const rows = activeDomain === 'all'
    ? NARRATIVE
    : NARRATIVE.filter(r => inferDomain(r.destination) === activeDomain);
  const byDate = {{}};
  rows.forEach(r => {{ if (!byDate[r.date]) byDate[r.date] = []; byDate[r.date].push(r); }});
  const lines = ['# Sweep — Narrative'];
  for (const [d, dayRows] of Object.entries(byDate).sort()) {{
    lines.push('', `## ${{d}}`, '', '| Section | Summary | Destination |', '|---|---|---|');
    dayRows.forEach(r => {{ lines.push(`| ${{r.section}} | ${{r.summary}} | ${{normDest(r.destination)}} |`); }});
  }}
  const md = lines.join('\\n');
  navigator.clipboard.writeText(md).then(() => {{
    const btn = document.getElementById('copy-btn');
    const orig = btn.textContent;
    btn.textContent = '✓ Copied';
    setTimeout(() => btn.textContent = orig, 1500);
  }}).catch(() => {{
    const w = window.open('');
    if (w) w.document.write('<pre>' + md.replace(/</g, '&lt;') + '</pre>');
  }});
}}

// ── Unified diff parser ────────────────────────────────────────────────────
function parseDiff(text) {{
  const files = [];
  let cur = null;
  let leftN = 0, rightN = 0;
  const lines = text.split('\\n');
  for (let i = 0; i < lines.length; i++) {{
    const l = lines[i];
    if (l.startsWith('diff --git ')) {{
      if (cur) files.push(cur);
      cur = {{ filename: '', hunks: [] }};
      continue;
    }}
    if (!cur) continue;
    if (l.startsWith('+++ ')) {{
      // Handle both: `+++ b/path` and `+++ "b/path"` (already decoded by Python)
      let p = l.slice(4).trim();
      if (p.startsWith('"') && p.endsWith('"')) p = p.slice(1, -1);
      if (p.startsWith('b/')) cur.filename = p.slice(2);
      continue;
    }}
    if (l.startsWith('--- ') || l.startsWith('index ') || l.startsWith('new file') || l.startsWith('deleted file') || l.startsWith('old mode') || l.startsWith('new mode')) continue;
    if (l.startsWith('@@')) {{
      const m = l.match(/@@ -(\\d+)(?:,\\d+)? \\+(\\d+)(?:,\\d+)? @@/);
      if (m) {{ leftN = parseInt(m[1]); rightN = parseInt(m[2]); }}
      cur.hunks.push({{ hdr: l, left: [], right: [] }});
      continue;
    }}
    if (!cur.hunks.length) continue;
    const hunk = cur.hunks[cur.hunks.length - 1];
    if (l.startsWith('+')) {{
      hunk.right.push({{ n: rightN++, c: l.slice(1) }});
    }} else if (l.startsWith('-')) {{
      hunk.left.push({{ n: leftN++, c: l.slice(1) }});
    }} else {{
      hunk.left.push({{ n: leftN++, c: l.slice(1) }});
      hunk.right.push({{ n: rightN++, c: l.slice(1) }});
    }}
  }}
  if (cur) files.push(cur);
  return files;
}}

// ── Side-by-side renderer ──────────────────────────────────────────────────
function esc(s) {{
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

function renderHunk(hunk) {{
  const llen = hunk.left.length, rlen = hunk.right.length;
  const total = Math.max(llen, rlen);
  let leftRows = '', rightRows = '';

  for (let i = 0; i < total; i++) {{
    const l = i < llen ? hunk.left[i] : null;
    const r = i < rlen ? hunk.right[i] : null;
    const isCtx = l && r && l.c === r.c;
    const lCls = isCtx ? 'ctx' : (l ? 'del' : 'ctx');
    const rCls = isCtx ? 'ctx' : (r ? 'add' : 'ctx');
    leftRows  += `<div class="row ${{lCls}}"><span class="ln">${{l ? l.n : ''}}</span><span class="lc">${{l ? esc(l.c) : ''}}</span></div>`;
    rightRows += `<div class="row ${{rCls}}"><span class="ln">${{r ? r.n : ''}}</span><span class="lc">${{r ? esc(r.c) : ''}}</span></div>`;
  }}

  return `
    <div class="sbs">
      <div class="sbs-col">
        <div class="col-hdr">Before</div>
        <div class="row hdr"><span class="ln"></span><span class="lc">${{esc(hunk.hdr)}}</span></div>
        ${{leftRows}}
      </div>
      <div class="sbs-col">
        <div class="col-hdr">After</div>
        <div class="row hdr"><span class="ln"></span><span class="lc">${{esc(hunk.hdr)}}</span></div>
        ${{rightRows}}
      </div>
    </div>`;
}}

function renderDiffFiles(files) {{
  const sidebar = document.getElementById('sidebar');
  const diff = document.getElementById('diff');

  sidebar.innerHTML = files.map((f, fi) => {{
    const adds = f.hunks.reduce((s, h) => s + h.right.length, 0);
    const dels = f.hunks.reduce((s, h) => s + h.left.length, 0);
    const isAdd = adds > 0 && dels === 0;
    const isDel = dels > 0 && adds === 0;
    const badge = isAdd ? `<span class="badge ba">+${{adds}}</span>` :
                  isDel ? `<span class="badge bd">-${{dels}}</span>` :
                          `<span class="badge bm">~</span>`;
    const name = (f.filename || '(unknown)').split('/').pop() || f.filename || '(unknown)';
    return `<div class="fi" id="nav-${{fi}}" onclick="scrollToFile(${{fi}});setActive(${{fi}})">${{badge}}<span class="name" title="${{esc(f.filename || '')}}">${{esc(name)}}</span></div>`;
  }}).join('');

  diff.innerHTML = files.map((f, fi) => {{
    const adds = f.hunks.reduce((s, h) => s + h.right.length, 0);
    const dels = f.hunks.reduce((s, h) => s + h.left.length, 0);
    const hunksHtml = f.hunks.map(renderHunk).join('');
    const displayName = f.filename || '(unknown file)';
    return `<div class="fd" id="file-${{fi}}">
      <div class="fdh">
        <span class="fn">${{esc(displayName)}}</span>
        <span><span style="color:#3fb950">+${{adds}}</span> <span style="color:#f85149">-${{dels}}</span></span>
      </div>
      ${{hunksHtml}}
    </div>`;
  }}).join('');
}}

function scrollToFile(fi) {{
  const el = document.getElementById('file-' + fi);
  if (el) el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
}}
function setActive(fi) {{
  document.querySelectorAll('.fi').forEach(e => e.classList.remove('active'));
  const el = document.getElementById('nav-' + fi);
  if (el) el.classList.add('active');
}}

// ── Init ──────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {{
  const statLines = STAT_TEXT.trim().split('\\n');
  document.getElementById('stat-line').textContent = statLines[statLines.length - 1] || '';

  // Date range from swept Calendar filenames (YYYYMMDD.md)
  const calDates = CHANGED_CALENDAR_FILES
    .map(f => {{ const m = f.match(/(\\d{{8}})\\.md$/); return m ? m[1] : null; }})
    .filter(Boolean).sort();
  if (calDates.length > 0) {{
    const fmt = d => `${{d.slice(0,4)}}-${{d.slice(4,6)}}-${{d.slice(6,8)}}`;
    const rangeStr = calDates.length === 1
      ? fmt(calDates[0])
      : `${{fmt(calDates[0])}} → ${{fmt(calDates[calDates.length - 1])}}`;
    document.getElementById('date-range').textContent = rangeStr;
  }}

  renderNarrative();

  allParsedFiles = parseDiff(DIFF_TEXT);
  renderDiffFiles(allParsedFiles);
}});
</script>
<div id="modal-overlay" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-hdr">
      <span class="modal-title" id="modal-title"></span>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-body" id="modal-body"></div>
  </div>
</div>
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


# ---------------------------------------------------------------------------
# scan_sweep_runs — used by dashboard.py to populate the Sweep Reviews tab
# ---------------------------------------------------------------------------

def scan_sweep_runs(root: Path) -> list[dict]:
    """Return metadata for all sweep runs, newest first."""
    sweeps = root / "sweeps"
    if not sweeps.exists():
        return []
    runs = []
    for snap in sorted(sweeps.glob("*.snapshot.html"), reverse=True):
        m = re.match(r'(\d{4}-\d{2}-\d{2})-(\d+)\.snapshot', snap.stem)
        if not m:
            continue
        date_str, run_n = m.group(1), int(m.group(2))
        run_id = f"{date_str}-{run_n:02d}"
        review_path = sweeps / f"{run_id}.review.html"
        comment_files = sorted(sweeps.glob(f"{run_id}-r*.comments.jsonl"))
        sha = ""
        stats = ""
        try:
            content = snap.read_text(encoding="utf-8", errors="replace")
            sha_m = re.search(r'sha:\s*([0-9a-f]{7,40})', content)
            if sha_m:
                sha = sha_m.group(1)[:7]
            stat_m = re.search(r'const STAT_TEXT = "([^"]+)"', content)
            if stat_m:
                raw = stat_m.group(1).replace("\\n", "\n").replace("\\t", "\t")
                stats = raw.split("\n")[0].strip()
        except Exception:
            pass
        runs.append({
            "run_id": run_id,
            "date": date_str,
            "run_n": run_n,
            "sha": sha,
            "stats": stats,
            "has_review": review_path.exists(),
            "comment_rounds": len(comment_files),
        })
    return runs
