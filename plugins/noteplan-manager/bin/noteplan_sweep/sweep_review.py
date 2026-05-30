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
from datetime import date, datetime, timezone
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

    html = _build_snapshot_html(run_id, date_str, sweep_sha, stat_text, diff_text,
                                seed_comments, narrative, changed_calendar_files,
                                base_commit=base_commit)
    out_path = sweeps / f"{run_id}.snapshot.html"
    out_path.write_text(html, encoding="utf-8")
    utils.log(f"sweep-review-generate: wrote {out_path}  (range: {base_commit[:7]}..HEAD)")


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
    base_commit: str | None = None,
    pre_classification: list | None = None,
    cross_row_issues: list | None = None,
) -> str:
    seed_json = json.dumps(seed_comments, indent=2)
    narrative_json = json.dumps(narrative or [], indent=2)
    changed_cal_json = json.dumps(changed_calendar_files or [], indent=2)
    pre_classification_json = json.dumps(pre_classification or [], indent=2)
    cross_row_issues_json = json.dumps(cross_row_issues or [], indent=2)
    base_commit_comment = f"<!-- base_commit: {base_commit} -->" if base_commit else ""
    return f"""<!DOCTYPE html>
{base_commit_comment}
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
.domain-chip,.type-chip{{padding:3px 10px;border-radius:12px;cursor:pointer;font-size:12px;background:#21262d;color:#8b949e;border:1px solid #30363d}}
.domain-chip.active{{background:#1a3a28;color:#3fb950;border-color:#3fb950}}
.type-chip.active{{background:#1c2128;color:#e6edf3;border-color:#58a6ff}}
.toggle-chip{{padding:3px 10px;border-radius:12px;cursor:pointer;font-size:11px;background:#21262d;color:#484f58;border:1px dashed #30363d}}
.toggle-chip.on{{color:#8b949e;border-color:#484f58}}
.filter-sep{{color:#30363d;font-size:14px;margin:0 2px}}
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
.modal-body{{flex:1;min-height:0;padding:16px;display:grid;grid-template-columns:1fr 1fr;gap:16px;overflow:hidden}}
.modal-body>div{{min-width:0;overflow-y:auto;overflow-x:hidden;display:flex;flex-direction:column}}
.modal-panel-hdr{{font-size:11px;font-weight:600;color:#8b949e;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #30363d}}
.modal-empty{{color:#484f58;font-size:12px;padding:16px;text-align:center}}
.diff-lines{{font-family:'SF Mono','Fira Code',monospace;font-size:11.5px;line-height:18px;overflow-x:auto;flex:1}}
.diff-line{{padding:1px 8px;white-space:pre;font-family:'SF Mono','Fira Code',monospace;font-size:11.5px;line-height:18px}}
.diff-line.removed{{background:#4a0f1a;color:#ffdcd7}}
.diff-line.added{{background:#0e4429;color:#aff5b4}}
.diff-line.new-content{{background:#1f1200;color:#e3b341}}
.diff-line.cross-moved{{background:#0d1b2a;color:#79c0ff}}
.modal-panel-tabs{{display:flex;gap:4px;margin-bottom:8px}}
.mpanel-tab{{padding:2px 10px;border-radius:4px;cursor:pointer;font-size:11px;background:#21262d;color:#8b949e;border:1px solid #30363d}}
.mpanel-tab.active{{background:#1a3a28;color:#3fb950;border-color:#3fb950}}
.mpanel-tab.new-tab.active{{background:#2d1f00;color:#e3b341;border-color:#e3b341}}
.mpanel-tab.cross-tab.active{{background:#0d1b2a;color:#79c0ff;border-color:#79c0ff}}
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
.row.add{{background:#0e4429}}.row.add .ln{{background:#0a3320;color:#3fb950}}.row.add .lc{{color:#aff5b4}}
.row.del{{background:#1a0a0f}}.row.del .ln{{background:#120508;color:#6e3a44}}.row.del .lc{{color:#6b7280}}
.row.ctx{{background:#0d1117}}
.row.hdr{{background:#1c2128}}.row.hdr .lc{{color:#8b949e}}
.diff-ctx-hdr{{font-family:'SF Mono','Fira Code',monospace;font-size:11px;padding:4px 8px 2px;color:#58a6ff;font-weight:600;background:#0d1117;border-top:1px solid #21262d;margin-top:6px}}
.diff-ctx-skip{{font-family:'SF Mono','Fira Code',monospace;font-size:11px;padding:0 8px 4px;color:#484f58;background:#0d1117}}
.line-no{{color:#484f58;font-size:10px;min-width:30px;display:inline-block;text-align:right;padding-right:8px;user-select:none;flex-shrink:0}}
.pair-highlight{{background:rgba(255,255,255,0.06)!important;outline:1px solid rgba(255,255,255,0.15);z-index:1;position:relative}}
[data-pair-id]{{cursor:pointer}}
.move-badge{{margin-left:6px;padding:0 5px;border-radius:3px;font-size:10px;background:#1a3a28;color:#3fb950;border:1px solid #3fb950;text-decoration:none;white-space:nowrap;flex-shrink:0}}
.move-badge:hover{{background:#204830}}
.lost-badge{{margin-left:6px;padding:0 5px;border-radius:3px;font-size:10px;background:#2d0a0a;color:#f85149;border:1px solid #f85149;white-space:nowrap;flex-shrink:0}}
.row.add .lc{{color:#aff5b4}}.row.del .lc{{color:#ffdcd7}}
/* ── Narrative panel ── */
#narrative{{padding:16px}}
.day-block{{margin-bottom:24px}}
.day-hdr{{font-size:14px;font-weight:600;color:#58a6ff;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #30363d}}
.nav-tbl{{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed}}
.nav-tbl th{{background:#161b22;padding:6px 10px;text-align:left;color:#8b949e;font-weight:500;border-bottom:2px solid #30363d;position:sticky;top:0;z-index:1}}
.nav-tbl th:nth-child(1){{width:28px}}.nav-tbl th:nth-child(2){{width:50px}}.nav-tbl th:nth-child(3){{width:18%}}.nav-tbl th:nth-child(4){{width:22%}}.nav-tbl th:nth-child(5){{width:88px}}.nav-tbl th:nth-child(6){{width:auto}}.nav-tbl th:nth-child(7){{width:44px}}
.src-col{{color:#58a6ff;font-family:monospace;font-size:11px;white-space:nowrap}}
.row-badge{{display:inline-block;font-size:11px;min-width:16px;text-align:center;border-radius:3px;padding:1px 4px;font-weight:600}}
.rb-move{{background:#1a3a28;color:#3fb950}}.rb-lost{{background:#2d0a0a;color:#f85149}}.rb-went-to{{background:#001730;color:#58a6ff}}.rb-untraced{{background:#1a1a00;color:#e3b341}}.rb-empty{{background:#1c2128;color:#484f58}}.rb-pending{{color:#484f58}}
.nav-tbl td{{padding:5px 10px;border-bottom:1px solid #21262d;vertical-align:middle;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.nav-tbl tr:hover td{{background:#161b22}}
.nav-tbl .section-col{{color:#e6edf3;font-weight:500}}
.nav-tbl .summary-col{{color:#8b949e}}
.day-sep-row td{{background:#0d1117;padding:14px 10px 5px;font-size:13px;font-weight:600;color:#58a6ff;border-bottom:1px solid #30363d;white-space:normal;overflow:visible}}
.src-sep-row td{{background:#0a0f1a;padding:4px 10px 3px;font-size:10px;font-weight:500;color:#3d6a9e;border-bottom:1px solid #1c2128;font-family:monospace;white-space:nowrap;overflow:visible}}
.item-row td{{background:#0a0d12;padding:3px 10px;border-bottom:1px solid #161b22;font-size:11px}}
.item-row:hover td{{background:#0d1117}}
.item-row .item-text{{color:#c9d1d9;font-family:'SF Mono','Fira Code',monospace;padding-left:20px}}
.sec-toggle{{padding:0 5px 0 0;background:none;border:none;color:#484f58;cursor:pointer;font-size:9px;vertical-align:middle}}
.sec-toggle:hover{{color:#8b949e}}
.empty{{color:#484f58;padding:24px;text-align:center}}
/* ── Validation ── */
.row-warn{{display:inline-block;font-size:10px;margin-left:4px;color:#e3b341;cursor:help;vertical-align:middle}}
#validation-banner{{padding:6px 16px;font-size:12px;border-bottom:1px solid #30363d;display:none}}
#validation-banner.ok{{background:#0e2a14;color:#3fb950;display:block}}
#validation-banner.warn{{background:#2d1f00;color:#e3b341;display:block}}
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
  <span class="filter-sep">|</span>
  <span style="font-size:11px;color:#484f58;margin-right:2px">Type:</span>
  <button class="type-chip active" data-type="all" onclick="setType('all')" title="Show all rows">All</button>
  <button class="type-chip" data-type="move" onclick="setType('move')" title="Move — all source lines confirmed at destination">→ Move</button>
  <button class="type-chip" data-type="went-to" onclick="setType('went-to')" title="Went to — source lines found in a different file than the breadcrumb destination">⇢ Went to</button>
  <button class="type-chip" data-type="lost" onclick="setType('lost')" title="Absent — source lines not found in any diff addition">✗ Absent</button>
  <button class="type-chip" data-type="anomaly" onclick="setType('anomaly')" title="Untraced — destination has additions with no traceable source row">? Untraced</button>
  <button class="type-chip" data-type="empty" onclick="setType('empty')" title="Empty — no source content found or destination file is empty">· Empty</button>
  <button class="toggle-chip" id="empty-toggle" onclick="toggleEmpty()" title="Empty rows have no content to verify — toggle to show/hide them in All view">· Empty: hidden</button>
  <button class="copy-btn" id="copy-btn" onclick="copyNarrative()">📋 Copy</button>
</div>
<div id="layout">
  <nav id="sidebar" style="display:none"></nav>
  <main id="main">
    <div id="validation-banner"></div>
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
const PRE_CLASSIFICATION = {pre_classification_json};
const CROSS_ROW_ISSUES = {cross_row_issues_json};

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
// ── Expandable section rows ────────────────────────────────────────────────
// rowIdx       — breadcrumb idx (PRE_CLASSIFICATION lookup)
// btn          — the toggle button DOM element
// outcomeIdx   — optional: when set, expand only that outcome's lines (per-row
//                view from #97). Without it, expand the full breadcrumb (legacy
//                non-split tables and old snapshots).
function toggleSectionItems(rowIdx, btn, outcomeIdx) {{
  const parentKey = (outcomeIdx == null) ? String(rowIdx) : `${{rowIdx}}-${{outcomeIdx}}`;
  const existing = document.querySelectorAll(`tr.item-row[data-parent="${{parentKey}}"]`);
  if (existing.length) {{
    existing.forEach(r => r.remove());
    btn.textContent = '▶';
    return;
  }}
  const row = MODAL_ROWS[rowIdx];
  if (!row) return;

  // Python-primary: read line_statuses from PRE_CLASSIFICATION. Each source line is
  // classified at compile time as 'move' / 'went-to' / 'absent' — JS only renders.
  const _pyc = (PRE_CLASSIFICATION || []).find(pc => pc.idx === rowIdx);
  const _lineStatuses = _pyc?.line_statuses || {{}};
  // Per-outcome expand (#97): show only the lines for the specific outcome
  // owning this toggle button. Falls back to full breadcrumb aggregation when
  // outcomeIdx is unset (legacy non-split rendering).
  let allSrcLines;
  if (_pyc && outcomeIdx != null && _pyc.outcomes && _pyc.outcomes[outcomeIdx]) {{
    allSrcLines = (_pyc.outcomes[outcomeIdx].lines || [])
      .filter(l => l.trim() && !isNoiseLine(l));
  }} else {{
    allSrcLines = _pyc ? [
      ...(_pyc.moved_lines      || []),
      ...(_pyc.truly_lost_lines || []),
      ...Object.values(_pyc.went_to_details || {{}}).flat(),
    ].filter(l => l.trim() && !isNoiseLine(l)) : [];
  }}
  if (!allSrcLines.length) {{ btn.textContent = '○'; return; }}
  btn.textContent = '▼';
  // Anchor expanded items right after the row that owns this toggle button.
  const parentRow = btn.closest('tr') || document.querySelector(`tr[data-row-idx="${{rowIdx}}"]`);
  if (!parentRow) return;
  let insertAfter = parentRow.nextSibling?.dataset?.mixedLostFor === String(rowIdx)
    ? parentRow.nextSibling : parentRow;
  for (const line of allSrcLines) {{
    const clean = line.replace(/^-\\s*\\[[x ]\\]\\s*/i, '').replace(/^-\\s+/, '').trim();
    if (!clean) continue;
    const status = _lineStatuses[normLine(line)] || 'absent';
    const badge = status === 'move'
      ? `<span style="color:#3fb950;font-size:9px;margin-right:4px">→</span>`
      : status === 'went-to'
        ? `<span style="color:#58a6ff;font-size:9px;margin-right:4px">⇢</span>`
        : `<span style="color:#f85149;font-size:9px;margin-right:4px">✗</span>`;
    const color = status === 'move' ? '' : status === 'went-to' ? 'color:#58a6ff;opacity:0.8;' : 'color:#f85149;opacity:0.8;';
    const tr = document.createElement('tr');
    tr.className = 'item-row';
    tr.dataset.parent = parentKey;
    tr.innerHTML = `<td class="sec-toggle" style="color:#30363d;text-align:right">↳</td><td></td><td class="item-text" colspan="3" style="${{color}}">${{badge}}${{esc(clean)}}</td><td></td><td></td>`;
    insertAfter.insertAdjacentElement('afterend', tr);
    insertAfter = tr;
  }}
}}

function closeModal() {{
  document.getElementById('modal-overlay').classList.remove('open');
  const scopeEl = document.getElementById('modal-scope');
  if (scopeEl) scopeEl.style.display = 'none';
}}

document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeModal(); }});

// Classify destination added lines as "moved" (matches source) or "new" (no match)
// Shared normaliser: strip date tags + hashtags, collapse whitespace, lowercase
const normLine = s => s.replace(/>\\d{{4}}-\\d{{2}}-\\d{{2}}/g, '').replace(/#\\w+/g, '').replace(/\\s+/g, ' ').trim().toLowerCase();
const bodyText = s => s.replace(/^[-*]\\s*\\[[x ]\\]\\s*/i, '').trim();

// Noise filter — shared by classifyRow and showSectionModal
const isNoiseLine = line => {{
  if (/^#+\\s/.test(line.trim())) return true;          // markdown headings never move
  const n = normLine(line);
  if (n.length <= 3) return true;
  if (/^`+(\\w*)$/.test(n)) return true;
  if (/^-{{2,}}$/.test(n) || /^—{{1,}}$/.test(n)) return true;
  if (/^[-*]\\s*\\[\\s*\\]\\s*$/.test(n)) return true;
  return false;
}};

// Row classification cache: idx → {{type, movedCount, newCount}}
const _rowClassifications = new Map();
// Layer 2: row-level validation issues
const _rowValidation = new Map(); // idx → [issue strings]
// Layer 4: cross-row issues
const _crossRowIssues = [];

const _badgeLabels   = {{ move: '→', 'went-to': '⇢', lost: '✗', anomaly: '?', untraced: '?', empty: '·' }};
// Internal type 'anomaly' maps to CSS class 'rb-untraced' and label '?'
const _badgeCls      = {{ anomaly: 'untraced', 'went-to': 'went-to' }};
const _badgeTitles   = {{
  move:       'Move — all source lines confirmed at destination',
  'went-to':  'Went to — source lines found in a different file than the breadcrumb destination',
  lost:       'Absent — source lines not found in any diff addition',
  anomaly:    'Untraced — destination has additions with no traceable source row',
  untraced:   'Untraced — destination has additions with no traceable source row',
  empty:      'Empty — nothing to verify',
}};

function updateRowBadge(idx, classification) {{
  const tr = document.querySelector(`tr[data-row-idx="${{idx}}"]`);
  if (!tr) return;
  // #97 — per-outcome rows render their badges at compile time. Skip aggregate
  // updates so we don't overwrite per-row truth.
  if (tr.dataset.outcomeRendered === 'true') return;
  const badge = tr.querySelector('.row-badge');
  if (!badge) return;
  classification = classification || _rowClassifications.get(idx);
  if (!classification) return;
  const {{ type, movedCount, lostCount, newCount }} = classification;
  const blocks = classification.blocks || [];
  // Compound Lost: some lines moved, some lost — render →N ✗M badge, type stays 'lost'
  if (blocks.length > 1) {{
    badge.className = 'row-badge rb-lost';
    badge.textContent = blocks.map(b => (_badgeLabels[b.type] || '?') + b.count).join(' ');
    const moveBlock = blocks.find(b => b.type === 'move');
    const lostBlock = blocks.find(b => b.type === 'lost');
    badge.title = `Absent — ${{moveBlock?.count ?? 0}} moved, ${{lostBlock?.count ?? 0}} absent from diff`;
    badge.style.cursor = 'pointer';
    badge.onclick = (e) => {{ e.stopPropagation(); showSectionModal(idx); }};
    const mbCountCell = tr.querySelector('.count-col');
    if (mbCountCell) {{
      mbCountCell.textContent = blocks.map(b => b.count).join('+');
      mbCountCell.title = blocks.map(b => `${{b.count}} ${{b.type}}`).join(', ');
      mbCountCell.style.color = '#f85149';
    }}
    const mbDestCell = tr.querySelector('.dest-col');
    if (mbDestCell) {{
      mbDestCell.style.opacity = '0.45';
      mbDestCell.title = 'Intended destination — some lines NOT confirmed moved here';
    }}
    tr.dataset.rowType = 'lost';
    if (activeType !== 'all' && activeType !== 'lost') tr.style.display = 'none';
    return;
  }}
  // Single-block path
  const displayType = type;
  const badgeCls = _badgeCls[displayType] || displayType;
  badge.className = `row-badge rb-${{badgeCls}}`;
  badge.textContent = _badgeLabels[displayType] || '?';
  const misroutedCount = classification.misroutedCount || 0;
  let counts = '';
  if (type === 'move')        counts = ` (${{movedCount}} line${{movedCount!==1?'s':''}} moved)`;
  else if (type === 'went-to') counts = ` (${{misroutedCount}} line${{misroutedCount!==1?'s':''}} found elsewhere)`;
  else if (type === 'lost')   counts = ` (${{lostCount}} line${{lostCount!==1?'s':''}} absent from diff)`;
  else if (type === 'anomaly') counts = newCount ? ` (${{newCount}} unexpected)` : '';
  const wentToFiles = classification.wentToFiles || [];
  const wentToDetail = (type === 'went-to' && wentToFiles.length > 0)
    ? ' → ' + wentToFiles.map(f => f.split('/').pop().replace(/\.md$/, '')).join(', ') : '';
  const emptyDetail = (displayType === 'empty' && classification.emptyReason)
    ? ` — ${{classification.emptyReason}}` : '';
  badge.title = (_badgeTitles[displayType] || displayType) + counts + wentToDetail + emptyDetail;
  // Mark destination cell for lost/empty rows; went-to keeps full opacity (the dest is context, not verdict)
  const destCell = tr.querySelector('.dest-col');
  if (destCell) {{
    if (type === 'lost' || type === 'empty') {{
      destCell.style.opacity = '0.45';
      destCell.title = 'Intended destination — content was NOT confirmed moved here';
    }} else if (type === 'went-to') {{
      destCell.style.opacity = '0.65';
      destCell.title = 'Breadcrumb destination — content arrived at a different file';
    }} else {{
      destCell.style.opacity = '';
      destCell.title = destCell.querySelector('a')?.textContent || '';
    }}
  }}
  // Populate count cell
  const countCell = tr.querySelector('.count-col');
  if (countCell) {{
    if (type === 'move')         {{ countCell.textContent = movedCount; countCell.title = `${{movedCount}} lines moved`; countCell.style.color = '#3fb950'; }}
    else if (type === 'went-to') {{ countCell.textContent = misroutedCount; countCell.title = `${{misroutedCount}} lines found elsewhere`; countCell.style.color = '#58a6ff'; }}
    else if (type === 'lost')    {{ countCell.textContent = lostCount; countCell.title = `${{lostCount}} lines absent from diff`; countCell.style.color = '#f85149'; }}
    else if (type === 'anomaly') {{ countCell.textContent = newCount ? `+${{newCount}}` : '+?'; countCell.title = `${{newCount}} unexpected lines`; countCell.style.color = '#e3b341'; }}
    else                          {{ countCell.textContent = '·'; countCell.style.color = '#484f58'; }}
  }}
  // Lost/went-to/anomaly/empty badges are clickable — open the modal directly
  if (displayType === 'lost' || displayType === 'went-to' || displayType === 'anomaly' || displayType === 'empty') {{
    badge.style.cursor = 'pointer';
    badge.onclick = (e) => {{ e.stopPropagation(); showSectionModal(idx); }};
  }} else {{
    badge.style.cursor = '';
    badge.onclick = null;
  }}
  tr.dataset.rowType = displayType;
  tr.style.display = isRowVisible(displayType) ? '' : 'none';
}}

// ── Row integrity warnings (from Python PRE_CLASSIFICATION.issues[]) ──────
function annotateRowWarnings(idx, issues) {{
  if (!issues || !issues.length) return;
  _rowValidation.set(idx, issues);
  const tr = document.querySelector(`tr[data-row-idx="${{idx}}"]`);
  if (!tr) return;
  // Insert ⚠ span next to the badge, avoid duplicates
  if (tr.querySelector('.row-warn')) return;
  const badgeCell = tr.querySelector('td:first-child');
  if (!badgeCell) return;
  const span = document.createElement('span');
  span.className = 'row-warn';
  span.textContent = '⚠';
  span.title = issues.join('\\n');
  badgeCell.appendChild(span);
}}

// ── Validation banner (reads Python-embedded CROSS_ROW_ISSUES + _rowValidation) ──
function updateValidationBanner() {{
  const banner = document.getElementById('validation-banner');
  if (!banner) return;
  const rowWarnCount = _rowValidation.size;
  const crossCount = CROSS_ROW_ISSUES.length;

  // Outcome summary across all rows (derived from PRE_CLASSIFICATION outcomes).
  const outcomeCounts = {{move: 0, 'went-to': 0, lost: 0, anomaly: 0, empty: 0}};
  for (const pc of (PRE_CLASSIFICATION || [])) {{
    for (const o of (pc.outcomes || [])) {{
      if (o.kind in outcomeCounts) outcomeCounts[o.kind]++;
    }}
  }}
  const summary = `→${{outcomeCounts.move}} ⇢${{outcomeCounts['went-to']}} ⌀${{outcomeCounts.lost}} ?${{outcomeCounts.anomaly}}`;

  if (rowWarnCount === 0 && crossCount === 0) {{
    banner.className = 'ok';
    banner.textContent = `✓ All rows validated — no integrity issues found  ·  ${{summary}}`;
  }} else {{
    const parts = [];
    if (rowWarnCount) parts.push(`${{rowWarnCount}} row${{rowWarnCount !== 1 ? 's' : ''}} with integrity warnings (V-R)`);
    if (crossCount)   parts.push(`${{crossCount}} cross-row consistency issue${{crossCount !== 1 ? 's' : ''}} (V-C) — some destination lines may be double-claimed`);
    banner.className = 'warn';
    banner.textContent = `⚠ ${{parts.join(' · ')}}  ·  ${{summary}}`;
  }}
}}

function _showSectionModalFromPython(idx, row, _pyc, focusLost) {{
  // ── Python-primary modal rendering ─────────────────────────────────────────
  // Renders entirely from PRE_CLASSIFICATION data — no JS re-classification.
  // Called when _pyc has moved_lines/dest_lines/truly_lost_lines content.
  const sectionName = row.section.replace(/^#+\\s*/, '').trim();
  const destRaw     = row.destination.replace(/\\[\\[([^\\]]+)\\]\\]/g, '$1').trim().replace(/\\.md$/, '');
  const destShort   = destRaw.split('/').pop();
  const srcShort    = row.source_file.split('/').pop();
  const srcName     = `<span style="color:#e6edf3;font-family:monospace;font-size:11px">${{esc(srcShort)}}</span>`;

  const movedLines     = _pyc.moved_lines      || [];
  const destLines      = _pyc.dest_lines       || [];
  const trulyLostLines = _pyc.truly_lost_lines || [];
  const wentToDetails  = _pyc.went_to_details  || {{}};
  const rowType        = _pyc.type || 'empty';
  const issues         = _pyc.issues || [];
  const isMixed        = movedLines.length > 0 && trulyLostLines.length > 0;
  const isFocusAnomaly = (rowType === 'anomaly');
  const isFocusWentTo  = (rowType === 'went-to');
  // Mixed rows (some moved, some lost) need two-panel mode to show both — focusLost only
  // for explicit user request OR pure-lost rows OR empty rows.
  const isFocusLost    = !isFocusAnomaly && !isMixed && (focusLost || rowType === 'lost' || rowType === 'empty');

  // ── Source panel ──────────────────────────────────────────────────────────
  let srcBody;
  if (rowType === 'empty') {{
    const reason = issues.join(', ') || 'no content found';
    srcBody = `<div class="diff-lines"><div style="color:#e3b341;padding:12px 0">⚠ ${{esc(reason)}}<br><br>Cannot verify this row — open the source file to inspect manually.</div></div>`;
  }} else if (isFocusAnomaly) {{
    // Anomaly: dest additions with no traceable source — single-column display
    const anomalyHtml = destLines.map(l => `<div class="diff-line new-content">${{esc(l)}}</div>`).join('')
      || `<div class="modal-empty" style="color:#6e7681">No unexpected lines.</div>`;
    srcBody = `<div class="diff-lines">` +
      `<div style="color:#e3b341;font-size:11px;font-weight:600;padding:2px 0 6px">? ${{destLines.length}} unexpected line${{destLines.length !== 1 ? 's' : ''}} — appeared in destination without a matching source row</div>` +
      anomalyHtml + `</div>`;
  }} else {{
    // ⇢ Went-to banner (from went_to_details)
    let wentToHtml = '';
    const wentToStems = Object.keys(wentToDetails);
    if (wentToStems.length > 0) {{
      const _items = wentToStems.map(stem => {{
        const lines = wentToDetails[stem] || [];
        const linesHtml = lines.map(l => `<div class="diff-line" style="font-family:monospace;font-size:10px;color:#8b949e;padding:1px 0 1px 8px">${{esc(l)}}</div>`).join('');
        return `<details style="margin-top:4px"><summary style="color:#58a6ff;font-family:monospace;font-size:11px;cursor:pointer;list-style:none">${{esc(stem)}} — ${{lines.length}} line${{lines.length!==1?'s':''}} found ▸</summary>${{linesHtml}}</details>`;
      }}).join('');
      wentToHtml = `<div class="v-r6-banner" style="margin:4px 0 8px;padding:6px 8px;background:#001730;border-left:2px solid #58a6ff;border-radius:3px">` +
        `<div style="color:#58a6ff;font-size:11px;font-weight:600">⇢ Content arrived at a different destination</div>` +
        `<div style="color:#8b949e;font-size:10px;margin-top:2px">Source lines were found in a file other than <strong>${{esc(destShort)}}</strong>.</div>` +
        _items + `</div>`;
    }} else if (isFocusWentTo && (_pyc.went_to_files || []).length > 0) {{
      const _items2 = (_pyc.went_to_files || []).map(stem =>
        `<details style="margin-top:4px"><summary style="color:#58a6ff;font-family:monospace;font-size:11px;cursor:pointer;list-style:none">${{esc(stem)}} ▸</summary></details>`
      ).join('');
      wentToHtml = `<div class="v-r6-banner" style="margin:4px 0 8px;padding:6px 8px;background:#001730;border-left:2px solid #58a6ff;border-radius:3px">` +
        `<div style="color:#58a6ff;font-size:11px;font-weight:600">⇢ Content arrived at a different destination</div>` +
        `<div style="color:#8b949e;font-size:10px;margin-top:2px">Source lines found in a different file than the breadcrumb destination.</div>` +
        _items2 + `</div>`;
    }}
    // Confirmed moved (green border)
    const movedHtml = movedLines.map(l =>
      `<div class="diff-line removed" style="border-left:2px solid #3fb950">${{esc(l)}}</div>`
    ).join('');
    // Absent (red)
    const absentHtml = trulyLostLines.map(l => `<div class="diff-line removed">${{esc(l)}}</div>`).join('');
    const absentSection = trulyLostLines.length > 0
      ? `<div style="margin-top:8px;border-top:1px solid #30363d;padding-top:6px">` +
        (isMixed
          ? `<div style="color:#e3b341;font-size:11px;font-weight:600;padding:2px 0 6px">⚡ ✗ Absent (${{trulyLostLines.length}} line${{trulyLostLines.length>1?'s':''}}) — ⌀ no destination — these lines were not added anywhere in the diff</div>`
          : `<div style="color:#f85149;font-size:10px;padding:2px 0 4px">✗ ${{trulyLostLines.length}} line${{trulyLostLines.length>1?'s':''}} — ⌀ no destination (absent from diff additions)</div>`) +
        absentHtml + `</div>`
      : '';

    if (isFocusWentTo) {{
      const allSrc = [...movedLines, ...trulyLostLines, ...Object.values(wentToDetails).flat()];
      const allSrcHtml = allSrc.map(l => `<div class="diff-line removed">${{esc(l)}}</div>`).join('')
        || `<div class="modal-empty" style="color:#6e7681">Source lines not found in diff.</div>`;
      srcBody = `<div class="diff-lines">${{wentToHtml}}${{allSrcHtml}}</div>`;
    }} else if (isFocusLost) {{
      const lostHtml = trulyLostLines.map(l => `<div class="diff-line removed">${{esc(l)}}</div>`).join('')
        || `<div class="modal-empty" style="color:#6e7681">No unmatched lines found.</div>`;
      srcBody = `<div class="diff-lines">${{wentToHtml}}${{lostHtml}}</div>`;
    }} else {{
      const movedHeader = isMixed
        ? `<div style="color:#3fb950;font-size:11px;font-weight:600;padding:2px 0 6px">✓ Moved (${{movedLines.length}} line${{movedLines.length!==1?'s':''}}) — arrived at destination</div>`
        : '';
      srcBody = `<div class="diff-lines">${{movedHeader}}${{movedHtml}}${{absentSection}}</div>`;
    }}
  }}
  const srcPanelHdr = isFocusAnomaly
    ? `Untraced additions — <span style="color:#e6edf3;font-family:monospace;font-size:11px">${{esc(destShort)}}</span>`
    : `Removed from source — ${{srcName}}`;
  const srcPanel = `<div><div class="modal-panel-hdr">${{srcPanelHdr}}</div>${{srcBody}}</div>`;

  // ── Dest panel ─────────────────────────────────────────────────────────────
  let destPanel = '';
  if (!isFocusLost && !isFocusWentTo && !isFocusAnomaly && rowType !== 'empty') {{
    const destHdr   = `Added to destination — <span style="color:#e6edf3;font-family:monospace;font-size:11px">${{esc(destShort)}}</span>`;
    const destHtml  = destLines.map(l => `<div class="diff-line new-content">${{esc(l)}}</div>`).join('')
      || `<div class="modal-empty" style="color:#6e7681">No matching additions in destination.</div>`;
    const movedCount = _pyc.moved_count || 0;
    const countLabel = movedCount > 0
      ? `<div class="modal-panel-tabs"><span style="color:#3fb950;font-size:10px">✓ ${{movedCount}} line${{movedCount!==1?'s':''}} confirmed moved</span></div>`
      : `<div class="modal-panel-tabs"><span style="color:#f85149;font-size:10px">✗ 0 lines confirmed moved</span></div>`;
    destPanel = `<div><div class="modal-panel-hdr">${{destHdr}}</div>${{countLabel}}<div class="diff-lines" id="modal-dest-lines">${{destHtml}}</div></div>`;
  }}

  // ── Render + badge ─────────────────────────────────────────────────────────
  const titleSuffix = isFocusAnomaly ? ' — ? Untraced additions'
    : isFocusLost   ? ' — ✗ Absent (⌀ no destination)'
    : isFocusWentTo ? ' ⇢ Arrived elsewhere'
    : ' → ' + normDest(row.destination);
  document.getElementById('modal-title').textContent = sectionName + titleSuffix;
  const scopeEl = document.getElementById('modal-scope');
  if (scopeEl) scopeEl.style.display = 'none';
  const modalBodyEl = document.getElementById('modal-body');
  modalBodyEl.style.gridTemplateColumns = (isFocusLost || isFocusWentTo || isFocusAnomaly) ? '1fr' : '1fr 1fr';
  modalBodyEl.innerHTML = srcPanel + destPanel;
  document.getElementById('modal-overlay').classList.add('open');

  const classification = {{
    type:           rowType,
    movedCount:     _pyc.moved_count     || 0,
    lostCount:      _pyc.lost_count      || 0,
    newCount:       0,
    misroutedCount: _pyc.misrouted_count || 0,
    wentToFiles:    _pyc.went_to_files   || [],
    trulyLostLines: trulyLostLines,
    movedLines:     movedLines,
    destLines:      destLines,
    wentToDetails:  wentToDetails,
    lineStatuses:   _pyc.line_statuses   || {{}},
    emptyReason:    issues.join(', '),
    blocks:         [],
  }};
  if (classification.movedCount > 0) classification.blocks.push({{type: 'move', count: classification.movedCount}});
  if (classification.lostCount  > 0) classification.blocks.push({{type: 'lost',  count: classification.lostCount, lines: trulyLostLines}});
  _rowClassifications.set(idx, classification);
  updateRowBadge(idx, classification);
}}

function showSectionModal(idx, focusLost = false) {{
  const row = MODAL_ROWS[idx];
  if (!row) return;
  // Python-primary: render from PRE_CLASSIFICATION. When pc is missing (no narrative/diff
  // for this idx), synthesize an empty pyc so the modal still opens with a clear message.
  const _pyc = (PRE_CLASSIFICATION || []).find(pc => pc.idx === idx) || {{
    idx, type: 'empty', moved_lines: [], dest_lines: [], truly_lost_lines: [],
    went_to_details: {{}}, line_statuses: {{}}, issues: ['no_pre_classification']
  }};
  _showSectionModalFromPython(idx, row, _pyc, focusLost);
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
let activeType = 'all';
let showEmpty = false; // empty rows hidden by default (42%+ in typical sweeps = noise)

function isRowVisible(rowType) {{
  if (activeType === 'empty') return rowType === 'empty';
  if (activeType !== 'all') return rowType === activeType;
  return rowType !== 'empty' || showEmpty;
}}

function toggleEmpty() {{
  showEmpty = !showEmpty;
  const btn = document.getElementById('empty-toggle');
  if (btn) {{
    btn.textContent = showEmpty ? '· Empty: shown' : '· Empty: hidden';
    btn.classList.toggle('on', showEmpty);
  }}
  setType(activeType);
}}

function setDomain(d) {{
  activeDomain = d;
  activeType = 'all'; // reset type filter on domain change — indices will shift
  document.querySelectorAll('.domain-chip').forEach(c =>
    c.classList.toggle('active', c.dataset.domain === d));
  document.querySelectorAll('.type-chip').forEach(c =>
    c.classList.toggle('active', c.dataset.type === 'all'));
  renderNarrative();
}}

function setType(t) {{
  activeType = t;
  document.querySelectorAll('.type-chip').forEach(c =>
    c.classList.toggle('active', c.dataset.type === t));
  // Show/hide rows by their current classified type (no re-render needed)
  document.querySelectorAll('tr[data-row-idx]').forEach(tr => {{
    const rowType = tr.dataset.rowType || 'pending';
    tr.style.display = isRowVisible(rowType) ? '' : 'none';
  }});
  // Also hide/show day separator rows — hide if all their rows are hidden
  document.querySelectorAll('tr.day-sep-row').forEach(sep => {{
    let next = sep.nextElementSibling;
    let anyVisible = false;
    while (next && !next.classList.contains('day-sep-row')) {{
      if (next.style.display !== 'none' && !next.classList.contains('mixed-lost-sub-row') && !next.classList.contains('src-sep-row')) anyVisible = true;
      next = next.nextElementSibling;
    }}
    sep.style.display = anyVisible ? '' : 'none';
  }});
  // Also hide/show src-sep-row — hide if all following rows (until next sep) are hidden
  document.querySelectorAll('tr.src-sep-row').forEach(sep => {{
    let next = sep.nextElementSibling;
    let anyVisible = false;
    while (next && !next.classList.contains('day-sep-row') && !next.classList.contains('src-sep-row')) {{
      if (next.style.display !== 'none' && !next.classList.contains('mixed-lost-sub-row')) anyVisible = true;
      next = next.nextElementSibling;
    }}
    sep.style.display = anyVisible ? '' : 'none';
  }});
}}

// ── Narrative renderer ─────────────────────────────────────────────────────
function renderNarrative() {{
  const el = document.getElementById('narrative');
  MODAL_ROWS.length = 0;

  if (!NARRATIVE.length) {{
    el.innerHTML = '<div class="empty">No sweep breadcrumb data found.<br>Breadcrumb tables are written to each swept Calendar note.</div>';
    showTab('diff');
    return;
  }}

  const isSepRow = r => /^-+$/.test((r.section || '').trim()) || /^-+$/.test((r.destination || '').trim());

  const rows = (activeDomain === 'all'
    ? NARRATIVE
    : NARRATIVE.filter(r => inferDomain(r.destination) === activeDomain)
  ).filter(r => !isSepRow(r));

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

    tbody += `<tr class="day-sep-row"><td colspan="7">📅 ${{esc(label)}} — ${{dayRows.length}} section${{dayRows.length !== 1 ? 's' : ''}} swept</td></tr>`;

    // Sort within day by source file so rows from the same file are adjacent
    const sortedDayRows = [...dayRows].sort((a, b) => {{
      const sa = a.source_file || '';
      const sb = b.source_file || '';
      return sa < sb ? -1 : sa > sb ? 1 : 0;
    }});

    let lastSrcStem = null;
    tbody += sortedDayRows.map(r => {{
      const idx = MODAL_ROWS.push(r) - 1;
      const srcStem = r.source_file.split('/').pop().replace(/\\.md$/, '');
      const srcUrl = `noteplan://x-callback-url/openNote?filename=${{srcStem}}`;
      let sepRow = '';
      if (srcStem !== lastSrcStem) {{
        if (lastSrcStem !== null) {{
          // thin visual break between source files within the same day
          sepRow = `<tr class="src-sep-row"><td colspan="7">📄 ${{esc(srcStem)}}</td></tr>`;
        }}
        lastSrcStem = srcStem;
      }}
      // #97 — per-outcome row split. Each entry in pyc.outcomes becomes its own
      // <tr> sharing the breadcrumb's modal idx via data-row-idx; siblings are
      // visually grouped under the breadcrumb's section label.
      const _pyc = (PRE_CLASSIFICATION || []).find(pc => pc.idx === idx);
      // Fallback: legacy fixtures (and old snapshots) lack `outcomes`. Synthesize
      // them from legacy fields so the row split renders correctly without a
      // recompile from current Python.
      const _synthOutcomes = (pc) => {{
        if (!pc) return [];
        const out = [];
        if ((pc.moved_lines || []).length) out.push({{ kind: 'move', dest: r.destination, dest_stem: null, lines: pc.moved_lines }});
        const wt = pc.went_to_details || {{}};
        for (const [stem, lines] of Object.entries(wt)) {{
          if ((lines || []).length) out.push({{ kind: 'went-to', dest: stem, dest_stem: stem.toLowerCase(), lines }});
        }}
        if ((pc.truly_lost_lines || []).length) out.push({{ kind: 'lost', dest: null, dest_stem: null, lines: pc.truly_lost_lines }});
        if (pc.type === 'anomaly' && (pc.dest_lines || []).length) {{
          out.push({{ kind: 'anomaly', dest: r.destination, dest_stem: null, lines: pc.dest_lines }});
        }}
        return out;
      }};
      const _outcomes = (_pyc && _pyc.outcomes && _pyc.outcomes.length)
        ? _pyc.outcomes
        : (_synthOutcomes(_pyc).length
            ? _synthOutcomes(_pyc)
            : [{{ kind: 'empty', dest: r.destination, dest_stem: null, lines: [] }}]);
      const _badgeStem = {{ move: 'move', 'went-to': 'went-to', lost: 'lost', anomaly: 'untraced', empty: 'empty' }};
      const _badgeGlyph = {{ move: '→', 'went-to': '⇢', lost: '✗', anomaly: '?', empty: '·' }};
      const _countColor = {{ move: '#3fb950', 'went-to': '#58a6ff', lost: '#f85149', anomaly: '#e3b341', empty: '#484f58' }};
      const _kindTitle = {{
        move:      'Move — lines confirmed at the breadcrumb destination',
        'went-to': 'Went to — lines found at a different file than the breadcrumb claimed',
        lost:      'Absent — lines not found in any diff addition',
        anomaly:   'Untraced — destination has additions with no traceable source',
        empty:     'Empty — nothing to verify for this outcome'
      }};
      // Render N <tr> rows — one per outcome. First row owns the section/source
      // columns; subsequent siblings show "↳" prefix and reduced visual weight.
      const trs = _outcomes.map((o, oi) => {{
        const isFirst = oi === 0;
        const kind    = o.kind || 'empty';
        const lineN   = (o.lines || []).length;
        const badgeCls = _badgeStem[kind] || kind;
        const glyph   = _badgeGlyph[kind] || '·';
        // Per-outcome dest cell.
        let destCellHtml;
        if (kind === 'lost') {{
          destCellHtml = `<span style="color:#f85149" title="Lost lines have no destination">⌀ no destination</span>`;
        }} else if (kind === 'went-to') {{
          const stem = o.dest || normDest(r.destination);
          destCellHtml = `<a class="dest-link" href="${{xcallbackUrl('[[' + stem + ']]')}}" style="color:#58a6ff" title="Lines arrived at ${{esc(stem)}} (breadcrumb claimed ${{esc(normDest(r.destination))}})">⇢ ${{esc(stem)}}</a>`;
        }} else {{
          // move / anomaly / empty — show breadcrumb dest
          destCellHtml = `<a class="dest-link" href="${{xcallbackUrl(r.destination)}}">${{esc(normDest(r.destination))}}</a>`;
        }}
        const countCellTxt = (kind === 'empty') ? '·' : (lineN || 0);
        const countTitle   = (kind === 'empty')
          ? 'Empty outcome'
          : `${{lineN}} ${{kind}} line${{lineN === 1 ? '' : 's'}}`;
        // Section/source columns: first sibling shows full info; later siblings
        // get a "↳" sibling marker and inherit the breadcrumb's data via title.
        // Each sibling gets its OWN toggle button — expansion is per-outcome so
        // the line count cell and the expand list always agree.
        const toggleHtml = (lineN > 0)
          ? `<button class="sec-toggle" onclick="toggleSectionItems(${{idx}},this,${{oi}})" title="Expand items for this outcome">▶</button>`
          : '';
        const sectionCell = isFirst
          ? `<td class="section-col">${{toggleHtml}}${{esc(r.section)}}</td>`
          : `<td class="section-col" style="padding-left:24px;color:#7d8590;font-size:11px" title="Sibling outcome of: ${{esc(r.section)}}">${{toggleHtml}}↳ ${{esc(r.section)}}</td>`;
        const summaryCell = isFirst
          ? `<td class="summary-col">${{esc(r.summary)}}</td>`
          : `<td class="summary-col" style="color:#484f58;font-size:11px;font-style:italic">${{esc(r.summary || '')}}</td>`;
        const srcCell = isFirst
          ? `<td class="src-col"><a class="dest-link" href="${{srcUrl}}" title="${{esc(r.source_file)}}">${{srcStem}}</a></td>`
          : `<td class="src-col" style="opacity:0.4">${{srcStem}}</td>`;
        // Sibling-row visual marker: subtle left border so a glance shows grouping.
        const trStyle = isFirst ? '' : 'background:rgba(110,118,129,0.04);border-left:2px solid #30363d';
        const dataAttrs = `data-row-idx="${{idx}}" data-row-type="${{kind}}" data-outcome-kind="${{kind}}" data-outcome-rendered="true" data-sibling="${{isFirst ? 'first' : 'true'}}"`;
        return `<tr ${{dataAttrs}} style="${{trStyle}}">
          <td style="padding:3px 6px;text-align:center"><span class="row-badge rb-${{badgeCls}}" title="${{_kindTitle[kind] || kind}}" onclick="event.stopPropagation();showSectionModal(${{idx}})" style="cursor:pointer">${{glyph}}</span></td>
          <td class="count-col" style="width:48px;text-align:center;font-size:10px;color:${{_countColor[kind] || '#484f58'}};font-family:monospace" title="${{countTitle}}">${{countCellTxt}}</td>
          ${{sectionCell}}
          ${{summaryCell}}
          ${{srcCell}}
          <td class="dest-col" title="${{esc(r.destination)}}">${{destCellHtml}}</td>
          <td style="padding:3px 6px;text-align:center"><button class="view-btn" onclick="showSectionModal(${{idx}})">⌕</button></td>
        </tr>`;
      }}).join('');
      return sepRow + trs;
    }}).join('');
  }}

  let html = `<table class="nav-tbl">
    <thead><tr><th></th><th style="width:48px;text-align:center">#</th><th>Section</th><th>Summary</th><th>Source</th><th>Destination</th><th></th></tr></thead>
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
      // else: deleted file (+++ /dev/null) — keep filename from --- line set below
      continue;
    }}
    if (l.startsWith('--- ')) {{
      // Fallback filename source for deleted files (--- a/path, +++ /dev/null)
      if (!cur.filename) {{
        let p = l.slice(4).trim();
        if (p.startsWith('"') && p.endsWith('"')) p = p.slice(1, -1);
        if (p.startsWith('a/')) cur.filename = p.slice(2);
      }}
      continue;
    }}
    if (l.startsWith('new file')) {{ cur.isNewFile = true; continue; }}
    if (l.startsWith('index ') || l.startsWith('deleted file') || l.startsWith('old mode') || l.startsWith('new mode')) continue;
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

// Build map: normLine(content) → [destFilename, ...]  (all + lines across all files)
function buildMoveMap(files) {{
  const map = new Map();
  for (const f of files) {{
    for (const hunk of f.hunks) {{
      for (const r of hunk.right) {{
        const n = normLine(r.c);
        if (n.length < 6) continue;
        if (!map.has(n)) map.set(n, []);
        map.get(n).push(f.filename);
      }}
    }}
  }}
  return map;
}}

function renderHunk(hunk, srcFilename, moveMap) {{
  const llen = hunk.left.length, rlen = hunk.right.length;
  const total = Math.max(llen, rlen);
  let leftRows = '', rightRows = '';

  for (let i = 0; i < total; i++) {{
    const l = i < llen ? hunk.left[i] : null;
    const r = i < rlen ? hunk.right[i] : null;
    const isCtx = l && r && l.c === r.c;
    const lCls = isCtx ? 'ctx' : (l ? 'del' : 'ctx');
    const rCls = isCtx ? 'ctx' : (r ? 'add' : 'ctx');

    let annotation = '';
    if (!isCtx && l && lCls === 'del' && moveMap) {{
      const n = normLine(l.c);
      if (n.length >= 6) {{
        const dests = (moveMap.get(n) || []).filter(f => f !== srcFilename);
        if (dests.length > 0) {{
          const stem = dests[0].split('/').pop().replace(/\\.md$/, '');
          const cb = 'noteplan://x-callback-url/openNote?noteTitle=' + encodeURIComponent(stem);
          const label = stem.replace(/^\\S+\\s*/, '').slice(0, 28) || stem.slice(0, 28);
          annotation = `<a href="${{cb}}" class="move-badge" title="Moved to ${{esc(stem)}}">→ ${{esc(label)}}</a>`;
        }} else {{
          annotation = `<span class="lost-badge">✗ lost</span>`;
        }}
      }}
    }}

    leftRows  += `<div class="row ${{lCls}}" style="align-items:center"><span class="ln">${{l ? l.n : ''}}</span><span class="lc">${{l ? esc(l.c) : ''}}</span>${{annotation}}</div>`;
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

  const moveMap = buildMoveMap(files);

  diff.innerHTML = files.map((f, fi) => {{
    const adds = f.hunks.reduce((s, h) => s + h.right.length, 0);
    const dels = f.hunks.reduce((s, h) => s + h.left.length, 0);
    const hunksHtml = f.hunks.map(h => renderHunk(h, f.filename, moveMap)).join('');
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

  // Seed badge cache + warnings from PRE_CLASSIFICATION (Python compile time).
  if (PRE_CLASSIFICATION && PRE_CLASSIFICATION.length > 0) {{
    for (const pc of PRE_CLASSIFICATION) {{
      const idx = pc.idx;
      if (idx == null || _rowClassifications.has(idx)) continue;
      const c = {{
        type:            pc.type,
        movedCount:      pc.moved_count || 0,
        lostCount:       pc.lost_count  || 0,
        newCount:        0,
        misroutedCount:  pc.misrouted_count || 0,
        wentToFiles:     pc.went_to_files || [],
        trulyLostLines:  pc.truly_lost_lines || [],
        movedLines:      pc.moved_lines   || [],
        destLines:       pc.dest_lines    || [],
        wentToDetails:   pc.went_to_details || {{}},
        lineStatuses:    pc.line_statuses  || {{}},
        emptyReason:     (pc.issues || []).join(', '),
        blocks:          [],
      }};
      if (c.movedCount > 0) c.blocks.push({{ type: 'move', count: c.movedCount }});
      if (c.lostCount  > 0) c.blocks.push({{ type: 'lost',  count: c.lostCount, lines: c.trulyLostLines }});
      _rowClassifications.set(idx, c);
      updateRowBadge(idx, c);
      annotateRowWarnings(idx, pc.issues || []);
    }}
  }}

  allParsedFiles = parseDiff(DIFF_TEXT);
  renderDiffFiles(allParsedFiles);

  // Phase E pre-classified everything from PRE_CLASSIFICATION; just paint the banner.
  updateValidationBanner();

  // Hover sync + click-to-scroll: pair src/dest lines by data-pair-id
  const modalBody = document.getElementById('modal-body');
  modalBody.addEventListener('mouseover', e => {{
    const el = e.target.closest('[data-pair-id]');
    const id = el?.dataset.pairId;
    modalBody.querySelectorAll('[data-pair-id]').forEach(n => {{
      n.classList.toggle('pair-highlight', n.dataset.pairId === id && id != null);
    }});
  }});
  modalBody.addEventListener('mouseleave', () => {{
    modalBody.querySelectorAll('.pair-highlight').forEach(n => n.classList.remove('pair-highlight'));
  }});
  modalBody.addEventListener('click', e => {{
    const el = e.target.closest('[data-pair-id]');
    if (!el) return;
    const id = el.dataset.pairId;
    const peer = [...modalBody.querySelectorAll(`[data-pair-id="${{id}}"]`)].find(n => n !== el);
    if (peer) peer.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
  }});
}});
</script>
<div id="modal-overlay" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-hdr">
      <div style="flex:1;overflow:hidden">
        <span class="modal-title" id="modal-title"></span>
        <span id="modal-scope" style="display:none;margin-left:8px;font-size:10px;color:#8b949e;font-weight:normal"></span>
      </div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-body" id="modal-body"></div>
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTML data extraction helpers (module-level for testability)
# ---------------------------------------------------------------------------

def _extract_js_str(html: str, var: str) -> str:
    """Extract a JSON string value assigned to `var` in the snapshot HTML."""
    marker = f'const {var} = '
    idx = html.find(marker)
    if idx == -1:
        return ""
    start = idx + len(marker)
    try:
        value, _ = json.JSONDecoder().raw_decode(html, start)
        return value if isinstance(value, str) else ""
    except Exception:
        return ""


def _extract_js_val(html: str, var: str) -> object:
    """Extract a JSON array/object value assigned to `var` in the snapshot HTML."""
    marker = f'const {var} = '
    idx = html.find(marker)
    if idx == -1:
        return []
    start = idx + len(marker)
    try:
        value, _ = json.JSONDecoder().raw_decode(html, start)
        return value if isinstance(value, (list, dict)) else []
    except Exception:
        return []


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

    # Deduplicate: latest entry per anchor wins
    by_anchor: dict = {}
    for entry in all_comments:
        anchor = entry.get("anchor", "")
        if anchor:
            by_anchor[anchor] = entry

    merged_comments = list(by_anchor.values())

    # Always rebuild review.html from current source code, extracting embedded data
    # from the snapshot. This ensures latest JS/CSS + decoded emoji paths.
    snapshot_html = snapshot_path.read_text(encoding="utf-8")

    diff_text = _extract_js_str(snapshot_html, "DIFF_TEXT")
    stat_text = _extract_js_str(snapshot_html, "STAT_TEXT")
    narrative = _extract_js_val(snapshot_html, "NARRATIVE")
    changed_cal = _extract_js_val(snapshot_html, "CHANGED_CALENDAR_FILES")

    # Re-apply path decoding to fix old snapshots that stored octal-quoted paths
    diff_text = _decode_git_quoted_paths(diff_text)
    stat_text = _decode_git_quoted_paths(stat_text)

    # Extract sha from header span in snapshot
    sha_m = re.search(r'sha: ([0-9a-f]{7,40})', snapshot_html)
    sha = sha_m.group(1) if sha_m else run_id

    review_path = sweeps / f"{run_id}.review.html"
    if utils.DRY_RUN:
        utils.log(f"[dry-run] Would write {review_path} with {len(merged_comments)} comment(s)")
        return

    # Layer 1 — Diff integrity checks (non-blocking, warns to stderr)
    for w in _validate_diff_integrity(diff_text, narrative or []):
        utils.err(f"[V-D] {w}")

    # Phase E: pre-compute row classification in Python at compile time.
    # Embedded as PRE_CLASSIFICATION / CROSS_ROW_ISSUES so the portal has instant badges
    # and inspectable data without waiting for the JS background scan.
    pre_classification = _py_classify_all_rows(diff_text, narrative or [], _np_root())
    cross_row_issues   = _py_cross_row_issues(pre_classification)

    # #86 production invariant monitoring — surface mental-model violations
    # to the quality log so drift on real data is visible on the next sweep
    # without waiting for tests to catch it. Don't fail compile; warn + log.
    inv_violations = _py_invariant_violations(pre_classification, cross_row_issues)
    if inv_violations:
        utils.err(f"[INV] {len(inv_violations)} mental-model invariant violation(s) — see quality-log.jsonl")
        try:
            log_path = _quality_log_path(_np_root())
            log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "ts":            datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "run_id":        run_id,
                "kind":          "invariant_violations",
                "count":         len(inv_violations),
                "violations":    inv_violations[:50],  # cap to keep log bounded
            }
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            utils.err(f"[INV] failed to write quality log: {e}")

    new_html = _build_snapshot_html(run_id, date_str, sha, stat_text, diff_text, merged_comments, narrative, changed_cal,
                                    pre_classification=pre_classification,
                                    cross_row_issues=cross_row_issues)
    review_path.write_text(new_html, encoding="utf-8")
    cmt_note = f"{len(merged_comments)} comment(s) from {len(comment_rounds)} round(s)" if merged_comments else "no comments"
    utils.log(f"sweep-review-compile: wrote {review_path} ({cmt_note})")


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
# sweep-review-export
# ---------------------------------------------------------------------------

def cmd_sweep_review_export(args):
    """Export raw sweep data (diff, narrative, stats, rows) as JSON to stdout or a file."""
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
    snap_path = sweeps / f"{run_id}.snapshot.html"
    if not snap_path.exists():
        utils.err(f"Snapshot not found: {snap_path}. Run sweep-review-generate first.")
        sys.exit(utils.EXIT_NOT_FOUND)

    html = snap_path.read_text(encoding="utf-8")
    diff_text  = _extract_js_str(html, "DIFF_TEXT")
    stat_text  = _extract_js_str(html, "STAT_TEXT")
    narrative  = _extract_js_val(html, "NARRATIVE")
    modal_rows = _extract_js_val(html, "MODAL_ROWS")
    cal_files  = _extract_js_val(html, "CHANGED_CALENDAR_FILES")

    # Extract sweep SHA from snapshot comment header
    sha_m = re.search(r'sha:\s*([0-9a-f]{7,40})', html)
    sweep_sha = sha_m.group(1) if sha_m else ""

    payload = {
        "run_id":   run_id,
        "date":     date_str,
        "sha":      sweep_sha,
        "stats":    stat_text,
        "diff":     diff_text,
        "narrative": narrative,
        "modal_rows": modal_rows,
        "changed_calendar_files": cal_files,
    }

    out = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(out, encoding="utf-8")
        utils.log(f"sweep-review-export: wrote {out_path}")
    else:
        print(out)


# ---------------------------------------------------------------------------
# sweep-review-audit
# ---------------------------------------------------------------------------

def _norm_line(s: str) -> str:
    """Python mirror of JS normLine — strips date tags, hashtags, collapses whitespace."""
    import re as _re
    s = _re.sub(r'>\d{4}-\d{2}-\d{2}', '', s)
    s = _re.sub(r'#\w+', '', s)
    s = _re.sub(r'\s+', ' ', s).strip().lower()
    return s

def _find_dest_on_disk(root: Path, dest_stem: str) -> Path | None:
    """Search for a destination .md file by stem anywhere under the Notes dir."""
    notes = root / "Notes"
    if not notes.exists():
        return None
    target = dest_stem.lower() + '.md'
    for p in notes.rglob('*.md'):
        if p.name.lower() == target:
            return p
    return None

def _fuzzy_match(a: str, b: str) -> bool:
    """Python mirror of classifyDestLines prefix/body matching."""
    if not a or not b:
        return False
    if a == b:
        return True
    p = min(50, min(len(a), len(b)))
    if p >= 10 and min(len(a), len(b)) / max(len(a), len(b)) >= 0.5 and (a.startswith(b[:p]) or b.startswith(a[:p])):
        return True
    body_a = re.sub(r'^[-*]\s*\[[x ]\]\s*', '', a, flags=re.I).strip()
    body_b = re.sub(r'^[-*]\s*\[[x ]\]\s*', '', b, flags=re.I).strip()
    if len(body_a) >= 8 and len(body_b) >= 8:
        bl = min(40, min(len(body_a), len(body_b)))
        if bl >= 8 and min(len(body_a), len(body_b)) / max(len(body_a), len(body_b)) >= 0.5 and (body_a.startswith(body_b[:bl]) or body_b.startswith(body_a[:bl])):
            return True
    return False

def _is_noise(line: str) -> bool:
    if re.match(r'^#+\s', line.strip()): return True   # markdown headings never move
    n = _norm_line(line)
    if len(n) <= 3: return True
    if re.match(r'^`+\w*$', n): return True
    if re.match(r'^-{2,}$', n) or re.match(r'^—+$', n): return True
    if re.match(r'^[-*]\s*\[\s*\]\s*$', n): return True
    return False


def _validate_diff_integrity(diff_text: str, narrative: list) -> list[str]:
    """Layer 1 — Diff integrity checks. Returns list of warning strings."""
    warnings: list[str] = []

    # V-D1: diff is non-empty
    if not diff_text or not diff_text.strip():
        warnings.append("V-D1: diff_text is empty — report has no diff data")
        return warnings  # further checks meaningless

    # V-D2: at least one Calendar file (YYYYMMDD.md) appears in diff
    if not re.search(r'\b\d{8}\.md\b', diff_text):
        warnings.append("V-D2: no Calendar file (YYYYMMDD.md) found in diff — sweep may not have touched any daily notes")

    # V-D3: all @@ hunk headers match @@ -N[,N] +N[,N] @@
    for hunk in re.findall(r'@@[^@\n]*@@', diff_text):
        if not re.match(r'^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@', hunk):
            warnings.append(f"V-D3: malformed hunk header: {hunk!r}")

    # V-D4: no residual octal escapes (\NNN) in filenames after path decoding
    for line in diff_text.splitlines():
        if line.startswith('diff --git ') or line.startswith('+++ ') or line.startswith('--- '):
            if re.search(r'\\[0-7]{3}', line):
                warnings.append(f"V-D4: residual octal escape in filename line: {line!r}")

    # V-D5: every source_file in narrative rows appears in the diff
    for row in (narrative or []):
        sf = row.get('source_file', '')
        if not sf:
            continue
        stem = sf.split('/')[-1]
        if stem and stem.lower() not in diff_text.lower():
            warnings.append(f"V-D5: source_file '{stem}' not found in diff")

    return warnings

def _parse_diff_sections(diff_text: str) -> dict:
    """Parse diff into {filename: {removed: [lines], added: [lines]}}."""
    files: dict = {}
    cur: dict | None = None
    for line in diff_text.splitlines():
        if line.startswith('diff --git '):
            m = re.search(r'b/(.+)$', line)
            fname = m.group(1) if m else ''
            cur = {'removed': [], 'added': []}
            files[fname] = cur
        elif cur is None:
            continue
        elif line.startswith('---') or line.startswith('+++') or line.startswith('index') or line.startswith('@@'):
            continue
        elif line.startswith('-') and len(line) > 1:
            cur['removed'].append(line[1:])
        elif line.startswith('+') and len(line) > 1:
            cur['added'].append(line[1:])
    return files


def _extract_section_lines(diff_text: str, filename: str, section_name: str, line_type: str) -> list[str]:
    """Python mirror of JS extractSectionLines — returns lines of given type within a section."""
    base = filename.split('/')[-1].lower()
    name_lower = section_name.lower().strip() if section_name else None
    in_file = False
    in_section = section_name is None
    section_level = 0
    result = []

    def header_matches(content: str) -> bool:
        h = re.sub(r'^#+\s*', '', content).strip().lower()
        n = name_lower or ''
        if h == n: return True
        if h.startswith(n + ' ') or h.startswith(n + ':'): return True
        if n.startswith(h + ' ') or n.startswith(h + ':'): return False
        # Last-token check: query's last token (≥3 chars) as whole word in header
        q_toks = [w for w in n.split() if len(w) >= 3]
        if q_toks:
            last = re.escape(q_toks[-1])
            if re.search(rf'\b{last}\b', h): return True
        return False

    for raw in diff_text.splitlines():
        if raw.startswith('diff --git '):
            in_file = base in raw.lower()
            in_section = section_name is None
            section_level = 0
            continue
        if not in_file:
            continue
        if raw.startswith('+++') or raw.startswith('---') or raw.startswith('index') or raw.startswith('@@'):
            continue
        if not raw:
            continue
        t = raw[0]
        if t not in ('+', '-', ' '):
            continue
        content = raw[1:]
        hm = re.match(r'^(#+)\s', content)
        depth = len(hm.group(1)) if hm else 0

        if section_name is not None:
            if depth > 0 and header_matches(content):
                in_section = True
                section_level = depth
            elif in_section and depth > 0 and depth <= section_level and t != '+':
                in_section = False

        if in_section and t == line_type:
            result.append(content)

    # Fallback: if section not found, return empty (caller handles inferred match)
    return result



def cmd_sweep_review_audit(args):
    """Data quality audit: classify all rows, report lost lines, mixed rows, and structural issues."""
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
    snap_path = sweeps / f"{run_id}.snapshot.html"
    if not snap_path.exists():
        utils.err(f"Snapshot not found: {snap_path}")
        sys.exit(utils.EXIT_NOT_FOUND)

    html = snap_path.read_text(encoding="utf-8")
    diff_text  = _extract_js_str(html, "DIFF_TEXT")
    narrative  = _extract_js_val(html, "NARRATIVE")

    if not diff_text:
        utils.err("Empty diff — nothing to audit.")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    # Build global diff index
    diff_index = _parse_diff_sections(diff_text)
    diff_lower = {k.lower(): v for k, v in diff_index.items()}

    def get_file(name: str) -> dict | None:
        stem = name.split('/')[-1].lower()
        for k, v in diff_lower.items():
            if k.endswith(stem):
                return v
        return None

    # B-13 layer 1: per-dest union of all sibling rows' removed norms.
    def _build_sibling_norms() -> dict:
        result: dict[str, set] = {}
        for r in narrative:
            d = re.sub(r'\[\[([^\]]+)\]\]', r'\1', r.get('destination', '')).strip()
            d = re.sub(r'\.md$', '', d).strip()
            sec = re.sub(r'^#+\s*', '', r.get('section', '')).strip()
            src = (r.get('source_file') or '').split('/')[-1]
            lines = _extract_section_lines(diff_text, src, sec, '-')
            norms = {_norm_line(l) for l in lines if not _is_noise(l) and len(_norm_line(l)) > 2}
            result.setdefault(d, set()).update(norms)
        return result

    # B-13 layer 2: global removed norms — all lines removed from ANY source file in diff.
    # Catches lines that were swept under an unmatched section name (V-47 scope miss).
    def _build_global_removed_norms() -> set:
        norms: set = set()
        for line in diff_text.split('\n'):
            if line.startswith('-') and len(line) > 1:
                n = _norm_line(line[1:])
                if len(n) > 5:
                    norms.add(n)
        return norms

    _sibling_norms = _build_sibling_norms()
    _global_removed_norms = _build_global_removed_norms()

    def classify_row(row: dict) -> dict:
        src_file  = (row.get('source_file') or '').split('/')[-1]
        dest_raw  = re.sub(r'\[\[([^\]]+)\]\]', r'\1', row.get('destination', '')).strip()
        dest_raw  = re.sub(r'\.md$', '', dest_raw).strip()
        section   = re.sub(r'^#+\s*', '', row.get('section', '')).strip()

        issues = []
        src_in_diff  = any(k.endswith(src_file.lower()) for k in diff_lower)
        dest_in_diff = any(k.endswith((dest_raw + '.md').lower()) for k in diff_lower)
        if not src_in_diff:  issues.append('src_not_in_diff')
        if not dest_in_diff: issues.append('dest_not_in_diff')
        if src_file.lower() == (dest_raw + '.md').lower(): issues.append('self_migration')

        if not src_in_diff or not dest_in_diff:
            return {'type': 'empty', 'issues': issues, 'moved': [], 'lost': [], 'new': []}

        # Extract SECTION-scoped removed lines (mirrors JS extractSectionLines)
        raw_removed = _extract_section_lines(diff_text, src_file, section, '-')

        # Infer from full file if section not found
        if not raw_removed:
            all_removed = _extract_section_lines(diff_text, src_file, None, '-')
            dest_added_all = _extract_section_lines(diff_text, dest_raw + '.md', None, '+')
            dest_norms_all = {_norm_line(l) for l in dest_added_all if len(_norm_line(l)) > 5}
            raw_removed = [l for l in all_removed
                           if not _is_noise(l) and len(_norm_line(l)) > 4
                           and any(_fuzzy_match(_norm_line(l), dn) for dn in dest_norms_all)]

        removed = [l for l in raw_removed if not _is_noise(l) and len(_norm_line(l)) > 2]
        if not removed:
            # B-14: newly created plan/note files have portal-generated boilerplate and
            # swept content as additions. When source has no countable removed lines and
            # the dest was created in this diff, treat as 'empty' — nothing to verify.
            _dest_stem_lower = (dest_raw.split('/')[-1] + '.md').lower()
            _dest_is_new = any(
                'new file mode' in blk
                for blk in re.split(r'(?=diff --git )', diff_text)
                if _dest_stem_lower in blk.lower()
            )
            if _dest_is_new:
                return {'type': 'empty', 'issues': issues + ['new_file'],
                        'moved': [], 'lost': [], 'new': []}
            dest_added = _extract_section_lines(diff_text, dest_raw + '.md', None, '+')
            # B-13: subtract additions claimed by sibling rows (layer 1) OR any diff source (layer 2)
            sibling_norms = _sibling_norms.get(dest_raw, set())
            dest_content = [
                l for l in dest_added
                if not _is_noise(l) and len(_norm_line(l)) > 2
                and _norm_line(l) not in sibling_norms
                and _norm_line(l) not in _global_removed_norms
            ]
            if not dest_content:
                return {'type': 'empty', 'issues': issues, 'moved': [], 'lost': [], 'new': []}
            # B-16: multi-commit sweep FP — source section removal was committed separately.
            # When the diff is incomplete (section gone from disk but not in diff), unclaimed
            # dest additions that are ALL present on disk are confirmed-arrived. Classify empty.
            dest_file_path = _find_dest_on_disk(root, dest_raw)
            if dest_file_path:
                dest_text = dest_file_path.read_text(errors='replace')
                dest_file_norms = {_norm_line(l) for l in dest_text.splitlines()
                                   if len(_norm_line(l)) > 4}
                unconfirmed = [l for l in dest_content
                               if not any(_fuzzy_match(_norm_line(l), dn)
                                          for dn in dest_file_norms)]
                if not unconfirmed:
                    return {'type': 'empty', 'issues': issues + ['disk_confirmed'],
                            'moved': [], 'lost': [], 'new': []}
            return {'type': 'anomaly', 'issues': issues,
                    'moved': [], 'lost': [], 'new': dest_content[:5]}

        # Match removed lines against destination added lines (diff only)
        dest_added = _extract_section_lines(diff_text, dest_raw + '.md', None, '+')

        # B-15: Redirect-stub FP — if dest file on disk contains "> Migrated: see [[LinkedPlan]]",
        # recheck removed lines against the linked plan's diff additions instead.
        _dest_file_b15 = _find_dest_on_disk(root, dest_raw)
        if _dest_file_b15:
            try:
                _dest_text_b15 = _dest_file_b15.read_text(errors='replace')
                _redir = re.search(r'> Migrated: see \[\[([^\]]+)\]\]', _dest_text_b15, re.IGNORECASE)
                if _redir:
                    _linked_stem = _redir.group(1).strip()
                    _linked_added = _extract_section_lines(diff_text, _linked_stem + '.md', None, '+')
                    if _linked_added:
                        dest_added = _linked_added
                        issues.append('b15_redirect')
            except OSError:
                pass

        dest_norms = [(_norm_line(l), l) for l in dest_added
                      if not _is_noise(l) and len(_norm_line(l)) > 2]

        moved, lost = [], []
        for src_line in removed:
            sn = _norm_line(src_line)
            matched = any(_fuzzy_match(sn, dn) for dn, _ in dest_norms)
            (moved if matched else lost).append(src_line)

        # Secondary grep: lines not found in diff may already exist in dest file on disk
        # (moved by a prior sweep — not a +line, so not in diff)
        already_present = []
        if lost:
            dest_file_path = _find_dest_on_disk(root, dest_raw)
            if dest_file_path:
                dest_text_norm = _norm_line(dest_file_path.read_text(errors='replace'))
                # Use full file text for substring search (faster than line-by-line for audit)
                dest_full = dest_file_path.read_text(errors='replace')
                dest_file_norms = {_norm_line(l) for l in dest_full.splitlines()
                                   if len(_norm_line(l)) > 4}
                truly_lost = []
                for l in lost:
                    sn = _norm_line(l)
                    if any(_fuzzy_match(sn, dn) for dn in dest_file_norms):
                        already_present.append(l)
                    else:
                        truly_lost.append(l)
                lost = truly_lost

        row_type = 'move' if (moved and not lost) else 'lost'
        if not lost and not moved and already_present: row_type = 'move'  # all present on disk
        if already_present: issues.append(f'{len(already_present)} line(s) already in dest file')

        blocks = []
        if moved: blocks.append({'type': 'move', 'lines': moved, 'count': len(moved)})
        if lost:  blocks.append({'type': 'lost', 'lines': lost,  'count': len(lost)})

        return {'type': row_type, 'issues': issues, 'blocks': blocks,
                'moved': moved, 'lost': lost, 'already_present': already_present, 'new': []}

    # Run audit
    sep = lambda: '─' * 60
    lines_out = [f"Sweep audit — {run_id}", sep()]

    isSep = lambda r: re.match(r'^-+$', (r.get('section') or '').strip())
    rows = [r for r in (narrative or []) if not isSep(r)]

    counts: dict = {'move': 0, 'lost': 0, 'anomaly': 0, 'empty': 0}
    problems = []

    for row in rows:
        result = classify_row(row)
        t = result['type']
        counts[t] = counts.get(t, 0) + 1

        if result['issues'] or result['lost'] or result['new'] or result.get('already_present'):
            problems.append((row, result))

    total = sum(counts.values())
    lines_out.append(f"  {total} rows — ✓ {counts.get('move',0)} moved  ✗ {counts.get('lost',0)} lost  + {counts.get('anomaly',0)} anomaly  · {counts.get('empty',0)} empty")
    lines_out.append(sep())

    if not problems:
        lines_out.append("  No issues found.")
    else:
        for row, result in problems:
            src  = row.get('source_file', '?').split('/')[-1]
            dest = re.sub(r'\[\[([^\]]+)\]\]', r'\1', row.get('destination', '?')).strip()
            sect = row.get('section', '?')
            blocks = result.get('blocks', [])
            if len(blocks) > 1:
                type_label = '⚡ ' + ' '.join(('→' if b['type']=='move' else '✗') + str(b['count']) for b in blocks)
            else:
                type_label = result['type'].upper()
            lines_out.append(f"\n  {type_label}  {sect}  →  {dest}  [{src}]")
            for issue in result['issues']:
                lines_out.append(f"    ⚠  {issue.replace('_', ' ')}")
            if result['moved'] and result['lost']:
                for l in result['moved'][:3]:
                    lines_out.append(f"    →  {l[:80]}")
                if len(result['moved']) > 3:
                    lines_out.append(f"    →  … {len(result['moved'])-3} more moved lines")
            for l in result['lost'][:5]:
                lines_out.append(f"    ✗  {l[:80]}")
            if len(result['lost']) > 5:
                lines_out.append(f"    ✗  … {len(result['lost'])-5} more lost lines")
            for l in result.get('already_present', [])[:3]:
                lines_out.append(f"    ✓~  {l[:80]}  (already in dest file)")
            if len(result.get('already_present', [])) > 3:
                lines_out.append(f"    ✓~  … {len(result['already_present'])-3} more already present")
            for l in result['new'][:3]:
                lines_out.append(f"    +  {l[:80]}")
            if len(result['new']) > 3:
                lines_out.append(f"    +  … {len(result['new'])-3} more new lines")

    lines_out.append('')
    report = '\n'.join(lines_out)

    if args.output:
        Path(args.output).write_text(report, encoding='utf-8')
        utils.log(f"sweep-review-audit: wrote {args.output}")
    else:
        print(report)

    # Auto-append to quality log so sweep-review-quality can track trends over time
    _append_quality_log(root, run_id, counts, problems)


def _py_classify_all_rows(diff_text: str, narrative: list, root: Path) -> list[dict]:
    """Pre-compute row classifications at compile time.
    Returns a list of dicts (one per NARRATIVE row, same index) with:
      {idx, type, moved_count, lost_count, truly_lost_lines, issues}
    Used to embed const PRE_CLASSIFICATION in the review HTML so the portal has
    instant badges and inspectable data without waiting for the JS background scan.
    """
    diff_index = _parse_diff_sections(diff_text)
    diff_lower = {k.lower(): v for k, v in diff_index.items()}

    # Build global added map: normLine → [filename] — for V-R6 misroute detection
    all_added_entries: list[tuple[str, str]] = []  # (normLine, filename)
    for fname, fdata in diff_index.items():
        for line in fdata.get('added', []):
            n = _norm_line(line)
            if len(n) > 2 and not _is_noise(line):
                all_added_entries.append((n, fname))

    # Build global removed map: normLine → source filename (for inference cross-source filter)
    # Allows us to exclude dest additions that came from other source files.
    global_removed_srcs: dict[str, str] = {}
    for fname, fdata in diff_index.items():
        for line in fdata.get('removed', []):
            n = _norm_line(line)
            if len(n) > 2 and not _is_noise(line) and n not in global_removed_srcs:
                global_removed_srcs[n] = fname

    def _dest_stem(efname: str) -> str:
        """Extract bare filename stem (no path, no .md), lowercased for matching."""
        stem = efname.split('/')[-1]
        if stem.lower().endswith('.md'):
            stem = stem[:-3]
        return stem.lower()

    def _dest_stem_pretty(efname: str) -> str:
        """Like _dest_stem but preserves original casing — used for display."""
        stem = efname.split('/')[-1]
        if stem.lower().endswith('.md'):
            stem = stem[:-3]
        return stem

    def _misroute_count(lost_lines: list[str], dest_raw: str) -> int:
        dest_stem_key = _dest_stem(dest_raw)
        count = 0
        for ll in lost_lines:
            nll = _norm_line(ll)
            if len(nll) < 6:
                continue
            for en, efname in all_added_entries:
                if _dest_stem(efname) == dest_stem_key:
                    continue  # skip same dest — use stem comparison, not rstrip
                if _fuzzy_match(nll, en):
                    count += 1
                    break
        return count

    results: list[dict] = []
    seen_tuples: dict[tuple, int] = {}  # (source_file, section, destination) → first modal_idx
    isSep = lambda r: re.match(r'^-+$', (r.get('section') or '').strip())

    # CRITICAL: Use MODAL_ROWS indices (non-separator rows only) not NARRATIVE indices.
    # JS renderNarrative() pushes only non-separator rows to MODAL_ROWS, so MODAL_ROWS[k]
    # corresponds to the k-th non-separator NARRATIVE entry. PRE_CLASSIFICATION idx values
    # are seeded into _rowClassifications.set(idx,...) which MODAL_ROWS[idx] is then read
    # from. If separator rows inflate the idx, every badge gets data from the wrong row.
    modal_idx = 0
    for row in narrative:
        if isSep(row):
            continue  # separator rows are not in MODAL_ROWS — skip entirely

        src_file = (row.get('source_file') or '').split('/')[-1]
        dest_raw = re.sub(r'\[\[([^\]]+)\]\]', r'\1', row.get('destination', '')).strip()
        dest_raw = re.sub(r'\.md$', '', dest_raw).strip()
        section  = re.sub(r'^#+\s*', '', row.get('section', '')).strip()
        issues: list[str] = []

        src_in_diff  = any(k.endswith(src_file.lower()) for k in diff_lower)
        dest_in_diff = any(k.endswith((dest_raw.split('/')[-1] + '.md').lower()) for k in diff_lower)
        if not src_in_diff:  issues.append('src_not_in_diff')
        if not dest_in_diff: issues.append('dest_not_in_diff')

        # V-R4: duplicate (source_file × section × destination) tuple
        _tuple_key = (row.get('source_file', ''), row.get('section', ''), row.get('destination', ''))
        if _tuple_key in seen_tuples:
            issues.append('duplicate_row')
        else:
            seen_tuples[_tuple_key] = modal_idx

        # V-R5: self-migration — source file and destination resolve to the same file
        if src_file.lower() == (dest_raw.split('/')[-1] + '.md').lower():
            issues.append('self_migration')

        if not src_in_diff or not dest_in_diff:
            results.append({'idx': modal_idx, 'breadcrumb_idx': modal_idx,
                            'type': 'empty', 'moved_count': 0,
                            'lost_count': 0, 'truly_lost_lines': [], 'moved_lines': [],
                            'dest_lines': [], 'went_to_details': {}, 'line_statuses': {},
                            'inferred': False, 'dest_stem': _dest_stem(dest_raw),
                            'outcomes': [{'kind': 'empty', 'dest': dest_raw,
                                          'dest_stem': _dest_stem(dest_raw), 'lines': []}],
                            'issues': issues})
            modal_idx += 1
            continue

        # Extract removed lines for this section
        inferred = False
        raw_removed = _extract_section_lines(diff_text, src_file, section, '-')
        if not raw_removed:
            # V-R3: section header not found in diff — classification uses inference
            inferred = True
            issues.append('inferred_section')
            # Infer from full file if section not found.
            # Cross-source filter: only use dest additions that came from THIS source file
            # (or have no known source) — prevents matching lines swept on other dates.
            all_rem = _extract_section_lines(diff_text, src_file, None, '-')
            dest_add_all = _extract_section_lines(diff_text, dest_raw + '.md', None, '+')
            src_file_lower = src_file.lower()
            infer_dest = []
            for _l in dest_add_all:
                _n = _norm_line(_l)
                if len(_n) <= 5:
                    continue
                _src = global_removed_srcs.get(_n)
                if _src is None or _src.lower().endswith(src_file_lower):
                    infer_dest.append(_l)
            dest_norms_all = {_norm_line(l) for l in infer_dest}
            raw_removed = [l for l in all_rem
                           if not _is_noise(l) and len(_norm_line(l)) > 4
                           and any(_fuzzy_match(_norm_line(l), dn) for dn in dest_norms_all)]

        removed = [l for l in raw_removed if not _is_noise(l) and len(_norm_line(l)) > 2]
        if not removed:
            # Anomaly: source contributed nothing for this section, but dest still has
            # additions — content arrived without a traceable source row.
            _anom_dest = _extract_section_lines(diff_text, dest_raw + '.md', None, '+')
            _anom_lines = [l for l in _anom_dest if not _is_noise(l) and len(_norm_line(l)) > 4]
            _anom_type = 'anomaly' if _anom_lines else 'empty'
            _ds = _dest_stem(dest_raw)
            _outcomes = [{
                'kind': _anom_type,
                'dest': dest_raw,
                'dest_stem': _ds,
                'lines': _anom_lines[:20] if _anom_type == 'anomaly' else [],
            }]
            results.append({'idx': modal_idx, 'breadcrumb_idx': modal_idx,
                            'type': _anom_type, 'moved_count': 0,
                            'lost_count': 0, 'truly_lost_lines': [], 'moved_lines': [],
                            'dest_lines': _anom_lines[:20] if _anom_type == 'anomaly' else [],
                            'went_to_details': {}, 'line_statuses': {},
                            'misrouted_count': 0, 'went_to_files': [],
                            'inferred': inferred, 'dest_stem': _ds,
                            'outcomes': _outcomes,
                            'issues': issues})
            modal_idx += 1
            continue

        # Full-file dest additions (no V-47a scoping — deliberate; matches intended behaviour of #82)
        dest_added = _extract_section_lines(diff_text, dest_raw + '.md', None, '+')

        # B-15: redirect-stub — recheck against linked plan.
        # First check disk for the redirect comment, then fall back to scanning the
        # diff for an in-diff context line of the form `> Migrated: see [[Target]]`.
        dest_on_disk = _find_dest_on_disk(root, dest_raw)
        b15_target: str | None = None
        if dest_on_disk:
            try:
                _redir = re.search(r'> Migrated: see \[\[([^\]]+)\]\]',
                                   dest_on_disk.read_text(errors='replace'), re.IGNORECASE)
                if _redir:
                    b15_target = _redir.group(1).strip()
            except OSError:
                pass
        if b15_target is None:
            _dest_base = (dest_raw.split('/')[-1] + '.md').lower()
            _in_block = False
            for _raw in diff_text.splitlines():
                if _raw.startswith('diff --git '):
                    _in_block = _dest_base in _raw.lower()
                    continue
                if not _in_block:
                    continue
                if _raw.startswith(('+++', '---', 'index', '@@')):
                    continue
                if _raw.startswith(' '):
                    _m = re.match(r'> Migrated: see \[\[([^\]]+)\]\]', _raw[1:], re.IGNORECASE)
                    if _m:
                        b15_target = _m.group(1).strip()
                        break
        if b15_target:
            linked = _extract_section_lines(diff_text, b15_target + '.md', None, '+')
            if linked:
                dest_added = linked
                issues.append('b15_redirect')

        # Build norm→original mapping to recover actual dest line text for moved_lines/dest_lines
        _dest_norm_to_orig: dict[str, str] = {}
        for _dl in dest_added:
            _dn = _norm_line(_dl)
            if not _is_noise(_dl) and len(_dn) > 2 and _dn not in _dest_norm_to_orig:
                _dest_norm_to_orig[_dn] = _dl
        dest_norms = list(_dest_norm_to_orig.keys())

        moved_lines, lost_lines = [], []
        _matched_dest_norms: set[str] = set()
        for src_line in removed:
            sn = _norm_line(src_line)
            _match = next((_dn for _dn in dest_norms if _fuzzy_match(sn, _dn)), None)
            if _match is not None:
                moved_lines.append(src_line)
                _matched_dest_norms.add(_match)
            else:
                lost_lines.append(src_line)
        dest_lines = [_dest_norm_to_orig[_dn] for _dn in dest_norms if _dn in _matched_dest_norms]

        # V-R6: check if lost lines exist elsewhere in the diff
        dest_stem_key = _dest_stem(dest_raw)
        truly_lost = []
        went_to_files_set: set[str] = set()
        went_to_details: dict[str, list[str]] = {}  # pretty stem → [source lines found there]
        for ll in lost_lines:
            nll = _norm_line(ll)
            found_elsewhere = False
            if len(nll) >= 6:
                for en, efname in all_added_entries:
                    _stem = _dest_stem(efname)
                    if _fuzzy_match(nll, en) and _stem != dest_stem_key:
                        _pretty = _dest_stem_pretty(efname)
                        went_to_files_set.add(_pretty)
                        went_to_details.setdefault(_pretty, []).append(ll)
                        found_elsewhere = True
                        break
            if not found_elsewhere:
                truly_lost.append(ll)

        # Secondary: check disk for already-present lines
        if truly_lost and dest_on_disk:
            try:
                disk_norms = {_norm_line(l) for l in dest_on_disk.read_text(errors='replace').splitlines()
                              if len(_norm_line(l)) > 4}
                truly_lost = [l for l in truly_lost
                              if not any(_fuzzy_match(_norm_line(l), dn) for dn in disk_norms)]
            except OSError:
                pass

        misrouted_count = len(lost_lines) - len(truly_lost)
        if not truly_lost and not moved_lines and misrouted_count > 0:
            row_type = 'went-to'
        elif not truly_lost:
            row_type = 'move'
        else:
            row_type = 'lost'

        # Per-line status map: normLine → 'move'|'went-to'|'absent'
        line_statuses: dict[str, str] = {}
        for _sl in moved_lines:
            line_statuses[_norm_line(_sl)] = 'move'
        for _stem_lines in went_to_details.values():
            for _ll in _stem_lines:
                line_statuses[_norm_line(_ll)] = 'went-to'
        for _ll in truly_lost:
            line_statuses[_norm_line(_ll)] = 'absent'

        # Per-outcome buckets — each entry is one (kind, dest) pair with its own lines.
        # Move: lines confirmed at the breadcrumb's claimed destination.
        # Went-to: lines actually at a different file (one outcome per other-file stem).
        # Lost: lines absent from the diff (no destination — semantic null).
        # Empty: row produced no lines at all (placeholder for completeness).
        # NOTE: full lists kept here. Dedupe (#98) needs to see the unabridged
        # claims to detect cross-row duplicates beyond the first 20. A final
        # truncation pass applies display caps after dedupe runs.
        outcomes: list[dict] = []
        if moved_lines:
            outcomes.append({
                'kind':      'move',
                'dest':      dest_raw,
                'dest_stem': dest_stem_key,
                'lines':     list(moved_lines),
            })
        for stem, lines in went_to_details.items():
            if lines:
                outcomes.append({
                    'kind':      'went-to',
                    'dest':      stem,
                    'dest_stem': stem.lower(),
                    'lines':     list(lines),
                })
        if truly_lost:
            outcomes.append({
                'kind':      'lost',
                'dest':      None,
                'dest_stem': None,
                'lines':     list(truly_lost),
            })
        if not outcomes:
            outcomes.append({
                'kind':      'empty',
                'dest':      dest_raw,
                'dest_stem': dest_stem_key,
                'lines':     [],
            })

        results.append({
            'idx':              modal_idx,
            'breadcrumb_idx':   modal_idx,
            'type':             row_type,
            'moved_count':      len(moved_lines),
            'lost_count':       len(truly_lost),
            'truly_lost_lines': list(truly_lost),
            'moved_lines':      list(moved_lines),
            'dest_lines':       list(dest_lines),
            'went_to_details':  {k: list(v) for k, v in went_to_details.items()},
            'line_statuses':    line_statuses,
            'misrouted_count':  misrouted_count,
            'went_to_files':    sorted(went_to_files_set),
            'inferred':         inferred,
            'dest_stem':        dest_stem_key,
            'outcomes':         outcomes,
            'issues':           issues,
        })
        modal_idx += 1

    # #89 — Dedupe dest-line claims across rows.
    # Two rows that share the same destination but different sections can both
    # claim the same dest line as moved when at least one used section inference.
    # Without dedupe, the same content shows under both rows in the portal.
    # Strategy: build (dest_stem, normLine) → [idx] map; for each conflict where
    # at least one owner is inferred, prefer the non-inferred row (tiebreak on
    # lowest idx). Losing rows have the line REMOVED from their accounting (not
    # demoted to truly_lost) — the line was misattributed to the loser's section
    # by inference; from the loser's perspective the line was never part of its
    # section. Adding to truly_lost would falsely report it as lost when it's
    # actually safely accounted for in the winner row (and on disk at dest).
    by_idx = {r['idx']: r for r in results}
    dest_owners: dict[tuple[str, str], list[int]] = {}
    for r in results:
        idx_r = r['idx']
        stem = r.get('dest_stem', '')
        if not stem:
            continue
        for dl in r.get('dest_lines', []):
            n = _norm_line(dl)
            if len(n) > 4:
                dest_owners.setdefault((stem, n), []).append(idx_r)

    for (stem, norm), owners in dest_owners.items():
        unique = sorted(set(owners))
        if len(unique) < 2:
            continue
        if not any(by_idx[i].get('inferred') for i in unique):
            continue  # both real headers — leave V-C2 to flag, no demotion
        non_inferred = [i for i in unique if not by_idx[i].get('inferred')]
        winner = (non_inferred or unique)[0]  # lowest idx wins
        for li in unique:
            if li == winner:
                continue
            loser = by_idx[li]
            loser['dest_lines'] = [dl for dl in loser.get('dest_lines', [])
                                   if _norm_line(dl) != norm]
            # Demote ALL source lines that fuzzy-match this dest norm — not
            # just the first. With near-prefix lines (e.g. option-c vs option-d)
            # the loser may have multiple source lines all fuzzy-pointing to
            # this single dest claim; if their only attribution was via this
            # collided dest, leaving any behind creates phantom moves.
            new_moved, demoted = [], []
            for sl in loser.get('moved_lines', []):
                if _fuzzy_match(_norm_line(sl), norm):
                    demoted.append(sl)
                else:
                    new_moved.append(sl)
            if demoted:
                loser['moved_lines'] = new_moved
                loser['moved_count'] = len(new_moved)
                # Drop line_statuses entries for the demoted source lines —
                # they are no longer attributed to this row at all.
                for d in demoted:
                    loser.get('line_statuses', {}).pop(_norm_line(d), None)
            if 'dedupe_demoted' not in loser.get('issues', []):
                loser.setdefault('issues', []).append('dedupe_demoted')
            # Recompute type if counts changed
            if loser['type'] == 'anomaly':
                if not loser['dest_lines']:
                    loser['type'] = 'empty'
            elif loser.get('moved_count', 0) == 0:
                loser['type'] = 'lost' if loser.get('lost_count', 0) > 0 else 'empty'

    # Rebuild `outcomes` for any row touched by dedupe so the per-outcome view
    # stays in sync with the legacy fields after demotion. Lines stay full here;
    # the final truncation pass below caps them for display.
    for r in results:
        if 'dedupe_demoted' not in r.get('issues', []):
            continue
        new_outcomes: list[dict] = []
        if r.get('moved_lines'):
            new_outcomes.append({
                'kind':      'move',
                'dest':      None,  # filled below
                'dest_stem': r.get('dest_stem'),
                'lines':     list(r['moved_lines']),
            })
        for stem, lines in (r.get('went_to_details') or {}).items():
            if lines:
                new_outcomes.append({
                    'kind':      'went-to',
                    'dest':      stem,
                    'dest_stem': stem.lower(),
                    'lines':     list(lines),
                })
        if r.get('truly_lost_lines'):
            new_outcomes.append({
                'kind':      'lost',
                'dest':      None,
                'dest_stem': None,
                'lines':     list(r['truly_lost_lines']),
            })
        if r.get('type') == 'anomaly' and r.get('dest_lines'):
            new_outcomes.append({
                'kind':      'anomaly',
                'dest':      None,
                'dest_stem': r.get('dest_stem'),
                'lines':     list(r['dest_lines']),
            })
        # Fill the `dest` field for non-lost outcomes by reading the original
        # outcomes' dest (preserves the human-readable destination string)
        old_dest_for_kind: dict[str, str | None] = {}
        for o in r.get('outcomes', []):
            old_dest_for_kind.setdefault(o.get('kind'), o.get('dest'))
        for o in new_outcomes:
            if o['dest'] is None and o['kind'] != 'lost':
                o['dest'] = old_dest_for_kind.get(o['kind'])
        if not new_outcomes:
            new_outcomes.append({
                'kind':      'empty',
                'dest':      old_dest_for_kind.get('move') or old_dest_for_kind.get('empty'),
                'dest_stem': r.get('dest_stem'),
                'lines':     [],
            })
        r['outcomes'] = new_outcomes

    # #98 — Final display-cap pass. Dedupe ran on full lists so cross-row
    # duplicates beyond the first 20 lines are caught; now apply truncation
    # to keep portal payload size bounded.
    _MOVE_CAP = 20
    _WT_CAP = 10
    _LOST_CAP = 20
    _DEST_CAP = 20
    for r in results:
        r['moved_lines']      = r.get('moved_lines', [])[:_MOVE_CAP]
        r['dest_lines']       = r.get('dest_lines', [])[:_DEST_CAP]
        r['truly_lost_lines'] = r.get('truly_lost_lines', [])[:_LOST_CAP]
        r['went_to_details']  = {k: v[:_WT_CAP]
                                 for k, v in (r.get('went_to_details') or {}).items()}
        for o in r.get('outcomes') or []:
            kind = o.get('kind')
            if kind == 'move' or kind == 'anomaly':
                o['lines'] = o.get('lines', [])[:_MOVE_CAP]
            elif kind == 'went-to':
                o['lines'] = o.get('lines', [])[:_WT_CAP]
            elif kind == 'lost':
                o['lines'] = o.get('lines', [])[:_LOST_CAP]

    return results


def _py_invariant_violations(results: list[dict], cross_row_issues: list[str]) -> list[dict]:
    """Check the #86 mental-model invariants on a classified result set.

    Returns a list of violation dicts (empty list = clean). Production callers
    log these to quality-log.jsonl so drift surfaces on the next sweep without
    waiting for tests to catch it. Mirrors assertions in test_invariants.py
    (kept independent to avoid making tests a runtime dep).
    """
    violations: list[dict] = []
    valid_kinds = {'move', 'went-to', 'lost', 'anomaly', 'empty'}

    # INV-4 — outcomes shape
    for r in results:
        idx = r.get('idx')
        outcomes = r.get('outcomes')
        if not isinstance(outcomes, list) or not outcomes:
            violations.append({'inv': 'INV-4', 'idx': idx,
                               'detail': 'outcomes missing or empty'})
            continue
        for o in outcomes:
            if not isinstance(o, dict) or 'kind' not in o or 'lines' not in o:
                violations.append({'inv': 'INV-4', 'idx': idx,
                                   'detail': f'malformed outcome: {o!r}'[:200]})
                continue
            if o['kind'] not in valid_kinds:
                violations.append({'inv': 'INV-4', 'idx': idx,
                                   'detail': f'invalid kind: {o["kind"]!r}'})
            if o['kind'] == 'lost':
                if o.get('dest') is not None or o.get('dest_stem') is not None:
                    violations.append({'inv': 'INV-4', 'idx': idx,
                                       'detail': 'lost outcome has non-null dest/dest_stem'})
            elif o.get('dest_stem') is None:
                violations.append({'inv': 'INV-4', 'idx': idx,
                                   'detail': f'non-lost outcome missing dest_stem (kind={o["kind"]})'})

    # INV-5 — outcomes ↔ legacy parity (within truncation caps)
    for r in results:
        idx = r.get('idx')
        outs = r.get('outcomes') or []
        moved_legacy = len(r.get('moved_lines') or [])
        wt_legacy = sum(len(v) for v in (r.get('went_to_details') or {}).values())
        lost_legacy = len(r.get('truly_lost_lines') or [])
        moved_o = sum(len(o['lines']) for o in outs if o['kind'] == 'move')
        wt_o    = sum(len(o['lines']) for o in outs if o['kind'] == 'went-to')
        lost_o  = sum(len(o['lines']) for o in outs if o['kind'] == 'lost')
        if moved_legacy <= 20 and moved_o != moved_legacy:
            violations.append({'inv': 'INV-5', 'idx': idx,
                               'detail': f'move parity: outcomes={moved_o} legacy={moved_legacy}'})
        if wt_legacy <= 10 and wt_o != wt_legacy:
            violations.append({'inv': 'INV-5', 'idx': idx,
                               'detail': f'went-to parity: outcomes={wt_o} legacy={wt_legacy}'})
        if lost_legacy <= 20 and lost_o != lost_legacy:
            violations.append({'inv': 'INV-5', 'idx': idx,
                               'detail': f'lost parity: outcomes={lost_o} legacy={lost_legacy}'})

    # INV-6 — dedupe non-duplication when ≥1 inferred (move-outcomes only)
    move_owners: dict[tuple[str, str], list[tuple[int, bool]]] = {}
    for r in results:
        idx = r.get('idx')
        inferred = bool(r.get('inferred'))
        for o in (r.get('outcomes') or []):
            if o.get('kind') != 'move':
                continue
            stem = o.get('dest_stem')
            if not stem:
                continue
            for line in o.get('lines', []):
                key = (stem, _norm_line(line))
                move_owners.setdefault(key, []).append((idx, inferred))
    for (stem, norm), entries in move_owners.items():
        distinct_idxs = sorted({i for i, _ in entries})
        if len(distinct_idxs) < 2:
            # Within-row duplicates (same line appearing twice in one row's moves)
            # are not a cross-row dedupe miss — out of scope for INV-6.
            continue
        if any(inferred for _, inferred in entries):
            violations.append({'inv': 'INV-6', 'idxs': distinct_idxs,
                               'detail': f'dedupe missed at stem={stem[:40]!r}: {norm[:80]!r}'})

    # INV-7 — no phantom losses (line_statuses[lost] ⊆ truly_lost_lines for demoted rows)
    for r in results:
        if 'dedupe_demoted' not in (r.get('issues') or []):
            continue
        idx = r.get('idx')
        truly_lost_norms = {_norm_line(l) for l in (r.get('truly_lost_lines') or [])}
        for n, status in (r.get('line_statuses') or {}).items():
            if status == 'lost' and n not in truly_lost_norms:
                violations.append({'inv': 'INV-7', 'idx': idx,
                                   'detail': f'phantom lost line_status without truly_lost entry: {n[:80]!r}'})

    # INV-8 — breadcrumb_idx == idx (1:1 staged shape)
    for r in results:
        idx = r.get('idx')
        if 'breadcrumb_idx' not in r:
            violations.append({'inv': 'INV-8', 'idx': idx, 'detail': 'breadcrumb_idx missing'})
        elif r['breadcrumb_idx'] != idx:
            violations.append({'inv': 'INV-8', 'idx': idx,
                               'detail': f'breadcrumb_idx={r["breadcrumb_idx"]} != idx={idx}'})

    # INV-9 — V-C2/V-C3 issues include dest stem context
    for issue in (cross_row_issues or []):
        if issue.startswith('V-C2') and ' at ' not in issue:
            violations.append({'inv': 'INV-9', 'detail': f'V-C2 missing stem: {issue[:120]!r}'})
        elif issue.startswith('V-C3') and ' to ' not in issue:
            violations.append({'inv': 'INV-9', 'detail': f'V-C3 missing stem: {issue[:120]!r}'})

    return violations


def _py_cross_row_issues(pre_classification: list[dict]) -> list[str]:
    """Detect cross-row consistency issues from PRE_CLASSIFICATION at compile time.
    Replaces JS validateCrossRowConsistency. Returns list of human-readable issue strings.
    V-C2: same dest line claimed as moved by two move-rows targeting the same dest stem.
    V-C3: same source line moved by two rows targeting the same dest stem (duplicated source).
    Both checks now scope on (dest_stem, normLine) — different destinations no longer
    collide on identical content (e.g. shared frontmatter is no longer flagged).
    """
    issues: list[str] = []
    # (dest_stem, normLine) → [idx, ...] — only move-outcome rows participate.
    dest_line_owners: dict[tuple[str, str], list[int]] = {}
    src_line_owners:  dict[tuple[str, str], list[int]] = {}

    for pc in pre_classification:
        idx = pc.get('idx')
        if idx is None:
            continue
        # Walk per-outcome data. Only move-outcomes can collide cross-row.
        for o in (pc.get('outcomes') or []):
            if o.get('kind') != 'move':
                continue
            stem = o.get('dest_stem') or pc.get('dest_stem') or ''
            if not stem:
                continue
            for sl in o.get('lines', []):
                n = _norm_line(sl)
                if len(n) > 4:
                    src_line_owners.setdefault((stem, n), []).append(idx)
        # Dest_lines collisions are about the destination side (what's at dest).
        # Read from legacy dest_lines for now — it tracks move-outcome dest content.
        stem = pc.get('dest_stem', '')
        if not stem:
            continue
        for dl in pc.get('dest_lines', []):
            n = _norm_line(dl)
            if len(n) > 4:
                dest_line_owners.setdefault((stem, n), []).append(idx)

    for (stem, n), idxs in dest_line_owners.items():
        unique = sorted(set(idxs))
        if len(unique) > 1:
            issues.append(f'V-C2: dest line claimed by rows {unique} at {stem[:30]}: {n[:60]}')

    for (stem, n), idxs in src_line_owners.items():
        unique = sorted(set(idxs))
        if len(unique) > 1:
            issues.append(f'V-C3: src line moved by rows {unique} to {stem[:30]}: {n[:60]}')

    return issues


def _quality_log_path(root: Path) -> Path:
    return root / "sweeps" / "quality-log.jsonl"


def _resolution_cache_path(root: Path) -> Path:
    return root / "sweeps" / "resolutions.jsonl"


def _append_quality_log(root: Path, run_id: str, counts: dict, problems: list) -> None:
    """Append one structured entry per audit run to quality-log.jsonl."""
    from datetime import datetime as _dt
    entry = {
        "run_id": run_id,
        "generated_at": _dt.now().isoformat(timespec='seconds'),
        "by_type": counts,
        "total": sum(counts.values()),
        "issues": [
            {
                "source": row.get("source_file", ""),
                "section": row.get("section", ""),
                "dest": row.get("destination", ""),
                "type": result["type"],
                "issue_tags": result.get("issues", []),
                "lost_count": len(result.get("lost", [])),
                "new_count": len(result.get("new", [])),
                "already_present_count": len(result.get("already_present", [])),
                "lost_lines": result.get("lost", [])[:3],
                "new_lines": result.get("new", [])[:3],
            }
            for row, result in problems
        ],
    }
    log_path = _quality_log_path(root)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def _load_resolutions(root: Path) -> set:
    """Load the set of (source_file, section, dest) tuples marked as resolved."""
    path = _resolution_cache_path(root)
    resolved = set()
    if not path.exists():
        return resolved
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
            resolved.add((e.get('source', ''), e.get('section', ''), e.get('dest', '')))
        except Exception:
            pass
    return resolved


# sweep-review-quality
def cmd_sweep_review_quality(args) -> None:
    """Read quality-log.jsonl across all runs and surface patterns + suggested fixes."""
    root = _np_root()
    log_path = _quality_log_path(root)

    if not log_path.exists():
        utils.err("No quality log found. Run sweep-review-audit first.")
        sys.exit(utils.EXIT_NOT_FOUND)

    entries = []
    for line in log_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass

    if not entries:
        print("Quality log is empty.")
        return

    resolutions = _load_resolutions(root)

    # Aggregate across all runs
    total_runs = len(entries)
    all_issues = [i for e in entries for i in e.get('issues', [])]
    # Filter out resolved rows
    open_issues = [
        i for i in all_issues
        if (i['source'], i['section'], i['dest']) not in resolutions
    ]

    # Count by type and tag
    from collections import Counter, defaultdict
    type_counts = Counter(i['type'] for i in open_issues)
    tag_counts  = Counter(t for i in open_issues for t in i.get('issue_tags', []))

    # Top recurring anomaly destinations
    anomaly_dests  = Counter(i['dest'] for i in open_issues if i['type'] == 'anomaly')
    # Top recurring lost sections
    lost_sections  = Counter(i['section'] for i in open_issues if i['type'] == 'lost')
    # Sections where dest_not_in_diff — likely sectionHeaderMatches false match
    fp_sections    = Counter(
        i['section'] for i in open_issues if 'dest_not_in_diff' in i.get('issue_tags', [])
    )

    sep = '─' * 64
    print(f"Sweep quality report — {total_runs} run(s) in log")
    print(sep)

    # Summary
    print(f"  Open issues across all runs: {len(open_issues)}")
    print(f"  Resolved (suppressed):       {len(all_issues) - len(open_issues)}")
    print(f"  By type:  " + "  ".join(f"{t}: {n}" for t, n in type_counts.most_common()))
    if tag_counts:
        print(f"  By tag:   " + "  ".join(f"{t}: {n}" for t, n in tag_counts.most_common(5)))
    print(sep)

    # Anomaly hotspots — destinations that repeatedly receive untraced additions
    if anomaly_dests:
        print("\n  Anomaly hotspots (recurring + destinations with no source trace):")
        for dest, n in anomaly_dests.most_common(5):
            dest_clean = re.sub(r'\[\[([^\]]+)\]\]', r'\1', dest).strip()
            print(f"    + {dest_clean}  ({n}×)")
        print(f"\n  → These destinations may need their own breadcrumb rows, or the")
        print(f"    anomaly lines are from a different source file not yet covered.")

    # Lost section hotspots
    if lost_sections:
        print("\n  Lost section hotspots (sections that repeatedly lose lines):")
        for sect, n in lost_sections.most_common(5):
            print(f"    ✗ {sect}  ({n}×)")
        print(f"\n  → Check if these sections are being split during sweep.")
        print(f"    If the lines are truly lost, run /noteplan-manager:sweep-remediate.")

    # False positive patterns (dest_not_in_diff → portal showed row but dest wasn't modified)
    if fp_sections:
        print("\n  Likely false positives (dest not in diff — breadcrumb but no dest change):")
        for sect, n in fp_sections.most_common(5):
            print(f"    ⚠ {sect}  ({n}×)")
        print(f"\n  → These rows may be from stale breadcrumbs or mismatched section names.")
        print(f"    Code location: sectionHeaderMatches() in sweep_review.py")
        print(f"    Check: does the section name in the breadcrumb match any ## header in the diff?")

    # Per-run trend
    print(f"\n{sep}")
    print("  Trend (newest first):")
    for e in reversed(entries[-5:]):
        t = e.get('by_type', {})
        run_open = [i for i in e.get('issues', [])
                    if (i['source'], i['section'], i['dest']) not in resolutions]
        print(f"    {e['run_id']}  total={e['total']}  "
              f"✓{t.get('move',0)} ✗{t.get('lost',0)} +{t.get('anomaly',0)} "
              f"open_issues={len(run_open)}")

    # --show-fp-patterns: break down rows by false-positive pattern category
    if getattr(args, 'show_fp_patterns', False):
        # Tag → pattern label + description
        FP_PATTERNS = {
            'new_file':       ('B-14 new_file',       'Newly created dest — additions are boilerplate'),
            'b15_redirect':   ('B-15 redirect_stub',  'Dest is a migration stub; content reached linked plan'),
            'disk_confirmed': ('B-16 retroactive',    'Content swept in prior run; confirmed on disk'),
            'dest_not_in_diff': ('V-47 scope_miss',   'Section header not in diff hunk; full-file fallback'),
            'src_not_in_diff':  ('src_missing',       'Source calendar not in diff for this sweep'),
        }
        # Collect: tag → list of (run_id, source, section, dest)
        pattern_rows: dict = {k: [] for k in FP_PATTERNS}
        cross_row_count = 0
        for e in entries:
            rid = e['run_id']
            for i in e.get('issues', []):
                tags = set(i.get('issue_tags', []))
                matched = False
                for tag, (label, _) in FP_PATTERNS.items():
                    if tag in tags:
                        pattern_rows[tag].append((rid, i['source'], i['section']))
                        matched = True
                # Cross-row: anomaly rows where B-13 subtracted all additions
                if not matched and i['type'] == 'anomaly':
                    cross_row_count += 1

        print(f"\n{sep}")
        print("  False-positive pattern breakdown (--show-fp-patterns):")
        any_pattern = False
        for tag, (label, desc) in FP_PATTERNS.items():
            rows = pattern_rows[tag]
            if not rows:
                continue
            any_pattern = True
            # Count by run
            run_hits = Counter(r for r, _, _ in rows)
            top_runs = ', '.join(f"{r}×{n}" for r, n in run_hits.most_common(3))
            print(f"\n    [{label}]  {len(rows)} row(s)  —  {desc}")
            print(f"    Runs: {top_runs}")
            for _, src, sec in rows[:3]:
                print(f"      {src.split('/')[-1]}  §  {sec[:60]}")
            if len(rows) > 3:
                print(f"      … {len(rows)-3} more")
        if cross_row_count:
            print(f"\n    [B-13 cross_row]  {cross_row_count} row(s)  —  Dest additions claimed by sibling rows")
        if not any_pattern and not cross_row_count:
            print("    No false-positive patterns found in log.")
        # Dominant pattern
        all_counts = {tag: len(rows) for tag, rows in pattern_rows.items() if rows}
        if cross_row_count:
            all_counts['B-13 cross_row'] = cross_row_count
        if all_counts:
            dominant = max(all_counts, key=all_counts.get)
            label = FP_PATTERNS.get(dominant, (dominant,))[0] if dominant in FP_PATTERNS else dominant
            print(f"\n    Dominant pattern: {label} ({all_counts[max(all_counts, key=all_counts.get)]} rows)")

    print(f"\n  To mark a row as resolved/intentional, run:")
    print(f"    noteplan-sweep sweep-review-resolve <run_id> <section>")
    print(f"  To remediate open issues:")
    print(f"    /noteplan-manager:sweep-remediate")


# sweep-review-resolve
def cmd_sweep_review_resolve(args) -> None:
    """Mark a (source × section × dest) tuple as resolved so it won't re-appear in quality reports."""
    root = _np_root()
    log_path = _quality_log_path(root)

    if not log_path.exists():
        utils.err("No quality log found. Run sweep-review-audit first.")
        sys.exit(utils.EXIT_NOT_FOUND)

    # Find matching issues in the log
    run_id = args.run_id
    section_query = args.section.lower().strip()

    matches = []
    for line in log_path.read_text(encoding='utf-8').splitlines():
        try:
            e = json.loads(line)
            if e.get('run_id') != run_id:
                continue
            for i in e.get('issues', []):
                if section_query in i.get('section', '').lower():
                    matches.append(i)
        except Exception:
            pass

    if not matches:
        utils.err(f"No issues found matching run={run_id!r} section={section_query!r}")
        sys.exit(utils.EXIT_NOT_FOUND)

    from datetime import datetime as _dt
    res_path = _resolution_cache_path(root)
    res_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with res_path.open('a', encoding='utf-8') as f:
        for i in matches:
            entry = {
                "source": i['source'], "section": i['section'], "dest": i['dest'],
                "resolved_at": _dt.now().isoformat(timespec='seconds'),
                "run_id": run_id, "reason": args.reason or "intentional",
            }
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            written += 1

    utils.log(f"sweep-review-resolve: marked {written} issue(s) as resolved in {res_path}")


# ---------------------------------------------------------------------------
# sweep-diff-coverage  (#70)
# ---------------------------------------------------------------------------

def cmd_sweep_diff_coverage(args) -> None:
    """Per-source-file coverage report: breadcrumb count vs removed lines in diff.
    Files with ratio < 0.5 are flagged as thin-coverage (B-16 retroactive sweep risk)."""
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
    snap_path = sweeps / f"{run_id}.snapshot.html"
    if not snap_path.exists():
        utils.err(f"Snapshot not found: {snap_path}")
        sys.exit(utils.EXIT_NOT_FOUND)

    html = snap_path.read_text(encoding="utf-8")
    diff_text = _extract_js_str(html, "DIFF_TEXT")
    narrative = _extract_js_val(html, "NARRATIVE")

    if not narrative:
        print("No narrative rows found.")
        return

    from collections import Counter, defaultdict

    breadcrumb_count: Counter = Counter()
    for row in narrative:
        src = row.get("source_file", "").split("/")[-1]
        if src:
            breadcrumb_count[src] += 1

    removed_per_file: defaultdict = defaultdict(int)
    cur_file = None
    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            cur_file = raw.split("/")[-1].split()[0] if raw.split("/") else None
        elif cur_file and raw and raw[0] == "-" and not raw.startswith("---"):
            removed_per_file[cur_file] += 1

    base_m = re.search(r"<!-- base_commit: ([0-9a-f]{7,40}) -->", html)
    sha_m = re.search(r"sha:\s*([0-9a-f]{7,40})", html)
    diff_range = ""
    if base_m and sha_m:
        diff_range = f"{base_m.group(1)[:7]}..{sha_m.group(1)[:7]}"

    print(f"\nSweep diff coverage — {run_id}{(' (' + diff_range + ')') if diff_range else ''}")
    print(f"{'File':<30} {'Breadcrumbs':>12} {'Removed':>8} {'Ratio':>6}  Status")
    print("-" * 65)

    total_thin = 0
    for src_file in sorted(breadcrumb_count.keys()):
        count = breadcrumb_count[src_file]
        removed = removed_per_file.get(src_file, 0)
        ratio = removed / count if count else 0.0
        thin = ratio < 0.5
        if thin:
            total_thin += 1
        status = "⚠  THIN (B-16 risk)" if thin else "✓"
        print(f"{src_file:<30} {count:>12} {removed:>8} {ratio:>6.2f}  {status}")

    print("-" * 65)
    total_rows = sum(breadcrumb_count.values())
    total_removed = sum(removed_per_file.get(f, 0) for f in breadcrumb_count)
    overall = total_removed / total_rows if total_rows else 0.0
    print(f"{'TOTAL':<30} {total_rows:>12} {total_removed:>8} {overall:>6.2f}  "
          f"{'⚠  ' + str(total_thin) + ' file(s) thin' if total_thin else '✓ all OK'}")
    if total_thin:
        print("\nThin files: source section removals not captured in diff.")
        print("Root cause: sweep committed sections in a prior run (retroactive breadcrumbing).")
        print("Impact: portal audit uses disk-confirmation (B-16) to classify these as empty.")


# ---------------------------------------------------------------------------
# sweep-review-diagnose  (#70)
# ---------------------------------------------------------------------------

def cmd_sweep_review_diagnose(args) -> None:
    """Per-row diagnostic: source diff coverage, section match, anomaly root cause.
    Prints a breakdown for every row (or just --section NAME) in a snapshot."""
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
    snap_path = sweeps / f"{run_id}.snapshot.html"
    if not snap_path.exists():
        utils.err(f"Snapshot not found: {snap_path}")
        sys.exit(utils.EXIT_NOT_FOUND)

    html = snap_path.read_text(encoding="utf-8")
    diff_text = _extract_js_str(html, "DIFF_TEXT")
    narrative = _extract_js_val(html, "NARRATIVE")

    if not narrative:
        print("No narrative rows found.")
        return

    section_filter = (args.section or "").lower().strip()
    show_only = args.show or "all"  # "all" | "anomaly" | "empty" | "move" | "lost"

    # Build global removed norms (B-13 layer 2)
    _global_removed_norms: set = set()
    for raw in diff_text.splitlines():
        if raw.startswith("-") and len(raw) > 1 and not raw.startswith("---"):
            n = _norm_line(raw[1:])
            if len(n) > 5:
                _global_removed_norms.add(n)

    # Build sibling norms (B-13 layer 1) per dest stem
    _sibling_norms: dict = {}
    for row in narrative:
        dest_raw = re.sub(r"\[\[([^\]]+)\]\]", r"\1", row.get("destination", "")).strip()
        dest_raw = re.sub(r"\.md$", "", dest_raw).strip()
        sec = re.sub(r"^#+\s*", "", row.get("section", "")).strip()
        src = row.get("source_file", "").split("/")[-1]
        lines = _extract_section_lines(diff_text, src, sec, "-")
        norms = {_norm_line(l) for l in lines if not _is_noise(l) and len(_norm_line(l)) > 2}
        _sibling_norms.setdefault(dest_raw, set()).update(norms)

    print(f"\nSweep diagnose — {run_id}  ({len(narrative)} rows)")
    print("=" * 70)
    shown = 0

    for idx, row in enumerate(narrative):
        section = re.sub(r"^#+\s*", "", row.get("section", "")).strip()
        if section_filter and section_filter not in section.lower():
            continue

        src_file = row.get("source_file", "").split("/")[-1]
        dest_raw = re.sub(r"\[\[([^\]]+)\]\]", r"\1", row.get("destination", "")).strip()
        dest_raw = re.sub(r"\.md$", "", dest_raw).strip()

        # Source diff analysis
        src_all_removed = _extract_section_lines(diff_text, src_file, None, "-")
        src_sec_removed = _extract_section_lines(diff_text, src_file, section, "-")

        # Check if section header appears anywhere in the source file's diff block
        base = src_file.lower()
        hdr_in_diff = False
        in_src = False
        for raw in diff_text.splitlines():
            if raw.startswith("diff --git "):
                in_src = base in raw.lower()
                continue
            if not in_src:
                continue
            if raw and raw[0] in ("+", "-", " "):
                content = raw[1:]
                hm = re.match(r"^(#+)\s", content)
                if hm and section.lower() in re.sub(r"^#+\s*", "", content).strip().lower():
                    hdr_in_diff = True
                    break

        dest_added = _extract_section_lines(diff_text, dest_raw + ".md", None, "+")
        scope_method = "full-file"

        # B-13 filtering
        sibling_norms = _sibling_norms.get(dest_raw, set())
        unclaimed = [
            l for l in dest_added
            if not _is_noise(l) and len(_norm_line(l)) > 2
            and _norm_line(l) not in sibling_norms
            and _norm_line(l) not in _global_removed_norms
        ]

        # B-14: dest is a new file — all additions are boilerplate/sweep content, not anomalous
        dest_stem_lower = (dest_raw.split("/")[-1] + ".md").lower()
        dest_is_new = any(
            "new file mode" in blk
            for blk in re.split(r"(?=diff --git )", diff_text)
            if dest_stem_lower in blk.lower()
        )

        # Disk confirmation (B-16) — also try Calendar directory for calendar-dest rows
        disk_confirmed = None
        dest_file_path = _find_dest_on_disk(root, dest_raw)
        if dest_file_path is None:
            cal_path = root / "Calendar" / f"{dest_raw}.md"
            if cal_path.exists():
                dest_file_path = cal_path
        if unclaimed and dest_file_path:
            dest_text = dest_file_path.read_text(errors="replace")
            dest_file_norms = {_norm_line(l) for l in dest_text.splitlines()
                               if len(_norm_line(l)) > 4}
            unconfirmed = [
                l for l in unclaimed
                if not any(_fuzzy_match(_norm_line(l), dn) for dn in dest_file_norms)
            ]
            disk_confirmed = not bool(unconfirmed)
        elif not unclaimed:
            disk_confirmed = True  # nothing to confirm

        # Classify + root cause
        removed_countable = [l for l in src_sec_removed
                             if not _is_noise(l) and len(_norm_line(l)) > 2]
        if not removed_countable:
            if dest_is_new:
                classification = "empty [new_file]"
                root_cause = "B-14 — dest was newly created in this sweep; additions are boilerplate"
            elif not dest_added:
                classification = "empty"
                root_cause = "source and dest both empty in diff"
            elif not unclaimed:
                classification = "empty"
                root_cause = "B-13 (all dest additions claimed by siblings/global removed)"
            elif disk_confirmed:
                classification = "empty [disk_confirmed]"
                root_cause = "B-16 retroactive sweep — sections moved in prior run"
            else:
                classification = "anomaly"
                if not hdr_in_diff and len(src_all_removed) < 3:
                    root_cause = "B-16? (section header absent from diff, very thin source diff)"
                elif not hdr_in_diff:
                    root_cause = "V-47 scope miss (section header not in diff hunk context)"
                else:
                    root_cause = "genuine anomaly — dest has additions with no traceable source"
        else:
            classification = "move/lost (see audit)"
            root_cause = "source removals found — classified by classifyDestLines"

        if show_only != "all":
            if show_only == "anomaly" and "anomaly" not in classification:
                continue
            elif show_only in ("empty", "move", "lost") and show_only not in classification:
                continue

        shown += 1
        src_coverage = f"{len(src_sec_removed)}/{len(src_all_removed)} lines" if src_all_removed else "0 lines"
        print(f"\n[{idx:02d}] {section}")
        print(f"      src={src_file}  dest={dest_raw}")
        print(f"      source:  hdr_in_diff={hdr_in_diff}  sec_removed={len(src_sec_removed)}  total_removed={len(src_all_removed)}")
        print(f"      dest:    scope={scope_method}  added={len(dest_added)}  unclaimed={len(unclaimed)}")
        print(f"      confirm: disk_confirmed={disk_confirmed}")
        print(f"      ▶ {classification}  —  {root_cause}")

    print(f"\n{'-'*70}")
    print(f"Showed {shown}/{len(narrative)} rows"
          + (f" matching section={section_filter!r}" if section_filter else "")
          + (f" filter={show_only}" if show_only != "all" else ""))


# ---------------------------------------------------------------------------
# sweep-review-diff-range  (#71)
# ---------------------------------------------------------------------------

def cmd_sweep_review_diff_range(args) -> None:
    """Show the git diff range stored in a snapshot and the commits it covers."""
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
    snap_path = sweeps / f"{run_id}.snapshot.html"
    if not snap_path.exists():
        utils.err(f"Snapshot not found: {snap_path}")
        sys.exit(utils.EXIT_NOT_FOUND)

    html = snap_path.read_text(encoding="utf-8")
    base_m = re.search(r"<!-- base_commit: ([0-9a-f]{7,40}) -->", html)
    sha_m = re.search(r"sha:\s*([0-9a-f]{7,40})", html)

    print(f"\nSnapshot: {run_id}")
    if not base_m:
        print("  base_commit: not stored (snapshot generated before v3.100.7)")
        print("  Upgrade: re-run sweep-review-generate to embed base_commit.")
        return

    base = base_m.group(1)
    head = sha_m.group(1) if sha_m else "unknown"
    print(f"  diff range: {base[:7]}..{head[:7]}")
    print(f"  base_commit (full): {base}")
    print(f"  head_sha:           {head}")

    log_r = _git(["log", "--oneline", f"{base}..{head}"], cwd=root)
    if log_r.returncode == 0 and log_r.stdout.strip():
        commits = log_r.stdout.strip().splitlines()
        print(f"\n  Commits in range ({len(commits)}):")
        for c in commits:
            print(f"    {c}")
    else:
        print("\n  No commits found in range (range may be stale or already squashed).")

    # Show which calendar files changed in range
    cal_r = _git(["diff", "--name-only", f"{base}..{head}", "--", "Calendar/*.md"], cwd=root)
    if cal_r.returncode == 0 and cal_r.stdout.strip():
        cal_files = cal_r.stdout.strip().splitlines()
        print(f"\n  Calendar files in range ({len(cal_files)}):")
        for f in cal_files:
            print(f"    {f}")

    # Warn about thin-coverage files
    diff_text = _extract_js_str(html, "DIFF_TEXT")
    narrative = _extract_js_val(html, "NARRATIVE")
    from collections import Counter
    bc: Counter = Counter()
    for row in narrative or []:
        src = row.get("source_file", "").split("/")[-1]
        if src:
            bc[src] += 1
    removed_per: dict = {}
    cur = None
    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            cur = raw.split("/")[-1].split()[0] if "/" in raw else None
        elif cur and raw and raw[0] == "-" and not raw.startswith("---"):
            removed_per[cur] = removed_per.get(cur, 0) + 1
    thin = [(f, bc[f], removed_per.get(f, 0)) for f in bc
            if removed_per.get(f, 0) / bc[f] < 0.5]
    if thin:
        print(f"\n  ⚠  {len(thin)} thin-coverage source file(s) — retroactive sweep likely:")
        print(f"     (sections were moved in a PRIOR run, not captured in {base[:7]}..{head[:7]})")
        for f, cnt, rem in thin:
            print(f"     {f}: {cnt} breadcrumbs, {rem} removed lines")
        print(f"\n  Fix options:")
        print(f"     1. Use audit disk-confirmation (B-16) — already active, 0 anomalies.")
        print(f"     2. Re-generate with wider --base-commit to cover prior sweep commits.")
        print(f"     3. Squash all sweep commits: git rebase -i {base[:7]} (loses granularity).")


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
